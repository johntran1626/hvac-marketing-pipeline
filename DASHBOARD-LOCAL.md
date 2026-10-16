# Wren dashboard — local review implementation

Updated October 16, 2026. Scope: `/private/tmp/wren-dashboard-local` only. User instructions are authoritative; the linked Notion decision register was read for context. Existing uncommitted prototype work was preserved and extended. No commit, push, merge, deployment, migration, backend write, permission change, or other worktree edit was performed.

## Review locally

Existing Next development server remains on **http://127.0.0.1:3100/dashboard**. Its PID at inspection was 14222 and its working directory was this worktree's `web` directory. No competing server was started. `ps` process enumeration was sandbox-denied; `lsof` verified the existing listener and working directory. The four routes remain `/dashboard`, `/dashboard/channels`, `/dashboard/data`, `/dashboard/alerts`.

The existing local publishable configuration is used; no environment values were copied or exposed. Run commands from `web`: `npm run lint`, `npx tsc --noEmit`, `npm run build -- --webpack`. If a restart is needed later, use `npm run dev -- --hostname 127.0.0.1 --port 3100` after stopping only this worktree's server.

## Implemented

- Overview upper-right Today, WTD, MTD, YTD and Recorded history selector. YTD is the default. Selected dates drive all four KPIs, both charts, spend-share insight, prior-year evidence and analysis/coverage links. Navigation preserves the date preset. Loading state is announced and prevents duplicate selection during navigation.
- Central calendar dates (`America/Chicago`), Monday week start, inclusive bounds and partial-current-period warnings. Meta's existing Pacific account-date labels are explicitly preserved, not silently converted. Current dates use the clock, not the latest imported day. Missing Today records remain unavailable.
- All accessible history retained, replacing the previous trailing-year truncation. Calendar months include first-day records and missing buckets. LY full calendar reference, LY WTD, LY MTD and LY YTD use actual source rows. WTD uses 52 weeks earlier to match weekdays; calendar anniversaries clamp February 29 to February 28. Full LY totals are not compared as if they were to-date totals. Observed differences are explicitly unverified and not trends. Historical cells disclose observed date-label counts and absent metric sources; even all date labels do not certify delivery.
- Redundant top banner removed; sidebar logo, navigation and page h1 retained. Four KPIs and two charts precede the larger Google Ads insight. One compact number-backed investigation sentence sits above the spend chart. Desktop and mobile maintain the navy/teal styling; charts scroll horizontally rather than becoming illegible.
- Channels has a compact heading, then filters, selected KPI/charts, comparisons and lower detail tables. Date range, month, channel, actual campaign, campaign type and metric scopes are consistent. Chart drill-downs preserve campaign/channel/type/date; metric exploration also preserves the selected month. Selecting phone leads shows tracked calls as its companion rather than duplicating the chart. Actual campaign names come from public fact rows.
- Apply Filters: white hover fill, dark-green outline/text, approximately one-pixel contraction per edge and two-pixel downward pressed translation. Reset and Alerts link hover changes, focus-visible controls, keyboard operation and reduced-motion rules.
- Coverage evidence ledger sorts every column ascending/descending with `aria-sort`, accessible buttons and live sort announcements. Numeric values sort numerically, period/watermark/refresh dates chronologically, statuses by explicit rank, missing values last in either direction. Only public aggregate evidence is serialized to the sortable client component.
- Back to top on all pages. Alerts include selected-window missing sources, recorded qualifying-phone/call counts and measurable investigations.
- Channel-level CPL evidence includes source-owned spend, platform conversions, qualifying phone counts and exact overlapping date-label counts. Each channel's blocked state explains missing evidence. Common reconciliation steps require exact dates, account/campaign attribution, timezone alignment, delivery manifests, source-total differences and caller deduplication.
- Read-only pagination orders every field of the database's unique grain. Before/after row counts and latest refresh watermark reject reads spanning detectable rebuilds; partial loads are never presented as a successful full result. This is a guard, not a transactional snapshot guarantee against arbitrary edits that preserve count and watermark.
- Source-owned metric aggregation retained. Null/blank numeric values remain unavailable; absent unrelated-source metrics do not contribute structural zeros. Unknown/unattributed labels stay explicit. Existing stored-zero/coalescing limitations remain disclosed.

