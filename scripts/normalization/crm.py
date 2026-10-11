"""Pure CRM normalization and booking-cohort aggregation for GitHub #31.

Supply current upserted jobs and an explicitly versioned source dictionary.
No I/O, campaign/person joins, revenue date invention or production writes.
"""
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, localcontext
from hashlib import sha256
import json
from types import MappingProxyType
from zoneinfo import ZoneInfo

CENTRAL = ZoneInfo("America/Chicago")
STATUSES = frozenset({"scheduled", "completed", "canceled", "estimate_sold", "estimate_lost"})
JOB_TYPES = frozenset({"repair", "maintenance", "install", "estimate", "diagnostic"})
SOURCE_BUCKETS = frozenset({"google_ads", "google_lsa", "meta", "gbp", "website",
    "direct", "referral", "existing_customer", "maintenance_plan", "builder_hoa",
    "yelp", "nextdoor", "unattributed"})


class CrmNormalizationError(ValueError):
    """Field-specific failure without exposing raw customer/job information."""


def _text(row: Mapping[str, object], field: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise CrmNormalizationError(f"{field}: expected a non-empty string")
    return value


def _timestamp(row: Mapping[str, object], field: str) -> datetime:
    value = _text(row, field)
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise CrmNormalizationError(f"{field}: expected an ISO timestamp") from None
    if result.tzinfo is None or result.utcoffset() is None:
        raise CrmNormalizationError(f"{field}: timestamp requires an explicit offset")
    return result.astimezone(timezone.utc)


def _money(value: object) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise CrmNormalizationError("revenue_usd: expected a numeric value or null")
    result = value if isinstance(value, Decimal) else Decimal(str(value))
    if not result.is_finite() or result < 0:
        raise CrmNormalizationError("revenue_usd: expected finite non-negative revenue")
    return result


@dataclass(frozen=True)
class SourceRules:
    """Explicit candidate/reviewed dictionary. No built-in production default."""
    version: str
    aliases: Mapping[str, str]
    fingerprint: str = field(init=False)

    def __post_init__(self):
        if not isinstance(self.version, str) or not self.version.strip():
            raise CrmNormalizationError("source rules require a non-empty version")
        if not isinstance(self.aliases, Mapping):
            raise CrmNormalizationError("source aliases must be a mapping")
        canonical = {}
        for label, bucket in self.aliases.items():
            if not isinstance(label, str) or not label.strip() or not isinstance(bucket, str) or bucket not in SOURCE_BUCKETS:
                raise CrmNormalizationError("source alias must be non-empty with a supported bucket")
            key = label.strip().casefold()
            if key in canonical and canonical[key] != bucket:
                raise CrmNormalizationError("conflicting case/space-normalized source aliases")
            canonical[key] = bucket
        object.__setattr__(self, "aliases", MappingProxyType(canonical))
        serialized = json.dumps(canonical, sort_keys=True, separators=(",", ":"),
                                ensure_ascii=True).encode("utf-8")
        object.__setattr__(self, "fingerprint", sha256(serialized).hexdigest())


@dataclass(frozen=True)
class CrmContribution:
    """One current job, with completed revenue placed on original booking date."""
    job_id: str
    customer_id: str
    created_at: datetime
    updated_at: datetime
    analysis_date: str
    lead_source: str | None
    mapping_version: str
    mapping_fingerprint: str
    channel: str
    source_platform: str
    source_account_id: None
    campaign_id: None
    brand_classification: str
    job_type: str
    status: str
    zip: str
    jobs: int
    completed_jobs: int
    observed_revenue_usd: Decimal | None
    revenue_usd: Decimal | None
    attribution_issues: tuple[str, ...]
    quality_issues: tuple[str, ...]

    @property
    def source_state_key(self) -> tuple[object, ...]:
        """Source fields only; derived mapping changes do not mutate CRM state."""
        return (self.job_id, self.customer_id, self.created_at, self.updated_at,
                self.lead_source, self.job_type, self.status, self.zip,
                self.observed_revenue_usd)

    @property
    def raw_key(self) -> str:
        return self.job_id

    @property
    def bucket_key(self) -> tuple[str | None, ...]:
        return (self.analysis_date, self.channel, self.source_platform,
                self.source_account_id, self.campaign_id, self.brand_classification)


def normalize_crm_row(row: Mapping[str, object], *, rules: SourceRules) -> CrmContribution:
    if not isinstance(row, Mapping) or not isinstance(rules, SourceRules):
        raise CrmNormalizationError("expected a raw record and explicit SourceRules")
    created = _timestamp(row, "created_at")
    updated = _timestamp(row, "updated_at")
    if updated < created:
        raise CrmNormalizationError("updated_at: update precedes job creation")
    status = _text(row, "status")
    kind = _text(row, "job_type")
    if status not in STATUSES or kind not in JOB_TYPES:
        raise CrmNormalizationError("status/job_type: unsupported source value")
    if "lead_source" not in row or "revenue_usd" not in row:
        raise CrmNormalizationError("missing nullable lead_source/revenue_usd field")
    label = row["lead_source"]
    if label is not None and not isinstance(label, str):
        raise CrmNormalizationError("lead_source: expected raw text or null")
    key = label.strip().casefold() if label is not None else ""
    channel = rules.aliases.get(key, "unattributed")
    attribution = ()
    if not key:
        attribution = ("missing_lead_source",)
    elif key not in rules.aliases:
        attribution = ("unknown_lead_source",)
    elif channel == "unattributed":
        attribution = ("ambiguous_lead_source",)
    observed_revenue = _money(row["revenue_usd"])
    quality = []
    if status == "completed" and observed_revenue is None:
        quality.append("missing_completed_revenue")
    elif status != "completed" and observed_revenue is not None:
        quality.append("revenue_on_noncompleted_job")
    return CrmContribution(
        job_id=_text(row, "job_id"), customer_id=_text(row, "customer_id"),
        created_at=created, updated_at=updated,
        analysis_date=created.astimezone(CENTRAL).date().isoformat(),
        lead_source=label, mapping_version=rules.version, mapping_fingerprint=rules.fingerprint,
        channel=channel,
        source_platform="crm", source_account_id=None, campaign_id=None,
        brand_classification="not_applicable", job_type=kind, status=status,
        zip=_text(row, "zip"), jobs=1, completed_jobs=int(status == "completed"),
        observed_revenue_usd=observed_revenue,
        revenue_usd=observed_revenue if status == "completed" else Decimal(0),
        attribution_issues=attribution, quality_issues=tuple(quality),
    )


@dataclass(frozen=True)
class DailyCrm:
    analysis_date: str
    channel: str
    source_platform: str
    source_account_id: None
    campaign_id: None
    brand_classification: str
    mapping_version: str
    mapping_fingerprint: str
    jobs: int
    completed_jobs: int
    revenue_usd: Decimal | None
    known_completed_revenue_usd: Decimal
    missing_completed_revenue_jobs: int
    unresolved_jobs: int
    attribution_issues: tuple[str, ...]
    quality_issues: tuple[str, ...]

    @property
    def bucket_key(self) -> tuple[str | None, ...]:
        return (self.analysis_date, self.channel, self.source_platform,
                self.source_account_id, self.campaign_id, self.brand_classification)


def _exact_sum(values: list[Decimal]) -> Decimal:
    if not values:
        return Decimal(0)
    integer_digits = max(max(value.adjusted() + 1, 0) for value in values)
    fraction_digits = max(max(-value.as_tuple().exponent, 0) for value in values)
    with localcontext() as context:
        context.prec = max(28, integer_digits + fraction_digits + len(str(len(values))) + 1)
        return sum(values, Decimal(0))


def aggregate_crm(rows: Iterable[CrmContribution]) -> tuple[DailyCrm, ...]:
    """One current version per job; reject mixed source dictionary versions."""
    groups = {}
    seen = set()
    versions = set()
    for row in rows:
        if not isinstance(row, CrmContribution):
            raise CrmNormalizationError("expected a normalized current CRM job")
        if row.raw_key in seen:
            raise CrmNormalizationError("duplicate job_id; provide current upserted jobs")
        seen.add(row.raw_key)
        versions.add((row.mapping_version, row.mapping_fingerprint))
        if len(versions) > 1:
            raise CrmNormalizationError("cannot mix source dictionary versions or contents")
        groups.setdefault(row.bucket_key, []).append(row)
    output = []
    for key in sorted(groups, key=lambda k: tuple(
            (v is not None, v if v is not None else "") for v in k)):
        members = groups[key]
        missing = sum(row.status == "completed" and row.revenue_usd is None for row in members)
        known = _exact_sum([row.revenue_usd for row in members if row.revenue_usd is not None])
        output.append(DailyCrm(
            analysis_date=key[0], channel=key[1], source_platform=key[2],
            source_account_id=key[3], campaign_id=key[4], brand_classification=key[5],
            mapping_version=members[0].mapping_version,
            mapping_fingerprint=members[0].mapping_fingerprint,
            jobs=len(members), completed_jobs=sum(row.completed_jobs for row in members),
            revenue_usd=None if missing else known, known_completed_revenue_usd=known,
            missing_completed_revenue_jobs=missing,
            unresolved_jobs=sum(bool(row.attribution_issues) for row in members),
            attribution_issues=tuple(sorted({i for row in members for i in row.attribution_issues})),
            quality_issues=tuple(sorted({i for row in members for i in row.quality_issues})),
        ))
    return tuple(output)


def affected_booking_dates(previous: CrmContribution | None,
                           current: CrmContribution) -> tuple[str, ...]:
    """Rebuild full CRM slices for source updates or explicit policy remapping.

    Equal timestamps must agree on source fields; derived policy may change.
    A changed dictionary still requires deliberately reprocessing all history.
    """
    if not isinstance(current, CrmContribution) or (
            previous is not None and not isinstance(previous, CrmContribution)):
        raise CrmNormalizationError("expected normalized old/current job versions")
    if previous is not None:
        if previous.job_id != current.job_id:
            raise CrmNormalizationError("job_id differs between old/current versions")
        if current.updated_at < previous.updated_at:
            raise CrmNormalizationError("current job is older than previous state")
        if (current.updated_at == previous.updated_at
                and current.source_state_key != previous.source_state_key):
            raise CrmNormalizationError("conflicting job versions with equal update timestamp")
    return tuple(sorted({current.analysis_date} | (
        {previous.analysis_date} if previous is not None else set())))
