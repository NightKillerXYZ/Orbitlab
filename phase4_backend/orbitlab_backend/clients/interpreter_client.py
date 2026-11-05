"""Interpreter HTTP client implementing IExperimentInterpreter."""
from __future__ import annotations
import asyncio, json
from typing import Any, Callable, Optional
from orbitlab_backend.config import get_settings
from phase3_ai_interpreter.interpreter.model import IExperimentInterpreter, InterpretationResult
from phase3_ai_interpreter.interpreter.json_interpreter import JsonExperimentInterpreter
try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

class InterpreterClientError(RuntimeError):
    pass
class InterpreterUnavailableError(InterpreterClientError):
    pass
class InterpreterClient:
    def interpret(self, raw_text: str) -> InterpretationResult:
        raise NotImplementedError
class MockInterpreterClient(IExperimentInterpreter):
    def __init__(self, canned_json=None):
        self.canned_json = canned_json
        self._json_interp = JsonExperimentInterpreter()
    def interpret(self, raw_text: str) -> InterpretationResult:
        payload = self.canned_json if self.canned_json is not None else raw_text
        return self._json_interp.interpret(payload)
    async def interpret_prompt(self, prompt: str, warming_callback=None):
        if self.canned_json:
            try:
                obj = json.loads(self.canned_json)
                if isinstance(obj, str):
                    obj = json.loads(obj)
                return obj
            except Exception:
                return json.loads(self.canned_json)
        return {'version': '1.0','experimentName': 'MockExp','spacecraft': {'name': 'SC_MockExp','dryMassKg': 500},'centralBody': 'Earth','initialOrbit': {'type': 'Keplerian','coordinateSystem': 'EarthMJ2000Eq','elements': {'semiMajorAxisKm': 6778.136,'eccentricity': 0,'inclinationDeg': 28.5,'raanDeg': 0,'argumentOfPeriapsisDeg': 0,'trueAnomalyDeg': 0}},'forceModel': {'gravityDegree': 4,'gravityOrder': 4,'pointMasses': ['Luna','Sun'],'atmosphericDrag': {'enabled': False,'model': 'JacchiaRoberts'},'solarRadiationPressure': True},'propagation': {'integrator': 'RungeKutta89','stopCondition': {'type': 'ElapsedHours','value': 2},'stepSizeSecs': 60},'maneuvers': []}
INTERPRETER_SYSTEM_PROMPT = (
    "The model is an OrbitLab Experiment Interpreter.\n"
    "\n"
    "It converts natural-language orbital-simulation requests into the exact OrbitLab Experiment JSON structure.\n"
    "\n"
    "Rules:\n"
    "- Output only the Experiment JSON when the request contains enough information for a valid experiment.\n"
    "- Never output raw GMAT script.\n"
    "- Never invent unsupported fields.\n"
    "- Never silently change user-specified physical parameters.\n"
    "- Use only fields supported by the actual OrbitLab schema.\n"
    "- Do not decide physical validity independently of OrbitLab validation.\n"
    "- Preserve the user's requested values and units after converting them to the schema's required units.\n"
    "- If required information is genuinely missing, the production system should request clarification rather than inventing a value.\n"
    "- The deterministic OrbitLab compiler, not the AI, is responsible for producing GMAT syntax."
)

def _strip_fences(text: str) -> str:
    s = text.strip()
    if s.startswith("```"):
        lines = s.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        s = "\n".join(lines).strip()
    return s

class HttpInterpreterClient(IExperimentInterpreter):
    def __init__(self, model_url=None, model_key=None, timeout_s=None, model_name=None):
        s=get_settings()
        self.model_url=model_url or s.ORBITLAB_MODEL_URL
        self.model_key=model_key or s.ORBITLAB_MODEL_KEY
        self.timeout_s=timeout_s if timeout_s is not None else float(s.ORBITLAB_MODEL_TIMEOUT_S)
        self.model_name=model_name or getattr(s, "ORBITLAB_MODEL_NAME", None) or "orbitlab-interpreter"
        if not self.model_url or not str(self.model_url).strip():
            raise RuntimeError("Missing required environment variable: ORBITLAB_MODEL_URL")
        if not self.model_key or not str(self.model_key).strip():
            raise RuntimeError("Missing required environment variable: ORBITLAB_MODEL_KEY")
        self._json_interp=JsonExperimentInterpreter()
    def interpret(self, raw_text: str) -> InterpretationResult:
        return self._json_interp.interpret(raw_text)
    async def interpret_prompt(self, prompt: str, warming_callback=None):
        # OpenAI-compatible chat completions contract: POST
        # {base_url}/v1/chat/completions with system+user messages and
        # Authorization: Bearer <key>; the experiment JSON is read from
        # choices[0].message.content.
        if not HAS_HTTPX:
            raise InterpreterUnavailableError("httpx not installed")
        url=self.model_url.rstrip("/")+"/v1/chat/completions"
        headers={"Authorization": f"Bearer {self.model_key}","Content-Type": "application/json"}
        payload={"model": self.model_name,"messages": [{"role":"system","content": INTERPRETER_SYSTEM_PROMPT},{"role":"user","content": prompt}],"temperature":0}
        async def single_attempt():
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                task=asyncio.create_task(client.post(url, json=payload, headers=headers))
                done,pending=await asyncio.wait([task], timeout=10)
                if not done:
                    if warming_callback:
                        try:
                            r=warming_callback()
                            if asyncio.iscoroutine(r):
                                await r
                        except Exception:
                            pass
                    rem=self.timeout_s-10
                    if rem<0: rem=self.timeout_s
                    done2,pending2=await asyncio.wait([task], timeout=rem)
                    if not done2:
                        task.cancel()
                        raise InterpreterUnavailableError(f"Interpreter timeout after {self.timeout_s}s")
                    result=task.result()
                else:
                    result=task.result()
                if result.status_code in (502,503,504):
                    raise InterpreterUnavailableError(f"Interpreter returned {result.status_code}")
                result.raise_for_status()
                data=result.json()
                try:
                    content=data["choices"][0]["message"]["content"]
                except (KeyError, IndexError, TypeError) as e:
                    raise ValueError(f"Unexpected chat-completions response shape: {str(data)[:200]}") from e
                if isinstance(content, dict):
                    return content
                if not isinstance(content, str):
                    raise ValueError(f"Unexpected content type: {type(content)}")
                try:
                    return json.loads(_strip_fences(content))
                except json.JSONDecodeError:
                    raise ValueError(f"Invalid JSON string: {content[:200]}")
        last=None
        # Retry exactly once, and only for timeout/502/503/504 (raised as
        # InterpreterUnavailableError). All other errors propagate immediately.
        for attempt in range(2):
            try:
                return await single_attempt()
            except InterpreterUnavailableError as e:
                last=e
                if attempt==0:
                    await asyncio.sleep(1)
                    continue
                raise
            except Exception:
                raise
        if last:
            raise last
        raise InterpreterUnavailableError("Interpreter unavailable")
def get_interpreter_client():
    s=get_settings()
    if s.ORBITLAB_USE_MOCK_INTERPRETER:
        return MockInterpreterClient()
    try:
        return HttpInterpreterClient()
    except RuntimeError:
        return MockInterpreterClient()
