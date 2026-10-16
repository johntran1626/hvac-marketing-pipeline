import Link from "next/link";
import { type FactRow, CHANNEL_LABELS } from "@/lib/dashboard";
import { format, metricHref, metricRows, total, type Metric } from "@/lib/dashboard-view";
import { Empty } from "./shared";

export function monthly(rows: FactRow[], months: string[], metric: Metric) {
  return months.map(month => ({ label: month, value: total(metricRows(rows.filter(r => r.analysis_date.startsWith(month)), metric), metric) }));
}
export function RecordedChart({ title, metric, points, caption, context = "", insight, selectedMonth = "" }: {
  title: string; metric: Metric; points: { label: string; value: number | null }[]; caption: string; context?: string; insight?: string; selectedMonth?: string;
}) {
  const available = points.filter(p => p.value !== null);
  const max = Math.max(0, ...available.map(p => p.value!));
  const min = Math.min(0, ...available.map(p => p.value!));
  const span = max - min || 1;
  const y = (value: number) => 160 - (value - min) / span * 136;
  const width = 560;
  const step = (width - 76) / Math.max(1, points.length);
  return <section className={`panel chart-panel ${metric === "unique_leads" ? "chart-teal" : ""}`}>
    <div className="panel-heading"><h2>{title}</h2><span className="tag">Recorded</span></div>
    {insight && <p className="chart-insight">{insight}</p>}
    <p className="chart-caption">{caption} · Coverage unverified</p>
    {available.length ? <><div className="chart-scroll"><svg style={{minWidth: Math.max(400, points.length * 42)}} viewBox={`0 0 ${width} 207`} role="img" aria-label={`${title}. Coverage unverified. Exact values in chart data below.`}>
      {[min, min + (max - min) / 2, max].filter((v, i, a) => a.indexOf(v) === i).map(v => <g key={v}><line x1="64" x2={width - 8} y1={y(v)} y2={y(v)} stroke="#e0e8ed" strokeDasharray="3 4"/><text x="57" y={y(v) + 4} textAnchor="end" className="axis-label">{new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1, ...(metric === "spend_usd" ? { style: "currency", currency: "USD" } : {}) }).format(v)}</text></g>)}
      {points.map((p, i) => { const x = 64 + i * step + step / 2; return <a key={p.label} href={`${metricHref(metric,p.label).replace("#analysis", "")}${context}#analysis`} aria-label={`${p.label}: ${format(p.value, metric)}. Explore ${title}`}>{p.value === null ? <text x={x} y="150" textAnchor="middle" className="missing-mark">—</text> : p.value === 0 ? <circle cx={x} cy={y(0)} r="3" className="chart-bar"/> : <rect x={x - Math.min(48, step * .56) / 2} y={Math.min(y(0), y(p.value))} width={Math.min(48, step * .56)} height={Math.abs(y(0) - y(p.value))} rx="4" className="chart-bar"/>}<text x={x} y="185" textAnchor="middle" className="axis-label">{p.label.slice(5)}</text><text x={x} y="200" textAnchor="middle" className="axis-year">{p.label.slice(0,4)}</text></a>; })}
    </svg></div><details className="chart-data"><summary>View exact chart values</summary><div className="table-scroll"><table><caption>{title} · recorded totals</caption><thead><tr><th>Month</th><th>Value</th></tr></thead><tbody>{points.map(p => <tr key={p.label}><th>{p.label}</th><td>{format(p.value,metric)}</td></tr>)}</tbody></table></div></details><Link className="text-link" href={`${metricHref(metric,selectedMonth).replace("#analysis", "")}${context}#analysis`}>Explore this metric →</Link><div className="chart-key"><span><i/> Recorded total</span><span>— Unavailable · dot = recorded zero</span></div></> : <Empty text="No complete numeric totals are available for this metric in the selected records. Missing values are not plotted as zero."/>}
  </section>;
}
export function ChannelComparison({ rows }: { rows: FactRow[] }) {
  const channels = [...new Set(rows.map(r => r.channel))].sort();
  return <section className="panel"><div className="panel-heading"><h2>Channel comparison</h2><span className="tag">Coverage unverified</span></div><p>Recorded totals for the selected window. Separate scales; these are not efficiency rankings. Phone leads and platform conversions use different definitions.</p><div className="comparison-grid">{(["spend_usd", "unique_leads"] as Metric[]).map(metric => {
    const points = channels.map(channel => ({ label: CHANNEL_LABELS[channel] ?? channel, value: total(metricRows(rows.filter(r => r.channel === channel),metric),metric) }));
    const max = Math.max(0,...points.map(p => Math.abs(p.value ?? 0)));
    return <div key={metric} className={metric === "unique_leads" ? "chart-teal" : ""}><h3>{metric === "spend_usd" ? "Recorded ad spend" : "Recorded unique phone leads"}</h3>{points.map(p => <div className="comparison-row" key={p.label}><div><span>{p.label}</span><strong>{format(p.value,metric)}</strong></div><div className="bar-track" aria-hidden="true">{p.value !== null && <span style={{width:`${max ? Math.abs(p.value) / max * 100 : 0}%`}}/>}</div></div>)}{!points.length && <Empty text="No channel records match this selection."/>}</div>;
  })}</div></section>;
}
