from scripts.generate_dashboard import (
    HTML_TEMPLATE,
    _capabilities_from_tags,
    _category_from_score,
    _format_chips,
    _format_compact_number,
    _format_hallucination,
    _format_price,
    _format_release_date,
    _source_confidence,
)


def test_capabilities_include_function_calling_and_expanded_tags():
    display = _capabilities_from_tags(
        ["coding", "function-calling", "video", "ocr", "document-analysis", "rag", "audio"],
        context_window=1_000_000,
    )

    assert "Audio" in display
    assert "Tools" in display
    assert "Video" in display
    assert "OCR" in display
    assert "Docs" in display
    assert "RAG" in display
    assert "Long Context" in display


def test_dashboard_formats_pricing_and_hallucination():
    assert "$0.14 / $0.28" in _format_price(0.00014, 0.00028)
    hallucination = _format_hallucination(4.2)
    assert "4.2%" in hallucination
    assert "Low risk" in hallucination


def test_dashboard_formats_release_date():
    assert _format_release_date("2026-04-23T00:00:00") == "2026-04-23"
    assert _format_release_date(None) == "-"


def test_dashboard_formats_compact_numbers():
    assert _format_compact_number(128000) == "128K"
    assert _format_compact_number(1_000_000) == "1.0M"
    assert _format_compact_number(None) == "-"


def test_dashboard_formats_chips():
    assert _format_chips([]) == "-"
    chips = _format_chips(["Coding: 90.0", "<unsafe>"])
    assert "Coding: 90.0" in chips
    assert "&lt;unsafe&gt;" in chips


def test_dashboard_source_confidence_labels():
    assert _source_confidence(0, 0) == "Needs sources"
    assert _source_confidence(6, 3) == "Strong sourced coverage"
    assert _source_confidence(6, 1) == "Partial sourced coverage"
    assert _source_confidence(3, 0, 3) == "Claims need source mapping"
    assert _source_confidence(3, 0, 1) == "Unverified claims"


def test_dashboard_category_from_score_uses_capability_metadata():
    assert _category_from_score({"use_case_scores": {"coding": 90.0}, "tags": []}) == "coding"
    assert _category_from_score({"use_case_scores": {"reasoning": 90.0}, "tags": []}) == "reasoning"
    assert _category_from_score({"use_case_scores": {"math": 90.0}, "tags": []}) == "math"
    assert _category_from_score({"use_case_scores": {"tool_use": 90.0}, "tags": []}) == "tool-use"
    assert _category_from_score(
        {
            "use_case_scores": {},
            "tags": ["vision"],
            "model_card": {"context_window_tokens": 128000},
        }
    ) == "multimodal"
    assert _category_from_score(
        {
            "use_case_scores": {},
            "tags": ["text"],
            "model_card": {"context_window_tokens": 128000},
        }
    ) == "long-context"
    assert _category_from_score({"use_case_scores": {}, "tags": ["text"]}) == "all"


def test_dashboard_describes_reliability_first_ordering():
    assert "Model Capability Rankings" in HTML_TEMPLATE
    assert "Models are ordered by independently verified evidence first" in HTML_TEMPLATE
    assert "weighted composite of demonstrated capability" in HTML_TEMPLATE
    assert "zero-evidence models are placed last" in HTML_TEMPLATE
    assert "Leaderboard cross-check sources" in HTML_TEMPLATE
    assert "BenchLM" in HTML_TEMPLATE
    assert "Artificial Analysis" in HTML_TEMPLATE
    assert "All Benchmarks" in HTML_TEMPLATE
    assert "Source Confidence" in HTML_TEMPLATE
    assert "Claim Coverage" in HTML_TEMPLATE
    assert "providerFilter" in HTML_TEMPLATE
