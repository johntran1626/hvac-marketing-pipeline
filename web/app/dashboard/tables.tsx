import {
  CHANNEL_LABELS,
  PAID_CHANNELS,
  costPerJob,
  costPerLead,
  empty,
  sumBy,
  type FactRow,
  type Totals,
} from "@/lib/dashboard";

export const usd = (n: number | null) =>
  n === null ? "–" : n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
export const usd2 = (n: number | null) =>
  n === null ? "–" : n.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 2 });
const num = (n: number) => Math.round(n).toLocaleString("en-US");
const dec = (n: number) => n.toLocaleString("en-US", { maximumFractionDigits: 1 });
const monthLabel = (m: string) =>
  new Date(`${m}-15T12:00:00Z`).toLocaleDateString("en-US", { month: "short", year: "numeric", timeZone: "UTC" });
const label = (c: string) => CHANNEL_LABELS[c] ?? c;

export function Table({ head, rows, caption }: { head: string[]; rows: (string | number)[][]; caption?: string }) {
  return (
    <div className="table-scroll">
      <table>
        {caption && <caption>{caption}</caption>}
        <thead>
          <tr>
            {head.map((h, i) => (
              <th key={i}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {r.map((c, j) => (j === 0 ? <th key={j}>{c}</th> : <td key={j}>{c}</td>))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const byChannel = (rows: FactRow[]) => sumBy(rows, (r) => r.channel);

// Paid channels, whole selection: spend, phone leads, cost per lead, and the CRM jobs next to them.
export function CostPerLeadByChannel({ rows }: { rows: FactRow[] }) {
  const t = byChannel(rows);
  return (
    <Table
      head={["Channel", "Spend", "Unique phone leads", "Cost per lead", "Booked jobs", "Cost per booked job"]}
      rows={PAID_CHANNELS.map((c) => {
        const x = t.get(c) ?? empty();
        return [label(c), usd(x.spend), num(x.unique), usd2(costPerLead(x)), num(x.jobs), usd2(costPerJob(x))];
      })}
    />
  );
}

export function CostPerLeadByMonth({ rows, months }: { rows: FactRow[]; months: string[] }) {
  const t = sumBy(rows, (r) => `${r.analysis_date.slice(0, 7)}|${r.channel}`);
  return (
    <Table
      head={["Month", ...PAID_CHANNELS.flatMap((c) => [`${label(c)} spend`, "Unique leads", "Cost per lead"])]}
      rows={[...months].reverse().map((m) => [
        monthLabel(m),
        ...PAID_CHANNELS.flatMap((c) => {
          const x = t.get(`${m}|${c}`) ?? empty();
          return [usd(x.spend), num(x.unique), usd2(costPerLead(x))];
        }),
      ])}
    />
  );
}

export function ReportedVsUnique({ rows }: { rows: FactRow[] }) {
  const t = byChannel(rows);
  const channels = Object.keys(CHANNEL_LABELS).filter((c) => (t.get(c)?.calls ?? 0) > 0 || PAID_CHANNELS.includes(c));
  return (
    <Table
      head={["Channel", "Platform-reported leads", "Unique phone leads", "Reported ÷ unique", "All calls"]}
      rows={channels.map((c) => {
        const x = t.get(c) ?? empty();
        const paid = PAID_CHANNELS.includes(c);
        return [
          label(c),
          paid ? dec(x.reported) : "–",
          num(x.unique),
          paid && x.unique > 0 ? `${(x.reported / x.unique).toFixed(1)}×` : "–",
          num(x.calls),
        ];
      })}
    />
  );
}

// Google Ads only. Brand is campaign 20814455901 (people already searching for Wren by name).
export function BrandSplit({ rows, months }: { rows: FactRow[]; months: string[] }) {
  const t = sumBy(
    rows.filter((r) => r.channel === "google_ads"),
    (r) => `${r.analysis_date.slice(0, 7)}|${r.brand_classification}`,
  );
  const total = (k: string) =>
    months.reduce((acc: Totals, m) => {
      const x = t.get(`${m}|${k}`) ?? empty();
      return { ...acc, spend: acc.spend + x.spend, reported: acc.reported + x.reported, unique: acc.unique + x.unique };
    }, empty());
  const row = (name: string, get: (k: string) => Totals) => [
    name,
    ...["brand", "non_brand"].flatMap((k) => {
      const x = get(k);
      return [usd(x.spend), dec(x.reported), num(x.unique), usd2(costPerLead(x))];
    }),
  ];
  return (
    <Table
      head={[
        "Month",
        "Brand spend", "Brand reported", "Brand unique", "Brand cost per lead",
        "Non-brand spend", "Non-brand reported", "Non-brand unique", "Non-brand cost per lead",
      ]}
      rows={[
        row("Selected period", total),
        ...[...months].reverse().map((m) => row(monthLabel(m), (k) => t.get(`${m}|${k}`) ?? empty())),
      ]}
    />
  );
}

// Jobs booked in the CRM by lead source (#84), next to the channel's phone leads and spend.
export function JobsByChannel({ rows }: { rows: FactRow[] }) {
  const t = byChannel(rows);
  const channels = Object.keys(CHANNEL_LABELS).filter((c) => (t.get(c)?.jobs ?? 0) > 0);
  return (
    <Table
      head={["Channel", "Unique phone leads", "Booked jobs", "Completed jobs", "Revenue", "Spend", "Cost per booked job"]}
      rows={channels.map((c) => {
        const x = t.get(c)!;
        const paid = PAID_CHANNELS.includes(c);
        return [
          label(c),
          x.calls > 0 ? num(x.unique) : "–",
          num(x.jobs),
          num(x.completed),
          usd(x.revenue),
          paid ? usd(x.spend) : "free",
          paid ? usd2(costPerJob(x)) : "free",
        ];
      })}
    />
  );
}

// Three or four plain sentences for Diane, each with its numbers. Returns [] when there's nothing to say.
export function insights(rows: FactRow[]): string[] {
  const t = byChannel(rows);
  const paid = PAID_CHANNELS.map((c) => ({ c, x: t.get(c) ?? empty() })).filter(({ x }) => costPerLead(x) !== null);
  const out: string[] = [];
  if (paid.length >= 2) {
    const sorted = [...paid].sort((a, b) => costPerLead(a.x)! - costPerLead(b.x)!);
    const best = sorted[0], worst = sorted.at(-1)!;
    out.push(
      `${label(best.c)} brings phone leads at ${usd2(costPerLead(best.x))} each, against ${usd2(costPerLead(worst.x))} for ${label(worst.c)}.`,
    );
  }
  const meta = t.get("meta");
  if (meta && meta.jobs > 0 && meta.jobs > meta.unique) {
    out.push(
      `Meta looks expensive per phone lead (${usd2(costPerLead(meta))}), but it booked ${num(meta.jobs)} jobs from ${num(meta.unique)} phone leads: its lead forms bring jobs the phone count misses. That's ${usd2(costPerJob(meta))} per booked job.`,
    );
  }
  const g = sumBy(rows.filter((r) => r.channel === "google_ads"), (r) => r.brand_classification);
  const brand = g.get("brand"), non = g.get("non_brand");
  if (brand && non && costPerLead(brand) !== null && costPerLead(non) !== null) {
    out.push(
      `Google Ads brand search costs ${usd2(costPerLead(brand))} per phone lead and non-brand ${usd2(costPerLead(non))}. Brand is mostly people already looking for Wren, so it flatters Google's numbers.`,
    );
  }
  const reported = PAID_CHANNELS.reduce((s, c) => s + (t.get(c)?.reported ?? 0), 0);
  const unique = PAID_CHANNELS.reduce((s, c) => s + (t.get(c)?.unique ?? 0), 0);
  if (unique > 0) {
    out.push(
      `The ad platforms reported ${num(reported)} leads, but only ${num(unique)} were first-time callers on the line 30 seconds or more. The platforms claim ${(reported / unique).toFixed(1)}× more leads than real new callers.`,
    );
  }
  return out;
}
