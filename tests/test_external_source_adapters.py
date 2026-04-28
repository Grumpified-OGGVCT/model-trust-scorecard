from trust_scorecard.benchmark_sources.artificial_analysis import ArtificialAnalysisSource
from trust_scorecard.benchmark_sources.benchlm import BenchLMSource
from trust_scorecard.models import BenchmarkConfig, MetricKind, ModelCard
from trust_scorecard.source_evidence import summarize_source_evidence


def _config(source_id: str) -> BenchmarkConfig:
    return BenchmarkConfig(
        id=source_id,
        display_name=source_id,
        metric_kind=MetricKind.SCORE,
        weight_max=1.0,
        data_source="test",
        data_source_params={},
    )


def test_benchlm_source_emits_overall_and_category_rows_for_canonical_model_id():
    source = BenchLMSource(_config("benchlm"))
    source._cache = {
        "lastUpdated": "April 27, 2026",
        "mode": "provisional",
        "models": [
            {
                "rank": 12,
                "model": "Kimi 2.6",
                "creator": "Moonshot AI",
                "sourceType": "Open Weight",
                "overallScore": 85,
                "categoryScores": {
                    "agentic": 78.3,
                    "coding": 88.9,
                    "multimodalGrounded": 68.1,
                    "knowledge": 75.9,
                },
            }
        ],
    }

    results = source.get_results("kimi-k2.6-cloud")
    ids = {result.benchmark_id for result in results}

    assert "benchlm_overall" in ids
    assert "benchlm_coding" in ids
    assert "benchlm_multimodal_grounded" in ids
    assert {result.model_id for result in results} == {"kimi-k2.6-cloud"}


def test_artificial_analysis_source_emits_evaluations_runtime_and_pricing():
    source = ArtificialAnalysisSource(_config("artificial_analysis"))
    source._cache = [
        {
            "id": "kimi-2-6",
            "name": "Kimi 2.6",
            "evaluations": {
                "artificial_analysis_intelligence_index": 54,
                "livecodebench": 70.8,
            },
            "median_output_tokens_per_second": 85.0,
            "pricing": {"price_1m_input_tokens": 0.95, "price_1m_output_tokens": 4.0},
        }
    ]

    ids = {result.benchmark_id for result in source.get_results("kimi-k2.6-cloud")}

    assert "aa_intelligence_index" in ids
    assert "aa_livecodebench" in ids
    assert "aa_output_tokens_per_second" in ids
    assert "aa_price_1m_input_tokens" in ids


def test_source_evidence_summary_derives_lane_freshness_and_category_coverage():
    source = BenchLMSource(_config("benchlm"))
    source._cache = {
        "lastUpdated": "April 27, 2026",
        "mode": "provisional",
        "models": [
            {
                "rank": 12,
                "model": "Kimi 2.6",
                "overallScore": 85,
                "categoryScores": {"agentic": 78.3, "coding": 88.9, "knowledge": 75.9},
            }
        ],
    }

    metadata = summarize_source_evidence(
        ModelCard(model_id="kimi-k2.6-cloud", display_name="Kimi 2.6"),
        [],
        [],
        source.get_results("kimi-k2.6-cloud"),
    )

    assert metadata["ranking_lane"] == "provisional"
    assert metadata["primary_leaderboard_rank"] == 12
    assert metadata["primary_leaderboard_score"] == 85.0
    assert metadata["source_freshness"] == {"BenchLM": "April 27, 2026"}
    assert metadata["category_coverage"]["covered"] == 3


def test_source_evidence_summary_ignores_leaderboard_context_rows_for_other_models():
    source = BenchLMSource(_config("benchlm"))
    source._cache = {
        "lastUpdated": "April 27, 2026",
        "mode": "provisional",
        "models": [
            {"rank": 1, "model": "Other Model", "overallScore": 99, "categoryScores": {"coding": 99}},
            {"rank": 12, "model": "Kimi 2.6", "overallScore": 85, "categoryScores": {"coding": 88.9}},
        ],
    }
    target_rows = source.get_results("kimi-k2.6-cloud")
    context_rows = source.get_all_results()

    metadata = summarize_source_evidence(
        ModelCard(model_id="kimi-k2.6-cloud", display_name="Kimi 2.6"),
        [],
        [],
        [*target_rows, *context_rows],
    )

    assert metadata["primary_leaderboard_rank"] == 12
    assert metadata["primary_leaderboard_score"] == 85.0


def test_benchlm_source_does_not_collapse_reasoning_variant_into_base_model():
    source = BenchLMSource(_config("benchlm"))
    source._cache = {
        "lastUpdated": "April 27, 2026",
        "mode": "provisional",
        "models": [
            {"rank": 25, "model": "Kimi K2.5 (Reasoning)", "overallScore": 77, "categoryScores": {}},
            {"rank": 43, "model": "Kimi K2.5", "overallScore": 64, "categoryScores": {}},
        ],
    }

    overall_scores = [
        result.value for result in source.get_results("kimi-k2.5-cloud")
        if result.benchmark_id == "benchlm_overall"
    ]

    assert overall_scores == [64.0]