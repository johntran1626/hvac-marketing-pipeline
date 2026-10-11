# Issue #30: guarded worker persistence integration

## Status

Safe for teammate code review and offline testing. **Not ready to enable on a
hosted worker.** The shipped API client fails closed before network/database
access for paid sources because the documented API cannot supply an immutable,
current, all-account snapshot manifest with revision-bound pages. No completeness
claim is made from terminal cursors, page counts or row counts alone.

New branch: `30-safe-persistence-integration`

Base: `5c32cef88a25943c5c7c3da4d6af1ef23935dd80` (PR #49).
No commits, pushes, merges, PRs, deployment or production Supabase access.
No dependency installation. Existing PGlite under `/private/tmp` was reused.
The reviewed no-Git directory and all existing checkouts were read only.

## Upstream inspected

All six PRs were OPEN and unmerged when rechecked during draft preparation:

| PR | Head | Base | Inspected head SHA |
|---|---|---|---|
| #43 | 25-worker-scaffold | main | b27f04eaba4bb624631d40982a0073ce95e6c177 |
| #44 | 28-lsa-worker | 25-worker-scaffold | 41e8a51ef7e771b4843447c369fc5fb7a21aa0da |
| #45 | 26-google-ads-sync | 28-lsa-worker | 6d1d24e9c3c84cb6dcff8172560d1c8aec5db555 |
| #46 | 32-actions-workflow | 26-google-ads-sync | d2cad75d6067214008fc8752ee6d3f579fedd4fb |
| #48 | 36-api-client | 25-worker-scaffold | 6776d0a9591450bc52bd396e51182daa9fc89b3d |
| #49 | 37-calls-sync | 32-actions-workflow | 5c32cef88a25943c5c7c3da4d6af1ef23935dd80 |

The #49 base contains #43/#44/#45/#46 as ancestors (verified with
`git merge-base --is-ancestor`). Only #48's `worker/http.py` change and API-client
tests were applied to this worktree; unrelated hour logs were not copied.
Those two files are byte-identical upstream ports from PR #48, not original
Issue #30 implementation. Keep their provenance explicit in the PR and commit.
HEAD exactly matches the inspected PR #49 head; the proposed stacked PR base
is `37-calls-sync`, not `main`, so the ancestor teammate commits stay out of
this PR's change set. Recheck the base before publication if the stack moves.
Issue #30 also depends on Meta Issue #27, which remains open; no open Meta PR
was returned by the repository PR listing. The source descriptor here does not
claim to complete #27's live ingestion requirements.
#46's GitHub concurrency group was inspected: it coordinates that workflow,
not manual workers or other deployments. It is not used as the data fence.

The existing Meta loader worktree has uncommitted files. They were inspected
but not changed. This worktree adds its own equivalent Meta source descriptor.
The reviewed persistence copy contains the normalization prerequisites; only
necessary source, test, fixture, reconciliation and migration files were copied.
`m2-integration-reviewed-manifest.json` pins all 22 copied files. Their content
was checked against both the manifest and the preserved reviewed directory.

## Implemented protections

### Durable source generation before acquisition

`worker.sync.run` explicitly routes `google_ads`, `meta`, and `lsa` to
`worker.paid_sync`. Mapping to fact platforms is explicit:
`google_ads -> google_ads`, `meta -> meta_ads`, `lsa -> lsa`.

The database issues a monotonically increasing source generation before health
lookup and snapshot acquisition. Every staging, replacement, failure and success
operation checks that generation under the same source advisory transaction
lock. Starting a newer run invalidates every older run for that source, including
partially overlapping windows. Stale workers cannot overwrite facts, mark the
new worker failed or publish success. This is durable fencing across the whole
acquisition/normalization/publication lifecycle, not merely a final-write lock.
The namespace is one shared all-account dataset per source, as in the worker;
multi-tenant/different API datasets must not share these tables.

### Complete immutable snapshots, never leftover raw upserts

The future provider contract is `SnapshotManifest` plus `SnapshotPage`:
source, window, generation, immutable snapshot ID, acquisition timestamp,
all-account scope, and an independently supplied whole-snapshot digest. Every
page must use the same immutable ID and cursor chain, including the terminal
page. The entire ordered array must match the provider manifest. A checksum
computed only from whatever pages the worker happened to fetch is insufficient.

Provider JSON parsing must use Decimal for decimal numeric tokens. Binary floats
are rejected by the paid transport. The canonical digest is SHA-256 over
`exact_json` of the ordered raw array (sorted object keys; Decimal JSON numeric
literals; no rounding or float conversion). Snapshot/currentness attestation is
a provider trust boundary, not something a hash or generation token proves.
The repository does NOT yet contain an API provider capable of this contract;
the concrete client raises `UnsafeSnapshot`. There is no environment switch that
turns row counts into proof or silently falls back to unfenced loading.

