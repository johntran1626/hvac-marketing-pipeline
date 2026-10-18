// The Overview's story for Diane: this month's insights, then charts (Hamza's M2 note, Oct 15).
import { CHANNEL_LABELS, PAID_CHANNELS, costPerJob, costPerLead, empty, sumBy, type FactRow, type Totals } from "@/lib/dashboard";
import { usd, usd2 } from "./tables";

export const CHANNEL_COLORS: Record<string, string> = {
  google_ads: "#2f6fb0",
  google_lsa: "#2a9d8f",
  meta: "#7b5ea7",
  gbp: "#e09f3e",
  website: "#5c7c8a",
  direct: "#9aa9b3",
};
const OTHER = "#c3ced6";
const LAST_YEAR = "#c9d6de";
const THIS_YEAR = "#284f6b";

const num = (n: number) => Math.round(n).toLocaleString("en-US");
const label = (c: string) => CHANNEL_LABELS[c] ?? c;
export const monthName = (m: string, opts: Intl.DateTimeFormatOptions = { month: "long", year: "numeric" }) =>
  new Date(`${m}-15T12:00:00Z`).toLocaleDateString("en-US", { ...opts, timeZone: "UTC" });
export const shiftMonth = (m: string, n: number) => {
  const d = new Date(`${m}-15T12:00:00Z`);
  d.setUTCMonth(d.getUTCMonth() + n);
  return d.toISOString().slice(0, 7);
};
const pct = (now: number, then: number) => (then > 0 ? Math.round(((now - then) / then) * 100) : null);
const change = (now: number, then: number) => {
  const p = pct(now, then);
  return p === null ? "" : p === 0 ? "the same as" : p > 0 ? `up ${p}% on` : `down ${-p}% on`;
};

// The newest month with every day loaded. The current month is partial, so "this month" is the last full one.
export function lastFullMonth(rows: FactRow[]) {
  const latest = rows.map((r) => r.analysis_date).sort().at(-1);
  if (!latest) return null;
  const m = latest.slice(0, 7);
  const lastDay = new Date(Date.UTC(Number(m.slice(0, 4)), Number(m.slice(5, 7)), 0)).toISOString().slice(0, 10);
  return latest === lastDay ? m : shiftMonth(m, -1);
}

export function last12(month: string) {
  return Array.from({ length: 12 }, (_, i) => shiftMonth(month, i - 11));
}

const byMonth = (rows: FactRow[]) => sumBy(rows, (r) => r.analysis_date.slice(0, 7));
const byMonthChannel = (rows: FactRow[]) => sumBy(rows, (r) => `${r.analysis_date.slice(0, 7)}|${r.channel}`);

// Three or four sentences, each with its number, for the last full month next to the same month last year.
export function monthInsights(rows: FactRow[], month: string): string[] {
  const m = byMonth(rows), mc = byMonthChannel(rows);
  const now = m.get(month) ?? empty(), then = m.get(shiftMonth(month, -12)) ?? empty();
  const name = monthName(month, { month: "long" });
  const out: string[] = [];
  if (now.jobs > 0) {
    const c = change(now.jobs, then.jobs);
    out.push(`${name}: ${num(now.jobs)} jobs booked and ${usd(now.revenue)} from completed jobs${c ? `, ${c} ${name} last year (${num(then.jobs)} jobs)` : ""}.`);
  }
  const paid = PAID_CHANNELS.map((c) => ({ c, x: mc.get(`${month}|${c}`) ?? empty() })).filter(({ x }) => costPerLead(x) !== null);
  if (paid.length >= 2) {
    const s = [...paid].sort((a, b) => costPerLead(a.x)! - costPerLead(b.x)!);
    out.push(`${label(s[0].c)} was the cheapest way to get a new caller in ${name}, at ${usd2(costPerLead(s[0].x))} a lead, against ${usd2(costPerLead(s.at(-1)!.x))} for ${label(s.at(-1)!.c)}.`);
  }
  // Meta's lead forms don't ring a phone, so judge it on jobs too, over 12 months (one month is too few jobs).
  const meta = last12(month).reduce((t: Totals, mm) => {
    const x = mc.get(`${mm}|meta`) ?? empty();
    return { ...t, spend: t.spend + x.spend, unique: t.unique + x.unique, jobs: t.jobs + x.jobs };
  }, empty());
  if (meta.jobs > 0 && meta.unique > 0) {
    out.push(`Meta looks expensive at ${usd2(costPerLead(meta))} per phone lead over the last 12 months, but it booked ${num(meta.jobs)} jobs from ${num(meta.unique)} phone leads, because its lead forms don't ring a phone. That's ${usd2(costPerJob(meta))} per booked job.`);
  }
  if (now.unique > 0 && then.unique > 0) {
    out.push(`New callers (first-time, 30 seconds or more): ${num(now.unique)} in ${name}, ${change(now.unique, then.unique) || "against"} last year's ${num(then.unique)}.`);
  }
  return out;
}

