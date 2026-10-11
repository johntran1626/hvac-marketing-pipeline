"""CRM jobs into raw_crm_jobs: full load, then incremental by updated_since (Issue #29).

docs/API.md: /v1/crm/jobs has no dates. It returns each job once, in its latest state, whose
updated_at is *after* updated_since, ordered by updated_at then job_id.
- First run: updated_since=2000-01-01T00:00:00Z loads every job.
- Every page is upserted on job_id, so a job that went scheduled -> completed updates its row.
- After each page, the largest updated_at written so far is saved as sync_state.watermark.
  A killed run restarts from that watermark instead of from the beginning.
- Later runs ask for jobs updated after the watermark minus OVERLAP. updated_since is strictly
  "after", and several jobs can share one updated_at (118 timestamps do in the snapshot), so a
  run killed between two pages could otherwise skip the rest of a tie. Re-pulling the last
  second costs a few rows; the upsert makes it harmless.
- updated_at mixes -05:00 and -06:00 offsets, so timestamps are compared as times, not text.
Rows are stored exactly as the API returns them.
"""
from datetime import datetime, timedelta

from worker import state
from worker.sources import SOURCES

FULL_LOAD_SINCE = "2000-01-01T00:00:00Z"  # docs/API.md: "To load every job, use an old time"
OVERLAP = timedelta(seconds=1)


def parse(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


class CrmSource:
    name = "crm"
    path = "/v1/crm/jobs"
    table = "raw_crm_jobs"
    on_conflict = "job_id"

    def run(self, api, db):
        st = state.load(db, self.name)
        watermark = parse(st["watermark"]) if st.get("watermark") else None
        since = (watermark - OVERLAP).isoformat() if watermark else FULL_LOAD_SINCE
        state.save(db, self.name, status="running", last_error=None, last_run_started_at=state.now())
        print(f"[crm] watermark={watermark.isoformat() if watermark else None}, "
              f"asking for jobs updated after {since}")

        written = 0
        try:
            for rows, _ in api.pages(self.path, {"updated_since": since}):
                if not rows:
                    continue
                db.upsert(self.table, rows, self.on_conflict)        # write first...
                written += len(rows)
                newest = max(parse(r["updated_at"]) for r in rows)
                if watermark is None or newest > watermark:
                    watermark = newest
                    state.save(db, self.name, watermark=watermark.isoformat())  # ...then move it
            print(f"  {written} jobs written, watermark now {watermark.isoformat() if watermark else None}")
            state.save(db, self.name, status="ok", last_success_at=state.now())
        except BaseException as e:  # includes Ctrl-C and the runner cancelling the job
            state.save(db, self.name, status="failed", last_error=f"{type(e).__name__}: {e}"[:500])
            raise


CRM = CrmSource()
SOURCES[CRM.name] = CRM
