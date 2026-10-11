"""Synthetic coverage/resume boundary tests; no live API or database evidence."""
from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, timedelta
import unittest

from scripts.normalization.coverage import (
    CoverageError, SourceScope, DateWindow, PageReceipt, plan_refresh,
    complete_raw_window, complete_normalized_window, complete_refresh,
)

START = date(2024, 10, 1)
THROUGH = date(2026, 10, 6)
RUN = datetime.fromisoformat("2026-10-07T16:00:00+00:00")
RAW_DONE = RUN + timedelta(minutes=1)
FACT_DONE = RUN + timedelta(minutes=2)


class CoverageTests(unittest.TestCase):
    def scope(self, platform="google_ads", scope_id="synthetic-test-dataset"):
        return SourceScope(platform, scope_id)

    def plan(self, platform="google_ads", previous=THROUGH, **changes):
        parameters = dict(history_start=START, api_data_through=THROUGH,
                          previous_data_through=previous, started_at=RUN)
        parameters.update(changes)
        return plan_refresh(self.scope(platform), **parameters)

    def pages(self, plan, window=None, *, count=3):
        window = window or plan.windows[0]
        return (
            PageReceipt(plan.scope, window, None, "cursor-2", count, True),
            PageReceipt(plan.scope, window, "cursor-2", None, 0, True),
        )

    def normalized(self, plan, window=None, *, count=3, at=FACT_DONE):
        window = window or plan.windows[0]
        raw = complete_raw_window(plan.scope, window, self.pages(plan, window, count=count),
                                  completed_at=RAW_DONE)
        return complete_normalized_window(raw, normalized_at=at, facts_persisted=True)

    def test_google_and_meta_conservative_mutable_window_has_boundary_day(self):
        for platform in ("google_ads", "meta_ads"):
            plan = self.plan(platform)
            self.assertEqual(plan.windows, (DateWindow(date(2026, 9, 29), THROUGH),))
            self.assertEqual((plan.windows[0].end_date - plan.windows[0].start_date).days + 1, 8)

    def test_lsa_thirty_day_credit_boundary_fits_one_request(self):
        plan = self.plan("lsa")
        self.assertEqual(plan.windows, (DateWindow(date(2026, 9, 6), THROUGH),))
        self.assertEqual((plan.windows[0].end_date - plan.windows[0].start_date).days + 1, 31)
        self.assertLessEqual(plan.windows[0].start_date, THROUGH - timedelta(days=30))

    def test_initial_backfill_windows_have_no_gaps_or_overlaps(self):
        plan = self.plan(previous=None)
        self.assertEqual(plan.windows[0].start_date, START)
        self.assertEqual(plan.windows[-1].end_date, THROUGH)
        for left, right in zip(plan.windows, plan.windows[1:]):
            self.assertEqual(right.start_date, left.end_date + timedelta(days=1))
        days = [window.start_date + timedelta(days=offset)
                for window in plan.windows
                for offset in range((window.end_date - window.start_date).days + 1)]
        self.assertEqual(len(days), len(set(days)))
        self.assertEqual(len(days), (THROUGH - START).days + 1)
        self.assertTrue(all((w.end_date - w.start_date).days < 31 for w in plan.windows))

    def test_long_outage_includes_missed_days_before_mutable_window(self):
        plan = self.plan("lsa", previous=date(2026, 7, 1))
        self.assertEqual(plan.windows[0].start_date, date(2026, 6, 1))
        self.assertEqual(plan.windows[-1].end_date, THROUGH)
        self.assertGreater(len(plan.windows), 1)

    def test_recent_gap_also_rereads_mutable_history(self):
        plan = self.plan(previous=date(2026, 10, 3))
        self.assertEqual(plan.windows[0].start_date, date(2026, 9, 26))

    def test_outage_rereads_dates_mutable_at_prior_sync_even_if_now_immutable(self):
        previous = date(2026, 9, 1)
        for platform, lookback in (("google_ads", 7), ("meta_ads", 7), ("lsa", 30)):
            with self.subTest(platform=platform):
                plan = self.plan(platform, previous=previous)
                oldest_mutable = previous - timedelta(days=lookback)
                self.assertEqual(plan.windows[0].start_date, oldest_mutable)
                # A late conversion/credit on the old boundary must still be
                # fetched even though it is outside the current lookback.
                for changed_day in (oldest_mutable, previous):
                    self.assertTrue(any(w.start_date <= changed_day <= w.end_date
                                        for w in plan.windows))
                old_gap_plan = replace(plan, windows=(DateWindow(previous + timedelta(days=1),
                                                               previous + timedelta(days=31)),
                                                     DateWindow(previous + timedelta(days=32), THROUGH)))
                receipts = [self.normalized(old_gap_plan, w) for w in old_gap_plan.windows]
                with self.assertRaises(CoverageError):
                    complete_refresh(old_gap_plan, receipts)

    def test_lookback_clamps_to_source_history_start(self):
        plan = self.plan("lsa", previous=None, history_start=date(2026, 10, 1))
        self.assertEqual(plan.windows, (DateWindow(date(2026, 10, 1), THROUGH),))

    def test_health_availability_bounds_the_plan_independent_of_run_clock(self):
        plan = self.plan(previous=date(2026, 9, 21), api_data_through=date(2026, 9, 22))
        self.assertEqual(plan.windows[-1].end_date, date(2026, 9, 22))
        self.assertLess(plan.windows[-1].end_date, RUN.date())

    def test_invalid_or_regressed_previous_watermark_is_rejected(self):
        for previous in (START - timedelta(days=1), THROUGH + timedelta(days=1), "2026-10-06"):
            with self.subTest(previous=previous), self.assertRaises(CoverageError):
                self.plan(previous=previous)

    def test_scopes_dates_and_timestamps_require_explicit_types(self):
        for platform, token in (("crm", "test"), ("google_ads", ""), ("meta_ads", " ")):
            with self.assertRaises(CoverageError):
                SourceScope(platform, token)
        for changes in ({"history_start": datetime(2024, 10, 1)},
                        {"api_data_through": "2026-10-06"},
                        {"started_at": datetime(2026, 10, 7)}):
            with self.assertRaises(CoverageError):
                self.plan(**changes)

    def test_windows_reject_reversal_and_api_limit_violations(self):
        for start, end in ((date(2026, 10, 7), THROUGH),
                           (date(2026, 9, 5), THROUGH)):
            with self.assertRaises(CoverageError):
                DateWindow(start, end)

    def test_before_history_no_windows_and_no_publishable_freshness(self):
        plan = self.plan(previous=None, api_data_through=START - timedelta(days=1))
        self.assertEqual(plan.windows, ())
        with self.assertRaises(CoverageError):
            complete_refresh(plan, [])

    def test_complete_persisted_chain_counts_rows_and_pages(self):
        plan = self.plan()
        result = complete_raw_window(plan.scope, plan.windows[0], self.pages(plan),
                                     completed_at=RAW_DONE)
        self.assertEqual((result.page_count, result.source_row_count), (2, 3))

    def test_empty_terminal_page_proves_queried_range_without_observed_rows(self):
        plan = self.plan("lsa")
        page = PageReceipt(plan.scope, plan.windows[0], None, None, 0, True)
        raw = complete_raw_window(plan.scope, plan.windows[0], [page], completed_at=RAW_DONE)
        fact = complete_normalized_window(raw, normalized_at=FACT_DONE, facts_persisted=True)
        fresh = complete_refresh(plan, [fact])
        self.assertEqual(fresh.data_through, THROUGH)
        self.assertEqual(fresh.source_row_count, 0)

    def test_no_pages_cannot_be_mistaken_for_an_empty_completed_range(self):
        plan = self.plan()
        with self.assertRaises(CoverageError):
            complete_raw_window(plan.scope, plan.windows[0], [], completed_at=RAW_DONE)

    def test_missing_terminal_page_cannot_advance_coverage(self):
        plan = self.plan()
        with self.assertRaisesRegex(CoverageError, "terminal"):
            complete_raw_window(plan.scope, plan.windows[0], self.pages(plan)[:1],
                                completed_at=RAW_DONE)

    def test_resume_requires_the_durable_first_page_receipt(self):
        plan = self.plan()
        with self.assertRaisesRegex(CoverageError, "gap"):
            complete_raw_window(plan.scope, plan.windows[0], self.pages(plan)[1:],
                                completed_at=RAW_DONE)

    def test_cursor_gaps_cycles_duplicates_and_extra_terminal_pages_fail(self):
        plan = self.plan()
        first, last = self.pages(plan)
        cases = [
            [first, replace(last, request_cursor="missing-cursor")],
            [first, replace(last, next_cursor="cursor-2"), last],
            [first, first, last],
            [replace(first, next_cursor=None), last],
        ]
        for pages in cases:
            with self.subTest(pages=pages), self.assertRaises(CoverageError):
                complete_raw_window(plan.scope, plan.windows[0], pages, completed_at=RAW_DONE)

    def test_empty_or_nonstring_cursors_are_rejected(self):
        plan = self.plan()
        for value in ("", 123, False):
            page = replace(self.pages(plan)[0], next_cursor=value)
            with self.assertRaises(CoverageError):
                complete_raw_window(plan.scope, plan.windows[0], [page], completed_at=RAW_DONE)

    def test_changed_scope_or_date_parameters_are_rejected(self):
        plan = self.plan()
        first, last = self.pages(plan)
        for changed in (
            replace(last, scope=self.scope("meta_ads")),
            replace(last, scope=self.scope(scope_id="other-test-dataset")),
            replace(last, window=DateWindow(date(2026, 10, 1), THROUGH)),
        ):
            with self.assertRaises(CoverageError):
                complete_raw_window(plan.scope, plan.windows[0], [first, changed],
                                    completed_at=RAW_DONE)

    def test_failed_raw_upsert_or_invalid_row_count_fails(self):
        plan = self.plan()
        for changes in ({"raw_persisted": False}, {"raw_persisted": 1},
                        {"row_count": True}, {"row_count": -1}, {"row_count": 1.5}):
            first, last = self.pages(plan)
            with self.assertRaises(CoverageError):
                complete_raw_window(plan.scope, plan.windows[0], [replace(first, **changes), last],
                                    completed_at=RAW_DONE)

    def test_failed_fact_persistence_leaves_raw_success_unpublished(self):
        plan = self.plan()
        raw = complete_raw_window(plan.scope, plan.windows[0], self.pages(plan),
                                  completed_at=RAW_DONE)
        for state in (False, 1):
            with self.assertRaises(CoverageError):
                complete_normalized_window(raw, normalized_at=FACT_DONE, facts_persisted=state)
        with self.assertRaises(CoverageError):
            complete_refresh(plan, [raw])

    def test_normalization_cannot_precede_raw_or_use_naive_time(self):
        plan = self.plan()
        raw = complete_raw_window(plan.scope, plan.windows[0], self.pages(plan),
                                  completed_at=RAW_DONE)
        for at in (RUN, datetime(2026, 10, 7)):
            with self.assertRaises(CoverageError):
                complete_normalized_window(raw, normalized_at=at, facts_persisted=True)

    def test_missing_backfill_window_blocks_source_wide_freshness(self):
        plan = self.plan(previous=None, history_start=date(2026, 8, 1))
        receipts = [self.normalized(plan, window) for window in plan.windows]
        with self.assertRaisesRegex(CoverageError, "incomplete"):
            complete_refresh(plan, receipts[:-1])
        result = complete_refresh(plan, reversed(receipts))
        self.assertEqual(result.data_through, THROUGH)
        self.assertEqual(result.covered_windows, plan.windows)

    def test_duplicate_or_wrong_source_receipts_are_rejected(self):
        plan = self.plan()
        receipt = self.normalized(plan)
        with self.assertRaises(CoverageError):
            complete_refresh(plan, [receipt, receipt])
        other = self.plan("meta_ads")
        with self.assertRaises(CoverageError):
            complete_refresh(plan, [self.normalized(other)])

    def test_old_success_receipt_cannot_make_current_refresh_successful(self):
        plan = self.plan()
        receipt = self.normalized(plan)
        old = replace(receipt, raw=replace(receipt.raw, completed_at=RUN - timedelta(minutes=1)))
        with self.assertRaisesRegex(CoverageError, "stale"):
            complete_refresh(plan, [old])

    def test_malformed_plan_cannot_skip_required_history(self):
        plan = self.plan(previous=None, history_start=date(2026, 8, 1))
        shortened = replace(plan, windows=plan.windows[1:])
        with self.assertRaisesRegex(CoverageError, "contiguous"):
            complete_refresh(shortened, [self.normalized(plan, w) for w in shortened.windows])

    def test_freshness_is_latest_success_time_and_explicit_completed_end(self):
        plan = self.plan(previous=None, history_start=date(2026, 8, 1))
        receipts = [self.normalized(plan, window, at=FACT_DONE + timedelta(minutes=index))
                    for index, window in enumerate(plan.windows)]
        result = complete_refresh(plan, receipts)
        self.assertEqual(result.synced_at, receipts[-1].normalized_at)
        self.assertEqual(result.data_through, plan.api_data_through)
        self.assertEqual(result.scope, plan.scope)
        self.assertEqual(result.source_row_count, sum(r.raw.source_row_count for r in receipts))
        with self.assertRaises(FrozenInstanceError):
            result.data_through = START

    def test_offset_equivalent_success_timestamps_are_compared_as_instants(self):
        plan = self.plan()
        receipt = self.normalized(plan, at=datetime.fromisoformat("2026-10-07T11:02:00-05:00"))
        result = complete_refresh(plan, [receipt])
        self.assertEqual(result.synced_at, FACT_DONE)


if __name__ == "__main__":
    unittest.main()
