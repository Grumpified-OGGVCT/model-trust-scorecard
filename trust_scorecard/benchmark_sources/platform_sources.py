"""
Composite benchmark sources for community platforms (lm-eval, HELM, OpenCompass, SLM/edge).

These sources read curated JSON snapshots so they work offline, while still matching
the canonical benchmark IDs used in claims (e.g., "mmlu", "mmlupro", "longbench").
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from trust_scorecard.benchmark_sources.base import BenchmarkSourceBase
from trust_scorecard.models import BenchmarkConfig, BenchmarkResult, MetricKind

logger = logging.getLogger(__name__)


def _normalize_metric(name: str) -> str:
    return name.lower().replace("-", "").replace(" ", "").replace("_", "")


class _MultiBenchmarkJSONSource(BenchmarkSourceBase):
    """
    Generic source that emits one BenchmarkResult per metric in a JSON snapshot.

    JSON schema (list of rows):
    {
      "model_id": "gpt-4.1",
      "source_url": "https://example.com/leaderboard",
      "metrics": {
         "MMLU": 89.5,
         "GSM8K": 93.1,
         "HumanEval": 91.0,
         ...
      }
    }
    """

    def __init__(
        self,
        config: BenchmarkConfig,
        snapshot_path: Path,
        metric_kind_overrides: dict[str, MetricKind] | None = None,
    ) -> None:
        super().__init__(config)
        self._snapshot_path = snapshot_path
        self._cache: list[dict[str, Any]] | None = None
        self._metric_kind_overrides = {
            _normalize_metric(k): v for k, v in (metric_kind_overrides or {}).items()
        }

    # ------------------------------------------------------------------
    # BenchmarkSourceBase hooks
    # ------------------------------------------------------------------

    def _fetch(self, model_id: str) -> list[BenchmarkResult]:
        target = _normalize_metric(model_id)
        rows = self._load_snapshot()
        results: list[BenchmarkResult] = []

        for row in rows:
            row_id = str(row.get("model_id", ""))
            if not row_id:
                continue
            if target not in _normalize_metric(row_id) and _normalize_metric(row_id) not in target:
                continue
            results.extend(self._results_from_row(row))

        return results

    def get_all_results(self) -> list[BenchmarkResult]:
        rows = self._load_snapshot()
        results: list[BenchmarkResult] = []
        for row in rows:
            results.extend(self._results_from_row(row))
        return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load_snapshot(self) -> list[dict[str, Any]]:
        if self._cache is not None:
            return self._cache

        try:
            text = self._snapshot_path.read_text(encoding="utf-8")
            self._cache = json.loads(text)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] failed to read snapshot %s: %s", self.config.id, self._snapshot_path, exc)
            self._cache = []
        return self._cache

    def _results_from_row(self, row: dict[str, Any]) -> list[BenchmarkResult]:
        model_id = str(row.get("model_id", "")).strip()
        metrics = row.get("metrics") or {}
        if not model_id or not isinstance(metrics, dict):
            return []

        source_url = row.get("source_url") or self.config.data_source_params.get("url")
        results: list[BenchmarkResult] = []

        for metric_name, raw_value in metrics.items():
            if raw_value is None:
                continue
            try:
                value = float(raw_value)
            except (TypeError, ValueError):
                continue

            metric_key = _normalize_metric(metric_name)
            kind = self._metric_kind_overrides.get(metric_key, self.config.metric_kind)

            results.append(
                BenchmarkResult(
                    benchmark_id=metric_key,
                    model_id=model_id,
                    metric_kind=kind,
                    value=value,
                    source_url=source_url,
                    raw_payload={"metric": metric_name, "platform": self.config.id},
                )
            )

        return results


# ----------------------------------------------------------------------
# Concrete platform sources
# ----------------------------------------------------------------------

_BASE_DIR = Path(__file__).resolve().parents[2]


class LMEvalHarnessSource(_MultiBenchmarkJSONSource):
    """Aggregated results from EleutherAI lm-evaluation-harness."""

    def __init__(self, config: BenchmarkConfig) -> None:
        snapshot = _BASE_DIR / "benchmarks" / "lm_eval_harness_results.json"
        super().__init__(
            config,
            snapshot,
            metric_kind_overrides={
                "humaneval": MetricKind.PASS_AT_K,
            },
        )


class HELMSource(_MultiBenchmarkJSONSource):
    """Holistic Evaluation of Language Models (HELM) signals."""

    def __init__(self, config: BenchmarkConfig) -> None:
        snapshot = _BASE_DIR / "benchmarks" / "helm_results.json"
        super().__init__(config, snapshot)


class OpenCompassSource(_MultiBenchmarkJSONSource):
    """OpenCompass results, covering long-context, agentic/tool-use, and robustness suites."""

    def __init__(self, config: BenchmarkConfig) -> None:
        snapshot = _BASE_DIR / "benchmarks" / "opencompass_results.json"
        super().__init__(
            config,
            snapshot,
            metric_kind_overrides={
                "humaneval": MetricKind.PASS_AT_K,
            },
        )


class SLMBenchSource(_MultiBenchmarkJSONSource):
    """Edge / small-language-model benchmarks (SLM-Bench, SMOL WorldCup, TinyMobileLLM)."""

    def __init__(self, config: BenchmarkConfig) -> None:
        snapshot = _BASE_DIR / "benchmarks" / "slm_bench_results.json"
        super().__init__(config, snapshot)
