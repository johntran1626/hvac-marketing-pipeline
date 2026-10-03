-- Fill fact_marketing_daily with LSA rows, one per Central day (Issue #11, so /health can read a row).
-- Run in Supabase: SQL Editor -> New query -> paste -> Run. Safe to run again: it updates instead of duplicating.
-- Rules from schema/normalized-fact-table.md:
--   analysis_date = lead_created_at converted from UTC to Central
--   spend_usd     = cost_usd of CHARGED leads only (CREDITED was refunded, NOT_CHARGED cost nothing)
--   reported_leads = every LSA lead row, including credited ones
-- Only LSA platform data is loaded so far. Impressions, clicks, unique_leads, calls and jobs stay 0
-- until the Google, Meta, calls and CRM tables are filled and normalized.
insert into public.fact_marketing_daily (
  analysis_date, channel, source_platform, source_account_id, campaign_id, campaign_name,
  brand_classification, impressions, clicks, spend_usd, reported_leads, unique_leads,
  calls, jobs, completed_jobs, revenue_usd, synced_at, data_through
)
select
  (lead_created_at at time zone 'America/Chicago')::date as analysis_date,
  'google_lsa', 'lsa', null, null, null,
  'not_applicable', 0, 0,
  coalesce(sum(cost_usd) filter (where charge_status = 'CHARGED'), 0),
  count(*), 0,
  0, 0, 0, 0,
  now(),
  max((lead_created_at at time zone 'America/Chicago')::date) over ()
from public.raw_lsa_leads
group by 1
on conflict on constraint fact_marketing_daily_grain do update set
  source_platform = excluded.source_platform,
  spend_usd       = excluded.spend_usd,
  reported_leads  = excluded.reported_leads,
  synced_at       = excluded.synced_at,
  data_through    = excluded.data_through;

-- Check: should show 633 days (days with at least one lead), 1,724 leads, $51,302.98 charged spend.
select count(*) as days, sum(reported_leads) as lsa_leads, sum(spend_usd) as charged_spend_usd,
       min(analysis_date) as first_day, max(analysis_date) as last_day
from public.fact_marketing_daily
where channel = 'google_lsa';
