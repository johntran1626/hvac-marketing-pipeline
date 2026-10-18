# M3 Issue #69 — SQL safety research and rollout contract (offline only)

**No production migration, private RPC, worker switch, or deployment is included.** This PR deliberately does not extract the unverified production migrations or `PostgrestFactRpc` from draft PR #50. The old unfenced RPC must be treated as **unsafe/deprecated**, not a supported fallback.

## Disposable SQL transaction tests

Run `python3 -m unittest discover -s tests/sql -p 'test_*.py' -v`. Six local SQLite transaction experiments validate expected fencing behavior for a stale source generation, cancellation, rollback after injected failure, scope isolation, duplicate/stale input rejection, and two simultaneous connections contending for a writer lock. The test harness is a **behavioral research model**, not a faithful PostgreSQL/PostgREST implementation or proof of hosted correctness. Nothing writes outside a disposable temp directory.

## Required production contract (not implemented or verified)

1. Receive a provider-issued **immutable snapshot/revision identity** before starting pagination. Request every page against that same identity; verify revision-bound cursors, full source/account manifest and final terminal page. A page count, terminal cursor, count, or hash of a partial export cannot prove missing accounts or omitted records are absent.
2. Acquire a durable, monotonically increasing generation for a source **before** acquiring a snapshot. Lock and verify the same active generation during every stage, raw/fact transaction, failure transition and success/watermark update. A cancelled or superseded run must fail closed.
3. Stage a complete, attested source/account/date window; validate expected raw-vs-fact totals, precision, account coverage, and duplicate natural keys. Perform atomically scoped replacement of raw and fact slices in one committed transaction. No page-by-page or incomplete raw upsert may advance a freshness watermark.
4. Retries of an identical staged revision must be idempotent; conflicting payloads with the same revision must fail; rollback on any validation or write failure must retain the prior successful facts and watermark.
5. Restrict persistence to appropriate service roles through reviewed private-schema grants. Never expose the unsafe public unfenced RPC or invoke it via a PostgREST default-public fallback.

## Unverified blockers for production activation

- PostgreSQL/Supabase advisory locks, overlapping connections, isolation levels, and true hosted concurrency **not tested** here; SQLite locking differs materially.
- PostgREST private-schema exposure, grants, RLS and authenticated/anonymous denial **not tested**.
- External provider guarantee of immutable revision-bound, all-account snapshots **not established**.
- Source-side cancellations, refunds, late restatements and partial fetch behavior must be exercised against real provider contracts before rollout.

Separate explicit review and approval are required for any production migration, worker connection, or hosted verification. All existing production configuration stays untouched.

## Relationship to draft PR #50

Original `tests/sql/test_paid_integration.mjs` and `tests/sql/test_paid_persistence.mjs` require external PGlite and unverified migrations; they are *not* claimed passing and have not been copied into this deliverable. Their failure-mode inventory informed these independently runnable transactional safety checks. This issue delivers testable research and rollout conditions only.
