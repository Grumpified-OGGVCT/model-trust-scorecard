"""
Reporting helpers for local artifacts, markdown summaries, and dashboard HTML.
"""

from __future__ import annotations

import json
from html import escape
from pathlib import Path

from trust_scorecard.models import BenchmarkResult, ModelEvaluation


def build_status_summary(
    *,
    total_claims: int,
    verified_count: int,
    refuted_count: int,
    unverifiable_count: int,
    pending_count: int = 0,
) -> str:
    """Return a compact human-readable verification summary."""
    if total_claims == 0:
        return "No claims extracted"

    parts: list[str] = []
    if verified_count:
        parts.append(f"{verified_count} verified")
    if refuted_count:
        parts.append(f"{refuted_count} refuted")
    if unverifiable_count:
        parts.append(f"{unverifiable_count} unverifiable")
    if pending_count:
        parts.append(f"{pending_count} pending")

    return ", ".join(parts) if parts else "No verification outcomes"


def _serialize_benchmark_results(results: list[BenchmarkResult]) -> list[dict]:
    serialized = []
    for result in sorted(results, key=lambda item: (item.benchmark_id, item.value)):
        serialized.append({
            "benchmark_id": result.benchmark_id,
            "value": result.value,
            "source_url": result.source_url,
        })
    return serialized


def _normalize_benchmark_name(name: str) -> str:
    return name.lower().replace(" ", "").replace("-", "").replace("_", "")


def _build_benchmark_knowledge(
    benchmark_results: list[dict],
    claim_details: list[dict],
    *,
    verified_count: int,
    refuted_count: int,
    unverifiable_count: int,
) -> dict:
    all_claim_norms = {
        _normalize_benchmark_name(str(claim.get("metric", "")))
        for claim in claim_details
        if claim.get("metric")
    }
    comparable_claim_norms = {
        _normalize_benchmark_name(str(claim.get("metric", "")))
        for claim in claim_details
        if claim.get("metric") and claim.get("official_value") is not None
    }

    comparable_results = [
        result for result in benchmark_results
        if _normalize_benchmark_name(result["benchmark_id"]) in comparable_claim_norms
    ]
    unclaimed_results = [
        result for result in benchmark_results
        if _normalize_benchmark_name(result["benchmark_id"]) not in all_claim_norms
    ]
    claims_without_data = [
        claim for claim in claim_details
        if claim.get("official_value") is None
    ]

    facts = [
        f"Independent sources contain {len(benchmark_results)} benchmark row(s) for this model."
        if benchmark_results
        else "No independent benchmark rows were found for this model in the current source set.",
        f"We can directly compare {len(comparable_results)} extracted claim(s) against official benchmark rows."
        if comparable_results
        else "None of the extracted claims can be directly checked against an official benchmark row yet.",
    ]

    comparisons: list[str] = []
    if verified_count:
        comparisons.append(f"{verified_count} claim(s) line up with official benchmark data.")
    if refuted_count:
        comparisons.append(f"{refuted_count} claim(s) conflict with official benchmark data.")
    if not comparisons:
        comparisons.append("No claim-to-benchmark comparisons have been confirmed yet.")

    gaps: list[str] = []
    if claims_without_data:
        gaps.append(
            f"{len(claims_without_data)} extracted claim(s) still lack a matching official benchmark row."
        )
    if unclaimed_results:
        gaps.append(
            f"{len(unclaimed_results)} benchmark row(s) are known for this model but were not part of the extracted claims."
        )
    if not gaps and not benchmark_results:
        gaps.append("The current benchmark sources do not expose any rows for this model yet.")
    elif not gaps and unverifiable_count == 0:
        gaps.append("Current benchmark coverage is good for the claims we extracted.")

    return {
        "facts": facts,
        "comparisons": comparisons,
        "gaps": gaps,
        "comparable_benchmarks": comparable_results,
        "unclaimed_benchmarks": unclaimed_results,
        "claims_without_data": claims_without_data,
    }


