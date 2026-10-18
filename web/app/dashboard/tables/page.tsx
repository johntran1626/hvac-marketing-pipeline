import Link from "next/link";
import { empty, sumBy } from "@/lib/dashboard";
import { getDashboard, metricRows, metricNames, total, format, coverageNote, type Metric } from "@/lib/dashboard-view";
import { periodFor, monthsBetween, inPeriod, comparisons, presets, type Query } from "@/lib/reporting-period";
import { Heading } from "../shared";
import { BrandSplit, CostPerLeadByChannel, CostPerLeadByMonth, JobsByChannel, ReportedVsUnique, Table, usd } from "../tables";
import { lastFullMonth, monthName, shiftMonth } from "../story";

const num = (n: number) => Math.round(n).toLocaleString("en-US");

export default async function Tables({ searchParams }: { searchParams: Promise<Query> }) {
  const [d, q] = await Promise.all([getDashboard(), searchParams]);
  const p = periodFor(q, d.rows.map((r) => r.analysis_date).sort());
  const rows = d.rows.filter((r) => inPeriod(r.analysis_date, p));
  const months = monthsBetween(p.start, p.end);
  const m = sumBy(d.rows, (r) => r.analysis_date.slice(0, 7));
  const full = lastFullMonth(d.rows);
  const yoy = [...months].reverse().map((mm) => {
    const now = m.get(mm) ?? empty(), then = m.get(shiftMonth(mm, -12)) ?? empty();
    return [`${monthName(mm, { month: "short", year: "numeric" })}${full && mm > full ? " (so far)" : ""}`, num(now.jobs), num(then.jobs), num(now.unique), num(then.unique), usd(now.spend), usd(then.spend)];
  });
  return (
    <>
      <Heading range={p.preset} period={`${p.start} — ${p.end}`} title="Tables" description="Every number on the dashboard, month by month." />
      <form className="filter-bar" action="/dashboard/tables">
        <label>Reporting period<select name="range" defaultValue={p.preset}>{Object.entries(presets).map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
        <button type="submit">Apply</button>
      </form>
      <section className="panel"><h2>Each month vs the same month last year</h2><Table head={["Month", "Booked jobs", "Last year", "New callers", "Last year", "Ad spend", "Last year"]} rows={yoy} /></section>
      <section className="panel" id="cost-per-lead"><h2>Cost per lead by channel</h2><CostPerLeadByChannel rows={rows} /></section>
      <section className="panel"><h2>Cost per lead by month</h2><CostPerLeadByMonth rows={rows} months={months} /></section>
      <section className="panel"><h2>Booked jobs by channel</h2><JobsByChannel rows={rows} /></section>
      <section className="panel"><h2>Reported vs unique leads</h2><ReportedVsUnique rows={rows} /></section>
      <section className="panel"><h2>Google Ads: brand vs non-brand</h2><BrandSplit rows={rows} months={months} /></section>
      <section className="panel"><h2>Same period last year</h2><div className="table-scroll"><table><thead><tr><th>Comparison / dates</th>{Object.values(metricNames).map((n) => <th key={n}>{n}</th>)}</tr></thead><tbody>{comparisons(p).map((c) => <tr key={c.label}><th>{c.label}<small>{c.start} — {c.end}</small></th>{(Object.keys(metricNames) as Metric[]).map((mt) => { const sel = d.rows.filter((r) => inPeriod(r.analysis_date, c)); return <td key={mt}>{format(total(metricRows(sel, mt), mt), mt)}<small>{coverageNote(sel, mt, c.start, c.end)}</small></td>; })}</tr>)}</tbody></table></div></section>
      <p className="definition-note">What each column means: <Link href={`/dashboard/data?range=${p.preset}#definitions`}>Data →</Link></p>
    </>
  );
}
