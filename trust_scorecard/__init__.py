"""
trust_scorecard – transparent, reproducible trust-score engine for AI model benchmark claims.
"""

from trust_scorecard.models import (
    Claim,
    BenchmarkResult,
    VerificationOutcome,
    TrustScore,
    ModelEvaluation,
    BenchmarkConfig,
)
from trust_scorecard.pipeline import evaluate_model, evaluate_batch

__all__ = [
    "Claim",
    "BenchmarkResult",
    "VerificationOutcome",
    "TrustScore",
    "ModelEvaluation",
    "BenchmarkConfig",
    "evaluate_model",
    "evaluate_batch",
]

__version__ = "0.1.0"