// Bars for each month, this year next to the same month last year.
export function YoyChart({ title, rows, months, pick, format = num }: {
  title: string; rows: FactRow[]; months: string[]; pick: (t: Totals) => number; format?: (n: number) => string;
}) {
  const m = byMonth(rows);
  const pts = months.map((mm) => ({ mm, now: pick(m.get(mm) ?? empty()), then: pick(m.get(shiftMonth(mm, -12)) ?? empty()) }));
  const max = Math.max(1, ...pts.flatMap((p) => [p.now, p.then]));
  const W = 560, H = 190, left = 44, base = 160, step = (W - left - 8) / pts.length, bw = Math.min(16, step * 0.34);
  const y = (v: number) => base - (v / max) * 130;
  const sum = (k: "now" | "then") => pts.reduce((s, p) => s + p[k], 0);
  return (
    <section className="panel chart-panel">
      <div className="panel-heading"><h2>{title}</h2></div>
      <p className="chart-caption">Last 12 months: {format(sum("now"))}, {change(sum("now"), sum("then")) || "vs"} the 12 months before ({format(sum("then"))}).</p>
      <div className="chart-scroll">
        <svg viewBox={`0 0 ${W} ${H + 12}`} role="img" aria-label={`${title}, this year against the same month last year`}>
          {[0, max / 2, max].map((v) => (
            <g key={v}><line x1={left} x2={W - 8} y1={y(v)} y2={y(v)} stroke="#e0e8ed" strokeDasharray="3 4" /><text x={left - 6} y={y(v) + 4} textAnchor="end" className="axis-label">{new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(v)}</text></g>
          ))}
          {pts.map((p, i) => {
            const x = left + i * step + step / 2;
            return (
              <g key={p.mm}>
                <rect x={x - bw - 1} y={y(p.then)} width={bw} height={base - y(p.then)} rx="2" fill={LAST_YEAR}><title>{`${monthName(shiftMonth(p.mm, -12))}: ${format(p.then)}`}</title></rect>
                <rect x={x + 1} y={y(p.now)} width={bw} height={base - y(p.now)} rx="2" fill={THIS_YEAR}><title>{`${monthName(p.mm)}: ${format(p.now)}`}</title></rect>
                <text x={x} y={base + 16} textAnchor="middle" className="axis-label">{monthName(p.mm, { month: "short" })}</text>
              </g>
            );
          })}
        </svg>
      </div>
      <div className="chart-key"><span><i style={{ background: THIS_YEAR }} /> This year</span><span><i style={{ background: LAST_YEAR }} /> Same month last year</span></div>
    </section>
  );
}

