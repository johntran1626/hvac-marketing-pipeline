"""Google Local Services Ads (Google Guaranteed) leads into raw_lsa_leads (Issue #28).

Moved from scripts/backfill_lsa.py (the M1 hand backfill). Rows are stored exactly as the API
returns them, including charge_status and credited_at.
Refresh is 30 days because a lead can flip from CHARGED to CREDITED up to 30 days later (docs/API.md).
"""
from datetime import date

from worker.sources import SOURCES
from worker.sync import Source

LSA = Source(
    name="lsa",
    path="/v1/lsa/leads",
    table="raw_lsa_leads",
    on_conflict="lead_id",
    first_day=date(2024, 10, 1),  # docs/API.md: "Data starts on 2024-10-01"
    refresh_days=30,
)
SOURCES[LSA.name] = LSA
