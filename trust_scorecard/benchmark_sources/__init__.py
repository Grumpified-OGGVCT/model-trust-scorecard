"""
Benchmark source registry.

All public exports:
  - BenchmarkSourceBase      – abstract base class
  - load_all_configs()       – load every JSON config in the benchmarks/ dir
  - get_source(cfg)          – return a concrete source implementation
  - fetch_results(model_id)  – convenience: query every enabled source
"""

from trust_scorecard.benchmark_sources.base import BenchmarkSourceBase
from trust_scorecard.benchmark_sources.registry import (
    get_source,
    load_all_configs,
    fetch_results_for_model,
)

__all__ = [
    "BenchmarkSourceBase",
    "get_source",
    "load_all_configs",
    "fetch_results_for_model",
]
