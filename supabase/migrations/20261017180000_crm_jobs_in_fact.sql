-- Project B: booked jobs by channel (Hamza's M2 feedback: "Put booked jobs by channel on the dashboard").
-- Adds CRM rows to rebuild_fact_marketing_daily(). Everything else is unchanged from
-- 20261011220000_rebuild_fact_marketing_daily.sql. No table or column changes: jobs, completed_jobs
-- and revenue_usd already exist in fact_marketing_daily (they were all 0 until now).
-- CRM rows never carry spend or leads, so jobs are never added to lead counts.

create or replace function public.rebuild_fact_marketing_daily()
returns table (source_platform text, fact_rows bigint)
language plpgsql
set search_path = public
as $$
begin
  delete from fact_marketing_daily f
  where f.source_platform in ('google_ads', 'meta_ads', 'lsa', 'call_tracking', 'crm');

  -- Google Ads: date is already the Central account day. Spend from micros, conversions = reported leads.
  insert into fact_marketing_daily
  select g.date, 'google_ads', 'google_ads', g.customer_id, g.campaign_id,
         (array_agg(g.campaign_name order by g.date desc))[1],
         case when g.campaign_id = '20814455901' then 'brand' else 'non_brand' end,
         sum(g.impressions), sum(g.clicks), sum(g.cost_micros) / 1000000.0, sum(g.conversions),
         0, 0, 0, 0, 0, now(),
         (select max(date) from raw_google_ads_insights)
  from raw_google_ads_insights g
  group by g.date, g.customer_id, g.campaign_id;

  -- Meta: date_start is the Pacific account day, kept as is (not shifted). Numbers arrive as strings.
  insert into fact_marketing_daily
  select m.date_start, 'meta', 'meta_ads', m.account_id, m.campaign_id,
         (array_agg(m.campaign_name order by m.date_start desc))[1],
         'non_brand',
         sum(m.impressions::bigint), sum(m.clicks::bigint), sum(m.spend::numeric),
         coalesce(sum((select sum((a->>'value')::numeric) from jsonb_array_elements(m.actions) a
                       where a->>'action_type' = 'lead')), 0),
         0, 0, 0, 0, 0, now(),
         (select max(date_start) from raw_meta_insights)
  from raw_meta_insights m
  group by m.date_start, m.account_id, m.campaign_id;

  -- LSA (Google Guaranteed): Central date of lead_created_at. Only CHARGED leads cost money.
  insert into fact_marketing_daily
  select (l.lead_created_at at time zone 'America/Chicago')::date, 'google_lsa', 'lsa', null, null, null,
         'not_applicable', 0, 0,
         coalesce(sum(l.cost_usd) filter (where l.charge_status = 'CHARGED'), 0), count(*),
         0, 0, 0, 0, 0, now(),
         (select max((lead_created_at at time zone 'America/Chicago')::date) from raw_lsa_leads)
  from raw_lsa_leads l
  group by 1;

  -- Calls: Central date of started_at, channel = the call's tracked source.
  insert into fact_marketing_daily
  select (c.started_at at time zone 'America/Chicago')::date, c.source, 'call_tracking', null, c.campaign_id, null,
         case when c.source = 'google_ads' and c.campaign_id = '20814455901' then 'brand'
              when c.source in ('google_ads', 'meta') then 'non_brand'
              else 'not_applicable' end,
         0, 0, 0, 0,
         count(*) filter (where c.first_time_caller and c.duration_sec >= 30),
         count(*), 0, 0, 0, now(),
         (select max((started_at at time zone 'America/Chicago')::date) from raw_calls)
  from raw_calls c
  group by 1, c.source, c.campaign_id;

  -- CRM jobs: Central date of created_at (schema/normalized-fact-table.md). Channel comes from the
  -- free-text lead_source, lower-cased and trimmed, using the team mapping in
  -- tests/fixtures/crm-source-map-proposed.json. Blank or unknown labels, and plain "google"
  -- (can't tell Ads, Guaranteed or Maps apart), stay 'unattributed'.
  -- Booked = any status except canceled. Completed = status completed. Revenue = completed jobs only.
  -- data_through uses updated_at: jobs change every day, and today's changes appear tomorrow (docs/API.md).
  insert into fact_marketing_daily
  select (j.created_at at time zone 'America/Chicago')::date, coalesce(m.channel, 'unattributed'), 'crm',
         null, null, null, 'not_applicable',
         0, 0, 0, 0, 0, 0,
         count(*) filter (where j.status <> 'canceled'),
         count(*) filter (where j.status = 'completed'),
         coalesce(sum(j.revenue_usd) filter (where j.status = 'completed'), 0),
         now(),
         (select max((updated_at at time zone 'America/Chicago')::date) from raw_crm_jobs)
  from raw_crm_jobs j
  left join (values
      ('builder', 'builder_hoa'),
      ('hoa', 'builder_hoa'),
      ('saw truck', 'direct'),
      ('truck', 'direct'),
      ('yard sign', 'direct'),
      ('customer', 'existing_customer'),
      ('existing', 'existing_customer'),
      ('existing customer', 'existing_customer'),
      ('repeat', 'existing_customer'),
      ('repeat customer', 'existing_customer'),
      ('returning', 'existing_customer'),
      ('gmb', 'gbp'),
      ('google maps', 'gbp'),
      ('maps', 'gbp'),
      ('google ad', 'google_ads'),
      ('google ads', 'google_ads'),
      ('google guaranteed', 'google_lsa'),
      ('google lsa', 'google_lsa'),
      ('google screened', 'google_lsa'),
      ('local services', 'google_lsa'),
      ('lsa', 'google_lsa'),
      ('maint plan', 'maintenance_plan'),
      ('maintenance plan', 'maintenance_plan'),
      ('plan', 'maintenance_plan'),
      ('plan member', 'maintenance_plan'),
      ('facebok', 'meta'),
      ('facebook', 'meta'),
      ('fb', 'meta'),
      ('fb ad', 'meta'),
      ('instagram', 'meta'),
      ('meta', 'meta'),
      ('nextdoor', 'nextdoor'),
      ('friend', 'referral'),
      ('neighbor', 'referral'),
      ('referral', 'referral'),
      ('referral - neighbor', 'referral'),
      ('?', 'unattributed'),
      ('ad', 'unattributed'),
      ('googel', 'unattributed'),
      ('google', 'unattributed'),
      ('google local', 'unattributed'),
      ('google reviews', 'unattributed'),
      ('google search', 'unattributed'),
      ('internet', 'unattributed'),
      ('online', 'unattributed'),
      ('reviews', 'unattributed'),
      ('site', 'website'),
      ('web', 'website'),
      ('web form', 'website'),
      ('webiste', 'website'),
      ('website', 'website'),
      ('yelp', 'yelp')
    ) as m(label, channel) on m.label = lower(btrim(j.lead_source))
  group by 1, 2;

  return query
    select f.source_platform, count(*) from fact_marketing_daily f group by 1 order by 1;
end;
$$;

-- Only the worker (secret key) may run it.
revoke all on function public.rebuild_fact_marketing_daily() from public, anon, authenticated;
grant execute on function public.rebuild_fact_marketing_daily() to service_role;