// Cost per lead by month, one line per paid channel.
export function CplLines({ rows, months }: { rows: FactRow[]; months: string[] }) {
  const mc = byMonthChannel(rows);
  const series = PAID_CHANNELS.map((c) => ({ c, pts: months.map((mm) => costPerLead(mc.get(`${mm}|${c}`) ?? empty())) }));
  // Months with one or two phone leads swing wildly; cap the axis so the other lines stay readable.
  const values = series.flatMap((s) => s.pts.filter((v): v is number => v !== null)).sort((a, b) => a - b);
  const max = Math.max(50, values[Math.floor(values.length * 0.9)] ?? 50);
  const W = 560, H = 190, left = 48, base = 160, step = (W - left - 8) / months.length;
  const y = (v: number) => base - (Math.min(v, max) / max) * 130;
  const x = (i: number) => left + i * step + step / 2;
  return (
    <section className="panel chart-panel chart-teal">
      <div className="panel-heading"><h2>Cost per lead by month</h2></div>
      <p className="chart-caption">Spend ÷ new callers (first-time, 30 seconds or more). Lower is better.</p>
      <div className="chart-scroll">
        <svg viewBox={`0 0 ${W} ${H + 12}`} role="img" aria-label="Cost per lead by month for Google Ads, Google Guaranteed and Meta">
          {[0, max / 2, max].map((v) => (
            <g key={v}><line x1={left} x2={W - 8} y1={y(v)} y2={y(v)} stroke="#e0e8ed" strokeDasharray="3 4" /><text x={left - 6} y={y(v) + 4} textAnchor="end" className="axis-label">{v === max ? `${usd(v)}+` : usd(v)}</text></g>
          ))}
          {series.map((s) => (
            <g key={s.c}>
              <polyline fill="none" stroke={CHANNEL_COLORS[s.c]} strokeWidth="2.5" strokeLinejoin="round"
                points={s.pts.map((v, i) => (v === null ? null : `${x(i)},${y(v)}`)).filter(Boolean).join(" ")} />
              {s.pts.map((v, i) => v !== null && (
                <circle key={i} cx={x(i)} cy={y(v)} r="3.5" fill={CHANNEL_COLORS[s.c]}><title>{`${label(s.c)}, ${monthName(months[i])}: ${usd2(v)}`}</title></circle>
              ))}
            </g>
          ))}
          {months.map((mm, i) => <text key={mm} x={x(i)} y={base + 16} textAnchor="middle" className="axis-label">{monthName(mm, { month: "short" })}</text>)}
        </svg>
      </div>
      <div className="chart-key">{series.map((s) => <span key={s.c}><i style={{ background: CHANNEL_COLORS[s.c] }} /> {label(s.c)}</span>)}</div>
    </section>
  );
}

// Booked jobs by channel over the months shown, biggest first.
export function JobsBars({ rows, months }: { rows: FactRow[]; months: string[] }) {
  const t = sumBy(rows.filter((r) => months.includes(r.analysis_date.slice(0, 7))), (r) => r.channel);
  const list = [...t.entries()].filter(([, x]) => x.jobs > 0).sort((a, b) => b[1].jobs - a[1].jobs);
  const max = Math.max(1, ...list.map(([, x]) => x.jobs));
  return (
    <section className="panel">
      <div className="panel-heading"><h2>Where booked jobs come from</h2></div>
      <p className="chart-caption">Jobs booked in the CRM over the last 12 months, by the source the office recorded. Canceled jobs aren&apos;t counted.</p>
      {list.map(([c, x]) => (
        <div className="comparison-row" key={c}>
          <div><span>{label(c)}</span><strong>{num(x.jobs)} jobs · {usd(x.revenue)}</strong></div>
          <div className="bar-track" aria-hidden="true"><span style={{ width: `${(x.jobs / max) * 100}%`, background: CHANNEL_COLORS[c] ?? OTHER }} /></div>
        </div>
      ))}
    </section>
  );
}

// One card per paid channel: what a new caller costs, and what a booked job costs.
export function ChannelCards({ rows, months }: { rows: FactRow[]; months: string[] }) {
  const t = sumBy(rows.filter((r) => months.includes(r.analysis_date.slice(0, 7))), (r) => r.channel);
  return (
    <section className="channel-cards" aria-label="Paid channels, last 12 months">
      {PAID_CHANNELS.map((c) => {
        const x = t.get(c) ?? empty();
        return (
          <div className="channel-card" key={c} style={{ borderTopColor: CHANNEL_COLORS[c] }}>
            <span>{label(c)}</span>
            <strong>{usd2(costPerLead(x))}</strong>
            <small>per new caller · {num(x.unique)} callers</small>
            <strong className="second">{usd2(costPerJob(x))}</strong>
            <small>per booked job · {num(x.jobs)} jobs</small>
            <small className="spend">{usd(x.spend)} spent</small>
          </div>
        );
      })}
    </section>
  );
}
