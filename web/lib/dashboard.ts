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
  jobs: number | null;
  completed_jobs: number | null;
  revenue_usd: number | null;
  synced_at: string;
  data_through: string;
};

const COLUMNS =
  "analysis_date,channel,source_platform,brand_classification,campaign_id,campaign_name,spend_usd,reported_leads,unique_leads,calls,jobs,completed_jobs,revenue_usd,synced_at,data_through";
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
        jobs: nullableNumber(r.jobs),
        completed_jobs: nullableNumber(r.completed_jobs),
        revenue_usd: nullableNumber(r.revenue_usd),
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
  // CRM-only channels (lead_source on booked jobs, #84): jobs but no spend or tracked calls.
  referral: "Referral",
  existing_customer: "Existing customer",
  maintenance_plan: "Maintenance plan",
  yelp: "Yelp",
  nextdoor: "Nextdoor",
  builder_hoa: "Builder / HOA",
  unknown: "Unknown attribution",
  unattributed: "Unattributed",
  "": "Unknown attribution",
};
export const PAID_CHANNELS = ["google_ads", "google_lsa", "meta"];

export type Totals = { spend: number; reported: number; unique: number; calls: number; jobs: number; completed: number; revenue: number };
export const empty = (): Totals => ({ spend: 0, reported: 0, unique: 0, calls: 0, jobs: 0, completed: 0, revenue: 0 });

function add(t: Totals, r: FactRow) {
  t.spend += r.spend_usd ?? 0;
  t.reported += r.reported_leads ?? 0;
  t.unique += r.unique_leads ?? 0;
  t.calls += r.calls ?? 0;
  t.jobs += r.jobs ?? 0;
  t.completed += r.completed_jobs ?? 0;
  t.revenue += r.revenue_usd ?? 0;
}

// Sum each metric by a key. Each source writes its own rows, so sums never double count:
// spend and reported leads come from platform rows, unique leads and calls only from call rows,
// jobs and revenue only from CRM rows.
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

// Cost per booked job = spend ÷ jobs booked in the CRM from that channel (canceled jobs excluded).
export const costPerJob = (t: Totals) => (t.jobs > 0 ? t.spend / t.jobs : null);

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

// Tracking alerts: the same rule as worker/alerts.py (#62), which opens a GitHub issue for each one.
// A paid channel spends for 3+ days in a row with 0 reported leads, and its previous 28 days say
// it should have brought 7+ leads in that stretch (zero is then less than a 1 in 1,000 chance).
const ALERT_MIN_DAYS = 3;
const ALERT_BASELINE_DAYS = 28;
const ALERT_MIN_EXPECTED = 7;

export type Anomaly = { channel: string; start: string; end: string; days: number; spend: number; expected: number };

const addDays = (d: string, n: number) => {
  const t = new Date(`${d}T12:00:00Z`);
  t.setUTCDate(t.getUTCDate() + n);
  return t.toISOString().slice(0, 10);
};

export function anomalies(rows: FactRow[]): Anomaly[] {
  const found: Anomaly[] = [];
  for (const channel of PAID_CHANNELS) {
    const byDay = sumBy(rows.filter((r) => r.channel === channel), (r) => r.analysis_date);
    let streak: string[] = [];
    for (const day of [...[...byDay.keys()].sort(), null]) {
      const t = day ? byDay.get(day)! : null;
      if (day && t && t.spend > 0 && t.reported === 0 && (!streak.length || day === addDays(streak.at(-1)!, 1))) {
        streak.push(day);
        continue;
      }
      if (streak.length >= ALERT_MIN_DAYS) {
        let baseline = 0;
        for (let i = 1; i <= ALERT_BASELINE_DAYS; i++) baseline += byDay.get(addDays(streak[0], -i))?.reported ?? 0;
        const expected = (baseline / ALERT_BASELINE_DAYS) * streak.length;
        if (expected >= ALERT_MIN_EXPECTED) {
          found.push({
            channel,
            start: streak[0],
            end: streak.at(-1)!,
            days: streak.length,
            spend: streak.reduce((s, d) => s + byDay.get(d)!.spend, 0),
            expected,
          });
        }
      }
      streak = day && t && t.spend > 0 && t.reported === 0 ? [day] : [];
    }
  }
  return found.sort((a, b) => b.start.localeCompare(a.start));
}
