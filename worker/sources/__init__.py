"""Every source the worker syncs, by name. Each loader adds itself here."""
SOURCES = {}

from worker.sources import lsa  # noqa: E402,F401
from worker.sources import google_ads  # noqa: E402,F401
from worker.sources import calls  # noqa: E402,F401