# Issue #2 contingency analysis: answers and source evidence

This note packages the analysis required by Issue #2 so another teammate can reproduce it from the snapshot without relying on the M1 memo.

Run:

`python3 scripts/check_issue2_evidence.py`

Source data: `data/snapshot-2026-09-23/*.csv`. The snapshot covers data through 2026-09-22 for the ad/call/CRM analysis used in M1. Time-zone handling follows `docs/API.md`: Google account dates are Central, Meta account dates are Pacific, and call/LSA timestamps are UTC.

For recent "real lead" comparisons, this analysis uses the M1 definition already documented in `memo/read.md`: a **unique first-time caller with a call duration of at least 30 seconds**, evaluated over 2026-08-24 through 2026-09-22 after converting timestamps to Central time.

## 1. Spend by channel and campaign

Full-snapshot paid spend:

- Google Ads: **$190,221.74**
- Meta: **$31,052.29**
- LSA net charged spend: **$50,518.51**
- LSA also contains **$8,484.68** of source cost attached to leads that were later credited/refunded; that amount is not net spend.

Google campaign totals are reproduced in script section 6. The largest Google spend is campaign `20814455917` at **$98,994.06**. That campaign appears under two names, so campaign analysis must group by ID rather than name.

Sources: `google_ads_insights.csv`, `meta_insights.csv`, `lsa_leads.csv`; script §§2, 6, 8.

## 2. Platform-reported leads/conversions vs real callers

Full snapshot:

- Google reports **4,610.0 conversions**. Google conversions are fractional and are not a count of individual people.
- Meta reports **1,234 leads**.
- LSA contains **1,701 lead rows**: 1,275 CHARGED, 222 CREDITED, and 204 NOT_CHARGED.

Latest 30 days, qualifying real callers:

- Google Ads: **100**
- Google LSA: **68**
- Meta: **6**
- GBP: **126**
- Website: **69**
- Direct: **74**

This is why platform-reported "lead" metrics should not be treated as interchangeable with unique callers.

Sources: ad/LSA CSVs plus `calls.csv`; script §§3–5.

## 3. Calls, unique callers, and repeat behavior

The tracking log contains **29,757 calls but only 13,580 unique caller hashes**.

By source:

| Source | Calls | Unique callers | First-time calls | Returning calls |
|---|---:|---:|---:|---:|
| direct | 17,665 | 6,916 | 2,136 | 15,529 |
| gbp | 5,459 | 4,266 | 2,616 | 2,843 |
| google_ads | 2,625 | 2,129 | 1,294 | 1,331 |
| google_lsa | 1,640 | 1,468 | 1,312 | 328 |
| meta | 165 | 128 | 113 | 52 |
| website | 2,203 | 1,827 | 1,101 | 1,102 |

There are also **3,608 calls under 30 seconds** in the full snapshot, another reason raw call counts should not be used as real-lead counts.

Source: `calls.csv`; script §4.

## 4. Recent paid-channel and campaign performance

Latest 30-day observed real-lead CPL from the dedicated Issue #2 verification:

- Google Ads: **$89.54** (100 real leads)
- Google LSA: **$45.22** (68)
- Meta: **$227.28** (6)

Google campaign-level recent performance:

- Brand: **$1,589.71 / 17 = $93.51 per real lead**
- AC Repair: **$4,769.70 / 47 = $101.48**
- Heating Repair: **$369.32 / 0 qualifying real leads**
- AC Replacement: **$2,225.03 / 36 = $61.81**

Meta does not expose a campaign/ad-set identifier in `calls.csv`, so true caller CPL cannot be defensibly attributed below channel level. Platform-reported ad-set CPLs are still reproduced in script §7 for comparison.

Sources: `google_ads_insights.csv`, `meta_insights.csv`, `calls.csv`; script §§5–7.

## 5. LSA charged vs credited

LSA status totals:

- CHARGED: **1,275 leads**, $50,518.51 source cost
- CREDITED: **222 leads**, $8,484.68 source cost attached to refunded leads
- NOT_CHARGED: **204 leads**, $0 source cost

Credited leads must remain in raw history but their source cost must not be treated as current net spend.

Source: `lsa_leads.csv`; script §8.

## 6. Completed CRM jobs and seasonality

CRM snapshot:

- **9,294 total jobs**
- **7,819 completed**
- Completed-job revenue: **$4,253,964**
- Other statuses: 800 canceled, 355 estimate_lost, 219 estimate_sold, 101 scheduled

Seasonal comparison:

- Nov 2025–Feb 2026: **843 completed jobs / 120 days = 7.03 per day**
- Jun–Aug 2026: **1,388 / 92 days = 15.09 per day**

The seasonal difference is real, but it does **not** prove that doubling winter ad spend would create summer-level demand.

Source: `crm_jobs.csv`; script §9.

## 7. Katy evidence

The snapshot README lists Wren's service-area ZIP codes; **77449, 77450, 77493, and 77494 are not in that service-area list**.

Across those Katy ZIPs there are **181 CRM jobs, all 181 canceled**:

- late 2024: 26
- 2025: 78
- 2026 through the snapshot: 77

The 2026 count reproduces Diane's "77 jobs turned away" statement, but the history does not show obvious accelerating growth: 2025 had 78.

Sources: `data/snapshot-2026-09-23/README.md` line 86 and `crm_jobs.csv`; script §9.

## 8. Misleading, duplicated, or suspicious reported numbers

The main evidence flags are:

1. Google reports fractional conversions, so its conversion count is not a person count.
2. Google campaign ID `20814455917` has two names ("AC Repair - Houston" and "Summer AC Repair"); grouping by name would split one campaign.
3. The call log has 29,757 calls but 13,580 unique callers, so raw calls substantially double-count people.
4. Brand's summer campaign logged **323 calls, 247 returning calls (76.5%)**. Its cheap platform-reported conversion CPL therefore should not be read as cheap acquisition of new callers.
5. LSA contains 222 credited/refunded leads whose original source cost remains present in the raw data.
6. Meta reported **zero leads Aug 4–10** while still recording **$291.15 spend, 135 clicks, and 4 tracked Meta calls**. That is evidence of a reporting/tracking anomaly, not evidence that customer response literally fell to zero.
7. CRM `lead_source` contains **59 distinct free-text values**, including 817 blanks and 341 "?"; CRM attribution cannot be used without normalization.
8. There is no shared ID linking CRM jobs to ad/call records, so ad-to-revenue attribution cannot be proven from this snapshot.

Sources: all five snapshot files, `data/snapshot-2026-09-23/README.md`, `notes/data-map.md`; script §10.

## Issue #2 checklist mapping

| Issue #2 requirement | Reproducible evidence |
|---|---|
| Spend by channel and campaign | §§2, 6, 7 |
| Platform-reported leads/conversions | §3 |
| Actual tracked calls by source | §4 |
| Unique callers using `caller_hash` | §4 |
| First-time vs repeat callers | §4 |
| LSA charged vs credited | §8 |
| Completed CRM jobs | §9 |
| Seasonal job volume | §9 |
| Katy ZIP/job evidence | §9 |
| Campaign and ad-set performance | §§6–7 |
| Misleading/duplicated/suspicious metrics | §10 |

The script is intentionally read-only and standard-library-only so another teammate can run the same analysis directly from the repository.
