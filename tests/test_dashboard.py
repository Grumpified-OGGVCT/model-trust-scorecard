from scripts.generate_dashboard import (
    HTML_TEMPLATE,
    _capabilities_from_tags,
    _format_hallucination,
    _format_price,
    _format_release_date,
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


def test_dashboard_describes_capability_first_ordering():
    assert "Model Capability Rankings" in HTML_TEMPLATE
    assert "Models are ordered by demonstrated capabilities" in HTML_TEMPLATE
    assert "Trust score is informational" in HTML_TEMPLATE
