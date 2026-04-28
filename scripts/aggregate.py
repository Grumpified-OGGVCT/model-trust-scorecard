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
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from trust_scorecard.ranking import CAPABILITY_CATEGORY_WEIGHTS, score_record_sort_key  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

HIGH_TRUST_THRESHOLD = 50
MEDIUM_TRUST_THRESHOLD = 30


def _numeric_trust_score(score: dict) -> float:
    value = score.get("trust_score")
    return float(value) if value is not None else 0.0


def sort_scores_by_capability(scores: list[dict]) -> list[dict]:
    """Sort scores by weighted demonstrated capability, not by static rank or trust totals."""
    return sorted(scores, key=score_record_sort_key)


def latest_evaluated_at(scores: list[dict]) -> str | None:
    """Return the latest available evaluation timestamp from score records."""
    timestamps = [
        value
        for score in scores
        for value in [score.get("evaluated_at")]
        if isinstance(value, str)
    ]
    return max(timestamps) if timestamps else None


def _strength_label(score: dict) -> str:
    use_case_scores = score.get("use_case_scores") or {}
    model_card = score.get("model_card") or {}
    leaderboard_score = score.get("primary_leaderboard_score") or model_card.get("leaderboard_score")
    labels = []
    if leaderboard_score is not None:
        source = score.get("primary_leaderboard_source") or model_card.get("leaderboard_source") or "External leaderboard"
        labels.append(f"{source} score: {float(leaderboard_score):.1f}")
    labels.extend(f"{name}: {value:.1f}" for name, value in use_case_scores.items())
    if labels:
        return ", ".join(labels)

    return "—"


def generate_markdown_table(scores: list[dict]) -> str:
    """Generate capability ranking table with trust metadata."""
    sorted_scores = sort_scores_by_capability(scores)

    lines = [
        "# Model Capability Rankings",
        "",
        "Models are ordered by independently sourced capability first, then demonstrated benchmark/use-case performance; trust score indicates confidence in model-local claims and verification status.",
        "",
        "| Rank | Model | Vendor | Lane | Category Coverage | Source Freshness | Use-Case Strengths | Trust Score | Verified Claims | License |",
        "|------|-------|--------|------|-------------------|------------------|--------------------|-------------|-----------------|---------|",
    ]

    for rank, score in enumerate(sorted_scores, 1):
        trust_score = score.get("trust_score")
        use_case_label = _strength_label(score)
        # Badge color based on score
        if trust_score is None:
            badge = "![N/A](https://img.shields.io/badge/Trust-N%2FA-lightgrey)"
        elif trust_score >= HIGH_TRUST_THRESHOLD:
            badge = f"![{trust_score:.1f}](https://img.shields.io/badge/Trust-{trust_score:.1f}-brightgreen)"
        elif trust_score >= MEDIUM_TRUST_THRESHOLD:
            badge = f"![{trust_score:.1f}](https://img.shields.io/badge/Trust-{trust_score:.1f}-yellow)"
        else:
            badge = f"![{trust_score:.1f}](https://img.shields.io/badge/Trust-{trust_score:.1f}-orange)"

        lane = score.get("ranking_lane") or "local_only"
        category_coverage = score.get("category_coverage") or {}
        category_label = f"{category_coverage.get('covered', 0)}/{category_coverage.get('total', 8)}"
        freshness = score.get("source_freshness") or {}
        freshness_label = ", ".join(f"{name}: {value}" for name, value in freshness.items()) or "—"
        lines.append(
            f"| {rank} | {score['display_name']} | {score['vendor'] or '—'} | {lane} | {category_label} | "
            f"{freshness_label} | {use_case_label} | {badge} | {score['verified_count']}/{score['total_claims']} | {score['license']} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "**Legend:**",
        "- Rank order: models with independently verified claims or external leaderboard score/rank evidence rank ahead of models with only unverified claims.",
        "- External leaderboard score/rank metadata is treated as current capability evidence when model-local benchmark claims are sparse.",
        "- Within each reliability tier, models are ranked by externally sourced or BenchLM-style weighted category capability before verification-count tie breakers.",
        "- Deployment/runtime signals are kept out of capability ranking so fast or cheap models do not outrank stronger models solely on operations metadata.",
        "- Tie-breakers: verified claim count, verification rate, trust score, evidence, capability metadata, scale/context, and name.",
        "- Partial-data models follow the fully ranked tier, and models with no evidence are placed last.",
        "- 🟢 **50-100**: Higher relative trust in the current score distribution",
        "- 🟡 **30-49**: Moderate relative trust - some claims verified or partial coverage",
        "- 🟠 **<30**: Low trust - few claims verified or significant gaps",
        "",
        f"*Last updated: {latest_evaluated_at(scores) or 'N/A'}*",
    ])

    return "\n".join(lines)


