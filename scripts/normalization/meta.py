"""Pure Meta API-row normalization for GitHub #30.

Sources: docs/API.md and schema/normalized-fact-table.md.
No network, database writes, worker state, or raw-record mutation.
"""
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, localcontext
import re

from .brand_rules import META_NON_BRAND_CAMPAIGNS
BIGINT_MAX = 9223372036854775807
_INTEGER = re.compile(r"[0-9]+")
_DECIMAL = re.compile(r"[0-9]+(?:\.[0-9]+)?")


class MetaNormalizationError(ValueError):
    """Invalid analytical input; field is safe to log without the raw payload."""

    def __init__(self, field: str, reason: str):
        self.field = field
        super().__init__(f"{field}: {reason}")


@dataclass(frozen=True)
class MetaContribution:
    """One ad-set contribution, NOT a complete fact_marketing_daily row.

    None brand classification means an unknown ID needs review. Do not insert
    it into the existing non-null fact column or infer non-brand from its name.
    """
    analysis_date: str
    channel: str
    source_platform: str
    source_account_id: str
    campaign_id: str
    campaign_name: str
    adset_id: str
    adset_name: str
    brand_classification: str | None
    impressions: int
    clicks: int
    spend_usd: Decimal
    reported_leads: Decimal

    @property
    def raw_key(self) -> tuple[str, str, str, str]:
        return (self.analysis_date, self.source_account_id,
                self.campaign_id, self.adset_id)


def _text(row: Mapping[str, object], field: str, *, identifier: bool = False) -> str:
    value = row.get(field)
    if not isinstance(value, str):
        raise MetaNormalizationError(field, "expected a string")
    if identifier and not value.strip():
        raise MetaNormalizationError(field, "expected a non-empty identifier")
    return value


def _day(row: Mapping[str, object], field: str) -> str:
    value = _text(row, field)
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise MetaNormalizationError(field, "expected YYYY-MM-DD") from None
    if parsed.isoformat() != value:
        raise MetaNormalizationError(field, "expected YYYY-MM-DD")
    return value


def _integer(row: Mapping[str, object], field: str) -> int:
    value = _text(row, field)
    if not _INTEGER.fullmatch(value):
        raise MetaNormalizationError(field, "expected a non-negative integer string")
    try:
        result = int(value)
    except ValueError:
        raise MetaNormalizationError(field, "integer cannot be represented") from None
    if result > BIGINT_MAX:
        raise MetaNormalizationError(field, "exceeds PostgreSQL bigint range")
    return result


def _decimal(value: object, field: str) -> Decimal:
    if not isinstance(value, str) or not _DECIMAL.fullmatch(value):
        raise MetaNormalizationError(field, "expected a non-negative decimal string")
    return Decimal(value)


def extract_meta_reported_leads(actions: object) -> Decimal:
    """Sum only exact action_type='lead' entries; empty list means zero.

    Non-lead values need not be numeric because they do not enter this metric.
    Missing/malformed lead values are errors rather than invented zeroes.
    """
    if not isinstance(actions, list):
        raise MetaNormalizationError("actions", "expected a JSON array")
    values = []
    for action in actions:
        if not isinstance(action, Mapping) or not isinstance(action.get("action_type"), str):
            raise MetaNormalizationError("actions.action_type", "expected an action object with a string type")
        if action["action_type"] == "lead":
            values.append(_decimal(action.get("value"), "actions.lead.value"))
    if not values:
        return Decimal(0)
    # Retain exact additions even if a caller uses a low global Decimal precision.
    integer_digits = max(max(v.adjusted() + 1, 0) for v in values)
    fractional_digits = max(max(-v.as_tuple().exponent, 0) for v in values)
    with localcontext() as context:
        context.prec = max(28, integer_digits + fractional_digits + len(str(len(values))) + 1)
        return sum(values, Decimal(0))


def normalize_meta_row(row: Mapping[str, object]) -> MetaContribution:
    """Normalize one current raw row, preserving its Pacific calendar date.

    Call this on current upserted raw rows. Passing both old and restated
    versions to later aggregation would double-count; this function does not
    guess source ordering, deduplicate pages, or calculate unique callers.
    """
    if not isinstance(row, Mapping):
        raise MetaNormalizationError("row", "expected a record")
    day = _day(row, "date_start")
    if _day(row, "date_stop") != day:
        raise MetaNormalizationError("date_stop", "expected the same account day as date_start")
    account = _text(row, "account_id", identifier=True)
    campaign = _text(row, "campaign_id", identifier=True)
    return MetaContribution(
        analysis_date=day,
        channel="meta",
        source_platform="meta_ads",
        source_account_id=account,
        campaign_id=campaign,
        campaign_name=_text(row, "campaign_name"),
        adset_id=_text(row, "adset_id", identifier=True),
        adset_name=_text(row, "adset_name"),
        brand_classification="non_brand" if campaign in META_NON_BRAND_CAMPAIGNS else None,
        impressions=_integer(row, "impressions"),
        clicks=_integer(row, "clicks"),
        spend_usd=_decimal(row.get("spend"), "spend"),
        reported_leads=extract_meta_reported_leads(row.get("actions")),
    )
