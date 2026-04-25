"""
Pydantic data models for the trust-score engine.

Every object that crosses a module boundary is typed here so that the
whole pipeline remains serialisable to JSON / SQLite without effort.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class MetricKind(str, enum.Enum):
    """The kind of numeric result a benchmark reports."""

    PERCENT_RESOLVED = "percent_resolved"  # SWE-bench (0-100)
    ACCURACY = "accuracy"                  # MMLU, TruthfulQA (0-100)
    PASS_AT_K = "pass_at_k"               # HumanEval pass@1 (0-100)
    SCORE = "score"                        # Generic normalised score (0-100)
    BOOL = "bool"                          # Pass / fail flag


class VerificationStatus(str, enum.Enum):
    VERIFIED = "verified"       # Claim matches an independent source within tolerance
    REFUTED = "refuted"         # Claim deviates beyond tolerance
    UNVERIFIABLE = "unverifiable"  # No independent source found for this claim
    PENDING = "pending"         # Not yet checked


class LicenseKind(str, enum.Enum):
    OPEN = "open"               # MIT, Apache-2, BSD, etc.
    RESTRICTED = "restricted"   # CC-BY-NC, research-only, etc.
    PROPRIETARY = "proprietary"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Core data shapes
# ---------------------------------------------------------------------------


class Claim(BaseModel):
    """A benchmark claim extracted from a model card or marketing text."""

    metric: str = Field(..., description="Canonical benchmark name, e.g. 'SWE-bench Verified'")
    value: float = Field(..., ge=0.0, le=100.0, description="Claimed value in [0, 100]")
    raw: str = Field(..., description="Verbatim text fragment that produced this claim")
    target: str | None = Field(None, description="Benchmark variant, e.g. 'Verified', 'Lite'")
    source_url: str | None = Field(None, description="URL of the source document")

    @field_validator("metric")
    @classmethod
    def normalise_metric(cls, v: str) -> str:
        return v.strip()


class BenchmarkResult(BaseModel):
    """A single independently-sourced benchmark result."""

    benchmark_id: str = Field(..., description="ID matching a BenchmarkConfig.id")
    model_id: str = Field(..., description="Canonical model identifier")
    metric_kind: MetricKind
    value: float = Field(..., description="Result value in [0, 100]")
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)
    source_url: str | None = None
    raw_payload: dict[str, Any] | None = Field(
        None, description="Raw JSON from the data source for full auditability"
    )


class BenchmarkClaim(BaseModel):
    """A structured 0-100 benchmark claim supplied directly in a model catalog entry."""

    benchmark: str = Field(
        ...,
        description=(
            "Benchmark name, configured display name, or configured ID such as "
            "'MMLU', 'SWE-bench Verified', or 'swe_bench_verified'."
        ),
    )
    metric: str | None = Field(None, description="Reported metric, e.g. 'accuracy' or 'pass@1'")
    value: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Claimed benchmark result normalized to the current 0-100 scoring scale.",
    )
    source: str | None = None
    source_url: str | None = None
    raw: str | None = None


class VerificationOutcome(BaseModel):
    """Result of matching one Claim against official benchmark data."""

    claim: Claim
    status: VerificationStatus
    official_value: float | None = None
    delta: float | None = Field(None, description="|claim.value - official_value|")
    tolerance: float = Field(2.0, description="Max |delta| to count as verified")
    benchmark_result: BenchmarkResult | None = None
    notes: str = ""


class TrustScoreBreakdown(BaseModel):
    """Per-component breakdown of a trust score."""

    coverage_score: float = Field(..., ge=0.0, le=30.0)
    verification_score: float = Field(..., ge=0.0, le=40.0)
    performance_gap_score: float = Field(..., ge=0.0, le=20.0)
    openness_score: float = Field(..., ge=0.0, le=5.0)
    safety_score: float = Field(..., ge=0.0, le=5.0)
    use_case_scores: dict[str, float] = Field(default_factory=dict, description="Per use-case strengths (0-100)")

    @property
    def total(self) -> float:
        return round(
            self.coverage_score
            + self.verification_score
            + self.performance_gap_score
            + self.openness_score
            + self.safety_score,
            1,
        )


class TrustScore(BaseModel):
    """Final trust score (0-100) for a model with a full audit trail."""

    model_id: str
    score: float = Field(..., ge=0.0, le=100.0)
    breakdown: TrustScoreBreakdown
    computed_at: datetime = Field(default_factory=datetime.utcnow)
    schema_version: str = "1"


class ModelCard(BaseModel):
    """Structured representation of metadata extracted from a model card."""

    model_id: str
    display_name: str
    vendor: str | None = None
    card_url: str | None = None
    card_text: str | None = None
    license_kind: LicenseKind = LicenseKind.UNKNOWN
    architecture: str | None = None
    parameter_count_billions: float | None = None
    total_parameter_count_billions: float | None = None
    context_window_tokens: int | None = None
    release_date: datetime | None = None
    tags: list[str] = Field(default_factory=list)
    pricing_per_1k_input_usd: float | None = None
    pricing_per_1k_output_usd: float | None = None
    weekly_tokens: str | None = None
    hallucination_rate: float | None = None
    structured_output_error_rate: float | None = None
    artificial_analysis_intelligence_index: float | None = None
    artificial_analysis_coding_index: float | None = None
    artificial_analysis_agentic_index: float | None = None
    capability_rank: int | None = None
    benchmark_claims: list[BenchmarkClaim] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def coerce_legacy_catalog_fields(cls, data: Any) -> Any:
        """Accept older catalog fields used by supplied model JSON files."""
        if not isinstance(data, dict):
            return data
        if "license_kind" not in data and "license" in data:
            data = data.copy()
            data["license_kind"] = data["license"]
        return data


class ModelEvaluation(BaseModel):
    """
    Complete evaluation record for a single model.

    This is the primary unit of persistence: one record = one model run,
    stored verbatim in SQLite and optionally exported to a HF Dataset.
    """

    model_id: str
    card: ModelCard
    claims: list[Claim] = Field(default_factory=list)
    outcomes: list[VerificationOutcome] = Field(default_factory=list)
    benchmark_results: list[BenchmarkResult] = Field(default_factory=list)
    trust_score: TrustScore | None = None
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)
    pipeline_version: str = "1"
    notes: str = ""


# ---------------------------------------------------------------------------
# Configuration shapes
# ---------------------------------------------------------------------------


class BenchmarkConfig(BaseModel):
    """
    A JSON-first descriptor for a benchmark source.

    Drop a new JSON file in benchmarks/ to register a new source – no code
    change required.
    """

    id: str = Field(..., description="Snake-case identifier, e.g. 'swe_bench_verified'")
    display_name: str
    description: str = ""
    metric_kind: MetricKind
    weight_max: float = Field(
        ...,
        gt=0,
        description="Maximum contribution to the trust score from this benchmark",
    )
    data_source: str = Field(
        ...,
        description=(
            "One of: 'hf_dataset', 'hf_leaderboard', 'swe_bench_html', 'opencompass', 'static_json'"
        ),
    )
    data_source_params: dict[str, Any] = Field(default_factory=dict)
    tolerance_default: float = Field(2.0, description="Absolute tolerance for claim verification")
    enabled: bool = True
    tags: list[str] = Field(default_factory=list)
