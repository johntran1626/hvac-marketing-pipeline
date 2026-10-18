"use client";
import { useTransition } from 'react';
import { useRouter } from 'next/navigation';
import { presets, type Period } from '@/lib/reporting-period';
export default function PeriodSelect({value}:{value:Period['preset']}) { const router=useRouter(); const [pending,startTransition]=useTransition(); return <label className="date-select">Reporting period<select aria-label="Reporting period" aria-busy={pending} disabled={pending} value={value} onChange={e=>startTransition(()=>router.push(`/dashboard?range=${e.target.value}`))}>{Object.entries(presets).map(([v,label])=><option key={v} value={v}>{label}</option>)}</select><span className="sr-only" role="status">{pending ? "Updating reporting period" : "Reporting period loaded"}</span></label>; }
