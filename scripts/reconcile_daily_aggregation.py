"""Offline, independently runnable reconciliation against synthetic source/day rows."""
import argparse
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from scripts.normalization.daily import aggregate_daily, DailyAggregationError

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/issue68-daily.json'

@dataclass(frozen=True)
class FixtureContribution:
    analysis_date: str
    channel: str
    source_platform: str
    source_account_id: str | None
    campaign_id: str | None
    campaign_name: str | None
    brand_classification: str | None
    raw_key: tuple[str, ...]
    impressions: int
    clicks: int
    spend_usd: Decimal
    reported_leads: Decimal

def load_row(data):
    return FixtureContribution(**{**data, 'raw_key': tuple(data['raw_key']),
        'spend_usd': Decimal(data['spend_usd']),
        'reported_leads': Decimal(data['reported_leads'])})

def reconcile_cases(path=FIXTURE):
    cases = json.loads(Path(path).read_text())['cases']
    findings = []
    for case in cases:
        expected = case['expected']
        try:
            actual_rows = aggregate_daily(map(load_row, case['rows']))
            actual = [{'key': list(row.bucket_key), 'spend_usd': str(row.spend_usd),
                       'reported_leads': str(row.reported_leads), 'source_row_count': row.source_row_count}
                      for row in actual_rows]
            observed = {'buckets': actual}
        except DailyAggregationError as exc:
            observed = {'error': str(exc)}
        passed = observed == expected
        findings.append({'case': case['id'], 'pass': passed, 'expected': expected, 'actual': observed})
    return findings

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fixture', type=Path, default=FIXTURE)
    args = parser.parse_args()
    findings = reconcile_cases(args.fixture)
    print(json.dumps(findings, indent=2))
    count = sum(row['pass'] for row in findings)
    print(f'{count}/{len(findings)} daily reconciliation cases passed')
    return 0 if count == len(findings) else 1

if __name__ == '__main__':
    raise SystemExit(main())
