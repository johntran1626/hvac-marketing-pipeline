"""Saved progress in public.sync_state, one row per source."""
from datetime import datetime, timezone


def now():
    return datetime.now(timezone.utc).isoformat()


def load(db, source):
    rows = db.select("sync_state", source=f"eq.{source}")
    return rows[0] if rows else {"source": source}


def save(db, source, **fields):
    db.upsert("sync_state", [{"source": source, **fields, "updated_at": now()}], "source")