def summarize_evaluation(evaluation: ModelEvaluation) -> dict:
    """Convert a model evaluation into a dashboard-ready summary row."""
    verified_count = sum(1 for outcome in evaluation.outcomes if outcome.status.value == "verified")
    refuted_count = sum(1 for outcome in evaluation.outcomes if outcome.status.value == "refuted")
    unverifiable_count = sum(1 for outcome in evaluation.outcomes if outcome.status.value == "unverifiable")
    pending_count = sum(1 for outcome in evaluation.outcomes if outcome.status.value == "pending")
    total_claims = len(evaluation.claims)
    breakdown = evaluation.trust_score.breakdown.model_dump(mode="json") if evaluation.trust_score else {}

    return {
        "model_id": evaluation.model_id,
        "display_name": evaluation.card.display_name,
        "vendor": evaluation.card.vendor,
        "trust_score": evaluation.trust_score.score if evaluation.trust_score else None,
        "breakdown": breakdown,
        "use_case_scores": breakdown.get("use_case_scores", {}),
        "total_claims": total_claims,
        "verified_count": verified_count,
        "refuted_count": refuted_count,
        "unverifiable_count": unverifiable_count,
        "pending_count": pending_count,
        "status_summary": build_status_summary(
            total_claims=total_claims,
            verified_count=verified_count,
            refuted_count=refuted_count,
            unverifiable_count=unverifiable_count,
            pending_count=pending_count,
        ),
        "license": evaluation.card.license_kind.value,
        "evaluated_at": evaluation.evaluated_at.isoformat(),
        "benchmark_results": _serialize_benchmark_results(evaluation.benchmark_results),
        "claim_details": [
            {
                "metric": outcome.claim.metric,
                "claimed_value": outcome.claim.value,
                "status": outcome.status.value,
                "official_value": outcome.official_value,
                "delta": outcome.delta,
                "notes": outcome.notes,
                "source_url": outcome.claim.source_url,
            }
            for outcome in evaluation.outcomes
        ],
        "benchmark_knowledge": _build_benchmark_knowledge(
            _serialize_benchmark_results(evaluation.benchmark_results),
            [
                {
                    "metric": outcome.claim.metric,
                    "claimed_value": outcome.claim.value,
                    "status": outcome.status.value,
                    "official_value": outcome.official_value,
                    "delta": outcome.delta,
                    "notes": outcome.notes,
                    "source_url": outcome.claim.source_url,
                }
                for outcome in evaluation.outcomes
            ],
            verified_count=verified_count,
            refuted_count=refuted_count,
            unverifiable_count=unverifiable_count,
        ),
    }


