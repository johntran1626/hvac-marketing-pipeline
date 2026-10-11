-- Project B Milestone 2 (Issue #25)
-- Saved worker progress, one row per source, so a killed run resumes instead of restarting.

create table if not exists public.sync_state (
  source text primary key,              -- e.g. 'lsa', 'google_ads', 'meta', 'calls', 'crm'
  backfilled_through date,              -- last day fully written for date-window sources
  window_start date,                    -- window in progress (null when no window is open)
  window_end date,
  cursor text,                          -- next_cursor of the last page safely written in that window
  watermark timestamptz,                -- for incremental sources (CRM): largest updated_at written
  status text not null default 'idle',
  last_error text,
  last_run_started_at timestamptz,
  last_success_at timestamptz,
  updated_at timestamptz not null default now(),
  check (status in ('idle', 'running', 'ok', 'failed'))
);

-- Server-side only: no policies, so the publishable key can't read or write it.
-- The worker uses the secret key, which bypasses RLS.
alter table public.sync_state enable row level security;
