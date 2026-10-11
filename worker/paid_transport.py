"""One-shot RPC transport: exact Decimal JSON, no automatic ambiguous-write retry."""
import json
import urllib.request
from decimal import Decimal


def exact_json(value):
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError('Non-finite decimal')
        return str(value)
    if isinstance(value, float):
        raise ValueError('Binary floats are not accepted in paid snapshots')
    if isinstance(value, dict):
        if any(not isinstance(k, str) for k in value):
            raise ValueError('JSON object keys must be strings')
        return '{' + ','.join(json.dumps(k)+':'+exact_json(value[k]) for k in sorted(value)) + '}'
    if isinstance(value, (list, tuple)):
        return '[' + ','.join(exact_json(x) for x in value) + ']'
    return json.dumps(value, allow_nan=False, separators=(',', ':'))


def rpc(base, headers, name, params):
    allowed = {'begin_paid_source_run','plan_paid_source_run','stage_paid_source_window',
               'persist_paid_source_window','finish_paid_source_run','fail_paid_source_run'}
    if name not in allowed:
        raise ValueError('Unsupported paid RPC')
    req = urllib.request.Request(f'{base}/rpc/{name}', method='POST',
        data=exact_json(params).encode(), headers={**headers, 'Prefer':'tx=commit'})
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            if 'tx=rollback' in response.headers.get('Preference-Applied',''):
                raise RuntimeError('Paid RPC rolled back')
            return json.loads(response.read(), parse_float=Decimal)
    except Exception:
        # Do not leak URLs, diagnostics, source records or request headers.
        raise RuntimeError('Paid RPC failed or acknowledgement lost; do not publish success') from None
