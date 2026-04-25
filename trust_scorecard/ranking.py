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

CAPABILITY_WEIGHTS = {
    "coding": 2.0,
    "reasoning": 2.0,
    "math": 1.5,
    "tool_use": 1.5,
    "agent_swarm": 1.2,
    "multimodal": 1.2,
    "vision_coding": 1.0,
    "ocr": 0.8,
    "video_understanding": 0.8,
    "multilingual": 0.8,
    "multilingual_depth": 0.7,
    "safety": 0.7,
    "hallucination_fidelity": 0.7,
    "long_context": 0.5,
    "commonsense": 0.5,
    "office_document": 0.5,
    "efficiency": 0.3,
    "edge": 0.3,
}

MIN_SCORES_FOR_RANKING = 3
DEFAULT_CAPABILITY_WEIGHT = 0.5

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
    scored_items = {key: float(value) for key, value in scores.items() if value is not None}

    if len(scored_items) >= MIN_SCORES_FOR_RANKING:
        weighted_score = sum(
            value * CAPABILITY_WEIGHTS.get(name, DEFAULT_CAPABILITY_WEIGHT)
            for name, value in scored_items.items()
        )
        total_weight = sum(
            CAPABILITY_WEIGHTS.get(name, DEFAULT_CAPABILITY_WEIGHT) for name in scored_items
        )
        capability_tier = (0, -(weighted_score / total_weight))
    elif scored_items:
        capability_tier = (1, 0.0)
    else:
        capability_tier = (2, 0.0)

    return (
        capability_tier,
        -(trust_score or 0.0),
        -benchmark_evidence_count,
        -int(bool(tags & MULTIMODAL_TAGS)),
        -int(bool(tags & AGENTIC_TAGS)),
        -active_params,
        -total_params,
        -(card.context_window_tokens or 0),
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
    benchmark_evidence_count = len(evaluation.claims)
    return capability_sort_key(
        evaluation.card,
        use_case_scores,
        trust_score,
        benchmark_evidence_count,
    )