def summarize_report(report: dict) -> dict:
    """Normalize a verification report JSON payload into a summary row."""
    claims = report.get("claims", [])
    breakdown = report.get("breakdown") or {}
    verified_count = report.get("verified_count", 0)
    refuted_count = report.get("refuted_count", 0)
    unverifiable_count = report.get("unverifiable_count", 0)
    pending_count = report.get("pending_count", 0)

    return {
        "model_id": report["model_id"],
        "display_name": report["display_name"],
        "vendor": report.get("vendor"),
        "trust_score": report.get("trust_score"),
        "breakdown": breakdown,
        "use_case_scores": breakdown.get("use_case_scores", report.get("use_case_scores", {})),
        "total_claims": len(claims),
        "verified_count": verified_count,
        "refuted_count": refuted_count,
        "unverifiable_count": unverifiable_count,
        "pending_count": pending_count,
        "status_summary": build_status_summary(
            total_claims=len(claims),
            verified_count=verified_count,
            refuted_count=refuted_count,
            unverifiable_count=unverifiable_count,
            pending_count=pending_count,
        ),
        "license": report.get("license", "unknown"),
        "evaluated_at": report.get("evaluated_at"),
        "benchmark_results": [
            {
                "benchmark_id": item["benchmark_id"],
                "value": item["value"],
                "source_url": item.get("source_url"),
            }
            for item in report.get("benchmark_results", [])
        ],
        "claim_details": [
            {
                "metric": item.get("claim", {}).get("metric", item.get("metric", "Unknown benchmark")),
                "claimed_value": item.get("claim", {}).get("value", item.get("claimed_value")),
                "status": item.get("status"),
                "official_value": item.get("official_value"),
                "delta": item.get("delta"),
                "notes": item.get("notes", ""),
                "source_url": item.get("claim", {}).get("source_url", item.get("source_url")),
            }
            for item in report.get("outcomes", [])
        ],
        "benchmark_knowledge": _build_benchmark_knowledge(
            [
                {
                    "benchmark_id": item["benchmark_id"],
                    "value": item["value"],
                    "source_url": item.get("source_url"),
                }
                for item in report.get("benchmark_results", [])
            ],
            [
                {
                    "metric": item.get("claim", {}).get("metric", item.get("metric", "Unknown benchmark")),
                    "claimed_value": item.get("claim", {}).get("value", item.get("claimed_value")),
                    "status": item.get("status"),
                    "official_value": item.get("official_value"),
                    "delta": item.get("delta"),
                    "notes": item.get("notes", ""),
                    "source_url": item.get("claim", {}).get("source_url", item.get("source_url")),
                }
                for item in report.get("outcomes", [])
            ],
            verified_count=verified_count,
            refuted_count=refuted_count,
            unverifiable_count=unverifiable_count,
        ),
    }


def aggregate_summaries(summaries: list[dict]) -> dict:
    """Build the aggregated scoreboard payload."""
    sorted_scores = sorted(
        summaries,
        key=lambda item: item["trust_score"] if item["trust_score"] is not None else 0.0,
        reverse=True,
    )

    generated_at = max(
        (item["evaluated_at"] for item in sorted_scores if item.get("evaluated_at")),
        default=None,
    )

    return {
        "generated_at": generated_at,
        "total_models": len(sorted_scores),
        "scores": sorted_scores,
    }


def generate_markdown_table(scores: list[dict]) -> str:
    """Generate a markdown rankings table."""
    lines = [
        "# Trust Scorecard Rankings",
        "",
        "| Rank | Model | Vendor | Trust Score | Verified Claims | Status | License |",
        "|------|-------|--------|-------------|-----------------|--------|---------|",
    ]

    for rank, score in enumerate(scores, 1):
        trust_score = score.get("trust_score")
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
            f"{score['verified_count']}/{score['total_claims']} | {score['status_summary']} | {score['license']} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "**Legend:**",
        "- 🟢 **80-100**: Highly trustworthy - most claims verified",
        "- 🟡 **60-79**: Moderately trustworthy - some claims verified",
        "- 🟠 **<60**: Low trust - few verified claims or significant gaps",
        "",
        f"*Last updated: {scores[0]['evaluated_at'] if scores else 'N/A'}*",
    ])

    return "\n".join(lines)


def _render_benchmark_list(score: dict) -> str:
    benchmark_results = score.get("benchmark_results", [])
    if not benchmark_results:
        return "<li>No independent benchmark rows found in the current source set.</li>"

    items = []
    for result in benchmark_results[:6]:
        source_label = ""
        if result.get("source_url"):
            source_label = f' <a href="{escape(result["source_url"])}" target="_blank" rel="noreferrer">source</a>'
        items.append(
            "<li><strong>{}</strong>: {:.1f}%{}</li>".format(
                escape(result["benchmark_id"]),
                result["value"],
                source_label,
            )
        )
    return "".join(items)


def _render_claim_list(score: dict) -> str:
    claim_details = score.get("claim_details", [])
    if not claim_details:
        return "<li>No extracted claims available.</li>"

    items = []
    for claim in claim_details[:6]:
        official = (
            f" → official {claim['official_value']:.1f}%"
            if claim.get("official_value") is not None
            else ""
        )
        items.append(
            "<li><strong>{}</strong>: {:.1f}% ({}){}<br><span class=\"muted\">{}</span></li>".format(
                escape(claim["metric"]),
                claim["claimed_value"],
                escape(claim["status"]),
                official,
                escape(claim.get("notes", "")),
            )
        )
    return "".join(items)


