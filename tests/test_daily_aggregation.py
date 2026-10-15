"""Independent source/day aggregation contract tests; fixture-only adapters."""
import json
import unittest
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from scripts.normalization.daily import aggregate_daily, DailyAggregationError
from scripts.reconcile_daily_aggregation import load_row, reconcile_cases

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / 'tests/fixtures/issue68-daily.json').read_text())['cases']

class DailyAggregationTests(unittest.TestCase):
    def test_all_documented_cases(self):
        findings = reconcile_cases()
        for finding in findings:
            with self.subTest(case=finding['case']):
                self.assertTrue(finding['pass'], finding)

    def test_order_independence(self):
        rows = [load_row(r) for r in next(c for c in CASES if c['id']=='all-platforms')['rows']]
        self.assertEqual(aggregate_daily(rows), aggregate_daily(reversed(rows)))

    def test_decimal_exactness(self):
        rows = [load_row(r) for r in next(c for c in CASES if c['id']=='exact-micros')['rows']]
        result, = aggregate_daily(rows)
        self.assertEqual(result.spend_usd, Decimal('0.000003'))
        self.assertEqual(result.reported_leads, Decimal('0.3'))

    def test_same_key_stale_update_rejected(self):
        row = load_row(next(c for c in CASES if c['id']=='exact-micros')['rows'][0])
        with self.assertRaises(DailyAggregationError):
            aggregate_daily([row,replace(row, spend_usd=Decimal('20'))])

    def test_missing_metric_rejected(self):
        row = load_row(next(c for c in CASES if c['id']=='exact-micros')['rows'][0])
        with self.assertRaises(DailyAggregationError):
            aggregate_daily([replace(row, spend_usd=Decimal('NaN'))])

if __name__=='__main__':
    unittest.main()
