"""
SWE-bench leaderboard source.

The official SWE-bench leaderboard is maintained at https://www.swebench.com/
and published as a public JSON file.  We also support a static fallback
derived from the community-curated DEV.to article so the pipeline works
completely offline.

Data format (swebench.com API endpoint):
  [{"name": "Claude Opus 4.5 (SWA)", "resolved": 72.0, "verified": true}, ...]

The "resolved" field is the % of instances correctly fixed.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional

import requests

from trust_scorecard.benchmark_sources.base import BenchmarkSourceBase
from trust_scorecard.models import BenchmarkConfig, BenchmarkResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Community-curated fallback data (kept current as of 2026-04)
# These are the verified entries from the DEV.to leaderboard article.
# The pipeline uses this when the live endpoint is unreachable.
# ---------------------------------------------------------------------------

_FALLBACK_DATA: list[dict] = [
    {"name": "MiniMax M2.5", "resolved": 80.2, "org": "MiniMax"},
    {"name": "Kimi K2.5", "resolved": 79.8, "org": "Moonshot AI"},
    {"name": "Claude Sonnet 4.5 (SWA)", "resolved": 77.4, "org": "Anthropic"},
    {"name": "DeepSeek V3.2", "resolved": 76.5, "org": "DeepSeek"},
    {"name": "GPT-4.1", "resolved": 54.6, "org": "OpenAI"},
    {"name": "Gemini 2.5 Pro", "resolved": 63.8, "org": "Google"},
    {"name": "Claude 3.7 Sonnet", "resolved": 70.3, "org": "Anthropic"},
    {"name": "Claude 3.5 Sonnet", "resolved": 49.0, "org": "Anthropic"},
    {"name": "GPT-4o", "resolved": 23.0, "org": "OpenAI"},
    {"name": "Llama 3.1 405B", "resolved": 17.0, "org": "Meta"},
    {"name": "o3 (low)", "resolved": 71.7, "org": "OpenAI"},
    {"name": "o3-mini (high)", "resolved": 49.3, "org": "OpenAI"},
    {"name": "Qwen2.5-Coder-32B", "resolved": 43.6, "org": "Alibaba"},
]


def _normalise_name(name: str) -> str:
    """Lower-case, strip punctuation/spaces for fuzzy matching."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


class SWEBenchSource(BenchmarkSourceBase):
    """
    Fetches % Resolved scores from the SWE-bench leaderboard.

    Supports:
      - Live JSON endpoint (swebench.com)
      - Locally cached JSON file
      - Built-in static fallback
    """

    # URL that returns the public leaderboard as JSON
    _LIVE_URL = "https://www.swebench.com/api/results"

    def __init__(self, config: BenchmarkConfig) -> None:
        super().__init__(config)
        self._cache: Optional[list[dict]] = None

    # ------------------------------------------------------------------
    # BenchmarkSourceBase implementation
    # ------------------------------------------------------------------

    def _fetch(self, model_id: str) -> list[BenchmarkResult]:
        rows = self._load_leaderboard()
        target = _normalise_name(model_id)
        results = []
        for row in rows:
            row_name = _normalise_name(row.get("name", ""))
            if target in row_name or row_name in target:
                value = float(row.get("resolved", row.get("score", 0)))
                results.append(
                    self._make_result(
                        model_id=model_id,
                        value=value,
                        source_url=self._LIVE_URL,
                        raw_payload=row,
                    )
                )
        return results

    def get_all_results(self) -> list[BenchmarkResult]:
        rows = self._load_leaderboard()
        results = []
        for row in rows:
            name = row.get("name", "")
            if not name:
                continue
            value = float(row.get("resolved", row.get("score", 0)))
            results.append(
                self._make_result(
                    model_id=name,
                    value=value,
                    source_url=self._LIVE_URL,
                    raw_payload=row,
                )
            )
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_leaderboard(self) -> list[dict]:
        if self._cache is not None:
            return self._cache

        # 1. Try a locally-cached JSON file (populated by a previous live fetch)
        cache_path = Path(
            self.config.data_source_params.get("cache_path", "swe_bench_cache.json")
        )
        if cache_path.exists():
            try:
                self._cache = json.loads(cache_path.read_text())
                logger.info("[swe_bench] Loaded %d rows from local cache", len(self._cache))
                return self._cache
            except Exception as exc:
                logger.warning("[swe_bench] Cache load failed: %s", exc)

        # 2. Try the live endpoint
        live_url = self.config.data_source_params.get("url", self._LIVE_URL)
        timeout = int(self.config.data_source_params.get("timeout", 10))
        try:
            resp = requests.get(live_url, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            rows: list[dict] = data if isinstance(data, list) else data.get("results", [])
            self._cache = rows
            # Persist for next run
            try:
                cache_path.write_text(json.dumps(rows, indent=2))
            except OSError:
                pass
            logger.info("[swe_bench] Fetched %d rows from live endpoint", len(rows))
            return rows
        except Exception as exc:
            logger.warning("[swe_bench] Live fetch failed (%s); using static fallback", exc)

        # 3. Static fallback
        self._cache = _FALLBACK_DATA
        return self._cache
