"""Offline daily-bucket reconciliation; frozen CSV adapters are not API loaders.

Run from repository root:
    python3 -m scripts.reconcile_daily_aggregation
Writes nothing unless --output is supplied; never calls APIs or databases.
"""
import argparse
import csv
from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.normalization.daily import aggregate_daily
from scripts.normalization.google import normalize_google_row
from scripts.normalization.lsa import normalize_lsa_row
from scripts.normalization.meta import normalize_meta_row

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data/snapshot-2026-09-23"
HEADERS = {
    "google_ads_insights.csv": ["date", "customer_id", "campaign_id", "campaign_name",
        "ad_group_id", "ad_group_name", "impressions", "clicks", "cost_micros", "conversions"],
    "meta_insights.csv": ["date_start", "date_stop", "account_id", "campaign_id",
        "campaign_name", "adset_id", "adset_name", "impressions", "clicks", "spend", "leads"],
    "lsa_leads.csv": ["lead_id", "lead_created_at", "category", "lead_type",
        "charge_status", "credited_at", "cost_usd"],
}


def reconcile_snapshot() -> dict:
    expected = {}
    contributions = []
    headers = {}
    for filename, required in HEADERS.items():
        with (SNAPSHOT / filename).open(newline="") as file:
            reader = csv.DictReader(file)
            headers[filename] = reader.fieldnames
            if reader.fieldnames != required:
                raise ValueError(f"{filename}: unexpected header")
            rows = list(reader)
        for raw in rows:
            # Build the independent expected bucket directly from CSV fields;
            # do not derive it from the normalized row or its brand classifier.
            if filename == "google_ads_insights.csv":
                brand = "brand" if raw["campaign_id"] == "20814455901" else (
                    "non_brand" if raw["campaign_id"] in {
                        "20814455917", "20814455930", "20814455948"} else None)
                key = (raw["date"], "google_ads", "google_ads",
                       raw["customer_id"], raw["campaign_id"], brand)
                impressions, clicks = int(raw["impressions"]), int(raw["clicks"])
                spend = Decimal(raw["cost_micros"]) / Decimal(1_000_000)
                leads = Decimal(raw["conversions"])
                adapted = dict(raw)
                for field in ("impressions", "clicks", "cost_micros"):
                    adapted[field] = int(raw[field])
                adapted["conversions"] = Decimal(raw["conversions"])
                contribution = normalize_google_row(adapted)
                name = raw["campaign_name"]
            elif filename == "meta_insights.csv":
                brand = "non_brand" if raw["campaign_id"] in {
                    "120208841937650100", "120208841937650200"} else None
                key = (raw["date_start"], "meta", "meta_ads",
                       raw["account_id"], raw["campaign_id"], brand)
                impressions, clicks = int(raw["impressions"]), int(raw["clicks"])
                spend, leads = Decimal(raw["spend"]), Decimal(raw["leads"])
                adapted = dict(raw)
                # CSV flattened leads are explicitly adapted for offline use.
                adapted["actions"] = [{"action_type": "lead", "value": raw["leads"]}]
                contribution = normalize_meta_row(adapted)
                name = raw["campaign_name"]
            else:
                day = datetime.fromisoformat(raw["lead_created_at"].replace("Z", "+00:00"))
                key = (day.astimezone(ZoneInfo("America/Chicago")).date().isoformat(),
                       "google_lsa", "lsa", None, None, "not_applicable")
                impressions, clicks = 0, 0
                spend = Decimal(raw["cost_usd"]) if raw["charge_status"] == "CHARGED" else Decimal(0)
                leads = Decimal(1)
                adapted = dict(raw)
                adapted["cost_usd"] = Decimal(raw["cost_usd"])
                adapted["credited_at"] = raw["credited_at"] or None
                contribution = normalize_lsa_row(adapted)
                name = None
            bucket = expected.setdefault(key, {
                "source_row_count": 0, "impressions": 0, "clicks": 0,
                "spend_usd": Decimal(0), "reported_leads": Decimal(0), "names": set()})
            bucket["source_row_count"] += 1
            bucket["impressions"] += impressions
            bucket["clicks"] += clicks
            bucket["spend_usd"] += spend
            bucket["reported_leads"] += leads
            if name is not None:
                bucket["names"].add(name)
            contributions.append(contribution)

    actual = aggregate_daily(contributions)
    if {row.bucket_key for row in actual} != set(expected):
        raise AssertionError("daily bucket keys differ from raw snapshot")
    for row in actual:
        bucket = expected[row.bucket_key]
        for field in ("source_row_count", "impressions", "clicks", "spend_usd", "reported_leads"):
            if getattr(row, field) != bucket[field]:
                raise AssertionError(f"{row.source_platform}: daily {field} mismatch")
        if row.campaign_names != tuple(sorted(bucket["names"])):
            raise AssertionError("daily campaign labels differ from raw snapshot")
    sources = {}
    for platform in ("google_ads", "meta_ads", "lsa"):
        buckets = [row for row in actual if row.source_platform == platform]
        sources[platform] = {
            "source_rows": sum(row.source_row_count for row in buckets),
            "daily_buckets": len(buckets),
            "first_day": min(row.analysis_date for row in buckets),
            "last_day": max(row.analysis_date for row in buckets),
            "impressions": sum(row.impressions for row in buckets),
            "clicks": sum(row.clicks for row in buckets),
            "spend_usd": str(sum((row.spend_usd for row in buckets), Decimal(0))),
            "reported_leads": str(sum((row.reported_leads for row in buckets), Decimal(0))),
            "unknown_brand_buckets": sum(row.brand_classification is None for row in buckets),
            "multi_name_buckets": sum(len(row.campaign_names) > 1 for row in buckets),
        }
    return {
        "scope": "Frozen snapshot only; no live ingestion or fact-table integration.",
        "snapshot": "data/snapshot-2026-09-23",
        "headers": headers,
        "bucket_grain": ["analysis_date", "channel", "source_platform",
                         "source_account_id", "campaign_id", "brand_classification"],
        "reconciliation": "PASS: all daily bucket keys, metrics, source counts and labels match raw CSVs.",
        "sources": sources,
        "all_source_rows": len(contributions),
        "all_daily_buckets": len(actual),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = reconcile_snapshot()
    rendered = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered)
    print(rendered)
