from trust_scorecard.models import (
    BenchmarkResult,
    Claim,
    MetricKind,
    ModelCard,
    ModelEvaluation,
    TrustScore,
    TrustScoreBreakdown,
    VerificationOutcome,
    VerificationStatus,
)
from trust_scorecard.ranking import (
    _numeric_scores,
    capability_sort_key,
    evaluation_sort_key,
    score_record_sort_key,
)


def test_numeric_scores_filters_invalid_values():
    assert _numeric_scores(
        {
            "coding": 99.0,
            "reasoning": "98.5",
            "math": "n/a",
            "safety": None,
            "edge": "",
        }
    ) == {"coding": 99.0, "reasoning": 98.5}


def test_composite_capability_score_beats_static_capability_rank():
    static_ranked = ModelCard(
        model_id="static-ranked",
        display_name="Static Ranked",
        capability_rank=5,
        tags=["text", "coding"],
    )
    dynamically_stronger = ModelCard(
        model_id="dynamically-stronger",
        display_name="Dynamically Stronger",
        capability_rank=1,
        tags=["text", "coding"],
    )

    ranked = sorted(
        [
            (static_ranked, {"coding": 70.0, "reasoning": 70.0, "math": 70.0}, 99.0),
            (dynamically_stronger, {"coding": 90.0, "reasoning": 88.0, "math": 86.0}, 10.0),
        ],
        key=lambda item: capability_sort_key(item[0], item[1], item[2]),
    )

    assert ranked[0][0].model_id == "dynamically-stronger"


def test_minimum_score_count_gates_capability_ranking():
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
            (
                sparse_high_trust,
                {"coding": 99.0, "reasoning": 99.0, "math": "n/a", "safety": None, "edge": ""},
                99.0,
                1,
            ),
            (broad_low_trust, {"coding": 80.0, "reasoning": 80.0, "math": 80.0}, 10.0, 6),
        ],
        key=lambda item: capability_sort_key(item[0], item[1], item[2], item[3]),
    )

    assert ranked[0][0].model_id == "broad-low-trust"


def test_partial_data_sorts_by_trust_before_metadata():
    lower_trust = ModelCard(
        model_id="lower-trust",
        display_name="Lower Trust",
        tags=["text", "multimodal"],
        parameter_count_billions=70,
    )
    higher_trust = ModelCard(
        model_id="higher-trust",
        display_name="Higher Trust",
        tags=["text"],
        parameter_count_billions=7,
    )

    ranked = sorted(
        [
            (lower_trust, {"coding": 95.0}, 25.0),
            (higher_trust, {"coding": 70.0}, 50.0),
        ],
        key=lambda item: capability_sort_key(item[0], item[1], item[2]),
    )

    assert ranked[0][0].model_id == "higher-trust"


def test_zero_score_models_sort_after_partial_data():
    no_scores = ModelCard(model_id="no-scores", display_name="No Scores", tags=["text"])
    partial_scores = ModelCard(
        model_id="partial-scores",
        display_name="Partial Scores",
        tags=["text"],
    )

    ranked = sorted(
        [
            (no_scores, {}, 99.0),
            (partial_scores, {"coding": 70.0}, 10.0),
        ],
        key=lambda item: capability_sort_key(item[0], item[1], item[2]),
    )

    assert ranked[0][0].model_id == "partial-scores"


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


def test_evaluation_and_score_record_use_same_evidence_count_semantics():
    card = ModelCard(
        model_id="stable",
        display_name="Stable",
        tags=["text"],
        parameter_count_billions=7,
        context_window_tokens=128000,
    )
    trust_score = TrustScore(
        model_id="stable",
        score=75.0,
        breakdown=TrustScoreBreakdown(
            coverage_score=10.0,
            verification_score=10.0,
            performance_gap_score=10.0,
            openness_score=5.0,
            safety_score=0.0,
            use_case_scores={"coding": 80.0},
        ),
    )
    claims = [
        Claim(metric="MMLU", value=80.0, raw="MMLU 80"),
        Claim(metric="GPQA", value=70.0, raw="GPQA 70"),
    ]
    outcomes = [
        VerificationOutcome(claim=claims[index % len(claims)], status=VerificationStatus.VERIFIED)
        for index in range(4)
    ]
    benchmark_results = [
        BenchmarkResult(
            benchmark_id=f"benchmark-{index}",
            model_id="stable",
            metric_kind=MetricKind.ACCURACY,
            value=80.0,
        )
        for index in range(6)
    ]
    evaluation = ModelEvaluation(
        model_id="stable",
        card=card,
        trust_score=trust_score,
        claims=claims,
        outcomes=outcomes,
        benchmark_results=benchmark_results,
    )
    score_record = {
        "model_card": card.model_dump(mode="json"),
        "use_case_scores": trust_score.breakdown.use_case_scores,
        "trust_score": trust_score.score,
        "total_claims": len(evaluation.claims),
    }

    assert evaluation_sort_key(evaluation) == score_record_sort_key(score_record)
