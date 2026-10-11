-- Evidence for Issue #26: row count, date range and duplicate-key check for the Google Ads load.
-- Run in Supabase: SQL Editor -> New query -> paste -> Run.
-- date is the Central account day as the API returns it.
select
  count(*)                                                    as row_count,
  count(distinct (date, customer_id, campaign_id, ad_group_id)) as distinct_keys,
  min(date)                                                   as first_day,
  max(date)                                                   as last_day,
  count(distinct campaign_id)                                 as campaigns,
  count(distinct ad_group_id)                                 as ad_groups
from public.raw_google_ads_insights;
