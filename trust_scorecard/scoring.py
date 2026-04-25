"""
Trust score calculation with weighted rubric.

Scoring Rubric (0-100):
  - Coverage (30%):       How many standard benchmarks does the model report?
  - Verification (40%):   What % of claims match independent sources?
  - Performance Gap (20%): How much do verified claims deviate from official values?
  - Openness (5%):        Is the model open-source / weights available?
  - Safety (5%):          Are safety benchmarks reported?

The rubric is designed to incentivize:
  1. Comprehensive benchmark reporting
  2. Accurate, verifiable claims
  3. Minimal exaggeration
  4. Transparency (open weights, safety evaluation)
"""

from __future__ import annotations

import logging
from typing import cast

from trust_scorecard.models import (
    LicenseKind,
    ModelCard,
    TrustScore,
    TrustScoreBreakdown,
    VerificationOutcome,
    VerificationStatus,
)

logger = logging.getLogger(__name__)


def _normalize_metric(name: str) -> str:
    return name.lower().replace("-", "").replace(" ", "").replace("_", "")


# ---------------------------------------------------------------------------
# Scoring weights
# ---------------------------------------------------------------------------

COVERAGE_WEIGHT = 30.0
VERIFICATION_WEIGHT = 40.0
PERFORMANCE_GAP_WEIGHT = 20.0
OPENNESS_WEIGHT = 5.0
SAFETY_WEIGHT = 5.0

# Standard benchmarks expected for comprehensive coverage
STANDARD_BENCHMARKS = [
    "SWE-bench",
    "MMLU",
    "MMLU-Pro",
    "BBH",
    "ARC-AGI",
    "HumanEval",
    "GPQA",
    "TruthfulQA",
    "GSM8K",
    "MATH",
    "HellaSwag",
    "ARC",
    "WinoGrande",
    "LongBench",
    "NeedleBench",
    "AgentBench",
    "MT-Bench",
    "HLE",
    "AIME",
    "HMMT",
    "ArenaHard",
    "OCRBench",
    "MathVision",
    "OmniDocBench",
    "VideoMME",
    "MMMU",
    "TAU2-Bench",
    "Toolathlon",
    "Terminal Bench",
    "WMT24++",
    "RULER",
]

# Safety benchmarks
SAFETY_BENCHMARKS = [
    "TruthfulQA",
    "BBQ",
    "BOLD",
    "RealToxicityPrompts",
]

# Use-case groupings to avoid flattening strengths
USE_CASE_BENCHMARKS: dict[str, list[str]] = {
    "coding": [
        "SWE-bench",
        "SWE-bench Verified",
        "SWE-bench Pro",
        "SWE-bench Multilingual",
        "HumanEval",
        "LiveCodeBench",
        "Terminal Bench 2",
        "AA Coding Index",
        "CodeXGLUE",
    ],
    "reasoning": [
        "MMLU",
        "MMLU-Pro",
        "MMLU-ProX",
        "GSM8K",
        "GPQA",
        "GPQA Diamond",
        "BBH",
        "ARC-AGI",
        "MATH",
        "AIME",
        "AIME25",
        "AIME26",
        "HMMT",
        "AA Intelligence Index",
    ],
    "math": ["AIME", "AIME25", "AIME26", "HMMT", "MATH", "GPQA", "GPQA Diamond", "MathVision"],
    "safety": [
        "TruthfulQA",
        "BBQ",
        "BOLD",
        "Bias",
        "Toxicity",
        "Hallucination Rate",
        "Structured Output Error Rate",
    ],
    "commonsense": ["HellaSwag", "WinoGrande", "ARC", "ARC Challenge", "LAMBADA"],
    "multilingual": ["MMLU-Pro", "MMLU-ProX", "WMT24++", "SWE-bench Multilingual", "BBH", "LAMBADA"],
    "multilingual_depth": ["MMLU-ProX", "WMT24++", "SWE-bench Multilingual"],
    "long_context": ["LongBench", "NeedleBench", "RULER"],
    "tool_use": [
        "AgentBench",
        "MT-Bench",
        "HLE Tools",
        "Toolathlon",
        "TAU2-Bench",
        "Terminal Bench 2",
        "AA Agentic Index",
    ],
    "agent_swarm": ["HLE Tools", "Toolathlon", "TAU2-Bench", "AA Agentic Index"],
    "vision_coding": ["OCRBench", "MathVision", "SWE-bench Multilingual"],
    "multimodal": ["MMMU", "OCRBench", "MathVision", "VideoMME", "OmniDocBench"],
    "ocr": ["OCRBench", "OmniDocBench", "CountBench"],
    "video_understanding": ["VideoMME"],
    "office_document": ["Terminal Bench 2", "GDPval-AA ELO"],
    "hallucination_fidelity": ["Hallucination Rate", "Structured Output Error Rate"],
    "edge": ["EdgeJSON", "EdgeIntent", "EdgeFuncCall", "SMOL-WorldCup"],
    "efficiency": ["Latency", "TinyMobileLLM-Throughput", "TinyMobileLLM-Memory"],
}

