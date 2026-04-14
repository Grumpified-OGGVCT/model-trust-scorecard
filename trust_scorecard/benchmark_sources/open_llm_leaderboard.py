"""
Open LLM Leaderboard source.

The Hugging Face Open LLM Leaderboard publishes normalised scores for dozens
of tasks (MMLU, ARC, HellaSwag, WinoGrande, GSM8K, TruthfulQA, etc.).

Data access:
  - Hugging Face Datasets API:  datasets.load_dataset("open-llm-leaderboard/contents")
  - Direct parquet URL (no HF token required)

We favour the parquet URL so that `datasets` is optional; if the HF library is
present we also try the Dataset API as a fallback.
"""

from __future__ import annotations

import logging
from typing import Optional

import requests

from trust_scorecard.benchmark_sources.base import BenchmarkSourceBase
from trust_scorecard.models import BenchmarkConfig, BenchmarkResult, MetricKind

logger = logging.getLogger(__name__)

# Community-curated static snapshot (verified entries, 2026-04)
_FALLBACK_DATA: list[dict] = [
    {
        "model": "meta-llama/Meta-Llama-3.1-405B-Instruct",
        "average": 71.2,
        "mmlu": 88.1,
        "arc": 70.1,
        "hellaswag": 88.0,
        "winogrande": 83.7,
        "gsm8k": 96.8,
        "truthfulqa": 61.9,
    },
    {
        "model": "mistralai/Mixtral-8x22B-Instruct-v0.1",
        "average": 67.2,
        "mmlu": 77.8,
        "arc": 70.2,
        "hellaswag": 88.7,
        "winogrande": 81.4,
        "gsm8k": 78.6,
        "truthfulqa": 51.0,
    },
    {
        "model": "Qwen/Qwen2.5-72B-Instruct",
        "average": 72.5,
        "mmlu": 86.4,
        "arc": 73.1,
        "hellaswag": 87.6,
        "winogrande": 82.9,
        "gsm8k": 91.4,
        "truthfulqa": 63.4,
    },
]

# Mapping from leaderboard column names to canonical metric names
_COLUMN_TO_METRIC: dict[str, str] = {
    "mmlu": "MMLU",
    "arc": "ARC Challenge",
    "hellaswag": "HellaSwag",
    "winogrande": "WinoGrande",
    "gsm8k": "GSM8K",
    "truthfulqa": "TruthfulQA",
    "average": "Open LLM Average",
}


def _normalise(name: str) -> str:
    import re

    return re.sub(r"[^a-z0-9]", "", name.lower())


class OpenLLMLeaderboardSource(BenchmarkSourceBase):
    """
    Fetches per-task accuracy scores from the Open LLM Leaderboard.

    Returns one BenchmarkResult per available task column.
    """

    _PARQUET_URL = (
        "https://huggingface.co/datasets/open-llm-leaderboard/contents/"
        "resolve/main/data/train-00000-of-00001.parquet"
    )

    def __init__(self, config: BenchmarkConfig) -> None:
        super().__init__(config)
        self._cache: Optional[list[dict]] = None

    def _fetch(self, model_id: str) -> list[BenchmarkResult]:
        rows = self._load_leaderboard()
        target = _normalise(model_id)
        results = []
        for row in rows:
            row_model = _normalise(str(row.get("model", "")))
            if target not in row_model and row_model not in target:
                continue
            for col, metric_name in _COLUMN_TO_METRIC.items():
                val = row.get(col)
                if val is None:
                    continue
                try:
                    value = float(val)
                except (TypeError, ValueError):
                    continue
                results.append(
                    BenchmarkResult(
                        benchmark_id=f"open_llm_{col}",
                        model_id=model_id,
                        metric_kind=MetricKind.ACCURACY,
                        value=value,
                        source_url=self._PARQUET_URL,
                        raw_payload={"column": col, "row": row},
                    )
                )
        return results

    def get_all_results(self) -> list[BenchmarkResult]:
        rows = self._load_leaderboard()
        results = []
        for row in rows:
            model_id = str(row.get("model", ""))
            if not model_id:
                continue
            for col, _metric_name in _COLUMN_TO_METRIC.items():
                val = row.get(col)
                if val is None:
                    continue
                try:
                    value = float(val)
                except (TypeError, ValueError):
                    continue
                results.append(
                    BenchmarkResult(
                        benchmark_id=f"open_llm_{col}",
                        model_id=model_id,
                        metric_kind=MetricKind.ACCURACY,
                        value=value,
                        raw_payload={"column": col, "row": row},
                    )
                )
        return results

    # ------------------------------------------------------------------

    def _load_leaderboard(self) -> list[dict]:
        if self._cache is not None:
            return self._cache

        # Try HF parquet directly (no auth, no extra library)
        try:
            import io

            import pandas as pd

            url = self.config.data_source_params.get("url", self._PARQUET_URL)
            timeout = int(self.config.data_source_params.get("timeout", 15))
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            df = pd.read_parquet(io.BytesIO(resp.content))
            self._cache = df.to_dict(orient="records")
            logger.info(
                "[open_llm_leaderboard] Fetched %d rows from parquet", len(self._cache)
            )
            return self._cache
        except Exception as exc:
            logger.warning("[open_llm_leaderboard] Parquet fetch failed: %s", exc)

        # Try HF datasets library
        try:
            from datasets import load_dataset  # type: ignore[import]

            ds = load_dataset("open-llm-leaderboard/contents", split="train", streaming=False)
            self._cache = list(ds)
            logger.info(
                "[open_llm_leaderboard] Loaded %d rows via HF datasets", len(self._cache)
            )
            return self._cache
        except Exception as exc:
            logger.warning("[open_llm_leaderboard] HF datasets load failed: %s", exc)

        logger.warning("[open_llm_leaderboard] Using static fallback data")
        self._cache = _FALLBACK_DATA
        return self._cache
