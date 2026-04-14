"""
Claim verification engine.

Match extracted claims against official benchmark sources to determine:
  - VERIFIED:   claim matches official value within tolerance
  - REFUTED:    claim deviates beyond tolerance
  - UNVERIFIABLE: no official data available

The engine also computes percentile rankings for models on each benchmark
when sufficient leaderboard data is available.
"""

from __future__ import annotations

import logging
from typing import Optional

from trust_scorecard.models import (
    BenchmarkResult,
    Claim,
    VerificationOutcome,
    VerificationStatus,
)

logger = logging.getLogger(__name__)


class VerificationEngine:
    """
    Engine for verifying claims against official benchmark results.
    """

    def __init__(
        self,
        benchmark_results: list[BenchmarkResult],
        default_tolerance: float = 2.0,
    ):
        """
        Initialize the verification engine.

        Parameters
        ----------
        benchmark_results:
            List of official benchmark results to verify against.
        default_tolerance:
            Default absolute tolerance for claim verification (in percentage points).
        """
        self.benchmark_results = benchmark_results
        self.default_tolerance = default_tolerance
        # Build index: (model_id, benchmark_id) -> BenchmarkResult
        self._index = {
            (r.model_id, r.benchmark_id): r for r in benchmark_results
        }

    def verify_claim(
        self,
        model_id: str,
        claim: Claim,
        tolerance: float | None = None,
    ) -> VerificationOutcome:
        """
        Verify a single claim against official benchmark data.

        Parameters
        ----------
        model_id:
            The model being evaluated.
        claim:
            The claim to verify.
        tolerance:
            Absolute tolerance in percentage points. If None, uses default_tolerance.

        Returns
        -------
        A VerificationOutcome describing the verification result.
        """
        tolerance = tolerance if tolerance is not None else self.default_tolerance

        # Try to find matching benchmark result
        # We need to match on benchmark name - map claim.metric to benchmark_id
        benchmark_result = self._find_matching_result(model_id, claim)

        if benchmark_result is None:
            return VerificationOutcome(
                claim=claim,
                status=VerificationStatus.UNVERIFIABLE,
                official_value=None,
                delta=None,
                tolerance=tolerance,
                benchmark_result=None,
                notes=f"No official data found for {claim.metric}",
            )

        # Compare claimed value with official value
        official_value = benchmark_result.value
        delta = abs(claim.value - official_value)

        if delta <= tolerance:
            status = VerificationStatus.VERIFIED
            notes = f"Claim matches official value within ±{tolerance}%"
        else:
            status = VerificationStatus.REFUTED
            notes = (
                f"Claim deviates from official value by {delta:.1f}% "
                f"(tolerance: ±{tolerance}%)"
            )

        return VerificationOutcome(
            claim=claim,
            status=status,
            official_value=official_value,
            delta=delta,
            tolerance=tolerance,
            benchmark_result=benchmark_result,
            notes=notes,
        )

    def verify_all(
        self,
        model_id: str,
        claims: list[Claim],
        tolerance: float | None = None,
    ) -> list[VerificationOutcome]:
        """
        Verify all claims for a model.

        Parameters
        ----------
        model_id:
            The model being evaluated.
        claims:
            List of claims to verify.
        tolerance:
            Absolute tolerance in percentage points. If None, uses default_tolerance.

        Returns
        -------
        List of VerificationOutcomes, one per claim.
        """
        return [
            self.verify_claim(model_id, claim, tolerance)
            for claim in claims
        ]

    def compute_percentile(
        self,
        benchmark_id: str,
        value: float,
    ) -> float | None:
        """
        Compute the percentile rank for a given value on a benchmark.

        Parameters
        ----------
        benchmark_id:
            The benchmark identifier.
        value:
            The score to rank.

        Returns
        -------
        Percentile rank (0-100), or None if insufficient data.
        """
        # Collect all scores for this benchmark
        scores = [
            r.value
            for r in self.benchmark_results
            if r.benchmark_id == benchmark_id
        ]

        if len(scores) < 2:
            return None

        # Count how many scores are strictly less than the given value
        count_below = sum(1 for s in scores if s < value)
        percentile = (count_below / len(scores)) * 100.0
        return round(percentile, 1)

    def _find_matching_result(
        self,
        model_id: str,
        claim: Claim,
    ) -> BenchmarkResult | None:
        """
        Find the benchmark result matching a claim.

        Attempts to match by:
        1. Exact benchmark_id match
        2. Fuzzy match on benchmark name (case-insensitive, normalized)

        Parameters
        ----------
        model_id:
            The model identifier.
        claim:
            The claim to match.

        Returns
        -------
        Matching BenchmarkResult or None.
        """
        # Try exact match first
        benchmark_id = self._normalize_benchmark_name(claim.metric)
        key = (model_id, benchmark_id)
        if key in self._index:
            return self._index[key]

        # Try fuzzy match on all results for this model
        for (mid, bid), result in self._index.items():
            if mid != model_id:
                continue
            if self._benchmark_names_match(claim.metric, bid):
                return result

        return None

    @staticmethod
    def _normalize_benchmark_name(name: str) -> str:
        """
        Normalize a benchmark name to a canonical form.

        Converts to lowercase, removes spaces and hyphens.
        """
        return name.lower().replace(" ", "").replace("-", "").replace("_", "")

    @staticmethod
    def _benchmark_names_match(name1: str, name2: str) -> bool:
        """
        Check if two benchmark names refer to the same benchmark.

        Uses normalized comparison.
        """
        n1 = VerificationEngine._normalize_benchmark_name(name1)
        n2 = VerificationEngine._normalize_benchmark_name(name2)
        return n1 == n2


def create_engine_from_sources(
    sources: list,  # List of BenchmarkSource instances
    model_ids: list[str] | None = None,
    default_tolerance: float = 2.0,
) -> VerificationEngine:
    """
    Create a verification engine by fetching data from benchmark sources.

    Parameters
    ----------
    sources:
        List of BenchmarkSource instances to fetch data from.
    model_ids:
        Optional list of model IDs to fetch. If None, fetches all available.
    default_tolerance:
        Default tolerance for verification.

    Returns
    -------
    A configured VerificationEngine.
    """
    all_results: list[BenchmarkResult] = []
    seen: set[tuple[str, str]] = set()

    def _add(items: list[BenchmarkResult]) -> None:
        for item in items:
            key = (item.model_id, item.benchmark_id)
            if key in seen:
                continue
            seen.add(key)
            all_results.append(item)

    for source in sources:
        logger.info("Fetching results from %s", source.__class__.__name__)
        try:
            if model_ids:
                for model_id in model_ids:
                    _add(source.get_results(model_id))
            _add(source.get_all_results())
        except Exception as exc:
            logger.warning(
                "Failed to fetch from %s: %s",
                source.__class__.__name__,
                exc,
            )

    logger.info("Loaded %d benchmark results", len(all_results))
    return VerificationEngine(all_results, default_tolerance)
