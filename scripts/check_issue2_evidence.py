"""Reproduce the evidence required by Issue #2 from the Project B snapshot.

Run from the repo root:
    python3 scripts/check_issue2_evidence.py

Standard library only. Reads the snapshot CSVs and never edits them.
A "real lead" for the latest-30-day comparisons is a unique first-time
caller with a call duration of at least 30 seconds.
"""
import csv
from collections import Counter, defaultdict
from datetime import date, datetime
from zoneinfo import ZoneInfo

SNAP = "data/snapshot-2026-09-23/"
CENTRAL = ZoneInfo("America/Chicago")
PACIFIC = ZoneInfo("America/Los_Angeles")
WINDOW_START = date(2026, 8, 24)
WINDOW_END = date(2026, 9, 22)
SUMMER_START = date(2026, 6, 1)
SUMMER_END = date(2026, 8, 31)
KATY_ZIPS = {"77449", "77450", "77493", "77494"}


def rows(name):
    with open(SNAP + name, newline="") as f:
        return list(csv.DictReader(f))


def section(title):
    print(f"\n== {title}")


def utc_to_central_day(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(CENTRAL).date()


def meta_to_central_day(value):
    d = date.fromisoformat(value)
    dt = datetime(d.year, d.month, d.day, tzinfo=PACIFIC)
    return dt.astimezone(CENTRAL).date()


g = rows("google_ads_insights.csv")
m = rows("meta_insights.csv")
lsa = rows("lsa_leads.csv")
calls = rows("calls.csv")
jobs = rows("crm_jobs.csv")

section("1. Snapshot coverage")
print(f"  Google Ads rows: {len(g):,}")
print(f"  Meta rows: {len(m):,}")
print(f"  LSA leads: {len(lsa):,}")
print(f"  Calls: {len(calls):,}")
print(f"  CRM jobs: {len(jobs):,}")

section("2. Paid spend by channel, full snapshot")
google_total = sum(int(r["cost_micros"]) for r in g) / 1_000_000
meta_total = sum(float(r["spend"]) for r in m)
lsa_charged = sum(float(r["cost_usd"]) for r in lsa if r["charge_status"] == "CHARGED")
lsa_credited_source = sum(float(r["cost_usd"]) for r in lsa if r["charge_status"] == "CREDITED")
print(f"  Google Ads: ${google_total:,.2f}")
print(f"  Meta: ${meta_total:,.2f}")
print(f"  LSA net charged spend: ${lsa_charged:,.2f}")
print(f"  LSA source cost attached to credited/refunded leads: ${lsa_credited_source:,.2f}")

section("3. Platform-reported leads/conversions, full snapshot")
google_conversions = sum(float(r["conversions"]) for r in g)
meta_leads = sum(int(r["leads"]) for r in m)
lsa_status = Counter(r["charge_status"] for r in lsa)
print(f"  Google reported conversions: {google_conversions:,.1f}")
print(f"  Meta reported leads: {meta_leads:,}")
print(f"  LSA rows: {len(lsa):,} {dict(lsa_status)}")

section("4. Tracked calls, unique callers, first-time vs returning")
for source in sorted({r["source"] for r in calls}):
    rs = [r for r in calls if r["source"] == source]
    unique = len({r["caller_hash"] for r in rs})
    first = sum(r["first_time_caller"].lower() == "true" for r in rs)
    returning = sum(r["first_time_caller"].lower() == "false" for r in rs)
    short = sum(int(r["duration_sec"]) < 30 for r in rs)
    print(
        f"  {source}: calls={len(rs):,} unique_callers={unique:,} "
        f"first_time_calls={first:,} returning_calls={returning:,} short_under_30s={short:,}"
    )
print(f"  TOTAL: calls={len(calls):,} unique_callers={len({r['caller_hash'] for r in calls}):,}")

real_callers = defaultdict(set)
for r in calls:
    d = utc_to_central_day(r["started_at"])
    if WINDOW_START <= d <= WINDOW_END and r["first_time_caller"].lower() == "true" and int(r["duration_sec"]) >= 30:
        real_callers[r["source"]].add(r["caller_hash"])
section("5. Latest 30 days: qualifying real callers")
for source in sorted(real_callers):
    print(f"  {source}: {len(real_callers[source])}")

section("5b. Latest 30 days: paid-channel spend and real-lead CPL")
google_30_total = sum(
    int(r["cost_micros"]) / 1_000_000
    for r in g
    if WINDOW_START <= date.fromisoformat(r["date"]) <= WINDOW_END
)
meta_30_total = sum(
    float(r["spend"])
    for r in m
    if WINDOW_START <= meta_to_central_day(r["date_start"]) <= WINDOW_END
)
lsa_30_total = sum(
    float(r["cost_usd"])
    for r in lsa
    if r["charge_status"] == "CHARGED"
    and WINDOW_START <= utc_to_central_day(r["lead_created_at"]) <= WINDOW_END
)
paid_30 = {
    "Google Ads": (google_30_total, len(real_callers["google_ads"])),
    "Google LSA": (lsa_30_total, len(real_callers["google_lsa"])),
    "Meta": (meta_30_total, len(real_callers["meta"])),
}
for channel, (spend, leads) in paid_30.items():
    print(f"  {channel}: spend=${spend:,.2f} real_leads={leads} CPL=${spend/leads:,.2f}")
paid_spend = sum(x[0] for x in paid_30.values())
paid_leads = sum(x[1] for x in paid_30.values())
print(f"  blended: spend=${paid_spend:,.2f} real_leads={paid_leads} CPL=${paid_spend/paid_leads:,.2f}")

section("6. Google campaign performance")
google_all = defaultdict(lambda: {"spend": 0.0, "conv": 0.0, "names": set()})
for r in g:
    x = google_all[r["campaign_id"]]
    x["spend"] += int(r["cost_micros"]) / 1_000_000
    x["conv"] += float(r["conversions"])
    x["names"].add(r["campaign_name"])
for cid, x in sorted(google_all.items()):
    print(
        f"  all-time {cid} | {', '.join(sorted(x['names']))} | spend=${x['spend']:,.2f} "
        f"| reported_conversions={x['conv']:.1f} | reported_CPL=${x['spend']/x['conv']:.2f}"
    )

google_30_spend = defaultdict(float)
google_30_names = defaultdict(set)
for r in g:
    d = date.fromisoformat(r["date"])
    if WINDOW_START <= d <= WINDOW_END:
        google_30_spend[r["campaign_id"]] += int(r["cost_micros"]) / 1_000_000
        google_30_names[r["campaign_id"]].add(r["campaign_name"])
google_30_callers = defaultdict(set)
for r in calls:
    if r["source"] != "google_ads" or not r["campaign_id"]:
        continue
    d = utc_to_central_day(r["started_at"])
    if WINDOW_START <= d <= WINDOW_END and r["first_time_caller"].lower() == "true" and int(r["duration_sec"]) >= 30:
        google_30_callers[r["campaign_id"]].add(r["caller_hash"])
for cid in sorted(google_30_spend):
    spend = google_30_spend[cid]
    leads = len(google_30_callers[cid])
    cpl = f"${spend/leads:,.2f}" if leads else "N/A"
    print(
        f"  latest30 {cid} | {', '.join(sorted(google_30_names[cid]))} | "
        f"spend=${spend:,.2f} | real_leads={leads} | real_CPL={cpl}"
    )

section("7. Meta campaign and ad-set performance")
meta_campaign = defaultdict(lambda: {"spend": 0.0, "leads": 0, "name": ""})
for r in m:
    x = meta_campaign[r["campaign_id"]]
    x["spend"] += float(r["spend"])
    x["leads"] += int(r["leads"])
    x["name"] = r["campaign_name"]
for cid, x in sorted(meta_campaign.items()):
    print(f"  campaign {cid} | {x['name']} | spend=${x['spend']:,.2f} | reported_leads={x['leads']} | reported_CPL=${x['spend']/x['leads']:.2f}")

meta_adset_30 = defaultdict(lambda: {"spend": 0.0, "leads": 0, "clicks": 0, "campaign": "", "name": ""})
for r in m:
    if WINDOW_START <= meta_to_central_day(r["date_start"]) <= WINDOW_END:
        x = meta_adset_30[r["adset_id"]]
        x["spend"] += float(r["spend"])
        x["leads"] += int(r["leads"])
        x["clicks"] += int(r["clicks"])
        x["campaign"] = r["campaign_name"]
        x["name"] = r["adset_name"]
for aid, x in sorted(meta_adset_30.items()):
    cpl = f"${x['spend']/x['leads']:.2f}" if x["leads"] else "N/A"
    print(f"  latest30 {aid} | {x['campaign']} | {x['name']} | spend=${x['spend']:.2f} | clicks={x['clicks']} | reported_leads={x['leads']} | reported_CPL={cpl}")
print("  NOTE: calls.csv has no Meta campaign/ad-set ID, so true caller CPL is only defensible at channel level.")

section("8. LSA charged vs credited")
for status in ("CHARGED", "CREDITED", "NOT_CHARGED"):
    rs = [r for r in lsa if r["charge_status"] == status]
    source_cost = sum(float(r["cost_usd"]) for r in rs)
    print(f"  {status}: leads={len(rs):,} source_cost=${source_cost:,.2f}")

section("9. CRM jobs, seasonality, and Katy")
status_counts = Counter(r["status"] for r in jobs)
completed_revenue = sum(float(r["revenue_usd"] or 0) for r in jobs if r["status"] == "completed")
print(f"  jobs={len(jobs):,} status={dict(status_counts)}")
print(f"  completed revenue=${completed_revenue:,.2f}")
periods = {
    "winter_2025_11_to_2026_02": (date(2025, 11, 1), date(2026, 2, 28)),
    "summer_2026_06_to_08": (date(2026, 6, 1), date(2026, 8, 31)),
}
for name, (start, end) in periods.items():
    completed = sum(
        r["status"] == "completed" and start <= datetime.fromisoformat(r["created_at"]).date() <= end
        for r in jobs
    )
    days = (end - start).days + 1
    print(f"  {name}: completed={completed:,} days={days} jobs/day={completed/days:.2f}")
katy = [r for r in jobs if r["zip"] in KATY_ZIPS]
print(f"  Katy zips {sorted(KATY_ZIPS)}: jobs={len(katy)} status={dict(Counter(r['status'] for r in katy))}")
print(f"  Katy by year/status: {dict(sorted(Counter((r['created_at'][:4], r['status']) for r in katy).items()))}")

section("10. Data-quality and misleading-number checks")
renamed = {cid: sorted(x["names"]) for cid, x in google_all.items() if len(x["names"]) > 1}
print(f"  Google campaign IDs with multiple names: {renamed}")
print(f"  Google conversions are fractional: total={google_conversions:,.1f}; they are not people.")
print(f"  Calls repeat heavily: {len(calls):,} calls vs {len({r['caller_hash'] for r in calls}):,} unique callers.")
print(f"  LSA credits: {lsa_status['CREDITED']} refunded leads retain source cost and must not be counted as net spend.")
meta_gap = [r for r in m if "2026-08-04" <= r["date_start"] <= "2026-08-10"]
gap_spend = sum(float(r["spend"]) for r in meta_gap)
gap_clicks = sum(int(r["clicks"]) for r in meta_gap)
gap_leads = sum(int(r["leads"]) for r in meta_gap)
gap_calls = sum(r["source"] == "meta" and "2026-08-04" <= r["started_at"][:10] <= "2026-08-10" for r in calls)
print(f"  Meta Aug 4-10: spend=${gap_spend:.2f} clicks={gap_clicks} reported_leads={gap_leads} tracked_calls={gap_calls}.")
lead_sources = Counter(r["lead_source"] for r in jobs)
print(f"  CRM lead_source is messy: {len(lead_sources)} distinct values, blank={lead_sources['']}, '?'={lead_sources['?']}.")

brand = "20814455901"
brand_summer = []
for r in calls:
    if r["source"] == "google_ads" and r["campaign_id"] == brand:
        d = utc_to_central_day(r["started_at"])
        if SUMMER_START <= d <= SUMMER_END:
            brand_summer.append(r)
brand_returning = sum(r["first_time_caller"].lower() == "false" for r in brand_summer)
print(f"  Brand summer calls: total={len(brand_summer)} returning={brand_returning} ({brand_returning/len(brand_summer):.1%}).")
