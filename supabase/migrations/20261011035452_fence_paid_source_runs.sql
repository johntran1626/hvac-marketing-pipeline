-- Requires PR #43 and the unchanged reviewed replacement migration, in that order.
-- Newest begun source run wins. The token is acquired BEFORE snapshot acquisition.
begin;
create schema paid_sync_private;
revoke all on schema paid_sync_private from public, anon, authenticated;
grant usage on schema paid_sync_private to service_role;
-- Remove the unfenced REST endpoint, retaining its reviewed implementation privately.
alter function public.replace_paid_fact_window(text,date,date,jsonb) set schema paid_sync_private;

create table paid_sync_private.paid_source_runs (
  source_platform text primary key check (source_platform in ('google_ads','meta_ads','lsa')),
  generation bigint not null, started_at timestamptz not null,
  planned_windows jsonb, committed_through date, target_through date,
  status text not null check (status in ('running','ok','failed'))
);
create table paid_sync_private.paid_window_receipts (
  source_platform text not null, generation bigint not null,
  start_date date not null, end_date date not null,
  snapshot_id text not null, raw_snapshot jsonb not null, fact_batch jsonb,
  reconciled_at timestamptz,
  primary key (source_platform,generation,start_date,end_date)
);
alter table paid_sync_private.paid_source_runs enable row level security;
alter table paid_sync_private.paid_window_receipts enable row level security;
revoke all on paid_sync_private.paid_source_runs, paid_sync_private.paid_window_receipts from public, anon, authenticated;
grant select,insert,update on paid_sync_private.paid_source_runs, paid_sync_private.paid_window_receipts to service_role;
-- PR #43's sync_state is server-only. Explicit privileges for invoker functions.
grant select,insert,update on public.sync_state to service_role;

create function paid_sync_private.lock_paid_source(p_source text) returns void
language plpgsql volatile security invoker set search_path='' as $$
begin
  if p_source is null or p_source not in ('google_ads','meta_ads','lsa') then raise exception 'invalid paid source'; end if;
  if current_setting('transaction_isolation') <> 'read committed' then raise exception 'READ COMMITTED required'; end if;
  perform pg_advisory_xact_lock(30,case p_source when 'google_ads' then 1 when 'meta_ads' then 2 else 3 end);
end $$;

create function public.begin_paid_source_run(p_source text) returns jsonb
language plpgsql volatile security invoker set search_path='' as $$
declare r paid_sync_private.paid_source_runs;
begin
  perform paid_sync_private.lock_paid_source(p_source);
  insert into paid_sync_private.paid_source_runs(source_platform,generation,started_at,status)
  values(p_source,1,clock_timestamp(),'running')
  on conflict(source_platform) do update set generation=paid_sync_private.paid_source_runs.generation+1,
    started_at=clock_timestamp(),status='running',planned_windows=null,target_through=null
  returning * into r;
  perform set_config('hvac.paid_source',p_source,true);
  perform set_config('hvac.paid_generation',r.generation::text,true);
  insert into public.sync_state(source,status,last_run_started_at,last_error)
    values(case p_source when 'meta_ads' then 'meta' else p_source end,'running',r.started_at,null)
    on conflict(source) do update set status='running',last_run_started_at=r.started_at,last_error=null;
  return jsonb_build_object('generation',r.generation,'started_at',r.started_at,'committed_through',r.committed_through);
end $$;

create function paid_sync_private.require_paid_run(p_source text,p_generation bigint) returns paid_sync_private.paid_source_runs
language plpgsql volatile security invoker set search_path='' as $$
declare r paid_sync_private.paid_source_runs;
begin
  perform paid_sync_private.lock_paid_source(p_source);
  select * into r from paid_sync_private.paid_source_runs where source_platform=p_source;
  if r.generation is distinct from p_generation or r.status is distinct from 'running' then
    raise exception 'stale or inactive source run';
  end if;
  perform set_config('hvac.paid_source',p_source,true);
  perform set_config('hvac.paid_generation',p_generation::text,true);
  return r;
end $$;

