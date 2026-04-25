"""
End-to-end pipeline for model evaluation.

Pipeline stages:
  1. Load model card (from JSON catalog or text input)
  2. Extract benchmark claims from model card text
  3. Fetch official benchmark data from registered sources
  4. Verify claims against official data
  5. Compute trust score
  6. Store evaluation in database

Supports single-model and batch processing modes.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from trust_scorecard.benchmark_sources.base import BenchmarkSourceBase
from trust_scorecard.claim_extractor import extract_claims
from trust_scorecard.models import (
    BenchmarkClaim,
    BenchmarkResult,
    Claim,
    LicenseKind,
    ModelCard,
    ModelEvaluation,
)
from trust_scorecard.persistence import EvaluationStore
from trust_scorecard.scoring import compute_trust_score
from trust_scorecard.verification_engine import VerificationEngine

logger = logging.getLogger(__name__)
SWE_BENCH_NORMALIZED = "swebench"
SWE_BENCH_VERIFIED_NORMALIZED = "swebenchverified"


class EvaluationPipeline:
    """
    Orchestrates the end-to-end model evaluation workflow.
    """

    def __init__(
        self,
        benchmark_sources: list[BenchmarkSourceBase] | None = None,
        store: EvaluationStore | None = None,
        default_tolerance: float = 2.0,
    ):
        """
        Initialize the evaluation pipeline.

        Parameters
        ----------
        benchmark_sources:
            List of benchmark data sources to use for verification.
            If None, creates default sources.
        store:
            Evaluation store for persistence. If None, uses in-memory store.
        default_tolerance:
            Default tolerance for claim verification (percentage points).
        """
        self.benchmark_sources = benchmark_sources or []
        self.store = store or EvaluationStore(":memory:")
        self.default_tolerance = default_tolerance

    def evaluate_model(
        self,
        model_card: ModelCard,
        card_text: str | None = None,
        source_url: str | None = None,
    ) -> ModelEvaluation:
        """
        Run the full evaluation pipeline for a single model.

        Parameters
        ----------
        model_card:
            Model metadata.
        card_text:
            Optional raw text from model card to extract claims from.
            If None, uses model_card.card_text.
        source_url:
            Optional URL of the source document for claim attribution.

        Returns
        -------
        Complete ModelEvaluation record.
        """
        logger.info("Evaluating model: %s", model_card.model_id)

        # Stage 1: Extract claims
        text = card_text or model_card.card_text or ""
        text_claims = extract_claims(text, source_url=source_url or model_card.card_url)
        # Text-extracted claims come first so source-specific prose takes precedence
        # over catalog fallback claims when both describe the same benchmark value.
        claims = _dedupe_claims([
            *text_claims,
            *_claims_from_structured_benchmarks(
                model_card.benchmark_claims,
                self.benchmark_sources,
                fallback_source_url=source_url or model_card.card_url,
            ),
        ])
        logger.info("Extracted %d claims", len(claims))

        if not claims:
            logger.warning("No claims extracted for %s", model_card.model_id)
            # Return minimal evaluation
            return ModelEvaluation(
                model_id=model_card.model_id,
                card=model_card,
                claims=[],
                outcomes=[],
                benchmark_results=[],
                trust_score=None,
                notes="No claims extracted from model card",
            )

        # Stage 2: Fetch benchmark data
        benchmark_results = self._fetch_benchmark_data(model_card.model_id)
        logger.info("Fetched %d benchmark results", len(benchmark_results))

        # Stage 3: Verify claims
        engine = VerificationEngine(benchmark_results, self.default_tolerance)
        outcomes = engine.verify_all(model_card.model_id, claims)
        logger.info(
            "Verified %d claims: %d verified, %d refuted, %d unverifiable",
            len(outcomes),
            sum(1 for o in outcomes if o.status.value == "verified"),
            sum(1 for o in outcomes if o.status.value == "refuted"),
            sum(1 for o in outcomes if o.status.value == "unverifiable"),
        )

        # Stage 4: Compute trust score
        trust_score = compute_trust_score(model_card.model_id, model_card, outcomes)

        # Stage 5: Create evaluation record
        evaluation = ModelEvaluation(
            model_id=model_card.model_id,
            card=model_card,
            claims=claims,
            outcomes=outcomes,
            benchmark_results=benchmark_results,
            trust_score=trust_score,
        )

        # Stage 6: Store evaluation
        self.store.save(evaluation)

        logger.info(
            "Evaluation complete for %s: trust score = %.1f",
            model_card.model_id,
            trust_score.score,
        )

        return evaluation

    def evaluate_batch(
        self,
        model_cards: list[ModelCard],
    ) -> list[ModelEvaluation]:
        """
        Evaluate multiple models in batch.

        Parameters
        ----------
        model_cards:
            List of model cards to evaluate.

        Returns
        -------
        List of ModelEvaluation records.
        """
        logger.info("Starting batch evaluation of %d models", len(model_cards))
        evaluations = []

        for i, card in enumerate(model_cards, 1):
            logger.info("Processing model %d/%d: %s", i, len(model_cards), card.model_id)
            try:
                evaluation = self.evaluate_model(card)
                evaluations.append(evaluation)
            except Exception as exc:
                logger.error(
                    "Failed to evaluate %s: %s",
                    card.model_id,
                    exc,
                    exc_info=True,
                )

        logger.info("Batch evaluation complete: %d/%d successful", len(evaluations), len(model_cards))
        return evaluations

    def _fetch_benchmark_data(self, model_id: str) -> list[BenchmarkResult]:
        """
        Fetch benchmark results from all configured sources.

        Returns both the target model's rows and full leaderboards (when
        available) so percentile calculations have global context.
        """
        results: list[BenchmarkResult] = []
        seen: set[tuple[str, str]] = set()

        def _add(items: list[BenchmarkResult]) -> None:
            for item in items:
                key = (item.model_id, item.benchmark_id)
                if key in seen:
                    continue
                seen.add(key)
                results.append(item)

        for source in self.benchmark_sources:
            try:
                logger.debug("Fetching from %s for %s", source.__class__.__name__, model_id)
                _add(source.get_results(model_id))
                _add(source.get_all_results())
            except Exception as exc:
                logger.warning(
                    "Failed to fetch from %s for %s: %s",
                    source.__class__.__name__,
                    model_id,
                    exc,
                )

        return results


def load_model_card_from_json(path: str | Path) -> ModelCard:
    """
    Load a ModelCard from a JSON file.

    Parameters
    ----------
    path:
        Path to the JSON file.

    Returns
    -------
    A ModelCard instance.
    """
    path = Path(path)
    data = json.loads(path.read_text())

    # Parse optional datetime field
    if "release_date" in data and data["release_date"]:
        data["release_date"] = datetime.fromisoformat(data["release_date"])

    return ModelCard(**data)


def _claims_from_structured_benchmarks(
    benchmark_claims: list[BenchmarkClaim],
    benchmark_sources: list[BenchmarkSourceBase] | None = None,
    fallback_source_url: str | None = None,
) -> list[Claim]:
    """Convert catalog-supplied benchmark_claims into verifier claims."""
    claims: list[Claim] = []
    for item in benchmark_claims:
        source_url = _structured_claim_source_url(item, fallback_source_url)
        benchmark = _canonical_structured_benchmark_name(item.benchmark, benchmark_sources or [])
        metric_label = f" {item.metric}" if item.metric else ""
        source_label = f" ({item.source})" if item.source else ""
        raw = item.raw or f"{benchmark}{metric_label} result: {item.value}{source_label}"
        claims.append(
            Claim.model_validate(
                {
                    "metric": benchmark,
                    "value": item.value,
                    "raw": raw,
                    "source_url": source_url,
                }
            )
        )
    return claims


def _dedupe_claims(claims: list[Claim]) -> list[Claim]:
    """Deduplicate text-extracted and structured claims while preserving order."""
    seen_metrics: set[str] = set()
    deduped: list[Claim] = []
    for claim in claims:
        key = _normalize_claim_metric(claim.metric)
        if key in seen_metrics:
            continue
        seen_metrics.add(key)
        deduped.append(claim)
    return deduped


def _normalize_claim_metric(name: str) -> str:
    return name.lower().replace(" ", "").replace("-", "").replace("_", "")


def _canonical_structured_benchmark_name(
    name: str,
    benchmark_sources: list[BenchmarkSourceBase],
) -> str:
    stripped = name.strip()
    normalized = _normalize_claim_metric(stripped)
    first_swebench_display_name: str | None = None

    for source in benchmark_sources:
        normalized_id = _normalize_claim_metric(source.config.id)
        normalized_display_name = _normalize_claim_metric(source.config.display_name)
        if normalized in {normalized_id, normalized_display_name}:
            return source.config.display_name
        if normalized == SWE_BENCH_NORMALIZED:
            if SWE_BENCH_VERIFIED_NORMALIZED in {normalized_id, normalized_display_name}:
                return source.config.display_name
            if first_swebench_display_name is None and normalized_display_name.startswith(SWE_BENCH_NORMALIZED):
                first_swebench_display_name = source.config.display_name

    if first_swebench_display_name is not None:
        return first_swebench_display_name

    return stripped


def _structured_claim_source_url(
    item: BenchmarkClaim,
    fallback_source_url: str | None = None,
) -> str | None:
    if item.source_url:
        return item.source_url
    if item.source and item.source.startswith("http"):
        return item.source
    return fallback_source_url


def load_model_cards_from_directory(directory: str | Path) -> list[ModelCard]:
    """
    Load all model cards from JSON files in a directory.

    Parameters
    ----------
    directory:
        Path to directory containing model JSON files.

    Returns
    -------
    List of ModelCard instances.
    """
    directory = Path(directory)
    if not directory.exists():
        logger.warning("Model directory not found: %s", directory)
        return []

    cards = []
    for json_file in directory.glob("*.json"):
        try:
            card = load_model_card_from_json(json_file)
            cards.append(card)
            logger.info("Loaded model card: %s", card.model_id)
        except Exception as exc:
            logger.error("Failed to load %s: %s", json_file, exc)

    logger.info("Loaded %d model cards from %s", len(cards), directory)
    return cards


def create_model_card_from_text(
    model_id: str,
    display_name: str,
    card_text: str,
    vendor: str | None = None,
    card_url: str | None = None,
    license_kind: LicenseKind = LicenseKind.UNKNOWN,
    **kwargs,
) -> ModelCard:
    """
    Create a ModelCard from raw text input.

    Useful for ad-hoc evaluation of models not in the catalog.

    Parameters
    ----------
    model_id:
        Unique identifier for the model.
    display_name:
        Human-readable model name.
    card_text:
        Raw text containing benchmark claims.
    vendor:
        Optional vendor name.
    card_url:
        Optional URL of the source document.
    license_kind:
        License type.
    **kwargs:
        Additional ModelCard fields.

    Returns
    -------
    A ModelCard instance.
    """
    return ModelCard(
        model_id=model_id,
        display_name=display_name,
        card_text=card_text,
        vendor=vendor,
        card_url=card_url,
        license_kind=license_kind,
        **kwargs,
    )
