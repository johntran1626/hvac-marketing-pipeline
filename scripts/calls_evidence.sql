-- Evidence for Issue #37: row count, distinct call_id, started_at range and duplicate-key check for the calls load.
-- Run in Supabase: SQL Editor -> New query -> paste ONE query -> Run (the editor only shows the last result).
-- started_at is UTC as the API returns it; the Central day is computed here, never stored.

-- 1. Row count, distinct key, UTC and Central range.
select
  count(*)                                                    as row_count,
  count(distinct call_id)                                     as distinct_call_ids,
  min(started_at)                                             as first_started_at_utc,
  max(started_at)                                             as last_started_at_utc,
  min((started_at at time zone 'America/Chicago')::date)      as first_central_day,
  max((started_at at time zone 'America/Chicago')::date)      as last_central_day
from public.raw_calls;

-- 2. Duplicate-key check: should return no rows.
select call_id, count(*) from public.raw_calls group by call_id having count(*) > 1;

-- 3. Same days as the snapshot (data/snapshot-2026-09-23/calls.csv, through Central 2026-09-22).
--    The snapshot is what the API returned on 2026-09-23, and calls don't change after their day,
--    so these should match the CSV: 29,757 rows, 8,572 first-time, 27,132 without a campaign_id.
select
  count(*)                                                    as rows_through_sep22,
  count(*) filter (where first_time_caller)                   as first_time_callers,
  count(*) filter (where campaign_id is null)                 as no_campaign_id,
  count(distinct caller_hash)                                 as distinct_callers
from public.raw_calls
where (started_at at time zone 'America/Chicago')::date <= date '2026-09-22';

-- 4. Same window, by source. Snapshot: direct 17,665, gbp 5,459, google_ads 2,625,
--    website 2,203, google_lsa 1,640, meta 165.
select source, count(*) as calls
from public.raw_calls
where (started_at at time zone 'America/Chicago')::date <= date '2026-09-22'
group by source
order by calls desc;
