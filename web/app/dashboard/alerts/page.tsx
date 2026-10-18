import Link from "next/link";
import { periodFor, type Query } from "@/lib/reporting-period";
import { anomalies, CHANNEL_LABELS } from "@/lib/dashboard";
import { getDashboard } from "@/lib/dashboard-view";
import { Heading } from "../shared";
import { usd2 } from "../tables";

// worker/alerts.py opens one GitHub issue per alert, titled with the channel and dates.
const ISSUES = "https://github.com/johntran1626/lab-b-hvac-pipeline/issues";

export default async function Alerts({ searchParams }: { searchParams: Promise<Query> }) {
  const [all, q] = await Promise.all([getDashboard(), searchParams]);
  const p = periodFor(q, all.rows.map((r) => r.analysis_date).sort());
  // The 28-day baseline needs all history; show alerts that overlap the selected dates.
  const alerts = anomalies(all.rows).filter((a) => a.end >= p.start && a.start <= p.end);
  const spend = alerts.reduce((s, a) => s + a.spend, 0);
  return (
    <>
      <Heading range={p.preset} period={`${p.start} — ${p.end}`} title="Tracking alerts" description="Paid channels that kept spending while their platform reported zero leads." />
      <section className="alert-summary" aria-label="Alert summary">
        <div><span>Alerts</span><strong>{alerts.length}</strong><small>in the selected dates</small></div>
        <div><span>Spend during alerts</span><strong>{usd2(spend)}</strong><small>with 0 reported leads</small></div>
        <div><span>Checked</span><strong>Daily</strong><small>after every sync, 7:47pm CT</small></div>
      </section>
      <section className="panel">
        <h2>How an alert fires</h2>
        <p>A paid channel (Google Ads, Google Guaranteed, Meta) spends money for 3 or more days in a row with 0 reported leads, when its previous 28 days say it should have brought 7 or more in that stretch. Zero is then less than a 1 in 1,000 chance, so quiet winter days don&apos;t fire. It usually means broken tracking: a lead form, pixel or conversion setup. Each alert also opens an issue on GitHub. Rule: <code>worker/alerts.py</code>.</p>
      </section>
      <section className="alert-list" aria-live="polite">
        {alerts.length ? alerts.map((a) => (
          <article className="alert-card anomaly" key={`${a.channel}-${a.start}`}>
            <div className="alert-card-top"><span className="priority-pill needs_attention">Tracking alert</span></div>
            <h2>{CHANNEL_LABELS[a.channel]} reported 0 leads for {a.days} days ({a.start} to {a.end})</h2>
            <p>{CHANNEL_LABELS[a.channel]} spent <strong>{usd2(a.spend)}</strong> over those days. Its previous 28 days say it should have brought about <strong>{a.expected.toFixed(0)} leads</strong>. Check its lead tracking before paying for more days like this.</p>
            <div className="alert-meta">
              <a href={`${ISSUES}?q=${encodeURIComponent(`is:issue in:title Anomaly ${a.start}`)}`} target="_blank" rel="noreferrer">GitHub issue →</a>
              <Link href={`/dashboard/channels?channel=${a.channel}&month=${a.start.slice(0, 7)}&metric=reported_leads&range=${p.preset}#analysis`}>See the numbers →</Link>
            </div>
          </article>
        )) : (
          <div className="panel empty"><h3>No alerts in these dates</h3><p>No paid channel had an unusual run of zero-lead days.</p></div>
        )}
      </section>
    </>
  );
}
