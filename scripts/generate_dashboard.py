#!/usr/bin/env python3
"""
Generate static HTML dashboard from trust_scores.json.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from trust_scorecard.reporting import build_dashboard_html

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate dashboard HTML")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("trust_scores.json"),
        help="Input JSON file with aggregated scores",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/index.html"),
        help="Output HTML file for GitHub Pages",
    )
    args = parser.parse_args()

    aggregated = json.loads(args.input.read_text())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build_dashboard_html(aggregated))
    logger.info("Generated dashboard at %s", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