Complete snapshots are stored durably in a private run/window record before the
reviewed persistence adapter receives a RawCoverage receipt. Normalization uses
only this acquired array, never reads historical raw upsert tables, never resumes
an old cursor and never silently skips a campaign, invalid record or failed page.
Exact natural-key duplicates fail. Unknown brands and conflicting campaign names
fail the whole window rather than being classified or omitted.

Within one fenced RPC, the complete source/window replaces current raw rows,
then calls the unchanged reviewed fact-replacement implementation. Disappeared
raw records and their facts are removed, including entirely empty windows.
Raw payload fields are preserved in the staged JSON; unexpected fields cause a
rejection rather than being silently discarded by typed raw-table insertion.
A natural key unexpectedly moving across date windows causes an insertion error
and rollback rather than silently moving another window's data.

### Independent reconciliation and success publication

The RPC compares staged/current raw data against facts with independently written
SQL, including day, source account, campaign, campaign name, reviewed brand map,
impressions, clicks, exact spend and reported leads. It does not import Python
normalization. Offsetting account errors with equal daily totals are detected.
LSA uses Central creation day and net CHARGED cost; Meta retains Pacific dates.
Every mismatch or write failure rolls back raw replacement and fact replacement
together. Receipt/reconciliation status is written only after these checks.

The database independently validates the canonical full refresh plan, including
missed windows and the conservative mutable lookback from the prior certified
watermark. Existing raw-only `sync_state.backfilled_through` is NOT a certified
fact watermark. Initial integration therefore requires a complete backfill.
Only `finish_paid_source_run`, after EVERY planned window has a reconciliation
receipt, advances `paid_source_runs.committed_through` and sync_state success.
Per-window row freshness is not advertised as whole-source freshness. A failed
multi-window run can leave earlier committed windows visible, but cannot advance
the source-wide watermark. This is per-window atomicity, not whole-run atomicity.

Transport sends a single RPC attempt. Timeout/failed/lost ACK produces no Python
completion receipt or subsequent success call. Identical payload replay within
the still-active generation is idempotent in SQL; changed payloads and superseded
generations are rejected. The worker itself aborts and reacquires a fresh run
instead of retrying an ambiguous write with recomputed timestamps. A lost ACK
for finish may leave database status `ok` only if all windows already reconciled;
a subsequent failure update cannot undo that completed generation.

### Bypass prevention

- `scripts/build_fact_lsa.sql` now raises immediately; its old upsert is retired.
- The legacy paid `sync.load_window` path and direct worker fact upserts raise.
- The reviewed unfenced RPC is moved to `paid_sync_private`; no old public REST endpoint
  remains. Its original migration/source are byte-identical to the review copy.
- Database triggers reject legacy direct paid raw/fact/sync-state writes without
  the active transaction's source-generation context. Calls/CRM fact sources and
  non-paid sync rows remain outside these guards. Guarded functions are invoker
  functions with empty search_path; new objects use RLS and restricted grants.

These protections cover application writers, not a trusted database administrator
who can change grants/triggers or set arbitrary SQL session state. The new `paid_sync_private`
schema must remain excluded from PostgREST's exposed schemas. This configuration
was not inspected on a hosted project. Old worker deployments must be stopped
before eventual rollout: their raw/state writes will intentionally be rejected.

## Migration order (local tests only)

1. Existing raw/fact schema and permissive-raw migration.
2. PR #43 `20261008200000_create_sync_state.sql` and
   `20261008200100_fact_grain_by_source.sql`.
3. Reviewed `20261011011135_replace_paid_fact_window.sql`, unchanged. It verifies
   the source/account-aware UNIQUE NULLS NOT DISTINCT grain and fails if absent.
4. CLI-generated `20261011035452_fence_paid_source_runs.sql`.

No migration was applied to Supabase. The new SQL migration was exercised only
against in-memory PGlite. A one-second upper acquisition-clock tolerance handles
millisecond database clocks versus Python microseconds; the lower bound remains
the source-run start. Generation checks, not wall clocks, are the write fence.
Clock skew beyond the guard fails closed rather than weakening snapshot checks.

## Verification

The latest offline validation after the runner fix passed 204 tests:

| Suite | Passed |
|---|---:|
| Normalization/persistence Python | 126 |
| Worker Python, including 8 runner regression tests | 46 |
| Reviewed SQL persistence | 15 |
| Fenced SQL integration and Python bridge | 17 |

The 8 runner tests also passed separately; they are included in 46, not added
again to 204. All commands exited 0. Existing mocked HTTP tests emitted five
ResourceWarnings. SQL ran on PGlite 0.5.8 / PostgreSQL 18.3 in memory.

