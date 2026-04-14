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
from pathlib import Path
from typing import Iterable

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def load_catalog_models(models_dir: Path) -> list[str]:
    """Return model IDs from local catalog JSON files."""
    ids: list[str] = []
    for path in models_dir.glob("*.json"):
        ids.append(path.stem)
    return ids


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
    ollama_ids = fetch_ollama_models(
        api_key=os.getenv("OLLAMA_API_KEY"),
        base_url=args.ollama_base,
        endpoint=args.ollama_endpoint,
    )

    combined = dedupe_preserve_order(
        [*ollama_ids, *catalog_ids, *args.extra_models],
        max_items=args.max_models,
    )

    if not combined:
        logger.error("No models discovered; nothing to emit")
        return 1

    args.output.write_text(json.dumps(combined))
    logger.info("Wrote matrix with %d model(s) to %s", len(combined), args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