create function public.plan_paid_source_run(p_source text,p_generation bigint,p_through date,p_windows jsonb) returns boolean
language plpgsql volatile security invoker set search_path='' as $$
declare r paid_sync_private.paid_source_runs; w jsonb; expected date; a date; b date;
begin
  r := paid_sync_private.require_paid_run(p_source,p_generation);
  if r.planned_windows is not null or p_through is null or not isfinite(p_through)
     or p_through < date '2024-10-01' or p_through < r.committed_through
     or p_windows is null or jsonb_typeof(p_windows)<>'array' or jsonb_array_length(p_windows)=0 then
    raise exception 'invalid source plan';
  end if;
  expected := greatest(date '2024-10-01',coalesce(r.committed_through,date '2024-10-01') - case p_source when 'lsa' then 30 else 7 end);
  for w in select value from jsonb_array_elements(p_windows) loop
    a := (w->>'start')::date; b := (w->>'end')::date;
    if a is distinct from expected or b is distinct from least(a+30,p_through) then raise exception 'incomplete source plan'; end if;
    expected := b+1;
  end loop;
  if expected is distinct from p_through+1 then raise exception 'incomplete source plan'; end if;
  update paid_sync_private.paid_source_runs set planned_windows=p_windows,target_through=p_through where source_platform=p_source;
  return true;
end $$;

-- Run-scoped durable staging; never mixed with historical raw upserts.
-- One-second upper clock tolerance accommodates millisecond DB clocks. The
-- lower bound remains the run start; the durable generation is the write fence.
create function public.stage_paid_source_window(
  p_source text,p_generation bigint,p_start date,p_end date,p_snapshot_id text,
  p_acquired_at timestamptz,p_raw jsonb
) returns integer
language plpgsql volatile security invoker set search_path='' as $$
declare r paid_sync_private.paid_source_runs; old paid_sync_private.paid_window_receipts;
begin
  r := paid_sync_private.require_paid_run(p_source,p_generation);
  if r.planned_windows is null or not (r.planned_windows @> jsonb_build_array(jsonb_build_object('start',p_start,'end',p_end)))
     or p_snapshot_id is null or btrim(p_snapshot_id)='' or p_acquired_at is null
     or p_acquired_at < r.started_at or p_acquired_at > clock_timestamp() + interval '1 second'
     or p_raw is null or jsonb_typeof(p_raw)<>'array' then raise exception 'missing complete current snapshot'; end if;
  select * into old from paid_sync_private.paid_window_receipts where source_platform=p_source and generation=p_generation and start_date=p_start and end_date=p_end;
  if found then
    if old.raw_snapshot is distinct from p_raw or old.snapshot_id is distinct from p_snapshot_id then raise exception 'staged snapshot differs'; end if;
  else
    insert into paid_sync_private.paid_window_receipts values(p_source,p_generation,p_start,p_end,p_snapshot_id,p_raw,null,null);
  end if;
  return jsonb_array_length(p_raw);
end $$;

create function public.persist_paid_source_window(
  p_source text,p_generation bigint,p_start date,p_end date,p_snapshot_id text,
  p_acquired_at timestamptz,p_raw jsonb,p_facts jsonb
) returns integer
language plpgsql volatile security invoker set search_path='' as $$
declare r paid_sync_private.paid_source_runs; old paid_sync_private.paid_window_receipts; raw_table text; date_expression text;
  item jsonb; raw_fields text[]; written integer; invalid boolean;
