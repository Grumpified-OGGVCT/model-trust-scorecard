"""
Claim extraction from model card text.

Strategy:
  1. Primary:  regex patterns for well-known benchmark names and numeric formats.
  2. Secondary: heuristic normalisation (capitalisation, alias resolution).
  3. Future hook: an optional LLM-based extractor (not shipped here to avoid
     API-key coupling, but the interface is defined so callers can swap it in).

The extractor is intentionally conservative: it only emits a claim when it
can associate a numeric value with a recognisable benchmark name.  Ambiguous
fragments are dropped with a warning rather than silently included.
"""

from __future__ import annotations

import logging
import re

from trust_scorecard.models import Claim

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Alias table – maps every surface form we might encounter to a canonical name
# ---------------------------------------------------------------------------

_ALIAS_TABLE: dict[str, str] = {
    # SWE-bench variants
    "swe bench": "SWE-bench",
    "swe-bench": "SWE-bench",
    "swebench": "SWE-bench",
    "swe_bench": "SWE-bench",
    "swe bench verified": "SWE-bench Verified",
    "swe-bench verified": "SWE-bench Verified",
    "swe bench lite": "SWE-bench Lite",
    "swe-bench lite": "SWE-bench Lite",
    "swe bench pro": "SWE-bench Pro",
    "swe-bench pro": "SWE-bench Pro",
    "swe bench verified (mini)": "SWE-bench Verified (mini)",
    # MMLU
    "mmlu": "MMLU",
    "mmlu pro": "MMLU-Pro",
    "mmlu-pro": "MMLU-Pro",
    "mmlupro": "MMLU-Pro",
    "massive multitask language understanding": "MMLU",
    "bbh": "BBH",
    "big bench hard": "BBH",
    # HumanEval
    "humaneval": "HumanEval",
    "human eval": "HumanEval",
    "human-eval": "HumanEval",
    # GPQA
    "gpqa": "GPQA",
    "gpqa diamond": "GPQA Diamond",
    # TruthfulQA
    "truthfulqa": "TruthfulQA",
    "truthful qa": "TruthfulQA",
    "truthful-qa": "TruthfulQA",
    # GSM8K
    "gsm8k": "GSM8K",
    "grade school math": "GSM8K",
    # BIG-Bench
    "bigbench": "BIG-Bench",
    "big bench": "BIG-Bench",
    "big-bench": "BIG-Bench",
    # OpenCompass
    "opencompass": "OpenCompass",
    # ARC
    "arc": "ARC",
    "arc agi": "ARC-AGI",
    "arc-agi": "ARC-AGI",
    "arc challenge": "ARC Challenge",
    "arc-challenge": "ARC Challenge",
    # HellaSwag
    "hellaswag": "HellaSwag",
    # WinoGrande
    "winogrande": "WinoGrande",
    # Math
    "math": "MATH",
    "math benchmark": "MATH",
    # MBPP
    "mbpp": "MBPP",
    # LiveCodeBench
    "livecodebench": "LiveCodeBench",
    "live code bench": "LiveCodeBench",
    # Aider
    "aider": "Aider",
    "aider polyglot": "Aider Polyglot",
    # EvalPlus
    "evalplus": "EvalPlus",
    # APPS
    "apps": "APPS",
    # HELMET
    "helmet": "HELMET",
    # Long-context / agentic
    "longbench": "LongBench",
    "needlebench": "NeedleBench",
    "agentbench": "AgentBench",
    "mt bench": "MT-Bench",
    "mt-bench": "MT-Bench",
    "mtbench": "MT-Bench",
    "lambada": "LAMBADA",
    # Efficiency / safety
    "latency": "Latency",
    "bias": "Bias",
    "toxicity": "Toxicity",
    # Edge / SLM
    "edgejson": "EdgeJSON",
    "edge intent": "EdgeIntent",
    "edgeintent": "EdgeIntent",
    "edge funccall": "EdgeFuncCall",
    "edge func call": "EdgeFuncCall",
    "edgefunccall": "EdgeFuncCall",
    "smol worldcup": "SMOL-WorldCup",
    "smol-worldcup": "SMOL-WorldCup",
    "tinymobilellm throughput": "TinyMobileLLM-Throughput",
    "tinymobilellm memory": "TinyMobileLLM-Memory",
}

