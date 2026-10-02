-- Keep raw source tables permissive so ingestion preserves source payloads.
-- Validation and business logic belong in downstream normalization.

alter table public.raw_google_ads_insights
  drop constraint if exists raw_google_ads_insights_impressions_check,
  drop constraint if exists raw_google_ads_insights_clicks_check,
  drop constraint if exists raw_google_ads_insights_cost_micros_check,
  drop constraint if exists raw_google_ads_insights_conversions_check;

alter table public.raw_meta_insights
  drop constraint if exists raw_meta_insights_check,
  drop constraint if exists raw_meta_insights_actions_check;

alter table public.raw_lsa_leads
  drop constraint if exists raw_lsa_leads_lead_type_check,
  drop constraint if exists raw_lsa_leads_charge_status_check,
  drop constraint if exists raw_lsa_leads_cost_usd_check,
  drop constraint if exists raw_lsa_leads_check;

alter table public.raw_calls
  drop constraint if exists raw_calls_duration_sec_check;

alter table public.raw_crm_jobs
  drop constraint if exists raw_crm_jobs_revenue_usd_check;
