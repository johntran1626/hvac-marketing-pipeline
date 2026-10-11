"""Offline reconciliation of every Calls daily bucket under both candidate rules.

CSV adapters are explicit; this is not a loader or evidence of live fact writes.
Run: python3 -m scripts.reconcile_calls --output notes/m2-calls-evidence.json
"""
import argparse
# Expected campaign IDs are independently transcribed from the schema.
# Do not import transformation brand rules: reconciliation must detect drift.
from collections import Counter
import csv
from datetime import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.normalization.calls import LeadRule, normalize_call_row, aggregate_calls

ROOT = Path(__file__).resolve().parents[1]
HEADER = ["call_id", "started_at", "duration_sec", "tracking_number",
          "source", "campaign_id", "caller_hash", "first_time_caller"]
BRANDS = {
    "20814455901": "brand", "20814455917": "non_brand",
    "20814455930": "non_brand", "20814455948": "non_brand",
}


def reconcile_calls_snapshot() -> dict:
    with (ROOT / "data/snapshot-2026-09-23/calls.csv").open(newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames != HEADER:
            raise ValueError("calls.csv: unexpected header")
        rows = list(reader)
    normalized = []
    expected = {}
    dates = []
    first_hashes = Counter()
    for raw in rows:
        if raw["first_time_caller"] not in {"true", "false"}:
            raise ValueError("calls.csv: unexpected boolean representation")
        first = raw["first_time_caller"] == "true"
        duration = int(raw["duration_sec"])
        day = datetime.fromisoformat(raw["started_at"].replace("Z", "+00:00")).astimezone(
            ZoneInfo("America/Chicago")).date().isoformat()
        dates.append(day)
        source = raw["source"]
        campaign = raw["campaign_id"] or None if source == "google_ads" else None
        brand = BRANDS.get(campaign) if source == "google_ads" else "not_applicable"
        key = (day, source, "call_tracking", None, campaign, brand)
        bucket = expected.setdefault(key, {"calls": 0, "first_time_calls": 0,
            "returning_calls": 0, "all_first_hashes": set(), "qualified_hashes": set()})
        bucket["calls"] += 1
        bucket["first_time_calls"] += int(first)
        bucket["returning_calls"] += int(not first)
        if first:
            first_hashes[raw["caller_hash"]] += 1
            bucket["all_first_hashes"].add(raw["caller_hash"])
            if duration >= 30:
                bucket["qualified_hashes"].add(raw["caller_hash"])
        adapted = dict(raw)
        adapted["duration_sec"] = duration
        adapted["campaign_id"] = raw["campaign_id"] or None
        adapted["first_time_caller"] = first
        normalized.append(normalize_call_row(adapted))

    outputs = {}
    for threshold, lead_field in ((0, "all_first_hashes"), (30, "qualified_hashes")):
        daily = aggregate_calls(normalized, rule=LeadRule(threshold))
        if {row.bucket_key for row in daily} != set(expected):
            raise AssertionError("daily call keys differ from raw snapshot")
        for row in daily:
            bucket = expected[row.bucket_key]
            for field in ("calls", "first_time_calls", "returning_calls"):
                if getattr(row, field) != bucket[field]:
                    raise AssertionError(f"daily {field} does not reconcile")
            if row.unique_leads != len(bucket[lead_field]):
                raise AssertionError("candidate unique-lead count does not reconcile")
            if row.unresolved_calls != 0:
                raise AssertionError("unexpected unresolved attribution in frozen data")
        outputs[threshold] = daily

    sources = {}
    recent = {}
    for channel in sorted({row["source"] for row in rows}):
        bare = [row for row in outputs[0] if row.channel == channel]
        qualified = [row for row in outputs[30] if row.channel == channel]
        sources[channel] = {
            "calls": sum(row.calls for row in bare),
            "first_time_unique_leads": sum(row.unique_leads for row in bare),
            "first_time_ge30_unique_leads": sum(row.unique_leads for row in qualified),
        }
        recent_bare = [row for row in bare if "2026-08-24" <= row.analysis_date <= "2026-09-22"]
        recent_qualified = [row for row in qualified if "2026-08-24" <= row.analysis_date <= "2026-09-22"]
        recent[channel] = {
            "calls": sum(row.calls for row in recent_bare),
            "first_time_unique_leads": sum(row.unique_leads for row in recent_bare),
            "first_time_ge30_unique_leads": sum(row.unique_leads for row in recent_qualified),
        }
    return {
        "scope": "Frozen Calls snapshot only; candidate rules are comparisons, not a canonical team decision.",
        "snapshot": "data/snapshot-2026-09-23/calls.csv",
        "header": HEADER,
        "reconciliation": "PASS: every daily bucket and call/lead metric matches independent raw calculations under thresholds 0 and 30.",
        "raw_rows": len(rows),
        "distinct_call_ids": len({row["call_id"] for row in rows}),
        "daily_buckets_per_rule": len(outputs[0]),
        "first_day_central": min(dates),
        "last_day_central": max(dates),
        "first_time_calls": sum(row["first_time_caller"] == "true" for row in rows),
        "returning_calls": sum(row["first_time_caller"] == "false" for row in rows),
        "distinct_first_time_hashes": len(first_hashes),
        "repeated_first_time_hash_groups": sum(count > 1 for count in first_hashes.values()),
        "first_time_ge30_unique_leads": sum(row.unique_leads for row in outputs[30]),
        "unresolved_attribution_calls": sum(row.unresolved_calls for row in outputs[0]),
        "by_channel_all_history": sources,
        "comparison_period": "Inclusive Central dates 2026-08-24 through 2026-09-22",
        "by_channel_comparison_period": recent,
        "live_api_and_fact_writes": "not run",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = reconcile_calls_snapshot()
    rendered = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered)
    print(rendered)
