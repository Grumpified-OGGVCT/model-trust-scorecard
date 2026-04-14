from trust_scorecard.benchmark_sources.platform_sources import (
    HELMSource,
    LMEvalHarnessSource,
    OpenCompassSource,
    SLMBenchSource,
)
from trust_scorecard.models import BenchmarkConfig, MetricKind


def _cfg(source_id: str, metric_kind: MetricKind) -> BenchmarkConfig:
    return BenchmarkConfig(
        id=source_id,
        display_name=source_id,
        description="test config",
        metric_kind=metric_kind,
        weight_max=1.0,
        data_source=source_id,
        data_source_params={},
        tolerance_default=2.0,
        enabled=True,
    )


def test_lm_eval_harness_source_loads_fallback():
    source = LMEvalHarnessSource(_cfg("lm_eval_harness", MetricKind.ACCURACY))
    results = source.get_results("gpt-4.1")
    ids = {r.benchmark_id for r in results}
    kinds = {r.benchmark_id: r.metric_kind for r in results}

    assert "mmlu" in ids
    assert "humaneval" in ids
    assert kinds["humaneval"] == MetricKind.PASS_AT_K


def test_helm_source_emits_safety_and_capability_signals():
    source = HELMSource(_cfg("helm", MetricKind.SCORE))
    results = source.get_results("claude-opus-4.5")
    ids = {r.benchmark_id for r in results}

    assert {"mmlupro", "gpqa", "toxicity", "bias"}.issubset(ids)


def test_opencompass_source_supports_long_context_and_agents():
    source = OpenCompassSource(_cfg("opencompass", MetricKind.SCORE))
    results = source.get_results("gemini-2.5-pro")
    ids = {r.benchmark_id for r in results}

    assert {"longbench", "needlebench", "agentbench", "mtbench"}.issubset(ids)


def test_slm_bench_source_reads_edge_metrics():
    source = SLMBenchSource(_cfg("slm_bench", MetricKind.SCORE))
    results = source.get_results("qwen2.5-7b-instruct")
    ids = {r.benchmark_id for r in results}

    assert {"edgejson", "edgeintent", "edgefunccall", "smolworldcup"}.issubset(ids)
