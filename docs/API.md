# Lab Ads API

This API serves the ad platform, call tracking, and CRM data for project B. It behaves like the real platform APIs: keys, date limits, paging, rate limits, and the occasional failed request.

## Base URL

```
https://ads-api.lab.zappstudios.us
```

All requests are `GET`. All responses are JSON, except this page.

## Authentication

Every request except `/v1/health` needs your group key in a header:

```
Authorization: Bearer <your group key>
```

A missing or wrong key returns `401 {"error":"unauthorized"}`. Keep the key out of your repo. Store it in an environment variable.

## Quick start

```
curl -H "Authorization: Bearer $LAB_API_KEY" \
  "https://ads-api.lab.zappstudios.us/v1/google_ads/insights?level=campaign&start_date=2026-09-01&end_date=2026-09-22"
```

## Dates and data freshness

- "Today" means today's date in Central time (America/Chicago).
- Data is available through yesterday. A new day becomes available after midnight Central time.
- `/v1/health` tells you today's date and the last date with data (`data_through`).
- Data starts on 2024-10-01. Earlier dates return no rows.
- The CSV files in `data/snapshot-2026-09-23/` are what this API returned on 2026-09-23 (data through 2026-09-22). Since then the API has added a new day every day, and recent days may have changed (see Numbers that change).
- `start_date` and `end_date` use the format `YYYY-MM-DD`. Both are required on the date endpoints and both are inclusive.
- One request can cover at most 31 days, for example `2026-08-01` to `2026-08-31`. A longer range returns `400 {"error":"date_range_too_large","max_days":31}`.
- An `end_date` of today or later is treated as yesterday.

## Time zones

| Endpoint | Dates and timestamps |
|---|---|
| `/v1/google_ads/insights` | `date` is the ad account's date, Central time (America/Chicago). |
| `/v1/meta/insights` | `date_start` and `date_stop` are the ad account's date, Pacific time (America/Los_Angeles). |
| `/v1/lsa/leads` | `lead_created_at` and `credited_at` are UTC. `start_date` and `end_date` filter on the Central time date of `lead_created_at`. |
| `/v1/calls` | `started_at` is UTC. `start_date` and `end_date` filter on the Central time date of `started_at`. |
| `/v1/crm/jobs` | `created_at` and `updated_at` are Central time with a UTC offset, for example `2026-07-14T10:22:00-05:00`. |

## Paging

- `limit`: rows per page. Default 100, max 200.
- Every data response looks like `{"data":[...],"paging":{"next_cursor":"..."}}`.
- For the next page, send the same request again and add `cursor=<next_cursor>`. Keep every other parameter the same.
- When `next_cursor` is `null`, you have all the rows.
- Rows come back in a fixed order (listed for each endpoint below).
- A cursor used with different parameters returns `400 {"error":"invalid_cursor"}`.

## Rate limits and retries

- Each key can make 60 requests per rolling 60 seconds. Your whole group shares one key.
- Responses to keyed requests include `X-RateLimit-Limit` and `X-RateLimit-Remaining`.
- Over the limit you get `429 {"error":"rate_limited"}` with a `Retry-After` header (seconds). Wait that many seconds, then send the same request again.
- A small share of requests fail with `503 {"error":"temporarily_unavailable"}` and `Retry-After: 2`. Wait, then send the same request again. Retry a few times with a growing wait (for example 2, 4, 8 seconds) before you give up.

## Numbers that change

- Numbers for the last 7 days can change when you pull them again. Conversions keep arriving after the day they belong to. This affects Google Ads `conversions` and Meta lead `actions`. Days older than 7 days do not change.
- LSA credits can appear up to 30 days later. A lead can show `CHARGED` first and `CREDITED` later. `credited_at` is filled in when that happens.
- CRM jobs change over time, for example from `scheduled` to `completed`. Use `updated_since` to get the jobs that changed.

## Errors

