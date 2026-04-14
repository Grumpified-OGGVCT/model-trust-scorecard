#!/usr/bin/env python3
"""
Generate static HTML dashboard from trust_scores.json.

Output: docs/index.html (GitHub Pages ready)

Usage:
  python scripts/generate_dashboard.py --input trust_scores.json --output docs/index.html
"""

import argparse
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Model Trust Scorecard</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 40px;
        }}
        h1 {{
            color: #2d3748;
            margin-bottom: 10px;
            font-size: 2.5rem;
        }}
        .subtitle {{
            color: #718096;
            margin-bottom: 40px;
            font-size: 1.1rem;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        .stat-card {{
            background: #f7fafc;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }}
        .stat-value {{
            font-size: 2rem;
            font-weight: bold;
            color: #667eea;
        }}
        .stat-label {{
            color: #718096;
            margin-top: 5px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}
        th, td {{
            padding: 15px;
            text-align: left;
            border-bottom: 1px solid #e2e8f0;
        }}
        th {{
            background: #f7fafc;
            font-weight: 600;
            color: #2d3748;
        }}
        tr:hover {{
            background: #f7fafc;
        }}
        .score-badge {{
            display: inline-block;
            padding: 5px 12px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 0.9rem;
        }}
        .score-high {{ background: #48bb78; color: white; }}
        .score-medium {{ background: #ed8936; color: white; }}
        .score-low {{ background: #f56565; color: white; }}
        .info-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 18px;
            margin-top: 32px;
        }}
        .info-card {{
            background: #f7fafc;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 22px;
        }}
        .info-card h3 {{
            margin-bottom: 10px;
            color: #2d3748;
        }}
        .info-card p, .info-card li {{
            color: #4a5568;
            line-height: 1.65;
        }}
        .info-card ul {{
            padding-left: 18px;
        }}
        code {{
            background: #edf2f7;
            border-radius: 6px;
            padding: 2px 6px;
            font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
            font-size: 0.95em;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #e2e8f0;
            text-align: center;
            color: #718096;
            font-size: 0.9rem;
        }}
        .github-link {{
            color: #667eea;
            text-decoration: none;
            font-weight: 600;
        }}
        .github-link:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 Model Trust Scorecard</h1>
        <p class="subtitle">Transparent, reproducible verification of AI model benchmark claims</p>

        <div class="stats">
            <div class="stat-card">
                <div class="stat-value">{total_models}</div>
                <div class="stat-label">Models Evaluated</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{avg_score:.1f}</div>
                <div class="stat-label">Average Trust Score</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{total_claims}</div>
                <div class="stat-label">Total Claims</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{verified_pct:.0f}%</div>
                <div class="stat-label">Claims Verified</div>
            </div>
        </div>

        <h2 style="margin-bottom: 20px; color: #2d3748;">Rankings</h2>
        <table>
            <thead>
                <tr>
                    <th>Rank</th>
                    <th>Model (Vendor)</th>
                    <th>Parameters / Context</th>
                    <th>Trust Score (Verified)</th>
                    <th>Capabilities</th>
                    <th>Use-Case Strengths</th>
                    <th>License</th>
                </tr>
            </thead>
            <tbody>
                {table_rows}
            </tbody>
        </table>

        <div class="info-grid">
            <div class="info-card">
                <h3>Where results go</h3>
                <ul>
                    <li>This page is generated into <code>docs/index.html</code> for GitHub Pages.</li>
                    <li>The machine-readable aggregate is committed as <code>trust_scores.json</code>.</li>
                    <li>A markdown summary is committed as <code>trust_scores.md</code>.</li>
                    <li>Per-model verification reports are attached to the workflow run as artifacts.</li>
                </ul>
            </div>
            <div class="info-card">
                <h3>Request a review for a model not listed here</h3>
                <ul>
                    <li>Open the <a href="https://github.com/Grumpified-OGGVCT/model-trust-scorecard/issues/new?template=model_submission.yml" class="github-link">Model Submission issue</a>.</li>
                    <li>Or submit a PR that adds <code>models/&lt;model-id&gt;.json</code> to the catalog.</li>
                    <li>For one-off checks, run the CLI with pasted claims via <code>trust-scorecard score --text</code> or <code>--text-file</code>.</li>
                    <li>Raw <code>ollama list</code> inventories and categorized Markdown lists are valid input examples. Models that do not map to a catalog entry are skipped until catalog data or pasted claims are provided.</li>
                </ul>
            </div>
        </div>

        <div class="footer">
            <p>Last updated: {updated_at}</p>
            <p style="margin-top: 10px;">
                <a href="https://github.com/Grumpified-OGGVCT/model-trust-scorecard" class="github-link">
                    View on GitHub
                </a> |
                <a href="https://github.com/Grumpified-OGGVCT/model-trust-scorecard#how-it-works" class="github-link">
                    Methodology
                </a> |
                <a href="https://github.com/Grumpified-OGGVCT/model-trust-scorecard/issues/new?template=model_submission.yml" class="github-link">
                    Submit model
                </a>
            </p>
        </div>
    </div>
</body>
</html>
"""


def main():
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

    # Load scores
    data = json.loads(args.input.read_text())
    # Sort by ACTUAL CAPABILITY (use-case strength scores), not verification count
    # Primary: coding score, Secondary: reasoning score, Tertiary: trust score
    def get_capability_score(score):
        use_cases = score.get("use_case_scores", {}) or {}
        # Average of available use-case scores
        if use_cases:
            return sum(use_cases.values()) / len(use_cases)
        return score.get("trust_score") or 0
    
    scores = sorted(
        data["scores"],
        key=lambda x: get_capability_score(x),
        reverse=True
    )

    # Calculate stats (skip None values)
    total_models = len(scores)
    valid_scores = [s["trust_score"] for s in scores if s["trust_score"] is not None]
    avg_score = sum(valid_scores) / len(valid_scores) if valid_scores else 0
    total_claims = sum(s["total_claims"] for s in scores)
    total_verified = sum(s["verified_count"] for s in scores)
    verified_pct = (total_verified / total_claims * 100) if total_claims > 0 else 0

    # Generate table rows with expanded metadata
    rows = []
    for rank, score in enumerate(scores, 1):
        trust_score = score["trust_score"]
        badge_class = (
            "score-high" if trust_score and trust_score >= 80
            else "score-medium" if trust_score and trust_score >= 60
            else "score-low"
        )
        score_display = f"{trust_score:.1f}" if trust_score is not None else "N/A"
        use_case_scores = score.get("use_case_scores", {}) or {}
        use_case_label = ", ".join(f"{k}: {v:.1f}" for k, v in use_case_scores.items()) or "—"
        
        # Extract metadata from model card
        model_card = score.get("model_card", {})
        params = model_card.get("parameter_count_billions")
        params_display = f"{params}B" if params else "—"
        
        ctx = model_card.get("context_window_tokens")
        ctx_display = f"{ctx // 1000}K" if ctx else "—"
        
        # Build capability tags string
        tags = score.get("tags", [])
        tag_html = "".join([f'<span class="tag">{t}</span>' for t in tags[:5]]) if tags else "—"
        
        # Build capabilities summary
        caps = []
        if any("vision" in t for t in tags):
            caps.append("Vision")
        if any("coding" in t for t in tags):
            caps.append("Code")
        if any("tool" in t for t in tags):
            caps.append("Tools")
        if any("agentic" in t for t in tags):
            caps.append("Agent")
        if any("multilingual" in t for t in tags):
            caps.append("Multi-Lang")
        caps_display = " • ".join(caps) if caps else "—"
        
        rows.append(
            f"""<tr>
                <td>{rank}</td>
                <td><strong>{score['display_name']}</strong><br><span style="color:#718096; font-size:0.85em;">{score['vendor'] or '—'}</span></td>
                <td>{params_display}<br><span style="color:#718096; font-size:0.85em;">{ctx_display} ctx</span></td>
                <td><span class="score-badge {badge_class}">{score_display}</span><br><span style="color:#718096; font-size:0.85em;">{score['verified_count']}/{score['total_claims']} verified</span></td>
                <td>{caps_display}</td>
                <td>{use_case_label}</td>
                <td>{score.get('license', 'unknown')}</td>
            </tr>"""
        )

    # Generate HTML
    html = HTML_TEMPLATE.format(
        total_models=total_models,
        avg_score=avg_score,
        total_claims=total_claims,
        verified_pct=verified_pct,
        table_rows="\n".join(rows),
        updated_at=data.get("generated_at", "N/A"),
    )

    # Write output
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html)
    logger.info(f"Generated dashboard at {args.output}")

    return 0


if __name__ == "__main__":
    exit(main())
