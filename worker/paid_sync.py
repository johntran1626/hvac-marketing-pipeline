"""Fenced full-window paid sync. The shipped API cannot attest immutable snapshots.

No row-count inference, no old raw-table reads, no saved cursor resume, and no
fallback to ordinary upserts. A future reviewed snapshot provider must implement
require_paid_snapshot_support and snapshot_manifest/snapshot_pages.
"""
from dataclasses import dataclass
from datetime import date, datetime, timezone
from hashlib import sha256

from scripts.normalization.coverage import (
    SourceScope, PageReceipt, complete_raw_window, plan_refresh, complete_refresh,
)
from scripts.normalization.daily import aggregate_daily
from scripts.normalization.google import normalize_google_row
from scripts.normalization.meta import normalize_meta_row
from scripts.normalization.lsa import normalize_lsa_row
from scripts.normalization.persistence import replace_paid_window
from worker.paid_transport import exact_json

SOURCE_PLATFORMS = {'google_ads': 'google_ads', 'meta': 'meta_ads', 'lsa': 'lsa'}
NORMALIZERS = {'google_ads': normalize_google_row, 'meta_ads': normalize_meta_row, 'lsa': normalize_lsa_row}


class UnsafeSnapshot(RuntimeError):
    pass


@dataclass(frozen=True)
class SnapshotManifest:
    """Provider-issued immutable full-window manifest, not a worker-made digest.

    All accounts, exact source/date params; digest covers canonical exact_json
    of the entire ordered raw array, supplied independently of the page traversal.
    The provider must acquire a CURRENT snapshot after this run's fence begins.
    A locally calculated checksum of fetched pages does not establish completeness.
    """
    source_platform: str
    generation: int
    start_date: date
    end_date: date
    snapshot_id: str
    acquired_at: datetime
    sha256: str
    all_accounts: bool


@dataclass(frozen=True)
class SnapshotPage:
    snapshot_id: str
    request_cursor: str | None
    next_cursor: str | None
    rows: tuple[dict, ...]


def load_window(api, db, src, scope, window, generation, started_at):
    manifest = api.snapshot_manifest(src, window, generation)
    if (not isinstance(manifest, SnapshotManifest) or
        manifest.source_platform != scope.source_platform or manifest.generation != generation or
        manifest.start_date != window.start_date or manifest.end_date != window.end_date or
        manifest.all_accounts is not True or not isinstance(manifest.snapshot_id, str) or not manifest.snapshot_id or
        not isinstance(manifest.acquired_at, datetime) or manifest.acquired_at.tzinfo is None or
        not started_at <= manifest.acquired_at <= datetime.now(timezone.utc)):
        raise UnsafeSnapshot('Missing current authoritative all-account snapshot manifest')
    rows, receipts, seen, cursor = [], [], set(), None
    terminal = False
    for page in api.snapshot_pages(src, window, manifest):
        if (not isinstance(page, SnapshotPage) or terminal or page.snapshot_id != manifest.snapshot_id or
            page.request_cursor != cursor or page.request_cursor in seen or
            (page.next_cursor is not None and (not isinstance(page.next_cursor, str) or not page.next_cursor)) or
            not isinstance(page.rows, tuple) or any(not isinstance(row, dict) for row in page.rows)):
            raise UnsafeSnapshot('Invalid, duplicate or drifting snapshot page')
        seen.add(page.request_cursor)
        rows.extend(page.rows)
        receipts.append(PageReceipt(scope, window, cursor, page.next_cursor, len(page.rows), True))
        cursor = page.next_cursor
        terminal = cursor is None
    if not terminal or not receipts:
        raise UnsafeSnapshot('Incomplete pagination; no terminal page')
    if sha256(exact_json(rows).encode()).hexdigest() != manifest.sha256:
        raise UnsafeSnapshot('Snapshot differs from independently supplied manifest')
    # Validate every raw record and natural key before staging. No invalid row is skipped.
    daily = aggregate_daily(NORMALIZERS[scope.source_platform](row) for row in rows)
    params = dict(p_source=scope.source_platform, p_generation=generation,
                  p_start=window.start_date.isoformat(), p_end=window.end_date.isoformat(),
                  p_snapshot_id=manifest.snapshot_id, p_acquired_at=manifest.acquired_at.isoformat(), p_raw=rows)
    count = db.paid_rpc('stage_paid_source_window', params)
    if type(count) is not int or count != len(rows):
        raise UnsafeSnapshot('Durable staging acknowledgement missing')
    # Receipts only become raw_persisted attestations AFTER the durable stage ACK.
    raw = complete_raw_window(scope, window, receipts, completed_at=datetime.now(timezone.utc))

    def fenced_rpc(name, payload):
        if name != 'replace_paid_fact_window':
            raise UnsafeSnapshot('Unsupported fact writer')
        return db.paid_rpc('persist_paid_source_window', {**params, 'p_facts': payload['p_rows']})

    # The RPC independently reconciles the exact staged raw snapshot and facts in SQL.
    return replace_paid_window(fenced_rpc, raw, daily)


def run(api, db, src):
    # This guard performs no network or database access in the shipped ApiClient.
    # It cannot be bypassed with an environment flag or a row-count attestation.
    api.require_paid_snapshot_support(src)
    source = SOURCE_PLATFORMS[src.name]
    run_info = db.paid_rpc('begin_paid_source_run', {'p_source': source})
    generation = run_info['generation']
    started_at = datetime.fromisoformat(run_info['started_at'])
    if type(generation) is not int or generation < 1 or started_at.tzinfo is None:
        raise UnsafeSnapshot('Invalid durable source fence acknowledgement')
    try:
        through = api.data_through()
        previous = run_info['committed_through']
        scope = SourceScope(source, 'worker-all-accounts')
        plan = plan_refresh(scope, history_start=src.first_day, api_data_through=through,
            previous_data_through=date.fromisoformat(previous) if previous else None, started_at=started_at)
        ack = db.paid_rpc('plan_paid_source_run', dict(p_source=source, p_generation=generation,
            p_through=through.isoformat(), p_windows=[{'start':w.start_date.isoformat(),'end':w.end_date.isoformat()} for w in plan.windows]))
        if ack is not True:
            raise UnsafeSnapshot('Source plan acknowledgement missing')
        completed = [load_window(api, db, src, scope, w, generation, started_at) for w in plan.windows]
        complete_refresh(plan, completed)
        if db.paid_rpc('finish_paid_source_run', {'p_source':source,'p_generation':generation}) is not True:
            raise UnsafeSnapshot('Source completion acknowledgement missing')
    except BaseException:
        # An older worker cannot mark a newer run failed. A lost completion ACK
        # may mean finish committed; fail then rejects the inactive generation.
        try:
            db.paid_rpc('fail_paid_source_run', {'p_source':source,'p_generation':generation})
        except Exception:
            pass
        raise
