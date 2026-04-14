"""
trust_scorecard – transparent, reproducible trust-score engine for AI model benchmark claims.
"""

from trust_scorecard.models import (
    BenchmarkConfig,
    BenchmarkResult,
    Claim,
    ModelEvaluation,
    TrustScore,
    VerificationOutcome,
)

__all__ = [
    "Claim",
    "BenchmarkResult",
    "VerificationOutcome",
    "TrustScore",
    "ModelEvaluation",
    "BenchmarkConfig",
]

__version__ = "0.1.0"
