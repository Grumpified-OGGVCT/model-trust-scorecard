from scripts.generate_dashboard import (
    _capabilities_from_tags,
    _format_hallucination,
    _format_price,
)


def test_capabilities_include_function_calling_and_expanded_tags():
    display = _capabilities_from_tags(
        ["coding", "function-calling", "video", "ocr", "document-analysis", "rag"],
        context_window=1_000_000,
    )

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
