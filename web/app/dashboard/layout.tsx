import { Suspense } from "react";
import Nav from "./nav";
import Link from "next/link";
import "./dashboard.css";
export default function Layout({ children }: { children: React.ReactNode }) {
 return <div className="wren"><aside className="sidebar"><Link className="brand" href="/dashboard"><span className="brand-mark">W</span><span>WREN<small>AIR & HEAT</small></span></Link><p className="nav-label">BUSINESS OVERVIEW</p><Suspense fallback={<nav aria-label="Dashboard"><Link href="/dashboard">Overview</Link><Link href="/dashboard/channels">Channels</Link><Link href="/dashboard/tables">Tables</Link><Link href="/dashboard/data">Data coverage</Link><Link href="/dashboard/alerts">Alerts</Link></nav>}><Nav/></Suspense><div className="sidebar-foot">Marketing dashboard<small>Updated every evening</small></div></aside><div className="workspace"><main id="top" tabIndex={-1} className="dashboard-main">{children}</main><footer className="dashboard-footer"><a className="back-top" href="#top">Back to top ↑</a><br/>Wren Air &amp; Heat marketing dashboard<br/>Google Ads, Google Guaranteed and calls use Central dates. Meta uses Pacific account dates.</footer></div></div>;
}
