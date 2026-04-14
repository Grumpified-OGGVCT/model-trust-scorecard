"""
CLI interface for the trust-scorecard engine.

Commands:
  score     - Evaluate a single model (from catalog or text input)
  batch     - Evaluate multiple models from the catalog
  list      - List all models in the catalog
  export    - Export evaluation results
  serve     - Start the API server (future)

Example usage:
  # Evaluate a single model from catalog
  trust-scorecard score gpt-4.1

  # Evaluate from raw text
  trust-scorecard score --text "Model achieves 80% on SWE-bench Verified" --model-id custom-model

  # Batch evaluate all models in catalog
  trust-scorecard batch --models-dir models/

  # Export results to JSON
  trust-scorecard export --output trust_scores.json
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from trust_scorecard.benchmark_sources import get_default_sources
from trust_scorecard.models import LicenseKind
from trust_scorecard.persistence import EvaluationStore
from trust_scorecard.pipeline import (
    EvaluationPipeline,
    create_model_card_from_text,
    load_model_card_from_json,
    load_model_cards_from_directory,
)

console = Console()


def setup_logging(verbose: bool = False) -> None:
    """Configure logging with rich handler."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


@click.group()
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose logging")
@click.pass_context
def cli(ctx, verbose: bool) -> None:
    """Trust Scorecard - Verify AI model benchmark claims."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    setup_logging(verbose)


@cli.command()
@click.argument("model_id", required=False)
@click.option("--text", help="Model card text to analyze")
@click.option("--url", help="Source URL for attribution")
@click.option("--display-name", help="Display name for the model")
@click.option("--vendor", help="Model vendor/provider")
@click.option("--license", type=click.Choice(["open", "restricted", "proprietary", "unknown"]), default="unknown", help="License type")
@click.option("--models-dir", type=click.Path(exists=True), default="models", help="Directory containing model catalog")
@click.option("--db", type=click.Path(), default="trust_scores.db", help="Database path")
@click.option("--tolerance", type=float, default=2.0, help="Verification tolerance (percentage points)")
@click.pass_context
def score(
    ctx,
    model_id: Optional[str],
    text: Optional[str],
    url: Optional[str],
    display_name: Optional[str],
    vendor: Optional[str],
    license: str,
    models_dir: str,
    db: str,
    tolerance: float,
) -> None:
    """
    Evaluate a single model and compute its trust score.

    Can evaluate models from the catalog (by MODEL_ID) or from raw text (--text).
    """
    if not model_id and not text:
        console.print("[red]Error: Either MODEL_ID or --text must be provided[/red]")
        sys.exit(1)

    # Initialize pipeline
    sources = get_default_sources()
    store = EvaluationStore(db)
    pipeline = EvaluationPipeline(sources, store, tolerance)

    # Load or create model card
    if text:
        # Create model card from text input
        if not model_id:
            model_id = "custom-model"
        if not display_name:
            display_name = model_id

        license_kind = LicenseKind(license)
        model_card = create_model_card_from_text(
            model_id=model_id,
            display_name=display_name,
            card_text=text,
            vendor=vendor,
            card_url=url,
            license_kind=license_kind,
        )
    else:
        # Load from catalog
        catalog_path = Path(models_dir) / f"{model_id}.json"
        if not catalog_path.exists():
            console.print(f"[red]Model not found in catalog: {model_id}[/red]")
            console.print(f"Searched in: {catalog_path}")
            sys.exit(1)

        model_card = load_model_card_from_json(catalog_path)

    # Run evaluation
    console.print(f"\n[bold]Evaluating: {model_card.display_name}[/bold]")
    console.print(f"Model ID: {model_card.model_id}")

    evaluation = pipeline.evaluate_model(model_card)

    # Display results
    _display_evaluation(evaluation)


@cli.command()
@click.option("--models-dir", type=click.Path(exists=True), default="models", help="Directory containing model catalog")
@click.option("--db", type=click.Path(), default="trust_scores.db", help="Database path")
@click.option("--tolerance", type=float, default=2.0, help="Verification tolerance (percentage points)")
@click.option("--filter", "model_filter", help="Only evaluate models matching this pattern")
@click.pass_context
def batch(
    ctx,
    models_dir: str,
    db: str,
    tolerance: float,
    model_filter: Optional[str],
) -> None:
    """
    Evaluate all models in the catalog directory.
    """
    # Load model cards
    model_cards = load_model_cards_from_directory(models_dir)

    if not model_cards:
        console.print(f"[yellow]No model cards found in {models_dir}[/yellow]")
        sys.exit(0)

    # Apply filter if specified
    if model_filter:
        model_cards = [
            c for c in model_cards
            if model_filter.lower() in c.model_id.lower() or model_filter.lower() in c.display_name.lower()
        ]
        console.print(f"Filtered to {len(model_cards)} models matching '{model_filter}'")

    # Initialize pipeline
    sources = get_default_sources()
    store = EvaluationStore(db)
    pipeline = EvaluationPipeline(sources, store, tolerance)

    # Run batch evaluation
    console.print(f"\n[bold]Evaluating {len(model_cards)} models...[/bold]\n")
    evaluations = pipeline.evaluate_batch(model_cards)

    # Display summary
    _display_batch_summary(evaluations)


@cli.command()
@click.option("--models-dir", type=click.Path(exists=True), default="models", help="Directory containing model catalog")
def list(models_dir: str) -> None:
    """List all models in the catalog."""
    model_cards = load_model_cards_from_directory(models_dir)

    if not model_cards:
        console.print(f"[yellow]No models found in {models_dir}[/yellow]")
        return

    table = Table(title=f"Model Catalog ({len(model_cards)} models)")
    table.add_column("Model ID", style="cyan")
    table.add_column("Display Name", style="green")
    table.add_column("Vendor", style="blue")
    table.add_column("License", style="magenta")

    for card in sorted(model_cards, key=lambda c: c.model_id):
        table.add_row(
            card.model_id,
            card.display_name,
            card.vendor or "—",
            card.license_kind.value,
        )

    console.print(table)


@cli.command()
@click.option("--db", type=click.Path(exists=True), required=True, help="Database path")
@click.option("--output", type=click.Path(), required=True, help="Output JSON file path")
def export(db: str, output: str) -> None:
    """Export evaluation results to JSON."""
    store = EvaluationStore(db)
    store.export_to_json(output)
    console.print(f"[green]✓[/green] Exported to {output}")


def _display_evaluation(evaluation) -> None:
    """Display a single evaluation result."""
    console.print("\n[bold cyan]═══ Trust Score ═══[/bold cyan]")

    if not evaluation.trust_score:
        console.print("[yellow]No trust score computed (no claims extracted)[/yellow]")
        return

    score = evaluation.trust_score
    breakdown = score.breakdown

    # Overall score
    console.print(f"\n[bold green]Overall Score: {score.score:.1f}/100[/bold green]\n")

    # Breakdown table
    table = Table(title="Score Breakdown")
    table.add_column("Component", style="cyan")
    table.add_column("Score", justify="right", style="green")
    table.add_column("Max", justify="right", style="dim")

    table.add_row("Coverage", f"{breakdown.coverage_score:.1f}", "30.0")
    table.add_row("Verification", f"{breakdown.verification_score:.1f}", "40.0")
    table.add_row("Performance Gap", f"{breakdown.performance_gap_score:.1f}", "20.0")
    table.add_row("Openness", f"{breakdown.openness_score:.1f}", "5.0")
    table.add_row("Safety", f"{breakdown.safety_score:.1f}", "5.0")

    console.print(table)

    # Claims summary
    console.print("\n[bold cyan]═══ Claims ═══[/bold cyan]")
    console.print(f"Total claims: {len(evaluation.claims)}")

    verified = sum(1 for o in evaluation.outcomes if o.status.value == "verified")
    refuted = sum(1 for o in evaluation.outcomes if o.status.value == "refuted")
    unverifiable = sum(1 for o in evaluation.outcomes if o.status.value == "unverifiable")

    console.print(f"[green]✓ Verified:[/green] {verified}")
    console.print(f"[red]✗ Refuted:[/red] {refuted}")
    console.print(f"[yellow]? Unverifiable:[/yellow] {unverifiable}")

    # Show individual outcomes
    if evaluation.outcomes:
        console.print("\n[bold cyan]═══ Verification Details ═══[/bold cyan]\n")
        for outcome in evaluation.outcomes:
            status_icon = {"verified": "[green]✓[/green]", "refuted": "[red]✗[/red]", "unverifiable": "[yellow]?[/yellow]"}
            icon = status_icon.get(outcome.status.value, "·")
            console.print(f"{icon} {outcome.claim.metric}: {outcome.claim.value}%")
            if outcome.official_value is not None:
                console.print(f"   Official: {outcome.official_value}% (Δ={outcome.delta:.2f}%)")
            console.print(f"   {outcome.notes}")
            console.print()


def _display_batch_summary(evaluations) -> None:
    """Display batch evaluation summary."""
    if not evaluations:
        console.print("[yellow]No evaluations completed[/yellow]")
        return

    table = Table(title=f"Batch Evaluation Results ({len(evaluations)} models)")
    table.add_column("Rank", justify="right", style="dim")
    table.add_column("Model", style="cyan")
    table.add_column("Trust Score", justify="right", style="green")
    table.add_column("Claims", justify="right")
    table.add_column("Verified", justify="right", style="green")

    # Sort by trust score descending
    sorted_evals = sorted(
        evaluations,
        key=lambda e: e.trust_score.score if e.trust_score else 0.0,
        reverse=True,
    )

    for rank, evaluation in enumerate(sorted_evals, 1):
        score = evaluation.trust_score.score if evaluation.trust_score else 0.0
        verified = sum(1 for o in evaluation.outcomes if o.status.value == "verified")

        table.add_row(
            str(rank),
            evaluation.card.display_name,
            f"{score:.1f}",
            str(len(evaluation.claims)),
            str(verified),
        )

    console.print(table)


if __name__ == "__main__":
    cli(obj={})
