"""Booked jobs, completed jobs and revenue by channel, from the CRM snapshot.

Same rules as the CRM block in rebuild_fact_marketing_daily():
- channel from lead_source, using tests/fixtures/crm-source-map-proposed.json
  (lower-cased, spaces trimmed); blank or unknown labels are 'unattributed'
- booked job = any status except canceled
- completed job = status completed; revenue counts completed jobs only
- date = Central date of created_at

Run from the repo root:  python scripts/check_crm_jobs_by_channel.py data/snapshot-2026-09-23
"""
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

D = sys.argv[1]
CT = ZoneInfo("America/Chicago")

with open("tests/fixtures/crm-source-map-proposed.json", encoding="utf-8") as f:
    MAP = {k.strip().lower(): v for k, v in json.load(f)["aliases"].items()}

totals = defaultdict(lambda: [0, 0, 0, Decimal(0)])  # channel -> all, booked, completed, revenue
with open(f"{D}/crm_jobs.csv", newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        ch = MAP.get(r["lead_source"].strip().lower(), "unattributed")
        t = totals[ch]
        t[0] += 1
        if r["status"] != "canceled":
            t[1] += 1
        if r["status"] == "completed":
            t[2] += 1
            t[3] += Decimal(r["revenue_usd"] or 0)

print(f"{'channel':<18}{'all jobs':>9}{'booked':>8}{'completed':>11}{'revenue':>15}")
for ch, (a, b, c, rev) in sorted(totals.items(), key=lambda kv: -kv[1][1]):
    print(f"{ch:<18}{a:>9,}{b:>8,}{c:>11,}{rev:>15,.2f}")
a, b, c, rev = (sum(t[i] for t in totals.values()) for i in range(4))
print(f"{'TOTAL':<18}{a:>9,}{b:>8,}{c:>11,}{rev:>15,.2f}")