STANDARD_BENCHMARK_ALIASES: dict[str, set[str]] = {
    _normalize_metric("SWE-bench"): {
        _normalize_metric("SWE-bench"),
        _normalize_metric("SWE-bench Verified"),
        _normalize_metric("SWE-bench Verified (mini)"),
        _normalize_metric("SWE-bench Lite"),
        _normalize_metric("SWE-bench Pro"),
        _normalize_metric("SWE-bench Multilingual"),
    },
    _normalize_metric("ARC"): {
        _normalize_metric("ARC"),
        _normalize_metric("ARC Challenge"),
        _normalize_metric("ARC-AGI"),
    },
    _normalize_metric("MMLU"): {
        _normalize_metric("MMLU"),
        _normalize_metric("MMLU-Pro"),
        _normalize_metric("MMLU-ProX"),
    },
    _normalize_metric("GPQA"): {
        _normalize_metric("GPQA"),
        _normalize_metric("GPQA Diamond"),
    },
    _normalize_metric("AIME"): {
        _normalize_metric("AIME"),
        _normalize_metric("AIME25"),
        _normalize_metric("AIME26"),
    },
    _normalize_metric("HLE"): {
        _normalize_metric("HLE"),
        _normalize_metric("HLE Tools"),
    },
    _normalize_metric("Terminal Bench"): {
        _normalize_metric("Terminal Bench"),
        _normalize_metric("Terminal Bench 2"),
    },
}

LOWER_IS_BETTER_METRICS = {
    _normalize_metric("Hallucination Rate"),
    _normalize_metric("Structured Output Error Rate"),
}


def _value_for_outcome(outcome: VerificationOutcome) -> float:
    """
    Return the use-case scoring value for an outcome.

    Most benchmark scores are higher-is-better percentages. Lower-is-better
    trust metrics, such as hallucination and structured-output error rates, are
    inverted onto the same 0-100 strength scale so lower risk contributes a
    higher use-case score. The floor prevents negative scores if a noisy source
    reports a value above 100.
    """
    value = outcome.official_value if outcome.official_value is not None else outcome.claim.value
    norm = _normalize_metric(outcome.claim.metric)
    if norm in LOWER_IS_BETTER_METRICS:
        # These lower-is-better metrics are extracted as percentages on the same 0-100 scale.
        return max(0.0, 100.0 - value)
    return value


def compute_coverage_score(
    outcomes: list[VerificationOutcome],
    max_score: float = COVERAGE_WEIGHT,
) -> float:
    """
    Compute coverage score based on number of standard benchmarks reported.

    Parameters
    ----------
    outcomes:
        List of verification outcomes.
    max_score:
        Maximum score for this component.

    Returns
    -------
    Coverage score (0 to max_score).
    """
    if not outcomes:
        return 0.0

    # Extract unique benchmarks from outcomes
    reported_benchmarks = set()
    for outcome in outcomes:
        reported_benchmarks.add(_normalize_metric(outcome.claim.metric))

    # Count how many standard benchmarks are covered
    covered = 0
    for benchmark in STANDARD_BENCHMARKS:
        normalized = _normalize_metric(benchmark)
        aliases = STANDARD_BENCHMARK_ALIASES.get(normalized, {normalized})
        if reported_benchmarks.intersection(aliases):
            covered += 1

    # Score scales linearly with coverage
    # Full marks if >= 8 benchmarks covered
    coverage_ratio = min(covered / 8.0, 1.0)
    score = coverage_ratio * max_score

    logger.debug(
        "Coverage: %d/%d standard benchmarks → %.1f/%.1f",
        covered,
        len(STANDARD_BENCHMARKS),
        score,
        max_score,
    )
    return round(score, 1)


def compute_verification_score(
    outcomes: list[VerificationOutcome],
    max_score: float = VERIFICATION_WEIGHT,
) -> float:
    """
    Compute verification score based on % of claims that are verified.

    Parameters
    ----------
    outcomes:
        List of verification outcomes.
    max_score:
        Maximum score for this component.

    Returns
    -------
    Verification score (0 to max_score).
    """
    if not outcomes:
        return 0.0

    verified_count = sum(
        1 for o in outcomes if o.status == VerificationStatus.VERIFIED
    )
    total_count = len(outcomes)

    verification_ratio = verified_count / total_count
    score = verification_ratio * max_score

    logger.debug(
        "Verification: %d/%d verified → %.1f/%.1f",
        verified_count,
        total_count,
        score,
        max_score,
    )
    return round(score, 1)


