import Link from "next/link";
import { freshness, type FactRow } from "@/lib/dashboard";
import { getDashboard } from "@/lib/dashboard-view";

const SOURCE_LABELS: Record<string, string> = {
  google_ads: "Google Ads",
  meta_ads: "Meta",
  lsa: "Google Guaranteed",
  call_tracking: "Call tracking",
  crm: "CRM jobs",
};
const ct = (iso: string) =>
  new Date(iso).toLocaleString("en-US", { timeZone: "America/Chicago", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });

// Freshness badge: is every source loaded through yesterday (Central), and when the daily sync last rebuilt the facts.
export function Freshness({ rows, expected, range, compact = false }: { rows: FactRow[]; expected: string; range?: string; compact?: boolean }) {
  const fresh = [...freshness(rows).entries()];
  const stale = fresh.filter(([, f]) => f.dataThrough < expected);
  const synced = fresh.map(([, f]) => f.syncedAt).sort().at(-1);
  return (
    <div className="fresh">
      <span className={`fresh-pill ${!fresh.length || stale.length ? "behind" : "current"}`}>
        {!fresh.length ? "No data" : stale.length ? "Data behind" : "Data current"}
      </span>
      <span>
        {stale.length
          ? `${stale.map(([s]) => SOURCE_LABELS[s] ?? s).join(", ")} not loaded through ${expected} yet.`
          : `Every source loaded through ${expected} (yesterday, Central).`}
        {synced && ` Last refreshed ${ct(synced)} CT.`}
      </span>
      {!compact && (
        <ul>
          {fresh.map(([s, f]) => (
            <li key={s} className={f.dataThrough < expected ? "late" : ""}>
              {SOURCE_LABELS[s] ?? s}: through {f.dataThrough}
            </li>
          ))}
        </ul>
      )}
      <Link href={`/dashboard/data${range ? `?range=${range}` : ""}`}>How the data is loaded →</Link>
    </div>
  );
}

export async function Heading({ title, description, period, range }: { title: string; description: string; compact?: boolean; period?: string; range?: string }) {
  const d = await getDashboard();
  return (
    <>
      <div className="eyebrow">MARKETING PERFORMANCE</div>
      <div className="page-heading">
        <div>
          <h1>{title}</h1>
          <p>{description}</p>
        </div>
        <span className="period">{period || d.period}</span>
      </div>
      {d.failed ? (
        <div className="notice">
          <span className="status-dot" />
          <div>
            <strong>Dashboard data unavailable</strong>
            <p>The dashboard could not read its data. Check /health.</p>
          </div>
        </div>
      ) : (
        <Freshness rows={d.rows} expected={d.expected} range={range} compact />
      )}
    </>
  );
}
export function Empty({ text }: { text: string }) {
  return (
    <div className="empty">
      <span className="empty-symbol">—</span>
      <h3>No data</h3>
      <p>{text}</p>
    </div>
  );
}
