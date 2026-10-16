import { monthsBetween } from "./reporting-period";
import { cache } from "react";
import { connection } from "next/server";
import { loadFacts, centralYesterday, type FactRow } from "./dashboard";

export const sources = [
  { id: "google_ads", label: "Google Ads", metrics: ["spend_usd", "reported_leads"] },
  { id: "meta_ads", label: "Meta", metrics: ["spend_usd", "reported_leads"] },
  { id: "lsa", label: "Google Guaranteed", metrics: ["spend_usd", "reported_leads"] },
  { id: "call_tracking", label: "Call tracking", metrics: ["unique_leads", "calls"] },
] as const;
export type Metric = "spend_usd" | "reported_leads" | "unique_leads" | "calls";
export const metricNames: Record<Metric, string> = { spend_usd: "Ad spend", reported_leads: "Platform conversions", unique_leads: "Unique phone leads", calls: "Tracked calls" };
export function total(rows: FactRow[], metric: Metric): number | null {
  if (!rows.length || rows.some(r => r[metric] === null)) return null;
  return rows.reduce((sum, row) => sum + row[metric]!, 0);
}
export function format(value: number | null, metric: Metric) {
  if (value === null) return "Unavailable";
  return value.toLocaleString("en-US", metric === "spend_usd" ? { style: "currency", currency: "USD", maximumFractionDigits: 2 } : { maximumFractionDigits: 2 });
}
export const getDashboard = cache(async () => {
  await connection();
  let rows: FactRow[] = [];
  let failed = false;
  try { rows = await loadFacts(); } catch { failed = true; }
  const dates = rows.map(r => r.analysis_date).filter(d => /^\d{4}-\d{2}-\d{2}$/.test(d)).sort();
  const end = dates.at(-1);
  const months = dates.length ? monthsBetween(dates[0], end!) : [];
  return { rows, failed, months, expected: centralYesterday(), latest: end, period: months.length ? `${dates[0]} — ${end} · observed records` : "Reporting period unavailable" };

});
export function metricRows(rows: FactRow[], metric: Metric) {
  const ids = sources.filter(s => (s.metrics as readonly string[]).includes(metric)).map(s => s.id as string);
  return rows.filter(r => ids.includes(r.source_platform));
}

export function metricHref(metric: Metric, month = "") { return `/dashboard/channels?metric=${metric}${month ? `&month=${month}` : ""}#analysis`; }

export function coverageNote(rows: FactRow[], metric: Metric, start: string, end: string) {
 const owned=metricRows(rows,metric);
 if(!owned.length) return "Missing metric records";
 if(owned.some(r=>r[metric]===null)) return "Null metric; total unavailable";
 const days=new Set(owned.map(r=>r.analysis_date)).size;
 const expected=Math.round((Date.parse(end)-Date.parse(start))/86400000)+1;
 const missing=sources.filter(s=>(s.metrics as readonly string[]).includes(metric)&&!owned.some(r=>r.source_platform===s.id)).map(s=>s.label);
 return `${days}/${expected} date labels observed; ${missing.length ? `absent sources: ${missing.join(', ')}; ` : ''}coverage unverified`;
}
