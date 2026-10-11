import unittest
from datetime import date, datetime, timezone
from decimal import Decimal

from scripts.normalization.daily import DailyContribution
from scripts.normalization.fact_rows import FactRowError, to_fact_row


class FactRowsTests(unittest.TestCase):
    def make_row(self, **updates):
        fields = dict(analysis_date='2026-09-30', channel='google_ads',
            source_platform='google_ads', source_account_id='account-A',
            campaign_id='camp-1', brand_classification='brand',
            campaign_names=('Main',), source_row_count=1, impressions=7,
            clicks=2, spend_usd=Decimal('1.230000'), reported_leads=Decimal('0.5'))
        fields.update(updates)
        return DailyContribution(**fields)

    def convert(self, row):
        return to_fact_row(row, synced_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
                           data_through=date(2026, 9, 30))

    def test_preserves_account_grain_exact_decimal_and_zeroes_unattributed_metrics(self):
        a = self.convert(self.make_row())
        b = self.convert(self.make_row(source_account_id='account-B'))
        self.assertNotEqual(a['source_account_id'], b['source_account_id'])
        self.assertEqual(a['spend_usd'], '1.230000')
        self.assertEqual(a['reported_leads'], '0.5')
        self.assertEqual((a['unique_leads'], a['calls'], a['jobs'], a['revenue_usd']),
                         (0, 0, 0, '0'))
        self.assertEqual(a['campaign_name'], 'Main')

    def test_refuses_unresolved_brand(self):
        with self.assertRaises(FactRowError):
            self.convert(self.make_row(brand_classification=None))

    def test_refuses_ambiguous_campaign_name(self):
        with self.assertRaises(FactRowError):
            self.convert(self.make_row(campaign_names=('A','B')))

    def test_refuses_unattested_freshness(self):
        with self.assertRaises(FactRowError):
            to_fact_row(self.make_row(), synced_at=datetime(2026, 10, 1),
                        data_through=date(2026, 9, 30))
        with self.assertRaises(FactRowError):
            to_fact_row(self.make_row(), synced_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
                        data_through=date(2026, 9, 29))


if __name__ == '__main__':
    unittest.main()
