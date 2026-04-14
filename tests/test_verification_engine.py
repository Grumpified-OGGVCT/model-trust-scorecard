"""Tests for verification engine."""

import pytest

from trust_scorecard.models import (
    BenchmarkResult,
    Claim,
    MetricKind,
    VerificationStatus,
)
from trust_scorecard.verification_engine import VerificationEngine


@pytest.fixture
def sample_benchmark_results():
    """Sample benchmark results for testing."""
    return [
        BenchmarkResult(
            benchmark_id="swe_bench_verified",
            model_id="gpt-4.1",
            metric_kind=MetricKind.PERCENT_RESOLVED,
            value=85.0,
        ),
        BenchmarkResult(
            benchmark_id="mmlu",
            model_id="gpt-4.1",
            metric_kind=MetricKind.ACCURACY,
            value=88.0,
        ),
    ]


def test_verify_claim_exact_match(sample_benchmark_results):
    """Test verification with exact match."""
    engine = VerificationEngine(sample_benchmark_results)

    claim = Claim(
        metric="SWE-bench Verified",
        value=85.0,
        raw="85.0% on SWE-bench Verified",
    )

    outcome = engine.verify_claim("gpt-4.1", claim)

    assert outcome.status == VerificationStatus.VERIFIED
    assert outcome.official_value == 85.0
    assert outcome.delta == 0.0


def test_verify_claim_within_tolerance(sample_benchmark_results):
    """Test verification within tolerance."""
    engine = VerificationEngine(sample_benchmark_results, default_tolerance=2.0)

    claim = Claim(
        metric="SWE-bench Verified",
        value=86.5,  # 1.5% higher
        raw="86.5% on SWE-bench Verified",
    )

    outcome = engine.verify_claim("gpt-4.1", claim)

    assert outcome.status == VerificationStatus.VERIFIED
    assert outcome.delta == 1.5


def test_verify_claim_outside_tolerance(sample_benchmark_results):
    """Test verification outside tolerance."""
    engine = VerificationEngine(sample_benchmark_results, default_tolerance=2.0)

    claim = Claim(
        metric="SWE-bench Verified",
        value=90.0,  # 5% higher
        raw="90.0% on SWE-bench Verified",
    )

    outcome = engine.verify_claim("gpt-4.1", claim)

    assert outcome.status == VerificationStatus.REFUTED
    assert outcome.delta == 5.0


def test_verify_claim_unverifiable(sample_benchmark_results):
    """Test unverifiable claim (no official data)."""
    engine = VerificationEngine(sample_benchmark_results)

    claim = Claim(
        metric="Unknown Benchmark",
        value=95.0,
        raw="95.0% on Unknown Benchmark",
    )

    outcome = engine.verify_claim("gpt-4.1", claim)

    assert outcome.status == VerificationStatus.UNVERIFIABLE
    assert outcome.official_value is None


def test_verify_all_claims(sample_benchmark_results):
    """Test batch verification."""
    engine = VerificationEngine(sample_benchmark_results)

    claims = [
        Claim(metric="SWE-bench Verified", value=85.0, raw="85.0%"),
        Claim(metric="MMLU", value=88.0, raw="88.0%"),
        Claim(metric="Unknown", value=90.0, raw="90.0%"),
    ]

    outcomes = engine.verify_all("gpt-4.1", claims)

    assert len(outcomes) == 3
    assert outcomes[0].status == VerificationStatus.VERIFIED
    assert outcomes[1].status == VerificationStatus.VERIFIED
    assert outcomes[2].status == VerificationStatus.UNVERIFIABLE
