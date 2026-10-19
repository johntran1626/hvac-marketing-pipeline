import Link from 'next/link';
import { anomalies, CHANNEL_LABELS } from '@/lib/dashboard';
import { getDashboard, metricRows, metricNames, metricNotes, total, format, type Metric } from '@/lib/dashboard-view';
import { periodFor, inPeriod, type Query } from '@/lib/reporting-period';
import PeriodSelect from './period-select';
import { Freshness } from './shared';
import { usd2 } from './tables';
import { ChannelCards, CplLines, JobsBars, YoyChart, last12, lastFullMonth, monthInsights, monthName } from './story';
export default async function Dashboard({searchParams}:{searchParams:Promise<Query>}) {
 const [d,q]=await Promise.all([getDashboard(),searchParams]);
 const p=periodFor(q,d.rows.map(r=>r.analysis_date).sort());
 const rows=d.rows.filter(r=>inPeriod(r.analysis_date,p));
 const href=(metric:Metric)=>`/dashboard/channels?metric=${metric}&range=${p.preset}#analysis`;
 // The story is about the last full month and the 12 months up to it, whatever period the cards show.
 const month=lastFullMonth(d.rows);
 const months=month?last12(month):[];
 const notes=month?monthInsights(d.rows,month):[];
 const alerts=anomalies(d.rows).filter(a=>a.end>=p.start&&a.start<=p.end);
 const latest=alerts[0];
 return <><div className="page-heading"><div><h1>Your marketing, at a glance.</h1>{month&&<p>What happened in {monthName(month)}, and the 12 months before it.</p>}</div></div>
 {d.failed ? <div className="notice"><span className="status-dot"/><div><strong>Dashboard data unavailable</strong><p>The dashboard could not read its data. Check /health.</p></div></div> : <Freshness rows={d.rows} expected={d.expected} range={p.preset} compact/>}
 {notes.length>0 && <section className="panel insight-panel"><div><span className="eyebrow">{month?monthName(month).toUpperCase():''} AT A GLANCE</span><ul className="insights">{notes.map(n=><li key={n}>{n}</li>)}</ul></div></section>}
 {latest && <Link className="overview-alert-indicator" href={`/dashboard/alerts?range=${p.preset}`}><span className="status-dot"/><strong>Tracking alert: {CHANNEL_LABELS[latest.channel]} reported 0 leads from {latest.start} to {latest.end} while spending {usd2(latest.spend)}. Check its lead tracking.</strong><span>{alerts.length>1?`All ${alerts.length} alerts →`:'Details →'}</span></Link>}
 <div className="charts-grid"><YoyChart title="Booked jobs, this year vs last year" rows={d.rows} months={months} pick={t=>t.jobs} owner="jobs"/><YoyChart title="New callers, this year vs last year" rows={d.rows} months={months} pick={t=>t.unique} owner="unique"/></div>
 <ChannelCards rows={d.rows} months={months}/>
 <div className="charts-grid"><CplLines rows={d.rows} months={months}/><JobsBars rows={d.rows} months={months}/></div>
 <div className="page-heading section-heading"><div><h2>Totals for a period</h2><p>Pick a period for these five numbers.</p></div><PeriodSelect value={p.preset}/></div>
 <section className="kpi-grid" aria-label="Marketing totals">{(Object.keys(metricNames) as Metric[]).map(metric=><Link className="kpi" href={href(metric)} key={metric}><span>{metricNames[metric]}</span><strong>{format(total(metricRows(rows,metric),metric),metric)}</strong><small>{metricNotes[metric]}</small><span className="kpi-link">Explore →</span></Link>)}</section>
 <p className="definition-note">Every number as a table, month by month: <Link href={`/dashboard/tables?range=${p.preset}`}>Tables →</Link> · How each number is defined: <Link href={`/dashboard/data?range=${p.preset}#definitions`}>Data →</Link></p>
 </>;
}
