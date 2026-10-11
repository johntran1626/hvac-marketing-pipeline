process.on('uncaughtException', e => { console.error(e.message, e.where ?? '', e.position ?? ''); process.exit(1); });
// Offline only. Uses the already installed PGlite; no downloads or hosted DB access.
import { readFile, readdir } from 'node:fs/promises';
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {createInterface} from 'node:readline';
const {PGlite}=await import(process.env.PGLITE_MODULE);
const db=new PGlite(); let passed=0;
async function test(name, fn) {await fn(); console.log(`ok ${++passed} - ${name}`);}
await db.exec('create role anon; create role authenticated; create role service_role bypassrls;');
for (const file of (await readdir('supabase/migrations')).sort()) {
  if (file.endsWith('.sql')) await db.exec(await readFile(`supabase/migrations/${file}`,'utf8'));
}
const first='2024-10-01', last='2024-10-02';
const raw=(patch={})=>({date:first,customer_id:'account',campaign_id:'20814455901',campaign_name:'Brand',ad_group_id:'ad-group',ad_group_name:'Group',impressions:10,clicks:2,cost_micros:1000001,conversions:'0.125',...patch});
const fact=(patch={})=>({analysis_date:first,channel:'google_ads',source_platform:'google_ads',source_account_id:'account',campaign_id:'20814455901',campaign_name:'Brand',brand_classification:'brand',impressions:10,clicks:2,spend_usd:'1.000001',reported_leads:'0.125',unique_leads:0,calls:0,jobs:0,completed_jobs:0,revenue_usd:'0',synced_at:new Date().toISOString(),data_through:last,...patch});
const call=async(name,args)=> (await db.query(`select public.${name}(${args.map((_,i)=>'$'+(i+1)).join(',')}) result`,args)).rows[0].result;
async function begin(source='google_ads',through=last){
  const r=await call('begin_paid_source_run',[source]);
  await call('plan_paid_source_run',[source,r.generation,through,JSON.stringify([{start:first,end:through}])]);
  return {...r,source,end:through};
}
async function stage(run,rows,start=first,end=run.end,id='immutable-fixture',acquired=new Date().toISOString()){
  await call('stage_paid_source_window',[run.source,run.generation,start,end,id,acquired,JSON.stringify(rows)]);
  return {run,rows,start,end,id,acquired};
}
async function persist(s,facts){return call('persist_paid_source_window',[s.run.source,s.run.generation,s.start,s.end,s.id,s.acquired,JSON.stringify(s.rows),JSON.stringify(facts)]);}
const state=async()=> (await db.query("select source,status,backfilled_through,last_success_at from public.sync_state order by source")).rows;
const facts=async()=> (await db.query('select * from public.fact_marketing_daily order by source_platform,analysis_date,source_account_id,campaign_id')).rows;
const raws=async()=> (await db.query('select * from public.raw_google_ads_insights order by date,customer_id,campaign_id,ad_group_id')).rows;
await test('old public RPC is absent; invoker wrapper has no anonymous privileges', async()=>{
  assert.equal((await db.query("select to_regprocedure('public.replace_paid_fact_window(text,date,date,jsonb)') x")).rows[0].x,null);
  for(const role of ['anon','authenticated']){
    await db.exec(`set role ${role}`); await assert.rejects(call('begin_paid_source_run',['google_ads']),/permission denied/); await db.exec('reset role');
  }
});
await test('source generation fences snapshot acquired by an older worker',async()=>{
  const old=await begin(); const s=await stage(old,[raw()]);
  const newer=await begin(); const before=await facts();
  await assert.rejects(persist(s,[fact()]),/stale/); assert.deepEqual(await facts(),before);
  await assert.rejects(call('fail_paid_source_run',['google_ads',old.generation]),/stale/);
  assert.equal((await state())[0].status,'running');
  await persist(await stage(newer,[raw()]),[fact()]);
  await call('finish_paid_source_run',['google_ads',newer.generation]);
});
await test('raw replacement deletes disappearing rows rather than rereading upsert leftovers',async()=>{
  let r=await begin(); await persist(await stage(r,[raw(),raw({campaign_id:'20814455917',campaign_name:'Other'})]),[fact(),fact({campaign_id:'20814455917',campaign_name:'Other',brand_classification:'non_brand'})]);
  r=await begin(); await persist(await stage(r,[raw()]),[fact()]);
  assert.equal((await raws()).length,1); assert.equal((await facts()).length,1);
});
await test('changed raw records and fact mismatch roll back together, preserving success watermark',async()=>{
  const r=await begin(); const beforeRaw=await raws(),beforeFact=await facts(),beforeState=await state();
  const s=await stage(r,[raw({cost_micros:2000000})]);
  await assert.rejects(persist(s,[fact()]),/reconciliation/);
  assert.deepEqual(await raws(),beforeRaw);assert.deepEqual(await facts(),beforeFact);assert.deepEqual(await state(),beforeState);
  await assert.rejects(call('finish_paid_source_run',['google_ads',r.generation]),/not all windows/);
});
await test('snapshot older than run is rejected before staging',async()=>{
  const r=await begin(); await assert.rejects(stage(r,[raw()],first,last,'stale','2020-01-01T00:00:00Z'),/snapshot/);
});
await test('source/account/campaign reconciliation catches offsetting errors with equal daily totals',async()=>{
  const r=await begin(); const s=await stage(r,[raw(),raw({customer_id:'other'})]);
  const before=await facts();
  await assert.rejects(persist(s,[fact({spend_usd:'0'}),fact({source_account_id:'other',spend_usd:'2.000002'})]),/reconciliation/);
  assert.deepEqual(await facts(),before);
});
await test('lost acknowledgement replay is idempotent, conflicting or superseded replay fails',async()=>{
  const r=await begin();const s=await stage(r,[raw()]); const batch=[fact()];
  assert.equal(await persist(s,batch),1);const before=await facts();
  assert.equal(await persist(s,batch),1);assert.deepEqual(await facts(),before);
  await assert.rejects(persist(s,[fact({spend_usd:'9'})]),/replay differs/);
  await begin();await assert.rejects(persist(s,batch),/stale/);
});
await test('empty authoritative window removes raw and fact leftovers',async()=>{
  const r=await begin();assert.equal(await persist(await stage(r,[]),[]),0);
  assert.equal((await raws()).length,0); assert.equal((await facts()).length,0);
});
await test('LSA replacement preserves Calls, CRM, Meta and out-of-window rows',async()=>{
  await db.exec('set session_replication_role=replica'); // administrator-only fixture seed
  await db.query('insert into public.fact_marketing_daily select * from jsonb_populate_recordset(null::public.fact_marketing_daily,$1::jsonb)',[JSON.stringify([
    fact({source_platform:'call_tracking',source_account_id:null,campaign_id:null,channel:'google_lsa',brand_classification:'not_applicable'}),
    fact({source_platform:'crm'}),fact({source_platform:'meta_ads',channel:'meta'}),fact({analysis_date:'2024-09-30'})])]);
  await db.exec('set session_replication_role=origin');
  const before=await facts();const r=await begin('lsa');
  const lsa={lead_id:'test',lead_created_at:'2024-10-02T04:59:00Z',category:'category',lead_type:'PHONE_CALL',charge_status:'CREDITED',credited_at:'2024-10-03T00:00:00Z',cost_usd:'999.000001'};
  await persist(await stage(r,[lsa]),[fact({source_platform:'lsa',channel:'google_lsa',source_account_id:null,campaign_id:null,campaign_name:null,brand_classification:'not_applicable',impressions:0,clicks:0,spend_usd:'0',reported_leads:'1'})]);
  assert.deepEqual((await facts()).filter(x=>x.source_platform!=='lsa'),before);
});
await test('independent SQL catches brand misclassification and extra raw fields',async()=>{
  let r=await begin();let s=await stage(r,[raw()]);
  await assert.rejects(persist(s,[fact({brand_classification:'non_brand'})]),/reconciliation/);
  r=await begin();s=await stage(r,[raw({unexpected:'cannot discard'})]);
  await assert.rejects(persist(s,[fact()]),/fields/);
});
await test('every planned window must reconcile; overlapping later run fences the entire earlier source',async()=>{
  const r=await call('begin_paid_source_run',['google_ads']);r.source='google_ads';r.end='2024-11-02';
  await call('plan_paid_source_run',['google_ads',r.generation,r.end,JSON.stringify([{start:first,end:'2024-10-31'},{start:'2024-11-01',end:r.end}])]);
  await persist(await stage(r,[],first,'2024-10-31'),[]);
  await assert.rejects(call('finish_paid_source_run',['google_ads',r.generation]),/not all windows/);
  const later=await begin();await persist(await stage(later,[raw()]),[fact()]);
  await assert.rejects(stage(r,[],'2024-11-01',r.end),/stale/);
});
await test('service role can stage/persist/finish; source-wide success is written only on finish',async()=>{
  await db.exec('set role service_role');const r=await begin('meta_ads');
  const rawMeta={date_start:first,date_stop:first,account_id:'account',campaign_id:'120208841937650100',campaign_name:'Meta',adset_id:'set',adset_name:'Set',impressions:'10',clicks:'2',spend:'12345678901234567890.000001',actions:[{action_type:'lead',value:'0.125'}]};
  await persist(await stage(r,[rawMeta]),[fact({source_platform:'meta_ads',channel:'meta',campaign_id:'120208841937650100',campaign_name:'Meta',brand_classification:'non_brand',spend_usd:'12345678901234567890.000001'})]);
  assert.equal((await state()).find(s=>s.source==='meta').status,'running');
  await call('finish_paid_source_run',['meta_ads',r.generation]);
  assert.equal((await state()).find(s=>s.source==='meta').status,'ok');
  assert.equal((await db.query("select spend_usd::text amount from public.fact_marketing_daily where source_platform='meta_ads'")).rows[0].amount,'12345678901234567890.000001');
  await db.exec('reset role');
});
await test('legacy LSA SQL fails without writes',async()=>{
  const before=await facts();await assert.rejects(db.exec(await readFile('scripts/build_fact_lsa.sql','utf8')),/disabled/);assert.deepEqual(await facts(),before);
});
await test('legacy direct paid raw, fact and success writes are rejected',async()=>{
  const before=await facts(),beforeState=await state();
  await db.exec('set role service_role');
  await assert.rejects(db.exec("update public.fact_marketing_daily set spend_usd=9 where source_platform='meta_ads'"),/unfenced/);
  await assert.rejects(db.exec("update public.raw_meta_insights set spend='9'"),/unfenced/);
  await assert.rejects(db.exec("update public.sync_state set status='ok' where source='google_ads'"),/unfenced/);
  await db.exec('reset role');assert.deepEqual(await facts(),before);assert.deepEqual(await state(),beforeState);
});
await test('injected fact insert failure rolls back raw replacement and the fact delete',async()=>{
  const run=await begin();const snap=await stage(run,[raw()]);const beforeRaw=await raws(),before=await facts();
  await db.exec("create function paid_sync_private.fail_insert_test() returns trigger language plpgsql as $$ begin raise exception 'injected insert failure'; end $$; create trigger fail_insert_test before insert on public.fact_marketing_daily for each row execute function paid_sync_private.fail_insert_test();");
  await assert.rejects(persist(snap,[fact()]),/injected insert failure/);
  assert.deepEqual(await raws(),beforeRaw);assert.deepEqual(await facts(),before);
  await db.exec('drop trigger fail_insert_test on public.fact_marketing_daily; drop function paid_sync_private.fail_insert_test();');
});
await test('outer rollback removes stage, facts and success publication together',async()=>{
  const before=await facts(),beforeState=await state();
  await db.exec('begin');const run=await begin();await persist(await stage(run,[raw()]),[fact()]);
  await call('finish_paid_source_run',['google_ads',run.generation]);await db.exec('rollback');
  assert.deepEqual(await facts(),before);assert.deepEqual(await state(),beforeState);
});
await test('actual Python orchestrator persists Google, Meta and LSA through real local SQL',async()=>{
  const order={
    begin_paid_source_run:['p_source'],
    plan_paid_source_run:['p_source','p_generation','p_through','p_windows'],
    stage_paid_source_window:['p_source','p_generation','p_start','p_end','p_snapshot_id','p_acquired_at','p_raw'],
    persist_paid_source_window:['p_source','p_generation','p_start','p_end','p_snapshot_id','p_acquired_at','p_raw','p_facts'],
    finish_paid_source_run:['p_source','p_generation'],fail_paid_source_run:['p_source','p_generation']
  };
  await db.exec('set role service_role');
  const child=spawn('python3',['-m','worker.tests.paid_sql_bridge'],{stdio:['pipe','pipe','pipe']});
  let stderr='';child.stderr.on('data',chunk=>stderr+=chunk);
  const done=new Promise((resolve,reject)=>{child.on('exit',code=>resolve(code));child.on('error',reject);});
  for await(const line of createInterface({input:child.stdout})){
    const request=JSON.parse(line);assert.ok(order[request.name]);
    const args=order[request.name].map(key=>['p_raw','p_facts','p_windows'].includes(key)?request.params[key]:JSON.parse(request.params[key]));
    try {child.stdin.write(JSON.stringify({result:await call(request.name,args)})+'\n');}
    catch(error){child.stdin.write(JSON.stringify({error:request.name+': '+error.message})+'\n');}
  }
  assert.equal(await done,0,stderr);
  assert.equal((await state()).filter(s=>['google_ads','meta','lsa'].includes(s.source)&&s.status==='ok').length,3);
  assert.equal((await db.query("select reported_leads::text amount from public.fact_marketing_daily where source_platform='google_ads' and source_account_id='account' and analysis_date='2024-10-01'")).rows[0].amount,'0.123456789012345678901');
  assert.equal((await db.query("select spend_usd::text amount from public.fact_marketing_daily where source_platform='lsa'")).rows[0].amount,'12.345678901');
  await db.exec('reset role');
});
console.log(`PASS: ${passed} fenced SQL integration tests`);await db.close();
