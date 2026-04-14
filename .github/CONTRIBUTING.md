# Contributing to Model Trust Scorecard

Thanks for your interest in contributing! 🎉

## Ways to Contribute

### 1. Add a New Model

Submit a model for evaluation via [Model Submission issue template](../../issues/new?template=model_submission.yml)

Or create a PR with a new JSON file in `models/`:

```json
{
  "model_id": "your-model-id",
  "display_name": "Your Model Name",
  "vendor": "Provider",
  "card_text": "Paste benchmark claims here...",
  "card_url": "https://link-to-source",
  "license_kind": "open|restricted|proprietary",
  "parameter_count_billions": 100,
  "context_window_tokens": 128000
}
```

### 2. Add a New Benchmark Source

Implement a new `BenchmarkSourceBase` subclass in `trust_scorecard/benchmark_sources/`:

1. Create `your_benchmark.py` with a class extending `BenchmarkSourceBase`
2. Implement `_fetch(model_id)` to return `list[BenchmarkResult]`
3. Add fallback data for offline operation
4. Add a JSON config in `benchmarks/`
5. Update `get_default_sources()` in `benchmark_sources/__init__.py`

### 3. Improve the Scoring Algorithm

The current rubric is in `trust_scorecard/scoring.py`:
- Coverage: 30%
- Verification: 40%
- Performance Gap: 20%
- Openness: 5%
- Safety: 5%

Open an issue to propose changes before implementing.

### 4. Add Tests

We need more test coverage! Add tests in `tests/`:
- `test_claim_extractor.py` - Test claim extraction patterns
- `test_verification.py` - Test verification logic
- `test_scoring.py` - Test scoring rubric
- `test_pipeline.py` - End-to-end integration tests

### 5. Improve Documentation

- Update `README.md` with examples
- Add architecture diagrams
- Write tutorials for common use cases

## Development Setup

```bash
# Clone the repository
git clone https://github.com/Grumpified-OGGVCT/model-trust-scorecard.git
cd model-trust-scorecard

# Install in development mode
pip install -e .[dev]

# Run tests
pytest tests/

# Run linter
ruff check trust_scorecard/ tests/

# Run type checker
mypy trust_scorecard/
```

## Code Style

- Use `ruff` for linting (configuration in `pyproject.toml`)
- Follow PEP 8
- Type hints for all function signatures
- Docstrings in NumPy style

## Pull Request Process

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes
4. Add tests for new functionality
5. Run tests and linting: `pytest && ruff check`
6. Commit with clear messages
7. Push to your fork
8. Open a Pull Request

## Community Guidelines

- Be respectful and inclusive
- Provide constructive feedback
- Focus on the technical merits of ideas
- Help newcomers get started

## Questions?

Open a [Discussion](../../discussions) or reach out via issues.
