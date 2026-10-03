"""Independent-source verification harness for Issue #4.

This script does NOT import scripts/check_m1_memo.py. It recomputes the
important memo claims directly from the snapshot CSVs, then checks the final
memo's required structure and cited values.

Run from the repo root:
    python3 scripts/verify_issue4_memo.py
"""
import csv
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SNAP = Path("data/snapshot-2026-09-23")
MEMO = Path("memo/read.md")
CENTRAL = ZoneInfo("America/Chicago")
PACIFIC = ZoneInfo("America/Los_Angeles")
WINDOW_START = date(2026, 8, 24)
WINDOW_END = date(2026, 9, 22)
SUMMER_START = date(2026, 6, 1)
SUMMER_END = date(2026, 8, 31)
KATY_ZIPS = {"77449", "77450", "77493", "77494"}


def rows(name):
    with (SNAP / name).open(newline="") as f:
        return list(csv.DictReader(f))


def central_day(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(CENTRAL).date()


def pacific_day(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(PACIFIC).date()


def meta_central_day(value):
    d = date.fromisoformat(value)
    return datetime(d.year, d.month, d.day, tzinfo=PACIFIC).astimezone(CENTRAL).date()


def near(actual, expected, cents=0.01):
    assert abs(actual - expected) <= cents, f"{actual} != {expected}"


def require(text, needle):
    assert needle in text, f"memo missing required text/value: {needle!r}"


g = rows("google_ads_insights.csv")
m = rows("meta_insights.csv")
lsa = rows("lsa_leads.csv")
calls = rows("calls.csv")
jobs = rows("crm_jobs.csv")
memo = MEMO.read_text()

# 1) Required format and ordering.
headings = [
    "## 1. What is actually driving the phones?",
    "## 2. What would you do in the next 30 days on the current budget?",
    "## 3. What would you refuse to do, and why?",
    "## 4. What number would tell you you were wrong?",
]
positions = [memo.index(h) for h in headings]
assert positions == sorted(positions), "required memo headings are out of order"
word_count = len(memo.split())
assert word_count <= 400, f"memo is over 400 words: {word_count}"
print(f"PASS structure: 4 exact headings in order; word count={word_count}")

# 2) Recompute latest-30-day qualifying callers.
real = defaultdict(set)
for r in calls:
    d = central_day(r["started_at"])
    if not (WINDOW_START <= d <= WINDOW_END):
        continue
    if r["first_time_caller"].lower() != "true" or int(r["duration_sec"]) < 30:
        continue
    real[r["source"]].add(r["caller_hash"])
assert len(real["google_ads"]) == 100
assert len(real["google_lsa"]) == 68
assert len(real["meta"]) == 6
assert len(real["gbp"]) == 126

google_spend = sum(
    int(r["cost_micros"]) / 1_000_000
    for r in g if WINDOW_START <= date.fromisoformat(r["date"]) <= WINDOW_END
)
meta_spend = sum(
    float(r["spend"])
    for r in m if WINDOW_START <= meta_central_day(r["date_start"]) <= WINDOW_END
)
lsa_spend = sum(
    float(r["cost_usd"])
    for r in lsa
    if r["charge_status"] == "CHARGED"
    and WINDOW_START <= central_day(r["lead_created_at"]) <= WINDOW_END
)
near(google_spend / 100, 89.54, 0.005)
near(lsa_spend / 68, 45.22, 0.005)
near(meta_spend / 6, 227.28, 0.005)
for value in ("100", "68", "6", "$89.54", "$45.22", "$227.28", "126"):
    require(memo, value)
print("PASS Q1 recent callers/CPL: Google 100/$89.54; LSA 68/$45.22; Meta 6/$227.28; GBP 126")

# 3) Brand summer platform metric vs real acquisition.
BRAND = "20814455901"
brand_spend = sum(
    int(r["cost_micros"]) / 1_000_000
    for r in g
    if r["campaign_id"] == BRAND
    and SUMMER_START <= date.fromisoformat(r["date"]) <= SUMMER_END
)
brand_conv = sum(
    float(r["conversions"])
    for r in g
    if r["campaign_id"] == BRAND
    and SUMMER_START <= date.fromisoformat(r["date"]) <= SUMMER_END
)
brand_real = {
    r["caller_hash"]
    for r in calls
    if r["source"] == "google_ads"
    and r["campaign_id"] == BRAND
    and SUMMER_START <= central_day(r["started_at"]) <= SUMMER_END
    and r["first_time_caller"].lower() == "true"
    and int(r["duration_sec"]) >= 30
}
near(brand_spend / brand_conv, 8.44, 0.005)
assert len(brand_real) == 65
near(brand_spend / len(brand_real), 72.59, 0.005)
require(memo, "$8.44")
require(memo, "$72.59")
print("PASS Q1 Brand: $8.44 reported conversion CPL vs $72.59 per qualifying real lead")

# 4) Latest-30-day Google campaign metrics.
campaign_spend = defaultdict(float)
campaign_real = defaultdict(set)
for r in g:
    if WINDOW_START <= date.fromisoformat(r["date"]) <= WINDOW_END:
        campaign_spend[r["campaign_id"]] += int(r["cost_micros"]) / 1_000_000
for r in calls:
    if r["source"] != "google_ads" or not r["campaign_id"]:
        continue
    d = central_day(r["started_at"])
    if WINDOW_START <= d <= WINDOW_END and r["first_time_caller"].lower() == "true" and int(r["duration_sec"]) >= 30:
        campaign_real[r["campaign_id"]].add(r["caller_hash"])
near(campaign_spend["20814455930"], 369.32, 0.005)
assert len(campaign_real["20814455930"]) == 0
require(memo, "$369.32")
require(memo, "zero qualifying real leads")

# 5) Meta retained-ad-set reported CPL.
KEEP_META = {"120208841937650212", "120208841937650213"}
kept_spend = 0.0
kept_leads = 0
for r in m:
    if r["adset_id"] in KEEP_META and WINDOW_START <= meta_central_day(r["date_start"]) <= WINDOW_END:
        kept_spend += float(r["spend"])
        kept_leads += int(r["leads"])
near(kept_spend / kept_leads, 8.08, 0.005)
require(memo, "$8.08")

# 6) Budget scenario.
google_campaign_cpl = {
    cid: campaign_spend[cid] / len(campaign_real[cid])
    for cid in ("20814455901", "20814455917", "20814455948")
}
channel_cpl = {
    "Google LSA": lsa_spend / len(real["google_lsa"]),
    "Meta": meta_spend / len(real["meta"]),
}
budget = {
    "Google LSA": (4000, channel_cpl["Google LSA"]),
    "AC Replacement": (3000, google_campaign_cpl["20814455948"]),
    "AC Repair": (2600, google_campaign_cpl["20814455917"]),
    "Brand": (1400, google_campaign_cpl["20814455901"]),
    "Meta": (400, channel_cpl["Meta"]),
}
assert sum(v[0] for v in budget.values()) == 11400
modeled_leads = sum(dollars / cpl for dollars, cpl in budget.values())
modeled_cpl = 11400 / modeled_leads
current_cpl = (google_spend + lsa_spend + meta_spend) / (100 + 68 + 6)
near(current_cpl, 76.97, 0.005)
near(modeled_cpl, 63.56, 0.005)
for value in ("$11,400", "$4,000", "$3,000", "$2,600", "$1,400", "$400", "$76.97", "$63.56"):
    require(memo, value)
print("PASS Q2: allocation totals $11,400; current blended CPL $76.97; modeled CPL $63.56")

# 7) Winter/summer completed jobs.
winter_start, winter_end = date(2025, 11, 1), date(2026, 2, 28)
summer_start, summer_end = date(2026, 6, 1), date(2026, 8, 31)
winter_completed = sum(
    r["status"] == "completed"
    and winter_start <= datetime.fromisoformat(r["created_at"]).date() <= winter_end
    for r in jobs
)
summer_completed = sum(
    r["status"] == "completed"
    and summer_start <= datetime.fromisoformat(r["created_at"]).date() <= summer_end
    for r in jobs
)
winter_rate = winter_completed / ((winter_end - winter_start).days + 1)
summer_rate = summer_completed / ((summer_end - summer_start).days + 1)
near(winter_rate, 7.03, 0.005)
near(summer_rate, 15.09, 0.005)
require(memo, "7.03/day")
require(memo, "15.09/day")

# 8) Meta Aug 4-10 anomaly, aligned to Meta/Pacific account days.
meta_gap_rows = [
    r for r in m if date(2026, 8, 4) <= date.fromisoformat(r["date_start"]) <= date(2026, 8, 10)
]
assert sum(int(r["leads"]) for r in meta_gap_rows) == 0
near(sum(float(r["spend"]) for r in meta_gap_rows), 291.15, 0.005)
assert sum(int(r["clicks"]) for r in meta_gap_rows) == 135
meta_gap_calls = [
    r for r in calls
    if r["source"] == "meta"
    and date(2026, 8, 4) <= pacific_day(r["started_at"]) <= date(2026, 8, 10)
]
assert len(meta_gap_calls) == 4
require(memo, "four tracked calls")
print("PASS Q3 Meta anomaly: $291.15 spend, 135 clicks, 0 reported leads, 4 tracked calls")

# 9) Katy cancellations.
katy = [r for r in jobs if r["zip"] in KATY_ZIPS]
assert all(r["status"] == "canceled" for r in katy)
katy_year = Counter(r["created_at"][:4] for r in katy)
assert katy_year == Counter({"2025": 78, "2026": 77, "2024": 26})
for value in ("77 in 2026", "78 in 2025", "26 in late 2024"):
    require(memo, value)
print("PASS Q3 Katy: 26 late-2024, 78 in 2025, 77 in 2026; all 181 rows canceled")

# 10) Question 4 must contain metric, threshold, and timeframe.
require(memo, "blended paid cost per real lead")
require(memo, "after the first 30 full days")
require(memo, "not below the current $76.97 baseline")
print("PASS Q4: metric, threshold, and 30-full-day check timeframe are explicit")

# 11) Check cited source paths exist.
for source in [
    Path("scripts/check_m1_memo.py"),
    Path("notes/data-map.md"),
    Path("README.md"),
    SNAP / "google_ads_insights.csv",
    SNAP / "meta_insights.csv",
    SNAP / "lsa_leads.csv",
    SNAP / "calls.csv",
    SNAP / "crm_jobs.csv",
]:
    assert source.exists(), f"missing cited source: {source}"
print("PASS sources: all cited repository paths exist and are checkable")

print("\nALL ISSUE #4 AUTOMATED CHECKS PASSED")
print("Reviewer must still read the memo and source evidence before independently approving Issue #4.")
