# Issue #59 — independent reconciliation evidence

Base: John's `main` at `4aeac51b6c00adaabbc0aee387848b4cd1a3c226`.
This standalone pack uses only merged #31 normalization and local fixed inputs.
No dependency on #58, PR #50, unmerged code, credentials, or #65.

## Reproduce

From the repository root, Python 3.10+ with America/Chicago system timezone data:

```sh
python3 -m scripts.reconcile_fixture_pack --output notes/issue59/fixture-evidence.json
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s worker/tests -t .
python3 -m scripts.reconcile_calls --output notes/issue59/snapshot-calls.json
python3 -m scripts.reconcile_crm --output notes/issue59/snapshot-crm.json
```

No pip packages, environment variables, database, or API calls are needed. The pack
returns 0 only if normal reconciliation and every exact expected anomaly match;
an unexpected mismatch or missed anomaly returns 1. JSON has no timestamps and is
byte reproducible. Tests verify it against the checked-in evidence. Test logs may
have different runtimes. Output paths must have an existing parent directory.

## Inputs and independent expectations

`tests/fixtures/issue59/source-and-expected.json` is explicitly **SYNTHETIC**.
The fixed expected buckets were authored separately from the normalizer; they are
never regenerated from actual output. The report contains both complete expected
and actual fact-shaped buckets, a SHA-256 input fingerprint, and exact differences
for each corruption. Source identifiers are synthetic and are not person links.
The fixture uses a minimal, explicitly versioned test-only source dictionary:
`Google Ads` → `google_ads`, `Google` → `unattributed`. It is not production policy.

Coverage and expected results (asserted by tests):

- Nine calls, seven distinct caller hashes, six qualified distinct first-time
  callers. A 29-second first call fails, exactly 30 seconds qualifies, and later
  90-second returning calls do not add or upgrade leads. Distinct counts are
  source-only; conflicting first-time flags are rejected across the full input.
- Central local midnight is tested at 04:59:59/05:00:00 UTC in summer and
  05:59:59/06:00:00 UTC in winter. UTC date is not the analysis date.
- Nine CRM booked jobs means all current jobs in the created-at booking cohort,
  including scheduled, canceled, completed, estimate_sold and estimate_lost.
  Four jobs are completed. Updated-at is days later and never selects the bucket.
- Known gross completed revenue is $123.40. One completed job lacks revenue, so
  its bucket's full gross revenue is **unknown (null)**, not $3.05 or zero.
  Gross revenue does not subtract ad spend, costs, or calculate profit.
- Unknown call sources, missing Google campaign, ambiguous CRM `Google`, an
  unknown CRM label, and missing CRM attribution remain unresolved. Accounts
  remain null; no cross-account inference or person-level Calls/CRM joins occur.

Fourteen scenarios include normal reconciliation; deliberately inflated lead
counts, dropped booking, false completion, understated gross revenue, hidden
unresolved attribution, zero-filled unknown revenue, shifted date bucket, forced
paid attribution, invented account, duplicate call/job IDs, and conflicting
first-time flags. Each is labeled SYNTHETIC. Missing/extra buckets are reported
with full expected/actual metrics; metric mismatches name the precise field.
Expected duplicate/conflict rejection is a passing anomaly test, not a clean
source reconciliation result.

## Frozen snapshot evidence

The two unchanged merged #31 scripts were rerun against the repository snapshot.
CSV headers read before use:

```text
call_id,started_at,duration_sec,tracking_number,source,campaign_id,caller_hash,first_time_caller
job_id,customer_id,created_at,updated_at,lead_source,job_type,status,revenue_usd,zip
```

`snapshot-calls.json` and `snapshot-crm.json` capture their results. The Calls
report includes threshold 0 only as a comparison; this pack uses the M2 rule of
first-time AND >=30 seconds. The snapshot CRM report uses the existing **proposed**
`draft-2026-10-07` dictionary, not an accepted production rule.

No independently verified historical discrepancy is claimed. Passing frozen
snapshot checks do not establish correctness of live data or deployed facts.
These are local fact-shaped normalization outputs, not database extracts or a
validation of persistence, ingestion completeness, or the dashboard. Inputs must
represent a complete current source slice for cross-history distinct validation.
No production writes, deployment changes, or schema changes are included.

## Validation results

See `tests.txt`, `worker-tests.txt`, and `web-checks.txt`. The fixture suite adds
eight tests; the combined normalization/fixture run passes 63 tests. Reconciliation
JSON is checked in for independent review. The web build is a repository-required
check and is separate from the dependency-free Python validation pack.

Worker tests: 27 passed. Web lint passed. `npm run build` was attempted twice
(including an approved retry outside the sandbox), but Turbopack failed when its
CSS build process tried to bind a port (`Operation not permitted`). This is a
build-environment limitation; the default build is not claimed to pass. A separate
`npm run build -- --webpack` check passed and is captured in `web-webpack-build.txt`. Web logs have ANSI color
and trailing whitespace removed for review.
`npm ci` installed only locked existing dependencies and reported five high
severity audit findings; no dependency changes or automatic fixes were made.

Web check commands (require existing npm dependencies or `npm ci`):

```sh
cd web
npm run build
npm run lint
npm run build -- --webpack
```
