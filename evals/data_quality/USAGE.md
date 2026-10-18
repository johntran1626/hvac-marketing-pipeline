# Standalone M3 data-quality evaluation — Issue #58

From the repository root, run:

```sh
python3 evals/data_quality/harness.py
python3 -m unittest discover -s evals/data_quality -p 'test_*.py' -v
```

Python 3.9+ and an installed IANA timezone database are required (standard on
macOS and GitHub's Ubuntu runners). No pip installation, environment variables,
secrets, network, database, or live services are used. Existing production code
is neither imported nor exercised. These same commands can be used in CI;
no deployment or scheduled production workflow is changed.

`--json` produces structured results. `--fixtures PATH` evaluates another suite
with the same fixture schema. Paths default relative to the harness file, so
execution does not depend on the current directory.

Exit codes: **0** means every expected finding matched; **1** means a missed or
unexpected finding; **2** means an invalid fixture/configuration. A deliberately
corrupted fixture should PASS when its expected anomalies are detected. PASS
is a test verdict, not a claim that the input data is clean.

Every result includes case, named check ID, pass/fail, expected and actual
finding keys, and evidence. Violations include row keys and expected/actual
field values. Expected keys are literal checked-in assertions, not generated
by the detector. `sample-output.txt` is the complete captured run, checked for
exact reproducibility by a regression test.

| ID | Check and contract |
| --- | --- |
| DQ01 | Latest revision per date/campaign/ad-group replaces prior conversions; stale, appended, missing, and orphan fact groups violate reconciliation. |
| DQ02 | A raw call ID occurs exactly once; repeated IDs are flagged, even if identical. |
| DQ03 | Count distinct caller hashes satisfying first-time AND duration >=30, within this fixture's evaluation window. Repeat calls do not inflate this count. |
| DQ04 | Calls/LSA use Central; Meta uses Pacific. Account date strings remain local dates. Covers midnight, winter, summer, and both DST transitions. |
| DQ05 | Per-call qualification is exactly first-time AND duration >=30; includes 29/30-second boundaries and returning callers. |
| DQ06 | Repeated IDs must agree on first-time status; multiple distinct first-time call IDs for one hash are flagged for review. A first-time call followed by a returning call is normal. |
| DQ07 | Missing/null spend is unknown; an explicit zero is valid. |
| DQ08 | Missing/null or nonpositive denominators cannot support a rate; flag rather than silently presenting zero CPL. This is an unavailable-rate signal, not necessarily a broken ingestion. |
| DQ09 | Attribution must have exactly one distinct (source, brand) candidate; zero or multiple candidates remain unresolved. No guess based on names. |
| DQ10 | Raw/fact call IDs, multiplicity, and duration agree; missing, orphan, and changed-value facts are flagged. |

## Fixtures and scope

`fixtures.json` contains one normal dataset and named corrupted cases. Each
case applies explicit path/value replacements to a deep copy of normal and
lists expected finding keys for **every** check. Empty arrays explicitly mean
no findings. The tests suppress each detector in turn to prove that an absent
detector cannot pass, and verify a CLI exit of 1 when a corruption is removed
but its expected finding remains.

These are synthetic contract fixtures, not production results or a replacement
ETL worker. The source field shapes/timezones follow `docs/API.md`. Identifiers
`CL1000001`, `5b519f28dc98`, `20814455901`, and `149302118801` come from the first
snapshot call/Google Ads records; values/durations/dates are deliberately edited
for tests. `fixture-*` identifiers are explicitly synthetic. Relevant snapshot
headers (read without modifying the files):

```text
calls.csv: call_id,started_at,duration_sec,tracking_number,source,campaign_id,caller_hash,first_time_caller
google_ads_insights.csv: date,customer_id,campaign_id,campaign_name,ad_group_id,ad_group_name,impressions,clicks,cost_micros,conversions
```

`revision`, `qualified`, `unique_callers`, `fact_date`, `candidates`, and metric
rows are harness-only observations, not assumed database columns. Revisions
are explicit fixture ordering, not API timestamps. Attribution candidates are
provided evidence; this harness does not implement a production mapping policy.
The unique count is scoped to the fixture window, not an invented global or
cross-channel deduplication policy. Raw/fact reconciliation covers the declared
call projection, not every production fact column.

Full fixture-schema validation, production adapters, hosted data verification,
and production integration are outside this standalone issue. No PR #50 code
or unmerged teammate changes are required.
