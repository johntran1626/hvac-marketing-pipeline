-- Requires PR #43's 20261008200100_fact_grain_by_source.sql, unchanged.
-- Fail closed rather than independently replacing the prerequisite migration.
begin;
do $$
begin
  if not exists (
    select 1 from pg_constraint c join pg_index i on i.indexrelid = c.conindid
    where c.conrelid = 'public.fact_marketing_daily'::regclass
      and c.conname = 'fact_marketing_daily_grain' and c.contype = 'u'
      and i.indnullsnotdistinct
      and (select array_agg(a.attname::text order by k.ordinality)
           from unnest(c.conkey) with ordinality k(attnum, ordinality)
           join pg_attribute a on a.attrelid=c.conrelid and a.attnum=k.attnum)
          = array['analysis_date','channel','source_platform','source_account_id',
                  'campaign_id','brand_classification']
  ) then
    raise exception 'PR #43 source-aware fact grain migration is required';
  end if;
end $$;

create function public.replace_paid_fact_window(
  p_source_platform text, p_start_date date, p_end_date date, p_rows jsonb
) returns integer
language plpgsql volatile security invoker
set search_path = ''
as $$
declare
  batch public.fact_marketing_daily[];
  r public.fact_marketing_daily;
  item jsonb;
  written integer;
  expected_channel text;
begin
  expected_channel := case p_source_platform when 'google_ads' then 'google_ads'
    when 'meta_ads' then 'meta' when 'lsa' then 'google_lsa' end;
  if expected_channel is null or p_start_date is null or p_end_date is null
     or not isfinite(p_start_date) or not isfinite(p_end_date)
     or p_end_date < p_start_date or p_end_date - p_start_date > 30
     or p_rows is null or jsonb_typeof(p_rows) <> 'array' then
    raise exception 'invalid source, inclusive window or batch';
  end if;
  -- Reject missing/extra fields and coercions of JSON objects into text.
  for item in select value from jsonb_array_elements(p_rows) loop
    if jsonb_typeof(item) <> 'object' or
      (select array_agg(key order by key) from jsonb_object_keys(item) key) <>
      (select array_agg(attname::text order by attname::text) from pg_attribute
       where attrelid='public.fact_marketing_daily'::regclass and attnum>0 and not attisdropped) then
      raise exception 'invalid fact row fields';
    end if;
    if exists (select 1 from jsonb_each(item) e where
       e.key in ('analysis_date','channel','source_platform','source_account_id',
                 'campaign_id','campaign_name','brand_classification','synced_at','data_through')
       and jsonb_typeof(e.value) not in ('string','null')) then
      raise exception 'invalid fact dimension type';
    end if;
  end loop;
  select coalesce(array_agg(x), array[]::public.fact_marketing_daily[])
    into batch from jsonb_populate_recordset(null::public.fact_marketing_daily, p_rows) x;
  -- Validate EVERY row in memory before DELETE/INSERT, including non-finite numerics.
  foreach r in array batch loop
    if r.analysis_date is null or r.analysis_date not between p_start_date and p_end_date
       or r.source_platform is distinct from p_source_platform
       or r.channel is distinct from expected_channel
       or r.brand_classification is null
       or r.brand_classification not in ('brand','non_brand','not_applicable')
       or r.data_through is distinct from p_end_date
       or r.synced_at is null or not isfinite(r.synced_at)
       or (r.source_account_id is not null and btrim(r.source_account_id)='')
       or (r.campaign_id is not null and btrim(r.campaign_id)='')
       or (r.campaign_name is not null and btrim(r.campaign_name)='')
       or r.impressions is null or r.impressions < 0 or r.clicks is null or r.clicks < 0
       or r.spend_usd is null or r.spend_usd < 0 or r.spend_usd::text in ('NaN','Infinity','-Infinity')
       or r.reported_leads is null or r.reported_leads < 0 or r.reported_leads::text in ('NaN','Infinity','-Infinity')
       or r.unique_leads is distinct from 0::bigint or r.calls is distinct from 0::bigint
       or r.jobs is distinct from 0::bigint or r.completed_jobs is distinct from 0::bigint
       or r.revenue_usd is distinct from 0::numeric then
      raise exception 'invalid fact row; entire window rejected';
    end if;
    if p_source_platform = 'lsa' then
      if r.source_account_id is not null or r.campaign_id is not null or r.campaign_name is not null
         or r.brand_classification <> 'not_applicable' or r.impressions <> 0 or r.clicks <> 0
         or r.reported_leads < 1 or trunc(r.reported_leads) <> r.reported_leads then
        raise exception 'invalid LSA dimensions/metrics';
      end if;
    elsif r.source_account_id is null or r.campaign_id is null or r.brand_classification='not_applicable' then
      raise exception 'paid campaign requires account, campaign and resolved brand';
    end if;
  end loop;
  if exists (select 1 from unnest(batch) x group by analysis_date, channel,
      source_platform, source_account_id, campaign_id, brand_classification having count(*) > 1) then
    raise exception 'duplicate fact grain';
  end if;
  -- All overlapping windows for a source share one transaction-scoped lock.
  -- READ COMMITTED (PostgREST default) sees the previous writer after waiting.
  if current_setting('transaction_isolation') <> 'read committed' then
    raise exception 'replacement requires READ COMMITTED isolation';
  end if;
  perform pg_advisory_xact_lock(30, case p_source_platform
      when 'google_ads' then 1 when 'meta_ads' then 2 when 'lsa' then 3 end);
  delete from public.fact_marketing_daily
    where source_platform=p_source_platform and analysis_date between p_start_date and p_end_date;
  insert into public.fact_marketing_daily select * from unnest(batch);
  get diagnostics written = row_count;
  -- No exception handler: any error rolls back the entire RPC transaction.
  -- No sync_state success or global freshness inference from a single window.
  return written;
end $$;
revoke all on function public.replace_paid_fact_window(text,date,date,jsonb) from public, anon, authenticated;
grant execute on function public.replace_paid_fact_window(text,date,date,jsonb) to service_role;
commit;
