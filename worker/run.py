"""Run the worker.

From the repo root:
  python3 -m worker.run              # every source
  python3 -m worker.run lsa          # one source
"""
import signal
import sys

from worker import sync
from worker.api_client import ApiClient
from worker.config import load_env
from worker.db import Db
from worker.sources import SOURCES


def stop(signum, frame):
    # GitHub Actions (and `kill`) stop a job with SIGTERM. Turn it into an exception so
    # sync.run records the run as failed; progress already saved stays saved.
    raise SystemExit(f"stopped by signal {signum}")


def main(names):
    signal.signal(signal.SIGTERM, stop)
    env = load_env()
    api = ApiClient(env["LAB_API_KEY"])
    db = Db(env["SUPABASE_URL"], env["SUPABASE_SECRET_KEY"])
    unknown = [n for n in names if n not in SOURCES]
    if unknown:
        raise SystemExit(f"Unknown source {unknown}. Choose from {list(SOURCES)}")
    for name in names or SOURCES:
        src = SOURCES[name]
        if hasattr(src, "run"):
            src.run(api, db)  # incremental sources (CRM) run their own loop
        else:
            sync.run(api, db, src)


if __name__ == "__main__":
    main(sys.argv[1:])
