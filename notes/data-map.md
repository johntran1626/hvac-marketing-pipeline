# Data map: Diane's questions → snapshot data (Issue #1)

For Ruslan (#2, calculations) and Kelsey (#3, memo). Every number below comes from
`python3 scripts/check_diane_claims.py` (section number in brackets). Files are in
`data/snapshot-2026-09-23/`, covering 2024-10-01 to 2026-09-22.

## The five files and how they connect

| File | One row per | Time zone | Joins to |
|---|---|---|---|
| `google_ads_insights.csv` | day × ad group | `date` = Central | `calls.campaign_id` = `campaign_id` (Google Ads calls only) |
| `meta_insights.csv` | day × ad set | `date_start` = **Pacific** | `calls` where `source = meta` (by date only) |
| `lsa_leads.csv` | LSA lead | `lead_created_at` = **UTC** | `calls` where `source = google_lsa` (by time only, no shared id) |
| `calls.csv` | phone call | `started_at` = **UTC** | `caller_hash` links repeat callers; `campaign_id` links to Google |
| `crm_jobs.csv` | job (latest state) | Central, with -05/-06 offset | **No id joins to any ad file.** Only `lead_source` (free text) |

**Big gap:** there is no key linking a call or lead to a CRM job. Ad → booked job can
only be estimated from `lead_source` text or matched by date. Say so in the memo.

## Diane's claims: do they reproduce?

| Diane says | Snapshot | Reproduces? | Why it may still be wrong |
|---|---|---|---|
| Google 1,209 leads at $24.00 | 1,208.6 conversions, $29,004.33 [1] | Yes | `conversions` is Google's count and fractional. Not the same as calls or unique callers |
| Brand best at $8.44 | Brand (`20814455901`) $8.44 [1] | Yes | Brand = people already searching "Wren". Most would likely call anyway. Check how many are `first_time_caller = false` |
| 1,388 jobs vs 1,245 | 1,388 / 1,245 by `created_at` [4] | Yes | Includes maintenance and repeat customers. Not proof the agency's ads did it |
| Meta zero leads Aug 4-10, $291.15 | 0 leads, $291.15, clicks kept coming [3] | Yes | Clicks stayed steady and some calls hit the Meta number [3]. Looks like **tracking broke**, not Meta dying. To verify |
| 77 jobs turned away from Katy | 77 canceled jobs in Katy zips in 2026 [5] | Yes | Also 78 in 2025 and 26 in late 2024. A steady trickle, not growth |

## Question by question

### 1. What is actually driving the phones?
- **Files:** `calls.csv` (main), `google_ads_insights.csv`, `meta_insights.csv`, `lsa_leads.csv`, `crm_jobs.csv`
- **Columns:** `source`, `campaign_id`, `caller_hash`, `first_time_caller`, `duration_sec`, `started_at`
- **Calculate:** calls by `source`. Then **unique, first-time, real (not short)** callers per source. Compare with what each platform reports (Google `conversions`, Meta `leads`, LSA rows).
- **Starting facts:** 29,757 calls but only 13,580 unique callers. 17,665 calls are `direct` and 5,459 `gbp` (Google listing, free). 3,608 calls are under 30 seconds [7].

### 2. Next 30 days on the current budget, per campaign
- **Files:** `google_ads_insights.csv` (campaign + ad group), `meta_insights.csv` (campaign + ad set), `lsa_leads.csv`, `calls.csv`
- **Calculate:** true cost per real lead per campaign/ad set = spend ÷ unique first-time callers (or charged LSA leads). Last 30–90 days, not all-time.
- **Names:** Google campaigns: Brand - Wren Air & Heat, AC Repair - Houston / Summer AC Repair (**same id `20814455917`, two names**: group by id [2]), Heating Repair - Houston, AC Replacement. Meta campaigns: Tune-Up Promo - Lead Form (3 ad sets), Retargeting - Site Visitors (3 ad sets).

### 3. What would you refuse to do?
- Diane's plan: double budget Nov–Feb, cut Meta, open a Katy office.
- **Data for "double winter budget":** winter vs summer completed jobs/day (`crm_jobs`), and Heating Repair's winter cost per lead (summer was $185/conversion [1]). Do ads even work in winter?
- **"Cut Meta":** the Aug 4-10 tracking question above, plus Meta's true cost per unique caller.
- **"Katy office":** Katy zips 77449, 77450, 77493, 77494 (outside the service-area list in the data README). All 181 jobs there are `canceled` [5].

### 4. What number would tell you you were wrong?
- Pick a metric we can pull **weekly from the API**, e.g. cost per unique first-time caller by channel, or completed jobs/day.
- Needs: the metric, a threshold (from the history above), and a check date.

## Data traps to handle (all of these feed the M3 eval)
1. **Time zones:** Google = Central, Meta = Pacific, calls/LSA = UTC. A call at 11pm Central lands on the next UTC date. Convert everything to Central before joining by day [9].
2. **Renamed campaign:** `20814455917` has two names. Group by `campaign_id`, never by name [2].
3. **Fractional Google conversions:** not a lead count [1].
4. **Repeat callers:** same `caller_hash` many times. Count unique and `first_time_caller` [7].
5. **Short calls:** 3,608 under 30 seconds. Decide a cutoff and write it down [7].
6. **LSA credits:** 222 `CREDITED` leads were refunded, and 204 were `NOT_CHARGED` [6]. Don't count refunded cost. Credits can arrive up to 30 days later (`docs/API.md`, Numbers that change).
7. **Restated days:** the last 7 days of Google conversions and Meta leads can still change (`docs/API.md`).
8. **CRM `lead_source` is messy free text:** 59 spellings ("google", "Google", "googel", "GOOGLE LSA", "fb", "facebok"...), 817 blank, 341 "?" [8]. It needs a mapping table to channels.
9. **Katy zips** are outside the service area. Exclude them from service-area totals [5].
10. **Meta Aug 4-10:** zero reported leads while clicks continued [3]. Most likely a tracking gap. Don't treat it as real zero.

## Not done here (owned by #2)
Winter vs summer jobs per day, true cost per lead per channel, brand repeat-caller share, and the 30-day plan numbers.