def _source_catalog(scores: list[dict]) -> list[dict]:
    catalog: dict[str, dict] = {}
    for score in scores:
        for evidence in score.get("source_evidence") or []:
            source = evidence.get("source")
            if not source:
                continue
            item = catalog.setdefault(
                source,
                {"source": source, "url": evidence.get("url"), "freshness_values": set()},
            )
            if evidence.get("url"):
                item["url"] = evidence["url"]
            if evidence.get("freshness"):
                item["freshness_values"].add(evidence["freshness"])

    output = []
    for item in catalog.values():
        freshness_values = sorted(item.pop("freshness_values"))
        item["freshness"] = freshness_values[-1] if freshness_values else None
        output.append(item)
    return sorted(output, key=lambda entry: entry["source"])


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
        model_card = report.get("model_card", {})
        license_value = report.get("license") or model_card.get("license_kind") or "unknown"
        if license_value == "unknown" and model_card.get("license_kind"):
            license_value = model_card["license_kind"]
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
            "license": license_value,
            "model_card": model_card,
            "tags": model_card.get("tags", []),
            "ranking_lane": report.get("ranking_lane"),
            "confidence_tier": report.get("confidence_tier"),
            "source_evidence": report.get("source_evidence", []),
            "source_freshness": report.get("source_freshness", {}),
            "primary_leaderboard_source": report.get("primary_leaderboard_source"),
            "primary_leaderboard_rank": report.get("primary_leaderboard_rank"),
            "primary_leaderboard_score": report.get("primary_leaderboard_score"),
            "benchlm_mode": report.get("benchlm_mode"),
            "benchlm_category_scores": report.get("benchlm_category_scores", {}),
            "artificial_analysis_scores": report.get("artificial_analysis_scores", {}),
            "category_coverage": report.get("category_coverage", {}),
            "rankable_benchmark_count": report.get("rankable_benchmark_count", 0),
            "rankable_category_count": report.get("rankable_category_count", 0),
        })

    # Write JSON
    aggregated = {
        "generated_at": latest_evaluated_at(scores),
        "total_models": len(scores),
        "source_catalog": _source_catalog(scores),
        "category_weights": CAPABILITY_CATEGORY_WEIGHTS,
        "ranking_lane_counts": dict(Counter(score.get("ranking_lane") or "unknown" for score in scores)),
        "confidence_distribution": dict(Counter(score.get("confidence_tier") or "unknown" for score in scores)),
        "snapshot_methodology_version": "benchlm-aa-source-evidence-v1",
        "scores": sort_scores_by_capability(scores),
    }
    args.output.write_text(json.dumps(aggregated, indent=2), encoding="utf-8")
    logger.info(f"Wrote aggregated scores to {args.output}")

    # Write markdown
    markdown = generate_markdown_table(scores)
    args.md.write_text(markdown, encoding="utf-8")
    logger.info(f"Wrote markdown table to {args.md}")

    return 0


if __name__ == "__main__":
    exit(main())
