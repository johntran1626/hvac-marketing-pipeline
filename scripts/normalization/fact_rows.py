"""Validate and stage paid/LSA aggregates for source-aware daily fact persistence.

No I/O. Call only after a complete reconciled source/day slice is available;
a caller must atomically replace the affected slice and independently attest
freshness. In particular, unknown brand classification is NOT guessed.
"""
from datetime import date, datetime
from decimal import Decimal

from .daily import DailyContribution


class FactRowError(ValueError):
    pass


def to_fact_row(row: DailyContribution, *, synced_at: datetime, data_through: date) -> dict:
    if not isinstance(row, DailyContribution):
        raise FactRowError('expected DailyContribution')
    if row.brand_classification not in {'brand', 'non_brand', 'not_applicable'}:
        raise FactRowError('unresolved brand classification: explicit mapping required')
    if not isinstance(synced_at, datetime) or synced_at.tzinfo is None or synced_at.utcoffset() is None:
        raise FactRowError('synced_at must be timezone-aware')
    if type(data_through) is not date:
        raise FactRowError('data_through must be a date')
    if date.fromisoformat(row.analysis_date) > data_through:
        raise FactRowError('data_through precedes analysis_date')
    if len(row.campaign_names) > 1:
        raise FactRowError('conflicting campaign names require explicit decision')
    return {
        'analysis_date': row.analysis_date,
        'channel': row.channel,
        'source_platform': row.source_platform,
        'source_account_id': row.source_account_id,
        'campaign_id': row.campaign_id,
        'campaign_name': row.campaign_names[0] if row.campaign_names else None,
        'brand_classification': row.brand_classification,
        'impressions': row.impressions,
        'clicks': row.clicks,
        'spend_usd': str(row.spend_usd),
        'reported_leads': str(row.reported_leads),
        'unique_leads': 0,
        'calls': 0,
        'jobs': 0,
        'completed_jobs': 0,
        'revenue_usd': '0',
        'synced_at': synced_at.isoformat(),
        'data_through': data_through.isoformat(),
    }
