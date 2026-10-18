"""Offline LSA rule checks; example variations are synthetic."""
from copy import deepcopy
import csv
from dataclasses import asdict, FrozenInstanceError
from datetime import datetime
from decimal import Decimal, localcontext
import json
from pathlib import Path
import unittest
from zoneinfo import ZoneInfo

from scripts.normalization.lsa import LsaNormalizationError, normalize_lsa_row

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = json.loads((ROOT / "tests/fixtures/lsa-api-example.json").read_text(), parse_float=Decimal)["response"]["data"][0]


class LsaNormalizationTests(unittest.TestCase):
    def row(self, **changes):
        row = deepcopy(EXAMPLE)
        row.update(changes)
        return row

    def test_documented_api_example(self):
        output = normalize_lsa_row(self.row())
        self.assertEqual(output.raw_key, "lsa_001455")
        self.assertEqual(output.analysis_date, "2026-09-21")
        self.assertEqual(output.spend_usd, Decimal("72.4"))
        self.assertEqual(output.reported_leads, Decimal(1))
        self.assertEqual((output.channel, output.source_platform), ("google_lsa", "lsa"))
        self.assertEqual(output.brand_classification, "not_applicable")
        self.assertEqual((output.impressions, output.clicks), (0, 0))
        self.assertNotIn("unique_leads", asdict(output))

    def test_credited_lead_keeps_reported_count_and_removes_net_spend(self):
        output = normalize_lsa_row(self.row(
            charge_status="CREDITED", credited_at="2026-09-22T18:05:52Z"))
        self.assertEqual(output.spend_usd, Decimal(0))
        self.assertEqual(output.reported_leads, Decimal(1))

    def test_not_charged_has_zero_spend_without_rewriting_raw_cost(self):
        row = self.row(charge_status="NOT_CHARGED")
        output = normalize_lsa_row(row)
        self.assertEqual(output.spend_usd, Decimal(0))
        self.assertEqual(row["cost_usd"], Decimal("72.4"))
        self.assertEqual(output.reported_leads, Decimal(1))

    def test_phone_and_message_leads_both_count_as_reported(self):
        for kind in ["PHONE_CALL", "MESSAGE"]:
            with self.subTest(kind=kind):
                self.assertEqual(normalize_lsa_row(self.row(lead_type=kind)).reported_leads,
                                 Decimal(1))

    def test_winter_and_summer_central_midnight_boundaries(self):
        pairs = [
            ("2026-01-15T05:59:59Z", "2026-01-14"),
            ("2026-01-15T06:00:00Z", "2026-01-15"),
            ("2026-07-15T04:59:59Z", "2026-07-14"),
            ("2026-07-15T05:00:00Z", "2026-07-15"),
        ]
        for timestamp, day in pairs:
            with self.subTest(timestamp=timestamp):
                self.assertEqual(normalize_lsa_row(self.row(
                    lead_created_at=timestamp)).analysis_date, day)

    def test_dst_transition_dates_use_timezone_rules(self):
        pairs = [
            ("2026-03-08T05:59:59Z", "2026-03-07"),
            ("2026-03-08T06:00:00Z", "2026-03-08"),
            ("2026-11-01T04:59:59Z", "2026-10-31"),
            ("2026-11-01T05:00:00Z", "2026-11-01"),
        ]
        for timestamp, day in pairs:
            with self.subTest(timestamp=timestamp):
                self.assertEqual(normalize_lsa_row(self.row(
                    lead_created_at=timestamp)).analysis_date, day)

    def test_equivalent_offset_timestamps_preserve_same_day(self):
        a = normalize_lsa_row(self.row(lead_created_at="2026-09-21T18:05:52+00:00"))
        b = normalize_lsa_row(self.row(lead_created_at="2026-09-21T20:05:52+02:00"))
        self.assertEqual(a.analysis_date, b.analysis_date)

    def test_naive_or_invalid_timestamps_are_rejected(self):
        for value in ["2026-09-21", "2026-09-21T18:05:52", "invalid",
                      "2026-02-30T00:00:00Z", 123, None]:
            with self.subTest(value=value), self.assertRaises(LsaNormalizationError):
                normalize_lsa_row(self.row(lead_created_at=value))

    def test_late_credit_restates_original_lead_date(self):
        output = normalize_lsa_row(self.row(
            lead_created_at="2026-08-31T18:05:52Z", charge_status="CREDITED",
            credited_at="2026-09-20T18:05:52Z"))
        self.assertEqual(output.analysis_date, "2026-08-31")
        self.assertEqual(output.spend_usd, Decimal(0))
        self.assertEqual(output.reported_leads, Decimal(1))

    def test_restatement_keeps_key_and_count_instead_of_creating_refund_lead(self):
        old = normalize_lsa_row(self.row())
        new = normalize_lsa_row(self.row(
            charge_status="CREDITED", credited_at="2026-09-22T18:05:52Z"))
        self.assertEqual(old.raw_key, new.raw_key)
        self.assertEqual(old.analysis_date, new.analysis_date)
        self.assertEqual((old.spend_usd, new.spend_usd), (Decimal("72.4"), Decimal(0)))
        self.assertEqual((old.reported_leads, new.reported_leads), (Decimal(1), Decimal(1)))

    def test_no_campaign_or_account_is_invented(self):
        output = normalize_lsa_row(self.row())
        self.assertIsNone(output.source_account_id)
        self.assertIsNone(output.campaign_id)
        self.assertIsNone(output.campaign_name)

    def test_exact_decimal_cost_and_zero_charge(self):
        with localcontext() as context:
            context.prec = 2
            output = normalize_lsa_row(self.row(cost_usd=Decimal("72.123456789")))
        self.assertEqual(output.spend_usd, Decimal("72.123456789"))
        self.assertEqual(normalize_lsa_row(self.row(cost_usd=0)).spend_usd, Decimal(0))

    def test_invalid_cost_is_not_silently_zeroed_even_for_credited_lead(self):
        for value in [-1, True, None, "72.4", float("nan"), float("inf"), Decimal("-0.01")]:
            with self.subTest(value=value), self.assertRaises(LsaNormalizationError):
                normalize_lsa_row(self.row(cost_usd=value, charge_status="CREDITED",
                                          credited_at="2026-09-22T18:05:52Z"))

    def test_missing_charge_states_or_unknown_lead_types_are_flagged(self):
        for field, value in [("charge_status", None), ("charge_status", ""),
                             ("lead_type", "UNKNOWN"), ("lead_type", None)]:
            with self.subTest(field=field), self.assertRaises(LsaNormalizationError):
                normalize_lsa_row(self.row(**{field: value}))

    def test_credit_state_requires_a_valid_credit_timestamp(self):
        for value in [None, "", "2026-09-22T18:05:52", "invalid"]:
            with self.subTest(value=value), self.assertRaises(LsaNormalizationError):
                normalize_lsa_row(self.row(charge_status="CREDITED", credited_at=value))

    def test_uncredited_states_cannot_have_credit_timestamps(self):
        for state in ["CHARGED", "NOT_CHARGED"]:
            with self.subTest(state=state), self.assertRaises(LsaNormalizationError):
                normalize_lsa_row(self.row(charge_status=state, credited_at="2026-09-22T18:05:52Z"))

    def test_credit_cannot_precede_creation(self):
        with self.assertRaisesRegex(LsaNormalizationError, "precedes"):
            normalize_lsa_row(self.row(charge_status="CREDITED",
                                      credited_at="2026-09-20T18:05:52Z"))

    def test_required_fields_are_not_guessed(self):
        for field in EXAMPLE:
            row = self.row()
            del row[field]
            with self.subTest(field=field), self.assertRaises(LsaNormalizationError):
                normalize_lsa_row(row)
        with self.assertRaises(LsaNormalizationError):
            normalize_lsa_row(self.row(lead_id=" "))

    def test_raw_record_is_unchanged_and_output_is_immutable(self):
        row = self.row(charge_status="CREDITED", credited_at="2026-09-22T18:05:52Z")
        before = deepcopy(row)
        output = normalize_lsa_row(row)
        self.assertEqual(row, before)
        with self.assertRaises(FrozenInstanceError):
            output.analysis_date = "2026-09-22"

    def test_fixture_expected_outputs_and_rejections(self):
        fixture = json.loads((ROOT / "tests/fixtures/lsa-normalization-cases.json").read_text(),
                             parse_float=Decimal)
        for case in fixture["cases"]:
            with self.subTest(case=case["name"]):
                row = self.row(**case["changes"])
                before = deepcopy(row)
                if "error" in case:
                    with self.assertRaises(LsaNormalizationError) as caught:
                        normalize_lsa_row(row)
                    self.assertEqual(caught.exception.field, case["error"])
                else:
                    result = normalize_lsa_row(row)
                    expected = dict(case["expected"])
                    if expected["spend_usd"] is not None:
                        expected["spend_usd"] = Decimal(expected["spend_usd"])
                    for key, value in expected.items():
                        self.assertEqual(getattr(result, key), value, key)
                    self.assertEqual(result.reported_leads, Decimal(1))
                    self.assertEqual(result.charge_status, row["charge_status"])
                    self.assertEqual(result.lead_created_at, row["lead_created_at"])
                    self.assertEqual(result.credited_at, row["credited_at"])
                    self.assertEqual(result.cost_usd, row["cost_usd"])
                    self.assertEqual(result, normalize_lsa_row(row))
                self.assertEqual(row, before)

    def test_account_identifiers_and_qualified_identity(self):
        for field in ["account_id", "source_account_id"]:
            a = normalize_lsa_row(self.row(**{field: "000123"}))
            b = normalize_lsa_row(self.row(**{field: "000124"}))
            self.assertEqual(a.source_account_id, "000123")
            self.assertEqual(a.raw_key, EXAMPLE["lead_id"])
            self.assertEqual(a.source_key, ("lsa", "000123", EXAMPLE["lead_id"]))
            self.assertNotEqual(a.source_key, b.source_key)
        both = normalize_lsa_row(self.row(account_id="000123", source_account_id="000123"))
        self.assertEqual(both.source_account_id, "000123")

    def test_json_decimal_precision_survives_refund(self):
        row = self.row(**json.loads('{"cost_usd": 72.12345678901234567890123456789}',
                                   parse_float=Decimal))
        with localcontext() as context:
            context.prec = 2
            charged = normalize_lsa_row(row)
            refunded = normalize_lsa_row(dict(row, charge_status="REFUNDED",
                                             credited_at=row["lead_created_at"]))
        self.assertEqual(charged.spend_usd, Decimal("72.12345678901234567890123456789"))
        self.assertEqual(refunded.cost_usd, charged.spend_usd)
        self.assertEqual(refunded.spend_usd, Decimal(0))
        self.assertEqual((charged.charged_leads, charged.refunded_leads), (1, 0))
        self.assertEqual((refunded.charged_leads, refunded.refunded_leads), (0, 1))

    def test_non_record_input_is_rejected(self):
        for value in [None, [], "lead"]:
            with self.subTest(value=value), self.assertRaises(LsaNormalizationError):
                normalize_lsa_row(value)

    def test_full_frozen_snapshot_reconciles(self):
        with (ROOT / "data/snapshot-2026-09-23/lsa_leads.csv").open(newline="") as file:
            rows = list(csv.DictReader(file))
        normalized = []
        for original in rows:
            row = dict(original)
            row["cost_usd"] = Decimal(row["cost_usd"])
            row["credited_at"] = row["credited_at"] or None
            normalized.append(normalize_lsa_row(row))
        # Literal snapshot oracle independently computed from the frozen CSV.
        self.assertEqual(len(rows), 1701)
        self.assertEqual(len({r.analysis_date for r in normalized}), 625)
        self.assertEqual(sum(r.charged_leads for r in normalized), 1275)
        self.assertEqual(sum(r.refunded_leads for r in normalized), 222)
        self.assertEqual(sum(r.not_charged_leads for r in normalized), 204)
        self.assertEqual(sum(r.unknown_status_leads for r in normalized), 0)
        self.assertEqual(sum((r.spend_usd for r in normalized), Decimal(0)),
                         Decimal("50518.51"))
        self.assertEqual(len({r.raw_key for r in normalized}), len(rows))
        self.assertEqual(sum((r.reported_leads for r in normalized), Decimal(0)), len(rows))
        self.assertEqual(sum((r.spend_usd for r in normalized), Decimal(0)),
                         sum((Decimal(r["cost_usd"]) for r in rows
                              if r["charge_status"] == "CHARGED"), Decimal(0)))
        expected_dates = [
            datetime.fromisoformat(r["lead_created_at"].replace("Z", "+00:00"))
            .astimezone(ZoneInfo("America/Chicago")).date().isoformat() for r in rows
        ]
        self.assertEqual([r.analysis_date for r in normalized], expected_dates)
        self.assertTrue(all(r.spend_usd == 0 for r in normalized
                            if r.charge_status != "CHARGED"))


if __name__ == "__main__":
    unittest.main()
