#!/usr/bin/env python3
"""
Aggregate individual verification reports into final trust_scores.json and markdown table.

Input: reports/*.json (individual verification reports)
Output: trust_scores.json, trust_scores.md

Usage:
  python scripts/aggregate.py --reports-dir reports/ --output trust_scores.json --md trust_scores.md
"""

import argparse
import json
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from trust_scorecard.ranking import score_record_sort_key  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def _numeric_trust_score(score: dict) -> float:
    value = score.get("trust_score")
    return float(value) if value is not None else 0.0


def sort_scores_by_capability(scores: list[dict]) -> list[dict]:
    """Sort scores by explicit capability priority, not by trust totals."""
    return sorted(scores, key=score_record_sort_key)


def generate_markdown_table(scores: list[dict]) -> str:
    """Generate markdown badge table."""
    sorted_scores = sort_scores_by_capability(scores)

    lines = [
        "# Trust Scorecard Rankings",
        "",
        "| Rank | Model | Vendor | Trust Score | Verified Claims | License |",
        "|------|-------|--------|-------------|-----------------|---------|",
    ]

    for rank, score in enumerate(sorted_scores, 1):
        trust_score = score.get("trust_score")
        # Badge color based on score
        if trust_score is None:
            badge = "![N/A](https://img.shields.io/badge/Trust-N%2FA-lightgrey)"
        elif trust_score >= 80:
            badge = f"![{trust_score:.1f}](https://img.shields.io/badge/Trust-{trust_score:.1f}-brightgreen)"
        elif trust_score >= 60:
            badge = f"![{trust_score:.1f}](https://img.shields.io/badge/Trust-{trust_score:.1f}-yellow)"
        else:
            badge = f"![{trust_score:.1f}](https://img.shields.io/badge/Trust-{trust_score:.1f}-orange)"

        lines.append(
            f"| {rank} | {score['display_name']} | {score['vendor'] or '—'} | {badge} | "
            f"{score['verified_count']}/{score['total_claims']} | {score['license']} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "**Legend:**",
        "- 🟢 **80-100**: Highly trustworthy - most claims verified",
        "- 🟡 **60-79**: Moderately trustworthy - some claims verified",
        "- 🟠 **<60**: Low trust - few claims verified or significant gaps",
        "",
        f"*Last updated: {scores[0]['evaluated_at'] if scores else 'N/A'}*",
    ])

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Aggregate verification reports")
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=Path("reports"),
        help="Directory containing individual verification JSON reports",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("trust_scores.json"),
        help="Output JSON file with aggregated scores",
    )
    parser.add_argument(
        "--md",
        type=Path,
        default=Path("trust_scores.md"),
        help="Output markdown file with badge table",
    )
    args = parser.parse_args()

    # Load all reports
    reports = []
    for report_file in args.reports_dir.glob("*.json"):
        try:
            data = json.loads(report_file.read_text())
            reports.append(data)
            logger.info(f"Loaded {report_file.name}")
        except Exception as e:
            logger.warning(f"Failed to load {report_file.name}: {e}")

    if not reports:
        logger.error("No reports found in %s", args.reports_dir)
        return 1

    logger.info(f"Aggregating {len(reports)} reports")

    # Prepare aggregated scores
    scores = []
    for report in reports:
        breakdown = report.get("breakdown") or {}
        scores.append({
            "model_id": report["model_id"],
            "display_name": report["display_name"],
            "vendor": report.get("vendor"),
            "trust_score": report["trust_score"],
            "breakdown": breakdown,
            "use_case_scores": breakdown.get("use_case_scores", {}),
            "total_claims": len(report.get("claims", [])),
            "verified_count": report.get("verified_count", 0),
            "refuted_count": report.get("refuted_count", 0),
            "unverifiable_count": report.get("unverifiable_count", 0),
            "evaluated_at": report.get("evaluated_at"),
            "license": report.get("license", "unknown"),
            "model_card": report.get("model_card", {}),
            "tags": report.get("model_card", {}).get("tags", []),
        })

    # Write JSON
    aggregated = {
        "generated_at": reports[0]["evaluated_at"] if reports else None,
        "total_models": len(scores),
        "scores": sort_scores_by_capability(scores),
    }
    args.output.write_text(json.dumps(aggregated, indent=2))
    logger.info(f"Wrote aggregated scores to {args.output}")

    # Write markdown
    markdown = generate_markdown_table(scores)
    args.md.write_text(markdown)
    logger.info(f"Wrote markdown table to {args.md}")

    return 0


if __name__ == "__main__":
    exit(main())
