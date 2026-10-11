import unittest
from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal

from scripts.normalization.coverage import SourceScope, DateWindow, RawCoverage
from scripts.normalization.daily import DailyContribution
from scripts.normalization.fact_rows import FactRowError
from scripts.normalization.persistence import replace_paid_window


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.raw = RawCoverage(SourceScope('google_ads', 'all-accounts'),
            DateWindow(date(2026, 9, 1), date(2026, 9, 2)),
            datetime(2026, 9, 3, tzinfo=timezone.utc), 1, 1)
        self.row = DailyContribution('2026-09-01', 'google_ads', 'google_ads',
            'account', 'campaign', 'brand', ('Campaign',), 1, 10, 2,
            Decimal('12345678901234567890.000001'), Decimal('0.125'))
        self.calls = []

    def rpc(self, name, params):
        self.calls.append((name, params))
        return len(params['p_rows'])

    def test_one_rpc_exact_decimal_and_receipt_after_ack(self):
        receipt = replace_paid_window(self.rpc, self.raw, [self.row])
        self.assertEqual(len(self.calls), 1)
        name, payload = self.calls[0]
        self.assertEqual(name, 'replace_paid_fact_window')
        self.assertEqual(payload['p_rows'][0]['spend_usd'], '12345678901234567890.000001')
        self.assertEqual(payload['p_end_date'], '2026-09-02')
        self.assertEqual(receipt.raw, self.raw)

    def test_empty_complete_window_is_sent(self):
        replace_paid_window(self.rpc, replace(self.raw, source_row_count=0), [])
        self.assertEqual(self.calls[0][1]['p_rows'], [])

    def test_invalid_late_row_causes_no_rpc(self):
        for changes in ({'brand_classification': None}, {'brand_classification': 'unknown'},
            {'source_platform': 'call_tracking'}, {'analysis_date': '2026-09-03'},
            {'spend_usd': Decimal('NaN')}, {'spend_usd': 0.1}, {'clicks': True},
            {'impressions': -1}, {'campaign_names': ('A', 'B')},
            {'source_account_id': None}, {'brand_classification': 'not_applicable'}):
            with self.subTest(changes=changes), self.assertRaises(FactRowError):
                replace_paid_window(self.rpc, replace(self.raw, source_row_count=2),
                    [self.row, replace(self.row, **changes)])
            self.assertEqual(self.calls, [])

    def test_duplicate_keys_no_rpc(self):
        with self.assertRaisesRegex(FactRowError, 'duplicate'):
            replace_paid_window(self.rpc, replace(self.raw, source_row_count=2), [self.row]*2)
        self.assertEqual(self.calls, [])

    def test_missing_rows_no_rpc(self):
        with self.assertRaises(FactRowError):
            replace_paid_window(self.rpc, self.raw, [])
        self.assertEqual(self.calls, [])

    def test_failed_rpc_never_returns_completion(self):
        def fail(*args):
            raise RuntimeError('transaction failed')
        with self.assertRaises(RuntimeError):
            replace_paid_window(fail, self.raw, [self.row])

    def test_bad_ack_never_returns_completion(self):
        with self.assertRaises(FactRowError):
            replace_paid_window(lambda *args: None, self.raw, [self.row])

    def test_generator_failure_before_rpc(self):
        def broken():
            yield self.row
            raise RuntimeError('normalization failed')
        with self.assertRaises(RuntimeError):
            replace_paid_window(self.rpc, self.raw, broken())
        self.assertEqual(self.calls, [])

    def test_distinct_accounts_allowed(self):
        replace_paid_window(self.rpc, replace(self.raw, source_row_count=2),
            [self.row, replace(self.row, source_account_id='other')])
        self.assertEqual(len(self.calls[0][1]['p_rows']), 2)

    def test_valid_lsa_and_meta(self):
        for source, channel in [('lsa', 'google_lsa'), ('meta_ads', 'meta')]:
            row = replace(self.row, source_platform=source, channel=channel)
            if source == 'lsa':
                row = replace(row, source_account_id=None, campaign_id=None,
                    campaign_names=(), brand_classification='not_applicable', impressions=0, clicks=0, reported_leads=Decimal(1))
            raw = replace(self.raw, scope=SourceScope(source, 'all-accounts'))
            replace_paid_window(self.rpc, raw, [row])


class TransportTests(unittest.TestCase):
    def test_single_post_and_no_float_conversion(self):
        import json
        from unittest.mock import MagicMock, patch
        from scripts.normalization.persistence import PostgrestFactRpc
        response = MagicMock()
        response.__enter__.return_value = response
        response.headers = {}
        response.read.return_value = b'1'
        with patch('urllib.request.urlopen', return_value=response) as send:
            result = PostgrestFactRpc('https://offline.invalid', 'test-only')(
                'replace_paid_fact_window', {'p_rows': [{'spend_usd': '0.000001'}]})
        self.assertEqual(result, 1)
        send.assert_called_once()
        request = send.call_args.args[0]
        self.assertEqual(request.method, 'POST')
        self.assertTrue(request.full_url.endswith('/rpc/replace_paid_fact_window'))
        self.assertEqual(json.loads(request.data)['p_rows'][0]['spend_usd'], '0.000001')

    def test_rollback_preference_is_not_success(self):
        from unittest.mock import MagicMock, patch
        from scripts.normalization.persistence import PostgrestFactRpc
        response = MagicMock()
        response.__enter__.return_value = response
        response.headers = {'Preference-Applied': 'tx=rollback'}
        with patch('urllib.request.urlopen', return_value=response), self.assertRaises(FactRowError):
            PostgrestFactRpc('https://offline.invalid', 'test-only')('replace_paid_fact_window', {})
