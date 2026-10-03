"""Reproduce Diane's numbers from the snapshot and print the data-quality flags in notes/data-map.md.

Run from the repo root:  python3 scripts/check_m1_memo.py
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

# Memo-specific calculations
from datetime import datetime, date
from zoneinfo import ZoneInfo

WINDOW_START = date(2026, 8, 24)
WINDOW_END = date(2026, 9, 22)
CENTRAL = ZoneInfo("America/Chicago")
PACIFIC = ZoneInfo("America/Los_Angeles")


def central_date_from_meta_day(date_start):
    """Meta's date_start is a Pacific calendar day (docs/API.md); convert it to
    the Central calendar date so it lines up with the Central-time window used
    for calls and LSA leads."""
    d = date.fromisoformat(date_start)
    pacific_midnight = datetime(d.year, d.month, d.day, tzinfo=PACIFIC)
    return pacific_midnight.astimezone(CENTRAL).date()


section("10. Winter vs summer completed jobs per calendar day")
periods = {
    "winter_2025_11_to_2026_02": (date(2025, 11, 1), date(2026, 2, 28)),
    "summer_2026_06_to_08": (date(2026, 6, 1), date(2026, 8, 31)),
}
for name, (start, end) in periods.items():
    completed = [
        r for r in jobs
        if r["status"] == "completed"
        and start <= datetime.fromisoformat(r["created_at"]).date() <= end
    ]
    days = (end - start).days + 1
    print(f"  {name}: completed={len(completed)} days={days} jobs/day={len(completed)/days:.2f}")


section("11. Latest 30 days: unique first-time calls >=30 seconds, Central dates")
real_callers = defaultdict(set)
for r in calls:
    d = datetime.fromisoformat(
        r["started_at"].replace("Z", "+00:00")
    ).astimezone(CENTRAL).date()

    if not (WINDOW_START <= d <= WINDOW_END):
        continue
    if r["first_time_caller"].lower() != "true":
        continue
    if int(r["duration_sec"]) < 30:
        continue

    real_callers[r["source"]].add(r["caller_hash"])

for source in sorted(real_callers):
    print(f"  {source}: {len(real_callers[source])}")


section("12. Latest 30 days: paid-channel spend and cost per real lead")
google_spend = sum(
    int(r["cost_micros"]) / 1_000_000
    for r in g
    if WINDOW_START <= date.fromisoformat(r["date"]) <= WINDOW_END
)

meta_spend = sum(
    float(r["spend"])
    for r in m
    if WINDOW_START <= central_date_from_meta_day(r["date_start"]) <= WINDOW_END
)

lsa_spend = 0.0
for r in lsa:
    d = datetime.fromisoformat(
        r["lead_created_at"].replace("Z", "+00:00")
    ).astimezone(CENTRAL).date()
    if WINDOW_START <= d <= WINDOW_END and r["charge_status"] == "CHARGED":
        lsa_spend += float(r["cost_usd"])

paid = {
    "Google Ads": (google_spend, len(real_callers["google_ads"])),
    "Google LSA": (lsa_spend, len(real_callers["google_lsa"])),
    "Meta": (meta_spend, len(real_callers["meta"])),
}

for channel, (spend, leads) in paid.items():
    print(f"  {channel}: spend=${spend:,.2f} real_leads={leads} CPL=${spend/leads:,.2f}")

total_paid_spend = sum(v[0] for v in paid.values())
total_real_leads = sum(v[1] for v in paid.values())
print(f"  blended: spend=${total_paid_spend:,.2f} real_leads={total_real_leads} CPL=${total_paid_spend/total_real_leads:,.2f}")


section("13. Google campaign performance, latest 30 days")
google_campaign_spend = defaultdict(float)
google_campaign_names = defaultdict(set)

for r in g:
    d = date.fromisoformat(r["date"])
    if WINDOW_START <= d <= WINDOW_END:
        cid = r["campaign_id"]
        google_campaign_spend[cid] += int(r["cost_micros"]) / 1_000_000
        google_campaign_names[cid].add(r["campaign_name"])

google_campaign_callers = defaultdict(set)
for r in calls:
    if r["source"] != "google_ads" or not r["campaign_id"]:
        continue

    d = datetime.fromisoformat(
        r["started_at"].replace("Z", "+00:00")
    ).astimezone(CENTRAL).date()

    if not (WINDOW_START <= d <= WINDOW_END):
        continue
    if r["first_time_caller"].lower() != "true":
        continue
    if int(r["duration_sec"]) < 30:
        continue

    google_campaign_callers[r["campaign_id"]].add(r["caller_hash"])

google_campaign_cpl = {}
for cid in sorted(google_campaign_spend):
    spend = google_campaign_spend[cid]
    leads = len(google_campaign_callers[cid])
    cpl = spend / leads if leads else None
    google_campaign_cpl[cid] = cpl
    cpl_text = f"${cpl:,.2f}" if cpl is not None else "N/A"
    print(
        f"  {cid} | {', '.join(sorted(google_campaign_names[cid]))} | "
        f"spend=${spend:,.2f} | real_leads={leads} | CPL={cpl_text}"
    )


section("14. Meta ad-set reported performance, latest 30 days")
meta_adsets = defaultdict(lambda: {
    "campaign": "",
    "name": "",
    "spend": 0.0,
    "clicks": 0,
    "leads": 0,
})

for r in m:
    d = central_date_from_meta_day(r["date_start"])
    if not (WINDOW_START <= d <= WINDOW_END):
        continue

    aid = r["adset_id"]
    meta_adsets[aid]["campaign"] = r["campaign_name"]
    meta_adsets[aid]["name"] = r["adset_name"]
    meta_adsets[aid]["spend"] += float(r["spend"])
    meta_adsets[aid]["clicks"] += int(r["clicks"])
    meta_adsets[aid]["leads"] += int(r["leads"])

for aid, s in sorted(meta_adsets.items()):
    reported_cpl = s["spend"] / s["leads"] if s["leads"] else None
    cpl_text = f"${reported_cpl:,.2f}" if reported_cpl is not None else "N/A"
    print(
        f"  {aid} | {s['campaign']} | {s['name']} | "
        f"spend=${s['spend']:,.2f} | clicks={s['clicks']} | "
        f"reported_leads={s['leads']} | reported_CPL={cpl_text}"
    )

kept_meta = {"120208841937650212", "120208841937650213"}
kept_spend = sum(meta_adsets[x]["spend"] for x in kept_meta)
kept_leads = sum(meta_adsets[x]["leads"] for x in kept_meta)
print(
    f"  proposed retained Meta ad sets: spend=${kept_spend:.2f} "
    f"reported_leads={kept_leads} reported_CPL=${kept_spend/kept_leads:.2f}"
)


section("15. Proposed $11,400 current-budget scenario")
budget = {
    "Google LSA": 4000,
    "AC Replacement": 3000,
    "AC Repair": 2600,
    "Brand": 1400,
    "Meta": 400,
}

observed_cpl = {
    "Google LSA": paid["Google LSA"][0] / paid["Google LSA"][1],
    "AC Replacement": google_campaign_cpl["20814455948"],
    "AC Repair": google_campaign_cpl["20814455917"],
    "Brand": google_campaign_cpl["20814455901"],
    "Meta": paid["Meta"][0] / paid["Meta"][1],
}

projected_leads = 0.0
for name, dollars in budget.items():
    leads = dollars / observed_cpl[name]
    projected_leads += leads
    print(
        f"  {name}: budget=${dollars:,.0f} observed_CPL=${observed_cpl[name]:,.2f} "
        f"modeled_real_leads={leads:.1f}"
    )

projected_cpl = sum(budget.values()) / projected_leads
current_cpl = total_paid_spend / total_real_leads
print(f"  current observed blended CPL=${current_cpl:.2f}")
print(f"  modeled blended CPL=${projected_cpl:.2f}")
print(f"  modeled improvement={(1 - projected_cpl/current_cpl) * 100:.1f}%")
print("  NOTE: scenario assumes recent observed CPLs hold after reallocation; it is not a forecast guarantee.")


section("16. Brand campaign, summer 2026: Diane's reported cost vs cost per real lead")
BRAND = "20814455901"
summer_start, summer_end = (date.fromisoformat(x) for x in SUMMER)
brand_spend = sum(
    int(r["cost_micros"]) / 1_000_000
    for r in g
    if r["campaign_id"] == BRAND and SUMMER[0] <= r["date"] <= SUMMER[1]
)
brand_conv = sum(
    float(r["conversions"])
    for r in g
    if r["campaign_id"] == BRAND and SUMMER[0] <= r["date"] <= SUMMER[1]
)
brand_callers = set()
for r in calls:
    if r["source"] != "google_ads" or r["campaign_id"] != BRAND:
        continue
    d = datetime.fromisoformat(
        r["started_at"].replace("Z", "+00:00")
    ).astimezone(CENTRAL).date()
    if not (summer_start <= d <= summer_end):
        continue
    if r["first_time_caller"].lower() != "true":
        continue
    if int(r["duration_sec"]) < 30:
        continue
    brand_callers.add(r["caller_hash"])
print(f"  spend=${brand_spend:,.2f} reported_conversions={brand_conv:.1f} cost/conv=${brand_spend/brand_conv:.2f}")
print(f"  real_leads={len(brand_callers)} cost/real_lead=${brand_spend/len(brand_callers):.2f}")
