"""Anomaly alert (#62): a paid channel keeps spending but its platform reports zero leads.

Rule, per paid channel (Google Ads, Google Guaranteed, Meta), on fact_marketing_daily:
  1. A streak is MIN_DAYS or more days in a row with spend > 0 and reported leads = 0.
  2. The channel's previous BASELINE_DAYS days set its normal leads per day. The streak fires
     only if that rate says it should have brought MIN_EXPECTED or more leads in the streak.
     With zero leads that is less than a 1 in 1,000 chance (Poisson), so quiet winter days
     on a low-volume channel don't fire.
Only streaks that end within RECENT_DAYS of the newest data are alerted, unless --since says
otherwise (to replay history). Each alert opens one GitHub issue, keyed by channel and start
date, so a rerun or a streak that keeps growing never opens a second one.

From the repo root:
  python3 -m worker.alerts                         # print recent anomalies
  python3 -m worker.alerts --since 2024-10-01      # replay all history
  python3 -m worker.alerts --notify                # also open GitHub issues (needs GITHUB_TOKEN)
"""
import argparse
import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from worker.config import load_env
from worker.db import Db
from worker.http import send

PAID = ("google_ads", "google_lsa", "meta")
LABELS = {"google_ads": "Google Ads", "google_lsa": "Google Guaranteed", "meta": "Meta"}
MIN_DAYS = 3
BASELINE_DAYS = 28
MIN_EXPECTED = 7  # P(0 leads | 7 expected) = e^-7, about 0.0009
RECENT_DAYS = 14
PAGE = 1000  # PostgREST returns at most 1,000 rows per request


@dataclass
class Anomaly:
    channel: str
    start: date
    end: date
    spend: float
    expected: float  # leads the baseline says the streak should have brought

    @property
    def days(self):
        return (self.end - self.start).days + 1

    @property
    def key(self):
        return f"anomaly:{self.channel}:{self.start}"

    def title(self):
        return (f"Anomaly: {LABELS[self.channel]} reported 0 leads for {self.days} days "
                f"({self.start} to {self.end}) while spending ${self.spend:,.2f}")


def daily(rows):
    """Sum fact rows to {channel: {day: (spend, reported_leads)}} for the paid channels."""
    out = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))
    for r in rows:
        if r["channel"] in PAID:
            t = out[r["channel"]][date.fromisoformat(r["analysis_date"])]
            t[0] += float(r["spend_usd"])
            t[1] += float(r["reported_leads"])
    return out


def find(by_day, min_days=MIN_DAYS, baseline_days=BASELINE_DAYS, min_expected=MIN_EXPECTED):
    """Every streak in by_day ({day: (spend, leads)}) that breaks the rule, oldest first."""
    found, streak = [], []
    for day in sorted(by_day) + [None]:  # None closes the last streak
        spend, leads = by_day[day] if day else (0, 1)
        if spend > 0 and leads == 0 and (not streak or day == streak[-1] + timedelta(days=1)):
            streak.append(day)
            continue
        if len(streak) >= min_days:
            start = streak[0]
            rate = sum(by_day[start - timedelta(days=i)][1] if start - timedelta(days=i) in by_day else 0
                       for i in range(1, baseline_days + 1)) / baseline_days
            expected = rate * len(streak)
            if expected >= min_expected:
                found.append((start, streak[-1], sum(by_day[d][0] for d in streak), expected))
        streak = [day] if day and spend > 0 and leads == 0 else []
    return found


def anomalies(rows, since=None):
    days = daily(rows)
    newest = max((d for ch in days.values() for d in ch), default=None)
    if newest is None:
        return []
    since = since or newest - timedelta(days=RECENT_DAYS)
    out = []
    for channel in PAID:
        for start, end, spend, expected in find(days.get(channel, {})):
            if end >= since:
                out.append(Anomaly(channel, start, end, spend, expected))
    return out


def load(db):
    rows = []
    for offset in range(0, 10**6, PAGE):
        page = db.select("fact_marketing_daily", select="analysis_date,channel,spend_usd,reported_leads",
                         channel=f"in.({','.join(PAID)})",
                         order="analysis_date,channel,source_platform,source_account_id,campaign_id,brand_classification",
                         offset=offset, limit=PAGE)
        rows += page
        if len(page) < PAGE:
            return rows


def body(a):
    # Totals only: no keys, no caller or customer data.
    return "\n".join([
        f"{LABELS[a.channel]} spent **${a.spend:,.2f}** over **{a.days} days** ({a.start} to {a.end}) "
        f"and its platform reported **0 leads**.",
        "",
        f"Based on the previous {BASELINE_DAYS} days it should have reported about **{a.expected:.1f} leads** "
        f"in that stretch. Zero is less than a 1 in 1,000 chance, so check the tracking "
        f"(lead form, pixel, conversion setup) before paying for more days like this.",
        "",
        "Source: `fact_marketing_daily`, summed by day. Rule: `worker/alerts.py`.",
        "Days in the last 7 can still change when the platform restates them (docs/API.md).",
        "",
        f"<!-- {a.key} -->",
    ])


def notify(found, repo, token):
    """Open one issue per anomaly. Skips anomalies that already have an issue, open or closed."""
    api = f"https://api.github.com/repos/{repo}/issues"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
               "Content-Type": "application/json", "User-Agent": "worker-alerts"}
    seen = set()
    for page in range(1, 50):
        issues, _ = send(f"{api}?state=all&per_page=100&page={page}", headers)
        seen |= {i.get("body") or "" for i in issues}
        if len(issues) < 100:
            break
    opened = []
    for a in found:
        if any(a.key in b for b in seen):
            print(f"[alert] already reported: {a.key}")
            continue
        issue, _ = send(api, headers, body={"title": a.title(), "body": body(a)}, method="POST")
        print(f"[alert] opened issue #{issue['number']}: {a.key}")
        opened.append(issue["number"])
    return opened


def summary(found, since):
    lines = ["## Anomaly alert", ""]
    if not found:
        return "\n".join(lines + [f"No anomalies in streaks ending on or after {since or 'the last 14 days'}."])
    lines += ["| Channel | Days | Spend | Reported leads | Expected leads |", "|---|---|---|---|---|"]
    lines += [f"| {LABELS[a.channel]} | {a.start} to {a.end} ({a.days}) | ${a.spend:,.2f} | 0 | {a.expected:.1f} |"
              for a in found]
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--since", type=date.fromisoformat, help="alert streaks ending on or after this day")
    p.add_argument("--notify", action="store_true", help="open a GitHub issue per new anomaly")
    args = p.parse_args(argv)

    env = load_env(required=("SUPABASE_URL", "SUPABASE_SECRET_KEY"))
    found = anomalies(load(Db(env["SUPABASE_URL"], env["SUPABASE_SECRET_KEY"])), args.since)
    for a in found:
        # ::warning shows as an annotation on the Actions run page
        print(f"::warning title=Anomaly alert::{a.title()}")
    if not found:
        print("[alert] no anomalies")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(summary(found, args.since) + "\n")
    if args.notify and found:
        token, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
        if not (token and repo):
            raise SystemExit("--notify needs GITHUB_TOKEN and GITHUB_REPOSITORY (set by GitHub Actions)")
        notify(found, repo, token)


if __name__ == "__main__":
    main()
