"""Tests for the API client (worker/api_client.py) and its retries (worker/http.py), Issue #36.

Fake HTTP responses only: no network, no keys, no calls against the group's shared rate limit.
Run from the repo root:  python3 -m unittest discover -s worker/tests -t . -v
"""
import email.message
import io
import json
import unittest
import urllib.error
import urllib.parse
from contextlib import redirect_stdout
from datetime import date, timedelta
from unittest import mock

from worker.api_client import PAGE_SIZE, WINDOW_DAYS, ApiClient, InvalidCursor, windows
from worker.http import MAX_TRIES, HTTPFailure, send

URL = "https://ads-api.lab.zappstudios.us/v1/calls?start_date=2026-09-01&end_date=2026-09-30&limit=200"
SECRET = "test-key-do-not-log-123"


class FakeResponse:
    """What urllib.request.urlopen returns on a 2xx."""
    def __init__(self, body):
        self.raw = json.dumps(body).encode()
        self.headers = email.message.Message()

    def read(self):
        return self.raw

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def error(status, body, retry_after=None):
    """What urllib.request.urlopen raises on a 4xx/5xx."""
    headers = email.message.Message()
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    return urllib.error.HTTPError(URL, status, "error", headers, io.BytesIO(json.dumps(body).encode()))


def fake_urlopen(*responses):
    """Hand out the given responses in order and record every request that was sent."""
    queue, sent = list(responses), []

    def urlopen(req, timeout=None):
        sent.append(req)
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    return urlopen, sent


RATE_LIMITED = {"error": "rate_limited"}
UNAVAILABLE = {"error": "temporarily_unavailable"}
OK = {"data": [{"call_id": "call_1"}], "paging": {"next_cursor": None}}


class PagingTest(unittest.TestCase):
    def test_follows_next_cursor_with_the_same_params_until_null(self):
        urlopen, sent = fake_urlopen(
            FakeResponse({"data": [{"call_id": "a"}, {"call_id": "b"}], "paging": {"next_cursor": "c1"}}),
            FakeResponse({"data": [{"call_id": "c"}], "paging": {"next_cursor": "c2"}}),
            FakeResponse({"data": [{"call_id": "d"}], "paging": {"next_cursor": None}}),
        )
        params = {"start_date": "2026-09-01", "end_date": "2026-09-30"}
        with mock.patch("urllib.request.urlopen", urlopen):
            pages = list(ApiClient(SECRET, pause=0).pages("/v1/calls", params))

        self.assertEqual([[r["call_id"] for r in rows] for rows, _ in pages], [["a", "b"], ["c"], ["d"]])
        self.assertEqual([cursor for _, cursor in pages], ["c1", "c2", None])
        self.assertEqual(len(sent), 3)  # stopped when next_cursor was null

        queries = [urllib.parse.parse_qs(urllib.parse.urlsplit(r.full_url).query) for r in sent]
        self.assertEqual([q.get("cursor") for q in queries], [None, ["c1"], ["c2"]])
        for q in queries:  # every page repeats the same request, only the cursor changes
            self.assertEqual(q["start_date"], ["2026-09-01"])
            self.assertEqual(q["end_date"], ["2026-09-30"])
            self.assertEqual(q["limit"], [str(PAGE_SIZE)])
        self.assertEqual(PAGE_SIZE, 200)  # docs/API.md: max 200
        self.assertTrue(all(urllib.parse.urlsplit(r.full_url).path == "/v1/calls" for r in sent))

    def test_rejected_cursor_raises_invalid_cursor(self):
        urlopen, _ = fake_urlopen(error(400, {"error": "invalid_cursor"}))
        with mock.patch("urllib.request.urlopen", urlopen):
            with self.assertRaises(InvalidCursor):
                list(ApiClient(SECRET, pause=0).pages("/v1/calls", {"start_date": "2026-09-01",
                                                                    "end_date": "2026-09-30"}, cursor="old"))

    def test_other_400s_are_not_mistaken_for_a_bad_cursor(self):
        urlopen, _ = fake_urlopen(error(400, {"error": "date_range_too_large", "max_days": 31}))
        with mock.patch("urllib.request.urlopen", urlopen):
            with self.assertRaises(HTTPFailure) as ctx:
                list(ApiClient(SECRET, pause=0).pages("/v1/calls", {"start_date": "2026-01-01",
                                                                    "end_date": "2026-03-01"}))
        self.assertEqual(ctx.exception.status, 400)
        self.assertIn("date_range_too_large", ctx.exception.body)


