from scripts.aggregate import generate_markdown_table, latest_evaluated_at


def test_latest_evaluated_at_uses_max_timestamp():
    scores = [
        {"evaluated_at": "2026-04-26T12:57:50.057774"},
        {"evaluated_at": "2026-04-26T12:58:23.671470"},
        {"evaluated_at": None},
    ]

    assert latest_evaluated_at(scores) == "2026-04-26T12:58:23.671470"


def test_markdown_last_updated_uses_latest_timestamp():
    markdown = generate_markdown_table(
        [
            {
                "display_name": "Older",
                "vendor": "Example",
                "trust_score": 10.0,
                "use_case_scores": {},
                "verified_count": 0,
                "total_claims": 1,
                "license": "unknown",
                "evaluated_at": "2026-04-26T12:57:50.057774",
                "model_card": {"model_id": "older", "display_name": "Older"},
            },
            {
                "display_name": "Newer",
                "vendor": "Example",
                "trust_score": 10.0,
                "use_case_scores": {},
                "verified_count": 0,
                "total_claims": 1,
                "license": "unknown",
                "evaluated_at": "2026-04-26T12:58:23.671470",
                "model_card": {"model_id": "newer", "display_name": "Newer"},
            },
        ]
    )

    assert "*Last updated: 2026-04-26T12:58:23.671470*" in markdown
