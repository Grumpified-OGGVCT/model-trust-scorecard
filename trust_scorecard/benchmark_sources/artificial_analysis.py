"""Artificial Analysis source adapter."""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import requests  # type: ignore[import-untyped]

from trust_scorecard.benchmark_sources.base import BenchmarkSourceBase
from trust_scorecard.models import BenchmarkConfig, BenchmarkResult, MetricKind

logger = logging.getLogger(__name__)

ARTIFICIAL_ANALYSIS_MODELS_URL = "https://artificialanalysis.ai/api/v2/data/llms/models"

_EVALUATION_TO_BENCHMARK_ID = {
    "artificial_analysis_intelligence_index": "aa_intelligence_index",
    "artificial_analysis_coding_index": "aa_coding_index",
    "artificial_analysis_math_index": "aa_math_index",
    "mmlu_pro": "aa_mmlu_pro",
    "gpqa": "aa_gpqa",
    "hle": "aa_hle",
    "livecodebench": "aa_livecodebench",
    "scicode": "aa_scicode",
    "math_500": "aa_math_500",
    "aime": "aa_aime",
}

_RUNTIME_TO_BENCHMARK_ID = {
    "median_output_tokens_per_second": "aa_output_tokens_per_second",
    "median_time_to_first_token_seconds": "aa_time_to_first_token_seconds",
    "median_time_to_first_answer_token": "aa_time_to_first_answer_token_seconds",
}

_PRICING_TO_BENCHMARK_ID = {
    "price_1m_blended_3_to_1": "aa_price_1m_blended_3_to_1",
    "price_1m_input_tokens": "aa_price_1m_input_tokens",
    "price_1m_output_tokens": "aa_price_1m_output_tokens",
}


def _normalise_name(name: str) -> str:
    value = re.sub(r"[^a-z0-9]", "", name.lower())
    return value.removesuffix("cloud")


def _names_match(left: str, right: str) -> bool:
    if ("reasoning" in left.lower()) != ("reasoning" in right.lower()):
        return False
    left_norm = _normalise_name(left).replace("kimik", "kimi")
    right_norm = _normalise_name(right).replace("kimik", "kimi")
    return left_norm == right_norm or left_norm in right_norm or right_norm in left_norm


