# Issue #66: offline Meta normalization evidence

Refs #66. Extracted from draft PR #50 at `e0652b8484e73687c047e51e937107ff0399aa50` onto John's main at `4aeac51b6c00adaabbc0aee387848b4cd1a3c226`.

Only `scripts/normalization/meta.py`, `tests/test_meta_normalization.py`, and `tests/fixtures/meta-api-cases.json` were ported. This note is new. The module uses `brand_rules.py` already merged on main; no other M3 branch or unmerged dependency is needed. No worker, schema, persistence, deployment, or production database changes/access.

## Contract and adjustments to PR #50

- `docs/API.md` defines date_start/date_stop as the same Pacific account day. `schema/normalized-fact-table.md` requires preserving that date: no UTC/Central rebucketing of daily aggregates. Fixtures pin summer/winter UTC midnight boundaries and the spring/fall DST days (23/25 hours). UTC bounds explain the source bucket; the normalizer accepts date-only aggregates, not timestamps.
- Preserve account, campaign, ad-set IDs and names. The natural key includes date/account/campaign/ad-set; source_platform remains `meta_ads`. No aggregation or cross-source join is performed.
- Only exact `action_type="lead"` is reported leads. Empty/no-lead arrays yield zero; missing actions or malformed lead values fail. Unlike PR #50, repeated lead entries now fail instead of being summed: the documented API does not establish disjointness. Additional fields on lead actions also fail because attribution-window breakdowns have no defined interpretation here. Non-lead values are not interpreted.
- Platform-reported leads are not qualified tracked callers. Output has no `unique_leads` or caller count. The schema's qualified-caller rule (first-time and duration >=30 seconds) belongs to Calls, not Meta actions. Zero reported leads cannot establish zero callers.
- Monetary and fractional lead strings become exact `Decimal` values, unaffected by caller precision. No float conversion or rounding. Nonnegative plain decimal strings are accepted, including subcent precision; downstream database scale/range validation is outside this offline contribution API.
- Reject missing required fields, noncanonical/invalid dates, multi-day ranges, invalid/nonfinite/negative numbers, integer overflow, blank names, and whitespace-bearing identifiers/action types. Errors identify the field without including the payload. Unknown campaign IDs explicitly return `brand_classification=None` for review rather than guessing from names.
- Inputs remain unchanged and output is immutable. Restatements normalize separately with the same key; choosing the current record and avoiding duplicate pages is the caller's responsibility.

## Reproducible before/after

Run from the repository root (Python 3.10+ with system IANA time-zone data):

```sh
python3 - <<'PY'
import json
from dataclasses import asdict
from pathlib import Path
from scripts.normalization.meta import normalize_meta_row
case = json.loads(Path('tests/fixtures/meta-api-cases.json').read_text())['cases'][0]
row = case['responses'][0]['data'][0]
print(json.dumps(row, sort_keys=True))
print(json.dumps(asdict(normalize_meta_row(row)), default=str, sort_keys=True))
PY
```

The illustrative API sample has spend `"41.65"`, lead value `"3"`, and date `2026-09-20`. Output has exact Decimal spend/reporting leads (serialized as strings), unchanged date/account/campaign/ad-set, `source_platform="meta_ads"`, `channel="meta"`, and unknown brand classification. Full expected outputs are committed in the fixture and checked independently of the implementation. The fixture labels its illustrative/synthetic provenance; it is not live API evidence.

Snapshot reconciliation reads the unchanged `data/snapshot-2026-09-23/meta_insights.csv` header:

```text
date_start,date_stop,account_id,campaign_id,campaign_name,adset_id,adset_name,impressions,clicks,spend,leads
```

Only the test adapts flattened CSV leads to an API actions array. It verifies distinct natural keys, impressions, clicks, exact total spend, reported leads, and known-ID classification against every frozen row. This is snapshot evidence, not a claim about current hosted totals.

## Validation

```text
python3 -m unittest discover -s tests -p 'test_meta_normalization.py' -v
Ran 28 tests — OK

python3 -m unittest discover -s tests -v
Ran 83 tests — OK (includes the 28 Meta tests)

python3 -m unittest discover -s worker/tests -t . -v
Ran 27 tests — OK (mocked API/database only)
```

110 distinct Python tests passed. The 13 positive fixture scenarios have complete expected outputs; 11 negative fixture scenarios supplement parameterized missing/type/range tests. No new dependency is added. `npm ci --ignore-scripts` installed the existing web lockfile and reported 5 high-severity vulnerabilities; dependency remediation is outside this extraction.

Build verification (database/API credential variables unset, no local env file):

- `npm run build`: failed in Turbopack CSS processing because local port binding was denied (`Operation not permitted`); retry with execution permission had the same result.
- `npm run build -- --webpack`: passed compilation, TypeScript, and static generation. No build/deployment configuration was changed.
- `git diff --cached --check`: passed.

## Remaining limits

No live ingestion, hosted reconciliation, database range/scale enforcement, persistence, freshness, completeness, or dashboard integration is claimed. Unknown campaigns require a reviewed classification before loading into a non-null fact field. A future API shape with multiple/broken-down lead entries requires an explicit contract change. Human review and independent rerun remain outstanding; this PR remains draft.
