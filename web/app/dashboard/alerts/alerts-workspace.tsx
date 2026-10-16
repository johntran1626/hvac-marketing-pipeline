"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { isAlertOverdue, type AlertCategory, type AlertPriority, type AlertRecord, type AlertStatus } from "@/lib/alerts";

const priorityLabel: Record<AlertPriority, string> = { critical: "Critical", needs_attention: "Needs Attention", informational: "Informational" };
const categoryLabel: Record<AlertCategory, string> = { data_quality: "Data quality", attribution: "Attribution", metric_definition: "Metric definition", freshness: "Freshness" };
const statusLabel: Record<AlertStatus, string> = { open: "Open", in_progress: "In progress", resolved: "Resolved" };

export default function AlertsWorkspace({ alerts }: { alerts: AlertRecord[] }) {
  const [view, setView] = useState<"all" | "mine">("all");
  const [priority, setPriority] = useState("all");
  const [status, setStatus] = useState("all");
  const [category, setCategory] = useState("all");
  const [assignee, setAssignee] = useState("all");
  const [dateQuery, setDateQuery] = useState("");
  const [sort, setSort] = useState("priority");
  const [selected, setSelected] = useState<AlertRecord | null>(null);
  const [checked, setChecked] = useState<Record<string, boolean>>({});
  const filtered = useMemo(() => alerts.filter((a) => (view === "all") && (priority === "all" || a.priority === priority) && (status === "all" || a.status === status) && (category === "all" || a.category === category) && (assignee === "all" || (assignee === "unassigned" && !a.assignee)) && (!dateQuery || a.evidence.some((e) => e.period.includes(dateQuery)))).sort((a, b) => {
    if (sort === "activity") return b.updatedAt.localeCompare(a.updatedAt);
    if (sort === "deadline") return (a.dueDate ?? "9999").localeCompare(b.dueDate ?? "9999");
    const rank: Record<AlertPriority, number> = { critical: 0, needs_attention: 1, informational: 2 };
    return rank[a.priority] - rank[b.priority];
  }), [alerts, view, priority, status, category, assignee, dateQuery, sort]);
  const counts = useMemo(() => ({ open: alerts.filter((a) => a.status === "open").length, inProgress: alerts.filter((a) => a.status === "in_progress").length, resolved: alerts.filter((a) => a.status === "resolved").length, attention: alerts.filter((a) => a.priority === "needs_attention").length, critical: alerts.filter((a) => a.priority === "critical").length }), [alerts]);
  return <>
    <section className="alert-summary" aria-label="Alert summary">
      <div><span>Open</span><strong>{counts.open}</strong><small>{counts.inProgress} in progress · {counts.resolved} resolved</small></div>
      <div><span>Needs attention</span><strong>{counts.attention}</strong><small>Investigation required</small></div>
      <div><span>Critical</span><strong>{counts.critical}</strong><small>Verified evidence threshold</small></div>
    </section>
    <section className="alert-toolbar panel">
      <div className="alert-tabs" role="tablist" aria-label="Alert scope"><button className={view === "all" ? "active" : ""} onClick={() => setView("all")} role="tab" aria-selected={view === "all"}>All alerts</button><button className={view === "mine" ? "active" : ""} onClick={() => setView("mine")} role="tab" aria-selected={view === "mine"} disabled>My alerts <span>Sign-in required</span></button></div>
      <div className="alert-filters"><label>Priority<select value={priority} onChange={(e) => setPriority(e.target.value)}><option value="all">All priorities</option><option value="critical">Critical</option><option value="needs_attention">Needs Attention</option><option value="informational">Informational</option></select></label><label>Status<select value={status} onChange={(e) => setStatus(e.target.value)}><option value="all">All statuses</option><option value="open">Open</option><option value="in_progress">In progress</option><option value="resolved">Resolved</option></select></label><label>Assignee<select value={assignee} onChange={(e) => setAssignee(e.target.value)}><option value="all">All assignees</option><option value="unassigned">Unassigned</option></select></label><label>Category<select value={category} onChange={(e) => setCategory(e.target.value)}><option value="all">All categories</option>{Object.entries(categoryLabel).map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label><label>Evidence date<input type="search" value={dateQuery} onChange={(e) => setDateQuery(e.target.value)} placeholder="YYYY-MM"/></label><label>Sort by<select value={sort} onChange={(e) => setSort(e.target.value)}><option value="priority">Priority</option><option value="deadline">Deadline</option><option value="activity">Recent activity</option></select></label></div>
      <p className="alert-readonly"><span className="status-dot"/> Read-only evidence alerts · assignments, status changes, notes, and resolution require authenticated Supabase workflows.</p>
    </section>
    <section className="alert-list" aria-live="polite">{filtered.length ? filtered.map((alert) => <article className={`alert-card ${alert.priority}`} key={alert.id} onClick={() => setSelected(alert)} tabIndex={0} onKeyDown={(e) => e.key === "Enter" && setSelected(alert)}>
      <div className="alert-card-top"><span className={`priority-pill ${alert.priority}`}>{priorityLabel[alert.priority]}</span><span className="alert-status">{statusLabel[alert.status]}</span></div><h2>{alert.title}</h2><p>{alert.explanation}</p><div className="alert-meta"><span>{categoryLabel[alert.category]}</span><span>{alert.assignee ? `Assigned to ${alert.assignee}` : "Unassigned"}</span><span>{alert.dueDate ? `Due ${alert.dueDate}` : "No due date configured"}</span>{isAlertOverdue(alert) && <span className="overdue-label">Overdue</span>}</div><button className="text-link" onClick={(e) => { e.stopPropagation(); setSelected(alert); }}>Review investigation →</button>
    </article>) : <div className="panel empty"><h3>No alerts match these filters</h3><p>Filters only apply to evidence returned by the current read-only source.</p></div>}</section>
    {selected && <div className="alert-drawer-backdrop" role="presentation" onClick={() => setSelected(null)}><aside className="alert-drawer" role="dialog" aria-modal="true" aria-labelledby="alert-detail-title" onClick={(e) => e.stopPropagation()}><button className="drawer-close" onClick={() => setSelected(null)} aria-label="Close alert details">×</button><span className={`priority-pill ${selected.priority}`}>{priorityLabel[selected.priority]}</span><h2 id="alert-detail-title">{selected.title}</h2><p>{selected.explanation}</p><div className="drawer-grid"><div><strong>Potential impact</strong><p>{selected.impact}</p></div><div><strong>Owner</strong><p>{selected.assignee ?? "Unassigned · routing rule not configured"}</p></div><div><strong>Status</strong><p>{statusLabel[selected.status]} · changes require sign-in</p></div><div><strong>Due date</strong><p>{selected.dueDate ?? "Unavailable · SLA settings require approval"}{isAlertOverdue(selected) && <span className="overdue-label"> · Overdue</span>}</p></div></div><h3>Verified evidence</h3><div className="evidence-list">{selected.evidence.map((e) => <div key={e.label}><span>{e.label}</span><strong>{e.value}</strong><small>{e.period}</small></div>)}</div><h3>Investigation checklist</h3><div className="checklist">{selected.checklist.map((item) => <label key={item.id}><input type="checkbox" checked={checked[`${selected.id}:${item.id}`] ?? item.completed} onChange={(e) => setChecked((old) => ({ ...old, [`${selected.id}:${item.id}`]: e.target.checked }))}/><span>{item.label}</span></label>)}</div><h3>Recommended investigation</h3><ol>{selected.investigation.map((step) => <li key={step}>{step}</li>)}</ol><h3>Investigation notes</h3><p className="disabled-field">Notes are unavailable until an authenticated assignment workflow is connected.</p><h3>Resolution details</h3><p className="disabled-field">No resolution recorded. Resolution requires a Manager/Admin reason and an append-only audit event.</p><Link className="drawer-data-link" href={selected.sourceLink}>Open filtered evidence →</Link><div className="disabled-actions"><button disabled>Assign owner</button><button disabled>Change status</button><button disabled>Resolve with reason</button></div><h3>Activity history</h3><div className="history">{selected.history.map((h) => <div key={h.at}><strong>{h.action}</strong><span>{h.actor} · {new Date(h.at).toLocaleString("en-US")}</span></div>)}</div></aside></div>}
  </>;
}
