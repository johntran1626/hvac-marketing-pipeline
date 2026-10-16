import { periodFor, inPeriod, monthsBetween, type Query } from "@/lib/reporting-period";
import { getDashboard } from "@/lib/dashboard-view";
import { Heading } from "../shared";
import AlertsWorkspace from "./alerts-workspace";
import { deriveAlerts } from "@/lib/alerts";
export default async function Alerts({searchParams}:{searchParams:Promise<Query>}){
 const [all,q]=await Promise.all([getDashboard(),searchParams]);const p=periodFor(q,all.rows.map(r=>r.analysis_date).sort());const d={...all,rows:all.rows.filter(r=>inPeriod(r.analysis_date,p)),months:monthsBetween(p.start,p.end)};
 
 return <><Heading range={p.preset} period={`${p.start} — ${p.end} · observed records`} title="Alerts workspace" description="Evidence-based issues, ownership, and the next investigation step."/><AlertsWorkspace alerts={deriveAlerts(d.rows, d.expected)}/></>;
}
