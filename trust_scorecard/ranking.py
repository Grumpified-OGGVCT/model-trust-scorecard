"""Capability-first model ranking helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from trust_scorecard.models import ModelCard, ModelEvaluation

USE_CASE_PRIORITY = (
    "coding",
    "reasoning",
    "tool_use",
    "long_context",
    "multilingual",
    "safety",
    "commonsense",
    "efficiency",
    "edge",
)

MULTIMODAL_TAGS = {"multimodal", "vision", "video", "ocr", "document-analysis"}
AGENTIC_TAGS = {"agentic", "tool-use", "function-calling", "software-engineering"}


def capability_sort_key(
    card: ModelCard,
    use_case_scores: Mapping[str, float] | None = None,
    trust_score: float | None = None,
    benchmark_evidence_count: int = 0,
) -> tuple[Any, ...]:
    """Return a sort key that prioritizes demonstrated capability over trust totals."""
    scores = use_case_scores or {}
    tags = set(card.tags or [])
    active_params = card.parameter_count_billions or 0.0
    total_params = card.total_parameter_count_billions or active_params
    use_case_breadth = sum(1 for value in scores.values() if value > 0)
    capability_rank = (
        (0, card.capability_rank) if card.capability_rank is not None else (1, float("inf"))
    )

    return (
        capability_rank,
        *(-float(scores.get(name, 0.0)) for name in USE_CASE_PRIORITY),
        -use_case_breadth,
        -benchmark_evidence_count,
        -int(bool(tags & MULTIMODAL_TAGS)),
        -int(bool(tags & AGENTIC_TAGS)),
        -active_params,
        -total_params,
        -(card.context_window_tokens or 0),
        -(trust_score or 0.0),
        card.display_name.lower(),
    )


def score_record_sort_key(score: Mapping[str, Any]) -> tuple[Any, ...]:
    """Sort key for aggregated score dictionaries."""
    model_card = ModelCard.model_validate(score.get("model_card") or {})
    return capability_sort_key(
        model_card,
        score.get("use_case_scores") or {},
        score.get("trust_score"),
        int(score.get("total_claims") or 0),
    )


def evaluation_sort_key(evaluation: ModelEvaluation) -> tuple[Any, ...]:
    """Sort key for ModelEvaluation objects."""
    trust_score = evaluation.trust_score.score if evaluation.trust_score else None
    use_case_scores = evaluation.trust_score.breakdown.use_case_scores if evaluation.trust_score else {}
    benchmark_evidence_count = max(
        len(evaluation.claims),
        len(evaluation.outcomes),
        len(evaluation.benchmark_results),
    )
    return capability_sort_key(
        evaluation.card,
        use_case_scores,
        trust_score,
        benchmark_evidence_count,
    )
