# Issue #31 reconciliation scripts and frozen-snapshot results

This PR extracts offline Calls/CRM reconciliation from the local #31 work. It adds no worker wiring, SQL migrations, production writes, dashboard changes, or dependencies. It does not complete the production integration requirements of #31.

## Reproduce (Python 3.10+)

```sh
python3 -m scripts.reconcile_calls --output notes/issue31-calls-reconciliation.json
python3 -m scripts.reconcile_crm --output notes/issue31-crm-reconciliation.json
python3 -m unittest discover -s tests -p 'test_*_normalization.py' -v
```

Inputs are the untouched `data/snapshot-2026-09-23/calls.csv` and `crm_jobs.csv`. Their headers are preserved in the result JSON. Every daily source/campaign bucket is compared with a separate raw CSV calculation; this is offline normalization reconciliation, not verification of deployed Supabase facts.

## Calls

Calls use Central business dates and preserve the observed source. Google campaign IDs use the schema's explicit brand mapping. Unknown source/campaign attribution is flagged, with no invented account or campaign name. Duplicate call IDs and repeated first-time caller hashes fail validation.

The agreed M2 rule is first_time_caller=true AND duration_sec>=30. The report also includes the zero-second rule for comparison; it must not replace the M2 rule. Returning callers remain calls, never new leads.

## CRM

The CRM report explicitly uses the **draft-2026-10-07 proposed dictionary** in `tests/fixtures/crm-source-map-proposed.json`. This is a review candidate, not an approved production mapping. In particular, `local services`, `maps`, `saw truck`, `truck`, `yard sign`, `customer`, and `plan` have proposed mappings that require team review. Do not adopt these ambiguous aliases automatically.

Jobs use their Central booking date (`created_at`), count completed jobs separately, and include revenue only for completed jobs. Decimal arithmetic preserves cents. Raw labels and unmapped counts remain visible; CRM jobs are not added to unique leads.

## Validation

Both full-history reconciliation scripts passed on this branch. The 55 focused normalization/reconciliation tests passed; the log is included. Results cover frozen history through 2026-09-22, not current live API data. No live API access or database writes were performed. `cd web && npm run build` and `npm run lint` also passed. Existing installed web dependencies were copied into this isolated checkout; no dependency was added.

## Integration dependencies

The current #31 lists #37 (Calls loader), #29 (CRM loader), and #30 (paid-source fact normalization). #36 is the shared paging/retry API client used by the loaders; it is an indirect live integration dependency. These offline CSV scripts do not import the client or worker. This PR references #31 without closing it; live raw-to-fact reconciliation and worker/database integration remain separate.
