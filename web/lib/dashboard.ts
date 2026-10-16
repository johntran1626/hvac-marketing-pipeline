import { createSupabaseClient } from "@/lib/supabase/client";

// One row of public.fact_marketing_daily (anon can read it; RLS allows select only).
export type FactRow = {
  analysis_date: string;
  channel: string;
  source_platform: string;
  brand_classification: string;
  campaign_id: string | null;
  campaign_name: string | null;
  spend_usd: number | null;
  reported_leads: number | null;
  unique_leads: number | null;
  calls: number | null;
  synced_at: string;
  data_through: string;
};

const COLUMNS =
  "analysis_date,channel,source_platform,brand_classification,campaign_id,campaign_name,spend_usd,reported_leads,unique_leads,calls,synced_at,data_through";
const nullableNumber = (value: unknown): number | null =>
  value === null || value === undefined || (typeof value === "string" && value.trim() === "") || !Number.isFinite(Number(value)) ? null : Number(value);

const PAGE = 1000; // PostgREST returns at most 1,000 rows per request

export async function loadFacts(): Promise<FactRow[]> {
  const supabase = createSupabaseClient();
  // Guard offset pagination against a concurrent transactional fact rebuild.
  // Ordering below includes every column of the source's unique grain.
  const snapshot = async () => {
    const { data, error, count } = await supabase.from("fact_marketing_daily")
      .select("synced_at", { count: "exact" }).order("synced_at", { ascending: false }).limit(1);
    if (error || count === null) throw new Error("Could not verify source snapshot.");
    return { count, latest: data?.[0]?.synced_at ?? null };
  };
  const before = await snapshot();
  const rows: FactRow[] = [];
  for (let from = 0; ; from += PAGE) {
    const { data, error } = await supabase
      .from("fact_marketing_daily")
      .select(COLUMNS)
      .order("analysis_date")
      .order("channel")
      .order("source_platform")
      .order("source_account_id")
      .order("campaign_id")
      .order("brand_classification")
      .range(from, from + PAGE - 1);
    if (error) throw new Error("Could not read fact_marketing_daily.");
    rows.push(
      ...data.map((r) => ({
        ...r,
        spend_usd: nullableNumber(r.spend_usd),
        reported_leads: nullableNumber(r.reported_leads),
        unique_leads: nullableNumber(r.unique_leads),
        calls: nullableNumber(r.calls),
      })),
    );
    if (data.length < PAGE) {
      const after = await snapshot();
      if (before.count !== after.count || after.count !== rows.length || before.latest !== after.latest)
        throw new Error("Source changed during pagination; reload to obtain consistent evidence.");
      return rows;
    }
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
  unknown: "Unknown attribution",
  unattributed: "Unattributed",
  "": "Unknown attribution",
};
export const PAID_CHANNELS = ["google_ads", "google_lsa", "meta"];

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
