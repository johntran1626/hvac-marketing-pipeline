"""Tracked phone calls into raw_calls (Issue #37).

Rows are stored exactly as the API returns them: started_at stays a UTC timestamp, and
caller_hash, first_time_caller, source and campaign_id (null included) are not touched.
The API's start_date/end_date filter on the Central time date of started_at (docs/API.md), so
the worker's windows are Central days, like the other sources. A call at 9pm Central is already
the next day in UTC; it still belongs to the Central window it was requested in.
Refresh is 1 day: docs/API.md doesn't list calls among the numbers that change, so only the
latest day is pulled again (upsert on call_id makes that harmless).
"""
from datetime import date

from worker.sources import SOURCES
from worker.sync import Source

CALLS = Source(
    name="calls",
    path="/v1/calls",
    table="raw_calls",
    on_conflict="call_id",
    first_day=date(2024, 10, 1),  # docs/API.md: "Data starts on 2024-10-01"
    refresh_days=1,
)
SOURCES[CALLS.name] = CALLS
