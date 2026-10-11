"""Pure LSA lead normalization for GitHub #30.

Sources: docs/API.md, schema/normalized-fact-table.md, scripts/build_fact_lsa.sql.
No I/O, database writes, invented call metrics, or mutation of the raw record.
"""
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

CENTRAL = ZoneInfo("America/Chicago")
CHARGE_STATUSES = frozenset({"CHARGED", "CREDITED", "NOT_CHARGED"})
LEAD_TYPES = frozenset({"PHONE_CALL", "MESSAGE"})


class LsaNormalizationError(ValueError):
    """Field-specific analytical failure without exposing the full raw row."""

    def __init__(self, field: str, reason: str):
        self.field = field
        super().__init__(f"{field}: {reason}")


@dataclass(frozen=True)
class LsaContribution:
    """One current LSA lead contribution, not a complete fact-table row."""
    lead_id: str
    analysis_date: str
    channel: str
    source_platform: str
    source_account_id: str | None
    campaign_id: str | None
    campaign_name: str | None
    brand_classification: str
    category: str
    lead_type: str
    charge_status: str
    impressions: int
    clicks: int
    spend_usd: Decimal
    reported_leads: Decimal

    @property
    def raw_key(self) -> str:
        return self.lead_id


def _text(row: Mapping[str, object], field: str, *, identifier: bool = False) -> str:
    value = row.get(field)
    if not isinstance(value, str):
        raise LsaNormalizationError(field, "expected a string")
    if identifier and not value.strip():
        raise LsaNormalizationError(field, "expected a non-empty identifier")
    return value


def _timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise LsaNormalizationError(field, "expected an offset-aware timestamp")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise LsaNormalizationError(field, "expected an ISO 8601 timestamp") from None
    if result.tzinfo is None or result.utcoffset() is None:
        raise LsaNormalizationError(field, "timestamp requires an explicit offset")
    return result


def _cost(value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise LsaNormalizationError("cost_usd", "expected a numeric value")
    result = value if isinstance(value, Decimal) else Decimal(str(value))
    if not result.is_finite() or result < 0:
        raise LsaNormalizationError("cost_usd", "expected a finite non-negative value")
    return result


def normalize_lsa_row(row: Mapping[str, object]) -> LsaContribution:
    """Keep lead count/date; change only net spend for the current charge state.

    CREDITED and NOT_CHARGED contribute zero spend but still one reported lead.
    Credits affect the original Central creation day, never the credit day.
    Supply current upserted raw leads, not both old and credited versions.
    """
    if not isinstance(row, Mapping):
        raise LsaNormalizationError("row", "expected a record")
    created = _timestamp(row.get("lead_created_at"), "lead_created_at")
    status = _text(row, "charge_status")
    if status not in CHARGE_STATUSES:
        raise LsaNormalizationError("charge_status", "unrecognized charge state")
    lead_type = _text(row, "lead_type")
    if lead_type not in LEAD_TYPES:
        raise LsaNormalizationError("lead_type", "unrecognized lead type")
    if "credited_at" not in row:
        raise LsaNormalizationError("credited_at", "missing nullable source field")
    credited = row["credited_at"]
    if status == "CREDITED":
        credit_time = _timestamp(credited, "credited_at")
        if credit_time < created:
            raise LsaNormalizationError("credited_at", "credit precedes lead creation")
    elif credited is not None:
        raise LsaNormalizationError("credited_at", "unexpected credit timestamp for charge state")
    cost = _cost(row.get("cost_usd"))
    return LsaContribution(
        lead_id=_text(row, "lead_id", identifier=True),
        analysis_date=created.astimezone(CENTRAL).date().isoformat(),
        channel="google_lsa",
        source_platform="lsa",
        source_account_id=None,
        campaign_id=None,
        campaign_name=None,
        brand_classification="not_applicable",
        category=_text(row, "category"),
        lead_type=lead_type,
        charge_status=status,
        impressions=0,
        clicks=0,
        spend_usd=cost if status == "CHARGED" else Decimal(0),
        reported_leads=Decimal(1),
    )
