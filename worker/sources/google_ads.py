"""Google Ads ad-group insights into raw_google_ads_insights (Issue #26).

level=ad_group matches the raw table's key (date, customer_id, campaign_id, ad_group_id).
Rows are stored exactly as the API returns them: date is the Central account day,
cost_micros stays in micros, conversions keep their decimals.
Refresh is 8 days (the last 7 plus the newest day) because conversions keep arriving after the day they belong to (docs/API.md).
"""
from datetime import date

from worker.sources import SOURCES
from worker.sync import Source

GOOGLE_ADS = Source(
    name="google_ads",
    path="/v1/google_ads/insights",
    table="raw_google_ads_insights",
    on_conflict="date,customer_id,campaign_id,ad_group_id",
    first_day=date(2024, 10, 1),  # docs/API.md: "Data starts on 2024-10-01"
    refresh_days=8,  # the day 7 days before data_through can still change: 8 days, not 7 (#87)
    params={"level": "ad_group"},
)
SOURCES[GOOGLE_ADS.name] = GOOGLE_ADS
