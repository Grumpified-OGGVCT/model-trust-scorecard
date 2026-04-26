"""Capability-first model ranking helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from trust_scorecard.models import ModelCard, ModelEvaluation, VerificationStatus

# Weights prioritize core frontier capabilities while including specialized metrics to reward
# measured breadth without allowing niche performance to skew rankings.
CAPABILITY_WEIGHTS = {
    # Core frontier-model competencies get the highest weight because they are broad,
    # heavily benchmarked predictors of general model quality.
    "coding": 2.0,
    "reasoning": 2.0,
    "math": 1.5,
    "tool_use": 1.5,
    # Specialized modalities and reliability dimensions contribute meaningfully but
    # should not outweigh core capability when fewer models report those scores.
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
    # Deployment-oriented metrics are useful tie-shapers, not primary capability signals.
    "efficiency": 0.3,
    "edge": 0.3,
}

MIN_SCORES_FOR_RANKING = 3
DEFAULT_CAPABILITY_WEIGHT = 0.5
TIER_VERIFIED = 0
TIER_UNVERIFIED = 1
TIER_CAPABILITY_ONLY = 2
TIER_NO_EVIDENCE = 3

MULTIMODAL_TAGS = {"multimodal", "vision", "video", "ocr", "document-analysis"}
AGENTIC_TAGS = {"agentic", "tool-use", "function-calling", "software-engineering"}


def _numeric_scores(scores: Mapping[str, float]) -> dict[str, float]:
    """Return score entries that can be safely converted to floats."""
    numeric_scores: dict[str, float] = {}
    for name, value in scores.items():
        try:
            numeric_scores[name] = float(value)
        except (TypeError, ValueError):
            continue
    return numeric_scores


def capability_sort_key(
    card: ModelCard,
    use_case_scores: Mapping[str, float] | None = None,
    trust_score: float | None = None,
    benchmark_evidence_count: int = 0,
    verified_evidence_count: int = 0,
) -> tuple[Any, ...]:
    """Return a reliability-first sort key for model rankings."""
    scores = use_case_scores or {}
    tags = set(card.tags or [])
    active_params = card.parameter_count_billions or 0.0
    total_params = card.total_parameter_count_billions or active_params
    valid_numeric_scores = _numeric_scores(scores)

    if verified_evidence_count > 0:
        reliability_tier = TIER_VERIFIED
    elif benchmark_evidence_count > 0:
        reliability_tier = TIER_UNVERIFIED
    elif valid_numeric_scores:
        reliability_tier = TIER_CAPABILITY_ONLY
    else:
        reliability_tier = TIER_NO_EVIDENCE

    if len(valid_numeric_scores) >= MIN_SCORES_FOR_RANKING:
        weighted_score = sum(
            value * CAPABILITY_WEIGHTS.get(name, DEFAULT_CAPABILITY_WEIGHT)
            for name, value in valid_numeric_scores.items()
        )
        total_weight = sum(
            CAPABILITY_WEIGHTS.get(name, DEFAULT_CAPABILITY_WEIGHT)
            for name in valid_numeric_scores
        )
        composite = weighted_score / total_weight
    else:
        composite = 0.0

    verification_rate = (
        min(verified_evidence_count, benchmark_evidence_count) / benchmark_evidence_count
        if benchmark_evidence_count > 0
        else 0.0
    )

    return (
        reliability_tier,
        -verified_evidence_count,
        -verification_rate,
        -composite,
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
        int(score.get("verified_count") or 0),
    )


def evaluation_sort_key(evaluation: ModelEvaluation) -> tuple[Any, ...]:
    """Sort key for ModelEvaluation objects."""
    trust_score = evaluation.trust_score.score if evaluation.trust_score else None
    use_case_scores = evaluation.trust_score.breakdown.use_case_scores if evaluation.trust_score else {}
    benchmark_evidence_count = len(evaluation.claims)
    verified_evidence_count = sum(
        1 for outcome in evaluation.outcomes if outcome.status == VerificationStatus.VERIFIED
    )
    return capability_sort_key(
        evaluation.card,
        use_case_scores,
        trust_score,
        benchmark_evidence_count,
        verified_evidence_count,
    )