class ArtificialAnalysisSource(BenchmarkSourceBase):
    """Fetches Artificial Analysis model evaluations, runtime, and pricing metadata."""

    def __init__(self, config: BenchmarkConfig) -> None:
        super().__init__(config)
        self._cache: list[dict[str, Any]] | None = None

    def _fetch(self, model_id: str) -> list[BenchmarkResult]:
        rows = self._load_rows()
        results: list[BenchmarkResult] = []
        for row in rows:
            source_name = str(row.get("name") or row.get("slug") or row.get("id") or "")
            if not _names_match(model_id, source_name):
                continue
            results.extend(self._results_from_row(row, model_id=model_id))
        return results

    def get_all_results(self) -> list[BenchmarkResult]:
        results: list[BenchmarkResult] = []
        for row in self._load_rows():
            model_id = str(row.get("name") or row.get("slug") or row.get("id") or "").strip()
            if not model_id:
                continue
            results.extend(self._results_from_row(row, model_id=model_id))
        return results

    def _results_from_row(self, row: dict[str, Any], *, model_id: str) -> list[BenchmarkResult]:
        source_url = self.config.data_source_params.get("url", ARTIFICIAL_ANALYSIS_MODELS_URL)
        retrieved_at = datetime.utcnow().isoformat()
        common_payload = {
            "source": "Artificial Analysis",
            "retrieved_at": retrieved_at,
            "id": row.get("id"),
            "name": row.get("name"),
            "slug": row.get("slug"),
            "model_creator": row.get("model_creator"),
        }
        results: list[BenchmarkResult] = []

        for name, value in _flatten_evaluations(row.get("evaluations")).items():
            benchmark_id = _EVALUATION_TO_BENCHMARK_ID.get(name)
            if benchmark_id is None or value is None:
                continue
            results.append(
                BenchmarkResult(
                    benchmark_id=benchmark_id,
                    model_id=model_id,
                    metric_kind=MetricKind.SCORE,
                    value=float(value),
                    source_url=source_url,
                    raw_payload={**common_payload, "evaluation": name, "raw": row.get("evaluations")},
                )
            )

        for field, benchmark_id in _RUNTIME_TO_BENCHMARK_ID.items():
            raw_value = row.get(field)
            if raw_value is None:
                continue
            try:
                numeric_value = float(raw_value)
            except (TypeError, ValueError):
                continue
            results.append(
                BenchmarkResult(
                    benchmark_id=benchmark_id,
                    model_id=model_id,
                    metric_kind=MetricKind.SCORE,
                    value=numeric_value,
                    source_url=source_url,
                    raw_payload={**common_payload, "runtime_metric": field},
                )
            )

        pricing = row.get("pricing") or {}
        if isinstance(pricing, dict):
            for field, benchmark_id in _PRICING_TO_BENCHMARK_ID.items():
                raw_value = pricing.get(field)
                if raw_value is None:
                    continue
                try:
                    numeric_value = float(raw_value)
                except (TypeError, ValueError):
                    continue
                results.append(
                    BenchmarkResult(
                        benchmark_id=benchmark_id,
                        model_id=model_id,
                        metric_kind=MetricKind.SCORE,
                        value=numeric_value,
                        source_url=source_url,
                        raw_payload={**common_payload, "pricing_metric": field, "pricing": pricing},
                    )
                )
        return results

    def _load_rows(self) -> list[dict[str, Any]]:
        if self._cache is not None:
            return self._cache

        cache_path = self.config.data_source_params.get("cache_path")
        if cache_path and Path(cache_path).exists():
            try:
                cached = json.loads(Path(cache_path).read_text(encoding="utf-8"))
                self._cache = _extract_rows(cached)
                logger.info("[artificial_analysis] Loaded %d cached rows", len(self._cache))
                return self._cache
            except Exception as exc:  # noqa: BLE001
                logger.warning("[artificial_analysis] Cache load failed: %s", exc)

        api_key = os.environ.get("ARTIFICIAL_ANALYSIS_API_KEY")
        if not api_key:
            logger.info("[artificial_analysis] ARTIFICIAL_ANALYSIS_API_KEY not set; skipping live fetch")
            self._cache = []
            return self._cache

        url = self.config.data_source_params.get("url", ARTIFICIAL_ANALYSIS_MODELS_URL)
        timeout = int(self.config.data_source_params.get("timeout", 20))
        try:
            response = requests.get(url, headers={"x-api-key": api_key}, timeout=timeout)
            response.raise_for_status()
            payload = response.json()
            self._cache = _extract_rows(payload)
            if cache_path:
                try:
                    Path(cache_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
                except OSError:
                    pass
            return self._cache
        except Exception as exc:  # noqa: BLE001
            logger.warning("[artificial_analysis] Live fetch failed: %s", exc)
            self._cache = []
            return self._cache


def _extract_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("data", "models", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
    return []


def _flatten_evaluations(evaluations: Any) -> dict[str, float]:
    flattened: dict[str, float] = {}
    iterator: Iterable[tuple[Any, Any]]
    if isinstance(evaluations, dict):
        iterator = evaluations.items()
    elif isinstance(evaluations, list):
        iterator = ((_evaluation_name(item), _evaluation_score(item)) for item in evaluations)
    else:
        return flattened

    for name, value in iterator:
        if not name or value is None:
            continue
        try:
            flattened[str(name)] = float(value)
        except (TypeError, ValueError):
            continue
    return flattened


def _evaluation_name(item: Any) -> str | None:
    if not isinstance(item, dict):
        return None
    return item.get("name") or item.get("id") or item.get("slug") or item.get("benchmark")


def _evaluation_score(item: Any) -> float | None:
    if not isinstance(item, dict):
        return None
    for key in ("score", "value", "percent", "accuracy"):
        if item.get(key) is not None:
            return item[key]
    return None