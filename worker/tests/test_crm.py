"""Tests for the CRM loader (worker/sources/crm.py), Issue #29. Fake API and database: no network, no keys.

Run from the repo root:  python3 -m unittest discover -s worker/tests -t . -v
"""
import copy
import unittest
from datetime import datetime

from worker.sources import SOURCES
from worker.sources.crm import CRM, FULL_LOAD_SINCE
from worker.tests.test_sync import FakeDb


def job(job_id, updated_at, status="scheduled", revenue=None):
    """Shaped like docs/API.md's /v1/crm/jobs example."""
    return {"job_id": job_id, "customer_id": "C" + job_id[1:], "created_at": "2026-09-01T09:00:00-05:00",
            "updated_at": updated_at, "lead_source": "Google", "job_type": "repair",
            "status": status, "revenue_usd": revenue, "zip": "77070"}


def when(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


class FakeCrmApi:
    """Behaves like /v1/crm/jobs: jobs updated strictly after updated_since, ordered by
    (updated_at, job_id), `page_size` per page. Raises KeyboardInterrupt after `kill_after` pages."""
    def __init__(self, jobs, page_size=2, kill_after=None):
        self.jobs = {j["job_id"]: copy.deepcopy(j) for j in jobs}
        self.page_size, self.kill_after = page_size, kill_after
        self.asked, self.pages_served = [], 0

    def pages(self, path, params, cursor=None):
        assert path == "/v1/crm/jobs" and set(params) == {"updated_since"}
        self.asked.append(params["updated_since"])
        since = when(params["updated_since"])
        rows = sorted((j for j in self.jobs.values() if when(j["updated_at"]) > since),
                      key=lambda j: (when(j["updated_at"]), j["job_id"]))
        for i in range(0, max(len(rows), 1), self.page_size):
            if self.kill_after is not None and self.pages_served == self.kill_after:
                raise KeyboardInterrupt
            self.pages_served += 1
            more = i + self.page_size < len(rows)
            yield [copy.deepcopy(r) for r in rows[i:i + self.page_size]], ("next" if more else None)


class FakeCrmDb(FakeDb):
    def __init__(self):
        super().__init__()
        self.tables["raw_crm_jobs"] = {}


JOBS = [
    job("J-1", "2026-09-20T08:00:00-05:00", "completed", 250.0),
    job("J-2", "2026-09-21T10:00:00-05:00"),
    # Three jobs share one updated_at, and the page boundary (2 per page) falls inside the tie.
    job("J-3", "2026-09-22T23:32:00-05:00"),
    job("J-4", "2026-09-22T23:32:00-05:00"),
    job("J-5", "2026-09-22T23:32:00-05:00", "canceled"),
]


class CrmLoaderTest(unittest.TestCase):
    def test_registered_with_the_documented_endpoint_table_and_key(self):
        self.assertIs(SOURCES["crm"], CRM)
        self.assertEqual((CRM.path, CRM.table, CRM.on_conflict), ("/v1/crm/jobs", "raw_crm_jobs", "job_id"))

    def test_first_run_loads_everything_and_saves_the_newest_updated_at(self):
        api, db = FakeCrmApi(JOBS), FakeCrmDb()
        CRM.run(api, db)
        self.assertEqual(api.asked, [FULL_LOAD_SINCE])
        self.assertEqual(db.tables["raw_crm_jobs"], {j["job_id"]: j for j in JOBS})  # stored as returned
        st = db.tables["sync_state"]["crm"]
        self.assertEqual(st["status"], "ok")
        self.assertEqual(when(st["watermark"]), when("2026-09-22T23:32:00-05:00"))

    def test_next_run_only_asks_for_changes_and_updates_rows_in_place(self):
        db = FakeCrmDb()
        CRM.run(FakeCrmApi(JOBS), db)
        changed = JOBS[:1] + [job("J-2", "2026-09-23T15:00:00-05:00", "completed", 480.5)] + JOBS[2:]
        api = FakeCrmApi(changed)
        CRM.run(api, db)
        self.assertEqual([when(a) for a in api.asked], [when("2026-09-22T23:31:59-05:00")])  # watermark - 1s
        self.assertEqual(len(db.tables["raw_crm_jobs"]), 5)  # no duplicate J-2
        self.assertEqual(db.tables["raw_crm_jobs"]["J-2"]["status"], "completed")
        self.assertEqual(db.tables["raw_crm_jobs"]["J-2"]["revenue_usd"], 480.5)
        self.assertEqual(when(db.tables["sync_state"]["crm"]["watermark"]), when("2026-09-23T15:00:00-05:00"))

    def test_killed_inside_a_tie_resumes_without_skipping_jobs(self):
        db = FakeCrmDb()
        with self.assertRaises(KeyboardInterrupt):
            CRM.run(FakeCrmApi(JOBS, kill_after=2), db)  # pages: [J-1,J-2] [J-3,J-4] | killed before [J-5]
        self.assertEqual(sorted(db.tables["raw_crm_jobs"]), ["J-1", "J-2", "J-3", "J-4"])
        st = db.tables["sync_state"]["crm"]
        self.assertEqual(st["status"], "failed")
        self.assertEqual(when(st["watermark"]), when("2026-09-22T23:32:00-05:00"))  # same instant as J-5

        CRM.run(FakeCrmApi(JOBS), db)  # strictly-after the watermark alone would skip J-5
        self.assertEqual(sorted(db.tables["raw_crm_jobs"]), ["J-1", "J-2", "J-3", "J-4", "J-5"])
        self.assertEqual(db.tables["sync_state"]["crm"]["status"], "ok")

    def test_watermark_compares_times_not_text_across_utc_offsets(self):
        # 01:30-06:00 (07:30 UTC, after DST ends) is later than 01:45-05:00 (06:45 UTC),
        # even though "01:45" sorts after "01:30" as text.
        later, earlier = "2025-11-02T01:30:00-06:00", "2025-11-02T01:45:00-05:00"
        db = FakeCrmDb()
        CRM.run(FakeCrmApi([job("J-7", earlier), job("J-8", later)], page_size=1), db)
        self.assertEqual(when(db.tables["sync_state"]["crm"]["watermark"]), when(later))

    def test_rerun_with_no_changes_writes_almost_nothing(self):
        db = FakeCrmDb()
        CRM.run(FakeCrmApi(JOBS), db)
        api = FakeCrmApi(JOBS)
        CRM.run(api, db)
        self.assertEqual(len(db.tables["raw_crm_jobs"]), 5)
        self.assertEqual(api.pages_served, 2)  # only the 3 jobs in the last second come back


if __name__ == "__main__":
    unittest.main()
