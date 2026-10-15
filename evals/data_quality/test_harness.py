"""Offline regression tests, including detector suppression and CLI exit codes."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).parent
spec = importlib.util.spec_from_file_location('harness', ROOT / 'harness.py')
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.suite = json.loads(harness.FIXTURES.read_text())

    def test_checked_in_expectations(self):
        results = harness.evaluate(self.suite)
        self.assertTrue(all(r['pass'] for r in results))
        for check in harness.CHECKS:
            selected = [r for r in results if r['check_id'] == check]
            self.assertTrue(any(r['expected'] for r in selected), check)
            self.assertTrue(any(not r['expected'] for r in selected), check)

    def test_suppression_of_each_detector_is_a_failure(self):
        inspect = harness.inspect
        for check in harness.CHECKS:
            with self.subTest(check=check):
                def suppressed(data):
                    findings = inspect(data)
                    findings[check] = []
                    return findings
                with patch.object(harness, 'inspect', suppressed):
                    self.assertTrue(any(not r['pass'] for r in harness.evaluate(self.suite)))

    def test_unexpected_anomaly_fails(self):
        self.suite['normal']['unique_callers'] = 999
        self.assertFalse(harness.evaluate(self.suite)[2]['pass'])

    def test_deterministic_and_no_input_mutation(self):
        before = deepcopy(self.suite)
        first = harness.evaluate(self.suite)
        self.assertEqual(first, harness.evaluate(self.suite))
        self.assertEqual(before, self.suite)

    def run_cli(self, suite):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'fixtures.json'
            path.write_text(json.dumps(suite))
            return subprocess.run([sys.executable, str(ROOT / 'harness.py'), '--fixtures', str(path), '--json'],
                                  capture_output=True, text=True, env={})

    def test_cli_success_without_environment_or_services(self):
        result = self.run_cli(self.suite)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(all(r['pass'] for r in json.loads(result.stdout)))

    def test_cli_missed_anomaly_is_nonzero(self):
        self.suite['cases'][1]['changes'] = []
        result = self.run_cli(self.suite)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertTrue(any(not r['pass'] for r in json.loads(result.stdout)))

    def test_cli_invalid_expectations_and_empty_suite_fail(self):
        for cases in ([], [{'name':'invalid','changes':[], 'expected':{}}]):
            self.suite['cases'] = cases
            self.assertEqual(self.run_cli(self.suite).returncode, 2)

    def test_sample_output_matches_current_run(self):
        result = subprocess.run([sys.executable, str(ROOT / 'harness.py')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, (ROOT / 'sample-output.txt').read_text())


if __name__ == '__main__':
    unittest.main()
