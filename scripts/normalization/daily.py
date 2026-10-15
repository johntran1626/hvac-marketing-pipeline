"""Pure daily aggregation of current normalized source rows for GitHub #30.

This is a staging contract, not the existing database uniqueness constraint.
Rebuild complete affected source/day slices; do not add these totals to old
facts. No I/O, freshness inference, unique callers, or campaign attribution.
"""
from collections.abc import Iterable
from typing import Protocol, runtime_checkable
from dataclasses import dataclass
from decimal import Decimal, localcontext

@runtime_checkable
class Contribution(Protocol):
    """Minimal source-independent contract; concrete vendor adapters are optional."""
    analysis_date: str
    channel: str
    source_platform: str
    source_account_id: str | None
    campaign_id: str | None
    campaign_name: str | None
    brand_classification: str | None
    raw_key: tuple
    impressions: int
    clicks: int
    spend_usd: Decimal
    reported_leads: Decimal
BIGINT_MAX = 9223372036854775807


class DailyAggregationError(ValueError):
    """Analytical failure without exposing identifiers or raw payloads."""


@dataclass(frozen=True)
class DailyContribution:
    """One source/account/campaign/day/brand bucket, not a complete fact row.

    campaign_names retains every observed source label rather than choosing
    an arbitrary winner for renamed campaigns. None brand remains unresolved.
    source_row_count is provenance, not a unique-person or call count.
    """
    analysis_date: str
    channel: str
    source_platform: str
    source_account_id: str | None
    campaign_id: str | None
    brand_classification: str | None
    campaign_names: tuple[str, ...]
    source_row_count: int
    impressions: int
    clicks: int
    spend_usd: Decimal
    reported_leads: Decimal

    @property
    def bucket_key(self) -> tuple[str | None, ...]:
        return (self.analysis_date, self.channel, self.source_platform,
                self.source_account_id, self.campaign_id,
                self.brand_classification)


def _exact_sum(values: list[Decimal]) -> Decimal:
    # Enough precision for all integer/fractional digits and addition carry.
    integer_digits = max(max(value.adjusted() + 1, 0) for value in values)
    fractional_digits = max(max(-value.as_tuple().exponent, 0) for value in values)
    with localcontext() as context:
        context.prec = max(28, integer_digits + fractional_digits
                           + len(str(len(values))) + 1)
        return sum(values, Decimal(0))


def aggregate_daily(rows: Iterable[Contribution]) -> tuple[DailyContribution, ...]:
    """Aggregate one current version of each raw natural key.

    Any repeated source key raises, even if identical. With no update version
    in contributions, silently choosing first/last could keep stale spend or
    conversions. Use the loaders' current upserted raw rows before calling.
    Input may be a generator and may contain all three supported sources.
    """
    groups = {}
    seen = set()
    for row in rows:
        if not isinstance(row, Contribution) or row.source_platform not in {"google_ads", "meta_ads", "lsa"}:
            raise DailyAggregationError("expected a normalized source contribution")
        source_key = (row.source_platform, row.raw_key)
        if source_key in seen:
            raise DailyAggregationError(
                "duplicate source natural key; provide current upserted rows")
        seen.add(source_key)
        for field in ("impressions", "clicks"):
            value = getattr(row, field)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise DailyAggregationError(f"{field}: expected a non-negative integer")
        for field in ("spend_usd", "reported_leads"):
            value = getattr(row, field)
            if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
                raise DailyAggregationError(f"{field}: expected a finite non-negative Decimal")
        key = (row.analysis_date, row.channel, row.source_platform,
               row.source_account_id, row.campaign_id, row.brand_classification)
        groups.setdefault(key, []).append(row)

    output = []
    # Explicit nullable sorting keeps output stable without merging None/''
    # or relying on Python comparing None to strings.
    for key in sorted(groups, key=lambda key: tuple(
            (value is not None, value if value is not None else "") for value in key)):
        members = groups[key]
        impressions = sum(row.impressions for row in members)
        clicks = sum(row.clicks for row in members)
        if max(impressions, clicks) > BIGINT_MAX:
            raise DailyAggregationError("daily integer metric exceeds PostgreSQL bigint range")
        output.append(DailyContribution(
            analysis_date=key[0], channel=key[1], source_platform=key[2],
            source_account_id=key[3], campaign_id=key[4], brand_classification=key[5],
            campaign_names=tuple(sorted({row.campaign_name for row in members
                                         if row.campaign_name is not None})),
            source_row_count=len(members), impressions=impressions, clicks=clicks,
            spend_usd=_exact_sum([row.spend_usd for row in members]),
            reported_leads=_exact_sum([row.reported_leads for row in members]),
        ))
    return tuple(output)
