"""Reviewed campaign IDs from schema/normalized-fact-table.md.

Shared transformation rules, scoped by platform. Frozen reconciliation scripts
intentionally retain independently transcribed expectations from the schema.
Changes require updating/reviewing those expectations and reconciliation.
"""
GOOGLE_BRAND_CAMPAIGNS = frozenset({"20814455901"})
GOOGLE_NON_BRAND_CAMPAIGNS = frozenset({
    "20814455917", "20814455930", "20814455948",
})
META_NON_BRAND_CAMPAIGNS = frozenset({
    "120208841937650100", "120208841937650200",
})
