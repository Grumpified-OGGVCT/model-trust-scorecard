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
from trust_scorecard.benchmark_sources.platform_sources import (
    HELMSource,
    LMEvalHarnessSource,
    OpenCompassSource,
    SLMBenchSource,
)
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
    sources: list[BenchmarkSourceBase] = []

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

    # lm-eval-harness aggregate (broad, multi-genre)
    lm_eval_config = BenchmarkConfig(
        id="lm_eval_harness",
        display_name="LM Evaluation Harness",
        description="EleutherAI lm-evaluation-harness aggregate tasks",
        metric_kind=MetricKind.ACCURACY,
        weight_max=7.0,
        data_source="lm_eval_harness",
        data_source_params={"url": "https://github.com/EleutherAI/lm-evaluation-harness"},
        tolerance_default=2.0,
        enabled=True,
        tags=["coding", "reasoning", "commonsense", "multilingual"],
    )
    sources.append(LMEvalHarnessSource(lm_eval_config))

    # HELM (holistic safety/latency/harms + capability)
    helm_config = BenchmarkConfig(
        id="helm",
        display_name="HELM",
        description="Holistic Evaluation of Language Models (capability + safety)",
        metric_kind=MetricKind.SCORE,
        weight_max=6.0,
        data_source="helm",
        data_source_params={"url": "https://github.com/stanford-crfm/helm"},
        tolerance_default=2.0,
        enabled=True,
        tags=["safety", "long-context", "efficiency"],
    )
    sources.append(HELMSource(helm_config))

    # OpenCompass (long-context + agent/tool-use + robustness)
    opencompass_config = BenchmarkConfig(
        id="opencompass",
        display_name="OpenCompass",
        description="OpenCompass consolidated benchmarks (LongBench, NeedleBench, AgentBench, MT-Bench)",
        metric_kind=MetricKind.SCORE,
        weight_max=7.0,
        data_source="opencompass",
        data_source_params={"url": "https://github.com/open-compass/opencompass"},
        tolerance_default=2.0,
        enabled=True,
        tags=["long-context", "agentic", "robustness"],
    )
    sources.append(OpenCompassSource(opencompass_config))

    # Small/edge model benchmarks
    slm_config = BenchmarkConfig(
        id="slm_bench",
        display_name="SLM Benchmarks",
        description="Edge/SLM benchmarks (SLM-Bench, SMOL WorldCup, TinyMobileLLM)",
        metric_kind=MetricKind.SCORE,
        weight_max=5.0,
        data_source="slm_bench",
        data_source_params={"url": "https://slmbench.com"},
        tolerance_default=2.0,
        enabled=True,
        tags=["edge", "multilingual", "efficiency"],
    )
    sources.append(SLMBenchSource(slm_config))

    return sources


__all__ = [
    "BenchmarkSourceBase",
    "BenchmarkSource",
    "SWEBenchSource",
    "OpenLLMLeaderboardSource",
    "LMEvalHarnessSource",
    "HELMSource",
    "OpenCompassSource",
    "SLMBenchSource",
    "get_default_sources",
]
