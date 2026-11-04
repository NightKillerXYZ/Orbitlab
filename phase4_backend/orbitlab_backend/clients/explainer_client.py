"""IPhysicsExplainer with mock and OpenAI-compatible impl."""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from orbitlab_backend.config import get_settings
try:
    import httpx
    HAS_HTTPX=True
except ImportError:
    HAS_HTTPX=False

class IPhysicsExplainer(ABC):
    @abstractmethod
    async def explain(self, experiment: Optional[Dict[str, Any]], stage: str, error: Optional[str], warnings: list, trajectory_summary: Optional[Dict]=None) -> str:
        raise NotImplementedError

class MockExplainer(IPhysicsExplainer):
    async def explain(self, experiment, stage, error, warnings, trajectory_summary=None) -> str:
        if error:
            return f"Mock explanation for failure at {stage}: {error}. Warnings: {warnings}"
        return f"Mock explanation for successful run at {stage}. Warnings: {warnings}"

class OpenAIExplainer(IPhysicsExplainer):
    def __init__(self, base_url=None, api_key=None, model=None):
        s=get_settings()
        self.base_url=base_url or s.EXTRACTOR_BASE_URL
        self.api_key=api_key or s.EXTRACTOR_API_KEY
        self.model=model or s.EXTRACTOR_MODEL
        if not self.base_url or not str(self.base_url).strip():
            raise RuntimeError("Missing required environment variable: EXTRACTOR_BASE_URL")
        if not self.api_key or not str(self.api_key).strip():
            raise RuntimeError("Missing required environment variable: EXTRACTOR_API_KEY")
        if not self.model or not str(self.model).strip():
            raise RuntimeError("Missing required environment variable: EXTRACTOR_MODEL")
    async def explain(self, experiment, stage, error, warnings, trajectory_summary=None) -> str:
        if not HAS_HTTPX:
            raise RuntimeError("httpx not installed")
        url=self.base_url.rstrip("/")+"/chat/completions"
        headers={"Authorization": f"Bearer {self.api_key}", "Content-Type":"application/json"}
        prompt=f"Explain physics for experiment {experiment} at stage {stage} error {error} warnings {warnings} trajectory {trajectory_summary}"
        payload={"model": self.model, "messages":[{"role":"system","content":"You are an orbital mechanics explainer."},{"role":"user","content": prompt}], "temperature":0}
        async with httpx.AsyncClient(timeout=30) as client:
            r=await client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            data=r.json()
            return data["choices"][0]["message"]["content"]

def get_explainer()->IPhysicsExplainer:
    s=get_settings()
    try:
        return OpenAIExplainer()
    except RuntimeError:
        return MockExplainer()
