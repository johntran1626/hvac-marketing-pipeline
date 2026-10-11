-- Project B Milestone 2 (Issue #25, agreed with the team for #30 and #31)
-- Each source writes its own fact rows, so LSA spend, calls and CRM jobs for the same
-- channel and day no longer share (and overwrite) one row. The dashboard sums by channel.

alter table public.fact_marketing_daily
  drop constraint if exists fact_marketing_daily_grain;

alter table public.fact_marketing_daily
  add constraint fact_marketing_daily_grain
    unique nulls not distinct
      (analysis_date, channel, source_platform, source_account_id, campaign_id, brand_classification);
