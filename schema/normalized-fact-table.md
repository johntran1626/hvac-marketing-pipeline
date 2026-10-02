# Normalized Fact Table Design

## Purpose

The normalized fact table provides a shared analytical layer across Google Ads, Meta Ads, Local Services Ads, call tracking, and CRM data.

It is designed to support the Project B dashboard requirements, including:

- true cost per lead by channel and month
- reported leads compared with unique leads
- brand versus non-brand analysis
- campaign-level analysis
- consistent analysis dates across source time zones
- data freshness tracking

Raw source data remains unchanged in the raw tables. Source-specific fields are standardized only in this normalized analytical layer.

For Meta Ads, raw `impressions`, `clicks`, and `spend` values arrive as strings and are converted to numeric types during normalization; lead counts are extracted from the raw `actions` array.

## Grain

One row represents one unique combination of:

`analysis_date + channel + campaign_id + brand_classification`

This grain supports daily analysis while allowing the dashboard to aggregate results by month, channel, campaign, and brand classification.

For sources that do not have a meaningful campaign identifier, `campaign_id` and `campaign_name` may be null.

## Analysis Date

`analysis_date` is the daily reporting bucket used to place the sources side by side. Timestamped sources are normalized to the Central Time business day (`America/Chicago`). Platform data that arrives only as an already-aggregated account-local date keeps that source date because there is no event timestamp available to re-bucket without inventing timing.

Source dates and timestamps are normalized as follows:

- Google Ads: use `date` directly because it is already the Central Time account day.
- Meta Ads: use `date_start` directly. Meta returns a daily aggregate for the Pacific Time account day (`America/Los_Angeles`), not event timestamps. Do not shift the date into Central Time or split the row across Central days; that would invent detail the source does not provide.
- Local Services Ads: convert `lead_created_at` from UTC to Central Time and use its Central calendar date. A later credit does not move the lead to the `credited_at` date.
- Calls: convert `started_at` from UTC to Central Time and use its Central calendar date.
- CRM Jobs: use the Central Time calendar date from `created_at`.

The original source timestamps and dates remain preserved in the raw tables, so the dashboard can disclose that Meta's daily bucket is Pacific-account-day data.

## Dimensions and Source Identifiers

Each normalized row identifies both the reporting channel and the originating source platform.

### Channel

`channel` represents the business-facing marketing or lead channel used for dashboard analysis.

Expected values include:

- `google_ads`
- `meta`
- `google_lsa`
- `direct`
- `gbp`
- `website`

Additional channel values may be added if new source data introduces them.

### Source Platform

`source_platform` records the system that produced the underlying raw data.

Expected values include:

- `google_ads`
- `meta_ads`
- `lsa`
- `call_tracking`
- `crm`

`channel` and `source_platform` are intentionally separate. For example, a call-tracking record may have `source_platform = call_tracking` while its `channel` is `google_ads`, `meta`, `google_lsa`, `direct`, `gbp`, or `website`.

### Source Identifiers

Identifiers from different platforms must not be assumed to be globally unique.

The normalized table therefore preserves the source namespace using:

- `source_platform`
- `source_account_id`
- `campaign_id`
- `campaign_name`

`source_account_id` stores the platform-specific account identifier when one exists.

Examples:

- Google Ads → `customer_id`
- Meta Ads → `account_id`
- sources without an account identifier → null

`campaign_id` stores the source campaign identifier when available.

For records without a meaningful campaign, `campaign_id` and `campaign_name` are null.

## Brand Classification

`brand_classification` supports comparison of brand and non-brand marketing performance.

Expected values are:

- `brand`
- `non_brand`
- `not_applicable`

Classification rules for the current snapshot use `source_platform + campaign_id`, not campaign-name text:

- Google Ads `20814455901` (`Brand - Wren Air & Heat`) → `brand`
- Google Ads `20814455917` → `non_brand`
- Google Ads `20814455930` → `non_brand`
- Google Ads `20814455948` → `non_brand`
- Meta `120208841937650100` → `non_brand`
- Meta `120208841937650200` → `non_brand`
- rows without meaningful campaign or brand context → `not_applicable`

