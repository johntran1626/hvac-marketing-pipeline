"""Complete source/window replacement; transport must perform ONE committed RPC.

No credentials, raw fetching or sync-state writes. RawCoverage is a caller
attestation, not a proof that the upstream dataset was fetched completely.
"""
from datetime import datetime, timezone
from decimal import Decimal

from .coverage import RawCoverage, complete_normalized_window
from .daily import BIGINT_MAX, DailyContribution
from .fact_rows import FactRowError, to_fact_row

CHANNELS = {'google_ads': 'google_ads', 'meta_ads': 'meta', 'lsa': 'google_lsa'}


def replace_paid_window(rpc, raw: RawCoverage, rows):
    """rpc(name, params) must return the decoded result AFTER database commit.

    Supply the entire source, all accounts, for raw.window, not a page or
    changed-only rows. No completion receipt is returned on any failure.
    Decimal values go over JSON as strings, never through binary floats.
    """
    if not isinstance(raw, RawCoverage):
        raise FactRowError('complete raw coverage required')
    now = datetime.now(timezone.utc)
    # Validate receipt chronology before any remote operation.
    complete_normalized_window(raw, normalized_at=now, facts_persisted=True)
    if type(raw.page_count) is not int or raw.page_count < 1:
        raise FactRowError('complete page chain required')
    if type(raw.source_row_count) is not int or raw.source_row_count < 0:
        raise FactRowError('invalid raw row count')
    staged, seen, count = [], set(), 0
    for row in rows:
        if not isinstance(row, DailyContribution):
            raise FactRowError('expected DailyContribution')
        if row.source_platform != raw.scope.source_platform or row.channel != CHANNELS[raw.scope.source_platform]:
            raise FactRowError('source/channel mismatch')
        fact = to_fact_row(row, synced_at=now, data_through=raw.window.end_date)
        if not raw.window.start_date.isoformat() <= row.analysis_date <= raw.window.end_date.isoformat():
            raise FactRowError('row outside inclusive window')
        for value in (row.source_account_id, row.campaign_id):
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise FactRowError('invalid source identifier')
        if any(not isinstance(name, str) or not name.strip() for name in row.campaign_names):
            raise FactRowError('invalid campaign name')
        if row.source_platform == 'lsa':
            if row.source_account_id is not None or row.campaign_id is not None or row.campaign_names or row.brand_classification != 'not_applicable' or row.impressions or row.clicks:
                raise FactRowError('invalid LSA dimensions/metrics')
        elif row.source_account_id is None or row.campaign_id is None or row.brand_classification == 'not_applicable':
            raise FactRowError('paid campaign requires account, campaign and resolved brand')
        for value in (row.impressions, row.clicks):
            if type(value) is not int or not 0 <= value <= BIGINT_MAX:
                raise FactRowError('invalid integer metric')
        for value in (row.spend_usd, row.reported_leads):
            if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
                raise FactRowError('invalid Decimal metric')
        if type(row.source_row_count) is not int or row.source_row_count < 1:
            raise FactRowError('invalid contribution provenance')
        if row.source_platform == 'lsa' and row.reported_leads != Decimal(row.source_row_count):
            raise FactRowError('LSA reported leads must equal raw lead count')
        if row.bucket_key in seen:
            raise FactRowError('duplicate fact grain')
        seen.add(row.bucket_key)
        count += row.source_row_count
        staged.append(fact)
    if count != raw.source_row_count:
        raise FactRowError('batch does not account for complete raw window')
    result = rpc('replace_paid_fact_window', {
        'p_source_platform': raw.scope.source_platform,
        'p_start_date': raw.window.start_date.isoformat(),
        'p_end_date': raw.window.end_date.isoformat(), 'p_rows': staged,
    })
    if type(result) is not int or result != len(staged):
        raise FactRowError('unexpected RPC acknowledgement; do not publish freshness')
    return complete_normalized_window(raw, normalized_at=datetime.now(timezone.utc),
                                      facts_persisted=True)


class PostgrestFactRpc:
    """Standard-library server-side transport; never reads environment/secrets.

    A single POST is one PostgREST transaction. A timeout has an unknown commit
    outcome: propagate it, publish no success, and replay a COMPLETE window
    only under the worker's source/run serialization policy.
    """
    def __init__(self, supabase_url, secret_key, *, timeout=60):
        self.url = supabase_url.rstrip('/') + '/rest/v1/rpc/replace_paid_fact_window'
        self.secret_key = secret_key
        self.timeout = timeout

    def __call__(self, name, params):
        import json
        import urllib.request
        if name != 'replace_paid_fact_window':
            raise FactRowError('unsupported RPC')
        request = urllib.request.Request(self.url, method='POST',
            data=json.dumps(params, allow_nan=False).encode('utf-8'), headers={
                'apikey': self.secret_key, 'Authorization': f'Bearer {self.secret_key}',
                'Content-Type': 'application/json', 'Prefer': 'tx=commit',
            })
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            if 'tx=rollback' in response.headers.get('Preference-Applied', ''):
                raise FactRowError('server rolled back RPC; no completion')
            return json.loads(response.read())
