"""CRM source/booking-date tests; API-example variations are synthetic."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from decimal import Decimal, localcontext
import json
from pathlib import Path
import unittest

from scripts.normalization.crm import (
    CrmNormalizationError, SourceRules, normalize_crm_row, aggregate_crm, affected_booking_dates,
)
from scripts.reconcile_crm import reconcile_crm_snapshot

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = json.loads((ROOT / "tests/fixtures/crm-api-example.json").read_text())["response"]["data"][0]
POLICY = json.loads((ROOT / "tests/fixtures/crm-source-map-proposed.json").read_text())
RULES = SourceRules(POLICY["version"], POLICY["aliases"])


class CrmTests(unittest.TestCase):
    def raw(self, **changes):
        row = deepcopy(EXAMPLE)
        row.update(changes)
        return row

    def job(self, **changes):
        return normalize_crm_row(self.raw(**changes), rules=RULES)

    def test_documented_example_preserves_booking_day_and_unknown_google_label(self):
        row = self.job()
        self.assertEqual((row.raw_key, row.analysis_date), ("J002145", "2026-09-11"))
        self.assertEqual((row.jobs, row.completed_jobs, row.revenue_usd), (1, 1, Decimal("487.39")))
        self.assertEqual(row.channel, "unattributed")
        self.assertEqual(row.attribution_issues, ("ambiguous_lead_source",))
        self.assertEqual(row.lead_source, "Google")
        self.assertEqual(row.updated_at.isoformat(), "2026-09-22T00:27:00+00:00")

    def test_source_aliases_trim_and_casefold_without_mutating_raw(self):
        row = self.job(lead_source="  gOoGLe AdS  ")
        self.assertEqual(row.channel, "google_ads")
        self.assertEqual(row.lead_source, "  gOoGLe AdS  ")
        self.assertEqual(row.attribution_issues, ())

    def test_explicit_paid_and_nonpaid_source_buckets_stay_separate(self):
        pairs = {"Google Ads": "google_ads", "LSA": "google_lsa", "FB": "meta",
            "maps": "gbp", "webiste": "website", "saw truck": "direct",
            "friend": "referral", "repeat": "existing_customer",
            "plan member": "maintenance_plan", "HOA": "builder_hoa",
            "Yelp": "yelp", "Nextdoor": "nextdoor"}
        for label, channel in pairs.items():
            self.assertEqual(self.job(lead_source=label).channel, channel)

    def test_ambiguous_and_new_labels_are_not_guessed(self):
        for label in ("Google", "googel", "google reviews", "Google Local", "online"):
            self.assertEqual(self.job(lead_source=label).attribution_issues, ("ambiguous_lead_source",))
        row = self.job(lead_source="Google Ads plus referral")
        self.assertEqual(row.channel, "unattributed")
        self.assertEqual(row.attribution_issues, ("unknown_lead_source",))

    def test_null_and_blank_source_are_explicitly_missing(self):
        for value in (None, "", " "):
            self.assertEqual(self.job(lead_source=value).attribution_issues, ("missing_lead_source",))

    def test_mapping_required_immutable_and_conflicts_rejected(self):
        original = {"Google Ads": "google_ads"}
        rules = SourceRules("test", original)
        original["Google Ads"] = "meta"
        self.assertEqual(rules.aliases["google ads"], "google_ads")
        with self.assertRaises(TypeError):
            rules.aliases["google ads"] = "meta"
        for version, aliases in (("", {}), ("test", {"": "direct"}),
                                 ("test", {"google": "unknown_bucket"}),
                                 ("test", {"Google": "google_ads", " google ": "gbp"})):
            with self.assertRaises(CrmNormalizationError):
                SourceRules(version, aliases)
        with self.assertRaises(TypeError):
            normalize_crm_row(self.raw())

    def test_all_noncompleted_states_count_jobs_without_completed_revenue(self):
        for status in ("scheduled", "canceled", "estimate_sold", "estimate_lost"):
            row = self.job(status=status, revenue_usd=None)
            self.assertEqual((row.jobs, row.completed_jobs, row.revenue_usd), (1, 0, Decimal(0)))

    def test_noncompleted_revenue_is_preserved_flagged_and_excluded(self):
        row = self.job(status="scheduled")
        self.assertEqual(row.observed_revenue_usd, Decimal("487.39"))
        self.assertEqual(row.revenue_usd, Decimal(0))
        self.assertEqual(row.quality_issues, ("revenue_on_noncompleted_job",))

    def test_missing_completed_revenue_stays_unknown_in_daily_total(self):
        rows = [self.job(revenue_usd=None), self.job(job_id="J002146")]
        daily, = aggregate_crm(rows)
        self.assertEqual((daily.jobs, daily.completed_jobs), (2, 2))
        self.assertIsNone(daily.revenue_usd)
        self.assertEqual(daily.known_completed_revenue_usd, Decimal("487.39"))
        self.assertEqual(daily.missing_completed_revenue_jobs, 1)

    def test_real_zero_completed_revenue_is_known_zero(self):
        daily, = aggregate_crm([self.job(revenue_usd=0)])
        self.assertEqual(daily.revenue_usd, Decimal(0))
        self.assertEqual(daily.missing_completed_revenue_jobs, 0)

    def test_money_rejects_invalid_values(self):
        for value in (-1, True, "487.39", float("nan"), Decimal("Infinity")):
            with self.assertRaises(CrmNormalizationError):
                self.job(revenue_usd=value)

    def test_decimal_revenue_is_exact_under_low_caller_precision(self):
        a = self.job(revenue_usd=Decimal("123456789.123456789"))
        b = self.job(job_id="J002146", revenue_usd=Decimal("0.000000001"))
        with localcontext() as context:
            context.prec = 2
            daily, = aggregate_crm([a, b])
        self.assertEqual(daily.revenue_usd, Decimal("123456789.123456790"))

    def test_central_midnight_and_dst_dates_preserve_booking_cohort(self):
        pairs = [("2026-01-15T05:59:59Z", "2026-01-14"),
                 ("2026-07-15T04:59:59Z", "2026-07-14"),
                 ("2026-03-08T06:00:00Z", "2026-03-08"),
                 ("2026-11-01T05:00:00Z", "2026-11-01")]
        for timestamp, day in pairs:
            row = self.job(created_at=timestamp, updated_at=timestamp)
            self.assertEqual(row.analysis_date, day)

    def test_invalid_or_naive_timestamps_and_reverse_updates_fail(self):
        for field in ("created_at", "updated_at"):
            for value in ("invalid", "2026-09-11", "2026-09-11T15:55:24", None):
                with self.assertRaises(CrmNormalizationError):
                    self.job(**{field: value})
        with self.assertRaises(CrmNormalizationError):
            self.job(updated_at="2026-09-01T00:00:00Z")

    def test_status_job_type_nullable_fields_and_identifiers_required(self):
        for field in EXAMPLE:
            raw = self.raw()
            del raw[field]
            with self.assertRaises(CrmNormalizationError):
                normalize_crm_row(raw, rules=RULES)
        for field, value in (("status", "unknown"), ("job_type", "unknown"),
                             ("lead_source", 123), ("job_id", " "), ("zip", 77020)):
            with self.assertRaises(CrmNormalizationError):
                self.job(**{field: value})

    def test_raw_is_unchanged_no_person_or_campaign_join_invented(self):
        raw = self.raw()
        before = deepcopy(raw)
        row = normalize_crm_row(raw, rules=RULES)
        self.assertEqual(raw, before)
        self.assertIsNone(row.campaign_id)
        self.assertIsNone(row.source_account_id)
        self.assertEqual(row.brand_classification, "not_applicable")
        with self.assertRaises(FrozenInstanceError):
            row.status = "scheduled"

    def test_multiple_jobs_for_one_customer_are_multiple_jobs(self):
        daily, = aggregate_crm([self.job(), self.job(job_id="J002146")])
        self.assertEqual((daily.jobs, daily.completed_jobs, daily.revenue_usd),
                         (2, 2, Decimal("974.78")))

    def test_old_and_restated_job_versions_must_not_be_added(self):
        old = self.job(status="scheduled", revenue_usd=None)
        new = self.job()
        with self.assertRaisesRegex(CrmNormalizationError, "duplicate job_id"):
            aggregate_crm([old, new])

    def test_mixed_source_dictionary_versions_cannot_be_aggregated(self):
        other = normalize_crm_row(self.raw(job_id="J002146"),
                                 rules=SourceRules("other", POLICY["aliases"]))
        with self.assertRaises(CrmNormalizationError):
            aggregate_crm([self.job(), other])

    def test_same_version_different_dictionary_contents_cannot_mix(self):
        first = normalize_crm_row(self.raw(), rules=SourceRules("same", {"Google": "google_ads"}))
        second = normalize_crm_row(self.raw(job_id="J002146"),
                                   rules=SourceRules("same", {"Google": "gbp"}))
        self.assertNotEqual(first.mapping_fingerprint, second.mapping_fingerprint)
        with self.assertRaisesRegex(CrmNormalizationError, "contents"):
            aggregate_crm([first, second])

    def test_canonical_dictionary_fingerprint_ignores_alias_order_case_and_space(self):
        a = SourceRules("same", {" Google Ads ": "google_ads", "FB": "meta"})
        b = SourceRules("same", {"fb": "meta", "google ads": "google_ads"})
        self.assertEqual(a.fingerprint, b.fingerprint)
        self.assertEqual(aggregate_crm([normalize_crm_row(self.raw(), rules=a)])[0].mapping_fingerprint,
                         a.fingerprint)

    def test_policy_revision_rebuilds_unchanged_source_without_timestamp_conflict(self):
        old = self.job()
        for rules in (SourceRules("next", POLICY["aliases"]),
                      SourceRules("next", {"Google": "google_ads"}),
                      SourceRules(RULES.version, {"Google": "gbp"})):
            new = normalize_crm_row(self.raw(), rules=rules)
            self.assertEqual(affected_booking_dates(old, new), ("2026-09-11",))
            changed_source = normalize_crm_row(self.raw(customer_id="different"), rules=rules)
            with self.assertRaises(CrmNormalizationError):
                affected_booking_dates(old, changed_source)

    def test_booking_days_and_channels_are_distinct_buckets(self):
        rows = [self.job(), self.job(job_id="J002146", lead_source="LSA"),
                self.job(job_id="J002147", created_at="2026-09-12T15:55:24-05:00")]
        self.assertEqual(len(aggregate_crm(rows)), 3)

    def test_empty_generator_order_and_immutable_daily_output(self):
        self.assertEqual(aggregate_crm([]), ())
        rows = [self.job(), self.job(job_id="J002146", lead_source="LSA")]
        self.assertEqual(aggregate_crm(iter(rows)), aggregate_crm(reversed(rows)))
        with self.assertRaises(FrozenInstanceError):
            aggregate_crm(rows)[0].jobs = 0
        with self.assertRaises(CrmNormalizationError):
            aggregate_crm([EXAMPLE])

    def test_late_status_change_rebuilds_original_booking_day(self):
        old = self.job(status="scheduled", revenue_usd=None, updated_at=EXAMPLE["created_at"])
        new = self.job(updated_at="2026-10-07T10:00:00-05:00")
        self.assertEqual(affected_booking_dates(old, new), ("2026-09-11",))
        self.assertEqual(affected_booking_dates(None, new), ("2026-09-11",))

    def test_creation_correction_includes_old_and_new_days(self):
        old = self.job()
        new = self.job(created_at="2026-09-12T15:55:24-05:00",
                       updated_at="2026-10-07T10:00:00-05:00")
        self.assertEqual(affected_booking_dates(old, new), ("2026-09-11", "2026-09-12"))

    def test_incremental_rebuild_rejects_stale_conflicting_and_wrong_jobs(self):
        old = self.job()
        for new in (self.job(updated_at=EXAMPLE["created_at"]), self.job(revenue_usd=0),
                    self.job(job_id="J002146")):
            with self.assertRaises(CrmNormalizationError):
                affected_booking_dates(old, new)
        self.assertEqual(affected_booking_dates(old, old), ("2026-09-11",))

    def test_every_frozen_job_bucket_reconciles(self):
        report = reconcile_crm_snapshot()
        self.assertTrue(report["reconciliation"].startswith("PASS"))
        self.assertEqual(report["raw_rows"], report["distinct_job_ids"])
        self.assertEqual(report["missing_completed_revenue_jobs"], 0)


if __name__ == "__main__":
    unittest.main()
