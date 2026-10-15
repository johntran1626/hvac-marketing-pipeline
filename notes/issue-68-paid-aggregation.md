# M3 Issue #68 — offline paid daily aggregation

All fixture records are synthetic and isolated from production. This is not a worker, database migration, or evidence of hosted completeness.

Run from the repository root:

```sh
python3 -m scripts.reconcile_daily_aggregation
python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m unittest discover -s worker/tests -t .
```

The standalone reconciliation pack `tests/fixtures/issue68-daily.json` documents 12 positive and should-flag cases. It checks exact micro-spend/lead addition, source/account/date separation, unknown brand buckets, stale/restated duplicated source rows, and negative metrics. It compares named expected buckets/errors to actual aggregation output, fails nonzero on any mismatch, and requires no live services.

This is intentionally distinct from #58's broad quality harness and #59's Calls/CRM evidence. #68 verifies paid-source daily aggregation contracts and refuses duplicate natural keys; a caller must provide current upserted records, not blindly sum multiple versions.

The `Contribution` structural interface accepts independently normalized Google/Meta/LSA contributions at runtime without importing unmerged source-specific modules. It does not validate source-specific fields itself: those remain the responsibility of #65–#67. The example inputs are local immutable fixture adapters and do not infer API or production correctness.

`fact_rows.py` is staging-only: a verified complete source/day snapshot, source-generation fencing and atomic persistence are required before production integration. `coverage.py` describes planning/attestation only; cursor/page counts alone do not prove completeness. Issue #69 covers persistence isolation, not this PR.
