from pathlib import Path

from trust_scorecard.models import (
    BenchmarkResult,
    Claim,
    LicenseKind,
    MetricKind,
    ModelCard,
    ModelEvaluation,
    TrustScore,
    TrustScoreBreakdown,
    VerificationOutcome,
    VerificationStatus,
)
from trust_scorecard.reporting import (
    aggregate_summaries,
    build_dashboard_html,
    build_status_summary,
    summarize_evaluation,
    summarize_report,
    write_local_artifacts,
)


def sample_evaluation() -> ModelEvaluation:
    card = ModelCard(
        model_id="deepseek-v3.2-cloud",
        display_name="DeepSeek V3.2 Cloud",
        vendor="DeepSeek",
        license_kind=LicenseKind.PROPRIETARY,
    )
    claim = Claim(
        metric="SWE-bench Verified",
        value=31.5,
        raw="31.5% on SWE-bench Verified",
        source_url="https://example.com/card",
    )
    benchmark = BenchmarkResult(
        benchmark_id="swe_bench_verified",
        model_id="deepseek-v3.2-cloud",
        metric_kind=MetricKind.PERCENT_RESOLVED,
        value=30.9,
        source_url="https://example.com/leaderboard",
    )
    extra_benchmark = BenchmarkResult(
        benchmark_id="mmlu",
        model_id="deepseek-v3.2-cloud",
        metric_kind=MetricKind.ACCURACY,
        value=74.2,
        source_url="https://example.com/mmlu",
    )
    outcome = VerificationOutcome(
        claim=claim,
        status=VerificationStatus.VERIFIED,
        official_value=30.9,
        delta=0.6,
        benchmark_result=benchmark,
        notes="Claim matches official value within ±2.0%",
    )
    trust_score = TrustScore(
        model_id=card.model_id,
        score=43.7,
        breakdown=TrustScoreBreakdown(
            coverage_score=12.0,
            verification_score=20.0,
            performance_gap_score=4.7,
            openness_score=2.0,
            safety_score=5.0,
            use_case_scores={"coding": 82.0},
        ),
    )
    return ModelEvaluation(
        model_id=card.model_id,
        card=card,
        claims=[claim],
        outcomes=[outcome],
        benchmark_results=[benchmark, extra_benchmark],
        trust_score=trust_score,
    )


def test_status_summary():
    assert build_status_summary(
        total_claims=3,
        verified_count=1,
        refuted_count=1,
        unverifiable_count=1,
        pending_count=0,
    ) == "1 verified, 1 refuted, 1 unverifiable"


def test_summarize_evaluation_includes_benchmark_evidence():
    summary = summarize_evaluation(sample_evaluation())

    assert summary["status_summary"] == "1 verified"
    assert summary["benchmark_results"][0]["benchmark_id"] == "mmlu"
    assert summary["claim_details"][0]["official_value"] == 30.9
    assert summary["benchmark_knowledge"]["unclaimed_benchmarks"][0]["benchmark_id"] == "mmlu"


def test_summarize_report_round_trips_verify_shape():
    summary = summarize_report({
        "model_id": "demo-model",
        "display_name": "Demo Model",
        "vendor": "Demo",
        "license": "open",
        "evaluated_at": "2026-04-14T00:00:00",
        "trust_score": 17.2,
        "breakdown": {"use_case_scores": {"coding": 25.0}},
        "claims": [{"metric": "MMLU", "value": 70.0}],
        "outcomes": [
            {
                "claim": {"metric": "MMLU", "value": 70.0, "source_url": "https://example.com"},
                "status": "unverifiable",
                "official_value": None,
                "delta": None,
                "notes": "No official data found for MMLU",
            }
        ],
        "benchmark_results": [{"benchmark_id": "mmlu", "value": 69.8, "source_url": "https://example.com/mmlu"}],
        "verified_count": 0,
        "refuted_count": 0,
        "unverifiable_count": 1,
        "pending_count": 0,
    })

    assert summary["status_summary"] == "1 unverifiable"
    assert summary["benchmark_results"][0]["value"] == 69.8


def test_write_local_artifacts_creates_dashboard_files(tmp_path: Path):
    aggregated = write_local_artifacts(
        [sample_evaluation()],
        json_path=tmp_path / "trust_scores.json",
        markdown_path=tmp_path / "trust_scores.md",
        html_path=tmp_path / "docs" / "index.html",
    )

    html = (tmp_path / "docs" / "index.html").read_text()
    markdown = (tmp_path / "trust_scores.md").read_text()

    assert aggregated["total_models"] == 1
    assert "Known benchmark evidence" in html
    assert "DeepSeek V3.2 Cloud" in html
    assert "| 1 | DeepSeek V3.2 Cloud |" in markdown


def test_build_dashboard_html_renders_status_and_evidence():
    aggregated = aggregate_summaries([summarize_evaluation(sample_evaluation())])
    html = build_dashboard_html(aggregated)

    assert "1 verified" in html
    assert "swe_bench_verified" in html
    assert "What we actually know from benchmarks" in html
    assert "Established facts" in html
