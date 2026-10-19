"use client";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
export default function Nav() {
 const path = usePathname();
 const range = useSearchParams().get("range");
 return <nav aria-label="Dashboard">{[["/dashboard","Overview"],["/dashboard/channels","Channels"],["/dashboard/tables","Tables"],["/dashboard/data","Data coverage"],["/dashboard/alerts","Alerts"]].map(([href,label]) => <Link key={href} href={`${href}${range ? `?range=${encodeURIComponent(range)}` : ""}`} aria-current={path === href ? "page" : undefined}>{label}</Link>)}</nav>;
}