| Status | Body | Meaning |
|---|---|---|
| 400 | `{"error":"missing_parameter","parameter":"start_date"}` | A required parameter is missing. |
| 400 | `{"error":"invalid_date","parameter":"end_date"}` | Not a valid `YYYY-MM-DD` date. |
| 400 | `{"error":"invalid_date_range"}` | `end_date` is before `start_date`. |
| 400 | `{"error":"date_range_too_large","max_days":31}` | The range covers more than 31 days. |
| 400 | `{"error":"invalid_limit","max_limit":200}` | `limit` is not a whole number from 1 to 200. |
| 400 | `{"error":"invalid_cursor"}` | The cursor is broken or belongs to a different request. |
| 400 | `{"error":"invalid_parameter","parameter":"level"}` | A parameter has a value the API does not accept. |
| 401 | `{"error":"unauthorized"}` | Missing or wrong key. |
| 404 | `{"error":"not_found"}` | Unknown path. |
| 429 | `{"error":"rate_limited"}` | Too many requests. See `Retry-After`. |
| 503 | `{"error":"temporarily_unavailable"}` | Temporary failure. See `Retry-After`. |

## Endpoints

### GET /v1/health

No key needed.

```json
{"ok": true, "today": "2026-09-24", "data_through": "2026-09-23"}
```

### GET /v1/google_ads/insights

Google Ads performance, one row per date and ad group, or per date and campaign.

| Parameter | Required | Notes |
|---|---|---|
| `level` | no | `ad_group` (default) or `campaign`. |
| `start_date`, `end_date` | yes | Max 31 days. |
| `limit`, `cursor` | no | See Paging. |

Fields:

- `date`: the day, Central time.
- `customer_id`: Google Ads account id, for example `"482-119-3307"`.
- `campaign_id`, `campaign_name`.
- `ad_group_id`, `ad_group_name`: only when `level=ad_group`.
- `impressions`, `clicks`: whole numbers.
- `cost_micros`: cost in millionths of a dollar. `1000000` is $1.00.
- `conversions`: can have decimals.

With `level=campaign`, each row is the sum of that campaign's ad group rows for the day.

Order: `date`, then `campaign_id`, then `ad_group_id`.

Example (`level=ad_group`, values are illustrative):

```json
{
  "data": [
    {
      "date": "2026-09-01",
      "customer_id": "482-119-3307",
      "campaign_id": "20114567803",
      "campaign_name": "Furnace Repair",
      "ad_group_id": "1551230021",
      "ad_group_name": "Furnace Repair Near Me",
      "impressions": 1314,
      "clicks": 53,
      "cost_micros": 623277880,
      "conversions": 9.42
    }
  ],
  "paging": {"next_cursor": "eyJrIjpbIjIwMjYtMDktMDEiXX0"}
}
```

### GET /v1/meta/insights

Meta (Facebook and Instagram) ads performance, one row per date and ad set. The shape follows the Meta Marketing API: numbers are strings.

| Parameter | Required | Notes |
|---|---|---|
| `start_date`, `end_date` | yes | Max 31 days. Pacific time dates. |
| `limit`, `cursor` | no | See Paging. |

Fields:

- `date_start`, `date_stop`: the day, Pacific time. Both are the same day.
- `account_id`, `campaign_id`, `campaign_name`, `adset_id`, `adset_name`.
- `impressions`, `clicks`: strings, for example `"859"`.
- `spend`: dollars as a string with 2 decimals, for example `"41.65"`.
- `actions`: a list. Leads are the item with `"action_type": "lead"`, and its `value` is a string. When there are no leads, `actions` is an empty list `[]`.

Order: `date_start`, then `campaign_id`, then `adset_id`.

Example (values are illustrative):

```json
{
  "data": [
    {
      "date_start": "2026-09-20",
      "date_stop": "2026-09-20",
      "account_id": "act_1029384756",
      "campaign_id": "23851234560001",
      "campaign_name": "Lead Gen - AC Tune-Up",
      "adset_id": "23851234560101",
      "adset_name": "Homeowners 30-65",
      "impressions": "859",
      "clicks": "8",
      "spend": "41.65",
      "actions": [{"action_type": "lead", "value": "3"}]
    }
  ],
  "paging": {"next_cursor": null}
}
```

### GET /v1/lsa/leads

