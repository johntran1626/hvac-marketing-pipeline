# Anomaly alert (#62)

**What it catches:** a paid channel (Google Ads, Google Guaranteed, Meta) keeps spending money while its platform reports zero leads. That usually means broken tracking (a lead form, pixel or conversion setup), and Diane pays for days she can't see.

**Rule** (`worker/alerts.py`, on `fact_marketing_daily` summed by channel and day):

1. 3 or more days in a row with spend > 0 and reported leads = 0.
2. The channel's previous 28 days set its normal leads per day. The streak fires only if that rate says it should have brought **7 or more leads** in the streak. Zero leads when 7 are expected is less than a 1 in 1,000 chance, so quiet winter days on a low-volume channel don't fire.

**When it runs:** after every sync in the `worker-sync` workflow (daily at 7:47pm CT, and by hand). It checks streaks that ended in the last 14 days. To replay history, run the workflow by hand with `alert_since` set, e.g. `2024-10-01`.

**What it does when it fires:**

- a warning on the Actions run page and a table in the run summary
- one GitHub issue per anomaly, keyed by channel and start date (`<!-- anomaly:meta:2026-08-04 -->` in the body), so reruns and a streak that keeps growing never open a second issue
- totals only: no keys, no caller or customer data

## Real anomalies it found

Run on all history, Oct 2024 to Oct 2026, every paid channel. It fires twice, both Meta:

| Channel | Days | Spend | Reported leads | Expected leads |
|---|---|---|---|---|
| Meta | 2026-08-04 to 2026-08-10 (7) | $291.15 | 0 | 16.2 |
| Meta | 2026-10-04 to 2026-10-08 (5) | $234.94 | 0 | 11.2 |

The August streak is the week Diane wrote about in her letter (README.md: "For a whole week in August (Aug 4 to Aug 10) it showed zero leads while we still paid $291.15."). The October streak came in through the live API after the snapshot.

For comparison, a flat "3 zero days in a row" rule would also fire on 6 quiet stretches (Dec 2024, Jan 2025, May 2025, Nov 2025, Jan 2026), where Meta normally gets 1 to 2 leads a day. Google Ads never has more than 2 zero days in a row. Google Guaranteed never has a zero-lead day with spend, because it only charges per lead.

## Run it

```sh
python3 -m worker.alerts                      # recent anomalies (last 14 days)
python3 -m worker.alerts --since 2024-10-01   # replay all history
python3 -m unittest worker.tests.test_alerts -v
```

Locally it reads `SUPABASE_URL` and `SUPABASE_SECRET_KEY` from `.env.local`. `--notify` (opening issues) only works in Actions, which sets `GITHUB_TOKEN`.

## Limits

- Platform numbers for the last 7 days can still change (docs/API.md), so a fresh streak can fill in later. The issue says so.
- It watches reported leads, not calls. A channel whose calls drop while its platform still reports leads is not caught.
- A low-volume channel needs a longer streak to fire: at 1 lead a day, 7 zero days in a row.
