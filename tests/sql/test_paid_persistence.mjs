// No repo dependencies. PGLITE_MODULE points at an externally installed package.
// PR43_GRAIN_SQL must contain the exact prerequisite migration from PR #43.
import {readFile, readdir} from 'node:fs/promises';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
const {PGlite} = await import(process.env.PGLITE_MODULE);
const db = new PGlite();
let passed = 0;
async function test(name, fn) { await fn(); console.log(`ok ${++passed} - ${name}`); }
const migration = (await readdir('supabase/migrations')).find(x=>x.endsWith('_replace_paid_fact_window.sql'));
const sql = await readFile(`supabase/migrations/${migration}`, 'utf8');
await db.exec('create role anon; create role authenticated; create role service_role bypassrls;');
await db.exec(await readFile('supabase/migrations/20261002042403_create_marketing_schema.sql','utf8'));
await db.exec(await readFile('supabase/migrations/20261002070816_relax_raw_source_constraints.sql','utf8'));
await test('migration rejects missing PR43 prerequisite', async()=> {
  await assert.rejects(db.exec(sql), /PR #43/); await db.exec('rollback');
});
const prerequisite = await readFile(process.env.PR43_GRAIN_SQL, 'utf8');
assert.equal(createHash('sha256').update(prerequisite).digest('hex'),
  '59431468dded2d67446b91224c7a67571bd809824bb3e4b566e305a82007dfae', 'use the pinned, unchanged PR43 migration');
await db.exec(prerequisite);
await db.exec(sql);
const day = '2026-09-01';
function row(source='google_ads', updates={}) {
  return {analysis_date:day, channel:source==='lsa'?'google_lsa':source==='meta_ads'?'meta':'google_ads',
    source_platform:source, source_account_id:source==='lsa'?null:'account',
    campaign_id:source==='lsa'?null:'campaign', campaign_name:source==='lsa'?null:'Campaign',
    brand_classification:source==='lsa'?'not_applicable':'brand', impressions:source==='lsa'?0:10,
    clicks:source==='lsa'?0:2, spend_usd:'1.000001', reported_leads:source==='lsa'?'1':'0.125',
    unique_leads:0,calls:0,jobs:0,completed_jobs:0,revenue_usd:'0',
    synced_at:'2026-09-03T00:00:00Z',data_through:'2026-09-02',...updates};
}
async function rpc(source, rows, start=day,end='2026-09-02') {
  return (await db.query('select public.replace_paid_fact_window($1,$2,$3,$4::jsonb) n',
    [source,start,end,JSON.stringify(rows)])).rows[0].n;
}
async function all() { return (await db.query('select * from public.fact_marketing_daily order by source_platform,analysis_date,campaign_id,source_account_id')).rows; }
async function insert(rows) { await db.query('insert into public.fact_marketing_daily select * from jsonb_populate_recordset(null::public.fact_marketing_daily,$1)',[JSON.stringify(rows)]); }
await test('service_role can execute; exact monetary digits survive', async()=> {
  await db.exec('set role service_role');
  assert.equal(await rpc('google_ads',[row('google_ads',{spend_usd:'12345678901234567890.000001'})]),1);
  assert.equal((await db.query('select spend_usd::text amount from public.fact_marketing_daily')).rows[0].amount,'12345678901234567890.000001');
  await db.exec('reset role');
});
await test('disappearing campaign deleted; outside inclusive window preserved', async()=> {
  await rpc('google_ads',[row(),row('google_ads',{campaign_id:'gone'})]);
  await insert([row('google_ads',{analysis_date:'2026-08-31'}),row('google_ads',{analysis_date:'2026-09-03'})]);
  await rpc('google_ads',[row('google_ads',{analysis_date:'2026-09-02'})]);
  const rows = await all(); assert.equal(rows.length,3);
  assert.deepEqual(rows.map(r=>r.analysis_date.toISOString().slice(0,10)),['2026-08-31','2026-09-02','2026-09-03']);
});
await test('LSA and Calls collide on old grain but coexist; CRM and Meta preserved', async()=> {
  await rpc('lsa',[row('lsa')]); await rpc('meta_ads',[row('meta_ads')]);
  await insert([row('lsa',{source_platform:'call_tracking',calls:4,unique_leads:2,spend_usd:'0'}),
    row('lsa',{source_platform:'crm',jobs:3,revenue_usd:'123',spend_usd:'0'})]);
  const protectedBefore=(await all()).filter(r=>r.source_platform!=='lsa');
  await rpc('lsa',[row('lsa',{spend_usd:'0'})]);
  assert.deepEqual((await all()).filter(r=>r.source_platform!=='lsa'),protectedBefore);
});
await test('empty complete window deletes stale LSA only',async()=> {
  const before=(await all()).filter(r=>r.source_platform!=='lsa');
  assert.equal(await rpc('lsa',[]),0); assert.deepEqual(await all(),before);
});
await test('duplicate NULL grain aborts without modifying facts', async()=> {
  const before=await all(); await assert.rejects(rpc('lsa',[row('lsa'),row('lsa')]),/duplicate/);
  assert.deepEqual(await all(),before);
});
await test('distinct accounts are distinct keys',async()=> {
  assert.equal(await rpc('google_ads',[row(),row('google_ads',{source_account_id:'other'})]),2);
});
await test('invalid late brand rejects entire batch before writes',async()=> {
  const before=await all();
  for (const brand of [null,'unknown','not_applicable']) {
    await assert.rejects(rpc('google_ads',[row(),row('google_ads',{campaign_id:'bad',brand_classification:brand})]));
    assert.deepEqual(await all(),before);
  }
});
await test('invalid source, window, metrics, fields and scope abort',async()=> {
  const before=await all();
  for (const change of [{source_platform:'crm'},{channel:'meta'},{analysis_date:'2026-08-31'},
    {spend_usd:'NaN'},{spend_usd:'Infinity'},{spend_usd:'-1'},{clicks:null},{calls:1},
    {impressions:'9223372036854775808'},{data_through:'2026-10-01'},{campaign_id:{}},{extra:1}]) {
    await assert.rejects(rpc('google_ads',[row('google_ads',change)])); assert.deepEqual(await all(),before);
  }
  await assert.rejects(rpc('crm',[]));
  await assert.rejects(rpc('google_ads',[], '2026-09-02',day));
});
await test('insert failure after delete rolls back deleted and inserted rows',async()=> {
  await db.exec(`create function public.fail_test_insert() returns trigger language plpgsql as $$
    begin if new.campaign_id='explode' then raise exception 'injected write failure'; end if; return new; end $$;
    create trigger test_failure before insert on public.fact_marketing_daily for each row execute function public.fail_test_insert();`);
  const before=await all();
  await assert.rejects(rpc('google_ads',[row(),row('google_ads',{campaign_id:'explode'})]),/injected write failure/);
  assert.deepEqual(await all(),before);
  await db.exec('drop trigger test_failure on public.fact_marketing_daily; drop function public.fail_test_insert();');
});
await test('outer transaction rollback restores successful RPC',async()=> {
  const before=await all(); await db.exec('begin'); await rpc('google_ads',[]); await db.exec('rollback');
  assert.deepEqual(await all(),before);
});
await test('anon and authenticated cannot execute RPC',async()=> {
  for (const role of ['anon','authenticated']) {
    await db.exec(`set role ${role}`); await assert.rejects(rpc('google_ads',[]),/permission denied/); await db.exec('reset role');
  }
});
await test('function is invoker with empty search_path',async()=> {
  const r=(await db.query("select prosecdef,proconfig from pg_proc where oid='public.replace_paid_fact_window(text,date,date,jsonb)'::regprocedure")).rows[0];
  assert.equal(r.prosecdef,false); assert.deepEqual(r.proconfig,['search_path=""']);
});
await test('unsupported transaction isolation fails closed', async()=> {
  await db.exec('begin isolation level repeatable read');
  await assert.rejects(rpc('google_ads',[]),/READ COMMITTED/); await db.exec('rollback');
});
await test('independent raw Google/Meta/LSA reconciliation matches and detects drift', async()=> {
  await db.exec('truncate public.fact_marketing_daily');
  await db.exec(`insert into public.raw_google_ads_insights values
    ('2026-09-01','account','campaign','Campaign','group','Group',10,2,1000001,0.125);
    insert into public.raw_meta_insights values
    ('2026-09-01','2026-09-01','account','campaign','Campaign','set','Set','10','2','1.000001',
     '[{"action_type":"lead","value":"0.125"},{"action_type":"other","value":"99"}]');
    insert into public.raw_lsa_leads values
    ('charged','2026-09-02T04:59:00Z','category','PHONE_CALL','CHARGED',null,12.34),
    ('credited','2026-09-01T12:00:00Z','category','MESSAGE','CREDITED','2026-09-03T00:00:00Z',5),
    ('free','2026-09-01T12:00:00Z','category','MESSAGE','NOT_CHARGED',null,9);`);
  await rpc('google_ads',[row()]); await rpc('meta_ads',[row('meta_ads')]);
  await rpc('lsa',[row('lsa',{spend_usd:'12.34',reported_leads:'3'})]);
  const query=(await readFile('scripts/reconcile_paid_facts.sql','utf8'))
    .replaceAll(":'start_date'", "'2026-09-01'").replaceAll(":'end_date'", "'2026-09-02'");
  assert.equal((await db.query(query)).rows.length,0);
  await db.exec('update public.fact_marketing_daily set spend_usd=spend_usd+1');
  assert.deepEqual((await db.query(query)).rows.map(r=>r.source_platform),['google_ads','lsa','meta_ads']);
});
console.log(`PASS: ${passed} SQL integration tests`);
console.log((await db.query('select version()')).rows[0].version);
await db.close();
