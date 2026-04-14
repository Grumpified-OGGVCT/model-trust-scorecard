"""Ensure benchmark sources are consumed via the public interface."""

from trust_scorecard.benchmark_sources.base import BenchmarkSourceBase
from trust_scorecard.models import BenchmarkConfig, MetricKind, ModelCard
from trust_scorecard.persistence import EvaluationStore
from trust_scorecard.pipeline import EvaluationPipeline
from trust_scorecard.verification_engine import create_engine_from_sources


class DummySource(BenchmarkSourceBase):
    """Stub source that returns both targeted and leaderboard rows."""

    def __init__(self) -> None:
        super().__init__(
            BenchmarkConfig(
                id="mmlu",
                display_name="MMLU",
                description="Stubbed benchmark",
                metric_kind=MetricKind.ACCURACY,
                weight_max=1.0,
                data_source="dummy",
                data_source_params={},
                tolerance_default=2.0,
                enabled=True,
            )
        )
        self.fetch_calls: list[str] = []
        self.all_requested = False

    def _fetch(self, model_id: str):
        self.fetch_calls.append(model_id)
        return [self._make_result(model_id=model_id, value=80.0, raw_payload={"source": "fetch"})]

    def get_all_results(self):
        self.all_requested = True
        return [
            self._make_result(
                model_id="leaderboard-model",
                value=90.0,
                raw_payload={"source": "all"},
            )
        ]


def test_pipeline_uses_source_results_and_leaderboard_context():
    source = DummySource()
    pipeline = EvaluationPipeline([source], EvaluationStore(":memory:"), default_tolerance=2.0)

    card = ModelCard(
        model_id="test-model",
        display_name="Test Model",
        card_text="Model reports 80% on MMLU.",
    )

    evaluation = pipeline.evaluate_model(card)

    result_ids = {r.model_id for r in evaluation.benchmark_results}
    assert {"test-model", "leaderboard-model"}.issubset(result_ids)
    assert source.fetch_calls == ["test-model"]


def test_create_engine_from_sources_fetches_all_available_rows():
    source = DummySource()
    engine = create_engine_from_sources([source], model_ids=["foo"])

    result_ids = {r.model_id for r in engine.benchmark_results}

    assert {"foo", "leaderboard-model"}.issubset(result_ids)
    assert source.fetch_calls == ["foo"]
    assert source.all_requested is True
