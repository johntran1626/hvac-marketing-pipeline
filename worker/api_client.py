"""Lab Ads API client: paging and windows (docs/API.md). Ruslan's #36 hardens and tests this file."""
import time
import urllib.parse
from datetime import date, timedelta

from worker.http import HTTPFailure, send

API = "https://ads-api.lab.zappstudios.us"
PAGE_SIZE = 200   # API max
WINDOW_DAYS = 31  # API max per request
PAUSE = 1.1       # seconds between calls: 60 requests a minute is shared by the whole group


class InvalidCursor(Exception):
    """The API rejected a saved cursor. The caller restarts that window from page 1."""


class ApiClient:
    def __init__(self, key, pause=PAUSE):
        self.headers = {"Authorization": f"Bearer {key}"}
        self.pause = pause

    def data_through(self):
        body, _ = send(f"{API}/v1/health", {})
        return date.fromisoformat(body["data_through"])

    def pages(self, path, params, cursor=None):
        """Yield (rows, next_cursor) for every page. Every page repeats the same params plus the cursor."""
        while True:
            q = {**params, "limit": PAGE_SIZE}
            if cursor:
                q["cursor"] = cursor
            try:
                body, _ = send(f"{API}{path}?{urllib.parse.urlencode(q)}", self.headers)
            except HTTPFailure as e:
                if e.status == 400 and "invalid_cursor" in e.body:
                    raise InvalidCursor() from None
                raise
            time.sleep(self.pause)
            cursor = body["paging"]["next_cursor"]
            yield body["data"], cursor
            if not cursor:
                return


def windows(first, last, days=WINDOW_DAYS):
    """Split [first, last] into inclusive windows of at most `days` days."""
    start = first
    while start <= last:
        end = min(start + timedelta(days=days - 1), last)
        yield start, end
        start = end + timedelta(days=1)
