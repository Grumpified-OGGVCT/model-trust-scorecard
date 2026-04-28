"""Helpers for summarising external source evidence in reports and dashboards."""

from __future__ import annotations

from typing import Any

from trust_scorecard.models import BenchmarkResult, Claim, ModelCard, VerificationOutcome

BENCHLM_CATEGORY_IDS = {
    "benchlm_agentic": "agentic",
    "benchlm_coding": "coding",
    "benchlm_reasoning": "reasoning",
    "benchlm_multimodal_grounded": "multimodal_grounded",
    "benchlm_knowledge": "knowledge",
    "benchlm_multilingual": "multilingual",
    "benchlm_instruction_following": "instruction_following",
    "benchlm_math": "math",
}

AA_CATEGORY_IDS = {
    "aa_intelligence_index": "reasoning",
    "aa_coding_index": "coding",
    "aa_math_index": "math",
    "aa_mmlu_pro": "knowledge",
    "aa_gpqa": "knowledge",
    "aa_hle": "knowledge",
    "aa_livecodebench": "coding",
    "aa_scicode": "coding",
    "aa_math_500": "math",
    "aa_aime": "math",
}

AA_RUNTIME_OR_PRICE_PREFIXES = (
    "aa_output_tokens_per_second",
    "aa_time_to_first",
    "aa_price_",
)


def summarize_source_evidence(
    card: ModelCard,
    claims: list[Claim],
    outcomes: list[VerificationOutcome],
    benchmark_results: list[BenchmarkResult],
) -> dict[str, Any]:
    """Return source freshness, category coverage, and ranking-lane metadata."""
    source_names: set[str] = set()
    source_freshness: dict[str, str] = {}
    source_urls: dict[str, str] = {}
    benchlm_category_scores: dict[str, float] = {}
    aa_scores: dict[str, float] = {}
    covered_categories: set[str] = set()
    rankable_benchmark_ids: set[str] = set()
    benchlm_rank: int | None = None
    benchlm_score: float | None = None
    benchlm_mode: str | None = None

    for result in benchmark_results:
        if result.model_id != card.model_id:
            continue
        raw = result.raw_payload or {}
        source = raw.get("source")
        if not source:
            continue
        source_name = str(source)
        source_names.add(source_name)
        if result.source_url:
            source_urls[source_name] = result.source_url

        freshness = raw.get("lastUpdated") or raw.get("retrieved_at") or raw.get("retrievedAt")
        if freshness:
            source_freshness[source_name] = str(freshness)

        if source_name == "BenchLM":
            benchlm_mode = str(raw.get("mode") or benchlm_mode or "provisional")
            if result.benchmark_id == "benchlm_overall":
                benchlm_score = float(result.value)
                rank_value = raw.get("rank")
                if rank_value is not None:
                    benchlm_rank = int(rank_value)
                rankable_benchmark_ids.add(result.benchmark_id)
            category = BENCHLM_CATEGORY_IDS.get(result.benchmark_id)
            if category:
                benchlm_category_scores[category] = float(result.value)
                covered_categories.add(category)
                rankable_benchmark_ids.add(result.benchmark_id)

        if source_name == "Artificial Analysis":
            category = AA_CATEGORY_IDS.get(result.benchmark_id)
            if category:
                aa_scores[result.benchmark_id] = float(result.value)
                covered_categories.add(category)
                rankable_benchmark_ids.add(result.benchmark_id)

    if benchlm_score is not None:
        ranking_lane = "verified" if benchlm_mode == "verified" else "provisional"
    elif aa_scores:
        ranking_lane = "provisional"
    elif card.leaderboard_score is not None or card.leaderboard_rank is not None:
        ranking_lane = "estimated"
    elif claims:
        ranking_lane = "local_only"
    else:
        ranking_lane = "no_evidence"

    category_count = len(covered_categories)
    rankable_count = len(rankable_benchmark_ids)
    confidence_tier = _confidence_tier(rankable_count, category_count, ranking_lane)

    source_evidence = [
        {
            "source": source,
            "freshness": source_freshness.get(source),
            "url": source_urls.get(source),
        }
        for source in sorted(source_names)
    ]

    return {
        "ranking_lane": ranking_lane,
        "confidence_tier": confidence_tier,
        "source_evidence": source_evidence,
        "source_freshness": source_freshness,
        "primary_leaderboard_source": "BenchLM" if benchlm_score is not None else None,
        "primary_leaderboard_rank": benchlm_rank,
        "primary_leaderboard_score": benchlm_score,
        "benchlm_mode": benchlm_mode,
        "benchlm_category_scores": benchlm_category_scores,
        "artificial_analysis_scores": aa_scores,
        "category_coverage": {
            "covered": category_count,
            "total": 8,
            "categories": sorted(covered_categories),
        },
        "rankable_benchmark_count": rankable_count,
        "rankable_category_count": category_count,
    }


def _confidence_tier(rankable_count: int, category_count: int, ranking_lane: str) -> str:
    if rankable_count >= 20 and category_count >= 7:
        return "High confidence"
    if rankable_count >= 12 and category_count >= 5:
        return "Good confidence"
    if rankable_count >= 8 and category_count >= 3:
        return "Moderate confidence"
    if ranking_lane in {"provisional", "verified"}:
        return "Sourced external"
    if ranking_lane == "estimated":
        return "Low / estimated"
    return "Low confidence"