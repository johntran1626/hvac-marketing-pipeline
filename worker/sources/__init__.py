"""Every source the worker syncs, by name. Each loader adds itself here."""
SOURCES = {}

from worker.sources import lsa  # noqa: E402,F401
