export const presets = { today: 'Today', wtd: 'This Week (WTD)', mtd: 'This Month (MTD)', ytd: 'This Year (YTD)', observed: 'Recorded history' };
export type Query = Record<string, string | string[] | undefined>;
export type Period = { preset: keyof typeof presets; start: string; end: string };
export function shiftDay(date: string, days: number) { const d = new Date(date + 'T12:00:00Z'); d.setUTCDate(d.getUTCDate() + days); return d.toISOString().slice(0,10); }
export function lastYear(date: string) { const [y,m,d] = date.split('-').map(Number); return `${y-1}-${String(m).padStart(2,'0')}-${String(Math.min(d,new Date(Date.UTC(y-1,m,0)).getUTCDate())).padStart(2,'0')}`; }
export function periodFor(query: Query, dates: string[], now = new Date()): Period {
 const today = new Intl.DateTimeFormat('en-CA',{timeZone:'America/Chicago'}).format(now);
 const preset = typeof query.range === 'string' && Object.hasOwn(presets,query.range) ? query.range as keyof typeof presets : 'ytd';
 const weekday = new Date(today+'T12:00:00Z').getUTCDay();
 const start = preset === 'today' ? today : preset === 'wtd' ? shiftDay(today,-((weekday+6)%7)) : preset === 'mtd' ? today.slice(0,7)+'-01' : preset === 'ytd' ? today.slice(0,4)+'-01-01' : dates[0] || today;
 return {preset,start,end:preset === 'observed' ? dates.at(-1) || today : today};
}
export function monthsBetween(start:string,end:string) { const months:string[]=[]; const d=new Date(start.slice(0,7)+'-01T12:00:00Z'); while(d.toISOString().slice(0,7)<=end.slice(0,7)){months.push(d.toISOString().slice(0,7));d.setUTCMonth(d.getUTCMonth()+1);}return months; }
export function inPeriod(date:string,p:Pick<Period,'start'|'end'>) { return date>=p.start && date<=p.end; }
export function comparisons(p:Period) {
 const end=lastYear(p.end); const start=lastYear(p.start);
 const weekEnd=shiftDay(p.end,-364);
 const weekStart=shiftDay(weekEnd,-((new Date(weekEnd+'T12:00:00Z').getUTCDay()+6)%7));
 return [{label:'LY full matching period',start:p.preset==='wtd'?weekStart:start,end:p.preset==='mtd'?new Date(Date.UTC(Number(end.slice(0,4)),Number(end.slice(5,7)),0)).toISOString().slice(0,10):p.preset==='ytd'?end.slice(0,4)+'-12-31':p.preset==='wtd'?shiftDay(weekStart,6):end}, {label:'LY WTD',start:weekStart,end:weekEnd}, {label:'LY MTD',start:end.slice(0,7)+'-01',end}, {label:'LY YTD',start:end.slice(0,4)+'-01-01',end}];
}

export function matchingPrior(p:Period) {
 if(p.preset==='observed') return null;
 if(p.preset==='wtd') return {start:shiftDay(p.start,-364),end:shiftDay(p.end,-364)};
 return {start:lastYear(p.start),end:lastYear(p.end)};
}
