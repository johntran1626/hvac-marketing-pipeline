"""Daily aggregation tests; API example variations are synthetic."""
from copy import deepcopy
from dataclasses import asdict, FrozenInstanceError, replace
from decimal import Decimal, localcontext
import json
from pathlib import Path
import unittest

from scripts.normalization.daily import aggregate_daily, DailyAggregationError
from scripts.normalization.google import normalize_google_row
from scripts.normalization.lsa import normalize_lsa_row
from scripts.normalization.meta import normalize_meta_row
from scripts.reconcile_daily_aggregation import reconcile_snapshot

ROOT = Path(__file__).resolve().parents[1]
META = json.loads((ROOT / "tests/fixtures/meta-api-cases.json").read_text())["cases"][0]["responses"][0]["data"][0]
GOOGLE = json.loads((ROOT / "tests/fixtures/google-api-example.json").read_text())["response"]["data"][0]
LSA = json.loads((ROOT / "tests/fixtures/lsa-api-example.json").read_text())["response"]["data"][0]


class DailyAggregationTests(unittest.TestCase):
    def meta(self, **changes):
        raw = deepcopy(META)
        raw.update(changes)
        return normalize_meta_row(raw)

    def google(self, **changes):
        raw = deepcopy(GOOGLE)
        raw.update(changes)
        return normalize_google_row(raw)

    def lsa(self, **changes):
        raw = deepcopy(LSA)
        raw.update(changes)
        return normalize_lsa_row(raw)

    def test_empty_input_has_no_invented_zero_days(self):
        self.assertEqual(aggregate_daily([]), ())

    def test_single_row_preserves_dimensions_and_metrics(self):
        source = self.google(campaign_id="20814455901")
        output, = aggregate_daily([source])
        self.assertEqual(output.bucket_key, ("2026-09-01", "google_ads",
            "google_ads", "482-119-3307", "20814455901", "brand"))
        self.assertEqual((output.impressions, output.clicks, output.spend_usd,
                          output.reported_leads), (1314, 53, Decimal("623.277880"), Decimal("9.42")))
        self.assertEqual(output.source_row_count, 1)
        self.assertEqual(output.campaign_names, (source.campaign_name,))

    def test_meta_adsets_sum_to_one_campaign_day(self):
        output, = aggregate_daily([
            self.meta(adset_id="23851234560101", spend="1.23", actions=[{"action_type": "lead", "value": "0.5"}]),
            self.meta(adset_id="23851234560102", spend="2.34", actions=[{"action_type": "lead", "value": "1.25"}]),
        ])
        self.assertEqual(output.analysis_date, META["date_start"])
        self.assertEqual((output.source_row_count, output.impressions, output.clicks,
                          output.spend_usd, output.reported_leads),
                         (2, 1718, 16, Decimal("3.57"), Decimal("1.75")))

    def test_google_adgroups_keep_exact_micros_and_fractional_conversions(self):
        output, = aggregate_daily([
            self.google(ad_group_id="1551230021", cost_micros=1, conversions=Decimal("0.1")),
            self.google(ad_group_id="1551230022", cost_micros=2, conversions=Decimal("0.2")),
        ])
        self.assertEqual(output.spend_usd, Decimal("0.000003"))
        self.assertEqual(output.reported_leads, Decimal("0.3"))
        self.assertEqual(output.source_row_count, 2)

    def test_lsa_current_states_count_each_lead_and_only_charged_spend(self):
        output, = aggregate_daily([
            self.lsa(lead_id="lsa_001455"),
            self.lsa(lead_id="lsa_001456", charge_status="CREDITED",
                     credited_at="2026-10-01T18:05:52Z"),
            self.lsa(lead_id="lsa_001457", charge_status="NOT_CHARGED"),
        ])
        self.assertEqual(output.analysis_date, "2026-09-21")
        self.assertEqual((output.source_account_id, output.campaign_id, output.campaign_names),
                         (None, None, ()))
        self.assertEqual((output.spend_usd, output.reported_leads, output.source_row_count),
                         (Decimal("72.4"), Decimal(3), 3))

    def test_identical_duplicates_fail_for_every_source(self):
        for source in (self.google(), self.meta(), self.lsa()):
            with self.subTest(platform=source.source_platform), self.assertRaisesRegex(
                    DailyAggregationError, "duplicate source natural key"):
                aggregate_daily([source, source])

    def test_changed_ad_metrics_do_not_make_a_second_contribution(self):
        pairs = [
            (self.google(), self.google(cost_micros=1)),
            (self.meta(), self.meta(spend="1")),
        ]
        for before, after in pairs:
            with self.subTest(platform=before.source_platform), self.assertRaises(DailyAggregationError):
                aggregate_daily([before, after])

    def test_lsa_old_and_credited_versions_fail_in_either_order(self):
        old = self.lsa()
        new = self.lsa(charge_status="CREDITED", credited_at="2026-10-01T18:05:52Z")
        for rows in ([old, new], [new, old]):
            with self.assertRaises(DailyAggregationError):
                aggregate_daily(rows)

    def test_duplicate_lsa_id_is_rejected_even_if_date_changed(self):
        with self.assertRaises(DailyAggregationError):
            aggregate_daily([self.lsa(), self.lsa(lead_created_at="2026-09-22T18:05:52Z")])

    def test_accounts_with_same_campaign_and_adgroup_stay_separate(self):
        output = aggregate_daily([self.google(customer_id="482-119-3307"),
                                  self.google(customer_id="482-119-3308")])
        self.assertEqual(len(output), 2)
        self.assertEqual({row.source_account_id for row in output},
                         {"482-119-3307", "482-119-3308"})
        self.assertTrue(all(row.source_row_count == 1 for row in output))

    def test_cross_platform_identical_raw_keys_stay_separate(self):
        google = self.google()
        meta = self.meta(date_start=google.analysis_date, date_stop=google.analysis_date,
                         account_id=google.source_account_id, campaign_id=google.campaign_id,
                         adset_id=google.ad_group_id)
        self.assertEqual(google.raw_key, meta.raw_key)
        output = aggregate_daily([google, meta])
        self.assertEqual(len(output), 2)
        self.assertEqual({row.source_platform for row in output}, {"google_ads", "meta_ads"})

    def test_days_campaigns_and_brand_classifications_stay_separate(self):
        rows = [self.google(date="2026-09-01", campaign_id="20814455901"),
                self.google(date="2026-09-02", campaign_id="20814455901"),
                self.google(date="2026-09-01", campaign_id="20814455917")]
        output = aggregate_daily(rows)
        self.assertEqual(len(output), 3)
        self.assertEqual({row.brand_classification for row in output}, {"brand", "non_brand"})

    def test_unknown_brand_remains_unresolved(self):
        output, = aggregate_daily([self.google()])
        self.assertIsNone(output.brand_classification)

    def test_campaign_names_do_not_split_totals_or_choose_arbitrary_label(self):
        output, = aggregate_daily([
            self.google(campaign_id="20814455917", campaign_name="AC Repair - Houston"),
            self.google(campaign_id="20814455917", ad_group_id="1551230022",
                        campaign_name="Summer AC Repair"),
        ])
        self.assertEqual(output.source_row_count, 2)
        self.assertEqual(output.campaign_names, ("AC Repair - Houston", "Summer AC Repair"))

    def test_generator_and_reversed_order_give_same_immutable_output(self):
        rows = [self.meta(), self.google(), self.lsa(),
                self.google(ad_group_id="1551230022")]
        self.assertEqual(aggregate_daily(iter(rows)), aggregate_daily(reversed(rows)))

    def test_low_decimal_precision_does_not_round_totals(self):
        rows = [
            self.google(ad_group_id="1551230021", cost_micros=1,
                        conversions=Decimal("123456789.123456789")),
            self.google(ad_group_id="1551230022", cost_micros=2,
                        conversions=Decimal("0.000000001")),
        ]
        with localcontext() as context:
            context.prec = 2
            output, = aggregate_daily(rows)
        self.assertEqual(output.spend_usd, Decimal("0.000003"))
        self.assertEqual(output.reported_leads, Decimal("123456789.123456790"))

    def test_integer_aggregation_checks_database_bigint_limit(self):
        for field in ("impressions", "clicks"):
            rows = [replace(self.google(), **{field: 9223372036854775807}),
                    replace(self.google(ad_group_id="1551230022"), **{field: 1})]
            with self.subTest(field=field), self.assertRaisesRegex(DailyAggregationError, "bigint"):
                aggregate_daily(rows)

    def test_invalid_manually_constructed_metrics_are_rejected(self):
        cases = [("impressions", True), ("clicks", -1), ("spend_usd", 1.2),
                 ("reported_leads", Decimal("NaN")), ("spend_usd", Decimal("-1"))]
        for field, value in cases:
            with self.subTest(field=field), self.assertRaises(DailyAggregationError):
                aggregate_daily([replace(self.google(), **{field: value})])

    def test_raw_dicts_and_preaggregated_rows_cannot_enter_again(self):
        output = aggregate_daily([self.google()])
        for invalid in (GOOGLE, output[0]):
            with self.assertRaises(DailyAggregationError):
                aggregate_daily([invalid])

    def test_inputs_unchanged_and_no_call_crm_or_freshness_metrics_invented(self):
        rows = [self.google(), self.meta(), self.lsa()]
        before = [asdict(row) for row in rows]
        output = aggregate_daily(rows)
        self.assertEqual([asdict(row) for row in rows], before)
        for field in ("unique_leads", "calls", "jobs", "revenue_usd", "synced_at", "data_through"):
            self.assertNotIn(field, asdict(output[0]))
        with self.assertRaises(FrozenInstanceError):
            output[0].spend_usd = Decimal(0)

    def test_every_frozen_daily_bucket_matches_independent_raw_calculation(self):
        report = reconcile_snapshot()
        self.assertTrue(report["reconciliation"].startswith("PASS"))
        self.assertEqual(set(report["sources"]), {"google_ads", "meta_ads", "lsa"})
        self.assertGreater(report["all_daily_buckets"], 0)
        self.assertEqual(report["all_source_rows"],
                         sum(source["source_rows"] for source in report["sources"].values()))


if __name__ == "__main__":
    unittest.main()
