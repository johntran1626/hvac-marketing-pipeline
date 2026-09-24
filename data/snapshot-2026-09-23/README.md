# Snapshot: 2026-09-23

Wren Air & Heat data, exported from the lab API with "today" set to 2026-09-23. Every file covers 2024-10-01 through 2026-09-22.

Format for all files: comma separated, one header row, UTF-8, LF line endings. Booleans are `true` or `false`. Money columns always have two decimals. An empty field means no value.

## google_ads_insights.csv

Google Ads performance. One row per day per ad group.

| column | meaning |
|---|---|
| `date` | the ad account's day, in Central Time (America/Chicago) |
| `customer_id` | Google Ads account id |
| `campaign_id` | campaign id |
| `campaign_name` | campaign name on that date |
| `ad_group_id` | ad group id |
| `ad_group_name` | ad group name |
| `impressions` | times an ad was shown |
| `clicks` | ad clicks |
| `cost_micros` | cost in millionths of a dollar. 25330000 = $25.33 |
| `conversions` | conversions as reported by Google Ads. Can be fractional |

## meta_insights.csv

Meta (Facebook and Instagram) ads performance. One row per day per ad set.

| column | meaning |
|---|---|
| `date_start`, `date_stop` | the ad account's day, in Pacific Time (America/Los_Angeles). Both are the same day |
| `account_id` | Meta ad account id |
| `campaign_id`, `campaign_name` | campaign |
| `adset_id`, `adset_name` | ad set |
| `impressions` | times an ad was shown |
| `clicks` | clicks |
| `spend` | dollars |
| `leads` | leads as reported by Meta |

## lsa_leads.csv

Google Local Services Ads (the "Google Guaranteed" ads). One row per lead. Local Services Ads charge per lead, not per click.

| column | meaning |
|---|---|
| `lead_id` | lead id |
| `lead_created_at` | when the lead came in, UTC |
| `category` | service category |
| `lead_type` | `PHONE_CALL` or `MESSAGE` |
| `charge_status` | `CHARGED`: the lead was billed. `CREDITED`: the charge was refunded. `NOT_CHARGED`: never billed |
| `credited_at` | when the charge was refunded, UTC. Empty unless `CREDITED` |
| `cost_usd` | price of the lead in dollars. 0.00 when `NOT_CHARGED` |

## calls.csv

Inbound phone calls from the call tracking system. Each marketing source has its own phone number. One row per call.

| column | meaning |
|---|---|
| `call_id` | call id |
| `started_at` | when the call started, UTC |
| `duration_sec` | call length in seconds |
| `tracking_number` | the number that was dialed |
| `source` | what that number is attached to: `google_ads` (Google search ads), `google_lsa` (Local Services Ads), `meta` (Meta ads), `gbp` (Google Business Profile listing), `website` (the website), `direct` (the main office line: invoices, trucks, yard signs) |
| `campaign_id` | Google Ads campaign id for `google_ads` numbers, otherwise empty |
| `caller_hash` | the caller's phone number, anonymized. The same phone number always gets the same hash |
| `first_time_caller` | `true` if the call tracking system had never seen this phone number before this call |

## crm_jobs.csv

Jobs from the company's CRM. One row per job, showing its latest state as of 2026-09-23 00:00 Central Time.

| column | meaning |
|---|---|
| `job_id` | job id |
| `customer_id` | customer id |
| `created_at` | when the job was booked, Central Time with UTC offset |
| `updated_at` | when the job last changed, Central Time with UTC offset |
| `lead_source` | where the customer came from, typed by the customer service rep when booking |
| `job_type` | `repair`, `diagnostic`, `maintenance`, `estimate`, or `install` |
| `status` | `scheduled`, `completed`, `canceled`, `estimate_sold`, or `estimate_lost` |
| `revenue_usd` | amount billed, dollars. Filled in for completed jobs only |
| `zip` | customer zip code |

Prices: diagnostic visit $89, tune-up $129, maintenance plan $189 a year (two visits), repairs and installs vary.

Service area: 77014, 77040, 77041, 77043, 77064, 77065, 77066, 77068, 77069, 77070, 77080, 77084, 77086, 77088, 77090, 77092, 77095, 77373, 77375, 77377, 77379, 77388, 77389, 77429, 77433.
