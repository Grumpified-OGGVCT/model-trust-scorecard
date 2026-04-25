from trust_scorecard.models import ModelCard, ModelEvaluation, TrustScore, TrustScoreBreakdown
from trust_scorecard.ranking import capability_sort_key, evaluation_sort_key


def test_capability_rank_beats_trust_score():
    higher_trust = ModelCard(
        model_id="higher-trust",
        display_name="Higher Trust",
        capability_rank=5,
        tags=["text", "coding"],
    )
    higher_capability = ModelCard(
        model_id="higher-capability",
        display_name="Higher Capability",
        capability_rank=1,
        tags=["text", "coding"],
    )

    ranked = sorted(
        [
            (higher_trust, {"coding": 95.0}, 99.0),
            (higher_capability, {"coding": 70.0}, 10.0),
        ],
        key=lambda item: capability_sort_key(item[0], item[1], item[2]),
    )

    assert ranked[0][0].model_id == "higher-capability"


def test_benchmark_evidence_beats_trust_score_after_capability_scores():
    sparse_high_trust = ModelCard(
        model_id="sparse-high-trust",
        display_name="Sparse High Trust",
        tags=["text"],
        parameter_count_billions=7,
        context_window_tokens=128000,
    )
    broad_low_trust = ModelCard(
        model_id="broad-low-trust",
        display_name="Broad Low Trust",
        tags=["text"],
        parameter_count_billions=7,
        context_window_tokens=128000,
    )

    ranked = sorted(
        [
            (sparse_high_trust, {"coding": 80.0}, 99.0, 1),
            (broad_low_trust, {"coding": 80.0, "reasoning": 80.0}, 10.0, 6),
        ],
        key=lambda item: capability_sort_key(item[0], item[1], item[2], item[3]),
    )

    assert ranked[0][0].model_id == "broad-low-trust"


def test_evaluation_sort_prefers_broader_capability_profile():
    coder = ModelEvaluation(
        model_id="coder",
        card=ModelCard(
            model_id="coder",
            display_name="Coder",
            tags=["text", "coding", "agentic"],
            parameter_count_billions=32,
        ),
        trust_score=TrustScore(
            model_id="coder",
            score=95.0,
            breakdown=TrustScoreBreakdown(
                coverage_score=10.0,
                verification_score=10.0,
                performance_gap_score=10.0,
                openness_score=5.0,
                safety_score=0.0,
                use_case_scores={"coding": 80.0, "reasoning": 78.0},
            ),
        ),
    )
    frontier = ModelEvaluation(
        model_id="frontier",
        card=ModelCard(
            model_id="frontier",
            display_name="Frontier",
            tags=["text", "coding", "multimodal", "vision", "agentic"],
            parameter_count_billions=40,
            context_window_tokens=256000,
        ),
        trust_score=TrustScore(
            model_id="frontier",
            score=60.0,
            breakdown=TrustScoreBreakdown(
                coverage_score=10.0,
                verification_score=10.0,
                performance_gap_score=10.0,
                openness_score=5.0,
                safety_score=0.0,
                use_case_scores={"coding": 85.0, "reasoning": 84.0, "tool_use": 82.0},
            ),
        ),
    )

    ranked = sorted([coder, frontier], key=evaluation_sort_key)

    assert ranked[0].model_id == "frontier"
