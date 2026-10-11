"""Pure call-record normalization and explicitly selected lead-rule summaries.

GitHub #31 staging contract; no I/O, person/CRM joins or paid-platform metrics.
"""
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

CENTRAL = ZoneInfo("America/Chicago")
CHANNELS = frozenset({"google_ads", "google_lsa", "meta", "gbp", "website", "direct"})
from .brand_rules import (
    GOOGLE_BRAND_CAMPAIGNS as GOOGLE_BRAND,
    GOOGLE_NON_BRAND_CAMPAIGNS as GOOGLE_NON_BRAND,
)
INTEGER_MAX = 2147483647


class CallNormalizationError(ValueError):
    """Field-specific error without exposing raw payloads or caller identifiers."""


def _text(row: Mapping[str, object], field: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise CallNormalizationError(f"{field}: expected a non-empty string")
    return value


def _duration(value: object) -> int:
    if type(value) is not int or not 0 <= value <= INTEGER_MAX:
        raise CallNormalizationError("duration_sec: expected a non-negative PostgreSQL integer")
    return value


@dataclass(frozen=True)
class LeadRule:
    """Explicit threshold: 0 compares schema rule; 30 compares M1 memo rule.

    Integration uses QUALIFIED_LEAD_RULE; other thresholds are comparison-only.
    The raw first_time_caller flag is always required under either threshold.
    """
    min_duration_sec: int

    def __post_init__(self):
        _duration(self.min_duration_sec)


# Approved M2 rule: first-time flag AND at least 30 seconds.
QUALIFIED_LEAD_RULE = LeadRule(30)

@dataclass(frozen=True)
class CallContribution:
    """One observed call, not a complete fact row or an advertising account join."""
    call_id: str
    started_at: datetime
    analysis_date: str
    observed_source: str
    observed_campaign_id: str | None
    channel: str
    source_platform: str
    source_account_id: None
    campaign_id: str | None
    campaign_name: None
    brand_classification: str | None
    caller_hash: str
    tracking_number: str
    duration_sec: int
    first_time_caller: bool
    attribution_issues: tuple[str, ...]

    @property
    def raw_key(self) -> str:
        return self.call_id


def normalize_call_row(row: Mapping[str, object]) -> CallContribution:
    """Preserve observed source/first-time status; convert call start to Central.

    Google IDs can classify brand using the reviewed source-specific mapping.
    Account and campaign name remain unknown until an unambiguous dimension
    join is supported. Unknown sources are explicitly unattributed, preserving
    the original label. Unsupported campaign links are retained only as
    observed_campaign_id and flagged; they do not manufacture attribution.
    """
    if not isinstance(row, Mapping):
        raise CallNormalizationError("row: expected a record")
    timestamp = _text(row, "started_at")
    try:
        started = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        raise CallNormalizationError("started_at: expected an ISO timestamp") from None
    if started.tzinfo is None or started.utcoffset() is None:
        raise CallNormalizationError("started_at: timestamp requires an explicit offset")
    started = started.astimezone(timezone.utc)
    first = row.get("first_time_caller")
    if type(first) is not bool:
        raise CallNormalizationError("first_time_caller: expected a JSON boolean")
    if "campaign_id" not in row:
        raise CallNormalizationError("campaign_id: missing nullable source field")
    observed_campaign = row["campaign_id"]
    if observed_campaign is not None and (
            not isinstance(observed_campaign, str) or not observed_campaign.strip()):
        raise CallNormalizationError("campaign_id: expected null or a non-empty string")
    source = _text(row, "source")
    channel = source if source in CHANNELS else "unattributed"
    issues = []
    campaign = None
    brand = "not_applicable"
    if source not in CHANNELS:
        issues.append("unknown_source")
    if source == "google_ads":
        campaign = observed_campaign
        brand = None
        if campaign is None:
            issues.append("missing_google_campaign")
        elif campaign in GOOGLE_BRAND:
            brand = "brand"
        elif campaign in GOOGLE_NON_BRAND:
            brand = "non_brand"
        else:
            issues.append("unknown_google_campaign")
    elif observed_campaign is not None:
        issues.append("unsupported_campaign_source")
    return CallContribution(
        call_id=_text(row, "call_id"), started_at=started,
        analysis_date=started.astimezone(CENTRAL).date().isoformat(),
        observed_source=source, observed_campaign_id=observed_campaign,
        channel=channel, source_platform="call_tracking", source_account_id=None,
        campaign_id=campaign, campaign_name=None, brand_classification=brand,
        caller_hash=_text(row, "caller_hash"), tracking_number=_text(row, "tracking_number"),
        duration_sec=_duration(row.get("duration_sec")), first_time_caller=first,
        attribution_issues=tuple(issues),
    )


@dataclass(frozen=True)
class DailyCalls:
    """Daily call-only metrics under one explicit candidate lead rule.

    Additive leads require the cross-history first-time flag validation below.
    Production must apply the same check against persisted caller history,
    not only within each independently fetched date window.
    """
    analysis_date: str
    channel: str
    source_platform: str
    source_account_id: None
    campaign_id: str | None
    brand_classification: str | None
    min_duration_sec: int
    calls: int
    first_time_calls: int
    returning_calls: int
    unique_leads: int
    unresolved_calls: int
    observed_sources: tuple[str, ...]
    attribution_issues: tuple[str, ...]

    @property
    def bucket_key(self) -> tuple[str | None, ...]:
        return (self.analysis_date, self.channel, self.source_platform,
                self.source_account_id, self.campaign_id, self.brand_classification)


def aggregate_calls(rows: Iterable[CallContribution], *, rule: LeadRule) -> tuple[DailyCalls, ...]:
    """Count each call once; reject repeated first-time hashes across this input.

    Duplicate IDs (including restatements) are errors. Multiple first-time
    records for a caller are an analytical conflict: do not silently pick a
    channel/day or upgrade a short first call when a later call qualifies.
    Returning calls count as calls but never as new leads.
    """
    if not isinstance(rule, LeadRule):
        raise CallNormalizationError("an explicit LeadRule is required")
    groups = {}
    seen_calls = set()
    first_time_hashes = set()
    for row in rows:
        if not isinstance(row, CallContribution):
            raise CallNormalizationError("expected a normalized call contribution")
        if row.raw_key in seen_calls:
            raise CallNormalizationError("duplicate call_id; provide current upserted rows")
        seen_calls.add(row.raw_key)
        if row.first_time_caller:
            if row.caller_hash in first_time_hashes:
                raise CallNormalizationError("caller has multiple first-time records in supplied history")
            first_time_hashes.add(row.caller_hash)
        key = (row.analysis_date, row.channel, row.source_platform,
               row.source_account_id, row.campaign_id, row.brand_classification)
        groups.setdefault(key, []).append(row)

    output = []
    for key in sorted(groups, key=lambda k: tuple(
            (v is not None, v if v is not None else "") for v in k)):
        members = groups[key]
        first_count = sum(row.first_time_caller for row in members)
        output.append(DailyCalls(
            analysis_date=key[0], channel=key[1], source_platform=key[2],
            source_account_id=key[3], campaign_id=key[4], brand_classification=key[5],
            min_duration_sec=rule.min_duration_sec, calls=len(members),
            first_time_calls=first_count, returning_calls=len(members) - first_count,
            unique_leads=sum(row.first_time_caller and row.duration_sec >= rule.min_duration_sec
                             for row in members),
            unresolved_calls=sum(bool(row.attribution_issues) for row in members),
            observed_sources=tuple(sorted({row.observed_source for row in members})),
            attribution_issues=tuple(sorted({issue for row in members
                                             for issue in row.attribution_issues})),
        ))
    return tuple(output)
