#!/usr/bin/env python3
"""
Generate static HTML dashboard from trust_scores.json.

Output: docs/index.html (GitHub Pages ready)

Usage:
  python scripts/generate_dashboard.py --input trust_scores.json --output docs/index.html
"""

import argparse
import html as html_lib
import json
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from trust_scorecard.ranking import category_capability_scores, score_record_sort_key  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

HIGH_TRUST_THRESHOLD = 50
MEDIUM_TRUST_THRESHOLD = 30


def _format_param_count(value: float | int | None) -> str:
    if value is None:
        return "-"
    if float(value).is_integer():
        return f"{value:.0f}B"
    return f"{value:.1f}B"


def _format_price(input_per_1k: float | None, output_per_1k: float | None) -> str:
    if input_per_1k is None and output_per_1k is None:
        return "-"
    input_usd_per_1m = (input_per_1k or 0) * 1000
    output_usd_per_1m = (output_per_1k or 0) * 1000
    input_display = f"${input_usd_per_1m:.2f}"
    output_display = f"${output_usd_per_1m:.2f}"
    return f"{input_display} / {output_display}<br><span style=\"color:#718096; font-size:0.85em;\">per 1M in/out</span>"


def _format_hallucination(value: float | int | None) -> str:
    if value is None:
        return "-"
    value = float(value)
    if value < 15:
        risk = "Low"
        color = "#38a169"
    elif value <= 40:
        risk = "Medium"
        color = "#dd6b20"
    else:
        risk = "High"
        color = "#e53e3e"
    return f"<strong style=\"color:{color};\">{value:.1f}%</strong><br><span style=\"color:#718096; font-size:0.85em;\">{risk} risk</span>"


def _format_release_date(value: str | None) -> str:
    if not value:
        return "-"
    return value.split("T", 1)[0]


def _format_compact_number(value: int | float | None) -> str:
    if value is None:
        return "-"
    value = float(value)
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.0f}K"
    return f"{value:.0f}"


def _source_confidence(
    total_claims: int,
    verified_count: int,
    unverifiable_count: int = 0,
    category_count: int = 0,
) -> str:
    if total_claims <= 0:
        return "Low / estimated"
    if verified_count >= 20 and category_count >= 7:
        return "High confidence"
    if verified_count >= 12 and category_count >= 5:
        return "Good confidence"
    if verified_count >= 8 and category_count >= 3:
        return "Moderate confidence"
    if unverifiable_count >= total_claims:
        return "Low / estimated"
    return "Low confidence"


def _confidence_dots(label: str) -> str:
    if label == "High confidence":
        return "4/4 confidence"
    if label == "Good confidence":
        return "3/4 confidence"
    if label == "Moderate confidence":
        return "2/4 confidence"
    if label == "Sourced external":
        return "source-backed"
    return "1/4 confidence"


def _ranking_lane_label(value: str | None) -> str:
    labels = {
        "verified": "Verified",
        "provisional": "Provisional",
        "estimated": "Estimated",
        "local_only": "Local only",
        "no_evidence": "No evidence",
    }
    return labels.get(value or "", "Local only")


def _format_source_freshness(source_freshness: dict | None) -> str:
    if not source_freshness:
        return "-"
    return "<br>".join(
        f"<strong>{html_lib.escape(str(source))}</strong>: {html_lib.escape(str(value))}"
        for source, value in sorted(source_freshness.items())
    )


def _format_category_coverage(category_coverage: dict | None) -> str:
    if not category_coverage:
        return "0/8"
    covered = category_coverage.get("covered", 0)
    total = category_coverage.get("total", 8)
    categories = category_coverage.get("categories") or []
    category_label = ", ".join(str(category).replace("_", " ").title() for category in categories)
    if category_label:
        return f"{covered}/{total}<br><span class=\"muted\">{html_lib.escape(category_label)}</span>"
    return f"{covered}/{total}"


def _category_from_score(score: dict) -> str:
    use_case_scores = score.get("use_case_scores", {}) or {}
    tags = {tag.lower() for tag in score.get("tags", [])}
    model_card = score.get("model_card", {}) or {}
    context_window = model_card.get("context_window_tokens") or 0
    if "coding" in use_case_scores or tags.intersection({"coding", "software-engineering"}):
        return "coding"
    if "reasoning" in use_case_scores or "reasoning" in tags:
        return "reasoning"
    if (
        "multimodal" in use_case_scores
        or tags.intersection({"multimodal", "vision", "video", "ocr", "document-analysis"})
    ):
        return "multimodal"
    if "math" in use_case_scores:
        return "math"
    if "tool_use" in use_case_scores or tags.intersection({"tool-use", "function-calling", "agentic"}):
        return "tool-use"
    if context_window >= 128000:
        return "long-context"
    return "all"


