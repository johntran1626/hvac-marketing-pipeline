"""Offline Calls contract tests. API-example variations are synthetic."""
from copy import deepcopy
from dataclasses import asdict, FrozenInstanceError
from decimal import Decimal
import json
from pathlib import Path
import unittest

from scripts.normalization.calls import (
    CallNormalizationError, LeadRule, normalize_call_row, aggregate_calls,
)
from scripts.reconcile_calls import reconcile_calls_snapshot

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = json.loads((ROOT / "tests/fixtures/calls-api-example.json").read_text())["response"]["data"][0]


class CallsNormalizationTests(unittest.TestCase):
    def raw(self, **changes):
        row = deepcopy(EXAMPLE)
        row.update(changes)
        return row

    def call(self, **changes):
        return normalize_call_row(self.raw(**changes))

    def test_documented_api_example_preserves_call_observations(self):
        row = self.call()
        self.assertEqual(row.raw_key, "call_0003685")
        self.assertEqual(row.analysis_date, "2026-09-20")
        self.assertEqual(row.started_at.isoformat(), "2026-09-20T21:45:58+00:00")
        self.assertEqual((row.duration_sec, row.first_time_caller), (720, True))
        self.assertEqual(row.caller_hash, EXAMPLE["caller_hash"])
        self.assertEqual((row.channel, row.source_platform), ("google_ads", "call_tracking"))
        self.assertEqual(row.observed_campaign_id, "20114567803")
        self.assertIsNone(row.brand_classification)
        self.assertEqual(row.attribution_issues, ("unknown_google_campaign",))

    def test_winter_and_summer_midnight_dates_use_central(self):
        pairs = [
            ("2026-01-15T05:59:59Z", "2026-01-14"),
            ("2026-01-15T06:00:00Z", "2026-01-15"),
            ("2026-07-15T04:59:59Z", "2026-07-14"),
            ("2026-07-15T05:00:00Z", "2026-07-15"),
        ]
        for timestamp, day in pairs:
            with self.subTest(timestamp=timestamp):
                self.assertEqual(self.call(started_at=timestamp).analysis_date, day)

    def test_dst_boundaries_follow_timezone_rules(self):
        pairs = [
            ("2026-03-08T05:59:59Z", "2026-03-07"),
            ("2026-03-08T06:00:00Z", "2026-03-08"),
            ("2026-11-01T04:59:59Z", "2026-10-31"),
            ("2026-11-01T05:00:00Z", "2026-11-01"),
        ]
        for timestamp, day in pairs:
            self.assertEqual(self.call(started_at=timestamp).analysis_date, day)

    def test_equivalent_offsets_produce_identical_call_instants(self):
        a = self.call(started_at="2026-09-20T21:45:58Z")
        b = self.call(started_at="2026-09-20T16:45:58-05:00")
        self.assertEqual(a, b)

    def test_naive_invalid_and_missing_timestamps_fail(self):
        for value in ("2026-09-20", "2026-09-20T21:45:58", "invalid",
                      "2026-02-30T00:00:00Z", None, 123):
            with self.subTest(value=value), self.assertRaises(CallNormalizationError):
                self.call(started_at=value)

    def test_duration_requires_nonnegative_integer_with_database_bound(self):
        for value in (-1, True, 1.5, "30", None, Decimal("30"), 2147483648):
            with self.subTest(value=value), self.assertRaises(CallNormalizationError):
                self.call(duration_sec=value)
        for value in (0, 30, 2147483647):
            self.assertEqual(self.call(duration_sec=value).duration_sec, value)

    def test_first_time_flag_requires_real_boolean(self):
        for value in ("true", "false", 0, 1, None):
            with self.subTest(value=value), self.assertRaises(CallNormalizationError):
                self.call(first_time_caller=value)
        self.assertFalse(self.call(first_time_caller=False).first_time_caller)

    def test_every_documented_channel_is_preserved(self):
        for source in ("google_ads", "google_lsa", "meta", "gbp", "website", "direct"):
            row = self.call(source=source, campaign_id="20814455901" if source == "google_ads" else None)
            self.assertEqual(row.channel, source)
            self.assertEqual(row.observed_source, source)
            self.assertEqual(row.attribution_issues, ())

    def test_brand_uses_google_id_without_fabricating_account_or_name(self):
        for campaign, brand in (("20814455901", "brand"), ("20814455917", "non_brand"),
                                ("20814455930", "non_brand"), ("20814455948", "non_brand")):
            row = self.call(campaign_id=campaign)
            self.assertEqual(row.brand_classification, brand)
            self.assertEqual(row.campaign_id, campaign)
            self.assertIsNone(row.source_account_id)
            self.assertIsNone(row.campaign_name)

    def test_missing_unknown_and_other_platform_google_ids_stay_unresolved(self):
        for campaign, issue in ((None, "missing_google_campaign"),
                                ("20114567803", "unknown_google_campaign"),
                                ("120208841937650100", "unknown_google_campaign")):
            row = self.call(campaign_id=campaign)
            self.assertIsNone(row.brand_classification)
            self.assertEqual(row.attribution_issues, (issue,))
            self.assertEqual(row.campaign_id, campaign)

    def test_unknown_source_is_explicitly_unattributed_without_rewriting_raw_label(self):
        row = self.call(source="GOOGLE_ADS", campaign_id=None)
        self.assertEqual(row.channel, "unattributed")
        self.assertEqual(row.observed_source, "GOOGLE_ADS")
        self.assertEqual(row.attribution_issues, ("unknown_source",))

    def test_non_google_campaign_observation_cannot_manufacture_a_join(self):
        for source in ("meta", "direct", "website", "google_lsa", "gbp"):
            row = self.call(source=source, campaign_id="20814455901")
            self.assertEqual(row.observed_campaign_id, "20814455901")
            self.assertIsNone(row.campaign_id)
            self.assertEqual(row.brand_classification, "not_applicable")
            self.assertEqual(row.attribution_issues, ("unsupported_campaign_source",))

    def test_nullable_campaign_is_required_and_malformed_ids_fail(self):
        for value in ("", " ", 123, False):
            with self.assertRaises(CallNormalizationError):
                self.call(campaign_id=value)
        raw = self.raw()
        del raw["campaign_id"]
        with self.assertRaises(CallNormalizationError):
            normalize_call_row(raw)

    def test_required_fields_cannot_be_guessed(self):
        for field in EXAMPLE:
            row = self.raw()
            del row[field]
            with self.subTest(field=field), self.assertRaises(CallNormalizationError):
                normalize_call_row(row)
        for field in ("call_id", "source", "tracking_number", "caller_hash"):
            with self.subTest(field=field), self.assertRaises(CallNormalizationError):
                self.call(**{field: " "})
        with self.assertRaises(CallNormalizationError):
            normalize_call_row([])

    def test_raw_input_is_unchanged_and_output_immutable(self):
        row = self.raw()
        before = deepcopy(row)
        output = normalize_call_row(row)
        self.assertEqual(row, before)
        with self.assertRaises(FrozenInstanceError):
            output.first_time_caller = False

    def test_no_paid_platform_or_crm_or_freshness_metrics_are_invented(self):
        fields = asdict(self.call())
        for field in ("spend_usd", "reported_leads", "unique_leads", "jobs", "revenue_usd",
                      "customer_id", "synced_at", "data_through"):
            self.assertNotIn(field, fields)

    def test_explicit_rule_is_required_and_cannot_be_negative_or_coerced(self):
        with self.assertRaises(TypeError):
            aggregate_calls([])
        for value in (-1, True, "30", None, 1.5, 2147483648):
            with self.assertRaises(CallNormalizationError):
                LeadRule(value)
        with self.assertRaises(CallNormalizationError):
            aggregate_calls([], rule=30)

    def test_threshold_zero_and_thirty_have_explicit_boundary_behavior(self):
        for duration in (0, 29, 30, 31):
            row = self.call(duration_sec=duration)
            bare, = aggregate_calls([row], rule=LeadRule(0))
            qualified, = aggregate_calls([row], rule=LeadRule(30))
            self.assertEqual(bare.unique_leads, 1)
            self.assertEqual(qualified.unique_leads, int(duration >= 30))
            self.assertEqual(qualified.min_duration_sec, 30)

    def test_returning_caller_never_becomes_new_even_after_short_first_call(self):
        rows = [
            self.call(duration_sec=10),
            self.call(call_id="call_0003686", duration_sec=720, first_time_caller=False),
        ]
        bare, = aggregate_calls(rows, rule=LeadRule(0))
        qualified, = aggregate_calls(rows, rule=LeadRule(30))
        self.assertEqual((bare.calls, bare.first_time_calls, bare.returning_calls, bare.unique_leads),
                         (2, 1, 1, 1))
        self.assertEqual(qualified.unique_leads, 0)

    def test_duplicate_call_ids_and_restated_records_fail(self):
        a = self.call()
        for b in (a, self.call(duration_sec=30)):
            with self.assertRaisesRegex(CallNormalizationError, "duplicate call_id"):
                aggregate_calls([a, b], rule=LeadRule(30))

    def test_repeated_first_time_hash_fails_across_dates_and_channels(self):
        a = self.call(duration_sec=10)
        variants = [
            self.call(call_id="call_0003686", duration_sec=720),
            self.call(call_id="call_0003686", started_at="2026-09-21T21:45:58Z"),
            self.call(call_id="call_0003686", source="meta", campaign_id=None),
        ]
        for b in variants:
            with self.assertRaisesRegex(CallNormalizationError, "multiple first-time"):
                aggregate_calls([a, b], rule=LeadRule(30))

    def test_returning_call_repetitions_count_calls_not_unique_leads(self):
        rows = [self.call(first_time_caller=False),
                self.call(call_id="call_0003686", first_time_caller=False)]
        daily, = aggregate_calls(rows, rule=LeadRule(0))
        self.assertEqual((daily.calls, daily.returning_calls, daily.unique_leads), (2, 2, 0))

    def test_different_callers_aggregate_once_in_the_same_bucket(self):
        rows = [self.call(campaign_id="20814455901"),
                self.call(call_id="call_0003686", caller_hash=EXAMPLE["caller_hash"] + "2",
                          campaign_id="20814455901")]
        daily, = aggregate_calls(rows, rule=LeadRule(30))
        self.assertEqual((daily.calls, daily.unique_leads), (2, 2))
        self.assertEqual(daily.brand_classification, "brand")

    def test_channels_campaigns_dates_and_unresolved_buckets_stay_separate(self):
        rows = [
            self.call(campaign_id="20814455901"),
            self.call(call_id="call_0003686", campaign_id="20814455917", first_time_caller=False),
            self.call(call_id="call_0003687", source="direct", campaign_id=None, first_time_caller=False),
            self.call(call_id="call_0003688", started_at="2026-09-21T21:45:58Z", first_time_caller=False),
        ]
        daily = aggregate_calls(rows, rule=LeadRule(30))
        self.assertEqual(len(daily), 4)
        self.assertEqual(sum(row.calls for row in daily), 4)
        self.assertEqual(sum(row.unresolved_calls for row in daily), 1)

    def test_unknown_sources_preserve_observed_labels_and_unresolved_counts(self):
        rows = [self.call(source="GOOGLE_ADS", campaign_id=None),
                self.call(call_id="call_0003686", source="META", campaign_id=None, first_time_caller=False)]
        daily, = aggregate_calls(rows, rule=LeadRule(30))
        self.assertEqual(daily.observed_sources, ("GOOGLE_ADS", "META"))
        self.assertEqual((daily.channel, daily.calls, daily.unresolved_calls), ("unattributed", 2, 2))

    def test_empty_generators_order_and_daily_immutability(self):
        self.assertEqual(aggregate_calls([], rule=LeadRule(30)), ())
        rows = [self.call(), self.call(call_id="call_0003686", source="direct",
                                     campaign_id=None, first_time_caller=False)]
        a = aggregate_calls(iter(rows), rule=LeadRule(30))
        b = aggregate_calls(reversed(rows), rule=LeadRule(30))
        self.assertEqual(a, b)
        with self.assertRaises(FrozenInstanceError):
            a[0].calls = 0
        with self.assertRaises(CallNormalizationError):
            aggregate_calls([EXAMPLE], rule=LeadRule(30))
        with self.assertRaises(CallNormalizationError):
            aggregate_calls(a, rule=LeadRule(30))

    def test_full_snapshot_reconciles_every_bucket_under_both_rules(self):
        report = reconcile_calls_snapshot()
        self.assertTrue(report["reconciliation"].startswith("PASS"))
        self.assertEqual(report["raw_rows"], report["distinct_call_ids"])
        self.assertEqual(report["first_time_calls"] + report["returning_calls"], report["raw_rows"])
        self.assertEqual(report["repeated_first_time_hash_groups"], 0)
        self.assertEqual(report["unresolved_attribution_calls"], 0)


if __name__ == "__main__":
    unittest.main()