# Benchmark names grouped for pattern construction
_BENCHMARK_NAMES = [
    # Order matters – more specific patterns first
    r"SWE[- ]bench\s+Verified\s*\(mini\)",
    r"SWE[- ]bench\s+Verified",
    r"SWE[- ]bench\s+Lite",
    r"SWE[- ]bench\s+Pro",
    r"SWE[- ]bench",
    r"SWE\s*bench",
    r"MMLU(?:\s+Pro)?",
    r"BBH",
    r"ARC[- ]?AGI",
    r"HumanEval(?:\+)?",
    r"GPQA\s+Diamond",
    r"GPQA",
    r"TruthfulQA",
    r"Truthful\s+QA",
    r"GSM8K",
    r"BIG[- ]?Bench(?:\s+Hard)?",
    r"ARC(?:\s+Challenge)?",
    r"HellaSwag",
    r"WinoGrande",
    r"MATH(?:\s+benchmark)?",
    r"MBPP",
    r"LiveCodeBench",
    r"Aider(?:\s+Polyglot)?",
    r"EvalPlus",
    r"APPS(?:\s+benchmark)?",
    r"HELMET",
    r"OpenCompass",
    r"LongBench",
    r"NeedleBench",
    r"AgentBench",
    r"MT[- ]?Bench",
    r"LAMBADA",
    r"Latency",
    r"Bias",
    r"Toxicity",
    r"EdgeJSON",
    r"EdgeIntent",
    r"EdgeFuncCall",
    r"SMOL[- ]?WorldCup",
    r"TinyMobileLLM[- ]Throughput",
    r"TinyMobileLLM[- ]Memory",
]

# Construct master pattern:
#  <value> [%] <benchmark>  OR  <benchmark> [of|:|-|at|score] <value> [%]
_NUM = r"(?P<value>\d{1,3}(?:\.\d{1,2})?)"
_PCT = r"\s*%?"
_BM = r"(?P<metric>" + "|".join(_BENCHMARK_NAMES) + r")"

_PATTERNS = [
    # "80.2% SWE-bench Verified"  /  "80.2 % on SWE-bench"
    re.compile(
        _NUM + _PCT + r"\s+(?:on\s+)?" + _BM,
        re.IGNORECASE,
    ),
    # "SWE-bench Verified: 80.2%"  /  "SWE-bench score of 80.2"
    re.compile(
        _BM + r"\s*(?:score\s+)?(?:of|:|–|-|at)?\s*" + _NUM + _PCT,
        re.IGNORECASE,
    ),
    # "achieves 80.2 on SWE-bench"
    re.compile(
        r"achieves?\s+" + _NUM + _PCT + r"\s+on\s+" + _BM,
        re.IGNORECASE,
    ),
    # "resolves 80.2% of SWE-bench"
    re.compile(
        r"resolves?\s+" + _NUM + _PCT + r"\s+(?:of\s+)?" + _BM,
        re.IGNORECASE,
    ),
    # "pass@1 of 80.2 on HumanEval"
    re.compile(
        r"pass@\d\s+(?:of\s+)?" + _NUM + _PCT + r"\s+on\s+" + _BM,
        re.IGNORECASE,
    ),
]


def _resolve_alias(raw_metric: str) -> str:
    """Return the canonical benchmark name, falling back to title-cased input."""
    key = raw_metric.strip().lower()
    return _ALIAS_TABLE.get(key, raw_metric.strip())


def _deduplicate(claims: list[Claim]) -> list[Claim]:
    """
    Keep only the highest-valued claim per canonical metric name to avoid
    double-counting when the same number appears in multiple phrasings.
    """
    seen: dict[str, Claim] = {}
    for c in claims:
        key = c.metric.lower()
        if key not in seen or c.value > seen[key].value:
            seen[key] = c
    return list(seen.values())


def extract_claims(
    text: str,
    source_url: str | None = None,
    deduplicate: bool = True,
) -> list[Claim]:
    """
    Extract all benchmark performance claims from *text*.

    Parameters
    ----------
    text:
        Raw model-card markdown or marketing text.
    source_url:
        Optional provenance URL stored on every returned Claim.
    deduplicate:
        When True (default) keep only the highest value per benchmark metric
        name to avoid inflating verified_claim counts.

    Returns
    -------
    A list of :class:`~trust_scorecard.models.Claim` objects.
    """
    claims: list[Claim] = []

    for pat in _PATTERNS:
        for m in pat.finditer(text):
            try:
                raw_metric = m.group("metric")
                raw_value = m.group("value")
                value = float(raw_value)
                if value > 100.0:
                    # Likely token counts or parameter sizes – skip
                    logger.debug("Skipping out-of-range claim value %s for %s", value, raw_metric)
                    continue
                canonical = _resolve_alias(raw_metric)
                # Determine variant / target (e.g. "Verified", "Lite")
                target: str | None = None
                lc = canonical.lower()
                if "verified" in lc:
                    target = "Verified"
                elif "lite" in lc:
                    target = "Lite"
                elif "pro" in lc:
                    target = "Pro"
                elif "diamond" in lc:
                    target = "Diamond"

                claim = Claim(
                    metric=canonical,
                    value=value,
                    raw=m.group(0).strip(),
                    target=target,
                    source_url=source_url,
                )
                claims.append(claim)
            except (IndexError, ValueError, KeyError) as exc:
                logger.debug("Pattern %s raised %s on %r – skipping", pat.pattern, exc, m.group(0))

    if deduplicate:
        claims = _deduplicate(claims)

    logger.debug("Extracted %d claim(s) from text (%d chars)", len(claims), len(text))
    return claims
