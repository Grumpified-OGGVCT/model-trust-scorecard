"""
Benchmark source registry.

All public exports:
  - BenchmarkSourceBase      – abstract base class
  - BenchmarkSource          – alias for BenchmarkSourceBase
  - get_default_sources()    – return default source instances
"""

from trust_scorecard.benchmark_sources.base import BenchmarkSourceBase

# Alias for compatibility
BenchmarkSource = BenchmarkSourceBase


def get_default_sources() -> list[BenchmarkSourceBase]:
    """
    Return a list of default benchmark sources.

    Currently returns empty list as benchmark sources require external APIs.
    Populate this with SWEBenchSource, OpenLLMLeaderboardSource, etc. when
    they are fully implemented and configured.

    Returns
    -------
    List of BenchmarkSourceBase instances.
    """
    # TODO: Initialize actual sources when benchmark configs are ready
    # For now, return empty list - evaluations will work but with no
    # official data for verification
    return []


__all__ = [
    "BenchmarkSourceBase",
    "BenchmarkSource",
    "get_default_sources",
]
