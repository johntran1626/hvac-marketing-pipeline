import Link from 'next/link';
import { getDashboard, metricRows, metricNames, total, format, coverageNote, type Metric } from '@/lib/dashboard-view';
import { periodFor, monthsBetween, inPeriod, comparisons, matchingPrior, type Query } from '@/lib/reporting-period';
import PeriodSelect from './period-select';
import { monthly, RecordedChart } from './charts';
import { deriveAlerts } from '@/lib/alerts';
export default async function Dashboard({searchParams}:{searchParams:Promise<Query>}) {
 const [d,q]=await Promise.all([getDashboard(),searchParams]);
 const p=periodFor(q,d.rows.map(r=>r.analysis_date).sort());
 const rows=d.rows.filter(r=>inPeriod(r.analysis_date,p));
 const months=monthsBetween(p.start,p.end);
 const context=`&range=${p.preset}`;
 const href=(metric:Metric)=>`/dashboard/channels?metric=${metric}${context}#analysis`;
 const spend=total(metricRows(rows,'spend_usd'),'spend_usd');
 const google=total(rows.filter(r=>r.source_platform==='google_ads'),'spend_usd');
 const openAlerts=deriveAlerts(rows,d.expected).filter(a=>a.status!=='resolved');
 return <><div className="page-heading"><div><h1>Your marketing, at a glance.</h1><p>{p.start} — {p.end} · observed records</p></div><PeriodSelect value={p.preset}/></div>
 <div className="definition-note">{d.failed?'Source unavailable. ':''}Central reporting dates · Monday week start · today and current periods are partial. Meta retains Pacific account dates. Coverage unverified. <Link href={`/dashboard/data?range=${p.preset}`}>Review evidence →</Link></div>
 <Link className="overview-alert-indicator" href={`/dashboard/alerts?range=${p.preset}`}><span className="status-dot"/><strong>{openAlerts.length} unresolved evidence {openAlerts.length===1?'alert':'alerts'}</strong><span>Review investigations →</span></Link>
 <section className="kpi-grid" aria-label="Observed marketing totals">{(Object.keys(metricNames) as Metric[]).map(metric=><Link className="kpi" href={href(metric)} key={metric}><span>{metricNames[metric]}</span><strong>{format(total(metricRows(rows,metric),metric),metric)}</strong><small>{metric==='reported_leads'?'Platform-defined; not unique people':'Observed only · coverage unverified'}</small><span className="kpi-link">Investigate →</span></Link>)}</section>
 <div className="charts-grid"><RecordedChart context={context} title="Recorded spend" metric="spend_usd" points={monthly(rows,months,'spend_usd')} caption="Monthly buckets · selected dates only" insight={spend===null?'Spend evidence is unavailable for this selection.':`${format(spend,'spend_usd')} recorded; reconcile source delivery before changing budget.`}/><RecordedChart context={context} title="Recorded unique phone leads" metric="unique_leads" points={monthly(rows,months,'unique_leads')} caption="Monthly buckets · selected dates only"/></div>
 <section className="panel insight-panel"><div><span className="eyebrow">ACTION TO INVESTIGATE</span><h2>{google!==null&&spend!==null&&spend>0?`Google Ads accounts for ${(google/spend*100).toFixed(1)}% of recorded spend`:'Verify spend coverage before allocating budget'}</h2><p>{format(google,'spend_usd')} Google Ads / {format(spend,'spend_usd')} recorded spend. Spend share does not measure return. Review conversion actions and matched phone attribution before reallocating budget.</p><Link className="text-link" href={`/dashboard/channels?channel=google_ads&metric=reported_leads${context}#analysis`}>Investigate Google Ads →</Link></div></section>
 <section className="panel"><h2>Prior-year evidence</h2><p>Calendar anniversary anchor (February 29 clamps to February 28); LY weeks use 52 weeks earlier, Monday through the same weekday. Full periods are reference totals, not like-for-like to-date comparisons. No coverage is certified. Differences below use matching calendar dates (WTD: 52 weeks earlier, same weekdays) and describe observed records, not performance trends.</p><div className="table-scroll"><table><thead><tr><th>Comparison / dates</th>{Object.values(metricNames).map(n=><th key={n}>{n}</th>)}</tr></thead><tbody>{comparisons(p).map(c=><tr key={c.label}><th>{c.label}<small>{c.start} — {c.end}</small></th>{(Object.keys(metricNames) as Metric[]).map(m=>{const old=total(metricRows(d.rows.filter(r=>inPeriod(r.analysis_date,c)),m),m);return <td key={m}>{format(old,m)}<small>{coverageNote(d.rows.filter(r=>inPeriod(r.analysis_date,c)),m,c.start,c.end)}</small></td>;})}</tr>)}</tbody></table></div><p>{(Object.keys(metricNames) as Metric[]).map(m=>{const matching=matchingPrior(p);const old=matching?total(metricRows(d.rows.filter(r=>inPeriod(r.analysis_date,matching)),m),m):null;const current=total(metricRows(rows,m),m);return <span className="difference" key={m}>{metricNames[m]}: {current!==null&&old!==null?`${format(current-old,m)} observed difference; coverage unverified`:'difference unavailable (missing or nonmatching evidence)'}. </span>;})}</p></section>
 </>;
}
