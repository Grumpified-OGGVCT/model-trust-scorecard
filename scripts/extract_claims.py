#!/usr/bin/env python3
"""
Extract claims from all model cards in models/ directory.

Output: claims.json with all extracted claims per model.

Usage:
  python scripts/extract_claims.py --models-dir models/ --output claims.json
"""

import argparse
import json
import logging
from pathlib import Path

from trust_scorecard.claim_extractor import extract_claims
from trust_scorecard.pipeline import load_model_cards_from_directory

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Extract claims from model catalog")
    parser.add_argument(
        "--models-dir",
        type=Path,
        default=Path("models"),
        help="Directory containing model JSON files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("claims.json"),
        help="Output JSON file for extracted claims",
    )
    args = parser.parse_args()

    # Load all model cards
    model_cards = load_model_cards_from_directory(args.models_dir)
    logger.info(f"Loaded {len(model_cards)} model cards from {args.models_dir}")

    # Extract claims from each model
    results = {}
    for card in model_cards:
        text = card.card_text or ""
        claims = extract_claims(text, source_url=card.card_url)
        results[card.model_id] = {
            "model_id": card.model_id,
            "display_name": card.display_name,
            "vendor": card.vendor,
            "claims": [c.model_dump() for c in claims],
            "claim_count": len(claims),
        }
        logger.info(f"{card.model_id}: extracted {len(claims)} claims")

    # Write output
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2))
    logger.info(f"Wrote claims to {args.output}")


if __name__ == "__main__":
    main()
