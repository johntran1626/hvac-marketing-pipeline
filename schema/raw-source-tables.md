# Project B Raw Source Table Design

## Purpose

These tables preserve the source datasets closely enough for downstream
normalization and analysis without losing source identifiers, timestamps,
source semantics, or reported metrics.

## Google Ads

Source file:

`data/snapshot-2026-09-23/google_ads_insights.csv`

Source semantics:

- One row per day per ad group.
- `date` represents the Google Ads account day in America/Chicago.
- `customer_id` is the Google Ads account identifier.
- `campaign_id` and `ad_group_id` are source identifiers.
- `cost_micros` is cost in millionths of a dollar.
- `conversions` may be fractional.

### Table: `raw_google_ads_insights`

| Column | PostgreSQL type | Nullable | Notes |
|---|---|---|---|
| date | date | no | Google Ads account day, Central Time |
| customer_id | text | no | Source account identifier |
| campaign_id | text | no | Source campaign identifier |
| campaign_name | text | no | Campaign name on that date |
| ad_group_id | text | no | Source ad group identifier |
| ad_group_name | text | no | Ad group name |
| impressions | bigint | no | Number of impressions |
| clicks | bigint | no | Number of clicks |
| cost_micros | bigint | no | Millionths of a dollar |
| conversions | numeric | no | Google Ads reported conversions; may be fractional |

### Key

Composite primary key:

`(date, customer_id, campaign_id, ad_group_id)`

Validation against the 2026-09-23 snapshot:

- 8,664 data rows
- 0 duplicate composite keys
- 0 blank values across all columns
- Date range: 2024-10-01 through 2026-09-22
- 1 customer
- 4 campaigns
- 12 ad groups

The composite key was tested across the complete CSV rather than inferred
from sample rows.

## Meta Ads

Source file:

`data/snapshot-2026-09-23/meta_insights.csv`

Source semantics:

- One row per day per ad set.
- `date_start` and `date_stop` represent the ad account day in Pacific Time (America/Los_Angeles).
- `date_start` and `date_stop` are the same source day.
- `account_id`, `campaign_id`, and `adset_id` are source identifiers.
- `spend` is reported in dollars.
- `actions` stores the raw Meta actions array exactly as received from the API.

### Table: `raw_meta_insights`

| Column | PostgreSQL type | Nullable | Notes |
|---|---|---|---|
| date_start | date | no | Meta account day, Pacific Time |
| date_stop | date | no | Same source day as `date_start` |
| account_id | text | no | Source Meta ad account identifier |
| campaign_id | text | no | Source campaign identifier |
| campaign_name | text | no | Campaign name |
| adset_id | text | no | Source ad set identifier |
| adset_name | text | no | Ad set name |
| impressions | text | no | Raw impressions value as received from the API |
| clicks | text | no | Raw clicks value as received from the API |
| spend | text | no | Raw spend value as received from the API |
| actions | jsonb | no | Raw Meta actions array as received from the API |

### Key

Composite primary key:

`(date_start, account_id, campaign_id, adset_id)`

Validation against the 2026-09-23 snapshot:

- 4,332 data rows
- 0 duplicate composite keys
- 0 blank values across all columns
- Date range: 2024-10-01 through 2026-09-22
- 1 account
- 2 campaigns
- 6 ad sets

The composite key was tested across the complete CSV rather than inferred
from sample rows.

## LSA Leads

Source file:

`data/snapshot-2026-09-23/lsa_leads.csv`

Source semantics:

- One row per Local Services Ads lead.
- `lead_created_at` is stored in UTC.
- `lead_id` is the source lead identifier.
- `lead_type` is `PHONE_CALL` or `MESSAGE`.
- `charge_status` is `CHARGED`, `CREDITED`, or `NOT_CHARGED`.
- `credited_at` is the UTC timestamp when a charged lead was refunded.
- `credited_at` is empty unless `charge_status` is `CREDITED`.
- `cost_usd` is the source lead price in dollars.

### Table: `raw_lsa_leads`

| Column | PostgreSQL type | Nullable | Notes |
|---|---|---|---|
| lead_id | text | no | Source lead identifier |
| lead_created_at | timestamptz | no | Lead creation timestamp, UTC |
| category | text | no | Service category |
| lead_type | text | no | `PHONE_CALL` or `MESSAGE` |
| charge_status | text | no | `CHARGED`, `CREDITED`, or `NOT_CHARGED` |
| credited_at | timestamptz | yes | Refund timestamp; populated only for credited leads |
| cost_usd | numeric | no | Lead price in dollars |

### Key

Primary key:

`lead_id`

Validation against the 2026-09-23 snapshot:

