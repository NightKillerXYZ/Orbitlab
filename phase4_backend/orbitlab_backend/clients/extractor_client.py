"""IFieldExtractor interface with mock and OpenAI-compatible impl."""
from __future__ import annotations
import json
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from orbitlab_backend.config import get_settings
try:
    import httpx
    HAS_HTTPX=True
except ImportError:
    HAS_HTTPX=False

SYSTEM_PROMPT = """You are a field extractor. Extract structured fields from user text exactly as given, do not compute. Output JSON with keys: centralBody, spacecraftName, experimentName, dryMassKg, orbit (with kind and values), eccentricity, inclinationDeg, raanDeg, aopDeg, trueAnomalyDeg, integrator, duration, forces, maneuvers, cartesian. Numbers must be exact as user gave them."""

class IFieldExtractor(ABC):
    @abstractmethod
    async def extract(self, user_text: str) -> Dict[str, Any]:
        raise NotImplementedError
    @abstractmethod
    def extract_sync(self, user_text: str) -> Dict[str, Any]:
        raise NotImplementedError

class MockExtractor(IFieldExtractor):
    def __init__(self, canned: Optional[Dict[str, Any]] = None):
        self.canned = canned
    async def extract(self, user_text: str) -> Dict[str, Any]:
        return self.extract_sync(user_text)
    def extract_sync(self, user_text: str) -> Dict[str, Any]:
        if self.canned is not None:
            return self.canned
        # Simple deterministic fallback: try to parse basic patterns
        t = user_text.lower()
        body = "Earth"
        for b in ["Earth","Moon","Mars","Mercury","Venus","Jupiter","Sun"]:
            if b.lower() in t:
                body=b
                break
        # Very minimal mock
        return {"centralBody": body, "spacecraftName": None, "experimentName": None, "dryMassKg": None, "orbit": None, "eccentricity": None, "inclinationDeg": None, "raanDeg": None, "aopDeg": None, "trueAnomalyDeg": None, "integrator": None, "duration": None, "forces": None, "maneuvers": [], "cartesian": None, "raw_text": user_text}

def extract_json_object(text):
    """Return the first balanced {...} JSON object found in text (fences/prose tolerated).

    Raises ValueError when no balanced object parses. Never invents content.
    """
    s=text if isinstance(text, str) else ""
    stripped=s.strip()
    if stripped.startswith("{"):
        try:
            obj=json.loads(stripped)
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
    i=0
    n=len(s)
    while i<n:
        if s[i]!="{": i+=1; continue
        depth=0; in_str=False; esc=False; j=i
        while j<n:
            ch=s[j]
            if in_str:
                if esc: esc=False
                elif ch=="\\": esc=True
                elif ch=='"': in_str=False
            else:
                if ch=='"': in_str=True
                elif ch=="{": depth+=1
                elif ch=="}":
                    depth-=1
                    if depth==0: break
            j+=1
        if depth==0 and j<n:
            cand=s[i:j+1]
            try:
                obj=json.loads(cand)
                if isinstance(obj, dict):
                    return obj
            except Exception:
                pass
            i=j+1
        else:
            i+=1
    raise ValueError("No JSON object found in reply: %s" % s[:200])

class OpenAIExtractor(IFieldExtractor):
    def __init__(self, base_url=None, api_key=None, model=None, json_mode=None, timeout_s=None):
        s=get_settings()
        self.base_url=base_url or s.EXTRACTOR_BASE_URL
        self.api_key=api_key or s.EXTRACTOR_API_KEY
        self.model=model or s.EXTRACTOR_MODEL
        self.json_mode=(json_mode if json_mode is not None else getattr(s, "EXTRACTOR_JSON_MODE", "prompt") or "prompt").strip().lower()
        self.timeout_s=float(timeout_s) if timeout_s is not None else 30.0
        if not self.base_url or not str(self.base_url).strip():
            raise RuntimeError("Missing required environment variable: EXTRACTOR_BASE_URL")
        if not self.api_key or not str(self.api_key).strip():
            raise RuntimeError("Missing required environment variable: EXTRACTOR_API_KEY")
        if not self.model or not str(self.model).strip():
            raise RuntimeError("Missing required environment variable: EXTRACTOR_MODEL")
    async def extract_raw(self, user_text: str) -> str:
        """Return the raw chat content string (for debugging)."""
        if not HAS_HTTPX:
            raise RuntimeError("httpx not installed")
        url = self.base_url.rstrip("/") + "/chat/completions"
        headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload={"model": self.model, "messages": [{"role":"system","content": SYSTEM_PROMPT},{"role":"user","content": user_text}], "temperature":0}
        if self.json_mode=="json_object":
            payload["response_format"]={"type":"json_object"}
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            r=await client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            data=r.json()
            content=data["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise ValueError("Unexpected content type: %s" % type(content))
            return content
    async def extract(self, user_text: str) -> Dict[str, Any]:
        return extract_json_object(await self.extract_raw(user_text))
    def extract_sync(self, user_text: str) -> Dict[str, Any]:
        import asyncio
        return asyncio.run(self.extract(user_text))

def get_extractor() -> IFieldExtractor:
    s=get_settings()
    try:
        return OpenAIExtractor()
    except RuntimeError:
        return MockExtractor()
