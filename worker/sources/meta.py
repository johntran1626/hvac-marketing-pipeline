"""Meta full-window source; factual persistence requires the snapshot protocol."""
from datetime import date
from worker.sources import SOURCES
from worker.sync import Source
META = Source("meta", "/v1/meta/insights", "raw_meta_insights",
              "date_start,account_id,campaign_id,adset_id", date(2024,10,1), 7)
SOURCES[META.name] = META