## Evidence-dependent / blocked

**True or qualified observed CPL remains blocked, deliberately.** The public facts do not independently verify that paid spend and qualifying callers refer to the same attributed cohort. Meta also has a Pacific/Central date mismatch. Overlapping date labels alone are insufficient. No CPL ratio, new numerical business data, attribution fill, complete-coverage claim or performance-cause claim was invented.

The prototype's prior October 16 read-only inspection reported no visible sync-state rows or usable raw reconciliation evidence; the repository's source SQL and access restrictions corroborate the limits. This turn attempted fresh read-only checks, but direct tool networking failed; that earlier observation was not represented as a new successful audit. An inaccessible source does not mean an empty underlying table.

Historical totals are available, but full comparable coverage is **unverified**. Missing date labels may represent absent activity records or missing delivery; they are not labeled confirmed ingestion gaps. Business timezone configuration was not changed. Arbitrary custom dates were optional and are not implemented; month + preset filtering and recorded history are available.

## Validation

- PASS: `npm run lint`.
- PASS: `npx tsc --noEmit`.
- PASS: `npm run build -- --webpack`, with all four dashboard routes dynamic. An initial missing-Suspense build error was fixed and the build rerun successfully.
- PASS: calendar-only assertions for leap-day clamping, Central midnight/year rollover, Sunday-to-Monday WTD, DST date, month/year boundaries, inclusive ranges, invalid preset fallback and LY weekday alignment. No business fixtures were used.
- PASS: Chrome rendered all four routes with live records on the existing port 3100 server, including after the pagination guard was added.
- PASS: browser Today → WTD → MTD → YTD selections and context-preserving navigation. Today was unavailable, WTD showed $1,465.78 / 27.7 conversions / 41 qualifying phone leads / 202 calls; MTD showed $6,455.51 / 130.93 / 132 / 648; YTD showed $115,102.85 / 3,536.72 / 3,027 / 13,345. These are observed source-backed UI values at review time, not complete-business claims.
- PASS: browser Google Ads + Brand + MTD + platform-conversions filtering showed 41.67 conversions, $824.62 spend and 3 qualifying phone leads; chart links retained the scope. Actual campaign dropdown was populated from real source records.
- PASS: all eight ledger headers toggled ascending/descending; Enter activated sorting and `aria-sort` updated. Real MTD numeric values sorted 14 → 33 → 83.93 → 132 → 648 → 725.79 → 996.48 → 4,733.24, and reversed correctly. Back to top navigated to the page's top anchor. Mixed-null ordering is implemented/code-reviewed, not claimed as a live mixed-null test.
- PASS: visual review at 1440×900 showed four KPIs and both chart panels before scrolling, with larger spend insight below. At 390×844, cards stacked in two columns and charts retained readable width with internal horizontal scrolling. Viewport override was reset afterward. At the normal approximately 1337×728 viewport, both chart plots were visible; lower chart controls can extend below the fold.
- PARTIAL: browser route rendering verified, but the requested direct HTTP status matrix is blocked in the tool sandbox (`EPERM` on localhost). An earlier audit attempt reached Overview but used obsolete trailing-year expectations; it was corrected, not counted as a pass. Independent Supabase audit attempts subsequently failed with `fetch failed`. No successful final HTTP/reconciliation run is claimed.
- `web/wren-audit.mjs` now provides repeatable, read-only source reconciliation of all presets, KPI/chart/LY totals, channel/campaign filters, route HTTP statuses and accessible evidence counts when networking permits. It contains no business fixture values and makes no writes. Run `node wren-audit.mjs` from `web` in an environment allowed to reach the existing server and Supabase.

User visual review is still pending. No production readiness or certified CPL/comparison coverage is asserted.

Final browser follow-up: Recorded history spans 2024-10-01 through 2026-10-15. Chronological ledger sorting put 2024-10 first ascending and 2026-10 first descending. The final lint, TypeScript and webpack build all passed after the last code changes. `lsof` reconfirmed the original PID 14222 still listening on 127.0.0.1:3100.
