"""Check PR #52's dashboard against the snapshot CSVs.

Recomputes spend, unique leads and cost per lead with the rules in
rebuild_fact_marketing_daily(), then compares them to the live dashboard
(numbers typed in from the 7:41pm CT screenshot). Standard library only.

Run from the repo root:  python scripts/check_dashboard_vs_snapshot.py data/snapshot-2026-09-23
"""
import csv
import sys
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

D = sys.argv[1]
CT = ZoneInfo("America/Chicago")
BRAND = "20814455901"
CHANNELS = ("google_ads", "google_lsa", "meta")


def rows(name):
    with open(f"{D}/{name}", newline="", encoding="utf-8") as f:
        yield from csv.DictReader(f)


def ct_month(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(CT).strftime("%Y-%m")


spend = defaultdict(Decimal)   # (month, channel) -> spend
uniq = defaultdict(int)        # (month, channel) -> unique leads
brand = [Decimal(0), Decimal(0), 0]  # summer 2026 brand: spend, conversions, unique

for r in rows("google_ads_insights.csv"):
    s = Decimal(r["cost_micros"]) / 1000000
    spend[(r["date"][:7], "google_ads")] += s
    if r["campaign_id"] == BRAND and "2026-06-01" <= r["date"] <= "2026-08-31":
        brand[0] += s
        brand[1] += Decimal(r["conversions"])
for r in rows("meta_insights.csv"):
    spend[(r["date_start"][:7], "meta")] += Decimal(r["spend"])  # Meta account day, not shifted
for r in rows("lsa_leads.csv"):
    if r["charge_status"] == "CHARGED":  # credited / not charged cost $0
        spend[(ct_month(r["lead_created_at"]), "google_lsa")] += Decimal(r["cost_usd"])
for r in rows("calls.csv"):
    if r["first_time_caller"].lower() == "true" and int(r["duration_sec"]) >= 30:
        m = ct_month(r["started_at"])
        uniq[(m, r["source"])] += 1
        if r["source"] == "google_ads" and r["campaign_id"] == BRAND and "2026-06" <= m <= "2026-08":
            brand[2] += 1

# Live dashboard, "Cost per lead by channel and month" (spend, unique leads, cost per lead)
# for Google Ads, Google Guaranteed, Meta. Typed in from the 7:41pm CT screenshot.
dash = {
    "2025-11": [(6612, 24, "275.49"), (1469, 39, "37.66"), (1238, 7, "176.84")],
    "2025-12": [(7070, 20, "353.50"), (1239, 28, "44.24"), (1163, 3, "387.83")],
    "2026-01": [(7268, 23, "315.99"), (1332, 40, "33.29"), (1157, 3, "385.73")],
    "2026-02": [(7054, 11, "641.23"), (918, 29, "31.67"), (1132, 3, "377.37")],
    "2026-03": [(7061, 24, "294.23"), (1009, 26, "38.82"), (1527, 10, "152.65")],
    "2026-04": [(6824, 31, "220.13"), (1263, 30, "42.09"), (1463, 5, "292.57")],
    "2026-05": [(9537, 59, "161.65"), (2901, 69, "42.04"), (1411, 6, "235.18")],
    "2026-06": [(9376, 95, "98.69"), (3687, 74, "49.83"), (1239, 5, "247.72")],
    "2026-07": [(9705, 104, "93.32"), (3559, 71, "50.12"), (1230, 2, "614.90")],
    "2026-08": [(9924, 107, "92.74"), (3618, 75, "48.25"), (1278, 4, "319.57")],
}

print("month    channel     dashboard (spend/unique/CPL)   snapshot (spend/unique/CPL)   result")
same = 0
for m, cells in dash.items():
    for ch, (s, u, c) in zip(CHANNELS, cells):
        S, U = spend[(m, ch)], uniq[(m, ch)]
        C = f"{S / U:.2f}"
        if (u, c) == (U, C) and abs(S - s) < 1:
            same += 1
            note = "match" if abs(S - s) <= Decimal("0.5") else "match (spend rounding)"
        else:
            note = "DIFFERENT"
        print(f"{m}  {ch:<10}  ${s:>6,} / {u:>3} / ${c:>7}        ${S:>9,.2f} / {U:>3} / ${C:>7}   {note}")
print(f"\n{same} of {len(dash) * len(CHANNELS)} cells match")
print(f"Brand campaign, summer 2026: spend ${brand[0]:,.2f}, conversions {brand[1]}, unique leads {brand[2]}")
