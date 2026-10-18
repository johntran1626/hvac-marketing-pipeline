"""Offline contract checks. Fixture variations are synthetic, not live API evidence."""
from copy import deepcopy
import csv
from dataclasses import asdict, FrozenInstanceError
from decimal import Decimal, localcontext
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import json
from pathlib import Path
import unittest

from scripts.normalization.meta import (
    MetaNormalizationError,
    extract_meta_reported_leads,
    normalize_meta_row,
)

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / "tests/fixtures/meta-api-cases.json").read_text())["cases"]
NEGATIVE_CASES = json.loads((ROOT / "tests/fixtures/meta-api-cases.json").read_text())["negative_cases"]
EXAMPLE = CASES[0]["responses"][0]["data"][0]


class MetaNormalizationTests(unittest.TestCase):
    def row(self, **changes):
        row = deepcopy(EXAMPLE)
        row.update(changes)
        return row

    def test_documented_api_sample(self):
        output = normalize_meta_row(self.row())
        self.assertEqual(output.impressions, 859)
        self.assertEqual(output.clicks, 8)
        self.assertEqual(output.spend_usd, Decimal("41.65"))
        self.assertEqual(output.reported_leads, Decimal("3"))
        self.assertEqual(output.analysis_date, "2026-09-20")
        self.assertEqual((output.channel, output.source_platform), ("meta", "meta_ads"))
        self.assertEqual(output.raw_key, ("2026-09-20", "act_1029384756",
                                         "23851234560001", "23851234560101"))
        self.assertNotIn("unique_leads", asdict(output))

    def test_no_actions_is_zero_reported_leads(self):
        self.assertEqual(normalize_meta_row(self.row(actions=[])).reported_leads, Decimal(0))

    def test_only_exact_lead_action_counts(self):
        actions = [
            {"action_type": "link_click", "value": "8"},
            {"action_type": "offsite_conversion.fb_pixel_lead", "value": "99"},
            {"action_type": "Lead", "value": "99"},
            {"action_type": "lead", "value": "3"},
        ]
        self.assertEqual(extract_meta_reported_leads(actions), Decimal("3"))

    def test_no_lead_action_is_zero(self):
        self.assertEqual(extract_meta_reported_leads([
            {"action_type": "link_click", "value": "unused"}
        ]), Decimal(0))

    def test_fractional_lead_values_are_exact(self):
        self.assertEqual(extract_meta_reported_leads([
            {"action_type": "lead", "value": "1.25"},
        ]), Decimal("1.25"))

    def test_decimal_precision_does_not_depend_on_caller_context(self):
        with localcontext() as context:
            context.prec = 2
            output = normalize_meta_row(self.row(actions=[
                {"action_type": "lead", "value": "123456789.13"},
            ]))
        self.assertEqual(output.reported_leads, Decimal("123456789.13"))
        self.assertEqual(output.spend_usd, Decimal("41.65"))

    def test_raw_payload_is_not_mutated(self):
        row = self.row(actions=[{"action_type": "lead", "value": "3"}])
        original = deepcopy(row)
        normalize_meta_row(row)
        self.assertEqual(row, original)

    def test_output_is_immutable(self):
        output = normalize_meta_row(self.row())
        with self.assertRaises(FrozenInstanceError):
            output.impressions = 1

    def test_pacific_dates_are_never_rebucketed(self):
        for day in ["2026-10-03", "2026-03-08", "2026-11-01"]:
            with self.subTest(day=day):
                self.assertEqual(normalize_meta_row(
                    self.row(date_start=day, date_stop=day)).analysis_date, day)

    def test_invalid_or_noncanonical_dates_are_rejected(self):
        for day in ["2026-02-30", "20260920", "2026-W38-7", "2026-09-20T00:00:00"]:
            with self.subTest(day=day), self.assertRaises(MetaNormalizationError):
                normalize_meta_row(self.row(date_start=day))

    def test_mismatched_source_days_are_rejected(self):
        with self.assertRaisesRegex(MetaNormalizationError, "date_stop"):
            normalize_meta_row(self.row(date_stop="2026-09-21"))

    def test_integer_metrics_reject_bad_values(self):
        for value in ["-1", "1.5", "", "NaN", "1e3", 859, True, None]:
            for field in ["impressions", "clicks"]:
                with self.subTest(field=field, value=value), self.assertRaises(MetaNormalizationError):
                    normalize_meta_row(self.row(**{field: value}))

    def test_bigint_overflow_is_rejected(self):
        with self.assertRaisesRegex(MetaNormalizationError, "bigint"):
            normalize_meta_row(self.row(impressions="9223372036854775808"))

    def test_spend_rejects_invalid_negative_or_nonfinite_values(self):
        for value in ["-1.00", "NaN", "Infinity", "", "1e2", " 41.65", 41.65, None]:
            with self.subTest(value=value), self.assertRaises(MetaNormalizationError):
                normalize_meta_row(self.row(spend=value))

    def test_lead_value_rejects_invalid_inputs(self):
        for value in ["-1", "NaN", "Infinity", "", "abc", 3, None]:
            with self.subTest(value=value), self.assertRaises(MetaNormalizationError):
                extract_meta_reported_leads([{"action_type": "lead", "value": value}])
        with self.assertRaises(MetaNormalizationError):
            extract_meta_reported_leads([{"action_type": "lead"}])

    def test_malformed_actions_are_not_silently_zeroed(self):
        for actions in [None, {}, "[]", [None], [{}], [{"action_type": 1}]]:
            with self.subTest(actions=actions), self.assertRaises(MetaNormalizationError):
                normalize_meta_row(self.row(actions=actions))

    def test_required_fields_are_not_guessed(self):
        for field in EXAMPLE:
            row = self.row()
            del row[field]
            with self.subTest(field=field), self.assertRaises(MetaNormalizationError):
                normalize_meta_row(row)
        for field in ["account_id", "campaign_id", "adset_id"]:
            with self.subTest(field=field), self.assertRaises(MetaNormalizationError):
                normalize_meta_row(self.row(**{field: " "}))

    def test_namespace_and_adset_keys_remain_distinct(self):
        a = normalize_meta_row(self.row())
        b = normalize_meta_row(self.row(account_id="act_synthetic_other"))
        c = normalize_meta_row(self.row(adset_id="23851234560102"))
        d = normalize_meta_row(self.row(campaign_id="synthetic_other_campaign"))
        self.assertEqual(len({a.raw_key, b.raw_key, c.raw_key, d.raw_key}), 4)

    def test_known_meta_ids_classify_by_id_not_name(self):
        for campaign in ["120208841937650100", "120208841937650200"]:
            with self.subTest(campaign=campaign):
                self.assertEqual(normalize_meta_row(self.row(
                    campaign_id=campaign, campaign_name="Brand - synthetic rename"
                )).brand_classification, "non_brand")

    def test_unknown_and_google_brand_ids_are_unclassified(self):
        for campaign in ["23851234560001", "20814455901"]:
            with self.subTest(campaign=campaign):
                self.assertIsNone(normalize_meta_row(self.row(
                    campaign_id=campaign, campaign_name="Brand"
                )).brand_classification)

    def test_restatement_is_recomputed_not_added_to_old_values(self):
        a = normalize_meta_row(self.row())
        b = normalize_meta_row(self.row(actions=[{"action_type": "lead", "value": "4"}]))
        c = normalize_meta_row(self.row(actions=[]))
        self.assertEqual(a.raw_key, b.raw_key)
        self.assertEqual(b.raw_key, c.raw_key)
        self.assertEqual([x.reported_leads for x in [a, b, c]],
                         [Decimal(3), Decimal(4), Decimal(0)])

    def test_all_prepared_fixture_rows_normalize_without_mutation(self):
        self.assertGreaterEqual(len(CASES), 10)
        for case in CASES:
            for response in case["responses"]:
                for row in response["data"]:
                    with self.subTest(case=case["name"]):
                        before = deepcopy(row)
                        result = normalize_meta_row(row)
                        self.assertEqual(result.analysis_date, row["date_start"])
                        self.assertEqual(row, before)

    def test_explicit_fixture_outputs(self):
        for case in CASES:
            actual = []
            for response in case["responses"]:
                for row in response["data"]:
                    result = asdict(normalize_meta_row(row))
                    result["spend_usd"] = str(result["spend_usd"])
                    result["reported_leads"] = str(result["reported_leads"])
                    actual.append(result)
            with self.subTest(case=case["name"]):
                self.assertEqual(actual, case["expected_outputs"])

    def test_pacific_account_day_utc_boundaries(self):
        pacific = ZoneInfo("America/Los_Angeles")
        for case in CASES:
            if "utc_bounds" not in case:
                continue
            with self.subTest(case=case["name"]):
                row = case["responses"][0]["data"][0]
                result = normalize_meta_row(row)
                start = datetime.fromisoformat(result.analysis_date).replace(tzinfo=pacific)
                end = start + timedelta(days=1)
                self.assertEqual([start.astimezone(timezone.utc).isoformat(),
                                  end.astimezone(timezone.utc).isoformat()], case["utc_bounds"])
                # Last instant stays in the account day; exclusive end is tomorrow.
                last = end.astimezone(timezone.utc) - timedelta(microseconds=1)
                self.assertEqual(last.astimezone(pacific).date().isoformat(), result.analysis_date)
                self.assertNotEqual(end.date().isoformat(), result.analysis_date)

    def test_negative_fixtures(self):
        for case in NEGATIVE_CASES:
            with self.subTest(case=case["name"]):
                with self.assertRaises(MetaNormalizationError) as caught:
                    normalize_meta_row(self.row(**case["changes"]))
                self.assertEqual(caught.exception.field, case["error_field"])

    def test_large_and_subcent_money_is_preserved_without_rounding(self):
        for value in ["0.01", "0.001", "123456789012345678901234567890.12"]:
            with self.subTest(value=value), localcontext() as context:
                context.prec = 2
                self.assertEqual(str(normalize_meta_row(self.row(spend=value)).spend_usd), value)

    def test_non_mapping_rows_are_rejected(self):
        for row in [None, [], "row", 1]:
            with self.subTest(row=row), self.assertRaises(MetaNormalizationError):
                normalize_meta_row(row)

    def test_frozen_snapshot_metrics_reconcile(self):
        # CSV leads is flattened. Adapt ONLY here for offline verification.
        # Live/raw normalization always requires the original API actions array.
        with (ROOT / "data/snapshot-2026-09-23/meta_insights.csv").open(newline="") as file:
            rows = list(csv.DictReader(file))
        normalized = []
        for original in rows:
            row = dict(original)
            lead_count = row.pop("leads")
            row["actions"] = [] if Decimal(lead_count) == 0 else [
                {"action_type": "lead", "value": lead_count}
            ]
            normalized.append(normalize_meta_row(row))
        self.assertGreater(len(normalized), 0)
        self.assertEqual(len({r.raw_key for r in normalized}), len(rows))
        self.assertEqual(sum(r.impressions for r in normalized),
                         sum(int(r["impressions"]) for r in rows))
        self.assertEqual(sum(r.clicks for r in normalized),
                         sum(int(r["clicks"]) for r in rows))
        self.assertEqual(sum((r.spend_usd for r in normalized), Decimal(0)),
                         sum((Decimal(r["spend"]) for r in rows), Decimal(0)))
        self.assertEqual(sum((r.reported_leads for r in normalized), Decimal(0)),
                         sum((Decimal(r["leads"]) for r in rows), Decimal(0)))
        self.assertTrue(all(r.brand_classification == "non_brand" for r in normalized))


if __name__ == "__main__":
    unittest.main()
