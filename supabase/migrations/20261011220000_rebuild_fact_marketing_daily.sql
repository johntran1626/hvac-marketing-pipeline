-- Project B Milestone 2 (Issues #30, #31, #33, #34)
-- Rebuild fact_marketing_daily from the raw tables, one call, all or nothing.
-- Rules: schema/normalized-fact-table.md. Each source writes its own rows (grain from #43);
-- the dashboard sums them by channel. CRM jobs/revenue are not in here yet (#31 attribution).
--
-- Brand is by campaign id, never name: Google 20814455901 = brand, other Google = non_brand,
-- Meta = non_brand, everything else = not_applicable.
-- Unique lead (agreed for M2, same as the M1 memo): first_time_caller and duration_sec >= 30.

create or replace function public.rebuild_fact_marketing_daily()
returns table (source_platform text, fact_rows bigint)
language plpgsql
set search_path = public
as $$
begin
  delete from fact_marketing_daily f
  where f.source_platform in ('google_ads', 'meta_ads', 'lsa', 'call_tracking');

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

  return query
    select f.source_platform, count(*) from fact_marketing_daily f group by 1 order by 1;
end;
$$;

-- Only the worker (secret key) may run it.
revoke all on function public.rebuild_fact_marketing_daily() from public, anon, authenticated;
grant execute on function public.rebuild_fact_marketing_daily() to service_role;
