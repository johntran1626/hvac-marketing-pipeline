import { createSupabaseClient } from "@/lib/supabase/client";

// One row of public.fact_marketing_daily (anon can read it; RLS allows select only).
export type FactRow = {
  analysis_date: string;
  channel: string;
  source_platform: string;
  brand_classification: string;
  spend_usd: number;
  reported_leads: number;
  unique_leads: number;
  calls: number;
  synced_at: string;
  data_through: string;
};

const COLUMNS =
  "analysis_date,channel,source_platform,brand_classification,spend_usd,reported_leads,unique_leads,calls,synced_at,data_through";
const PAGE = 1000; // PostgREST returns at most 1,000 rows per request

export async function loadFacts(): Promise<FactRow[]> {
  const supabase = createSupabaseClient();
  const rows: FactRow[] = [];
  for (let from = 0; ; from += PAGE) {
    const { data, error } = await supabase
      .from("fact_marketing_daily")
      .select(COLUMNS)
      .order("analysis_date")
      .order("channel")
      .order("source_platform")
      .range(from, from + PAGE - 1);
    if (error) throw new Error("Could not read fact_marketing_daily.");
    rows.push(
      ...data.map((r) => ({
        ...r,
        spend_usd: Number(r.spend_usd),
        reported_leads: Number(r.reported_leads),
        unique_leads: Number(r.unique_leads),
        calls: Number(r.calls),
      })),
    );
    if (data.length < PAGE) return rows;
  }
}

// Diane's words: "Google Guaranteed", not LSA.
export const CHANNEL_LABELS: Record<string, string> = {
  google_ads: "Google Ads",
  google_lsa: "Google Guaranteed",
  meta: "Meta",
  gbp: "Google Business Profile (free)",
  website: "Website",
  direct: "Direct",
};
export const PAID_CHANNELS = ["google_ads", "google_lsa", "meta"];

export type Totals = { spend: number; reported: number; unique: number; calls: number };
const empty = (): Totals => ({ spend: 0, reported: 0, unique: 0, calls: 0 });

function add(t: Totals, r: FactRow) {
  t.spend += r.spend_usd;
  t.reported += r.reported_leads;
  t.unique += r.unique_leads;
  t.calls += r.calls;
}

// Sum each metric by a key. Each source writes its own rows, so sums never double count:
// spend and reported leads come from platform rows, unique leads and calls only from call rows.
export function sumBy(rows: FactRow[], key: (r: FactRow) => string | null) {
  const out = new Map<string, Totals>();
  for (const r of rows) {
    const k = key(r);
    if (k === null) continue;
    if (!out.has(k)) out.set(k, empty());
    add(out.get(k)!, r);
  }
  return out;
}

export const month = (r: FactRow) => r.analysis_date.slice(0, 7);

export function lastMonths(rows: FactRow[], n: number) {
  return [...new Set(rows.map(month))].sort().slice(-n);
}

// Cost per lead = spend ÷ unique leads (first-time callers on the line 30 seconds or more).
export const costPerLead = (t: Totals) => (t.unique > 0 ? t.spend / t.unique : null);

// Freshness per source: the latest day loaded and when the fact table was last rebuilt.
export function freshness(rows: FactRow[]) {
  const out = new Map<string, { dataThrough: string; syncedAt: string }>();
  for (const r of rows) {
    const cur = out.get(r.source_platform) ?? { dataThrough: "", syncedAt: "" };
    out.set(r.source_platform, {
      dataThrough: r.data_through > cur.dataThrough ? r.data_through : cur.dataThrough,
      syncedAt: r.synced_at > cur.syncedAt ? r.synced_at : cur.syncedAt,
    });
  }
  return out;
}

// Yesterday in Central time: the newest day the API can have (docs/API.md).
export function centralYesterday(now = new Date()) {
  const today = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Chicago" }).format(now);
  const d = new Date(`${today}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() - 1);
  return d.toISOString().slice(0, 10);
}
