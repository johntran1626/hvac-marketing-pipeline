"""Tests for the calls loader (worker/sources/calls.py), Issue #37. Fake API and database: no network, no keys.

Run from the repo root:  python3 -m unittest discover -s worker/tests -t . -v
"""
import copy
import unittest
from datetime import date

from worker import sync
from worker.sources import SOURCES
from worker.sources.calls import CALLS
from worker.tests.test_sync import FakeDb

# Shaped like docs/API.md's /v1/calls example. The second call is 9:30pm Central on 2024-10-01,
# which is already 2024-10-02 in UTC: it must stay in the 2024-10-01 window, timestamp untouched.
API_ROWS = [
    {"call_id": "call_0000001", "started_at": "2024-10-01T14:05:00Z", "duration_sec": 720,
     "tracking_number": "(713) 555-0115", "source": "google_ads", "campaign_id": "20114567803",
     "caller_hash": "695240ed4c93", "first_time_caller": True},
    {"call_id": "call_0000002", "started_at": "2024-10-02T02:30:00Z", "duration_sec": 12,
     "tracking_number": "(713) 555-0199", "source": "direct", "campaign_id": None,
     "caller_hash": "0a1b2c3d4e5f", "first_time_caller": False},
    {"call_id": "call_0000003", "started_at": "2024-10-03T16:00:00Z", "duration_sec": 30,
     "tracking_number": "(713) 555-0142", "source": "gbp", "campaign_id": None,
     "caller_hash": "695240ed4c93", "first_time_caller": False},
]
CENTRAL_DAY = {"call_0000001": "2024-10-01", "call_0000002": "2024-10-01", "call_0000003": "2024-10-03"}
LAST_DAY = date(2024, 10, 3)


class FakeCallsApi:
    """Serves API_ROWS by Central day, the way the real API filters, one row per page."""
    def __init__(self):
        self.requests = []

    def data_through(self):
        return LAST_DAY

    def pages(self, path, params, cursor=None):
        self.requests.append((path, params["start_date"], params["end_date"]))
        rows = [copy.deepcopy(r) for r in API_ROWS
                if params["start_date"] <= CENTRAL_DAY[r["call_id"]] <= params["end_date"]]
        start = int(cursor or 0)
        for i in range(start, len(rows)):
            yield [rows[i]], (str(i + 1) if i + 1 < len(rows) else None)
        if not rows:
            yield [], None


class FakeRawDb(FakeDb):
    def __init__(self):
        super().__init__()
        self.tables["raw_calls"] = {}


class CallsLoaderTest(unittest.TestCase):
    def test_registered_with_the_documented_endpoint_table_and_key(self):
        self.assertIs(SOURCES["calls"], CALLS)
        self.assertEqual((CALLS.path, CALLS.table, CALLS.on_conflict), ("/v1/calls", "raw_calls", "call_id"))
        self.assertEqual(CALLS.first_day, date(2024, 10, 1))  # docs/API.md: data starts 2024-10-01

    def test_rows_are_stored_exactly_as_the_api_returned_them(self):
        db = FakeRawDb()
        sync.run(FakeCallsApi(), db, CALLS)
        stored = db.tables["raw_calls"]
        self.assertEqual(sorted(stored), [r["call_id"] for r in API_ROWS])
        for row in API_ROWS:  # same keys, same values: UTC timestamps, null campaign_id, flags, hashes
            self.assertEqual(stored[row["call_id"]], row)

    def test_windows_are_requested_as_central_dates(self):
        api = FakeCallsApi()
        sync.run(api, FakeRawDb(), CALLS)
        self.assertEqual(api.requests[0], ("/v1/calls", "2024-10-01", "2024-10-03"))
        self.assertEqual(api.requests[-1], ("/v1/calls", "2024-10-03", "2024-10-03"))  # 1-day refresh

    def test_rerun_does_not_duplicate_and_only_refreshes_the_last_day(self):
        db = FakeRawDb()
        sync.run(FakeCallsApi(), db, CALLS)
        api = FakeCallsApi()
        sync.run(api, db, CALLS)
        self.assertEqual(len(db.tables["raw_calls"]), 3)
        self.assertEqual(api.requests, [("/v1/calls", "2024-10-03", "2024-10-03")])
        self.assertEqual(db.tables["sync_state"]["calls"]["backfilled_through"], "2024-10-03")


if __name__ == "__main__":
    unittest.main()
