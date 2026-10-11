-- Evidence for Issue #29: CRM full load, saved watermark, incremental runs, updates without duplicates.
-- Run in Supabase: SQL Editor -> New query -> paste ONE query -> Run (the editor only shows the last result).

-- 1. Row count, distinct key, updated_at range.
select
  count(*)                    as row_count,
  count(distinct job_id)      as distinct_job_ids,
  min(updated_at)             as first_updated_at,
  max(updated_at)             as last_updated_at
from public.raw_crm_jobs;

-- 2. Duplicate-key check: should return no rows.
select job_id, count(*) from public.raw_crm_jobs group by job_id having count(*) > 1;

-- 3. The saved checkpoint: watermark should equal max(updated_at) from query 1.
select source, status, watermark, last_success_at from public.sync_state where source = 'crm';

-- 4. Snapshot comparison (data/snapshot-2026-09-23/crm_jobs.csv: 9,294 jobs, 0 duplicate job_id).
--    Jobs only ever get added or updated, so live should have at least 9,294 jobs.
select count(*) as jobs_updated_after_snapshot
from public.raw_crm_jobs
where updated_at > timestamptz '2026-09-22T23:32:00-05:00';

-- 5. Updated, not duplicated: the 101 jobs that were 'scheduled' in the snapshot.
--    Each must appear exactly once; those that moved on show their new status and a later updated_at.
select status, count(*) as jobs, count(distinct job_id) as distinct_jobs
from public.raw_crm_jobs
where job_id in (
  'J-208833', 'J-208843', 'J-208885', 'J-208925', 'J-208933', 'J-208949', 'J-208962', 'J-208990',
  'J-208996', 'J-209001', 'J-209016', 'J-209018', 'J-209024', 'J-209025', 'J-209040', 'J-209045',
  'J-209046', 'J-209059', 'J-209076', 'J-209079', 'J-209082', 'J-209085', 'J-209089', 'J-209092',
  'J-209094', 'J-209097', 'J-209099', 'J-209100', 'J-209106', 'J-209108', 'J-209112', 'J-209117',
  'J-209123', 'J-209124', 'J-209126', 'J-209129', 'J-209133', 'J-209136', 'J-209145', 'J-209147',
  'J-209156', 'J-209159', 'J-209160', 'J-209162', 'J-209164', 'J-209166', 'J-209168', 'J-209171',
  'J-209172', 'J-209174', 'J-209178', 'J-209183', 'J-209187', 'J-209191', 'J-209193', 'J-209197',
  'J-209200', 'J-209201', 'J-209208', 'J-209209', 'J-209212', 'J-209214', 'J-209217', 'J-209222',
  'J-209230', 'J-209232', 'J-209233', 'J-209239', 'J-209246', 'J-209247', 'J-209248', 'J-209249',
  'J-209252', 'J-209253', 'J-209255', 'J-209259', 'J-209260', 'J-209263', 'J-209264', 'J-209267',
  'J-209270', 'J-209271', 'J-209272', 'J-209273', 'J-209275', 'J-209276', 'J-209277', 'J-209278',
  'J-209279', 'J-209280', 'J-209281', 'J-209282', 'J-209283', 'J-209284', 'J-209285', 'J-209286',
  'J-209288', 'J-209289', 'J-209291', 'J-209292', 'J-209294'
)
group by status
order by jobs desc;
