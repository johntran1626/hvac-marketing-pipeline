-- Evidence for Issue #8: row count and date range of the hand backfill.
-- Run in Supabase: SQL Editor -> New query -> paste -> Run.
-- Dates are shown in UTC (as stored) and in Central time (how the API filters).
select
  count(*)                                              as row_count,
  count(distinct lead_id)                               as distinct_lead_ids,
  min(lead_created_at)                                  as first_lead_utc,
  max(lead_created_at)                                  as last_lead_utc,
  min((lead_created_at at time zone 'America/Chicago')::date) as first_day_central,
  max((lead_created_at at time zone 'America/Chicago')::date) as last_day_central
from public.raw_lsa_leads;
