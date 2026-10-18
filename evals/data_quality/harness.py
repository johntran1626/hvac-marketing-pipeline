"""Offline fixture contract evaluator; no production worker or service imports."""
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

FIXTURES = Path(__file__).with_name('fixtures.json')
CHECKS = {
    'DQ01': 'Latest restatement replaces prior day',
    'DQ02': 'Repeated call IDs',
    'DQ03': 'Distinct qualified callers',
    'DQ04': 'Source-local date boundaries',
    'DQ05': 'First-time AND at least 30 seconds',
    'DQ06': 'Conflicting first-time records',
    'DQ07': 'Missing spend',
    'DQ08': 'Missing or zero denominator',
    'DQ09': 'Ambiguous brand/source attribution',
    'DQ10': 'Raw/fact call reconciliation',
}


def inspect(data):
    """Return stable finding IDs and row-level evidence for every named check."""
    findings = {key: [] for key in CHECKS}

    def flag(check, key, expected, actual):
        findings[check].append({'key': key, 'expected': expected, 'actual': actual})

    latest = {}
    for row in data['restatements']:
        key = (row['date'], row['campaign_id'], row['ad_group_id'])
        if key not in latest or row['revision'] > latest[key]['revision']:
            latest[key] = row
    facts = defaultdict(list)
    for row in data['ad_facts']:
        facts[(row['date'], row['campaign_id'], row['ad_group_id'])].append(row['conversions'])
    for key in sorted(latest.keys() | facts.keys()):
        expected = [latest[key]['conversions']] if key in latest else []
        if facts[key] != expected:
            flag('DQ01', '/'.join(key), expected, facts[key])

    counts = Counter(row['call_id'] for row in data['calls'])
    for key, count in sorted(counts.items()):
        if count > 1:
            flag('DQ02', key, 1, count)

    qualified = {row['caller_hash'] for row in data['calls']
                 if row['first_time_caller'] is True and row['duration_sec'] >= 30}
    if data['unique_callers'] != len(qualified):
        flag('DQ03', 'unique_callers', len(qualified), data['unique_callers'])

    zones = {'calls': 'America/Chicago', 'lsa': 'America/Chicago',
             'google_ads': 'America/Chicago', 'meta': 'America/Los_Angeles'}
    for row in data['dates']:
        # Account date strings are already local dates, never UTC timestamps.
        if 'account_date' in row:
            expected = row['account_date']
        else:
            instant = datetime.fromisoformat(row['timestamp'].replace('Z', '+00:00'))
            if instant.tzinfo is None:
                raise ValueError('Timestamp must include a UTC offset')
            expected = instant.astimezone(ZoneInfo(zones[row['source']])).date().isoformat()
        if row['fact_date'] != expected:
            flag('DQ04', row['id'], expected, row['fact_date'])

    by_id = defaultdict(list)
    by_caller = defaultdict(list)
    for row in data['calls']:
        expected = row['first_time_caller'] is True and row['duration_sec'] >= 30
        if row['qualified'] is not expected:
            flag('DQ05', row['call_id'], expected, row['qualified'])
        by_id[row['call_id']].append(row)
        by_caller[row['caller_hash']].append(row)
    for key, rows in sorted(by_id.items()):
        values = sorted({r['first_time_caller'] for r in rows})
        if len(values) > 1:
            flag('DQ06', 'call:' + key, 'consistent first_time_caller', values)
    for key, rows in sorted(by_caller.items()):
        first_ids = sorted({r['call_id'] for r in rows if r['first_time_caller'] is True})
        if len(first_ids) > 1:
            flag('DQ06', 'caller:' + key, 'at most one first-time call', first_ids)

    for row in data['metrics']:
        if row.get('spend') is None:
            flag('DQ07', row['id'], 'present spend (zero is valid)', None)
        if row.get('denominator') is None or row['denominator'] <= 0:
            flag('DQ08', row['id'], 'positive denominator', row.get('denominator'))

    for row in data['attributions']:
        candidates = sorted({(r['source'], r['brand']) for r in row['candidates']})
        if len(candidates) != 1:
            flag('DQ09', row['id'], 'exactly one source/brand candidate', candidates)

    raw = defaultdict(list)
    fact = defaultdict(list)
    for row in data['calls']:
        raw[row['call_id']].append(row['duration_sec'])
    for row in data['call_facts']:
        fact[row['call_id']].append(row['duration_sec'])
    for key in sorted(raw.keys() | fact.keys()):
        if sorted(raw[key]) != sorted(fact[key]):
            flag('DQ10', key, sorted(raw[key]), sorted(fact[key]))
    return findings


def evaluate(suite):
    results = []
    names = set()
    if not suite['cases']:
        raise ValueError('Fixture suite must not be empty')
    for case in suite['cases']:
        if case['name'] in names:
            raise ValueError('Duplicate case name')
        names.add(case['name'])
        if set(case['expected']) != set(CHECKS):
            raise ValueError('Every case must declare expectations for every check')
        data = deepcopy(suite['normal'])
        for change in case['changes']:
            parent = data
            for part in change['path'][:-1]:
                parent = parent[part]
            parent[change['path'][-1]] = deepcopy(change['value'])
        for check, evidence in inspect(data).items():
            actual = sorted(item['key'] for item in evidence)
            expected = sorted(case['expected'][check])
            results.append({'case': case['name'], 'check_id': check,
                            'name': CHECKS[check], 'pass': actual == expected,
                            'expected': expected, 'actual': actual,
                            'evidence': evidence or ['No violations in fixture input']})
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixtures', type=Path, default=FIXTURES)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    try:
        results = evaluate(json.loads(args.fixtures.read_text()))
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(f'ERROR: {error}')
        return 2
    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        for result in results:
            status = 'PASS' if result['pass'] else 'FAIL'
            print(f"{status} {result['case']} {result['check_id']} {result['name']} "
                  f"expected={json.dumps(result['expected'])} actual={json.dumps(result['actual'])} "
                  f"evidence={json.dumps(result['evidence'], sort_keys=True)}")
        print(f"{sum(r['pass'] for r in results)}/{len(results)} expectations passed")
    return 0 if all(r['pass'] for r in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
