"""
Benchmark source registry.

All public exports:
  - BenchmarkSourceBase      – abstract base class
  - BenchmarkSource          – alias for BenchmarkSourceBase
  - SWEBenchSource           – SWE-bench leaderboard source
  - OpenLLMLeaderboardSource – Open LLM Leaderboard source
  - get_default_sources()    – return default source instances
"""

from trust_scorecard.benchmark_sources.base import BenchmarkSourceBase
from trust_scorecard.benchmark_sources.open_llm_leaderboard import OpenLLMLeaderboardSource
from trust_scorecard.benchmark_sources.swe_bench import SWEBenchSource
from trust_scorecard.models import BenchmarkConfig, MetricKind

# Alias for compatibility
BenchmarkSource = BenchmarkSourceBase


def get_default_sources() -> list[BenchmarkSourceBase]:
    """
    Return a list of default benchmark sources with built-in configurations.

    These sources use fallback data when live APIs are unreachable, so they
    work completely offline.

    Returns
    -------
    List of configured BenchmarkSourceBase instances.
    """
    sources = []

    # SWE-bench Verified leaderboard
    swe_bench_config = BenchmarkConfig(
        id="swe_bench_verified",
        display_name="SWE-bench Verified",
        description="Official SWE-bench Verified leaderboard (% instances resolved)",
        metric_kind=MetricKind.PERCENT_RESOLVED,
        weight_max=10.0,
        data_source="swe_bench_html",
        data_source_params={"url": "https://www.swebench.com/api/results"},
        tolerance_default=2.0,
        enabled=True,
        tags=["coding", "agentic", "real-world"],
    )
    sources.append(SWEBenchSource(swe_bench_config))

    # Open LLM Leaderboard - MMLU
    mmlu_config = BenchmarkConfig(
        id="mmlu",
        display_name="MMLU",
        description="Massive Multitask Language Understanding",
        metric_kind=MetricKind.ACCURACY,
        weight_max=8.0,
        data_source="hf_leaderboard",
        data_source_params={
            "dataset": "open-llm-leaderboard/contents",
            "metric": "mmlu",
        },
        tolerance_default=2.0,
        enabled=True,
        tags=["knowledge", "reasoning"],
    )
    sources.append(OpenLLMLeaderboardSource(mmlu_config))

    # Open LLM Leaderboard - GSM8K
    gsm8k_config = BenchmarkConfig(
        id="gsm8k",
        display_name="GSM8K",
        description="Grade School Math 8K",
        metric_kind=MetricKind.ACCURACY,
        weight_max=7.0,
        data_source="hf_leaderboard",
        data_source_params={
            "dataset": "open-llm-leaderboard/contents",
            "metric": "gsm8k",
        },
        tolerance_default=2.0,
        enabled=True,
        tags=["math", "reasoning"],
    )
    sources.append(OpenLLMLeaderboardSource(gsm8k_config))

    # Open LLM Leaderboard - TruthfulQA
    truthfulqa_config = BenchmarkConfig(
        id="truthfulqa",
        display_name="TruthfulQA",
        description="TruthfulQA (measuring truthfulness and safety)",
        metric_kind=MetricKind.ACCURACY,
        weight_max=6.0,
        data_source="hf_leaderboard",
        data_source_params={
            "dataset": "open-llm-leaderboard/contents",
            "metric": "truthfulqa",
        },
        tolerance_default=2.0,
        enabled=True,
        tags=["safety", "truthfulness"],
    )
    sources.append(OpenLLMLeaderboardSource(truthfulqa_config))

    return sources


__all__ = [
    "BenchmarkSourceBase",
    "BenchmarkSource",
    "SWEBenchSource",
    "OpenLLMLeaderboardSource",
    "get_default_sources",
]
