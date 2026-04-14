"""Tests for scoring rubric."""

import pytest

from trust_scorecard.models import (
    Claim,
    LicenseKind,
    ModelCard,
    VerificationOutcome,
    VerificationStatus,
)
from trust_scorecard.scoring import (
    compute_coverage_score,
    compute_openness_score,
    compute_safety_score,
    compute_trust_score,
    compute_use_case_scores,
    compute_verification_score,
)


@pytest.fixture
def sample_model_card():
    """Sample model card."""
    return ModelCard(
        model_id="test-model",
        display_name="Test Model",
        license_kind=LicenseKind.OPEN,
    )


@pytest.fixture
def sample_outcomes():
    """Sample verification outcomes."""
    return [
        VerificationOutcome(
            claim=Claim(metric="SWE-bench Verified", value=85.0, raw="85.0%"),
            status=VerificationStatus.VERIFIED,
            official_value=85.0,
            delta=0.0,
        ),
        VerificationOutcome(
            claim=Claim(metric="MMLU", value=88.0, raw="88.0%"),
            status=VerificationStatus.VERIFIED,
            official_value=88.0,
            delta=0.0,
        ),
        VerificationOutcome(
            claim=Claim(metric="HumanEval", value=90.0, raw="90.0%"),
            status=VerificationStatus.UNVERIFIABLE,
        ),
    ]


def test_coverage_score(sample_outcomes):
    """Test coverage score calculation."""
    score = compute_coverage_score(sample_outcomes)
    assert 0 <= score <= 30.0
    assert score > 10.0


def test_verification_score(sample_outcomes):
    """Test verification score calculation."""
    score = compute_verification_score(sample_outcomes)
    # 2 verified out of 3 total = 66.7% * 40 = 26.7
    assert 25.0 <= score <= 27.0


def test_openness_score(sample_model_card):
    """Test openness score for open source model."""
    score = compute_openness_score(sample_model_card)
    assert score == 5.0

    # Test proprietary
    proprietary_card = ModelCard(
        model_id="test",
        display_name="Test",
        license_kind=LicenseKind.PROPRIETARY,
    )
    score = compute_openness_score(proprietary_card)
    assert score == 0.0


def test_safety_score(sample_outcomes):
    """Test safety score calculation."""
    score = compute_safety_score(sample_outcomes)
    assert 0 <= score <= 5.0


def test_compute_trust_score(sample_model_card, sample_outcomes):
    """Test overall trust score computation."""
    trust_score = compute_trust_score("test-model", sample_model_card, sample_outcomes)

    assert 0 <= trust_score.score <= 100
    assert trust_score.model_id == "test-model"
    assert trust_score.breakdown is not None
    assert trust_score.breakdown.total == trust_score.score
    assert "coding" in trust_score.breakdown.use_case_scores


def test_compute_use_case_scores(sample_outcomes):
    scores = compute_use_case_scores(sample_outcomes)
    assert scores["coding"] >= 80
    assert "reasoning" in scores
