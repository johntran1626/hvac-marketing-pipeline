"""Pure Google Ads ad-group normalization for GitHub #30.

Sources: docs/API.md and schema/normalized-fact-table.md.
Input matches raw_google_ads_insights. No I/O or raw-record mutation.
"""
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

BIGINT_MAX = 9223372036854775807
from .brand_rules import GOOGLE_BRAND_CAMPAIGNS, GOOGLE_NON_BRAND_CAMPAIGNS


class GoogleNormalizationError(ValueError):
    """Field-specific analytical failure without logging the raw payload."""

    def __init__(self, field: str, reason: str):
        self.field = field
        super().__init__(f"{field}: {reason}")


@dataclass(frozen=True)
class GoogleContribution:
    """One ad-group contribution, not a complete fact-table row.

    Unknown campaign IDs have brand_classification=None and need review
    before writing to the current non-null fact column.
    """
    analysis_date: str
    channel: str
    source_platform: str
    source_account_id: str
    campaign_id: str
    campaign_name: str
    ad_group_id: str
    ad_group_name: str
    brand_classification: str | None
    impressions: int
    clicks: int
    spend_usd: Decimal
    reported_leads: Decimal

    @property
    def raw_key(self) -> tuple[str, str, str, str]:
        return (self.analysis_date, self.source_account_id,
                self.campaign_id, self.ad_group_id)


def _text(row: Mapping[str, object], field: str, *, identifier: bool = False) -> str:
    value = row.get(field)
    if not isinstance(value, str):
        raise GoogleNormalizationError(field, "expected a string")
    if identifier and not value.strip():
        raise GoogleNormalizationError(field, "expected a non-empty identifier")
    return value


def _integer(row: Mapping[str, object], field: str) -> int:
    value = row.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise GoogleNormalizationError(field, "expected a non-negative integer")
    if value > BIGINT_MAX:
        raise GoogleNormalizationError(field, "exceeds PostgreSQL bigint range")
    return value


def _conversions(value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise GoogleNormalizationError("conversions", "expected a numeric value")
    # Decimal from numeric text avoids introducing binary-float artifacts.
    # Prefer JSON parse_float=Decimal upstream to retain the original precision.
    result = value if isinstance(value, Decimal) else Decimal(str(value))
    if not result.is_finite() or result < 0:
        raise GoogleNormalizationError("conversions", "expected a finite non-negative value")
    return result


def normalize_google_row(row: Mapping[str, object]) -> GoogleContribution:
    """Convert a current raw ad-group row; keep its Central account date.

    Campaign-level API aggregates lack ad-group fields and are rejected:
    mixing both API levels would double-count. Aggregate current ad-group
    contributions only after the shared fact grain is settled.
    """
    if not isinstance(row, Mapping):
        raise GoogleNormalizationError("row", "expected a record")
    day = _text(row, "date")
    try:
        parsed = date.fromisoformat(day)
    except ValueError:
        raise GoogleNormalizationError("date", "expected YYYY-MM-DD") from None
    if parsed.isoformat() != day:
        raise GoogleNormalizationError("date", "expected YYYY-MM-DD")
    campaign = _text(row, "campaign_id", identifier=True)
    classification = None
    if campaign in GOOGLE_BRAND_CAMPAIGNS:
        classification = "brand"
    elif campaign in GOOGLE_NON_BRAND_CAMPAIGNS:
        classification = "non_brand"
    micros = _integer(row, "cost_micros")
    # Quotient/remainder preserves all six decimal places, even when the
    # caller has a low Decimal precision. No division or cent rounding.
    dollars = Decimal(f"{micros // 1_000_000}.{micros % 1_000_000:06d}")
    return GoogleContribution(
        analysis_date=day,
        channel="google_ads",
        source_platform="google_ads",
        source_account_id=_text(row, "customer_id", identifier=True),
        campaign_id=campaign,
        campaign_name=_text(row, "campaign_name"),
        ad_group_id=_text(row, "ad_group_id", identifier=True),
        ad_group_name=_text(row, "ad_group_name"),
        brand_classification=classification,
        impressions=_integer(row, "impressions"),
        clicks=_integer(row, "clicks"),
        spend_usd=dollars,
        reported_leads=_conversions(row.get("conversions")),
    )
