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

import logging
import sys
from pathlib import Path

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
from trust_scorecard.reporting import build_status_summary, write_local_artifacts

console = Console()


def _safe_symbol(preferred: str, fallback: str) -> str:
    """Return a symbol that the active stdout encoding can render."""
    encoding = sys.stdout.encoding or "utf-8"
    try:
        preferred.encode(encoding)
        return preferred
    except Exception:  # noqa: BLE001
        return fallback


CHECK_MARK = _safe_symbol("✓", "OK")
CROSS_MARK = _safe_symbol("✗", "X")
UNKNOWN_MARK = _safe_symbol("?", "?")
PENDING_MARK = _safe_symbol("…", "...")
SECTION_BAR = "=" * 19
LIST_BULLET = _safe_symbol("·", "*")


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
@click.option(
    "--text-file",
    help="Path to a file (or '-' for stdin) containing pasted claims/model card text",
)
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
    model_id: str | None,
    text: str | None,
    text_file: str | None,
    url: str | None,
    display_name: str | None,
    vendor: str | None,
    license: str,
    models_dir: str,
    db: str,
    tolerance: float,
) -> None:
    """
    Evaluate a single model and compute its trust score.

    Can evaluate models from the catalog (by MODEL_ID) or from raw text (--text/--text-file/-).
    """
    card_text = _read_text_input(text, text_file)

    if not model_id and not card_text:
        console.print("[red]Error: Either MODEL_ID or --text must be provided[/red]")
        sys.exit(1)

    # Initialize pipeline
    sources = get_default_sources()
    store = EvaluationStore(db)
    pipeline = EvaluationPipeline(sources, store, tolerance)

    # Load or create model card
    if card_text:
        # Create model card from text input
        if not model_id:
            model_id = "custom-model"
        if not display_name:
            display_name = model_id

        license_kind = LicenseKind(license)
        model_card = create_model_card_from_text(
            model_id=model_id,
            display_name=display_name,
            card_text=card_text,
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

    evaluation = pipeline.evaluate_model(model_card, card_text=card_text, source_url=url)

    # Display results
    _display_evaluation(evaluation)
    _refresh_local_artifacts(store)


@cli.command()
@click.option("--models-dir", type=click.Path(exists=True), default="models", help="Directory containing model catalog")
@click.option("--db", type=click.Path(), default="trust_scores.db", help="Database path")
@click.option("--tolerance", type=float, default=2.0, help="Verification tolerance (percentage points)")
@click.option("--filter", "model_filter", help="Only evaluate models matching this pattern")
@click.option(
    "--models",
    "models",
    multiple=True,
    help="Explicit model IDs to evaluate (repeatable or comma-separated)",
)
@click.option(
    "--models-file",
    help="Path to a file (or '-' for stdin) containing model IDs, one per line",
)
@click.pass_context
def batch(
    ctx,
    models_dir: str,
    db: str,
    tolerance: float,
    model_filter: str | None,
    models: tuple[str, ...],
    models_file: str | None,
) -> None:
    """
    Evaluate all models in the catalog directory.
    """
    # Load model cards
    model_cards = load_model_cards_from_directory(models_dir)

    if not model_cards:
        console.print(f"[yellow]No model cards found in {models_dir}[/yellow]")
        sys.exit(0)

    # Apply explicit selection first (from CLI list and/or file/stdin)
    selected_ids = _collect_model_ids(models, models_file)
    if selected_ids:
        catalog_by_id = {c.model_id: c for c in model_cards}
        missing = [mid for mid in selected_ids if mid not in catalog_by_id]
        model_cards = [catalog_by_id[mid] for mid in selected_ids if mid in catalog_by_id]

        if missing:
            console.print(
                f"[yellow]Skipped {len(missing)} IDs not in catalog:[/yellow] {', '.join(missing)}"
            )

        console.print(f"Selected {len(model_cards)} models from provided list")

    # Apply filter if specified
    if model_filter:
        model_cards = [
            c for c in model_cards
            if model_filter.lower() in c.model_id.lower() or model_filter.lower() in c.display_name.lower()
        ]
        console.print(f"Filtered to {len(model_cards)} models matching '{model_filter}'")

    if not model_cards:
        console.print("[yellow]No models selected for evaluation[/yellow]")
        sys.exit(0)

    # Initialize pipeline
    sources = get_default_sources()
    store = EvaluationStore(db)
    pipeline = EvaluationPipeline(sources, store, tolerance)

    # Run batch evaluation
    console.print(f"\n[bold]Evaluating {len(model_cards)} models...[/bold]\n")
    evaluations = pipeline.evaluate_batch(model_cards)

    # Display summary
    _display_batch_summary(evaluations)
    _refresh_local_artifacts(store)


@cli.command(name="list")
@click.option("--models-dir", type=click.Path(exists=True), default="models", help="Directory containing model catalog")
def list_models(models_dir: str) -> None:
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
    console.print(f"\n[bold cyan]{SECTION_BAR} Trust Score {SECTION_BAR}[/bold cyan]")

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

    if breakdown.use_case_scores:
        uc_table = Table(title="Use-Case Strength (0-100)")
        uc_table.add_column("Use Case", style="cyan")
        uc_table.add_column("Score", justify="right", style="green")
        for use_case, value in breakdown.use_case_scores.items():
            uc_table.add_row(use_case, f"{value:.1f}")
        console.print(uc_table)

    # Claims summary
    console.print(f"\n[bold cyan]{SECTION_BAR} Claims {SECTION_BAR}[/bold cyan]")
    console.print(f"Total claims: {len(evaluation.claims)}")

    verified = sum(1 for o in evaluation.outcomes if o.status.value == "verified")
    refuted = sum(1 for o in evaluation.outcomes if o.status.value == "refuted")
    unverifiable = sum(1 for o in evaluation.outcomes if o.status.value == "unverifiable")
    pending = sum(1 for o in evaluation.outcomes if o.status.value == "pending")

    console.print(f"[green]{CHECK_MARK} Verified:[/green] {verified}")
    console.print(f"[red]{CROSS_MARK} Refuted:[/red] {refuted}")
    console.print(f"[yellow]{UNKNOWN_MARK} Unverifiable:[/yellow] {unverifiable}")
    if pending:
        console.print(f"[cyan]{PENDING_MARK} Pending:[/cyan] {pending}")

    # Show individual outcomes
    if evaluation.outcomes:
        console.print(f"\n[bold cyan]{SECTION_BAR} Verification Details {SECTION_BAR}[/bold cyan]\n")
        for outcome in evaluation.outcomes:
            status_icon = {
                "verified": f"[green]{CHECK_MARK}[/green]",
                "refuted": f"[red]{CROSS_MARK}[/red]",
                "unverifiable": f"[yellow]{UNKNOWN_MARK}[/yellow]",
                "pending": f"[cyan]{PENDING_MARK}[/cyan]",
            }
            icon = status_icon.get(outcome.status.value, LIST_BULLET)
            console.print(f"{icon} {outcome.claim.metric}: {outcome.claim.value}% ({outcome.status.value})")
            if outcome.official_value is not None:
                console.print(f"   Official: {outcome.official_value}% (delta={outcome.delta:.2f}%)")
                if outcome.benchmark_result and outcome.benchmark_result.source_url:
                    console.print(f"   Source: {outcome.benchmark_result.source_url}")
            console.print(f"   {outcome.notes}")
            console.print()

    _display_benchmark_evidence(evaluation)


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
    table.add_column("Evidence", justify="right", style="cyan")
    table.add_column("Status", style="yellow")

    # Sort by trust score descending
    sorted_evals = sorted(
        evaluations,
        key=lambda e: e.trust_score.score if e.trust_score else 0.0,
        reverse=True,
    )

    for rank, evaluation in enumerate(sorted_evals, 1):
        score = evaluation.trust_score.score if evaluation.trust_score else 0.0
        verified = sum(1 for o in evaluation.outcomes if o.status.value == "verified")
        refuted = sum(1 for o in evaluation.outcomes if o.status.value == "refuted")
        unverifiable = sum(1 for o in evaluation.outcomes if o.status.value == "unverifiable")
        pending = sum(1 for o in evaluation.outcomes if o.status.value == "pending")
        status = build_status_summary(
            total_claims=len(evaluation.claims),
            verified_count=verified,
            refuted_count=refuted,
            unverifiable_count=unverifiable,
            pending_count=pending,
        )

        table.add_row(
            str(rank),
            evaluation.card.display_name,
            f"{score:.1f}",
            str(len(evaluation.claims)),
            str(verified),
            str(len(evaluation.benchmark_results)),
            status,
        )

    console.print(table)


def _display_benchmark_evidence(evaluation) -> None:
    """Display independent benchmark rows that were found for the model."""
    console.print(f"\n[bold cyan]{SECTION_BAR} Known Benchmark Evidence {SECTION_BAR}[/bold cyan]")

    if not evaluation.benchmark_results:
        console.print(
            "[yellow]No independent benchmark rows were found for this model in the current sources.[/yellow]"
        )
        return

    table = Table(title="Official Benchmark Data")
    table.add_column("Benchmark", style="cyan")
    table.add_column("Official", justify="right", style="green")
    table.add_column("Source", style="blue")

    for result in sorted(evaluation.benchmark_results, key=lambda item: item.benchmark_id):
        table.add_row(
            result.benchmark_id,
            f"{result.value:.1f}%",
            result.source_url or "—",
        )

    console.print(table)


def _refresh_local_artifacts(store: EvaluationStore) -> None:
    """Refresh trust_scores outputs and dashboard from the latest saved evaluations."""
    try:
        evaluations = store.get_all_latest()
        if not evaluations:
            return
        write_local_artifacts(evaluations)
        console.print(
            "\n[dim]Updated local outputs: trust_scores.json, trust_scores.md, docs/index.html[/dim]"
        )
    except (OSError, ValueError) as exc:
        console.print(
            "[yellow]Warning: failed to refresh trust_scores.json, trust_scores.md, "
            f"or docs/index.html: {exc}[/yellow]"
        )


def _read_from_file_or_stdin(path: str) -> str:
    """Read text from a file path or stdin sentinel ('-')."""
    if path == "-":
        return sys.stdin.read()

    file_path = Path(path)
    if not file_path.exists():
        console.print(f"[red]File not found: {path}[/red]")
        sys.exit(1)

    return file_path.read_text()


def _read_text_input(text: str | None, text_file: str | None) -> str | None:
    """
    Combine inline text and optional file/stdin payloads.
    """
    blobs: list[str] = []

    if text and text.strip():
        blobs.append(text.strip())

    if text_file:
        file_text = _read_from_file_or_stdin(text_file)
        if file_text.strip():
            blobs.append(file_text.strip())

    if not blobs:
        return None

    return "\n".join(blobs)


def _collect_model_ids(models: tuple[str, ...], models_file: str | None) -> list[str]:
    """
    Build an ordered, de-duplicated list of model IDs from CLI args and optional file/stdin.
    """
    ids: list[str] = []

    for entry in models:
        for token in entry.split(","):
            token = token.strip()
            if token:
                ids.append(token)

    if models_file:
        content = _read_from_file_or_stdin(models_file)
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            ids.append(stripped)

    seen = set()
    ordered: list[str] = []
    for mid in ids:
        if mid in seen:
            continue
        seen.add(mid)
        ordered.append(mid)

    return ordered


if __name__ == "__main__":
    cli(obj={})
