"""Reproduce Diane's numbers from the snapshot and print the data-quality flags in notes/data-map.md.

Run from the repo root:  python3 scripts/check_diane_claims.py
Standard library only. Reads data/snapshot-2026-09-23/ and never edits it.
"""
import csv
from collections import Counter, defaultdict

SNAP = "data/snapshot-2026-09-23/"
SUMMER = ("2026-06-01", "2026-08-31")
KATY_ZIPS = {"77449", "77450", "77493", "77494"}


def rows(name):
    with open(SNAP + name, newline="") as f:
        return list(csv.DictReader(f))


g = rows("google_ads_insights.csv")
m = rows("meta_insights.csv")
lsa = rows("lsa_leads.csv")
calls = rows("calls.csv")
jobs = rows("crm_jobs.csv")


def section(title):
    print(f"\n== {title}")


section("1. Google Ads, summer 2026: reported conversions and cost by campaign")
by_campaign = defaultdict(lambda: [0.0, 0])
for r in g:
    if SUMMER[0] <= r["date"] <= SUMMER[1]:
        by_campaign[r["campaign_id"]][0] += float(r["conversions"])
        by_campaign[r["campaign_id"]][1] += int(r["cost_micros"])
total_conv = sum(v[0] for v in by_campaign.values())
total_cost = sum(v[1] for v in by_campaign.values()) / 1e6
for cid, (conv, micros) in sorted(by_campaign.items()):
    cost = micros / 1e6
    print(f"  {cid}: conversions={conv:.1f} cost=${cost:,.2f} cost/conv=${cost / conv:.2f}")
print(f"  TOTAL: conversions={total_conv:.1f} cost=${total_cost:,.2f} cost/conv=${total_cost / total_conv:.2f}")

section("2. One campaign_id, more than one campaign_name")
names = defaultdict(set)
for r in g:
    names[r["campaign_id"]].add(r["campaign_name"])
for cid, n in names.items():
    if len(n) > 1:
        print(f"  {cid}: {sorted(n)}")

section("3. Meta, Aug 1-14 2026 (Pacific dates): spend, reported leads, clicks")
daily = defaultdict(lambda: [0.0, 0, 0])
for r in m:
    if "2026-08-01" <= r["date_start"] <= "2026-08-14":
        d = daily[r["date_start"]]
        d[0] += float(r["spend"]); d[1] += int(r["leads"]); d[2] += int(r["clicks"])
for day in sorted(daily):
    s, l, c = daily[day]
    print(f"  {day}: spend=${s:.2f} leads={l} clicks={c}")
zero_week = sum(daily[d][0] for d in daily if "2026-08-04" <= d <= "2026-08-10")
print(f"  spend Aug 4-10: ${zero_week:.2f}")
meta_calls = [r for r in calls if r["source"] == "meta" and "2026-08-04" <= r["started_at"][:10] <= "2026-08-10"]
print(f"  calls to the Meta tracking number Aug 4-10 (UTC dates): {len(meta_calls)}")

section("4. CRM completed jobs, Jun-Aug, by created_at date")
for year in ("2025", "2026"):
    n = sum(1 for r in jobs if r["status"] == "completed" and f"{year}-06-01" <= r["created_at"][:10] <= f"{year}-08-31")
    print(f"  {year}: {n}")

section("5. CRM jobs in Katy zips, by year and status")
for k, v in sorted(Counter((r["created_at"][:4], r["status"]) for r in jobs if r["zip"] in KATY_ZIPS).items()):
    print(f"  {k}: {v}")

section("6. LSA leads by charge_status")
print(" ", dict(Counter(r["charge_status"] for r in lsa)))

section("7. Calls by source; repeat and short calls")
print(" ", dict(Counter(r["source"] for r in calls)))
print(f"  total calls={len(calls)} unique caller_hash={len({r['caller_hash'] for r in calls})}")
print(f"  first_time_caller: {dict(Counter(r['first_time_caller'] for r in calls))}")
print(f"  calls under 30 seconds: {sum(int(r['duration_sec']) < 30 for r in calls)}")
print("  google_ads calls by campaign_id:", dict(Counter(r["campaign_id"] for r in calls if r["source"] == "google_ads")))

section("8. CRM lead_source: distinct spellings (free text typed by the rep)")
ls = Counter(r["lead_source"] for r in jobs)
print(f"  {len(ls)} distinct values; blank={ls['']} '?'={ls['?']}")

section("9. Time zones")
print("  CRM created_at offsets:", dict(Counter(r["created_at"][-6:] for r in jobs)))
print("  Google date=Central, Meta date=Pacific, LSA/calls timestamps=UTC (see data README)")
