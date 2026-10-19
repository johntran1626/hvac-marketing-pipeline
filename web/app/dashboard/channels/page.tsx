import { periodFor, monthsBetween, inPeriod, presets } from "@/lib/reporting-period";
import Link from "next/link";
import { CHANNEL_LABELS } from "@/lib/dashboard";
import { getDashboard, metricRows, metricNames, total, format, type Metric } from "@/lib/dashboard-view";
import { monthly, RecordedChart, ChannelComparison } from "../charts";

export default async function Channels({ searchParams }: { searchParams: Promise<Record<string,string | string[] | undefined>> }) {
  const [d, query] = await Promise.all([getDashboard(), searchParams]);
  const p = periodFor(query,d.rows.map(r=>r.analysis_date).sort());
  const periodRows = d.rows.filter(r=>inPeriod(r.analysis_date,p));
  const channels = [...new Set(d.rows.map(r => r.channel))].sort();
  const observedMonths = monthsBetween(p.start,p.end);
  const month = typeof query.month === "string" && observedMonths.includes(query.month) ? query.month : "";
  const channel = typeof query.channel === "string" && channels.includes(query.channel) ? query.channel : "";
  const metric = typeof query.metric === "string" && Object.hasOwn(metricNames,query.metric) ? query.metric as Metric : "spend_usd";
  const campaigns = [...new Map(d.rows.filter(r=>r.campaign_id).map(r=>[r.campaign_id!,r.campaign_name || `Campaign ${r.campaign_id}`])).entries()].sort((a,b)=>a[1].localeCompare(b[1]));
  const campaign = typeof query.campaign === "string" && campaigns.some(([id])=>id===query.campaign) ? query.campaign : "";
  const brand = typeof query.brand === "string" && ["brand", "non_brand", "not_applicable"].includes(query.brand) ? query.brand : "";
  const rows = periodRows.filter(r => (!month || r.analysis_date.startsWith(month)) && (!channel || r.channel === channel) && (!brand || r.brand_classification === brand) && (!campaign || r.campaign_id === campaign));
  const context = `&range=${p.preset}${campaign ? `&campaign=${encodeURIComponent(campaign)}` : ""}${channel ? `&channel=${encodeURIComponent(channel)}` : ""}${brand ? `&brand=${brand}` : ""}`;
  const months = month ? [month] : observedMonths;
  const companion: Metric = metric === "unique_leads" ? "calls" : "unique_leads";
  return <><div className="page-heading"><div><h1>Channel performance</h1><p>{p.start} — {p.end}</p></div></div>
    <form key={`${p.preset}|${month}|${channel}|${brand}|${metric}|${campaign}`} className="filter-bar" action="/dashboard/channels"><label>Reporting period<select name="range" defaultValue={p.preset}>{Object.entries(presets).map(([v,label])=><option key={v} value={v}>{label}</option>)}</select></label><label>Month<select name="month" defaultValue={month}><option value="">All selected months</option>{observedMonths.map(m => <option key={m}>{m}</option>)}</select></label><label>Channel<select name="channel" defaultValue={channel}><option value="">All recorded channels</option>{channels.map(c => <option value={c} key={c}>{CHANNEL_LABELS[c] ?? c}</option>)}</select></label><label>Campaign<select name="campaign" defaultValue={campaign}><option value="">All campaigns / unattributed</option>{campaigns.map(([id,name])=><option key={id} value={id}>{name}</option>)}</select></label><label>Campaign type<select name="brand" defaultValue={brand}><option value="">All campaign types</option><option value="brand">Brand</option><option value="non_brand">Non-brand</option><option value="not_applicable">Not applicable</option></select></label><label>Focus metric<select name="metric" defaultValue={metric}>{(Object.keys(metricNames) as Metric[]).map(m => <option key={m} value={m}>{metricNames[m]}</option>)}</select></label><button type="submit">Apply Filters</button><Link href="/dashboard/channels">Reset</Link><span>{rows.length.toLocaleString()} source rows selected</span></form>
    <div className="selection-label">{month || "Selected date range"} / {channel ? CHANNEL_LABELS[channel] ?? channel : "All channels"} · applies to all charts and detail below</div>
    <section id="analysis" className="selected-metric panel"><span className="eyebrow">SELECTED RECORDS</span><h2>{metricNames[metric]}</h2><strong>{format(total(metricRows(rows,metric),metric),metric)}</strong><p>{month || `${p.start} — ${p.end}`} · {channel ? CHANNEL_LABELS[channel] ?? channel : "All channels"} · {brand || "All campaign types"} · {campaign ? campaigns.find(([id])=>id===campaign)?.[1] : "All campaigns / unattributed"}.</p>{metric === "reported_leads" && <p>Google Ads conversions can be fractional; Meta counts lead actions; Google Guaranteed counts lead records. These are not unique people. <Link href={`/dashboard/data?range=${p.preset}#definitions`}>Read metric definitions →</Link></p>}</section><div className="charts-grid"><RecordedChart selectedMonth={month} context={context} title={`${metricNames[metric]} over time`} metric={metric} points={monthly(rows,months,metric)} caption="Monthly buckets · selected dates only" insight={`${format(total(metricRows(rows,metric),metric),metric)} for this selection.`}/><RecordedChart selectedMonth={month} context={context} title={`${metricNames[companion]} over time`} metric={companion} points={monthly(rows,months,companion)} caption="Monthly buckets · selected dates only"/></div>
    <ChannelComparison rows={rows}/>
    <p className="definition-note">Cost per lead, booked jobs, brand vs non-brand and month-by-month numbers: <Link href={`/dashboard/tables?${context.slice(1)}${month ? `&month=${month}` : ""}`}>Tables →</Link></p>
  </>;
}
