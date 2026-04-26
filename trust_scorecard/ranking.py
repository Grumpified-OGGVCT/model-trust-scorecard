"""Capability-first model ranking helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from trust_scorecard.models import ModelCard, ModelEvaluation, VerificationStatus

# BenchLM-style category weights. Missing categories are excluded from the
# denominator so sparse-but-eligible models are not penalized as zeroes.
CAPABILITY_CATEGORY_WEIGHTS = {
    "agentic": 22.0,
    "coding": 20.0,
    "reasoning": 17.0,
    "multimodal": 12.0,
    "knowledge": 12.0,
    "multilingual": 7.0,
    "instruction_following": 5.0,
    "math": 5.0,
}

CAPABILITY_CATEGORY_SIGNALS = {
    "agentic": ("tool_use", "agent_swarm"),
    "coding": ("coding", "vision_coding"),
    "reasoning": ("reasoning", "long_context"),
    "multimodal": ("multimodal", "ocr", "video_understanding", "office_document"),
    "knowledge": ("commonsense", "safety", "hallucination_fidelity"),
    "multilingual": ("multilingual", "multilingual_depth"),
    "instruction_following": ("instruction_following",),
    "math": ("math",),
}

MIN_SCORES_FOR_RANKING = 3
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


def category_capability_scores(scores: Mapping[str, float]) -> dict[str, float]:
    """Collapse use-case signals into BenchLM-style weighted capability categories."""
    numeric_scores = _numeric_scores(scores)
    category_scores: dict[str, float] = {}
    for category, signal_names in CAPABILITY_CATEGORY_SIGNALS.items():
        values = [numeric_scores[name] for name in signal_names if name in numeric_scores]
        if values:
            category_scores[category] = sum(values) / len(values)
    return category_scores


def _weighted_category_score(category_scores: Mapping[str, float]) -> float | None:
    weighted_score = 0.0
    total_weight = 0.0
    for category, score in category_scores.items():
        weight = CAPABILITY_CATEGORY_WEIGHTS.get(category)
        if weight is None:
            continue
        weighted_score += float(score) * weight
        total_weight += weight
    if total_weight == 0.0:
        return None
    return weighted_score / total_weight


def _external_leaderboard_score(card: ModelCard) -> float | None:
    """Return an externally sourced capability score when the catalog supplies one."""
    if card.leaderboard_score is not None:
        return float(card.leaderboard_score)

    return None


def _metadata_fallback_score(card: ModelCard) -> float | None:
    """Return weaker catalog metadata scores when no scored leaderboard is available."""
    index_values = [
        card.artificial_analysis_intelligence_index,
        card.artificial_analysis_coding_index,
        card.artificial_analysis_agentic_index,
    ]
    numeric_index_values = [float(value) for value in index_values if value is not None]
    if numeric_index_values:
        return sum(numeric_index_values) / len(numeric_index_values)

    if card.capability_rank is None:
        return None
    return max(0.0, 100.0 - float(card.capability_rank))


def capability_sort_key(
    card: ModelCard,
    use_case_scores: Mapping[str, float] | None = None,
    trust_score: float | None = None,
    benchmark_evidence_count: int = 0,
    verified_evidence_count: int = 0,
) -> tuple[Any, ...]:
    """Return a sort key that prioritizes verified evidence over claimed capability."""
    scores = use_case_scores or {}
    tags = set(card.tags or [])
    active_params = card.parameter_count_billions or 0.0
    total_params = card.total_parameter_count_billions or active_params
    valid_numeric_scores = _numeric_scores(scores)
    category_scores = category_capability_scores(scores)
    external_score = _external_leaderboard_score(card)
    metadata_fallback_score = _metadata_fallback_score(card)
    has_external_leaderboard = card.leaderboard_score is not None or card.leaderboard_rank is not None

    if verified_evidence_count > 0 or has_external_leaderboard:
        reliability_tier = TIER_VERIFIED
    elif benchmark_evidence_count > 0:
        reliability_tier = TIER_UNVERIFIED
    elif valid_numeric_scores or metadata_fallback_score is not None:
        reliability_tier = TIER_CAPABILITY_ONLY
    else:
        reliability_tier = TIER_NO_EVIDENCE

    if external_score is not None:
        composite = external_score
    elif len(valid_numeric_scores) >= MIN_SCORES_FOR_RANKING and category_scores:
        composite = _weighted_category_score(category_scores) or 0.0
    elif metadata_fallback_score is not None:
        composite = metadata_fallback_score
    else:
        composite = 0.0

    # Keep zero-evidence models at a 0.0 verification rate and avoid dividing by zero.
    verification_rate = (
        verified_evidence_count / benchmark_evidence_count
        if benchmark_evidence_count > 0
        else 0.0
    )

    return (
        reliability_tier,
        -int(has_external_leaderboard),
        -composite,
        card.leaderboard_rank if card.leaderboard_rank is not None else float("inf"),
        -verified_evidence_count,
        -verification_rate,
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
