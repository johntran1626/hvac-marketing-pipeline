"""Offline Google source-contract checks; variations of the example are synthetic."""
from copy import deepcopy
import csv
from dataclasses import asdict, FrozenInstanceError
from decimal import Decimal, localcontext
import json
from pathlib import Path
import unittest

from scripts.normalization.google import GoogleNormalizationError, normalize_google_row

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = json.loads((ROOT / "tests/fixtures/google-api-example.json").read_text())["response"]["data"][0]


class GoogleNormalizationTests(unittest.TestCase):
    def row(self, **changes):
        row = deepcopy(EXAMPLE)
        row.update(changes)
        return row

    def test_documented_ad_group_example(self):
        output = normalize_google_row(self.row())
        self.assertEqual(output.analysis_date, "2026-09-01")
        self.assertEqual(output.impressions, 1314)
        self.assertEqual(output.clicks, 53)
        self.assertEqual(output.spend_usd, Decimal("623.277880"))
        self.assertEqual(output.reported_leads, Decimal("9.42"))
        self.assertEqual((output.channel, output.source_platform), ("google_ads", "google_ads"))
        self.assertEqual(output.raw_key, ("2026-09-01", "482-119-3307", "20114567803", "1551230021"))
        self.assertNotIn("unique_leads", asdict(output))

    def test_micros_keep_subcent_precision(self):
        for micros, expected in [(0, "0"), (1, "0.000001"), (999999, "0.999999"),
                                 (1000000, "1"), (25330000, "25.33")]:
            with self.subTest(micros=micros):
                self.assertEqual(normalize_google_row(self.row(cost_micros=micros)).spend_usd,
                                 Decimal(expected))

    def test_cost_conversion_is_independent_of_decimal_context(self):
        with localcontext() as context:
            context.prec = 2
            output = normalize_google_row(self.row(cost_micros=9223372036854775807))
        self.assertEqual(output.spend_usd, Decimal("9223372036854.775807"))

    def test_fractional_numeric_conversions_are_not_rounded(self):
        for value, expected in [(0, "0"), (9.42, "9.42"), (Decimal("1.234567890123456789"), "1.234567890123456789")]:
            with self.subTest(value=value):
                self.assertEqual(normalize_google_row(self.row(conversions=value)).reported_leads,
                                 Decimal(expected))

    def test_invalid_conversions_are_rejected(self):
        for value in [True, None, "9.42", -1, float("nan"), float("inf"),
                      Decimal("NaN"), Decimal("-0.01"), Decimal("Infinity")]:
            with self.subTest(value=value), self.assertRaises(GoogleNormalizationError):
                normalize_google_row(self.row(conversions=value))

    def test_integer_metrics_require_real_nonnegative_integers(self):
        for field in ["impressions", "clicks", "cost_micros"]:
            for value in [True, None, "1", 1.0, -1, 9223372036854775808]:
                with self.subTest(field=field, value=value), self.assertRaises(GoogleNormalizationError):
                    normalize_google_row(self.row(**{field: value}))

    def test_central_dates_are_preserved_including_dst_boundaries(self):
        for day in ["2026-03-08", "2026-11-01", "2026-10-06"]:
            with self.subTest(day=day):
                self.assertEqual(normalize_google_row(self.row(date=day)).analysis_date, day)

    def test_invalid_or_noncanonical_dates_are_rejected(self):
        for day in ["2026-02-30", "20260901", "2026-W36-2", "2026-09-01T00:00:00", None]:
            with self.subTest(day=day), self.assertRaises(GoogleNormalizationError):
                normalize_google_row(self.row(date=day))

    def test_brand_uses_google_id_even_after_rename(self):
        self.assertEqual(normalize_google_row(self.row(
            campaign_id="20814455901", campaign_name="Synthetic renamed campaign"
        )).brand_classification, "brand")

    def test_known_nonbrand_ids_ignore_brandlike_names(self):
        for campaign in ["20814455917", "20814455930", "20814455948"]:
            with self.subTest(campaign=campaign):
                self.assertEqual(normalize_google_row(self.row(
                    campaign_id=campaign, campaign_name="Brand - synthetic name"
                )).brand_classification, "non_brand")

    def test_unknown_and_meta_ids_are_not_guessed(self):
        for campaign in ["20114567803", "120208841937650100"]:
            with self.subTest(campaign=campaign):
                self.assertIsNone(normalize_google_row(self.row(
                    campaign_id=campaign, campaign_name="Brand"
                )).brand_classification)

    def test_raw_input_remains_unchanged_and_output_is_immutable(self):
        row = self.row()
        original = deepcopy(row)
        output = normalize_google_row(row)
        self.assertEqual(row, original)
        with self.assertRaises(FrozenInstanceError):
            output.spend_usd = Decimal(0)

    def test_account_and_ad_group_namespace_are_preserved(self):
        a = normalize_google_row(self.row())
        b = normalize_google_row(self.row(customer_id="synthetic-other-account"))
        c = normalize_google_row(self.row(ad_group_id="1551230022"))
        self.assertEqual(len({a.raw_key, b.raw_key, c.raw_key}), 3)

    def test_campaign_aggregates_are_rejected_to_prevent_mixed_grain(self):
        row = self.row()
        del row["ad_group_id"]
        del row["ad_group_name"]
        with self.assertRaisesRegex(GoogleNormalizationError, "ad_group_id"):
            normalize_google_row(row)

    def test_required_fields_cannot_be_guessed(self):
        for field in EXAMPLE:
            row = self.row()
            del row[field]
            with self.subTest(field=field), self.assertRaises(GoogleNormalizationError):
                normalize_google_row(row)
        for field in ["customer_id", "campaign_id", "ad_group_id"]:
            with self.subTest(field=field), self.assertRaises(GoogleNormalizationError):
                normalize_google_row(self.row(**{field: ""}))

    def test_restated_conversions_replace_instead_of_accumulating(self):
        old = normalize_google_row(self.row(conversions=9.42))
        new = normalize_google_row(self.row(conversions=10.42))
        zero = normalize_google_row(self.row(conversions=0))
        self.assertEqual(old.raw_key, new.raw_key)
        self.assertEqual(new.raw_key, zero.raw_key)
        self.assertEqual([r.reported_leads for r in [old, new, zero]],
                         [Decimal("9.42"), Decimal("10.42"), Decimal(0)])

    def test_full_snapshot_reconciles_and_renamed_campaign_stays_nonbrand(self):
        with (ROOT / "data/snapshot-2026-09-23/google_ads_insights.csv").open(newline="") as file:
            rows = list(csv.DictReader(file))
        normalized = []
        for original in rows:
            row = dict(original)
            for field in ["impressions", "clicks", "cost_micros"]:
                row[field] = int(row[field])
            row["conversions"] = Decimal(row["conversions"])
            normalized.append(normalize_google_row(row))
        self.assertGreater(len(rows), 0)
        self.assertEqual(len({r.raw_key for r in normalized}), len(rows))
        self.assertEqual(sum(r.impressions for r in normalized),
                         sum(int(r["impressions"]) for r in rows))
        self.assertEqual(sum(r.clicks for r in normalized),
                         sum(int(r["clicks"]) for r in rows))
        self.assertEqual(sum((r.spend_usd for r in normalized), Decimal(0)),
                         Decimal(sum(int(r["cost_micros"]) for r in rows)) / Decimal(1000000))
        self.assertEqual(sum((r.reported_leads for r in normalized), Decimal(0)),
                         sum((Decimal(r["conversions"]) for r in rows), Decimal(0)))
        self.assertTrue(all(r.brand_classification is not None for r in normalized))
        renamed = [r for r in normalized if r.campaign_id == "20814455917"]
        self.assertGreater(len({r.campaign_name for r in renamed}), 1)
        self.assertTrue(all(r.brand_classification == "non_brand" for r in renamed))


if __name__ == "__main__":
    unittest.main()
