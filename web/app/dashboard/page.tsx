import Link from 'next/link';
import { anomalies, CHANNEL_LABELS } from '@/lib/dashboard';
import { getDashboard, metricRows, metricNames, metricNotes, total, format, coverageNote, type Metric } from '@/lib/dashboard-view';
import { periodFor, monthsBetween, inPeriod, comparisons, matchingPrior, type Query } from '@/lib/reporting-period';
import PeriodSelect from './period-select';
import { monthly, RecordedChart } from './charts';
import { Freshness } from './shared';
import { CostPerLeadByChannel, insights, usd2 } from './tables';
export default async function Dashboard({searchParams}:{searchParams:Promise<Query>}) {
 const [d,q]=await Promise.all([getDashboard(),searchParams]);
 const p=periodFor(q,d.rows.map(r=>r.analysis_date).sort());
 const rows=d.rows.filter(r=>inPeriod(r.analysis_date,p));
 const months=monthsBetween(p.start,p.end);
 const context=`&range=${p.preset}`;
 const href=(metric:Metric)=>`/dashboard/channels?metric=${metric}${context}#analysis`;
 const spend=total(metricRows(rows,'spend_usd'),'spend_usd');
 // Alerts use all history for their 28-day baseline; count the ones that overlap the selected dates.
 const alerts=anomalies(d.rows).filter(a=>a.end>=p.start&&a.start<=p.end);
 const latest=alerts[0];
 const notes=insights(rows);
 return <><div className="page-heading"><div><h1>Your marketing, at a glance.</h1><p>{p.start} — {p.end}</p></div><PeriodSelect value={p.preset}/></div>
 {d.failed ? <div className="notice"><span className="status-dot"/><div><strong>Dashboard data unavailable</strong><p>The dashboard could not read its data. Check /health.</p></div></div> : <Freshness rows={d.rows} expected={d.expected} range={p.preset}/>}
 {alerts.length>0 && <Link className="overview-alert-indicator" href={`/dashboard/alerts?range=${p.preset}`}><span className="status-dot"/><strong>{alerts.length} tracking {alerts.length===1?'alert':'alerts'}{latest && `: ${CHANNEL_LABELS[latest.channel]} reported 0 leads ${latest.start} to ${latest.end} while spending ${usd2(latest.spend)}`}</strong><span>See alerts →</span></Link>}
 {notes.length>0 && <section className="panel insight-panel"><div><span className="eyebrow">WHAT THE NUMBERS SAY</span><ul className="insights">{notes.map(n=><li key={n}>{n}</li>)}</ul></div></section>}
 <section className="kpi-grid" aria-label="Marketing totals">{(Object.keys(metricNames) as Metric[]).map(metric=><Link className="kpi" href={href(metric)} key={metric}><span>{metricNames[metric]}</span><strong>{format(total(metricRows(rows,metric),metric),metric)}</strong><small>{metricNotes[metric]}</small><span className="kpi-link">Explore →</span></Link>)}</section>
 <section className="panel"><div className="panel-heading"><h2>Cost per lead by channel</h2></div><p>Cost per lead = spend ÷ unique phone leads (first-time callers on the line 30 seconds or more). Google Guaranteed spend counts charged leads only. Meta&apos;s lead forms don&apos;t ring a phone, so its booked jobs are shown next to its phone leads.</p><CostPerLeadByChannel rows={rows}/><Link className="text-link" href={`/dashboard/channels?range=${p.preset}#cost-per-lead`}>Cost per lead by month, brand split and jobs →</Link></section>
 <div className="charts-grid"><RecordedChart context={context} title="Ad spend by month" metric="spend_usd" points={monthly(rows,months,'spend_usd')} caption="Monthly totals · selected dates" insight={spend===null?undefined:`${format(spend,'spend_usd')} spent in the selected period.`}/><RecordedChart context={context} title="Unique phone leads by month" metric="unique_leads" points={monthly(rows,months,'unique_leads')} caption="Monthly totals · selected dates"/></div>
 <section className="panel"><h2>Same period last year</h2><p>Last year&apos;s matching dates (weeks line up Monday to Monday). The current month and week are still in progress.</p><div className="table-scroll"><table><thead><tr><th>Comparison / dates</th>{Object.values(metricNames).map(n=><th key={n}>{n}</th>)}</tr></thead><tbody>{comparisons(p).map(c=><tr key={c.label}><th>{c.label}<small>{c.start} — {c.end}</small></th>{(Object.keys(metricNames) as Metric[]).map(m=>{const old=total(metricRows(d.rows.filter(r=>inPeriod(r.analysis_date,c)),m),m);return <td key={m}>{format(old,m)}<small>{coverageNote(d.rows.filter(r=>inPeriod(r.analysis_date,c)),m,c.start,c.end)}</small></td>;})}</tr>)}</tbody></table></div><p>{(Object.keys(metricNames) as Metric[]).map(m=>{const matching=matchingPrior(p);const old=matching?total(metricRows(d.rows.filter(r=>inPeriod(r.analysis_date,matching)),m),m):null;const current=total(metricRows(rows,m),m);return <span className="difference" key={m}>{metricNames[m]}: {current!==null&&old!==null?`${current-old>=0?'+':''}${format(current-old,m)} vs last year`:'no comparison'}. </span>;})}</p></section>
 <p className="definition-note">Dates are Central, except Meta, which keeps its Pacific account day. <Link href={`/dashboard/data?range=${p.preset}#definitions`}>How each number is defined →</Link></p>
 </>;
}
