from pathlib import Path

from scripts.build_matrix import (
    candidate_model_ids,
    load_inventory_models,
    parse_inventory_models,
    prioritize_catalog_models,
)

EXAMPLE_INVENTORY = Path("docs/examples/personal-ollama-list.txt")


def test_parse_inventory_models_from_raw_ollama_list_example():
    models = parse_inventory_models(EXAMPLE_INVENTORY.read_text())

    assert models[:3] == [
        "qwen3-embedding:0.6b",
        "qwen3-embedding:4b",
        "nomic-embed-text-v2-moe:latest",
    ]
    assert "deepseek-v3.2:cloud" in models
    assert "gemma3:27b-cloud" in models
    assert "NAME" not in models


def test_load_inventory_models_reads_example_file():
    models = load_inventory_models([str(EXAMPLE_INVENTORY)])

    assert len(models) > 50
    assert models[0] == "qwen3-embedding:0.6b"


def test_candidate_model_ids_normalize_ollama_tags():
    assert candidate_model_ids("deepseek-v3.2:cloud") == ["deepseek-v3.2:cloud", "deepseek-v3.2"]
    assert candidate_model_ids("gemini-3-flash-preview:latest") == [
        "gemini-3-flash-preview:latest",
        "gemini-3-flash-preview",
    ]
    assert candidate_model_ids("gemma3:27b-cloud") == ["gemma3:27b-cloud", "gemma3:27b"]
    assert candidate_model_ids("model-name-cloud") == ["model-name-cloud", "model-name"]


def test_prioritize_catalog_models_only_emits_supported_entries():
    combined, skipped = prioritize_catalog_models(
        catalog_ids=["gpt-4.1", "deepseek-v3.2", "claude-opus-4.5"],
        requested_ids=["qwen3:14b", "deepseek-v3.2:cloud", "gpt-4.1", "qwen3:14b"],
        max_items=3,
    )

    assert combined == ["deepseek-v3.2", "gpt-4.1", "claude-opus-4.5"]
    assert skipped == ["qwen3:14b"]
