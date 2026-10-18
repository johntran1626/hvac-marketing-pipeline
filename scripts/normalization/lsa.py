"""Pure LSA lead normalization for GitHub #67 (extracted from PR #50).

Sources: docs/API.md, schema/normalized-fact-table.md, scripts/build_fact_lsa.sql.
No I/O, database writes, invented call metrics, or mutation of the raw record.
"""
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

CENTRAL = ZoneInfo("America/Chicago")
REFUND_STATUSES = frozenset({"CREDITED", "REFUNDED"})
CHARGE_STATUSES = frozenset({"CHARGED", "NOT_CHARGED"}) | REFUND_STATUSES
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
    lead_created_at: str
    credited_at: str | None
    cost_usd: Decimal
    spend_usd: Decimal | None
    reported_leads: Decimal
    charged_leads: int
    refunded_leads: int
    not_charged_leads: int
    unknown_status_leads: int

    @property
    def source_key(self) -> tuple[str, str | None, str]:
        """Account-qualified identity for consumers handling multiple accounts."""
        return (self.source_platform, self.source_account_id, self.lead_id)

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


def _account(row: Mapping[str, object]) -> str | None:
    # The documented API has no account field. Accept explicit adapter metadata
    # without inventing an account or collapsing identifiers across accounts.
    values = []
    for field in ("source_account_id", "account_id"):
        if row.get(field) is not None:
            values.append(_text(row, field, identifier=True))
    if len(set(values)) > 1:
        raise LsaNormalizationError("source_account_id", "conflicting account identifiers")
    return values[0] if values else None


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

    CREDITED/REFUNDED and NOT_CHARGED have zero net spend and one reported
    lead. Unknown states retain their exact text, have unknown (None) spend,
    and never increment charged/refunded counters. Do not coalesce that None
    to zero when aggregating. Credits restate the original Central creation
    day. Supply current upserted leads, not old and credited versions together.
    Original timestamp strings and source cost are retained verbatim/exactly.
    """
    if not isinstance(row, Mapping):
        raise LsaNormalizationError("row", "expected a record")
    created = _timestamp(row.get("lead_created_at"), "lead_created_at")
    status = _text(row, "charge_status", identifier=True)
    lead_type = _text(row, "lead_type")
    if lead_type not in LEAD_TYPES:
        raise LsaNormalizationError("lead_type", "unrecognized lead type")
    if "credited_at" not in row:
        raise LsaNormalizationError("credited_at", "missing nullable source field")
    credited = row["credited_at"]
    if status in REFUND_STATUSES or credited is not None:
        credit_time = _timestamp(credited, "credited_at")
        if credit_time < created:
            raise LsaNormalizationError("credited_at", "credit precedes lead creation")
        if status in {"CHARGED", "NOT_CHARGED"}:
            raise LsaNormalizationError("credited_at", "unexpected credit timestamp for charge state")
    cost = _cost(row.get("cost_usd"))
    return LsaContribution(
        lead_id=_text(row, "lead_id", identifier=True),
        analysis_date=created.astimezone(CENTRAL).date().isoformat(),
        channel="google_lsa",
        source_platform="lsa",
        source_account_id=_account(row),
        campaign_id=None,
        campaign_name=None,
        brand_classification="not_applicable",
        category=_text(row, "category"),
        lead_type=lead_type,
        charge_status=status,
        impressions=0,
        clicks=0,
        lead_created_at=row["lead_created_at"],
        credited_at=credited,
        cost_usd=cost,
        spend_usd=(cost if status == "CHARGED" else
                   Decimal(0) if status in CHARGE_STATUSES else None),
        reported_leads=Decimal(1),
        charged_leads=int(status == "CHARGED"),
        refunded_leads=int(status in REFUND_STATUSES),
        not_charged_leads=int(status == "NOT_CHARGED"),
        unknown_status_leads=int(status not in CHARGE_STATUSES),
    )
