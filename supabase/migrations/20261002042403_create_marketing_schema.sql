-- Project B Milestone 1
-- Raw source tables + normalized daily marketing fact table.

create table if not exists public.raw_google_ads_insights (
  date date not null,
  customer_id text not null,
  campaign_id text not null,
  campaign_name text not null,
  ad_group_id text not null,
  ad_group_name text not null,
  impressions bigint not null,
  clicks bigint not null,
  cost_micros bigint not null,
  conversions numeric not null,
  primary key (date, customer_id, campaign_id, ad_group_id),
  check (impressions >= 0),
  check (clicks >= 0),
  check (cost_micros >= 0),
  check (conversions >= 0)
);

create table if not exists public.raw_meta_insights (
  date_start date not null,
  date_stop date not null,
  account_id text not null,
  campaign_id text not null,
  campaign_name text not null,
  adset_id text not null,
  adset_name text not null,
  impressions text not null,
  clicks text not null,
  spend text not null,
  actions jsonb not null,
  primary key (date_start, account_id, campaign_id, adset_id),
  check (date_start = date_stop),
  check (jsonb_typeof(actions) = 'array')
);

create table if not exists public.raw_lsa_leads (
  lead_id text primary key,
  lead_created_at timestamptz not null,
  category text not null,
  lead_type text not null,
  charge_status text not null,
  credited_at timestamptz,
  cost_usd numeric not null,
  check (lead_type in ('PHONE_CALL', 'MESSAGE')),
  check (charge_status in ('CHARGED', 'CREDITED', 'NOT_CHARGED')),
  check (cost_usd >= 0),
  check (
    (charge_status = 'CREDITED' and credited_at is not null)
    or
    (charge_status <> 'CREDITED' and credited_at is null)
  )
);

create table if not exists public.raw_calls (
  call_id text primary key,
  started_at timestamptz not null,
  duration_sec integer not null,
  tracking_number text not null,
  source text not null,
  campaign_id text,
  caller_hash text not null,
  first_time_caller boolean not null,
  check (duration_sec >= 0)
);

create table if not exists public.raw_crm_jobs (
  job_id text primary key,
  customer_id text not null,
  created_at timestamptz not null,
  updated_at timestamptz not null,
  lead_source text,
  job_type text not null,
  status text not null,
  revenue_usd numeric,
  zip text not null,
  check (revenue_usd is null or revenue_usd >= 0)
);

create table if not exists public.fact_marketing_daily (
  analysis_date date not null,
  channel text not null,
  source_platform text not null,
  source_account_id text,
  campaign_id text,
  campaign_name text,
  brand_classification text not null,
  impressions bigint not null,
  clicks bigint not null,
  spend_usd numeric not null,
  reported_leads numeric not null,
  unique_leads bigint not null,
  calls bigint not null,
  jobs bigint not null,
  completed_jobs bigint not null,
  revenue_usd numeric not null,
  synced_at timestamptz not null,
  data_through date not null,

  constraint fact_marketing_daily_grain
    unique nulls not distinct
      (analysis_date, channel, campaign_id, brand_classification),

  check (brand_classification in ('brand', 'non_brand', 'not_applicable')),
  check (impressions >= 0),
  check (clicks >= 0),
  check (spend_usd >= 0),
  check (reported_leads >= 0),
  check (unique_leads >= 0),
  check (calls >= 0),
  check (jobs >= 0),
  check (completed_jobs >= 0),
  check (revenue_usd >= 0),
  check (completed_jobs <= jobs)
);

-- Supabase Data API access control.
-- Raw source tables stay server-side only.
alter table public.raw_google_ads_insights enable row level security;
alter table public.raw_meta_insights enable row level security;
alter table public.raw_lsa_leads enable row level security;
alter table public.raw_calls enable row level security;
alter table public.raw_crm_jobs enable row level security;
alter table public.fact_marketing_daily enable row level security;

revoke all on public.raw_google_ads_insights from anon, authenticated, public;
revoke all on public.raw_meta_insights from anon, authenticated, public;
revoke all on public.raw_lsa_leads from anon, authenticated, public;
revoke all on public.raw_calls from anon, authenticated, public;
revoke all on public.raw_crm_jobs from anon, authenticated, public;

grant select, insert, update, delete on public.raw_google_ads_insights to service_role;
grant select, insert, update, delete on public.raw_meta_insights to service_role;
grant select, insert, update, delete on public.raw_lsa_leads to service_role;
grant select, insert, update, delete on public.raw_calls to service_role;
grant select, insert, update, delete on public.raw_crm_jobs to service_role;

revoke all on public.fact_marketing_daily from anon, authenticated, public;
grant select on public.fact_marketing_daily to anon;
grant select, insert, update, delete on public.fact_marketing_daily to service_role;

create policy "public read fact_marketing_daily"
  on public.fact_marketing_daily
  for select
  to anon
  using (true);