def compute_performance_gap_score(
    outcomes: list[VerificationOutcome],
    max_score: float = PERFORMANCE_GAP_WEIGHT,
) -> float:
    """
    Compute performance gap score based on average deviation from official values.

    Lower average delta = higher score.

    Parameters
    ----------
    outcomes:
        List of verification outcomes.
    max_score:
        Maximum score for this component.

    Returns
    -------
    Performance gap score (0 to max_score).
    """
    verified = [
        o for o in outcomes
        if o.status == VerificationStatus.VERIFIED and o.delta is not None
    ]

    if not verified:
        # If no verified claims, give partial credit for attempting verification
        return max_score * 0.3

    # Average absolute deviation
    deltas = [cast(float, o.delta) for o in verified]
    avg_delta = sum(deltas) / len(deltas)

    # Score decreases with average delta
    # Full marks if avg_delta <= 0.5%
    # Zero marks if avg_delta >= 2.0%
    if avg_delta <= 0.5:
        score = max_score
    elif avg_delta >= 2.0:
        score = 0.0
    else:
        # Linear interpolation between 0.5 and 2.0
        ratio = 1.0 - ((avg_delta - 0.5) / 1.5)
        score = ratio * max_score

    logger.debug(
        "Performance gap: avg Δ=%.2f%% → %.1f/%.1f",
        avg_delta,
        score,
        max_score,
    )
    return round(score, 1)


def compute_openness_score(
    card: ModelCard,
    max_score: float = OPENNESS_WEIGHT,
) -> float:
    """
    Compute openness score based on license type.

    Parameters
    ----------
    card:
        Model card metadata.
    max_score:
        Maximum score for this component.

    Returns
    -------
    Openness score (0 to max_score).
    """
    if card.license_kind == LicenseKind.OPEN:
        score = max_score
    elif card.license_kind == LicenseKind.RESTRICTED:
        score = max_score * 0.5
    else:
        score = 0.0

    logger.debug("Openness: %s → %.1f/%.1f", card.license_kind, score, max_score)
    return round(score, 1)


def compute_safety_score(
    outcomes: list[VerificationOutcome],
    max_score: float = SAFETY_WEIGHT,
) -> float:
    """
    Compute safety score based on whether safety benchmarks are reported.

    Parameters
    ----------
    outcomes:
        List of verification outcomes.
    max_score:
        Maximum score for this component.

    Returns
    -------
    Safety score (0 to max_score).
    """
    if not outcomes:
        return 0.0

    # Extract unique benchmarks from outcomes
    reported_benchmarks = set()
    for outcome in outcomes:
        reported_benchmarks.add(_normalize_metric(outcome.claim.metric))

    # Count safety benchmarks
    safety_count = 0
    for benchmark in SAFETY_BENCHMARKS:
        if _normalize_metric(benchmark) in reported_benchmarks:
            safety_count += 1

    score = max_score if safety_count >= 1 else 0.0

    logger.debug("Safety: %d safety benchmarks → %.1f/%.1f", safety_count, score, max_score)
    return round(score, 1)


def compute_use_case_scores(
    outcomes: list[VerificationOutcome],
) -> dict[str, float]:
    """
    Compute per-use-case strength (0-100) based on available benchmark signals.

    A use-case score is the average of the best available value for its benchmarks,
    using verified official values when present, else claimed values as a fallback.
    """
    use_case_scores: dict[str, float] = {}
    if not outcomes:
        return use_case_scores

    # Build lookup by normalized metric
    normalized_outcomes: dict[str, list[VerificationOutcome]] = {}
    for outcome in outcomes:
        norm = _normalize_metric(outcome.claim.metric)
        normalized_outcomes.setdefault(norm, []).append(outcome)

    for use_case, benchmarks in USE_CASE_BENCHMARKS.items():
        values: list[float] = []
        for benchmark in benchmarks:
            norm_bm = _normalize_metric(benchmark)
            candidates = normalized_outcomes.get(norm_bm, [])
            for outcome in candidates:
                values.append(_value_for_outcome(outcome))
                break  # prefer first match
        if values:
            use_case_scores[use_case] = round(sum(values) / len(values), 1)

    return use_case_scores


def compute_trust_score(
    model_id: str,
    card: ModelCard,
    outcomes: list[VerificationOutcome],
) -> TrustScore:
    """
    Compute the overall trust score for a model.

    Parameters
    ----------
    model_id:
        The model identifier.
    card:
        Model card metadata.
    outcomes:
        List of verification outcomes for the model's claims.

    Returns
    -------
    A TrustScore object with the overall score and component breakdown.
    """
    coverage = compute_coverage_score(outcomes)
    verification = compute_verification_score(outcomes)
    performance_gap = compute_performance_gap_score(outcomes)
    openness = compute_openness_score(card)
    safety = compute_safety_score(outcomes)
    use_case_scores = compute_use_case_scores(outcomes)

    breakdown = TrustScoreBreakdown(
        coverage_score=coverage,
        verification_score=verification,
        performance_gap_score=performance_gap,
        openness_score=openness,
        safety_score=safety,
        use_case_scores=use_case_scores,
    )

    score = TrustScore(
        model_id=model_id,
        score=breakdown.total,
        breakdown=breakdown,
    )

    logger.info(
        "Trust score for %s: %.1f/100 (C:%.1f V:%.1f P:%.1f O:%.1f S:%.1f)",
        model_id,
        score.score,
        coverage,
        verification,
        performance_gap,
        openness,
        safety,
    )

    return score