def _render_bullet_list(items: list[str]) -> str:
    return "".join(f"<li>{escape(item)}</li>" for item in items)


def _render_knowledge_snapshot(score: dict) -> str:
    knowledge = score.get("benchmark_knowledge", {})
    return f"""<div class="knowledge-section">
        <h4>What we actually know from benchmarks</h4>
        <div class="knowledge-grid">
            <div class="knowledge-card">
                <h5>Established facts</h5>
                <ul>{_render_bullet_list(knowledge.get("facts", []))}</ul>
            </div>
            <div class="knowledge-card">
                <h5>Direct comparisons</h5>
                <ul>{_render_bullet_list(knowledge.get("comparisons", []))}</ul>
            </div>
            <div class="knowledge-card">
                <h5>Remaining gaps</h5>
                <ul>{_render_bullet_list(knowledge.get("gaps", []))}</ul>
            </div>
        </div>
    </div>"""


def build_dashboard_html(aggregated: dict) -> str:
    """Render the GitHub Pages dashboard HTML."""
    scores = aggregated["scores"]
    total_models = len(scores)
    scored_values = [item["trust_score"] for item in scores if item["trust_score"] is not None]
    avg_score = (sum(scored_values) / len(scored_values)) if scored_values else 0.0
    total_claims = sum(item["total_claims"] for item in scores)
    total_verified = sum(item["verified_count"] for item in scores)
    verified_pct = (total_verified / total_claims * 100.0) if total_claims else 0.0

    rows = []
    detail_cards = []
    for rank, score in enumerate(scores, 1):
        trust_score = score.get("trust_score") or 0.0
        badge_class = (
            "score-high" if trust_score >= 80
            else "score-medium" if trust_score >= 60
            else "score-low"
        )
        use_case_scores = score.get("use_case_scores", {}) or {}
        use_case_label = ", ".join(f"{key}: {value:.1f}" for key, value in use_case_scores.items()) or "—"
        rows.append(
            f"""<tr>
                <td>{rank}</td>
                <td><strong>{escape(score['display_name'])}</strong></td>
                <td>{escape(score['vendor'] or '—')}</td>
                <td><span class="score-badge {badge_class}">{trust_score:.1f}</span></td>
                <td>{score['verified_count']}/{score['total_claims']}</td>
                <td>{escape(score['status_summary'])}</td>
                <td>{len(score.get('benchmark_results', []))}</td>
                <td>{escape(score.get('license', 'unknown'))}</td>
            </tr>"""
        )
        detail_cards.append(
            f"""<div class="detail-card">
                <h3>{rank}. {escape(score['display_name'])}</h3>
                <p><strong>Status:</strong> {escape(score['status_summary'])}</p>
                <p><strong>Use-case strengths:</strong> {escape(use_case_label)}</p>
                {_render_knowledge_snapshot(score)}
                <div class="detail-grid">
                    <div>
                        <h4>Known benchmark evidence</h4>
                        <ul>{_render_benchmark_list(score)}</ul>
                    </div>
                    <div>
                        <h4>Extracted claims</h4>
                        <ul>{_render_claim_list(score)}</ul>
                    </div>
                </div>
            </div>"""
        )

    return """<!DOCTYPE html>
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
            color: #2d3748;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 40px;
        }}
        h1 {{ margin-bottom: 10px; font-size: 2.5rem; }}
        .subtitle {{ color: #718096; margin-bottom: 32px; font-size: 1.1rem; }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 32px;
        }}
        .stat-card {{
            background: #f7fafc;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            border: 1px solid #e2e8f0;
        }}
        .stat-value {{ font-size: 2rem; font-weight: bold; color: #667eea; }}
        .stat-label {{ color: #718096; margin-top: 5px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 15px; text-align: left; border-bottom: 1px solid #e2e8f0; vertical-align: top; }}
        th {{ background: #f7fafc; font-weight: 600; color: #2d3748; }}
        tr:hover {{ background: #f7fafc; }}
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
        .detail-list {{
            display: grid;
            gap: 18px;
            margin-top: 28px;
        }}
        .detail-card {{
            background: #f7fafc;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 22px;
        }}
        .detail-card h3 {{ margin-bottom: 10px; }}
        .detail-card h4 {{ margin-bottom: 8px; }}
        .detail-card h5 {{ margin-bottom: 8px; color: #2d3748; }}
        .detail-card p, .detail-card li {{
            color: #4a5568;
            line-height: 1.6;
        }}
        .detail-card ul {{ padding-left: 18px; }}
        .knowledge-section {{
            margin-top: 16px;
            padding: 18px;
            background: white;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
        }}
        .knowledge-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 14px;
            margin-top: 12px;
        }}
        .knowledge-card {{
            background: #f7fafc;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 14px;
        }}
        .detail-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 18px;
            margin-top: 14px;
        }}
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
        .info-card h3 {{ margin-bottom: 10px; }}
        .info-card p, .info-card li {{
            color: #4a5568;
            line-height: 1.65;
        }}
        .info-card ul {{ padding-left: 18px; }}
        .muted {{ color: #718096; }}
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
        .github-link:hover {{ text-decoration: underline; }}
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
                    <th>Model</th>
                    <th>Vendor</th>
                    <th>Trust Score</th>
                    <th>Verified</th>
                    <th>Status</th>
                    <th>Known Benchmark Rows</th>
                    <th>License</th>
                </tr>
            </thead>
            <tbody>
                {table_rows}
            </tbody>
        </table>

        <h2 style="margin: 28px 0 16px; color: #2d3748;">Model details</h2>
        <div class="detail-list">
            {detail_cards}
        </div>

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
                    <li>Local <code>score</code>/<code>batch</code> runs refresh <code>trust_scores.json</code>, <code>trust_scores.md</code>, and <code>docs/index.html</code>.</li>
                </ul>
            </div>
        </div>

        <div class="footer">
            <p>Last updated: {updated_at}</p>
            <p style="margin-top: 10px;">
                <a href="https://github.com/Grumpified-OGGVCT/model-trust-scorecard" class="github-link">View on GitHub</a> |
                <a href="https://github.com/Grumpified-OGGVCT/model-trust-scorecard#how-it-works" class="github-link">Methodology</a> |
                <a href="https://github.com/Grumpified-OGGVCT/model-trust-scorecard/issues/new?template=model_submission.yml" class="github-link">Submit model</a>
            </p>
        </div>
    </div>
</body>
</html>
""".format(
        total_models=total_models,
        avg_score=avg_score,
        total_claims=total_claims,
        verified_pct=verified_pct,
        table_rows="\n".join(rows),
        detail_cards="\n".join(detail_cards) if detail_cards else "<p>No model details available.</p>",
        updated_at=aggregated.get("generated_at") or "N/A",
    )


def write_local_artifacts(
    evaluations: list[ModelEvaluation],
    *,
    json_path: str | Path = "trust_scores.json",
    markdown_path: str | Path = "trust_scores.md",
    html_path: str | Path = "docs/index.html",
) -> dict:
    """Write the standard local scoreboard artifacts."""
    aggregated = aggregate_summaries([summarize_evaluation(evaluation) for evaluation in evaluations])

    json_output = Path(json_path)
    markdown_output = Path(markdown_path)
    html_output = Path(html_path)

    json_output.write_text(json.dumps(aggregated, indent=2))
    markdown_output.write_text(generate_markdown_table(aggregated["scores"]))
    html_output.parent.mkdir(parents=True, exist_ok=True)
    html_output.write_text(build_dashboard_html(aggregated))

    return aggregated
