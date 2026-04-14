"""Tests for claim extraction."""

from trust_scorecard.claim_extractor import extract_claims


def test_extract_swe_bench_claim():
    """Test extracting SWE-bench claim."""
    text = "Our model achieves 80.2% on SWE-bench Verified."
    claims = extract_claims(text)

    assert len(claims) == 1
    assert claims[0].metric == "SWE-bench Verified"
    assert claims[0].value == 80.2
    assert claims[0].target == "Verified"


def test_extract_mmlu_claim():
    """Test extracting MMLU claim."""
    text = "The model scores 88.7% on MMLU."
    claims = extract_claims(text)

    assert len(claims) == 1
    assert claims[0].metric == "MMLU"
    assert claims[0].value == 88.7


def test_extract_multiple_claims():
    """Test extracting multiple claims from text."""
    text = """
    Our model demonstrates strong performance:
    - 85.4% on SWE-bench Verified
    - 88.7% on MMLU
    - 92.3% on HumanEval
    - 78.2% on GPQA Diamond
    """
    claims = extract_claims(text)

    assert len(claims) >= 4
    metrics = {c.metric for c in claims}
    assert "SWE-bench Verified" in metrics or "SWE-bench" in metrics
    assert "MMLU" in metrics
    assert "HumanEval" in metrics
    assert "GPQA Diamond" in metrics or "GPQA" in metrics


def test_extract_with_different_formats():
    """Test various formatting patterns."""
    test_cases = [
        ("Achieves 90% on MMLU", "MMLU", 90.0),
        ("MMLU: 90.5%", "MMLU", 90.5),
        ("MMLU score of 90.2", "MMLU", 90.2),
        ("90.1% MMLU", "MMLU", 90.1),
    ]

    for text, _expected_metric, expected_value in test_cases:
        claims = extract_claims(text)
        assert len(claims) >= 1
        # Find the MMLU claim
        mmlu_claim = next((c for c in claims if "mmlu" in c.metric.lower()), None)
        assert mmlu_claim is not None
        assert mmlu_claim.value == expected_value


def test_deduplication():
    """Test that duplicate claims are deduplicated."""
    text = """
    Model achieves 90% on MMLU.
    It scores 90% on MMLU.
    MMLU: 90%
    """
    claims = extract_claims(text, deduplicate=True)

    mmlu_claims = [c for c in claims if "mmlu" in c.metric.lower()]
    assert len(mmlu_claims) == 1


def test_no_false_positives():
    """Test that parameter counts and token counts are not extracted as claims."""
    text = "Our 671B parameter model with 128000 token context achieves 90% on MMLU."
    claims = extract_claims(text)

    # Should not extract 671 or 128000 as benchmark scores
    values = [c.value for c in claims]
    assert 671.0 not in values
    assert 128000.0 not in values


def test_source_url_propagation():
    """Test that source URL is propagated to claims."""
    text = "Achieves 90% on MMLU"
    url = "https://example.com/model-card"
    claims = extract_claims(text, source_url=url)

    assert len(claims) >= 1
    assert all(c.source_url == url for c in claims)
