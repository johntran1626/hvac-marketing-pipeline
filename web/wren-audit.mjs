// Read-only local regression/reconciliation checks. No business fixtures or writes.
import env from '@next/env';
import {createClient} from '@supabase/supabase-js';
import ts from 'typescript';
import {readFileSync} from 'node:fs';
import assert from 'node:assert/strict';
env.loadEnvConfig(process.cwd());
const code=ts.transpile(readFileSync('lib/reporting-period.ts','utf8'),{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022});
const period=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
assert.equal(period.lastYear('2024-02-29'),'2023-02-28');
assert.equal(period.periodFor({range:'today'},[],new Date('2026-01-01T03:00:00Z')).start,'2025-12-31');
assert.deepEqual(period.monthsBetween('2025-12-31','2026-02-01'),['2025-12','2026-01','2026-02']);
assert.equal(period.periodFor({range:'wtd'},[],new Date('2026-10-18T18:00:00Z')).start,'2026-10-12');
const db=createClient(process.env.NEXT_PUBLIC_SUPABASE_URL,process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY,{auth:{persistSession:false}});
let rows=[];
for(let i=0;;i+=1000){const {data,error}=await db.from('fact_marketing_daily').select('analysis_date,channel,source_platform,brand_classification,campaign_id,spend_usd,reported_leads,unique_leads,calls,jobs').order('analysis_date').order('channel').order('source_platform').order('source_account_id').order('campaign_id').order('brand_classification').range(i,i+999);if(error)throw Error(error.message);rows.push(...data);if(data.length<1000)break;}
const ownership={spend_usd:['google_ads','meta_ads','lsa'],reported_leads:['google_ads','meta_ads','lsa'],unique_leads:['call_tracking'],calls:['call_tracking'],jobs:['crm']};
const sum=(r,m)=>{r=r.filter(x=>ownership[m].includes(x.source_platform));return !r.length||r.some(x=>x[m]===null)?null:r.reduce((a,x)=>a+Number(x[m]),0)};
const fmt=(v,m)=>v===null?'–':v.toLocaleString('en-US',m==='spend_usd'?{style:'currency',currency:'USD',maximumFractionDigits:2}:{maximumFractionDigits:2});
const report={rows:rows.length,earliest:rows[0]?.analysis_date,latest:rows.at(-1)?.analysis_date,presets:{},access:{},http:[],calendar:'PASS'};
const get=async path=>{const r=await fetch('http://127.0.0.1:3100'+path);assert.equal(r.status,200,path);report.http.push(path);return r.text()};
for(const range of Object.keys(period.presets)){
 const p=period.periodFor({range},rows.map(r=>r.analysis_date).sort());const selected=rows.filter(r=>period.inPeriod(r.analysis_date,p));const html=await get('/dashboard?range='+range);
 report.presets[range]={start:p.start,end:p.end,rows:selected.length};
 for(const m of Object.keys(ownership)){const expected=fmt(sum(selected,m),m);assert.ok(html.includes(expected),`${range}/${m} KPI`);report.presets[range][m]=expected;}
 for(const month of period.monthsBetween(p.start,p.end))for(const m of ['spend_usd','unique_leads']){const value=fmt(sum(selected.filter(r=>r.analysis_date.startsWith(month)),m),m);if(value!=='–')assert.ok(html.includes(`${month}: ${value}`),`${range}/${month}/${m} chart`);}
 for(const c of period.comparisons(p))for(const m of Object.keys(ownership))assert.ok(html.includes(fmt(sum(rows.filter(r=>period.inPeriod(r.analysis_date,c)),m),m)),`${range}/${c.label}/${m} comparison`);
}
for(const route of ['/dashboard/channels','/dashboard/data','/dashboard/alerts'])await get(route);
for(const channel of [...new Set(rows.map(r=>r.channel))]){const p=period.periodFor({range:'ytd'},[]);const selected=rows.filter(r=>period.inPeriod(r.analysis_date,p)&&r.channel===channel);const html=await get('/dashboard/channels?range=ytd&channel='+encodeURIComponent(channel)+'&metric=unique_leads');assert.ok(html.includes(fmt(sum(selected,'unique_leads'),'unique_leads')));assert.ok(html.includes('Cost per lead by channel and month'));}
const campaign=rows.find(r=>r.campaign_id)?.campaign_id;
if(campaign){const selected=rows.filter(r=>r.campaign_id===campaign);const html=await get('/dashboard/channels?range=observed&campaign='+encodeURIComponent(campaign)+'&metric=spend_usd');assert.ok(html.includes(fmt(sum(selected,'spend_usd'),'spend_usd')));}
for(const table of ['sync_state','raw_google_ads_insights','raw_meta_insights','raw_lsa_leads','raw_calls']){const {error,count}=await db.from(table).select('*',{head:true,count:'exact'}).limit(1);report.access[table]=error?{code:error.code}:{visibleCount:count};}
report.result='PASS: HTTP routes, all presets/KPIs/monthly charts/prior-year totals, channel and campaign filters reconcile to read-only facts';
console.log(JSON.stringify(report,null,2));