begin
  r := paid_sync_private.require_paid_run(p_source,p_generation);
  if r.planned_windows is null or not (r.planned_windows @> jsonb_build_array(jsonb_build_object('start',p_start,'end',p_end)))
     or p_snapshot_id is null or btrim(p_snapshot_id)='' or p_acquired_at is null
     or p_acquired_at < r.started_at or p_acquired_at > clock_timestamp() + interval '1 second'
     or p_raw is null or jsonb_typeof(p_raw)<>'array' then raise exception 'missing complete current snapshot'; end if;
  select * into old from paid_sync_private.paid_window_receipts where source_platform=p_source and generation=p_generation and start_date=p_start and end_date=p_end;
  if not found or old.raw_snapshot is distinct from p_raw or old.snapshot_id is distinct from p_snapshot_id then
    raise exception 'durable snapshot missing or changed';
  end if;
  if old.reconciled_at is not null then
    if old.fact_batch is distinct from p_facts then
      raise exception 'window replay differs from committed snapshot';
    end if;
    return jsonb_array_length(p_facts); -- idempotent lost-ack replay, same active run only
  end if;
  raw_table := case p_source when 'google_ads' then 'raw_google_ads_insights' when 'meta_ads' then 'raw_meta_insights' else 'raw_lsa_leads' end;
  date_expression := case p_source when 'google_ads' then 'date' when 'meta_ads' then 'date_start' else '(lead_created_at at time zone ''America/Chicago'')::date' end;
  select array_agg(attname::text order by attname::text) into raw_fields from pg_attribute
    where attrelid=('public.'||raw_table)::regclass and attnum>0 and not attisdropped;
  for item in select value from jsonb_array_elements(p_raw) loop
    if jsonb_typeof(item)<>'object' or (select array_agg(key order by key) from jsonb_object_keys(item) key) is distinct from raw_fields then
      raise exception 'invalid raw record fields; no fields may be silently discarded';
    end if;
  end loop;
  execute format('select exists(select 1 from jsonb_populate_recordset(null::public.%I,$1) where %s is null or %s not between $2 and $3)',raw_table,date_expression,date_expression)
    into invalid using p_raw,p_start,p_end;
  if invalid then raise exception 'raw record outside window'; end if;
  -- Replace, never merge with historical upserts. Disappeared records are removed.
  execute format('delete from public.%I where %s between $1 and $2',raw_table,date_expression) using p_start,p_end;
  execute format('insert into public.%I select * from jsonb_populate_recordset(null::public.%I,$1)',raw_table,raw_table) using p_raw;
  written := paid_sync_private.replace_paid_fact_window(p_source,p_start,p_end,p_facts);
  -- Independent SQL expectations preserve reporting_day/account/campaign/brand and exact NUMERIC.
  if exists (
    with raw_rows as (
      select date as reporting_day,customer_id as account,campaign_id as campaign,campaign_name as name,
        case when campaign_id='20814455901' then 'brand' when campaign_id in ('20814455917','20814455930','20814455948') then 'non_brand' end as brand,
        impressions::numeric impressions,clicks::numeric clicks,cost_micros::numeric/1000000 spend,conversions as leads
      from public.raw_google_ads_insights where p_source='google_ads' and date between p_start and p_end
      union all
      select date_start,account_id,campaign_id,campaign_name,
        case when campaign_id in ('120208841937650100','120208841937650200') then 'non_brand' end,
        impressions::numeric,clicks::numeric,spend::numeric,
        coalesce((select sum((a->>'value')::numeric) from jsonb_array_elements(actions) a where a->>'action_type'='lead'),0)
      from public.raw_meta_insights where p_source='meta_ads' and date_start between p_start and p_end
      union all
      select (lead_created_at at time zone 'America/Chicago')::date,null,null,null,'not_applicable',0,0,
        case when charge_status='CHARGED' then cost_usd else 0 end,1
      from public.raw_lsa_leads where p_source='lsa' and (lead_created_at at time zone 'America/Chicago')::date between p_start and p_end
    ), expected as (
      select reporting_day,account,campaign,name,brand,sum(impressions) impressions,sum(clicks) clicks,sum(spend) spend,sum(leads) leads
      from raw_rows group by reporting_day,account,campaign,name,brand
    ), actual as (
      select analysis_date reporting_day,source_account_id account,campaign_id campaign,campaign_name name,brand_classification brand,
        impressions::numeric,clicks::numeric,spend_usd spend,reported_leads leads
      from public.fact_marketing_daily where source_platform=p_source and analysis_date between p_start and p_end
    )
    (select * from expected except all select * from actual) union all
    (select * from actual except all select * from expected)
  ) then raise exception 'independent raw/fact reconciliation failed'; end if;
  update paid_sync_private.paid_window_receipts set fact_batch=p_facts,reconciled_at=clock_timestamp()
    where source_platform=p_source and generation=p_generation and start_date=p_start and end_date=p_end;
  return written;
end $$;

create function public.finish_paid_source_run(p_source text,p_generation bigint) returns boolean
language plpgsql volatile security invoker set search_path='' as $$
declare r paid_sync_private.paid_source_runs;
begin
  r := paid_sync_private.require_paid_run(p_source,p_generation);
  if r.planned_windows is null or exists (
    select 1 from jsonb_array_elements(r.planned_windows) w where not exists (
      select 1 from paid_sync_private.paid_window_receipts x where x.source_platform=p_source and x.generation=p_generation
        and x.start_date=(w->>'start')::date and x.end_date=(w->>'end')::date and x.reconciled_at is not null
    )) then raise exception 'not all windows persisted and independently reconciled'; end if;
  update paid_sync_private.paid_source_runs set committed_through=target_through,status='ok' where source_platform=p_source;
  update public.sync_state set status='ok',last_success_at=clock_timestamp(),backfilled_through=r.target_through,
    window_start=null,window_end=null,cursor=null,last_error=null,updated_at=clock_timestamp()
    where source=case p_source when 'meta_ads' then 'meta' else p_source end;
  return true;
