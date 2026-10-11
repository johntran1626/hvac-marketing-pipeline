"""Resume tests for worker/sync.py with a fake API and a fake database. No network, no keys.

Run from the repo root:  python3 -m unittest discover -s worker/tests -t . -v
"""
import unittest
from datetime import date

from worker import sync
from worker.api_client import InvalidCursor

DAYS = [date(2024, 10, d) for d in range(1, 31)] + [date(2024, 11, d) for d in range(1, 21)]  # 50 days


class FakeApi:
    """Two rows a day, 10 rows a page. Raises KeyboardInterrupt after `kill_after` pages."""
    def __init__(self, kill_after=None, reject_cursor=False):
        self.calls, self.kill_after, self.reject_cursor = [], kill_after, reject_cursor

    def data_through(self):
        return DAYS[-1]

    def pages(self, path, params, cursor=None):
        if cursor and self.reject_cursor:
            self.reject_cursor = False
            raise InvalidCursor()
        rows = [{"id": f"{d}-{i}"} for d in DAYS
                if params["start_date"] <= d.isoformat() <= params["end_date"] for i in range(2)]
        page = int(cursor or 0)
        while True:
            if self.kill_after is not None and len(self.calls) == self.kill_after:
                raise KeyboardInterrupt
            self.calls.append((params["start_date"], page))
            nxt = page + 1 if (page + 1) * 10 < len(rows) else None
            yield rows[page * 10:(page + 1) * 10], (str(nxt) if nxt else None)
            if nxt is None:
                return
            page = nxt


class FakeDb:
    def __init__(self):
        self.tables = {"sync_state": {}, "raw": {}}
        self.upserts = 0

    def upsert(self, table, rows, on_conflict):
        for r in rows:
            key = r[on_conflict]
            self.tables[table][key] = {**self.tables[table].get(key, {}), **r}
        if table == "raw":
            self.upserts += len(rows)

    def select(self, table, **filters):
        key = filters["source"].removeprefix("eq.")
        row = self.tables[table].get(key)
        return [row] if row else []


SRC = sync.Source("test", "/v1/test", "raw", "id", first_day=DAYS[0], refresh_days=7)


class ResumeTest(unittest.TestCase):
    def test_full_run_loads_every_row_once(self):
        db = FakeDb()
        sync.run(FakeApi(), db, SRC)
        self.assertEqual(len(db.tables["raw"]), 100)
        st = db.tables["sync_state"]["test"]
        self.assertEqual((st["status"], st["backfilled_through"], st["cursor"]), ("ok", "2024-11-20", None))

    def test_killed_run_resumes_from_saved_cursor(self):
        db = FakeDb()
        with self.assertRaises(KeyboardInterrupt):
            sync.run(FakeApi(kill_after=4), db, SRC)  # window 1 has 7 pages; killed after page 4
        st = db.tables["sync_state"]["test"]
        self.assertEqual((st["status"], st["window_start"], st["cursor"]), ("failed", "2024-10-01", "4"))

        api = FakeApi()
        sync.run(api, db, SRC)
        self.assertEqual(api.calls[0], ("2024-10-01", 4))  # picked up at page 4, not page 0
        self.assertNotIn(("2024-10-01", 0), api.calls[:7])  # finished pages were not redone
        self.assertEqual(len(db.tables["raw"]), 100)        # nothing missing, nothing duplicated
        self.assertEqual(db.tables["sync_state"]["test"]["status"], "ok")

    def test_rerun_only_refreshes_recent_days(self):
        db = FakeDb()
        sync.run(FakeApi(), db, SRC)
        api = FakeApi()
        sync.run(api, db, SRC)
        self.assertEqual({c[0] for c in api.calls}, {"2024-11-14"})  # just the 7-day refresh
        self.assertEqual(len(db.tables["raw"]), 100)

    def test_rejected_cursor_restarts_window(self):
        db = FakeDb()
        with self.assertRaises(KeyboardInterrupt):
            sync.run(FakeApi(kill_after=2), db, SRC)
        sync.run(FakeApi(reject_cursor=True), db, SRC)
        self.assertEqual(len(db.tables["raw"]), 100)
        self.assertEqual(db.tables["sync_state"]["test"]["status"], "ok")


if __name__ == "__main__":
    unittest.main()