Google Local Services Ads leads, one row per lead.

| Parameter | Required | Notes |
|---|---|---|
| `start_date`, `end_date` | yes | Max 31 days. Filters on the Central time date of `lead_created_at`. |
| `limit`, `cursor` | no | See Paging. |

Fields:

- `lead_id`.
- `lead_created_at`: UTC timestamp.
- `category`: for example `"HVAC"`.
- `lead_type`: `PHONE_CALL` or `MESSAGE`.
- `charge_status`: `CHARGED`, `CREDITED`, or `NOT_CHARGED`.
- `credited_at`: UTC timestamp when the lead was credited, otherwise `null`.
- `cost_usd`: dollars.

Order: `lead_created_at`, then `lead_id`.

Example (values are illustrative):

```json
{
  "data": [
    {
      "lead_id": "lsa_001455",
      "lead_created_at": "2026-09-21T18:05:52Z",
      "category": "HVAC",
      "lead_type": "MESSAGE",
      "charge_status": "CHARGED",
      "credited_at": null,
      "cost_usd": 72.4
    }
  ],
  "paging": {"next_cursor": null}
}
```

### GET /v1/calls

Tracked phone calls, one row per call.

| Parameter | Required | Notes |
|---|---|---|
| `start_date`, `end_date` | yes | Max 31 days. Filters on the Central time date of `started_at`. |
| `limit`, `cursor` | no | See Paging. |

Fields:

- `call_id`.
- `started_at`: UTC timestamp.
- `duration_sec`: call length in seconds.
- `tracking_number`: the tracking number that was called.
- `source`: `google_ads`, `google_lsa`, `meta`, `gbp` (Google Business Profile), `website`, or `direct`.
- `campaign_id`: a campaign id, or `null`.
- `caller_hash`: a hash of the caller's phone number.
- `first_time_caller`: `true` or `false`.

Order: `started_at`, then `call_id`.

Example (values are illustrative):

```json
{
  "data": [
    {
      "call_id": "call_0003685",
      "started_at": "2026-09-20T21:45:58Z",
      "duration_sec": 720,
      "tracking_number": "(713) 555-0115",
      "source": "google_ads",
      "campaign_id": "20114567803",
      "caller_hash": "695240ed4c93",
      "first_time_caller": true
    }
  ],
  "paging": {"next_cursor": null}
}
```

### GET /v1/crm/jobs

Jobs from the company's CRM. Each job is returned once, in its latest state.

| Parameter | Required | Notes |
|---|---|---|
| `updated_since` | yes | ISO 8601 timestamp. Returns jobs whose `updated_at` is after this time. |
| `limit`, `cursor` | no | See Paging. |

- Examples of `updated_since`: `2026-09-01T00:00:00-05:00` or `2026-09-01T05:00:00Z`. A plain date like `2026-09-01` means midnight Central time.
- URL-encode the value. A `+` in an offset must be sent as `%2B`.
- To load every job, use an old time such as `2000-01-01T00:00:00Z`.
- To get only what changed, save the largest `updated_at` you have seen and pass it as `updated_since` next time.
- Jobs and changes from today appear tomorrow.

Fields:

- `job_id`, `customer_id`.
- `created_at`, `updated_at`: Central time with a UTC offset.
- `lead_source`: free text entered when the job was booked.
- `job_type`: `repair`, `maintenance`, `install`, `estimate`, or `diagnostic`.
- `status`: `scheduled`, `completed`, `canceled`, `estimate_sold`, or `estimate_lost`.
- `revenue_usd`: dollars, or `null`.
- `zip`: service address ZIP code.

Order: `updated_at`, then `job_id`.

Example (values are illustrative):

```json
{
  "data": [
    {
      "job_id": "J002145",
      "customer_id": "C02261",
      "created_at": "2026-09-11T15:55:24-05:00",
      "updated_at": "2026-09-21T19:27:00-05:00",
      "lead_source": "Google",
      "job_type": "maintenance",
      "status": "completed",
      "revenue_usd": 487.39,
      "zip": "77020"
    }
  ],
  "paging": {"next_cursor": null}
}
```
