# Issue #67: standalone LSA normalization

Refs #67. Extracted `scripts/normalization/lsa.py`,
`tests/test_lsa_normalization.py`, and the unchanged documented API fixture
`tests/fixtures/lsa-api-example.json` from draft PR #50 at
`e0652b8484e73687c047e51e937107ff0399aa50`.
Base: John's main at `4aeac51b6c00adaabbc0aee387848b4cd1a3c226`.
Branch: `issue-67-m3-lsa-normalization`.

This is a pure standard-library transformation and offline tests. It imports no
other normalization modules, workers, persistence code, or unmerged branches.
No migrations, worker switches, deployment changes, or dependencies were added.

## Contract and differences from #50

Sources: `docs/API.md` (LSA fields, date filters, late credits),
`data/snapshot-2026-09-23/README.md` (billing meanings),
`schema/normalized-fact-table.md` (original creation date, reported lead count,
net spend, source namespace). Existing SQL is reference only and is unchanged.

| Status | Net spend | charged_leads | refunded_leads | not_charged_leads | unknown_status_leads |
| --- | --- | --- | --- | --- | --- |
| CHARGED | exact source cost | 1 | 0 | 0 | 0 |
| CREDITED | 0 | 0 | 1 | 0 | 0 |
| REFUNDED | 0 | 0 | 1 | 0 | 0 |
| NOT_CHARGED | 0 | 0 | 0 | 1 | 0 |
| Other nonblank string | None (unknown) | 0 | 0 | 0 | 1 |

Every valid row contributes one `reported_leads`, independently of its billing
state. `refunded_leads` combines CREDITED and REFUNDED; exact `charge_status`
remains available to distinguish them. CREDITED is the documented API refund
status. Literal REFUNDED is an explicit compatibility extension for this issue,
covered synthetically, not evidence of an observed API status.
Unknown status strings are preserved exactly (including case) instead of rejected
as in #50. They must be flagged for review; consumers must not coalesce unknown
spend to zero or write it to a nonnullable fact spend column.

Credits/refunds require a valid offset-aware `credited_at` at or after creation;
equal instants with different offsets are allowed. CHARGED and NOT_CHARGED require
null `credited_at`. Unknown states may retain null or a valid credit timestamp,
but that timestamp never infers a known billing state. Missing nullable fields,
naive/invalid timestamps, preceding credits, malformed identifiers, invalid lead
types, and nonfinite/negative/non-numeric costs raise field-specific errors.

The Central calendar date of `lead_created_at` determines `analysis_date`, using
`America/Chicago` timezone rules including DST. Credit dates never move the lead
or create another lead. Both source timestamp strings remain unchanged in the
output and input, including UTC spelling and precision. Offset-aware equivalents
are accepted without rewriting them. No wall clock is consulted; the documented
30-day refresh horizon is not a validity cutoff for older credits.

Source cost is retained even after a refund. Load JSON with
`json.loads(payload, parse_float=Decimal)` and CSV money with `Decimal(text)`;
no rounding/quantization is performed. Existing float callers are accepted via
`Decimal(str(value))`, but precision already lost before this function cannot be
recovered. Tests include a long decimal under a deliberately low decimal context.

The API example has no account/campaign identifiers, so those remain null.
Optional adapter metadata `source_account_id` or `account_id` is preserved as an
exact nonblank string (including leading zeros); conflicting values fail.
`source_key` is `(source_platform, source_account_id, lead_id)` for multi-account
consumers; `raw_key` retains #50's lead ID behavior. No campaign is inferred.

Normalize only the current version of each source/account/lead, replacing its old
contribution. This row transformer does not deduplicate histories or aggregate
rows. It adds no call-tracking unique leads or CRM metrics.

## Reproduce offline checks

Run from the repository root with Python 3.10+ and system IANA timezone data
(`America/Chicago`). No API keys, database, network, or pip install is required:

```sh
python3 -m unittest discover -s tests -p test_lsa_normalization.py -v
python3 -m unittest discover -s tests
python3 -m unittest discover -s worker/tests -t .
git diff --check
```

Observed on 2026-10-14 with Python 3.14.8:

```text
LSA:            Ran 24 tests ... OK
Normalization:  Ran 79 tests ... OK
Worker:         Ran 27 tests ... OK
git diff --check: exit 0
```

The LSA suite includes 36 named JSON cases with literal expected dates, spend,
billing counters, or error fields. It checks repeatability and input immutability.
Cases include charged, credited, refunded, never charged, unknown, malformed
values, equal-instant credits, late credits, winter/summer midnight, spring DST
skip, repeated fall hour, and a year boundary. Additional tests cover exact money,
account-qualified identity, required fields, and the entire frozen CSV.

Snapshot header, read before use:

```text
lead_id,lead_created_at,category,lead_type,charge_status,credited_at,cost_usd
```

The fixture reconciliation asserts literal totals independently computed from
that file as well as comparing against source rows:

```text
rows/reported leads: 1701
CHARGED:             1275
CREDITED:             222
NOT_CHARGED:          204
unknown:             0
Central days:        625
net spend USD:       50518.51
```

These are frozen-file totals, not live API totals. The example totals in the
existing SQL comments differ from this file; they are not used as test oracles.

Repository-required build, using the existing lockfile only:

```sh
cd web
npm ci --ignore-scripts --no-audit --no-fund
npm run build
```

Result: exit 0; compiled successfully; TypeScript passed; 6/6 static pages
generated. No credentials supplied. npm reported an existing ESLint deprecation
warning during dependency installation. No lockfile changes.

## Remaining review/integration risks

This verifies offline semantics, not hosted ingestion, reconciliation, or
production persistence. Future consumers must explicitly handle unknown spend,
account-qualified keys, and replacement of old billing states. The REFUNDED
compatibility spelling and optional account metadata are synthetic extensions;
the current documented API uses CREDITED and provides no account field. The
new counters are contribution fields only, not database schema changes.

Codex prepared the extraction and focused acceptance changes. Human review is
pending; the PR remains draft. Nothing was merged or deployed.
