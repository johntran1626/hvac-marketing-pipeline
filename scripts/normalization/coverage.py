"""Pure refresh planning and completion attestations for GitHub #30.

Caller supplies real health, durable page receipts and persistence outcomes.
No network, clock reads, database writes, cursor storage or resume machinery.
"""
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta

SUPPORTED = frozenset({"google_ads", "meta_ads", "lsa"})
# Conservative boundary day in addition to the documented mutable period.
LOOKBACK_DAYS = {"google_ads": 7, "meta_ads": 7, "lsa": 30}
MAX_REQUEST_DAYS = 31


class CoverageError(ValueError):
    """Incomplete or inconsistent coverage; do not advance freshness."""


def _day(value: date, field: str) -> None:
    if type(value) is not date:
        raise CoverageError(f"{field}: expected a calendar date")


def _time(value: datetime, field: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise CoverageError(f"{field}: expected an offset-aware timestamp")


@dataclass(frozen=True)
class SourceScope:
    """Stable caller-owned dataset token, separate from source account IDs.

    The API request is group-wide; scope_id identifies that loader dataset.
    Never use an API secret as the token. Persist scope consistently on resume.
    """
    source_platform: str
    scope_id: str

    def __post_init__(self):
        if self.source_platform not in SUPPORTED:
            raise CoverageError("unsupported source platform")
        if not isinstance(self.scope_id, str) or not self.scope_id.strip():
            raise CoverageError("scope_id: expected a stable non-empty dataset token")


@dataclass(frozen=True)
class DateWindow:
    start_date: date
    end_date: date

    def __post_init__(self):
        _day(self.start_date, "start_date")
        _day(self.end_date, "end_date")
        days = (self.end_date - self.start_date).days + 1
        if not 1 <= days <= MAX_REQUEST_DAYS:
            raise CoverageError("date window must contain 1 through 31 inclusive days")


@dataclass(frozen=True)
class RefreshPlan:
    scope: SourceScope
    history_start: date
    api_data_through: date
    previous_data_through: date | None
    started_at: datetime
    windows: tuple[DateWindow, ...]


def plan_refresh(scope: SourceScope, *, history_start: date,
                 api_data_through: date, previous_data_through: date | None,
                 started_at: datetime) -> RefreshPlan:
    """Use health.data_through, not machine today or the largest observed row.

    previous_data_through must attest contiguous completed historical coverage.
    None means backfill from history_start. Fetch all missed days AND re-read
    mutable creation dates; split the union into contiguous <=31-day requests.
    """
    if not isinstance(scope, SourceScope):
        raise CoverageError("expected a SourceScope")
    _day(history_start, "history_start")
    _day(api_data_through, "api_data_through")
    _time(started_at, "started_at")
    if previous_data_through is not None:
        _day(previous_data_through, "previous_data_through")
        if not history_start <= previous_data_through <= api_data_through:
            raise CoverageError("previous coverage is outside source history/availability")
    windows = []
    if api_data_through >= history_start:
        # Dates mutable at the prior successful watermark can change during
        # an outage and become immutable before this run. Re-read that earlier
        # overlap as well as every missed day; today's overlap alone misses them.
        anchor = previous_data_through if previous_data_through is not None else history_start
        start = max(history_start, anchor - timedelta(days=LOOKBACK_DAYS[scope.source_platform]))
        while start <= api_data_through:
            end = min(start + timedelta(days=MAX_REQUEST_DAYS - 1), api_data_through)
            windows.append(DateWindow(start, end))
            start = end + timedelta(days=1)
    return RefreshPlan(scope, history_start, api_data_through,
                       previous_data_through, started_at, tuple(windows))


@dataclass(frozen=True)
class PageReceipt:
    scope: SourceScope
    window: DateWindow
    request_cursor: str | None
    next_cursor: str | None
    row_count: int
    raw_persisted: bool


@dataclass(frozen=True)
class RawCoverage:
    scope: SourceScope
    window: DateWindow
    completed_at: datetime
    page_count: int
    source_row_count: int


def complete_raw_window(scope: SourceScope, window: DateWindow,
                        pages: Iterable[PageReceipt], *, completed_at: datetime) -> RawCoverage:
    """Validate the FULL persisted cursor chain, including pre-resume pages.

    An empty terminal page still attests its queried date range. No pages,
    a missing page, parameter drift, pending upsert or cursor cycle fails.
    Receipts are trusted attestations; this helper cannot observe the API/DB.
    """
    if not isinstance(scope, SourceScope) or not isinstance(window, DateWindow):
        raise CoverageError("expected a source scope and date window")
    _time(completed_at, "completed_at")
    pages = tuple(pages)
    if not pages:
        raise CoverageError("no pages: coverage is unknown")
    expected_cursor = None
    seen = set()
    rows = 0
    for index, page in enumerate(pages):
        if not isinstance(page, PageReceipt) or page.scope != scope or page.window != window:
            raise CoverageError("page scope/date parameters differ")
        for cursor in (page.request_cursor, page.next_cursor):
            if cursor is not None and (not isinstance(cursor, str) or not cursor):
                raise CoverageError("cursor must be null or a non-empty string")
        if page.request_cursor != expected_cursor or page.request_cursor in seen:
            raise CoverageError("cursor chain has a gap, duplicate or cycle")
        seen.add(page.request_cursor)
        if type(page.row_count) is not int or page.row_count < 0:
            raise CoverageError("page row_count must be a non-negative integer")
        if page.raw_persisted is not True:
            raise CoverageError("raw upsert did not complete")
        rows += page.row_count
        expected_cursor = page.next_cursor
        if expected_cursor is None and index != len(pages) - 1:
            raise CoverageError("extra pages after terminal cursor")
    if expected_cursor is not None:
        raise CoverageError("terminal page not reached")
    return RawCoverage(scope, window, completed_at, len(pages), rows)


@dataclass(frozen=True)
class NormalizedCoverage:
    raw: RawCoverage
    normalized_at: datetime


def complete_normalized_window(raw: RawCoverage, *, normalized_at: datetime,
                               facts_persisted: bool) -> NormalizedCoverage:
    """Call only after complete source/day replacement and reconciliation.

    Zero rows still require a successful explicit slice replacement. This
    function only attests that outcome; it never deletes or writes facts.
    """
    if not isinstance(raw, RawCoverage):
        raise CoverageError("expected complete raw coverage")
    _time(raw.completed_at, "completed_at")
    _time(normalized_at, "normalized_at")
    if normalized_at < raw.completed_at:
        raise CoverageError("normalization precedes raw completion")
    if facts_persisted is not True:
        raise CoverageError("fact persistence did not complete")
    return NormalizedCoverage(raw, normalized_at)


@dataclass(frozen=True)
class Freshness:
    scope: SourceScope
    synced_at: datetime
    data_through: date
    covered_windows: tuple[DateWindow, ...]
    source_row_count: int


def complete_refresh(plan: RefreshPlan,
                     receipts: Iterable[NormalizedCoverage]) -> Freshness:
    """Publish a full-refresh candidate only after every planned window.

    Never turn partial success into a source-wide successful sync. Durable
    storage and atomic fact/freshness commits remain the real worker's job.
    """
    if not isinstance(plan, RefreshPlan) or not plan.windows:
        raise CoverageError("no available planned dates; cannot publish freshness")
    canonical = plan_refresh(plan.scope, history_start=plan.history_start,
        api_data_through=plan.api_data_through,
        previous_data_through=plan.previous_data_through, started_at=plan.started_at)
    if plan != canonical:
        raise CoverageError("plan windows do not provide the required contiguous coverage")
    receipts = tuple(receipts)
    matched = {}
    for receipt in receipts:
        if not isinstance(receipt, NormalizedCoverage):
            raise CoverageError("normalization completion receipt required")
        raw = receipt.raw
        if raw.scope != plan.scope or raw.window not in plan.windows:
            raise CoverageError("receipt is outside this refresh scope/windows")
        if raw.completed_at < plan.started_at:
            raise CoverageError("stale receipt from an earlier refresh")
        if raw.window in matched:
            raise CoverageError("duplicate window receipt")
        if receipt.normalized_at < raw.completed_at:
            raise CoverageError("normalization precedes raw completion")
        matched[raw.window] = receipt
    if set(matched) != set(plan.windows):
        raise CoverageError("planned coverage is incomplete")
    return Freshness(
        scope=plan.scope,
        synced_at=max(receipt.normalized_at for receipt in receipts),
        data_through=plan.api_data_through,
        covered_windows=plan.windows,
        source_row_count=sum(receipt.raw.source_row_count for receipt in receipts),
    )
