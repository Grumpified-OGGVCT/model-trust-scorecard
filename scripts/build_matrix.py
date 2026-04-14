#!/usr/bin/env python3
"""
Build a GitHub Actions matrix of models by combining:
  1) Live Ollama Cloud model pool (optional, via OLLAMA_API_KEY)
  2) Local catalog models/ directory
  3) Optional overrides from --extra-models

Outputs a JSON list suitable for `matrix: ${{ fromJson(...) }}`.

This script is resilient: if Ollama is unreachable or the secret is absent,
it falls back to catalog-only.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from collections.abc import Iterable
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)
# Ollama inventory parsing patterns.
OLLAMA_LIST_HEADER_RE = re.compile(r"^NAME\s+ID\s+SIZE\s+MODIFIED$", re.IGNORECASE)
OLLAMA_COLUMN_SPLIT_RE = re.compile(r"\s{2,}")  # `ollama list` uses 2+ spaces between columns.
POWERSHELL_OLLAMA_LIST_RE = re.compile(r"^PS .+>\s+ollama\s+list$", re.IGNORECASE)


def load_catalog_models(models_dir: Path) -> list[str]:
    """Return model IDs from local catalog JSON files."""
    ids: list[str] = []
    # Keep ordering deterministic so matrix output and tests stay stable across platforms.
    for path in sorted(models_dir.glob("*.json")):
        ids.append(path.stem)
    return ids


def parse_inventory_models(text: str) -> list[str]:
    """Parse model IDs from plain lists, raw `ollama list`, or categorized Markdown."""
    models: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if POWERSHELL_OLLAMA_LIST_RE.match(line) or OLLAMA_LIST_HEADER_RE.match(line):
            continue

        columns = OLLAMA_COLUMN_SPLIT_RE.split(line)
        candidate = columns[0] if columns else line

        if " " in candidate:
            models.extend(parse_markdown_inventory_line(line))
            continue

        models.append(candidate)
    return models


def load_inventory_models(inventory_files: list[str]) -> list[str]:
    """Load model IDs from one or more inventory files or stdin."""
    models: list[str] = []
    for inventory_file in inventory_files:
        text = sys.stdin.read() if inventory_file == "-" else Path(inventory_file).read_text()
        models.extend(parse_inventory_models(text))
    return models


def parse_markdown_inventory_line(line: str) -> list[str]:
    """
    Parse model IDs from Markdown bullets such as:
    "- qwen3-embedding:0.6b / 4b - description".
    """
    stripped = re.sub(r"^[#>*-]\s*", "", line)
    stripped = stripped.replace("**", "").replace("__", "").replace("`", "")
    stripped = stripped.split(" - ", 1)[0].strip()
    if not stripped:
        return []

    segments = re.split(r"\s+/\s+", stripped) if "/" in stripped else [stripped]
    models: list[str] = []
    base_prefix: str | None = None
    for segment in segments:
        segment = segment.strip()
        if not segment:
            continue
        if ":" in segment:
            clean_segment = segment.split()[0]
            models.append(clean_segment)
            base_prefix = clean_segment.split(":", 1)[0]
        elif base_prefix:
            models.append(f"{base_prefix}:{segment.split()[0]}")
    return models


def candidate_model_ids(model_id: str) -> list[str]:
    """Return exact and normalized variants that may map to a catalog model ID."""
    candidates = [model_id]
    if model_id.endswith(":latest"):
        candidates.append(model_id.removesuffix(":latest"))
    if model_id.endswith(":cloud"):
        candidates.append(model_id.removesuffix(":cloud"))
    if model_id.endswith("-cloud"):
        candidates.append(model_id.removesuffix("-cloud"))
    return dedupe_preserve_order(candidates)


def prioritize_catalog_models(
    catalog_ids: list[str],
    requested_ids: Iterable[str],
    max_items: int | None = None,
) -> tuple[list[str], list[str]]:
    """Keep catalog-backed model IDs first and return skipped non-catalog IDs."""
    catalog_set = set(catalog_ids)
    prioritized: list[str] = []
    skipped: list[str] = []
    for requested_id in requested_ids:
        match = next(
            (candidate for candidate in candidate_model_ids(requested_id) if candidate in catalog_set),
            None,
        )
        if match:
            prioritized.append(match)
        else:
            skipped.append(requested_id)
    prioritized = dedupe_preserve_order(prioritized)
    skipped = dedupe_preserve_order(skipped)
    remaining_catalog = [mid for mid in catalog_ids if mid not in prioritized]
    combined = dedupe_preserve_order([*prioritized, *remaining_catalog], max_items=max_items)
    return combined, skipped


def fetch_ollama_models(
    api_key: str | None,
    base_url: str,
    endpoint: str,
    timeout: int = 10,
) -> list[str]:
    """Fetch available Ollama Cloud models; return empty list on failure."""
    if not api_key:
        logger.info("No OLLAMA_API_KEY provided; skipping Ollama fetch")
        return []

    url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Ollama fetch failed: %s", exc)
        return []

    models: list[str] = []
    # Support both {"models": [...]} and direct list payloads
    payload = data.get("models") if isinstance(data, dict) else data
    if isinstance(payload, list):
        for entry in payload:
            if isinstance(entry, str):
                models.append(entry)
            elif isinstance(entry, dict):
                mid = entry.get("name") or entry.get("model")
                if mid:
                    models.append(str(mid))
    logger.info("Fetched %d models from Ollama", len(models))
    return models


def dedupe_preserve_order(items: Iterable[str], max_items: int | None = None) -> list[str]:
    seen = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
        if max_items and len(result) >= max_items:
            break
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Build dynamic matrix list of models")
    parser.add_argument("--models-dir", type=Path, default=Path("models"), help="Catalog directory")
    parser.add_argument("--output", type=Path, default=Path("matrix.json"), help="Output JSON file")
    parser.add_argument("--extra-models", nargs="*", default=[], help="Additional model IDs to include")
    parser.add_argument(
        "--inventory-file",
        action="append",
        default=[],
        help=(
            "Path to a text file (or '-' for stdin) containing one model per line, raw `ollama list`, "
            "or categorized Markdown with model names"
        ),
    )
    parser.add_argument("--max-models", type=int, default=50, help="Safety cap on total models")
    parser.add_argument(
        "--ollama-base",
        default=os.getenv("OLLAMA_API_BASE", "https://api.ollama.ai"),
        help="Base URL for Ollama Cloud API",
    )
    parser.add_argument(
        "--ollama-endpoint",
        default=os.getenv("OLLAMA_MODELS_ENDPOINT", "/v1/models"),
        help="Endpoint for listing models",
    )
    args = parser.parse_args()

    catalog_ids = load_catalog_models(args.models_dir)
    inventory_ids = load_inventory_models(args.inventory_file)
    ollama_ids = fetch_ollama_models(
        api_key=os.getenv("OLLAMA_API_KEY"),
        base_url=args.ollama_base,
        endpoint=args.ollama_endpoint,
    )

    combined, skipped = prioritize_catalog_models(
        catalog_ids,
        [*args.extra_models, *inventory_ids, *ollama_ids],
        max_items=args.max_models,
    )
    if skipped:
        logger.info(
            "Skipped %d requested model(s) not present in the catalog: %s",
            len(skipped),
            ", ".join(skipped[:10]) + (" ..." if len(skipped) > 10 else ""),
        )

    if not combined:
        logger.error("No models discovered; nothing to emit")
        return 1

    args.output.write_text(json.dumps(combined))
    logger.info("Wrote matrix with %d model(s) to %s", len(combined), args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
