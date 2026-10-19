# CRM lead source → channel mapping

Booked jobs on the dashboard come from `raw_crm_jobs.lead_source`, which the office types in by hand. This is how each label maps to a channel. It is Kelsey's dictionary from #55 (`tests/fixtures/crm-source-map-proposed.json`), applied unchanged in `rebuild_fact_marketing_daily()` (#84). Labels are lower-cased and trimmed first, so `Facebook ` and `facebook` match.

| Channel | `lead_source` labels |
|---|---|
| Google Ads | `google ad`, `google ads` |
| Google Guaranteed | `google guaranteed`, `google lsa`, `google screened`, `local services`, `lsa` |
| Meta | `facebok`, `facebook`, `fb`, `fb ad`, `instagram`, `meta` |
| Google Business Profile (free) | `gmb`, `google maps`, `maps` |
| Website | `site`, `web`, `web form`, `webiste`, `website` |
| Direct (truck, yard sign) | `saw truck`, `truck`, `yard sign` |
| Referral | `friend`, `neighbor`, `referral`, `referral - neighbor` |
| Existing customer | `customer`, `existing`, `existing customer`, `repeat`, `repeat customer`, `returning` |
| Maintenance plan | `maint plan`, `maintenance plan`, `plan`, `plan member` |
| Yelp | `yelp` |
| Nextdoor | `nextdoor` |
| Builder / HOA | `builder`, `hoa` |
| Unattributed | `?`, `ad`, `googel`, `google`, `google local`, `google reviews`, `google search`, `internet`, `online`, `reviews` |

Anything not in the table, including a blank source, is **Unattributed**.

## Calls we made

- **Plain `google` stays Unattributed.** It could be Google Ads, Google Guaranteed or the free Maps listing, and guessing would move jobs onto a paid channel.
- **`maps`, `google maps`, `gmb` are the free Google Business Profile**, not Google Guaranteed.
- **`local services`, `google screened` are Google Guaranteed** (Google's own names for Local Services Ads).
- **`facebook`, `fb`, `instagram`, `facebok` are Meta.** These are the jobs that sit next to Meta's phone leads on the dashboard: Meta's lead forms don't ring a phone, so its phone count alone undercounts it.
- **`saw truck`, `truck`, `yard sign` are Direct.**
- **`customer`, `repeat`, `plan` and similar are existing customers or the maintenance plan**, not marketing.

## Status

Agreed by the team (John, Kelsey, Ruslan) after Hamza's M2 feedback (Oct 15): "Agree on the mapping, then put Meta's jobs next to its phone leads for the same months."

To change a label, edit the `values` list in the latest `rebuild_fact_marketing_daily()` migration and this file together, then run worker-sync.