def _format_chips(labels: list[str]) -> str:
    if not labels:
        return "-"
    return (
        '<div class="chips">'
        + "".join(f'<span class="chip">{html_lib.escape(label)}</span>' for label in labels)
        + "</div>"
    )


def _strength_chips(score: dict) -> str:
    use_case_scores = score.get("use_case_scores", {}) or {}
    model_card = score.get("model_card", {}) or {}
    leaderboard_score = score.get("primary_leaderboard_score") or model_card.get("leaderboard_score")
    labels = []
    if leaderboard_score is not None:
        source = score.get("primary_leaderboard_source") or model_card.get("leaderboard_source") or "External"
        labels.append(f"{source}: {float(leaderboard_score):.1f}")
    labels.extend(f"{k.replace('_', ' ').title()}: {v:.1f}" for k, v in use_case_scores.items())

    return _format_chips(labels)


def _capabilities_from_tags(tags: list[str], context_window: int | None = None) -> str:
    normalized = {tag.lower() for tag in tags}
    caps: list[str] = []
    capability_map = [
        ("Vision", {"vision", "image", "multimodal"}),
        ("Audio", {"audio", "speech"}),
        ("Video", {"video"}),
        ("OCR", {"ocr"}),
        ("Docs", {"document-analysis", "office-automation"}),
        ("Code", {"coding", "software-engineering"}),
        ("Tools", {"tool-use", "function-calling"}),
        ("Agent", {"agentic"}),
        ("Reasoning", {"reasoning"}),
        ("Multi-Lang", {"multilingual"}),
        ("RAG", {"rag"}),
        ("Enterprise", {"enterprise"}),
        ("Open Weights", {"open-weight"}),
        ("Dense", {"dense"}),
    ]
    for label, tag_set in capability_map:
        if normalized.intersection(tag_set):
            caps.append(label)
    if "long-context" in normalized or (context_window and context_window >= 128000):
        caps.append("Long Context")
    return " • ".join(caps) if caps else "-"


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Model Trust Scorecard</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        :root {{
            color-scheme: dark;
            --bg: #050505;
            --panel: #101010;
            --panel-soft: #171717;
            --border: #2a2a2a;
            --text: #f5f5f5;
            --muted: #9a9a9a;
            --accent: #d7ff41;
            --accent-soft: rgba(215, 255, 65, 0.14);
            --good: #22c55e;
            --warn: #f59e0b;
            --bad: #ef4444;
        }}
        body {{
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            background: radial-gradient(circle at top left, rgba(215, 255, 65, 0.12), transparent 34%), var(--bg);
            color: var(--text);
            min-height: 100vh;
        }}
        a {{ color: inherit; }}
        .top-nav {{
            position: sticky;
            top: 0;
            z-index: 20;
            display: flex;
            gap: 6px;
            align-items: center;
            padding: 10px 18px;
            border-bottom: 1px solid var(--border);
            background: rgba(0, 0, 0, 0.88);
            backdrop-filter: blur(16px);
        }}
        .brand {{
            font-weight: 800;
            letter-spacing: -0.03em;
            margin-right: 18px;
        }}
        .nav-item {{
            border: 0;
            border-radius: 8px;
            background: transparent;
            color: var(--muted);
            padding: 10px 12px;
            font-weight: 600;
            cursor: pointer;
        }}
        .nav-item.active, .nav-item:hover {{
            background: #1f1f1f;
            color: var(--text);
        }}
        .rankings-menu {{
            position: absolute;
            top: 48px;
            left: 0;
            right: 0;
            display: grid;
            grid-template-columns: minmax(260px, 1fr) minmax(240px, 1fr) minmax(240px, 1fr);
            gap: 32px;
            padding: 22px 24px;
            border: 1px solid var(--border);
            border-radius: 0 0 18px 18px;
            background: rgba(0, 0, 0, 0.94);
            box-shadow: 0 24px 80px rgba(0, 0, 0, 0.55);
        }}
        .menu-section-title {{
            color: var(--muted);
            font-size: 0.72rem;
            letter-spacing: 0.25em;
            text-transform: uppercase;
            margin: 0 0 10px 12px;
        }}
        .menu-link {{
            display: block;
            color: var(--muted);
            text-decoration: none;
            padding: 10px 12px;
            border-radius: 10px;
            line-height: 1.1;
        }}
        .menu-link.active, .menu-link:hover {{
            background: #1b1b1b;
            color: var(--text);
        }}
        .container {{
            width: min(1480px, calc(100% - 32px));
            margin: 28px auto 60px;
        }}
        .hero {{
            display: grid;
            grid-template-columns: minmax(0, 1.3fr) minmax(280px, 0.7fr);
            gap: 22px;
            margin-bottom: 24px;
        }}
        .hero-card, .panel, .stat-card, .info-card {{
            background: linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02));
            border: 1px solid var(--border);
            border-radius: 18px;
            box-shadow: 0 18px 55px rgba(0,0,0,0.28);
        }}
        .hero-card {{ padding: 30px; }}
        h1 {{
            font-size: clamp(2.2rem, 5vw, 4.6rem);
            letter-spacing: -0.07em;
            line-height: 0.95;
            margin-bottom: 14px;
        }}
        .subtitle {{
            color: #c8c8c8;
            max-width: 900px;
            font-size: 1.08rem;
            line-height: 1.7;
        }}
        .anchor-pill {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 18px;
            padding: 8px 12px;
            border: 1px solid rgba(215, 255, 65, 0.28);
            border-radius: 999px;
            color: var(--accent);
            background: var(--accent-soft);
            font-weight: 700;
            text-decoration: none;
            width: fit-content;
        }}
        .hero-side {{ padding: 22px; }}
        .hero-side h2 {{ font-size: 1.05rem; margin-bottom: 12px; }}
        .hero-side p {{ color: var(--muted); line-height: 1.6; margin-bottom: 12px; }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(4, minmax(150px, 1fr));
            gap: 14px;
            margin-bottom: 22px;
        }}
        .stat-card {{ padding: 18px; }}
        .stat-value {{
            font-size: 2rem;
            font-weight: 850;
            letter-spacing: -0.04em;
        }}
        .stat-label {{ color: var(--muted); margin-top: 6px; }}
        .panel {{ padding: 20px; overflow: hidden; }}
        .toolbar {{
            display: grid;
            grid-template-columns: minmax(220px, 1.2fr) repeat(3, minmax(150px, 0.55fr));
            gap: 12px;
            margin: 18px 0 18px;
        }}
        .toolbar input, .toolbar select {{
            width: 100%;
            border: 1px solid var(--border);
            border-radius: 12px;
            background: #0d0d0d;
            color: var(--text);
            padding: 12px 14px;
            font: inherit;
        }}
        .table-wrap {{ overflow-x: auto; border: 1px solid var(--border); border-radius: 16px; }}
        table {{ width: 100%; border-collapse: collapse; min-width: 1180px; }}
        th, td {{ padding: 15px; text-align: left; border-bottom: 1px solid var(--border); vertical-align: top; }}
        th {{
            position: sticky;
            top: 49px;
            z-index: 5;
            background: #101010;
            color: #cfcfcf;
            font-size: 0.78rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }}
        tbody tr {{ background: rgba(255,255,255,0.015); }}
        tbody tr:hover {{ background: rgba(215, 255, 65, 0.06); }}
        .model-name {{ font-weight: 800; color: var(--text); }}
        .muted {{ color: var(--muted); font-size: 0.88em; }}
        .score-badge, .confidence-badge, .lane-badge {{
            display: inline-block;
            padding: 6px 10px;
            border-radius: 999px;
            font-weight: 800;
            font-size: 0.86rem;
            white-space: nowrap;
        }}
        .score-high, .confidence-strong, .lane-verified {{ background: rgba(34,197,94,0.18); color: #86efac; border: 1px solid rgba(34,197,94,0.35); }}
        .score-medium, .confidence-partial, .lane-provisional {{ background: rgba(245,158,11,0.18); color: #fcd34d; border: 1px solid rgba(245,158,11,0.35); }}
        .score-low, .confidence-low, .lane-estimated, .lane-local-only, .lane-no-evidence {{ background: rgba(239,68,68,0.18); color: #fca5a5; border: 1px solid rgba(239,68,68,0.35); }}
        .score-na {{ background: rgba(148,163,184,0.18); color: #cbd5e1; border: 1px solid rgba(148,163,184,0.35); }}
        .chips {{ display: flex; flex-wrap: wrap; gap: 6px; }}
        .chip {{
            border: 1px solid var(--border);
            border-radius: 999px;
            padding: 4px 8px;
            color: #d7d7d7;
            background: #121212;
            font-size: 0.82rem;
            white-space: nowrap;
        }}
        .info-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 16px;
            margin-top: 22px;
        }}
        .info-card {{ padding: 22px; }}
        .info-card h3 {{ margin-bottom: 10px; }}
        .info-card p, .info-card li {{ color: #c4c4c4; line-height: 1.65; }}
        .info-card ul {{ padding-left: 18px; }}
        code {{ background: #1f1f1f; border: 1px solid var(--border); border-radius: 6px; padding: 2px 6px; }}
        .github-link {{ color: var(--accent); text-decoration: none; font-weight: 700; }}
        .github-link:hover {{ text-decoration: underline; }}
        .footer {{
            margin-top: 34px;
            padding-top: 22px;
            border-top: 1px solid var(--border);
            text-align: center;
            color: var(--muted);
            font-size: 0.92rem;
        }}
        @media (max-width: 900px) {{
            .rankings-menu, .hero, .toolbar, .stats {{ grid-template-columns: 1fr; }}
            .top-nav {{ overflow-x: auto; }}
            th {{ top: 0; }}
        }}
    </style>
</head>
<body>
    <nav class="top-nav" aria-label="Main navigation">
        <div class="brand">Model Trust Scorecard</div>
        <button class="nav-item active" type="button">Rankings ^</button>
        <button class="nav-item" type="button">Dashboards</button>
        <button class="nav-item" type="button">Explore</button>
        <button class="nav-item" type="button">Tools</button>
        <button class="nav-item" type="button">Methodology</button>
        <div class="rankings-menu" aria-label="Ranking categories">
            <div>
                <div class="menu-section-title">Core Rankings</div>
                <a class="menu-link active" href="#rankings" data-filter-link="all">All Benchmarks</a>
                <a class="menu-link" href="#rankings" data-filter-link="coding">Coding</a>
                <a class="menu-link" href="#rankings" data-filter-link="multimodal">Multimodal</a>
                <a class="menu-link" href="#rankings" data-filter-link="reasoning">Reasoning</a>
            </div>
            <div>
                <div class="menu-section-title">Specialized</div>
                <a class="menu-link" href="#rankings" data-filter-link="math">Math</a>
                <a class="menu-link" href="#rankings" data-filter-link="tool-use">Tool Use</a>
                <a class="menu-link" href="#rankings" data-filter-link="long-context">Long Context</a>
                <a class="menu-link" href="#rankings" data-filter-link="all">Source Confidence</a>
            </div>
            <div>
                <div class="menu-section-title">Completeness</div>
                <a class="menu-link" href="#methodology">Evidence coverage</a>
                <a class="menu-link" href="#methodology">Claim verification</a>
                <a class="menu-link" href="#sources">Leaderboard anchors</a>
                <a class="menu-link" href="https://benchlm.ai/">BenchLM reference</a>
            </div>
        </div>
    </nav>

    <main class="container">
        <section class="hero">
            <div class="hero-card">
                <a class="anchor-pill" href="https://benchlm.ai/">BenchLM-inspired ranking surface</a>
                <h1>Reliability-first model leaderboard</h1>
                <p class="subtitle">A completeness-focused public ranking that pairs capability scores with source confidence, verification coverage, pricing, context, license, and model metadata in one filterable table.</p>
            </div>
            <aside class="hero-side hero-card">
                <h2>Accuracy guardrails</h2>
                <p>Rankings use independent capability evidence, including external leaderboard score/rank metadata, before raw verification-count tie breakers. Rows expose BenchLM-style confidence labels so sparse-source models do not look more authoritative than the evidence supports.</p>
                <p><a class="github-link" href="#sources">Review external leaderboard anchors</a></p>
            </aside>
        </section>

        <section class="stats" aria-label="Dataset coverage">
            <div class="stat-card"><div class="stat-value">{total_models}</div><div class="stat-label">Models Evaluated</div></div>
            <div class="stat-card"><div class="stat-value">{avg_score:.1f}</div><div class="stat-label">Average Trust Score</div></div>
            <div class="stat-card"><div class="stat-value">{total_claims}</div><div class="stat-label">Total Claims</div></div>
            <div class="stat-card"><div class="stat-value">{verified_pct:.0f}%</div><div class="stat-label">Claims Verified</div></div>
            <div class="stat-card"><div class="stat-value">{source_count}</div><div class="stat-label">Models With Sources</div></div>
            <div class="stat-card"><div class="stat-value">{claim_coverage_pct:.0f}%</div><div class="stat-label">Claim Coverage</div></div>
        </section>

        <section class="panel" id="rankings">
            <h2>Model Capability Rankings</h2>
            <p class="subtitle">Models are ordered by independently sourced capability first, then demonstrated benchmark/use-case performance; trust score indicates confidence in model-local claims and verification status.</p>
            <div class="toolbar" aria-label="Leaderboard filters">
                <input id="modelSearch" type="search" placeholder="Search models, providers, capabilities..." aria-label="Search models">
                <select id="categoryFilter" aria-label="Category filter">
                    <option value="all">All benchmarks</option>
                    <option value="coding">Coding</option>
                    <option value="reasoning">Reasoning</option>
                    <option value="multimodal">Multimodal</option>
                    <option value="math">Math</option>
                    <option value="tool-use">Tool Use</option>
                    <option value="long-context">Long Context</option>
                </select>
                <select id="providerFilter" aria-label="Provider filter">
                    <option value="all">All providers</option>
                    {provider_options}
                </select>
                <select id="licenseFilter" aria-label="License filter">
                    <option value="all">All licenses</option>
                    {license_options}
                </select>
            </div>
            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th>Rank</th>
                            <th>Model / Provider</th>
                            <th>Lane / Confidence</th>
                            <th>Category Coverage</th>
                            <th>Source Freshness</th>
                            <th>Trust Score</th>
                            <th>Use-Case Strengths</th>
                            <th>Capabilities</th>
                            <th>Params / Context</th>
                            <th>Pricing</th>
                            <th>Hallucination</th>
                            <th>License</th>
                        </tr>
                    </thead>
                    <tbody>{table_rows}</tbody>
                </table>
            </div>
        </section>

        <section class="info-grid" id="methodology">
            <div class="info-card">
                <h3>How rankings are ordered</h3>
                <p>Models with independently verified claims or live source score/rank metadata rank ahead of models with only unverified claims. Ranking lanes distinguish verified, provisional, estimated, local-only, and no-evidence rows; zero-evidence models are placed last. Within each lane, externally sourced or BenchLM-style weighted category capability sorts before raw verification-count tie breakers.</p>
            </div>
            <div class="info-card">
                <h3>Completeness and accuracy signals</h3>
                <ul>
                    <li><strong>Source Confidence</strong> uses a 4-tier confidence ladder based on sourced benchmark depth and weighted category breadth.</li>
                    <li><strong>Source Freshness</strong> exposes the source-reported date or retrieval timestamp used for each live adapter.</li>
                    <li><strong>Category Coverage</strong> shows how many BenchLM-style weighted categories have direct source rows.</li>
                    <li><strong>Claim Coverage</strong> shows how many models include checkable benchmark claims.</li>
                    <li><strong>Use-case and metadata columns</strong> surface context, pricing, release date, license, and capability tags without hiding uncertainty.</li>
                </ul>
            </div>
            <div class="info-card">
                <h3>Where results go</h3>
                <ul>
                    <li>This page is generated into <code>docs/index.html</code> for GitHub Pages.</li>
                    <li>The machine-readable aggregate is committed as <code>trust_scores.json</code>.</li>
                    <li>A markdown summary is committed as <code>trust_scores.md</code>.</li>
                    <li>Per-model verification reports are attached to workflow runs as artifacts.</li>
                </ul>
            </div>
            <div class="info-card">
                <h3>Request a review for a model not listed here</h3>
                <ul>
                    <li>Open the <a href="https://github.com/Grumpified-OGGVCT/model-trust-scorecard/issues/new?template=model_submission.yml" class="github-link">Model Submission issue</a>.</li>
                    <li>Or submit a PR that adds <code>models/&lt;model-id&gt;.json</code> to the catalog.</li>
                    <li>For one-off checks, run the CLI with pasted claims via <code>trust-scorecard score --text</code> or <code>--text-file</code>.</li>
                </ul>
            </div>
            <div class="info-card" id="sources">
                <h3>Leaderboard cross-check sources</h3>
                <p>When claims are not independently verified here yet, compare against external leaderboards before treating ranks as authoritative: <a href="https://benchlm.ai" class="github-link">BenchLM</a>, <a href="https://artificialanalysis.ai/leaderboards/models" class="github-link">Artificial Analysis</a>, <a href="https://llm-stats.com/leaderboards/llm-leaderboard" class="github-link">LLM Stats</a>, <a href="https://whatllm.org/explore" class="github-link">WhatLLM</a>, <a href="https://www.vellum.ai/llm-leaderboard" class="github-link">Vellum</a>, <a href="https://lmmarketcap.com" class="github-link">LM Market Cap</a>, <a href="https://openrouter.ai/rankings" class="github-link">OpenRouter rankings</a>, and Hugging Face leaderboard spaces.</p>
            </div>
        </section>

        <div class="footer">
            <p>Last updated: {updated_at}</p>
            <p style="margin-top: 10px;">
                <a href="https://github.com/Grumpified-OGGVCT/model-trust-scorecard" class="github-link">View on GitHub</a> |
                <a href="https://github.com/Grumpified-OGGVCT/model-trust-scorecard#how-it-works" class="github-link">Methodology</a> |
                <a href="https://github.com/Grumpified-OGGVCT/model-trust-scorecard/issues/new?template=model_submission.yml" class="github-link">Submit model</a>
            </p>
        </div>
    </main>

    <script>
        const searchInput = document.getElementById('modelSearch');
        const categoryFilter = document.getElementById('categoryFilter');
        const providerFilter = document.getElementById('providerFilter');
        const licenseFilter = document.getElementById('licenseFilter');
        const rows = Array.from(document.querySelectorAll('tbody tr[data-provider]'));
        function applyFilters() {{
            const query = searchInput.value.trim().toLowerCase();
            const category = categoryFilter.value;
            const provider = providerFilter.value;
            const license = licenseFilter.value;
            rows.forEach((row) => {{
                const matchesQuery = !query || row.dataset.search.includes(query);
                const matchesCategory = category === 'all' || row.dataset.category === category;
                const matchesProvider = provider === 'all' || row.dataset.provider === provider;
                const matchesLicense = license === 'all' || row.dataset.license === license;
                row.style.display = matchesQuery && matchesCategory && matchesProvider && matchesLicense ? '' : 'none';
            }});
        }}
        [searchInput, categoryFilter, providerFilter, licenseFilter].forEach((control) => control.addEventListener('input', applyFilters));
        document.querySelectorAll('[data-filter-link]').forEach((link) => {{
            link.addEventListener('click', () => {{
                categoryFilter.value = link.dataset.filterLink;
                document.querySelectorAll('[data-filter-link]').forEach((item) => item.classList.remove('active'));
                link.classList.add('active');
                applyFilters();
            }});
        }});
    </script>
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
    scores = sorted(data["scores"], key=score_record_sort_key)

    # Calculate stats (skip None values)
    total_models = len(scores)
    valid_scores = [s["trust_score"] for s in scores if s["trust_score"] is not None]
    avg_score = sum(valid_scores) / len(valid_scores) if valid_scores else 0
    total_claims = sum(s["total_claims"] for s in scores)
    total_verified = sum(s["verified_count"] for s in scores)
    verified_pct = (total_verified / total_claims * 100) if total_claims > 0 else 0
    source_count = sum(1 for s in scores if s.get("total_claims", 0) > 0)
    claim_coverage_pct = (source_count / total_models * 100) if total_models > 0 else 0
    providers = sorted({s.get("vendor") for s in scores if s.get("vendor")})
    licenses = sorted({
        (s.get("model_card", {}) or {}).get("license_kind") or s.get("license", "unknown")
        for s in scores
    })
    provider_options = "\n".join(
        f'<option value="{html_lib.escape(provider)}">{html_lib.escape(provider)}</option>'
        for provider in providers
    )
    license_options = "\n".join(
        f'<option value="{html_lib.escape(str(license_value))}">'
        f"{html_lib.escape(str(license_value))}</option>"
        for license_value in licenses
    )

    # Generate table rows with expanded metadata
    rows = []
    for rank, score in enumerate(scores, 1):
        trust_score = score["trust_score"]
        badge_class = (
            "score-na" if trust_score is None
            else "score-high" if trust_score >= HIGH_TRUST_THRESHOLD
            else "score-medium" if trust_score >= MEDIUM_TRUST_THRESHOLD
            else "score-low"
        )
        score_display = f"{trust_score:.1f}" if trust_score is not None else "N/A"
        use_case_scores = score.get("use_case_scores", {}) or {}
        use_case_label = _strength_chips(score)

        # Extract metadata from model card
        model_card = score.get("model_card", {})
        params = model_card.get("parameter_count_billions")
        total_params = model_card.get("total_parameter_count_billions")
        if params and total_params and total_params != params:
            params_display = f"{_format_param_count(params)} / {_format_param_count(total_params)}"
        else:
            params_display = _format_param_count(params)

        ctx = model_card.get("context_window_tokens")
        ctx_display = _format_compact_number(ctx)

        tags = score.get("tags", [])
        caps_display = _capabilities_from_tags(tags, ctx)
        caps_display = _format_chips(caps_display.split(" • ") if caps_display != "-" else [])
        price_display = _format_price(
            model_card.get("pricing_per_1k_input_usd"),
            model_card.get("pricing_per_1k_output_usd"),
        )
        hallucination_display = _format_hallucination(model_card.get("hallucination_rate"))
        license_display = model_card.get("license_kind") or score.get("license", "unknown")
        raw_license_display = str(license_display)
        release_date = _format_release_date(model_card.get("release_date"))
        source_confidence = score.get("confidence_tier") or _source_confidence(
            score.get("total_claims", 0),
            score.get("verified_count", 0),
            score.get("unverifiable_count", 0),
            len(category_capability_scores(use_case_scores)),
        )
        confidence_class = (
            "confidence-strong" if source_confidence in {"High confidence", "Good confidence", "Sourced external"}
            else "confidence-partial" if source_confidence == "Moderate confidence"
            else "confidence-low"
        )
        confidence_dots = _confidence_dots(source_confidence)
        ranking_lane = score.get("ranking_lane") or "local_only"
        lane_label = _ranking_lane_label(ranking_lane)
        lane_class = f"lane-{ranking_lane.replace('_', '-')}"
        category_coverage_display = _format_category_coverage(score.get("category_coverage"))
        freshness_display = _format_source_freshness(score.get("source_freshness"))
        category = _category_from_score(score)
        provider = html_lib.escape(score["vendor"] or "-")
        license_value = html_lib.escape(raw_license_display)
        search_blob = html_lib.escape(
            " ".join([
                score["display_name"],
                score["vendor"] or "",
                raw_license_display,
                " ".join(tags),
                " ".join(use_case_scores.keys()),
            ]).lower()
        )

        rows.append(
            f"""<tr data-provider="{provider}" data-license="{license_value}" data-category="{category}" data-search="{search_blob}">
                <td>{rank}</td>
                <td><span class="model-name">{html_lib.escape(score['display_name'])}</span><br><span class="muted">{provider} • {release_date}</span></td>
                <td><span class="lane-badge {lane_class}">{lane_label}</span><br><span class="confidence-badge {confidence_class}">{source_confidence}</span><br><span class="muted">{confidence_dots} • {score['verified_count']}/{score['total_claims']} verified</span></td>
                <td>{category_coverage_display}</td>
                <td>{freshness_display}</td>
                <td><span class="score-badge {badge_class}">{score_display}</span><br><span style="color:#718096; font-size:0.85em;">{score['verified_count']}/{score['total_claims']} verified</span></td>
                <td>{use_case_label}</td>
                <td>{caps_display}</td>
                <td>{params_display}<br><span class="muted">{ctx_display} ctx</span></td>
                <td>{price_display}</td>
                <td>{hallucination_display}</td>
                <td>{license_value}</td>
            </tr>"""
        )

    # Generate HTML
    html = HTML_TEMPLATE.format(
        total_models=total_models,
        avg_score=avg_score,
        total_claims=total_claims,
        verified_pct=verified_pct,
        source_count=source_count,
        claim_coverage_pct=claim_coverage_pct,
        provider_options=provider_options,
        license_options=license_options,
        table_rows="\n".join(rows),
        updated_at=data.get("generated_at", "N/A"),
    )

    # Write output
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding="utf-8")
    logger.info(f"Generated dashboard at {args.output}")

    return 0


if __name__ == "__main__":
    exit(main())
