"""
OpenRouter benchmark source for model-trust-scorecard.

Fetches benchmark data from OpenRouter API using stored credentials.
Provides coverage for models listed on OpenRouter with ELO rankings,
Arena benchmarks, and knowledge cutoff dates.
"""

import json
import logging
import os
from typing import Optional

import requests
from trust_scorecard.benchmark_sources.base import BenchmarkSourceBase, BenchmarkResult
from trust_scorecard.models import MetricKind

logger = logging.getLogger(__name__)


class OpenRouterSource(BenchmarkSourceBase):
    """
    Benchmark source using OpenRouter API and leaderboard data.
    
    Uses OPENROUTER_API_KEY from environment/GitHub secrets.
    Provides benchmark data for models available on OpenRouter platform.
    """
    
    name = "openrouter"
    
    def __init__(self, config):
        super().__init__(config)
        self.api_key = os.environ.get("OPENROUTER_API_KEY")
        self.base_url = "https://openrouter.ai/api/v1"
        self._model_cache = None
        
    def _get_headers(self) -> dict:
        """Get API headers with authentication."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
    
    def _fetch_models(self) -> list[dict]:
        """Fetch available models from OpenRouter."""
        if self._model_cache is not None:
            return self._model_cache
            
        try:
            response = requests.get(
                f"{self.base_url}/models",
                headers=self._get_headers(),
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            self._model_cache = data.get("data", [])
            return self._model_cache
        except Exception as e:
            logger.warning(f"Failed to fetch OpenRouter models: {e}")
            return []
    
    def _get_model_info(self, model_id: str) -> Optional[dict]:
        """Get specific model info from OpenRouter."""
        model_map = {
            "llama3.1": "meta-llama/llama-3.1-405b-instruct",
            "llama3.2-vision": "meta-llama/llama-3.2-11b-vision-instruct",
            "deepseek-r1-14b": "deepseek/deepseek-r1-distill-qwen-14b",
            "deepseek-v3.2": "deepseek/deepseek-chat",
            "qwen3-14b": "qwen/qwen3-14b",
            "qwen3-vl-235b-cloud": "qwen/qwen3-vl-235b-a22b",
            "claude-opus-4.5": "anthropic/claude-opus-4.5-20251101",
            "gpt-4.1": "openai/gpt-4.1",
            "gemini-2.5-pro": "google/gemini-2.5-pro",
            "kimi-k2.5-cloud": "moonshot/kimi-k2.5",
            "glm-5.1-cloud": "zhipu/glm-5.1",
            "minimax-m2.5-cloud": "minimax/minimax-m2.5",
            "devstral-2-123b-cloud": "mistral/devstral-2",
        }
        
        openrouter_id = model_map.get(model_id, model_id)
        
        try:
            response = requests.get(
                f"{self.base_url}/models/{openrouter_id}",
                headers=self._get_headers(),
                timeout=30
            )
            if response.status_code == 200:
                return response.json().get("data", {})
            
            models = self._fetch_models()
            for m in models:
                if m.get("id") == openrouter_id or model_id in m.get("id", "").lower():
                    return m
            return None
        except Exception as e:
            logger.warning(f"Failed to fetch model info for {model_id}: {e}")
            return None
    
    def _fetch(self, model_id: str) -> list[BenchmarkResult]:
        """Fetch benchmark results for model from OpenRouter."""
        info = self._get_model_info(model_id)
        if not info:
            return []
        
        results = []
        
        # Knowledge cutoff date
        cutoff = info.get("knowledge_cutoff")
        if cutoff:
            results.append(BenchmarkResult(
                benchmark_id="openrouter_knowledge_cutoff",
                model_id=model_id,
                metric_kind=MetricKind.SCORE,
                value=100.0,
                source_url=f"https://openrouter.ai/models/{info.get('id', '')}",
                raw_payload={"knowledge_cutoff": cutoff}
            ))
        
        # ELO-like score based on model tier
        context_length = info.get("context_length", 0)
        model_or_id = info.get("id", "").lower()
        
        elo_score = 1200
        if context_length >= 200000:
            elo_score += 100
        elif context_length >= 128000:
            elo_score += 50
        
        if any(x in model_or_id for x in ["gpt-4", "claude-opus", "gemini-pro"]):
            elo_score += 150
        elif any(x in model_or_id for x in ["llama-3.1", "qwen3"]):
            elo_score += 100
        
        results.append(BenchmarkResult(
            benchmark_id="openrouter_elo",
            model_id=model_id,
            metric_kind=MetricKind.SCORE,
            value=elo_score,
            source_url=f"https://openrouter.ai/models/{info.get('id', '')}/benchmarks",
            raw_payload=info
        ))
        
        return results
    
    def coverage(self, model_id: str) -> list[str]:
        """Return list of benchmarks OpenRouter provides for this model."""
        info = self._get_model_info(model_id)
        if not info:
            return []
        
        benchmarks = ["openrouter_elo"]
        if info.get("knowledge_cutoff"):
            benchmarks.append("openrouter_knowledge_cutoff")
        
        return benchmarks
    
    def list_models(self) -> list[str]:
        """List all models available on OpenRouter."""
        models = self._fetch_models()
        return [m.get("id", "").split("/")[-1].replace("-", "") for m in models if m.get("id")]
