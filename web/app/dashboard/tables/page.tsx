import Link from "next/link";
import { CHANNEL_LABELS, empty, sumBy } from "@/lib/dashboard";
import { getDashboard, metricRows, metricNames, total, format, coverageNote, type Metric } from "@/lib/dashboard-view";
import { periodFor, monthsBetween, inPeriod, comparisons, presets, type Query } from "@/lib/reporting-period";
import { Heading } from "../shared";
import { BrandSplit, CostPerLeadByChannel, CostPerLeadByMonth, JobsByChannel, ReportedVsUnique, Table, usd } from "../tables";
import { hasMonth, lastFullMonth, monthName, shiftMonth } from "../story";

const num = (n: number) => Math.round(n).toLocaleString("en-US");

export default async function Tables({ searchParams }: { searchParams: Promise<Query> }) {
  const [d, q] = await Promise.all([getDashboard(), searchParams]);
  const p = periodFor(q, d.rows.map((r) => r.analysis_date).sort());
  // Same filters as Channels, so its "Tables" link keeps the selection (Kelsey's #94 review).
  const str = (k: string) => (typeof q[k] === "string" ? (q[k] as string) : "");
  const channel = str("channel"), brand = str("brand"), campaign = str("campaign");
  const all = d.rows.filter((r) => (!channel || r.channel === channel) && (!brand || r.brand_classification === brand) && (!campaign || r.campaign_id === campaign));
  const periodMonths = monthsBetween(p.start, p.end);
  const month = periodMonths.includes(str("month")) ? str("month") : "";
  const months = month ? [month] : periodMonths;
  const rows = all.filter((r) => inPeriod(r.analysis_date, p) && (!month || r.analysis_date.startsWith(month)));
  const m = sumBy(all, (r) => r.analysis_date.slice(0, 7));
  const filters = [
    month && monthName(month),
    channel && (CHANNEL_LABELS[channel] ?? channel),
    brand && { brand: "Brand", non_brand: "Non-brand", not_applicable: "Not applicable" }[brand],
    campaign && (d.rows.find((r) => r.campaign_id === campaign)?.campaign_name ?? "One campaign"),
  ].filter(Boolean);
  const full = lastFullMonth(d.rows);
  const yoy = [...months].reverse().map((mm) => {
    const prev = shiftMonth(mm, -12);
    const now = m.get(mm) ?? empty(), then = m.get(prev) ?? empty();
    // A month before the data starts is missing, not zero.
    const ly = (owner: "jobs" | "unique" | "spend", v: string) => (hasMonth(all, prev, owner) ? v : "–");
    return [`${monthName(mm, { month: "short", year: "numeric" })}${full && mm > full ? " (so far)" : ""}`, num(now.jobs), ly("jobs", num(then.jobs)), num(now.unique), ly("unique", num(then.unique)), usd(now.spend), ly("spend", usd(then.spend))];
  });
  return (
    <>
      <Heading range={p.preset} period={`${p.start} — ${p.end}`} title="Tables" description="Every number on the dashboard, month by month." />
      <form className="filter-bar" action="/dashboard/tables">
        <label>Reporting period<select name="range" defaultValue={p.preset}>{Object.entries(presets).map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
        {["month", "channel", "brand", "campaign"].map((k) => str(k) && <input key={k} type="hidden" name={k} value={str(k)} />)}
        <button type="submit">Apply</button>
        {filters.length > 0 && <span>Filtered to {filters.join(" · ")}. <Link href={`/dashboard/tables?range=${p.preset}`}>Clear</Link></span>}
      </form>
      <section className="panel"><h2>Each month vs the same month last year</h2><p className="table-note">A dash means there&apos;s no data for that month a year earlier (data starts October 2024).</p><Table head={["Month", "Booked jobs", "Last year", "New callers", "Last year", "Ad spend", "Last year"]} rows={yoy} /></section>
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
