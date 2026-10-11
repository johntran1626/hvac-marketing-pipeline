-- Independent read-only source/date reconciliation. Set these psql variables:
-- psql ... -v start_date=2026-09-01 -v end_date=2026-09-30 -f scripts/reconcile_paid_facts.sql
-- Raw inputs must be complete current versions for the SAME source/window.
-- Result contains discrepancies only. Empty output means matching metric totals,
-- not proof of loader coverage, brand correctness, or raw freshness.
with raw_totals as (
  select 'google_ads'::text source_platform, date analysis_date,
    sum(impressions)::numeric impressions, sum(clicks)::numeric clicks,
    sum(cost_micros)::numeric / 1000000 spend_usd, sum(conversions) reported_leads
  from public.raw_google_ads_insights
  where date between :'start_date'::date and :'end_date'::date group by date
  union all
  select 'meta_ads', date_start, sum(impressions::numeric), sum(clicks::numeric),
    sum(spend::numeric), sum(coalesce((select sum((a->>'value')::numeric)
      from jsonb_array_elements(actions) a where a->>'action_type'='lead'),0))
  from public.raw_meta_insights
  where date_start between :'start_date'::date and :'end_date'::date group by date_start
  union all
  select 'lsa', (lead_created_at at time zone 'America/Chicago')::date,
    0, 0, sum(case when charge_status='CHARGED' then cost_usd else 0 end), count(*)::numeric
  from public.raw_lsa_leads
  where (lead_created_at at time zone 'America/Chicago')::date
    between :'start_date'::date and :'end_date'::date
  group by (lead_created_at at time zone 'America/Chicago')::date
), fact_totals as (
  select source_platform, analysis_date, sum(impressions)::numeric impressions,
    sum(clicks)::numeric clicks, sum(spend_usd) spend_usd, sum(reported_leads) reported_leads
  from public.fact_marketing_daily
  where source_platform in ('google_ads','meta_ads','lsa')
    and analysis_date between :'start_date'::date and :'end_date'::date
  group by source_platform, analysis_date
)
select coalesce(r.source_platform,f.source_platform) source_platform,
  coalesce(r.analysis_date,f.analysis_date) analysis_date,
  r.impressions raw_impressions, f.impressions fact_impressions,
  r.clicks raw_clicks, f.clicks fact_clicks,
  r.spend_usd raw_spend_usd, f.spend_usd fact_spend_usd,
  r.reported_leads raw_reported_leads, f.reported_leads fact_reported_leads
from raw_totals r full join fact_totals f using(source_platform,analysis_date)
where r.source_platform is null or f.source_platform is null
   or r.impressions is distinct from f.impressions or r.clicks is distinct from f.clicks
   or r.spend_usd is distinct from f.spend_usd or r.reported_leads is distinct from f.reported_leads
order by 1,2;
