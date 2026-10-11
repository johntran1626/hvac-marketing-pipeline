"""Offline runner regression tests; real guards and Calls ingestion, no secrets."""
import asyncio
import copy
import io
from pathlib import Path
import runpy
import signal
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from worker import run as runner
from worker.api_client import ApiClient
from worker.tests.test_calls import API_ROWS, FakeCallsApi, FakeRawDb


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.api = ApiClient('unused')
        calls = FakeCallsApi()
        self.api.data_through = calls.data_through
        self.api.pages = calls.pages
        self.db = FakeRawDb()
        self.output = io.StringIO()
        for target, kwargs in [
            ('worker.run.load_env', {'return_value': {
                'LAB_API_KEY': 'unused', 'SUPABASE_URL': 'https://unused.invalid',
                'SUPABASE_SECRET_KEY': 'unused'}}),
            ('worker.run.ApiClient', {'return_value': self.api}),
            ('worker.run.Db', {'return_value': self.db}),
            ('worker.run.signal.signal', {}),
            ('urllib.request.urlopen', {'side_effect': AssertionError('unexpected network')}),
        ]:
            self.enterContext(patch(target, **kwargs))
        self.enterContext(redirect_stdout(self.output))

    def assert_calls_ingested(self):
        self.assertEqual(self.db.tables['raw_calls'], {r['call_id']: r for r in API_ROWS})
        self.assertEqual(self.db.tables['sync_state']['calls']['status'], 'ok')

    def test_default_sources_continue_after_paid_guards_and_return_failure(self):
        self.assertEqual(runner.main([]), 1)
        self.assert_calls_ingested()
        self.assertEqual(set(self.db.tables['sync_state']), {'calls'})
        for name in ('lsa', 'google_ads', 'meta'):
            self.assertIn(f'[{name}] FAILED', self.output.getvalue())
            self.assertNotIn(f'[{name}] SUCCESS', self.output.getvalue())
        self.assertIn('[calls] SUCCESS', self.output.getvalue())

    def test_all_paid_sources_before_calls_preserve_existing_paid_state(self):
        prior = {name: {'source': name, 'status': 'failed',
                       'backfilled_through': '2024-10-01', 'last_success_at': None}
                 for name in ('lsa', 'google_ads', 'meta')}
        self.db.tables['sync_state'].update(copy.deepcopy(prior))
        self.assertEqual(runner.main(['lsa', 'google_ads', 'meta', 'calls']), 1)
        self.assert_calls_ingested()
        for name, state in prior.items():
            self.assertEqual(self.db.tables['sync_state'][name], state)

    def test_calls_only_returns_success(self):
        self.assertEqual(runner.main(['calls']), 0)
        self.assert_calls_ingested()

    def test_ordinary_failure_continues_without_printing_exception_payload(self):
        with patch('worker.run.sync.run', side_effect=[RuntimeError('secret-token private-row'), None]) as sync:
            self.assertEqual(runner.main(['lsa', 'calls']), 1)
        self.assertEqual([c.args[2].name for c in sync.call_args_list], ['lsa', 'calls'])
        self.assertEqual(self.output.getvalue(), '[lsa] FAILED\n[calls] SUCCESS\n')

    def test_cancellation_propagates_and_stops_later_sources(self):
        for error in (KeyboardInterrupt(), SystemExit(143), asyncio.CancelledError(), BaseException()):
            with self.subTest(error=type(error).__name__):
                self.output.seek(0)
                self.output.truncate()
                with patch('worker.run.sync.run', side_effect=error) as sync:
                    with self.assertRaises(type(error)) as raised:
                        runner.main(['calls', 'lsa'])
                self.assertIs(raised.exception, error)
                self.assertEqual(sync.call_count, 1)
                self.assertEqual(self.output.getvalue(), '')

    def test_sigterm_during_calls_propagates_after_loader_marks_failure(self):
        def cancelled_pages(*args, **kwargs):
            runner.stop(signal.SIGTERM, None)
        self.api.pages = cancelled_pages
        with patch('worker.run.sync.run', wraps=runner.sync.run) as sync:
            with self.assertRaises(SystemExit):
                runner.main(['calls', 'lsa'])
        self.assertEqual(sync.call_count, 1)
        self.assertEqual(self.db.tables['sync_state']['calls']['status'], 'failed')
        self.assertNotIn('[calls] SUCCESS', self.output.getvalue())

    def test_cli_exits_with_aggregate_status(self):
        for names, expected in [(['lsa', 'google_ads', 'meta', 'calls'], 1), (['calls'], 0)]:
            with self.subTest(names=names), \
                 patch('worker.config.load_env', runner.load_env), \
                 patch('worker.api_client.ApiClient', return_value=self.api), \
                 patch('worker.db.Db', return_value=self.db), \
                 patch('sys.argv', ['worker.run', *names]):
                with self.assertRaises(SystemExit) as raised:
                    runpy.run_path(str(Path(runner.__file__)), run_name='__main__')
                self.assertEqual(raised.exception.code, expected)
        self.assert_calls_ingested()

    def test_unknown_source_remains_fatal_before_any_source_runs(self):
        with patch('worker.run.sync.run') as sync:
            with self.assertRaises(SystemExit):
                runner.main(['calls', 'unknown'])
        sync.assert_not_called()
