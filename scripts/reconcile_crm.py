"""Offline CRM reconciliation under an explicitly proposed source dictionary."""
import argparse
from collections import Counter
import csv
from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.normalization.crm import SourceRules, normalize_crm_row, aggregate_crm

ROOT = Path(__file__).resolve().parents[1]
HEADER = ["job_id", "customer_id", "created_at", "updated_at", "lead_source",
          "job_type", "status", "revenue_usd", "zip"]


def reconcile_crm_snapshot() -> dict:
    policy = json.loads((ROOT / "tests/fixtures/crm-source-map-proposed.json").read_text())
    rules = SourceRules(policy["version"], policy["aliases"])
    # Expected values come directly from CSV plus the explicit policy fixture.
    aliases = {label.strip().casefold(): bucket for label, bucket in policy["aliases"].items()}
    with (ROOT / "data/snapshot-2026-09-23/crm_jobs.csv").open(newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames != HEADER:
            raise ValueError("unexpected CRM CSV header")
        rows = list(reader)
    expected = {}
    normalized = []
    label_counts = Counter()
    status_counts = Counter()
    for raw in rows:
        day = datetime.fromisoformat(raw["created_at"]).astimezone(
            ZoneInfo("America/Chicago")).date().isoformat()
        label = raw["lead_source"].strip().casefold()
        channel = aliases.get(label, "unattributed")
        key = (day, channel, "crm", None, None, "not_applicable")
        bucket = expected.setdefault(key, {"jobs": 0, "completed_jobs": 0,
            "revenue_usd": Decimal(0), "unresolved_jobs": 0})
        bucket["jobs"] += 1
        bucket["completed_jobs"] += int(raw["status"] == "completed")
        if raw["status"] == "completed":
            if not raw["revenue_usd"]:
                raise AssertionError("frozen completed job is missing revenue")
            bucket["revenue_usd"] += Decimal(raw["revenue_usd"])
        bucket["unresolved_jobs"] += int(channel == "unattributed")
        adapted = dict(raw)
        adapted["lead_source"] = raw["lead_source"] or None
        adapted["revenue_usd"] = Decimal(raw["revenue_usd"]) if raw["revenue_usd"] else None
        normalized.append(normalize_crm_row(adapted, rules=rules))
        label_counts[raw["lead_source"]] += 1
        status_counts[raw["status"]] += 1
    daily = aggregate_crm(normalized)
    if {row.bucket_key for row in daily} != set(expected):
        raise AssertionError("CRM bucket keys do not match raw source")
    for row in daily:
        for field, value in expected[row.bucket_key].items():
            if getattr(row, field) != value:
                raise AssertionError(f"daily CRM {field} mismatch")
        if row.missing_completed_revenue_jobs or row.quality_issues:
            raise AssertionError("unexpected frozen CRM revenue quality issue")
    channels = {}
    for channel in sorted({row.channel for row in daily}):
        group = [row for row in daily if row.channel == channel]
        channels[channel] = {
            "jobs": sum(row.jobs for row in group),
            "completed_jobs": sum(row.completed_jobs for row in group),
            "completed_revenue_usd": str(sum((row.revenue_usd for row in group), Decimal(0))),
        }
    return {
        "scope": "Frozen CRM snapshot; proposed dictionary is not an accepted production rule.",
        "header": HEADER, "mapping_version": rules.version,
        "mapping_fingerprint": rules.fingerprint,
        "reconciliation": "PASS: all booking-date/source buckets and job/revenue metrics match raw CSV calculations.",
        "raw_rows": len(rows), "distinct_job_ids": len({row["job_id"] for row in rows}),
        "daily_buckets": len(daily),
        "first_booking_day_central": min(row.analysis_date for row in daily),
        "last_booking_day_central": max(row.analysis_date for row in daily),
        "completed_jobs": sum(row.completed_jobs for row in daily),
        "completed_revenue_usd": str(sum((row.revenue_usd for row in daily), Decimal(0))),
        "missing_completed_revenue_jobs": sum(row.missing_completed_revenue_jobs for row in daily),
        "unresolved_source_jobs": sum(row.unresolved_jobs for row in daily),
        "status_counts": dict(sorted(status_counts.items())),
        "raw_source_label_counts": dict(sorted(label_counts.items())),
        "by_proposed_channel": channels,
        "live_api_and_fact_writes": "not run",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rendered = json.dumps(reconcile_crm_snapshot(), indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered)
    print(rendered)
