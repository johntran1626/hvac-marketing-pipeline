import { connection } from "next/server";
import {
  CHANNEL_LABELS,
  anomalies,
  PAID_CHANNELS,
  centralYesterday,
  costPerLead,
  freshness,
  lastMonths,
  loadFacts,
  month,
  sumBy,
  type FactRow,
  type Totals,
} from "@/lib/dashboard";

export const metadata = { title: "Wren Air & Heat: Marketing Dashboard" };

const MONTHS = 12;
const usd = (n: number | null) =>
  n === null ? "–" : n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const usd2 = (n: number | null) =>
  n === null ? "–" : n.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 });
const num = (n: number) => Math.round(n).toLocaleString("en-US");
const lastDayOf = (m: string) => {
  const [y, mo] = m.split("-").map(Number);
  return String(new Date(Date.UTC(y, mo, 0)).getUTCDate());
};
const monthLabel = (m: string) =>
  new Date(`${m}-15T12:00:00Z`).toLocaleDateString("en-US", { month: "short", year: "numeric", timeZone: "UTC" });

const SOURCE_LABELS: Record<string, string> = {
  google_ads: "Google Ads",
  meta_ads: "Meta",
  lsa: "Google Guaranteed",
  call_tracking: "Call tracking",
};

function Freshness({ rows }: { rows: FactRow[] }) {
  const fresh = freshness(rows);
  const expected = centralYesterday();
  const stale = [...fresh.values()].some((f) => f.dataThrough < expected);
  const synced = [...fresh.values()].map((f) => f.syncedAt).sort().at(-1);
  return (
    <section className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <div className="flex flex-wrap items-center gap-3">
        <span
          className={`rounded-full px-3 py-1 text-sm font-semibold ${
            stale
              ? "bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-200"
              : "bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-200"
          }`}
        >
          {stale ? "Data behind" : "Data current"}
        </span>
        <span className="text-sm text-zinc-600 dark:text-zinc-400">
          Expected through {expected} (yesterday, Central).{" "}
          {synced && `Last refreshed ${new Date(synced).toLocaleString("en-US", { timeZone: "America/Chicago" })} CT.`}
        </span>
      </div>
      <ul className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-sm">
        {[...fresh.entries()].map(([src, f]) => (
          <li key={src}>
            {SOURCE_LABELS[src] ?? src}: data through{" "}
            <span className={f.dataThrough < expected ? "font-semibold text-amber-700 dark:text-amber-300" : ""}>
              {f.dataThrough}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Table({ head, rows }: { head: string[]; rows: (string | number)[][] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] border-collapse text-sm tabular-nums">
        <thead>
          <tr className="border-b border-zinc-300 text-left dark:border-zinc-700">
            {head.map((h, i) => (
              <th key={i} className={`py-2 pr-4 font-semibold ${i > 0 ? "text-right" : ""}`}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-zinc-100 dark:border-zinc-900">
              {r.map((c, j) => (
                <td key={j} className={`py-1.5 pr-4 ${j > 0 ? "text-right" : ""}`}>
                  {c}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Section({ title, note, children }: { title: string; note: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="text-xl font-semibold">{title}</h2>
      <p className="max-w-3xl text-sm text-zinc-600 dark:text-zinc-400">{note}</p>
      {children}
    </section>
  );
}

export default async function Dashboard() {
  await connection(); // read live data on every request
  let rows: FactRow[];
  try {
    rows = await loadFacts();
  } catch {
    return <main className="p-8">The dashboard could not read its data. Check /health.</main>;
  }

  const months = lastMonths(rows, MONTHS);
  const first = months[0], last = months.at(-1)!;
  // The newest month is usually partway through; say so next to its numbers.
  const latestDay = rows.map((r) => r.analysis_date).sort().at(-1)!;
  const label = (m: string) => (m === last && latestDay !== `${m}-${lastDayOf(m).padStart(2, "0")}` ? `${monthLabel(m)} (so far)` : monthLabel(m));
  const recent = rows.filter((r) => months.includes(month(r)));
  // Alerts use all history for their 28-day baseline; show the ones that end in the window.
  const alerts = anomalies(rows).filter((a) => a.end >= `${first}-01`);
  const byMonthChannel = sumBy(recent, (r) => `${month(r)}|${r.channel}`);
  const get = (m: string, c: string): Totals =>
    byMonthChannel.get(`${m}|${c}`) ?? { spend: 0, reported: 0, unique: 0, calls: 0 };

  // 1. Cost per lead by channel and month (paid channels).
  const cplRows = months.map((m) => [
    label(m),
    ...PAID_CHANNELS.flatMap((c) => {
      const t = get(m, c);
      return [usd(t.spend), num(t.unique), usd2(costPerLead(t))];
    }),
  ]);

  // 2. Reported vs unique leads by channel (whole window).
  const byChannel = sumBy(recent, (r) => r.channel);
  const leadRows = Object.keys(CHANNEL_LABELS)
    .filter((c) => byChannel.has(c))
    .map((c) => {
      const t = byChannel.get(c)!;
      const paid = PAID_CHANNELS.includes(c);
      return [
        CHANNEL_LABELS[c],
        paid ? num(t.reported) : "–",
        num(t.unique),
        paid && t.unique > 0 ? `${(t.reported / t.unique).toFixed(1)}×` : "–",
        num(t.calls),
        paid ? usd(t.spend) : "free",
        paid ? usd2(costPerLead(t)) : "free",
      ];
    });

  // 3. Brand vs non-brand, Google Ads (campaign 20814455901 is brand).
  const brand = sumBy(
    recent.filter((r) => r.channel === "google_ads"),
    (r) => `${month(r)}|${r.brand_classification}`,
  );
  const b = (m: string, k: string) => brand.get(`${m}|${k}`) ?? { spend: 0, reported: 0, unique: 0, calls: 0 };
  const brandRows = months.map((m) => [
    label(m),
    ...["brand", "non_brand"].flatMap((k) => {
      const t = b(m, k);
      return [usd(t.spend), num(t.reported), num(t.unique), usd2(costPerLead(t))];
    }),
  ]);


  return (
    <main className="mx-auto w-full max-w-6xl space-y-10 px-4 py-8 sm:px-8">
      <header className="space-y-2">
        <h1 className="text-3xl font-semibold">Wren Air &amp; Heat: Marketing Dashboard</h1>
        <p className="max-w-3xl text-zinc-600 dark:text-zinc-400">
          {monthLabel(first)} to {monthLabel(last)}. A <strong>unique lead</strong> is a first-time caller who stayed on
          the line 30 seconds or more. <strong>Cost per lead</strong> is spend ÷ unique leads. Every number is summed from{" "}
          <code>fact_marketing_daily</code>, rebuilt from the raw API tables after each daily sync.
        </p>
      </header>

      <Freshness rows={rows} />

      <Section
        title="Tracking alerts"
        note="A paid channel kept spending but its platform reported 0 leads for 3+ days in a row, when the previous 28 days say it should have brought 7 or more. That usually means broken tracking (a lead form, pixel or conversion setup). Each one also opens an issue on GitHub."
      >
        {alerts.length === 0 ? (
          <p className="text-sm">No alerts from {monthLabel(first)} to {monthLabel(last)}.</p>
        ) : (
          <ul className="space-y-2">
            {alerts.map((a) => (
              <li
                key={`${a.channel}-${a.start}`}
                className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-100"
              >
                <strong>{CHANNEL_LABELS[a.channel]}</strong>: 0 reported leads for {a.days} days ({a.start} to {a.end})
                while spending <strong>{usd2(a.spend)}</strong>. Expected about {a.expected.toFixed(0)} leads.
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section
        title="Cost per lead by channel and month"
        note="Spend is what each platform charged (Google Guaranteed: charged leads only; credited and not-charged leads cost $0). Unique leads are calls to that channel's tracking number. Meta lead forms don't ring a phone, so Meta's cost per lead here only counts phone leads."
      >
        <Table
          head={["Month", ...PAID_CHANNELS.flatMap((c) => [`${CHANNEL_LABELS[c]} spend`, "Unique leads", "Cost per lead"])]}
          rows={cplRows}
        />
      </Section>

      <Section
        title="Reported vs unique leads"
        note={`What each platform says it delivered (Google Ads conversions, Meta lead actions, Google Guaranteed leads) next to the first-time callers we can see, ${monthLabel(first)} to ${monthLabel(last)}. Free channels have no platform count.`}
      >
        <Table
          head={["Channel", "Reported leads", "Unique leads", "Reported ÷ unique", "All calls", "Spend", "Cost per lead"]}
          rows={leadRows}
        />
      </Section>

      <Section
        title="Google Ads: brand vs non-brand"
        note="Brand is campaign 20814455901 (people already searching for Wren by name). Classified by campaign id, not name, because names change."
      >
        <Table
          head={[
            "Month",
            "Brand spend", "Brand reported", "Brand unique", "Brand cost per lead",
            "Non-brand spend", "Non-brand reported", "Non-brand unique", "Non-brand cost per lead",
          ]}
          rows={brandRows}
        />
      </Section>

      <footer className="text-xs text-zinc-500">
        Dates: Google Ads and Google Guaranteed and calls by Central day; Meta by its Pacific account day (not shifted).
      </footer>
    </main>
  );
}
