"""
Memory — pure calculations (Stage 10 in the master plan, section 13).

Scope note, stated plainly: the master plan describes a full knowledge
graph with typed relationships (section 13.2) and multiple memory types
(structured/semantic/temporal/episodic/procedural, section 13.1). Building
that now, with a handful of paper trades in the database, would be real
infrastructure with nothing to feed it — the same trap flagged earlier
about Kafka/Kubernetes/a dedicated vector DB. What's implemented here is
the genuinely useful subset: breaking down real trade history by the
categories that already exist (classification, quality grade), and
answering the master plan's "what's different this time?" question
(section 13.3) by comparing current conditions to similar past ones. Both
reuse app/performance/calculations.py's discipline (pure functions, no DB).
"""
from dataclasses import dataclass

from app.memory.repository import ClosedTradeRecord
from app.performance.calculations import PerformanceSummary, compute_performance_summary


@dataclass
class GroupedPerformance:
    group: str
    summary: PerformanceSummary


def breakdown_by_classification(records: list[ClosedTradeRecord]) -> list[GroupedPerformance]:
    groups: dict[str, list[float]] = {}
    for r in records:
        key = r.classification or "UNCLASSIFIED"
        groups.setdefault(key, []).append(r.realized_pnl)

    return [
        GroupedPerformance(group=group, summary=compute_performance_summary(pnls))
        for group, pnls in sorted(groups.items())
    ]


def breakdown_by_quality_grade(records: list[ClosedTradeRecord]) -> list[GroupedPerformance]:
    groups: dict[str, list[float]] = {}
    for r in records:
        key = r.quality_grade or "UNGRADED"
        groups.setdefault(key, []).append(r.realized_pnl)

    return [
        GroupedPerformance(group=group, summary=compute_performance_summary(pnls))
        for group, pnls in sorted(groups.items())
    ]


@dataclass
class SimilarSetupsResult:
    current_gold_macro_score: int
    similar_trade_count: int
    similar_trades_summary: PerformanceSummary
    tolerance: int


def find_similar_historical_setups(
    records: list[ClosedTradeRecord],
    current_gold_macro_score: int,
    current_classification: str,
    tolerance: int = 20,
) -> SimilarSetupsResult:
    """
    "What's different this time?" (master plan section 13.3), scoped to
    what's actually knowable from trade history: past trades with the SAME
    classification (e.g. also MACRO_ALIGNED_LONG) and a gold macro score
    within `tolerance` points of today's — a reasonable proxy for "similar
    macro backdrop," not a full similarity model.
    """
    similar_pnls = [
        r.realized_pnl
        for r in records
        if r.classification == current_classification
        and r.entry_gold_macro_score is not None
        and abs(r.entry_gold_macro_score - current_gold_macro_score) <= tolerance
    ]

    return SimilarSetupsResult(
        current_gold_macro_score=current_gold_macro_score,
        similar_trade_count=len(similar_pnls),
        similar_trades_summary=compute_performance_summary(similar_pnls),
        tolerance=tolerance,
    )
