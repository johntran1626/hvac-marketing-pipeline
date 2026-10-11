"""One HTTP call with retries, shared by the API client and the Supabase client. Standard library only."""
import json
import math
import time
import urllib.error
import urllib.request

MAX_TRIES = 6


class HTTPFailure(Exception):
    def __init__(self, status, body, where):
        super().__init__(f"{where} failed: {status} {body[:200]!r}")
        self.status = status
        self.body = body


def retry_after(headers):
    """Seconds the server asked us to wait, rounded up. Unreadable or missing counts as 0."""
    try:
        return max(0, math.ceil(float(headers.get("Retry-After") or 0)))
    except (TypeError, ValueError, OverflowError):
        return 0


def send(url, headers, body=None, method="GET", sleep=time.sleep):
    """Send a request. On 429/503 wait for Retry-After (or a growing wait) and retry, up to MAX_TRIES.

    Returns (parsed JSON or None, response headers). Logs only the path, never headers or keys.
    """
    data = json.dumps(body).encode() if body is not None else None
    where = f"{method} {url.split('?')[0]}"
    for attempt in range(1, MAX_TRIES + 1):
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
                return (json.loads(raw) if raw else None), r.headers
        except urllib.error.HTTPError as e:
            text = e.read().decode(errors="replace")
            if e.code not in (429, 503) or attempt == MAX_TRIES:
                raise HTTPFailure(e.code, text, where) from None
            wait = max(retry_after(e.headers), 2 ** attempt)
            print(f"  {e.code} on {where}, waiting {wait}s (try {attempt}/{MAX_TRIES})")
            sleep(wait)
        except urllib.error.URLError as e:
            if attempt == MAX_TRIES:
                raise HTTPFailure(0, str(e.reason), where) from None
            print(f"  network error on {where}, waiting {2 ** attempt}s (try {attempt}/{MAX_TRIES})")
            sleep(2 ** attempt)
