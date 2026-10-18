"""Independent golden expectations and negative controls for Issue #59."""
from copy import deepcopy
from decimal import Decimal
import json
import io
from contextlib import redirect_stdout
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts.reconcile_fixture_pack import actual_facts, build_report, compare, load_fixture, main


class FixturePackTests(unittest.TestCase):
    def test_fixed_source_matches_hand_authored_buckets(self):
        fixture = load_fixture()
        self.assertEqual(compare(fixture['expected'], actual_facts(fixture)), [])
        # Independent set arithmetic: repeated returning calls cannot add leads.
        self.assertEqual(len({r['caller_hash'] for r in fixture['calls']}), 7)
        self.assertEqual(len({r['caller_hash'] for r in fixture['calls']
                              if r['first_time_caller'] and r['duration_sec'] >= 30}), 6)
        facts = actual_facts(fixture)
        self.assertEqual(sum(r['metrics'].get('unique_leads', 0) for r in facts), 6)
        self.assertEqual(sum(r['metrics'].get('jobs', 0) for r in facts), 9)
        self.assertEqual(sum(r['metrics'].get('completed_jobs', 0) for r in facts), 4)
        self.assertEqual(sum((Decimal(r['metrics'].get('known_completed_revenue_usd', '0'))
                              for r in facts), Decimal(0)), Decimal('123.40'))
        self.assertTrue(all(r['bucket'][3] is None for r in facts))

    def test_all_synthetic_anomalies_match_exact_evidence(self):
        report = build_report()
        self.assertEqual(len(report['cases']), 14)
        self.assertTrue(report['passed'])
        for case in report['cases'][1:]:
            with self.subTest(case=case['name']):
                self.assertTrue(case['classification'].startswith('SYNTHETIC'))
                self.assertTrue(case.get('mismatches') or case.get('actual_error'))

    def test_missing_extra_and_duplicate_buckets(self):
        row = load_fixture()['expected'][0]
        self.assertEqual(compare([row], []), [dict(bucket=row['bucket'], field='__bucket__',
                                                  expected=row['metrics'], actual=None)])
        self.assertEqual(compare([], [row])[0]['actual'], row['metrics'])
        with self.assertRaisesRegex(ValueError, 'duplicate fact bucket'):
            compare([row], [row, row])

    def test_unknown_is_not_zero(self):
        row = load_fixture()['expected'][-1]
        changed = deepcopy(row)
        changed['metrics']['revenue_usd'] = '0.00'
        self.assertEqual(compare([row], [changed]), [dict(bucket=row['bucket'],
            field='revenue_usd', expected=None, actual='0.00')])

    def test_unexpected_baseline_drift_fails_report(self):
        fixture = load_fixture()
        fixture['expected'][1]['metrics']['unique_leads'] = 999
        with patch('scripts.reconcile_fixture_pack.load_fixture', return_value=fixture):
            self.assertFalse(build_report()['passed'])

    def test_noncompleted_revenue_is_excluded(self):
        fixture = load_fixture()
        fixture['crm'][2]['revenue_usd'] = '999.99'
        self.assertEqual(compare(fixture['expected'], actual_facts(fixture)), [])

    def test_cli_returns_failure_for_unexpected_drift(self):
        with patch('scripts.reconcile_fixture_pack.build_report', return_value={'passed': False}):
            with patch.object(sys, 'argv', ['reconcile_fixture_pack']), redirect_stdout(io.StringIO()):
                self.assertEqual(main(), 1)

    def test_reproducible_cli_and_checked_in_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'evidence.json'
            command = [sys.executable, '-m', 'scripts.reconcile_fixture_pack', '--output', str(path)]
            first = subprocess.run(command, check=True, capture_output=True, text=True)
            second = subprocess.run(command, check=True, capture_output=True, text=True)
            self.assertEqual(first.stdout, second.stdout)
            self.assertEqual(first.stdout, path.read_text())
            self.assertEqual(json.loads(first.stdout), build_report())
            evidence = Path(__file__).resolve().parents[1] / 'notes/issue59/fixture-evidence.json'
            self.assertEqual(first.stdout, evidence.read_text())


if __name__ == '__main__':
    unittest.main()
