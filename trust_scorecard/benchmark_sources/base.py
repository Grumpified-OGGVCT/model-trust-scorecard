"""
Abstract base class for all benchmark data sources.

Implementors must override `fetch(model_id)` which returns a list of
BenchmarkResult objects.  The base class handles logging and caching.
"""

from __future__ import annotations

import abc
import logging
from typing import Optional

from trust_scorecard.models import BenchmarkConfig, BenchmarkResult

logger = logging.getLogger(__name__)


class BenchmarkSourceBase(abc.ABC):
    """Abstract benchmark data source."""

    def __init__(self, config: BenchmarkConfig) -> None:
        self.config = config

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get_results(self, model_id: str) -> list[BenchmarkResult]:
        """
        Return all available results for *model_id* from this source.

        Wraps `_fetch` with logging and graceful error handling so that
        a single failing source never crashes the whole pipeline.
        """
        if not self.config.enabled:
            return []
        try:
            results = self._fetch(model_id)
            logger.debug(
                "[%s] fetched %d result(s) for model %r",
                self.config.id,
                len(results),
                model_id,
            )
            return results
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[%s] failed to fetch results for %r: %s",
                self.config.id,
                model_id,
                exc,
            )
            return []

    def get_all_results(self) -> list[BenchmarkResult]:
        """
        Return the full leaderboard (all models) for this source.

        Used by the verification engine to compute leaderboard medians /
        percentile ranks.  Override in subclasses that support it.
        """
        return []

    # ------------------------------------------------------------------
    # Subclass hooks
    # ------------------------------------------------------------------

    @abc.abstractmethod
    def _fetch(self, model_id: str) -> list[BenchmarkResult]:
        """Return results for *model_id* from this benchmark source."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_result(
        self,
        model_id: str,
        value: float,
        source_url: Optional[str] = None,
        raw_payload: Optional[dict] = None,
    ) -> BenchmarkResult:
        from datetime import datetime

        return BenchmarkResult(
            benchmark_id=self.config.id,
            model_id=model_id,
            metric_kind=self.config.metric_kind,
            value=value,
            retrieved_at=datetime.utcnow(),
            source_url=source_url or self.config.data_source_params.get("url"),
            raw_payload=raw_payload,
        )
