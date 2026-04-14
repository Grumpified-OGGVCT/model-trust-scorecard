# 🔍 Model Trust Scorecard

[![Tests](https://github.com/Grumpified-OGGVCT/model-trust-scorecard/workflows/Tests/badge.svg)](https://github.com/Grumpified-OGGVCT/model-trust-scorecard/actions)
[![CodeQL](https://github.com/Grumpified-OGGVCT/model-trust-scorecard/workflows/CodeQL/badge.svg)](https://github.com/Grumpified-OGGVCT/model-trust-scorecard/security/code-scanning)
[![License](https://img.shields.io/github/license/Grumpified-OGGVCT/model-trust-scorecard)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

**Stop guessing whether a model's "80% SWE-bench" claim is real.**

Model Trust Scorecard is a transparent, reproducible engine that verifies AI model benchmark claims by cross-referencing them against official leaderboard data.

🌐 **[Live Dashboard](https://grumpified-oggvct.github.io/model-trust-scorecard/)** | 📊 **[Latest Rankings](trust_scores.md)** | 📖 **[Documentation](#documentation)**

---

## ✨ Features

- **🎯 Automated Claim Extraction** - Regex-powered parser extracts benchmark claims from model cards
- **✅ Independent Verification** - Cross-references claims against official sources (SWE-bench, Open LLM Leaderboard, etc.)
- **📊 Trust Score (0-100)** - Weighted rubric: Coverage 30%, Verification 40%, Performance Gap 20%, Openness 5%, Safety 5%
- **💾 Persistent Storage** - SQLite database + optional HuggingFace Dataset export
- **🤖 GitHub-First** - Fully automated via GitHub Actions, triggerable via CLI
- **📈 Live Dashboard** - Auto-generated GitHub Pages dashboard with rankings
- **🔄 Nightly Updates** - Automatic re-evaluation to track claim accuracy over time

---

## 🚀 Quick Start

### Installation

```bash
pip install git+https://github.com/Grumpified-OGGVCT/model-trust-scorecard.git
```

### CLI Usage

```bash
# List models in catalog
trust-scorecard list

# Evaluate a single model
trust-scorecard score gpt-4.1

# Evaluate from pasted text (no catalog entry needed)
trust-scorecard score my-model \
  --text "Achieves 90% on MMLU and 85% on SWE-bench Verified" \
  --vendor "MyCompany" \
  --display-name "My Model"

# Evaluate from a pasted list / file (supports '-' for stdin)
trust-scorecard score my-model --text-file claims.txt
pbpaste | trust-scorecard score my-model --text-file -

# Batch evaluate all catalog models
trust-scorecard batch

# Batch evaluate an explicit subset (repeat or comma-list); works with stdin/file lists
trust-scorecard batch --models gpt-4.1 --models "gemini-2.5-pro,claude-opus-4.5"
cat models.txt | trust-scorecard batch --models-file -

# Export results
trust-scorecard export --db trust_scores.db --output results.json

# Storage and history (SQLite by default; reruns append)
# trust_scores.db accumulates every evaluation so you can track drift over time.
```

**Requesting which models are analyzed**
- Use `--models` or `--models-file` with `trust-scorecard batch` to target a specific set (comma-separated, repeatable, or newline file/STDIN).
- Paste provider claim lists directly via `--text-file -`; the parser handles multi-line/bullet inputs and keeps source URLs with each claim.
- Evaluations are stored in `trust_scores.db` with timestamps; rerunning a model creates a new record instead of overwriting, so history stays intact.
- `trust-scorecard list` shows the catalog; add more JSON entries under `models/` to make them available to batch runs and GitHub Actions.

### GitHub Actions Integration

Trigger evaluations via GitHub CLI:

```bash
# Manual trigger
gh workflow run trust-score.yml

# Trigger for a specific model
gh api repos/:owner/:repo/dispatches -f event_type=evaluate_model

# Check workflow status
gh run list --workflow=trust-score.yml
```

---

## 📊 Trust Score Rubric

| Component | Weight | Description |
|-----------|--------|-------------|
| **Coverage** | 30% | How many standard benchmarks are reported? |
| **Verification** | 40% | What % of claims match official sources? |
| **Performance Gap** | 20% | Average deviation from official values |
| **Openness** | 5% | Open-source vs proprietary license |
| **Safety** | 5% | Safety benchmarks reported? |

**Example Scores:**
- 🟢 **80-100**: Highly trustworthy - most claims verified
- 🟡 **60-79**: Moderately trustworthy - some verified claims
- 🟠 **<60**: Low trust - few verified claims or significant gaps

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        User Input                            │
│  (Model card text / JSON catalog entry / Pasted claims)      │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│              1. CLAIM EXTRACTION (claim_extractor.py)        │
│  • Regex patterns for benchmark names (SWE-bench, MMLU, ...) │
│  • Extract numeric values (80.2%, 90%, etc.)                 │
│  • Normalize & deduplicate → List[Claim]                     │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│       2. FETCH OFFICIAL DATA (benchmark_sources/)            │
│  • SWE-bench: https://www.swebench.com/api/results           │
│  • Open LLM Leaderboard: HF Datasets API                     │
│  • Fallback: Static community-curated data                   │
│  → List[BenchmarkResult]                                     │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│         3. VERIFICATION (verification_engine.py)             │
│  • Match claims to official results by benchmark name        │
│  • Check |claimed - official| ≤ tolerance (default 2%)      │
│  • Status: VERIFIED / REFUTED / UNVERIFIABLE                 │
│  → List[VerificationOutcome]                                 │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│              4. SCORING (scoring.py)                         │
│  • Coverage: Count of standard benchmarks                    │
│  • Verification: % of verified claims                        │
│  • Performance Gap: Avg |delta| for verified claims          │
│  • Openness: License type (open/restricted/proprietary)      │
│  • Safety: Safety benchmarks present?                        │
│  → TrustScore (0-100)                                        │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│           5. PERSISTENCE (persistence.py)                    │
│  • Store in SQLite (trust_scores.db)                         │
│  • Optional: Export to HuggingFace Dataset                   │
│  • History tracking for trend analysis                       │
└──────────────────────────────────────────────────────────────┘
```

---

## 📁 Repository Structure

```
model-trust-scorecard/
├── trust_scorecard/          # Core Python package
│   ├── __main__.py          # CLI interface (Click)
│   ├── models.py            # Pydantic data models
│   ├── claim_extractor.py   # Regex claim parser
│   ├── verification_engine.py # Claim verification logic
│   ├── scoring.py           # Trust score rubric
│   ├── persistence.py       # SQLite + HF Dataset export
│   ├── pipeline.py          # End-to-end orchestration
│   └── benchmark_sources/   # Benchmark data fetchers
│       ├── base.py          # Abstract base class
│       ├── swe_bench.py     # SWE-bench leaderboard
│       └── open_llm_leaderboard.py  # HF Open LLM Leaderboard
├── models/                  # JSON catalog of known models
│   ├── gpt-4.1.json
│   ├── claude-opus-4.5.json
│   └── ...
├── benchmarks/              # JSON configs for benchmark sources
│   ├── swe_bench_verified.json
│   ├── mmlu.json
│   └── ...
├── scripts/                 # Standalone CI scripts
│   ├── extract_claims.py   # Extract from all models
│   ├── verify.py           # Verify single model
│   ├── aggregate.py        # Merge reports → trust_scores.json
│   └── generate_dashboard.py  # Build static HTML
├── docs/                    # GitHub Pages dashboard
│   └── index.html
├── tests/                   # Pytest test suite
│   ├── test_claim_extractor.py
│   ├── test_verification_engine.py
│   └── test_scoring.py
├── .github/
│   ├── workflows/           # GitHub Actions
│   │   ├── trust-score.yml  # Main evaluation pipeline
│   │   ├── nightly.yml      # Nightly re-evaluation
│   │   ├── tests.yml        # Pytest on every PR
│   │   ├── codeql.yml       # Security scanning
│   │   └── pages.yml        # Deploy dashboard
│   ├── ISSUE_TEMPLATE/      # Issue templates
│   └── CONTRIBUTING.md
└── pyproject.toml           # Package configuration
```

---

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](.github/CONTRIBUTING.md) for guidelines.

### Adding a New Model

1. **Via Issue**: Use the [Model Submission template](../../issues/new?template=model_submission.yml)
2. **Via PR**: Add a JSON file to `models/`:

```json
{
  "model_id": "your-model-id",
  "display_name": "Your Model Name",
  "vendor": "Provider",
  "card_text": "Paste benchmark claims here...",
  "card_url": "https://source-url",
  "license_kind": "open|restricted|proprietary"
}
```

### Adding a Benchmark Source

Implement a new `BenchmarkSourceBase` subclass:

1. Create `trust_scorecard/benchmark_sources/your_benchmark.py`
2. Implement `_fetch(model_id)` → `list[BenchmarkResult]`
3. Add fallback data for offline operation
4. Add JSON config to `benchmarks/`
5. Update `get_default_sources()` in `benchmark_sources/__init__.py`

---

## 📖 Documentation

### Model Catalog Format

Each model in `models/` is a JSON file:

```json
{
  "model_id": "gpt-4.1",
  "display_name": "GPT-4.1",
  "vendor": "OpenAI",
  "card_text": "GPT-4.1 achieves 85.4% on SWE-bench Verified, 88.7% on MMLU...",
  "card_url": "https://platform.openai.com/docs/models/gpt-4",
  "license_kind": "proprietary",
  "parameter_count_billions": null,
  "context_window_tokens": 128000,
  "release_date": "2026-01-15T00:00:00",
  "tags": ["multimodal", "reasoning", "coding"],
  "pricing_per_1k_input_usd": 0.03,
  "pricing_per_1k_output_usd": 0.06
}
```

### Benchmark Config Format

Each benchmark in `benchmarks/` is a JSON file:

```json
{
  "id": "swe_bench_verified",
  "display_name": "SWE-bench Verified",
  "description": "Real-world GitHub issue resolution",
  "metric_kind": "percent_resolved",
  "weight_max": 10.0,
  "data_source": "swe_bench_html",
  "data_source_params": {
    "url": "https://www.swebench.com/api/results"
  },
  "tolerance_default": 2.0,
  "enabled": true,
  "tags": ["coding", "agentic"]
}
```

### CI/CD Pipeline

The trust score pipeline runs automatically on:
- Push to `main` (when models/ or trust_scorecard/ changes)
- Pull requests
- Nightly schedule (2 AM UTC)
- Manual trigger via GitHub CLI: `gh workflow run trust-score.yml`

**Pipeline Stages:**
1. **Extract Claims** - Parse all model cards → `claims.json`
2. **Verify (Matrix)** - Parallel verification per model → `reports/*.json`
3. **Aggregate** - Merge reports → `trust_scores.json` + `trust_scores.md`
4. **Publish** - Deploy dashboard to GitHub Pages

---

## 🔒 Security

- **No secrets required** - Uses public leaderboard APIs
- **Sandboxed execution** - No arbitrary code execution
- **CodeQL scanning** - Automated security checks
- **Dependency scanning** - Dependabot enabled

Report security issues to: [See SECURITY.md](.github/SECURITY.md)

---

## 📜 License

MIT License - see [LICENSE](LICENSE)

---

## 🙏 Acknowledgments

- [SWE-bench](https://www.swebench.com/) - Official leaderboard for software engineering benchmarks
- [Open LLM Leaderboard](https://huggingface.co/spaces/open-llm-leaderboard/open_llm_leaderboard) - HuggingFace community leaderboard
- [Pydantic](https://pydantic.dev/) - Data validation
- [Click](https://click.palletsprojects.com/) - CLI framework
- [Rich](https://rich.readthedocs.io/) - Terminal formatting

---

**Built with ❤️ by the open-source community**
