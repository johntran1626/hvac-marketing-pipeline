"""Backfill every LSA lead from the Lab API into Supabase `raw_lsa_leads` (Issue #8).

Run from the repo root:  python3 scripts/backfill_lsa.py
Reads LAB_API_KEY, SUPABASE_URL and SUPABASE_SECRET_KEY from .env.local. Never prints them.
Standard library only.

- Pulls 31 days per request (the API's max), 200 rows per page, following next_cursor.
- On 429 or 503 it waits for Retry-After, then retries with a growing wait, up to MAX_TRIES.
- Upserts on lead_id, so running it again updates rows instead of duplicating them
  (LSA leads can flip from CHARGED to CREDITED up to 30 days later).
- Stores rows exactly as the API returns them.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

API = "https://ads-api.lab.zappstudios.us"
FIRST_DAY = date(2024, 10, 1)  # docs/API.md: "Data starts on 2024-10-01"
WINDOW_DAYS = 31
PAGE_SIZE = 200
MAX_TRIES = 6
PAUSE = 1.1  # seconds between API calls, stays under 60 requests a minute


def load_env(path=".env.local"):
    env = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip("\"'")
    for k in ("LAB_API_KEY", "SUPABASE_URL", "SUPABASE_SECRET_KEY"):
        if not env.get(k):
            raise SystemExit(f"Missing {k} in {path}")
    return env


def request(url, headers, body=None, method="GET"):
    """Send a request, retrying on 429/503 with Retry-After and a growing wait."""
    data = json.dumps(body).encode() if body is not None else None
    for attempt in range(1, MAX_TRIES + 1):
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            if e.code not in (429, 503) or attempt == MAX_TRIES:
                raise SystemExit(f"{method} {url.split('?')[0]} failed: {e.code} {e.read()[:200]!r}")
            wait = max(int(e.headers.get("Retry-After") or 0), 2 ** attempt)
            print(f"  {e.code}, waiting {wait}s (try {attempt}/{MAX_TRIES})")
            time.sleep(wait)
        except urllib.error.URLError as e:
            if attempt == MAX_TRIES:
                raise SystemExit(f"Network error: {e.reason}")
            print(f"  network error, waiting {2 ** attempt}s (try {attempt}/{MAX_TRIES})")
            time.sleep(2 ** attempt)


def fetch_window(env, start, end):
    """Every LSA lead whose Central-time created date is in [start, end]."""
    rows, cursor = [], None
    while True:
        params = {"start_date": start.isoformat(), "end_date": end.isoformat(), "limit": PAGE_SIZE}
        if cursor:
            params["cursor"] = cursor
        page = request(f"{API}/v1/lsa/leads?{urllib.parse.urlencode(params)}",
                       {"Authorization": f"Bearer {env['LAB_API_KEY']}"})
        rows.extend(page["data"])
        cursor = page["paging"]["next_cursor"]
        time.sleep(PAUSE)
        if not cursor:
            return rows


def upsert(env, rows):
    request(f"{env['SUPABASE_URL']}/rest/v1/raw_lsa_leads?on_conflict=lead_id",
            {"apikey": env["SUPABASE_SECRET_KEY"],
             "Authorization": f"Bearer {env['SUPABASE_SECRET_KEY']}",
             "Content-Type": "application/json",
             "Prefer": "resolution=merge-duplicates,return=minimal"},
            body=rows, method="POST")


def summary(env):
    """Row count and date range, read back from Supabase."""
    base = f"{env['SUPABASE_URL']}/rest/v1/raw_lsa_leads"
    h = {"apikey": env["SUPABASE_SECRET_KEY"], "Authorization": f"Bearer {env['SUPABASE_SECRET_KEY']}"}
    req = urllib.request.Request(f"{base}?select=lead_id&limit=1", headers={**h, "Prefer": "count=exact"})
    with urllib.request.urlopen(req, timeout=60) as r:
        count = r.headers["Content-Range"].split("/")[1]
    first = request(f"{base}?select=lead_created_at&order=lead_created_at.asc&limit=1", h)
    last = request(f"{base}?select=lead_created_at&order=lead_created_at.desc&limit=1", h)
    return count, first[0]["lead_created_at"], last[0]["lead_created_at"]


def main():
    env = load_env()
    health = request(f"{API}/v1/health", {})
    last_day = date.fromisoformat(health["data_through"])
    print(f"API data_through={last_day}. Backfilling {FIRST_DAY} to {last_day}.")

    total, start = 0, FIRST_DAY
    while start <= last_day:
        end = min(start + timedelta(days=WINDOW_DAYS - 1), last_day)
        rows = fetch_window(env, start, end)
        if rows:
            upsert(env, rows)
        total += len(rows)
        print(f"  {start} to {end}: {len(rows)} leads (running total {total})")
        start = end + timedelta(days=1)

    count, first, last = summary(env)
    print(f"\nDone. Pulled {total} leads from the API.")
    print(f"raw_lsa_leads now has {count} rows, lead_created_at from {first} to {last} (UTC).")


if __name__ == "__main__":
    main()