Reproduce from the repository root using an already installed PGlite module
path in `PGLITE_MODULE` (no dependency installation is performed by the tests):

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest worker.tests.test_run -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s worker/tests -t .
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py'
PR43_GRAIN_SQL=supabase/migrations/20261008200100_fact_grain_by_source.sql node tests/sql/test_paid_persistence.mjs
PYTHONDONTWRITEBYTECODE=1 node tests/sql/test_paid_integration.mjs
```

Export `PGLITE_MODULE` before the SQL commands. The old local raw test transcript
is excluded from the proposed PR; this summary supersedes its pre-fix totals.

The suites cover incomplete/cyclic/drifting pagination, equal-count wrong
snapshots, stale snapshots, out-of-order/overlapping workers, disappeared raw
rows, duplicate keys, missing brand mappings, failed RPCs, lost acknowledgements,
source isolation, exact Decimal transport, SQL reconciliation, legacy bypasses,
insert failure after deletion, outer rollback, roles and publication ordering.

The SQL bridge executes the actual Python orchestrator for Google, Meta and LSA
against the real local SQL functions. JSONB parameters cross the test bridge as
encoded JSON strings to avoid JavaScript float conversion. This test uses a
synthetic authoritative provider; it does not claim the Lab API has one.

## Remaining blockers / unverified hosted assumptions

- Obtain and review an upstream immutable snapshot/export contract (or another
  independently demonstrated consistency/completeness guarantee). Implement its
  current-snapshot acquisition, all-account manifest and revision-bound paging.
  `docs/API.md` promises terminal-cursor exhaustion but does not establish that
  pages are pinned while recent data changes. Two identical fetches or equal row
  counts are not substituted for that missing guarantee.
- Merge/reconcile the open PR stack through normal teammate review and apply the
  prerequisite migrations in order. This worktree does not make them merged.
- Test genuine concurrent sessions on a disposable PostgreSQL/Supabase instance.
  PGlite tests ordered interleavings and actual SQL rollback, but is single-session.
  Hosted lock contention, role defaults, PostgREST commit/timeout/schema-cache
  behavior and compatibility with the hosted PostgreSQL version remain unverified.
- Verify private-schema exposure and disable old writers before rollout. No
  production roles, credentials or project configuration were inspected.
- Review retention/size limits for raw snapshot receipts. They intentionally
  retain audit evidence; no destructive cleanup policy was guessed. Large batch
  performance and HTTP payload limits have not been load-tested.
- No hosted advisors, live API reads or Supabase queries were run. Current paid
  CLI execution is deliberately blocked, so no live freshness advancement is
  claimed. The default all-source command now attempts Calls despite ordinary
  paid-source failures, prints fixed per-source success/failure labels without
  exception payloads, and exits 1 if any source failed. KeyboardInterrupt,
  SystemExit (including SIGTERM), and cancellation propagate immediately.
  The runner does not write paid sync_state or freshness.

References reviewed: Supabase database function security and PostgREST transaction
semantics. No new secret access or production authorization is implied.

## Proposed PR file inventory

- `notes/m2-integration-reviewed-manifest.json`
- `notes/m2-safe-persistence-integration.md`
- `scripts/build_fact_lsa.sql`
- `scripts/normalization/brand_rules.py`
- `scripts/normalization/coverage.py`
- `scripts/normalization/daily.py`
- `scripts/normalization/fact_rows.py`
- `scripts/normalization/google.py`
- `scripts/normalization/lsa.py`
- `scripts/normalization/meta.py`
- `scripts/normalization/persistence.py`
- `scripts/reconcile_daily_aggregation.py`
- `scripts/reconcile_paid_facts.sql`
- `supabase/migrations/20261011011135_replace_paid_fact_window.sql`
- `supabase/migrations/20261011035452_fence_paid_source_runs.sql`
- `tests/fixtures/google-api-example.json`
- `tests/fixtures/lsa-api-example.json`
- `tests/fixtures/meta-api-cases.json`
- `tests/sql/test_paid_integration.mjs`
- `tests/sql/test_paid_persistence.mjs`
- `tests/test_coverage.py`
- `tests/test_daily_aggregation.py`
- `tests/test_fact_rows.py`
- `tests/test_google_normalization.py`
- `tests/test_lsa_normalization.py`
- `tests/test_meta_normalization.py`
- `tests/test_persistence.py`
- `worker/api_client.py`
- `worker/db.py`
- `worker/http.py`
- `worker/paid_sync.py`
- `worker/paid_transport.py`
- `worker/run.py`
- `worker/sources/__init__.py`
- `worker/sources/meta.py`
- `worker/sync.py`
- `worker/tests/paid_sql_bridge.py`
- `worker/tests/test_api_client.py`
- `worker/tests/test_paid_sync.py`
- `worker/tests/test_run.py`
