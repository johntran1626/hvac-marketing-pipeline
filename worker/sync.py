"""Resumable sync for date-window sources (Google Ads, Meta, LSA, calls).

1. Backfill: every 31-day window from the source's first day to the API's data_through.
   After each page is upserted, the window and next_cursor are saved in sync_state.
   After each window, backfilled_through moves forward and the cursor is cleared.
   A killed run reloads that state and continues from the saved cursor.
2. Refresh: re-pull the last `refresh_days` days, because recent numbers change
   (Google conversions, Meta leads: 7 days; LSA credits: up to 30 days).
   Refresh never touches the backfill progress, so a failed refresh can't corrupt it.
"""
from datetime import date, timedelta

from worker import state
from worker.api_client import InvalidCursor, windows


class Source:
    """What a loader needs: where to read, where to write, and its natural key."""
    def __init__(self, name, path, table, on_conflict, first_day, refresh_days, params=None):
        self.name, self.path, self.table, self.on_conflict = name, path, table, on_conflict
        self.first_day, self.refresh_days, self.params = first_day, refresh_days, params or {}


def load_window(api, db, src, start, end, cursor=None, save_progress=True):
    """Upsert every row in [start, end]. Returns the row count written by this call."""
    params = {**src.params, "start_date": start.isoformat(), "end_date": end.isoformat()}
    written = 0
    try:
        for rows, next_cursor in api.pages(src.path, params, cursor):
            db.upsert(src.table, rows, src.on_conflict)  # write first...
            written += len(rows)
            if save_progress and next_cursor:             # ...then save progress
                state.save(db, src.name, window_start=start.isoformat(),
                           window_end=end.isoformat(), cursor=next_cursor)
    except InvalidCursor:
        print(f"  saved cursor rejected, restarting {start} to {end} from page 1")
        return written + load_window(api, db, src, start, end, None, save_progress)
    return written


def run(api, db, src):
    st = state.load(db, src.name)
    last_day = api.data_through()
    state.save(db, src.name, status="running", last_error=None, last_run_started_at=state.now())
    print(f"[{src.name}] API data_through={last_day}, backfilled_through={st.get('backfilled_through')}")

    try:
        # Finish the window a killed run left open.
        if st.get("window_start"):
            start, end = date.fromisoformat(st["window_start"]), date.fromisoformat(st["window_end"])
            print(f"  resuming {start} to {end} from saved cursor")
            n = load_window(api, db, src, start, end, st.get("cursor"))
            state.save(db, src.name, backfilled_through=end.isoformat(),
                       window_start=None, window_end=None, cursor=None)
            print(f"  {start} to {end}: {n} rows (resumed)")
            st["backfilled_through"] = end.isoformat()

        # Backfill every window not done yet.
        done = st.get("backfilled_through")
        first = date.fromisoformat(done) + timedelta(days=1) if done else src.first_day
        for start, end in windows(first, last_day):
            state.save(db, src.name, window_start=start.isoformat(), window_end=end.isoformat(), cursor=None)
            n = load_window(api, db, src, start, end)
            state.save(db, src.name, backfilled_through=end.isoformat(),
                       window_start=None, window_end=None, cursor=None)
            print(f"  {start} to {end}: {n} rows")

        # Re-pull recent days that the source can still change.
        start = max(src.first_day, last_day - timedelta(days=src.refresh_days - 1))
        n = load_window(api, db, src, start, last_day, save_progress=False)
        print(f"  refresh {start} to {last_day}: {n} rows")

        state.save(db, src.name, status="ok", last_success_at=state.now())
    except BaseException as e:  # includes Ctrl-C and the runner cancelling the job
        state.save(db, src.name, status="failed", last_error=f"{type(e).__name__}: {e}"[:500])
        raise
