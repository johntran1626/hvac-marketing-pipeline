"""Issue #59: deterministic offline source-to-fact-shaped evidence, no I/O clients."""
import argparse
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from scripts.normalization.calls import aggregate_calls, normalize_call_row, QUALIFIED_LEAD_RULE
from scripts.normalization.crm import SourceRules, aggregate_crm, normalize_crm_row

FIXTURE = Path(__file__).resolve().parents[1] / 'tests/fixtures/issue59/source-and-expected.json'
CALL_FIELDS = ('calls', 'first_time_calls', 'returning_calls', 'unique_leads', 'unresolved_calls')
CRM_FIELDS = ('jobs', 'completed_jobs', 'revenue_usd', 'known_completed_revenue_usd',
              'missing_completed_revenue_jobs', 'unresolved_jobs')


def load_fixture():
    return json.loads(FIXTURE.read_text())


def render(value):
    return format(value, '.2f') if isinstance(value, Decimal) else value


def actual_facts(fixture):
    """Exercise only the merged pure M2 code. No person-level Calls/CRM join."""
    calls = aggregate_calls((normalize_call_row(row) for row in fixture['calls']),
                            rule=QUALIFIED_LEAD_RULE)
    rules = SourceRules(**fixture['mapping'])
    crm_rows = deepcopy(fixture['crm'])
    for row in crm_rows:
        if row['revenue_usd'] is not None:
            row['revenue_usd'] = Decimal(row['revenue_usd'])
    crm = aggregate_crm(normalize_crm_row(row, rules=rules) for row in crm_rows)
    result = []
    for rows, fields in ((calls, CALL_FIELDS), (crm, CRM_FIELDS)):
        for row in rows:
            result.append({'bucket': list(row.bucket_key),
                           'metrics': {field: render(getattr(row, field)) for field in fields}})
    return result


def compare(expected, actual):
    """Full outer bucket comparison: preserve missing vs zero and null vs money."""
    def index(rows):
        result = {}
        for row in rows:
            key = tuple(row['bucket'])
            if key in result:
                raise ValueError('duplicate fact bucket')
            result[key] = row['metrics']
        return result
    left, right = index(expected), index(actual)
    differences = []
    for key in sorted(left.keys() | right.keys(), key=lambda key: json.dumps(key)):
        if key not in left or key not in right:
            differences.append(dict(bucket=list(key), field='__bucket__',
                                    expected=left.get(key), actual=right.get(key)))
            continue
        for field in sorted(left[key].keys() | right[key].keys()):
            if field not in left[key] or field not in right[key] or left[key][field] != right[key][field]:
                differences.append(dict(bucket=list(key), field=field,
                    expected=left[key].get(field), actual=right[key].get(field)))
    return differences


# Fixed mutations target the hand-authored expected fixture order, never production data.
MUTATIONS = (
    ('threshold_29_counted', 1, 'unique_leads', 2),
    ('returning_caller_counted', 1, 'unique_leads', 3),
    ('booking_dropped', 7, 'jobs', 4),
    ('scheduled_marked_completed', 7, 'completed_jobs', 2),
    ('gross_revenue_understated', 6, 'revenue_usd', '99.25'),
    ('unknown_attribution_hidden', 8, 'unresolved_jobs', 0),
    ('missing_revenue_zero_filled', 8, 'revenue_usd', '3.05'),
)


def build_report():
    fixture = load_fixture()
    expected = fixture['expected']
    actual = actual_facts(fixture)
    baseline = compare(expected, actual)
    cases = [dict(name='normal', classification='SYNTHETIC', mismatches=baseline,
                  expected_mismatches=[], passed=not baseline)]
    for name, position, field, value in MUTATIONS:
        corrupted = deepcopy(actual)
        key = expected[position]['bucket']
        next(row for row in corrupted if row['bucket'] == key)['metrics'][field] = value
        wanted = [dict(bucket=key, field=field,
                       expected=expected[position]['metrics'][field], actual=value)]
        found = compare(expected, corrupted)
        cases.append(dict(name=name, classification='SYNTHETIC fact corruption',
                          mismatches=found, expected_mismatches=wanted, passed=found == wanted))
    for name, position, dimension, value in (
        ('shifted_date_bucket', 0, 0, '2026-09-23'),
        ('ambiguous_source_forced_to_paid', 8, 1, 'meta'),
        ('invented_account', 0, 3, 'synthetic-account'),
    ):
        corrupted = deepcopy(actual)
        original = expected[position]
        changed = next(row for row in corrupted if row['bucket'] == original['bucket'])
        changed['bucket'][dimension] = value
        wanted = [dict(bucket=original['bucket'], field='__bucket__', expected=original['metrics'], actual=None),
                  dict(bucket=changed['bucket'], field='__bucket__', expected=None, actual=original['metrics'])]
        wanted.sort(key=lambda row: json.dumps(row['bucket']))
        found = compare(expected, corrupted)
        cases.append(dict(name=name, classification='SYNTHETIC fact corruption',
                          mismatches=found, expected_mismatches=wanted, passed=found == wanted))
    for name, source, mutation, message in (
        ('duplicate_call', 'calls', 'duplicate', 'duplicate call_id; provide current upserted rows'),
        ('duplicate_job', 'crm', 'duplicate', 'duplicate job_id; provide current upserted jobs'),
        ('conflicting_first_time', 'calls', 'first', 'caller has multiple first-time records in supplied history'),
    ):
        corrupt = deepcopy(fixture)
        if mutation == 'duplicate':
            corrupt[source].append(deepcopy(corrupt[source][0]))
        else:
            corrupt['calls'][3]['first_time_caller'] = True
        observed = None
        try:
            actual_facts(corrupt)
        except ValueError as error:
            observed = str(error)
        cases.append(dict(name=name, classification='SYNTHETIC source corruption',
                          expected_error=message, actual_error=observed, passed=observed == message))
    return dict(scope='Offline M2 fact-shaped normalization only; no deployed database validation.',
                historical_discrepancy='Not claimed: no independently verified historical discrepancy.',
                fixture_sha256=hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
                expected_facts=expected, actual_facts=actual, cases=cases,
                passed=all(case['passed'] for case in cases))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = build_report()
    output = json.dumps(report, indent=2, sort_keys=True) + '\n'
    if args.output:
        args.output.write_text(output)
    print(output, end='')
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
