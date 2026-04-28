"""BenchLM leaderboard source adapter."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import requests  # type: ignore[import-untyped]

from trust_scorecard.benchmark_sources.base import BenchmarkSourceBase
from trust_scorecard.models import BenchmarkConfig, BenchmarkResult, MetricKind

logger = logging.getLogger(__name__)

BENCHLM_LEADERBOARD_URL = "https://benchlm.ai/api/data/leaderboard"

_CATEGORY_TO_BENCHMARK_ID = {
    "agentic": "benchlm_agentic",
    "coding": "benchlm_coding",
    "reasoning": "benchlm_reasoning",
    "multimodalGrounded": "benchlm_multimodal_grounded",
    "knowledge": "benchlm_knowledge",
    "multilingual": "benchlm_multilingual",
    "instructionFollowing": "benchlm_instruction_following",
    "math": "benchlm_math",
}


def _normalise_name(name: str) -> str:
    value = re.sub(r"[^a-z0-9]", "", name.lower())
    return value.removesuffix("cloud")


def _candidate_aliases(name: str) -> set[str]:
    normalized = _normalise_name(name)
    aliases = {normalized}
    aliases.add(normalized.replace("kimik", "kimi"))
    aliases.add(normalized.replace("reasoning", ""))
    return {alias for alias in aliases if alias}


def _names_match(left: str, right: str) -> bool:
    left_text = left.lower()
    right_text = right.lower()
    if ("reasoning" in left_text) != ("reasoning" in right_text):
        return False
    left_aliases = _candidate_aliases(left)
    right_aliases = _candidate_aliases(right)
    return any(a == b or a in b or b in a for a in left_aliases for b in right_aliases)


class BenchLMSource(BenchmarkSourceBase):
    """Fetches BenchLM overall and category scores from the public JSON endpoint."""

    def __init__(self, config: BenchmarkConfig) -> None:
        super().__init__(config)
        self._cache: dict[str, Any] | None = None

    def _fetch(self, model_id: str) -> list[BenchmarkResult]:
        payload = self._load_payload()
        results: list[BenchmarkResult] = []
        for row in payload.get("models", []):
            if not _names_match(model_id, str(row.get("model", ""))):
                continue
            results.extend(self._results_from_row(row, model_id=model_id, payload=payload))
        return results

    def get_all_results(self) -> list[BenchmarkResult]:
        payload = self._load_payload()
        results: list[BenchmarkResult] = []
        for row in payload.get("models", []):
            model_name = str(row.get("model", "")).strip()
            if not model_name:
                continue
            results.extend(self._results_from_row(row, model_id=model_name, payload=payload))
        return results

    def _results_from_row(
        self,
        row: dict[str, Any],
        *,
        model_id: str,
        payload: dict[str, Any],
    ) -> list[BenchmarkResult]:
        results: list[BenchmarkResult] = []
        source_url = self.config.data_source_params.get("url", BENCHLM_LEADERBOARD_URL)
        common_payload = {
            "source": "BenchLM",
            "lastUpdated": payload.get("lastUpdated"),
            "mode": payload.get("mode"),
            "rank": row.get("rank"),
            "model": row.get("model"),
            "creator": row.get("creator"),
            "sourceType": row.get("sourceType"),
        }

        overall_score = row.get("overallScore")
        if overall_score is not None:
            results.append(
                BenchmarkResult(
                    benchmark_id="benchlm_overall",
                    model_id=model_id,
                    metric_kind=MetricKind.SCORE,
                    value=float(overall_score),
                    source_url=source_url,
                    raw_payload={**common_payload, "overallScore": overall_score},
                )
            )

        category_scores = row.get("categoryScores") or {}
        if isinstance(category_scores, dict):
            for category, benchmark_id in _CATEGORY_TO_BENCHMARK_ID.items():
                value = category_scores.get(category)
                if value is None:
                    continue
                results.append(
                    BenchmarkResult(
                        benchmark_id=benchmark_id,
                        model_id=model_id,
                        metric_kind=MetricKind.SCORE,
                        value=float(value),
                        source_url=source_url,
                        raw_payload={
                            **common_payload,
                            "category": category,
                            "categoryScores": category_scores,
                        },
                    )
                )
        return results

    def _load_payload(self) -> dict[str, Any]:
        if self._cache is not None:
            return self._cache

        cache_path = Path(self.config.data_source_params.get("cache_path", "benchlm_cache.json"))
        if cache_path.exists():
            try:
                self._cache = json.loads(cache_path.read_text(encoding="utf-8"))
                logger.info("[benchlm] Loaded cached leaderboard from %s", cache_path)
                if isinstance(self._cache, dict):
                    return self._cache
            except Exception as exc:  # noqa: BLE001
                logger.warning("[benchlm] Cache load failed: %s", exc)

        url = self.config.data_source_params.get("url", BENCHLM_LEADERBOARD_URL)
        timeout = int(self.config.data_source_params.get("timeout", 15))
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            self._cache = response.json()
            try:
                cache_path.write_text(json.dumps(self._cache, indent=2), encoding="utf-8")
            except OSError:
                pass
            if isinstance(self._cache, dict):
                return self._cache
        except Exception as exc:  # noqa: BLE001
            logger.warning("[benchlm] Live fetch failed: %s", exc)

        self._cache = {"models": [], "mode": "unavailable", "lastUpdated": None}
        assert self._cache is not None
        return self._cache