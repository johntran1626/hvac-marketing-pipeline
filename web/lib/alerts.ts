import type { FactRow } from "./dashboard";
import { format, total, metricRows } from "./dashboard-view";

export type AlertPriority = "critical" | "needs_attention" | "informational";
export type AlertStatus = "open" | "in_progress" | "resolved";
export type AlertCategory = "data_quality" | "attribution" | "metric_definition" | "freshness";

export type AlertChecklistItem = { id: string; label: string; completed: boolean };
export type AlertEvidence = { label: string; value: string; period: string };
export type AlertRecord = {
  id: string;
  fingerprint: string;
  category: AlertCategory;
  title: string;
  explanation: string;
  impact: string;
  investigation: string[];
  checklist: AlertChecklistItem[];
  evidence: AlertEvidence[];
  priority: AlertPriority;
  status: AlertStatus;
  assignee: null;
  dueDate: null;
  createdAt: string;
  updatedAt: string;
  sourceLink: string;
  history: { action: string; actor: string; at: string }[];
};

export function isAlertOverdue(alert: AlertRecord, now = new Date()) {
  return alert.status !== "resolved" && !!alert.dueDate && new Date(alert.dueDate).getTime() < now.getTime();
}

const period = (rows: FactRow[]) => {
  const dates = rows.map((r) => r.analysis_date).sort();
  return dates.length ? `${dates[0]} — ${dates.at(-1)}` : "Selected reporting window";
};

function base(input: Omit<AlertRecord, "id" | "createdAt" | "updatedAt" | "history">): AlertRecord {
  const at = new Date().toISOString();
  return {
    ...input,
    id: `al_${input.fingerprint}`,
    createdAt: at,
    updatedAt: at,
    history: [{ action: "Created from current read-only evidence", actor: "System", at }],
  };
}

export function deriveAlerts(rows: FactRow[], expected: string): AlertRecord[] {
  if (!rows.length) return [];
  const out: AlertRecord[] = [];
  const dates = new Set(rows.map((r) => r.analysis_date));
  const range = period(rows);
  const phoneRows = metricRows(rows, "unique_leads");
  const callRows = metricRows(rows, "calls");
  const phone = total(phoneRows, "unique_leads");
  const calls = total(callRows, "calls");

  out.push(base({
    fingerprint: "coverage-daily-completeness-v1",
    category: "data_quality",
    title: "Daily completeness is not verified",
    explanation: `${rows.length.toLocaleString()} source records are visible across ${dates.size} date labels. fact_marketing_daily does not expose an ingestion manifest, so the returned rows cannot prove that every expected day was delivered.`,
    impact: "Totals and period comparisons describe observed records and may understate activity when a source day is absent.",
    investigation: ["Compare each source's delivered dates with its upstream report.", "Review the latest successful sync and any failed or partial runs.", "Reconcile source totals before using a performance change to make a budget decision."],
    checklist: [
      { id: "coverage-upstream", label: "Compare delivered dates with upstream reports", completed: false },
      { id: "coverage-sync", label: "Review sync history for failed or partial runs", completed: false },
      { id: "coverage-reconcile", label: "Record the reconciliation result", completed: false },
    ],
    evidence: [{ label: "Records returned", value: rows.length.toLocaleString(), period: range }, { label: "Date labels", value: dates.size.toLocaleString(), period: range }, { label: "Freshness target", value: expected, period: "Central time" }],
    priority: "needs_attention",
    status: "open",
    assignee: null,
    dueDate: null,
    sourceLink: "/dashboard/data#definitions",
  }));

  if (phone !== null && calls !== null && calls > phone) out.push(base({
    fingerprint: "calls-vs-qualifying-phone-leads-v1",
    category: "attribution",
    title: "Tracked calls exceed qualifying phone leads",
    explanation: `${format(calls, "calls")} tracked calls were recorded alongside ${format(phone, "unique_leads")} qualifying phone leads. The source defines a qualifying lead as a first-time caller lasting at least 30 seconds.`,
    impact: "The difference identifies records with different definitions; it does not establish lost opportunities or a performance problem.",
    investigation: ["Check the first-time-caller definition and repeat-caller records.", "Review calls shorter than 30 seconds.", "Reconcile paid-source attribution for the selected dates before calculating CPL."],
    checklist: [
      { id: "calls-definition", label: "Confirm the first-time caller rule", completed: false },
      { id: "calls-duration", label: "Review short-call records", completed: false },
      { id: "calls-attribution", label: "Reconcile paid-source attribution", completed: false },
    ],
    evidence: [{ label: "Tracked calls", value: format(calls, "calls"), period: range }, { label: "Qualifying phone leads", value: format(phone, "unique_leads"), period: range }],
    priority: "needs_attention",
    status: "open",
    assignee: null,
    dueDate: null,
    sourceLink: "/dashboard/channels?metric=unique_leads#analysis",
  }));

  const google = total(rows.filter((r) => r.source_platform === "google_ads"), "reported_leads");
  if (google !== null && !Number.isInteger(google)) out.push(base({
    fingerprint: "fractional-platform-conversions-v1",
    category: "metric_definition",
    title: "Platform conversions include a fractional Google Ads total",
    explanation: `${format(google, "reported_leads")} Google Ads conversions are present in the selected records. Google Ads conversions are source-reported modeled values and may be fractional.`,
    impact: "This metric is not a count of unique people and should not be added to qualifying phone leads.",
    investigation: ["Review the conversion actions included by the upstream Google Ads report.", "Compare the selected reporting dates with call attribution.", "Keep platform conversions and phone leads separate in any owner report."],
    checklist: [
      { id: "conversion-actions", label: "Review included conversion actions", completed: false },
      { id: "conversion-period", label: "Confirm reporting-date alignment", completed: false },
      { id: "conversion-definition", label: "Document the metric definition", completed: false },
    ],
    evidence: [{ label: "Google Ads conversions", value: format(google, "reported_leads"), period: range }],
    priority: "informational",
    status: "open",
    assignee: null,
    dueDate: null,
    sourceLink: "/dashboard/channels?channel=google_ads&metric=reported_leads#analysis",
  }));
  return out;
}