class WindowsTest(unittest.TestCase):
    def test_windows_cover_every_day_once_and_never_exceed_31_days(self):
        first, last = date(2024, 10, 1), date(2026, 10, 8)
        got = list(windows(first, last))
        self.assertEqual(WINDOW_DAYS, 31)  # docs/API.md: max 31 days per request
        self.assertEqual(got[0][0], first)
        self.assertEqual(got[-1][1], last)
        for start, end in got:
            self.assertLessEqual((end - start).days + 1, 31)  # both dates are inclusive
            self.assertLessEqual(start, end)
        for (_, prev_end), (next_start, _) in zip(got, got[1:]):
            self.assertEqual(next_start, prev_end + timedelta(days=1))  # no gap, no overlap

    def test_single_day_and_empty_range(self):
        day = date(2026, 9, 22)
        self.assertEqual(list(windows(day, day)), [(day, day)])
        self.assertEqual(list(windows(day, day - timedelta(days=1))), [])


class RetryTest(unittest.TestCase):
    def send_with(self, *responses):
        """Call send() with fake responses. Returns (result, waits, requests sent, log)."""
        urlopen, sent = fake_urlopen(*responses)
        waits, log = [], io.StringIO()
        with mock.patch("urllib.request.urlopen", urlopen), redirect_stdout(log):
            result = send(URL, {"Authorization": f"Bearer {SECRET}"}, sleep=waits.append)
        return result, waits, sent, log.getvalue()

    def test_429_waits_for_retry_after_then_succeeds(self):
        (body, _), waits, sent, _ = self.send_with(error(429, RATE_LIMITED, "7"), FakeResponse(OK))
        self.assertEqual(body, OK)
        self.assertEqual(waits, [7])  # the server's Retry-After, not our own shorter guess
        self.assertEqual(len(sent), 2)
        self.assertEqual(sent[0].full_url, sent[1].full_url)  # the same request again

    def test_503_retries_with_growing_wait_then_succeeds(self):
        (body, _), waits, sent, _ = self.send_with(
            error(503, UNAVAILABLE, "2"), error(503, UNAVAILABLE, "2"), error(503, UNAVAILABLE, "2"),
            FakeResponse(OK))
        self.assertEqual(body, OK)
        self.assertEqual(waits, [2, 4, 8])  # docs/API.md: "for example 2, 4, 8 seconds"
        self.assertEqual(len(sent), 4)

    def test_gives_up_after_the_retry_limit(self):
        urlopen, sent = fake_urlopen(*[error(503, UNAVAILABLE, "2") for _ in range(MAX_TRIES + 5)])
        waits = []
        with mock.patch("urllib.request.urlopen", urlopen), redirect_stdout(io.StringIO()):
            with self.assertRaises(HTTPFailure) as ctx:
                send(URL, {}, sleep=waits.append)
        self.assertEqual(ctx.exception.status, 503)
        self.assertEqual(len(sent), MAX_TRIES)       # stopped, didn't loop forever
        self.assertEqual(len(waits), MAX_TRIES - 1)  # no pointless wait after the last try
        self.assertEqual(waits, sorted(waits))       # waits only grow

    def test_other_errors_fail_at_once_without_retrying(self):
        for status, body in [(401, {"error": "unauthorized"}), (400, {"error": "invalid_cursor"}),
                             (404, {"error": "not_found"})]:
            urlopen, sent = fake_urlopen(error(status, body))
            waits = []
            with mock.patch("urllib.request.urlopen", urlopen):
                with self.assertRaises(HTTPFailure) as ctx:
                    send(URL, {}, sleep=waits.append)
            self.assertEqual((ctx.exception.status, len(sent), waits), (status, 1, []))

    def test_retry_after_that_is_not_a_whole_number_still_waits(self):
        (body, _), waits, _, _ = self.send_with(error(429, RATE_LIMITED, "1.5"), FakeResponse(OK))
        self.assertEqual(body, OK)
        self.assertEqual(waits, [2])  # 1.5s rounded up, and never shorter than the growing wait

    def test_unreadable_retry_after_falls_back_to_growing_wait(self):
        (body, _), waits, _, _ = self.send_with(error(503, UNAVAILABLE, "soon"), FakeResponse(OK))
        self.assertEqual(body, OK)
        self.assertEqual(waits, [2])

    def test_retry_log_has_no_key_and_no_query_string(self):
        _, _, _, log = self.send_with(error(429, RATE_LIMITED, "3"), error(503, UNAVAILABLE, "2"),
                                      FakeResponse(OK))
        self.assertIn("429", log)
        self.assertIn("503", log)
        self.assertIn("/v1/calls", log)
        self.assertNotIn(SECRET, log)
        self.assertNotIn("Bearer", log)
        self.assertNotIn("start_date", log)  # query strings (cursors, dates) stay out of the log

    def test_failure_message_has_no_key(self):
        urlopen, _ = fake_urlopen(error(401, {"error": "unauthorized"}))
        with mock.patch("urllib.request.urlopen", urlopen):
            with self.assertRaises(HTTPFailure) as ctx:
                send(URL, {"Authorization": f"Bearer {SECRET}"}, sleep=lambda s: None)
        self.assertNotIn(SECRET, str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