- 1,701 data rows
- 0 duplicate `lead_id` values
- 1,479 rows have no `credited_at`
- 222 `CREDITED` rows have `credited_at`
- 1,275 `CHARGED` rows have no `credited_at`
- 204 `NOT_CHARGED` rows have no `credited_at`
- Category: `HVAC`
- Lead types: `PHONE_CALL`, `MESSAGE`
- Charge statuses: `CHARGED`, `CREDITED`, `NOT_CHARGED`
- Lead timestamps range from 2024-10-01 through 2026-09-23

The `lead_id` uniqueness was tested across the complete CSV.
The relationship between `charge_status` and `credited_at` was also
validated across the complete CSV.

## Calls

Source file:

`data/snapshot-2026-09-23/calls.csv`

Source semantics:

- One row per inbound phone call.
- `started_at` is stored in UTC.
- Each marketing source has its own tracking number.
- `campaign_id` is populated for `google_ads` calls and empty for other sources.
- `caller_hash` is an anonymized, stable representation of the caller's phone number.
- `first_time_caller` indicates whether the tracking system had previously seen that caller.

### Table: `raw_calls`

| Column | PostgreSQL type | Nullable | Notes |
|---|---|---|---|
| call_id | text | no | Source call identifier |
| started_at | timestamptz | no | Call start timestamp, UTC |
| duration_sec | integer | no | Call duration in seconds |
| tracking_number | text | no | Number dialed |
| source | text | no | Marketing/source channel |
| campaign_id | text | yes | Google Ads campaign ID; empty for other sources |
| caller_hash | text | no | Stable anonymized caller identifier |
| first_time_caller | boolean | no | Whether caller was new to the tracking system |

### Key

Primary key:

`call_id`

Validation against the 2026-09-23 snapshot:

- 29,757 data rows
- 0 duplicate `call_id` values
- 27,132 rows have no `campaign_id`
- Sources: `direct`, `gbp`, `google_ads`, `website`, `google_lsa`, `meta`
- 8,572 first-time callers
- 21,185 returning callers
- Timestamp range: 2024-10-01 through 2026-09-23

The `call_id` uniqueness was tested across the complete CSV.
The nullable `campaign_id` behavior was also tested across the complete CSV.

## CRM Jobs

Source file:

`data/snapshot-2026-09-23/crm_jobs.csv`

Source semantics:

- One row per CRM job.
- Each row represents the job's latest state as of 2026-09-23 00:00 Central Time.
- `created_at` and `updated_at` are Central Time timestamps with explicit UTC offsets.
- `job_id` is the source job identifier.
- `customer_id` identifies the CRM customer.
- `lead_source` is entered by the customer service representative and may
  contain inconsistent free-text values.
- `job_type` identifies the type of work.
- `status` identifies the current/latest job state.
- `revenue_usd` is populated for completed jobs and otherwise empty.
- `zip` is the customer's ZIP code.

### Table: `raw_crm_jobs`

| Column | PostgreSQL type | Nullable | Notes |
|---|---|---|---|
| job_id | text | no | Source job identifier |
| customer_id | text | no | Source customer identifier |
| created_at | timestamptz | no | Job booking timestamp with source UTC offset |
| updated_at | timestamptz | no | Latest job update timestamp with source UTC offset |
| lead_source | text | yes | CRM-entered source; free text and inconsistent |
| job_type | text | no | `repair`, `diagnostic`, `maintenance`, `estimate`, or `install` |
| status | text | no | Current/latest job status |
| revenue_usd | numeric | yes | Billed revenue; populated for completed jobs |
| zip | text | no | Customer ZIP code |

### Key

Primary key:

`job_id`

Validation against the 2026-09-23 snapshot:

- 9,294 data rows
- 0 duplicate `job_id` values
- 817 rows have no `lead_source`
- 1,475 rows have no `revenue_usd`
- 7,819 completed jobs have revenue
- 800 canceled jobs have no revenue
- 355 lost estimates have no revenue
- 219 sold estimates have no revenue
- 101 scheduled jobs have no revenue
- Job types: `repair`, `diagnostic`, `maintenance`, `estimate`, `install`
- Timestamp range: 2024-10-01 through 2026-09-22

The `job_id` uniqueness was tested across the complete CSV.
The relationship between job status and revenue presence was also
validated across the complete CSV.

The `lead_source` field is intentionally preserved as raw text. Its values
contain inconsistent capitalization, spelling, abbreviations, and source
labels. Standardization belongs in the normalized analytical layer rather
than the raw table.


## Design Principles

- Preserve source identifiers as text rather than treating identifiers as
  quantities.
- Preserve source timestamps/time-zone semantics.
- Preserve raw monetary representations before normalization.
- Allow nullable fields where the source can legitimately omit a value.
- Use primary or unique constraints only where uniqueness has been verified
  against the source data.
