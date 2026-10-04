# Memo verification (Issues #2 and #4)

Independent check of `memo/read.md` and the M1 evidence behind it, done by Ruslan on 2026-10-03.
Memo version checked: `main` after PR #23 (John's edits for the free Google listing and Brand cost).

## How to reproduce

From the repo root:

```
python3 scripts/check_diane_claims.py
python3 scripts/check_m1_memo.py
python3 scripts/check_heating_by_month.py
```

On Windows use `python` and run `python -m pip install tzdata` once (Windows has no built-in time zone data).
I ran all three on Windows, Python 3.14.

## Memo numbers

Every number in `memo/read.md`, checked against the `check_m1_memo.py` output (section numbers in brackets).

| Memo says | Script output | Match |
|---|---|---|
| Real leads, latest 30 days: Google Ads 100, LSA 68, Meta 6 | 100 / 68 / 6 [11] | yes |
| Cost per real lead: $89.54, $45.22, $227.28 | $89.54 / $45.22 / $227.28 [12] | yes |
| Free Google Business Profile: 126 real leads | gbp: 126 [11] | yes |
| Brand $8.44 per reported conversion is $72.59 per real lead | $8.44 / $72.59 [16] | yes |
| Heating Repair spent $369.32 with zero real leads | $369.32, real_leads=0 [13] | yes |
| Kept Meta ad sets: $8.08 reported CPL | $8.08 [14] | yes |
| Blended cost per real lead $76.97 → about $63.56 | $76.97 → $63.56 [12, 15] | yes |
| Budget split $4,000 + $3,000 + $2,600 + $1,400 + $400 | adds to $11,400 | yes |
| Winter 7.03 vs summer 15.09 completed jobs/day | 7.03 / 15.09 [10] | yes |
| Meta: 4 tracked calls during Aug 4–10 | 4 [3] | yes |
| Katy cancellations: 77 (2026), 78 (2025), 26 (late 2024) | 77 / 78 / 26 [5] | yes |

The $11,400 monthly budget comes from Diane's note in `README.md`.

## Memo format

- Path is `memo/read.md` on `main`.
- Word count: 390 by PowerShell `Measure-Object -Word`, 384 by `wc -w`. The tools count symbols like `·` differently. Both are under 400.
- The four headings are Diane's questions word for word, in her order, each with a number in front ("1." to "4.").
- Question 4 names a metric (blended paid cost per real lead), a threshold (below $76.97) and a time (after the first 30 full days of the new mix).

## Data map numbers (`notes/data-map.md`)

Checked against `check_diane_claims.py`: Google 1,208.6 conversions, $29,004.33, $24.00 each; Brand $8.44; campaign `20814455917` under two names; Katy 26 / 78 / 77 canceled (181 total); LSA 222 credited and 204 not charged; 29,757 calls and 13,580 unique callers; 3,608 calls under 30 seconds. All match.

## Database and live site

- `raw_lsa_leads` (team Supabase, `scripts/lsa_backfill_evidence.sql`): 1,724 rows, 1,724 distinct `lead_id`, Central days 2024-10-01 to 2026-10-01.
- `fact_marketing_daily` (check query in `scripts/build_fact_lsa.sql`): 633 days, 1,724 LSA leads, $51,302.98 charged spend.
- Table Editor shows all 5 raw tables and `fact_marketing_daily`. A `pg_constraint` query shows 0 check constraints left on the raw tables.
- https://lab-b-hvac-pipeline.vercel.app/health in a private window: `{"ok":true,"status":"ok","message":"Read one row from the configured HVAC table."}`

Screenshots are in my reviews on PR #19, #21 and #22.

## One finding: Heating Repair

The memo pauses Heating Repair because it had zero real leads from Aug 24 to Sep 22. That window is off-season for heating, so zero is expected. Claude pointed this out during the review, and I checked it month by month with `scripts/check_heating_by_month.py`:

- Dec–Jan, both winters: 5 to 10 real leads a month.
- Jun–Sep 2026: 0 every month.
- Best month ever: Jan 2025 at $163.42 per real lead. That is more than LSA ($45.22) and every other Google campaign ($61.81 to $101.48) in the latest 30 days.

So the pause still holds up, but the reason is cost, not zero leads. Not a blocker for M1. Worth rechecking in November, when real cold-weather data comes in.

## Reviews

- PR #13: https://github.com/johntran1626/lab-b-hvac-pipeline/pull/13#pullrequestreview-5402691624
- PR #19: https://github.com/johntran1626/lab-b-hvac-pipeline/pull/19#pullrequestreview-5402602314
- PR #20: https://github.com/johntran1626/lab-b-hvac-pipeline/pull/20#pullrequestreview-5402762254
- PR #21: https://github.com/johntran1626/lab-b-hvac-pipeline/pull/21#issuecomment-5972556718
- PR #22: https://github.com/johntran1626/lab-b-hvac-pipeline/pull/22#pullrequestreview-5402447845