Campaign IDs are the classifier because names can change over time. In the snapshot, Google campaign ID `20814455917` appears under both `AC Repair - Houston` and `Summer AC Repair`, so name matching would be less stable. Raw campaign names remain unchanged for display and auditability.

## Lead Definitions

The normalized table keeps platform-reported leads separate from independently observed unique leads.

### Reported Leads

`reported_leads` represents leads or conversions reported directly by an advertising platform.

Examples include:

- Google Ads `conversions`
- Meta Ads `actions` entries where `action_type = "lead"`; normalize the string `value` to numeric
- Local Services Ads: one reported lead per raw LSA lead row. A row that later becomes `CREDITED` remains a platform-reported lead; the credit changes its billable spend, not the fact that the platform reported a lead.

Platform-reported leads may be fractional when the source platform reports fractional attribution.

### LSA Credits and Net Spend

LSA `spend_usd` must reflect the lead's current billing state, not blindly sum `cost_usd`:

- `CHARGED` → use `cost_usd`
- `CREDITED` → `0` net spend because the charge was refunded
- `NOT_CHARGED` → `0` spend

Credits can arrive after the original lead. When a lead changes from `CHARGED` to `CREDITED`, normalization updates the spend on the lead's original `analysis_date` derived from `lead_created_at`; it does not create new spend or a new lead on the `credited_at` date.

### Unique Leads

`unique_leads` represents independently observed first-time callers from the call-tracking data.

A call counts as a unique lead when:

`first_time_caller = true`

The stable `caller_hash` field allows repeated calls from the same anonymized phone number to be distinguished from first-time callers.

Reported leads and unique leads are intentionally stored as separate metrics because an advertising platform's reported conversion count does not necessarily represent a unique person.

### True Cost per Lead

For the Project B dashboard, true cost per lead is calculated using advertising spend divided by unique leads:

`true_cpl = spend_usd / unique_leads`

The calculation should be performed only when `unique_leads > 0`.

The fact table stores the underlying spend and lead counts rather than storing a precomputed CPL so that the dashboard can correctly recalculate CPL at different aggregation levels.

## Table: `fact_marketing_daily`

| Column | PostgreSQL type | Nullable | Purpose |
|---|---|---|---|
| analysis_date | date | no | Daily reporting bucket; Central business date for timestamped sources, Meta Pacific account date for Meta daily aggregates |
| channel | text | no | Business-facing acquisition channel |
| source_platform | text | no | System that produced the underlying data |
| source_account_id | text | yes | Platform-specific account identifier |
| campaign_id | text | yes | Source campaign identifier |
| campaign_name | text | yes | Source campaign name |
| brand_classification | text | no | `brand`, `non_brand`, or `not_applicable` |
| impressions | bigint | no | Advertising impressions |
| clicks | bigint | no | Advertising clicks |
| spend_usd | numeric | no | Advertising or lead spend in dollars |
| reported_leads | numeric | no | Platform-reported conversions or leads |
| unique_leads | bigint | no | Independently observed first-time callers |
| calls | bigint | no | Total tracked calls |
| jobs | bigint | no | CRM jobs attributed to the row |
| completed_jobs | bigint | no | CRM jobs currently completed |
| revenue_usd | numeric | no | Revenue from completed jobs |
| synced_at | timestamptz | no | When source data was normalized |
| data_through | date | no | Most recent source date covered by the sync |

Metric columns should use zero when the metric is applicable but no activity occurred. Null should be reserved for dimensions or identifiers that genuinely do not apply.

## Data Freshness

Freshness requires two separate values:

- `synced_at` records when the normalization process last processed the source data.
- `data_through` records the latest analysis date represented by the loaded source data.

Keeping these values separate allows the dashboard to distinguish between a recently executed sync and the actual age of the underlying data.