end $$;

create function public.fail_paid_source_run(p_source text,p_generation bigint) returns boolean
language plpgsql volatile security invoker set search_path='' as $$
begin
  perform paid_sync_private.require_paid_run(p_source,p_generation);
  update paid_sync_private.paid_source_runs set status='failed' where source_platform=p_source;
  update public.sync_state set status='failed',last_error='Paid source integration failed; no source-wide freshness published',updated_at=clock_timestamp()
    where source=case p_source when 'meta_ads' then 'meta' else p_source end;
  return true;
end $$;

revoke all on function paid_sync_private.lock_paid_source(text), paid_sync_private.require_paid_run(text,bigint) from public,anon,authenticated;
grant execute on function paid_sync_private.lock_paid_source(text), paid_sync_private.require_paid_run(text,bigint) to service_role;
revoke all on function public.begin_paid_source_run(text),public.plan_paid_source_run(text,bigint,date,jsonb),
  public.stage_paid_source_window(text,bigint,date,date,text,timestamptz,jsonb),
  public.persist_paid_source_window(text,bigint,date,date,text,timestamptz,jsonb,jsonb),public.finish_paid_source_run(text,bigint),public.fail_paid_source_run(text,bigint)
  from public,anon,authenticated;
grant execute on function public.begin_paid_source_run(text),public.plan_paid_source_run(text,bigint,date,jsonb),
  public.stage_paid_source_window(text,bigint,date,date,text,timestamptz,jsonb),
  public.persist_paid_source_window(text,bigint,date,date,text,timestamptz,jsonb,jsonb),public.finish_paid_source_run(text,bigint),public.fail_paid_source_run(text,bigint)
  to service_role;
-- Old REST upserts and the private legacy function cannot bypass the fence.
-- This is defense against obsolete application writers, not a restriction on
-- a trusted database administrator who can alter triggers or role settings.
create function paid_sync_private.guard_paid_write() returns trigger
language plpgsql volatile security invoker set search_path='' as $$
declare sources text[]; source text; active paid_sync_private.paid_source_runs;
begin
  if tg_table_name='fact_marketing_daily' then
    sources := array[case when tg_op<>'INSERT' then old.source_platform end,
                     case when tg_op<>'DELETE' then new.source_platform end];
  elsif tg_table_name='sync_state' then
    sources := array[case when tg_op<>'INSERT' then case old.source when 'meta' then 'meta_ads' else old.source end end,
                     case when tg_op<>'DELETE' then case new.source when 'meta' then 'meta_ads' else new.source end end];
  else sources := array[tg_argv[0]];
  end if;
  foreach source in array sources loop
    if source in ('google_ads','meta_ads','lsa') then
      perform paid_sync_private.lock_paid_source(source);
      select * into active from paid_sync_private.paid_source_runs where source_platform=source;
      if current_setting('hvac.paid_source',true) is distinct from source
         or current_setting('hvac.paid_generation',true) is distinct from active.generation::text
         or active.generation is null
         or (tg_table_name<>'sync_state' and active.status<>'running') then
        raise exception 'unfenced or stale paid-source write disabled';
      end if;
    end if;
  end loop;
  if tg_op='DELETE' then return old; else return new; end if;
end $$;
revoke all on function paid_sync_private.guard_paid_write() from public,anon,authenticated;
grant execute on function paid_sync_private.guard_paid_write() to service_role;
create trigger guard_paid_facts before insert or update or delete on public.fact_marketing_daily
  for each row execute function paid_sync_private.guard_paid_write();
create trigger guard_paid_state before insert or update or delete on public.sync_state
  for each row execute function paid_sync_private.guard_paid_write();
create trigger guard_paid_google_raw before insert or update or delete on public.raw_google_ads_insights
  for each row execute function paid_sync_private.guard_paid_write('google_ads');
create trigger guard_paid_meta_raw before insert or update or delete on public.raw_meta_insights
  for each row execute function paid_sync_private.guard_paid_write('meta_ads');
create trigger guard_paid_lsa_raw before insert or update or delete on public.raw_lsa_leads
  for each row execute function paid_sync_private.guard_paid_write('lsa');

commit;
