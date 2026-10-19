"""Meta (Facebook and Instagram) ad-set insights into raw_meta_insights (Issue #27).

Rows are stored exactly as the API returns them: date_start/date_stop are the Pacific account day,
numbers stay strings, and actions stays the API's list. Refresh is 8 days (the last 7 plus the newest day) because lead actions
keep arriving after the day they belong to (docs/API.md).
"""
from datetime import date

from worker.sources import SOURCES
from worker.sync import Source

META = Source(
    name="meta",
    path="/v1/meta/insights",
    table="raw_meta_insights",
    on_conflict="date_start,account_id,campaign_id,adset_id",
    first_day=date(2024, 10, 1),  # docs/API.md: "Data starts on 2024-10-01"
    refresh_days=8,  # the day 7 days before data_through can still change: 8 days, not 7 (#87)
)
SOURCES[META.name] = META
