"""Heating Repair, month by month: spend and real leads (Issue #4, memo review on PR #20).

The memo pauses Heating Repair based on Aug 24 - Sep 22, which is off-season for heating.
This shows how it does across both winters in the snapshot.

Real lead = same definition as scripts/check_m1_memo.py: a unique first-time caller
(caller_hash) on a call of at least 30 seconds, dated in Central time.

Run from the repo root:  python3 scripts/check_heating_by_month.py
Standard library only. Reads data/snapshot-2026-09-23/ and never edits it.
"""
import csv
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

SNAP = "data/snapshot-2026-09-23/"
HEATING_REPAIR = "20814455930"  # campaign_id for "Heating Repair - Houston"
CENTRAL = ZoneInfo("America/Chicago")

spend = defaultdict(float)
with open(SNAP + "google_ads_insights.csv", newline="") as f:
    for r in csv.DictReader(f):
        if r["campaign_id"] == HEATING_REPAIR:
            spend[r["date"][:7]] += int(r["cost_micros"]) / 1_000_000

real_leads = defaultdict(set)
with open(SNAP + "calls.csv", newline="") as f:
    for r in csv.DictReader(f):
        if r["source"] != "google_ads" or r["campaign_id"] != HEATING_REPAIR:
            continue
        if r["first_time_caller"].lower() != "true" or int(r["duration_sec"]) < 30:
            continue
        started = datetime.fromisoformat(r["started_at"].replace("Z", "+00:00"))
        real_leads[started.astimezone(CENTRAL).strftime("%Y-%m")].add(r["caller_hash"])

print("Heating Repair - Houston (campaign_id 20814455930), by Central month")
for month in sorted(set(spend) | set(real_leads)):
    n = len(real_leads[month])
    cpl = f"${spend[month] / n:,.2f}" if n else "n/a"
    print(f"  {month}: spend=${spend[month]:,.2f} real_leads={n} cost/real_lead={cpl}")
