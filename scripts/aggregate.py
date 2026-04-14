#!/usr/bin/env python3
"""
Aggregate individual verification reports into trust_scores.json and trust_scores.md.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from trust_scorecard.reporting import aggregate_summaries, generate_markdown_table, summarize_report

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
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

    reports: list[dict] = []
    for report_file in args.reports_dir.glob("*.json"):
        try:
            reports.append(json.loads(report_file.read_text()))
            logger.info("Loaded %s", report_file.name)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load %s, skipping file: %s", report_file.name, exc)

    if not reports:
        logger.error("No reports found in %s", args.reports_dir)
        return 1

    aggregated = aggregate_summaries([summarize_report(report) for report in reports])
    args.output.write_text(json.dumps(aggregated, indent=2))
    logger.info("Wrote aggregated scores to %s", args.output)

    args.md.write_text(generate_markdown_table(aggregated["scores"]))
    logger.info("Wrote markdown table to %s", args.md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
