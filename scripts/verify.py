#!/usr/bin/env python3
"""
Verify claims for a single model and output detailed JSON report.

Usage:
  python scripts/verify.py --model-id gpt-4.1 --output reports/gpt-4.1.json
"""

import argparse
import json
import logging
from pathlib import Path

from trust_scorecard.benchmark_sources import get_default_sources
from trust_scorecard.persistence import EvaluationStore
from trust_scorecard.pipeline import EvaluationPipeline, load_model_card_from_json

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Verify claims for a single model")
    parser.add_argument("--model-id", required=True, help="Model ID to evaluate")
    parser.add_argument(
        "--models-dir",
        type=Path,
        default=Path("models"),
        help="Directory containing model JSON files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output JSON file for verification report",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=2.0,
        help="Verification tolerance (percentage points)",
    )
    args = parser.parse_args()

    # Load model card
    model_file = args.models_dir / f"{args.model_id}.json"
    if not model_file.exists():
        logger.error(f"Model not found: {model_file}")
        return 1

    model_card = load_model_card_from_json(model_file)
    logger.info(f"Loaded model card: {model_card.display_name}")

    # Set up pipeline
    sources = get_default_sources()
    store = EvaluationStore(":memory:")  # Don't persist during CI
    pipeline = EvaluationPipeline(sources, store, args.tolerance)

    # Run evaluation
    evaluation = pipeline.evaluate_model(model_card)

    # Prepare report
    report = {
        "model_id": evaluation.model_id,
        "display_name": evaluation.card.display_name,
        "vendor": evaluation.card.vendor,
        "evaluated_at": evaluation.evaluated_at.isoformat(),
        "trust_score": evaluation.trust_score.score if evaluation.trust_score else None,
        "breakdown": evaluation.trust_score.breakdown.model_dump(mode="json") if evaluation.trust_score else None,
        "use_case_scores": evaluation.trust_score.breakdown.use_case_scores if evaluation.trust_score else {},
        "claims": [c.model_dump(mode="json") for c in evaluation.claims],
        "outcomes": [o.model_dump(mode="json") for o in evaluation.outcomes],
        "verified_count": sum(1 for o in evaluation.outcomes if o.status.value == "verified"),
        "refuted_count": sum(1 for o in evaluation.outcomes if o.status.value == "refuted"),
        "unverifiable_count": sum(1 for o in evaluation.outcomes if o.status.value == "unverifiable"),
    }

    # Write output
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2))
    logger.info(f"Wrote verification report to {args.output}")
    trust_score = report["trust_score"]
    logger.info(
        "Trust score: %s",
        f"{trust_score:.1f}/100" if trust_score is not None else "N/A",
    )

    return 0


if __name__ == "__main__":
    exit(main())
