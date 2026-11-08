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

SYSTEM_PROMPT = """You are an OrbitLab experiment extractor. Read the user's orbital-simulation request and output ONE JSON object matching the schema below. Copy numbers exactly as written. Never compute, never convert units except by writing the unit field. Use null for anything the user did not state. Never invent values.

Schema (all keys always present):
{
  "centralBody": "Earth" | "Moon" | "Mars" | "Mercury" | "Venus" | "Jupiter" | "Sun" or null,
  "dryMassKg": number or null,
  "orbit": null or {"quantity": "altitude" | "periapsis_altitude" | "semi_major_axis" | "radius", "valueKm": number, "eccentricity": number or null},
  "inclinationDeg": number or null,
  "raanDeg": number or null,
  "argumentOfPeriapsisDeg": number or null,
  "trueAnomalyDeg": number or null,
  "duration": null or {"value": number, "unit": "seconds" | "hours" | "days" | "orbits"},
  "maneuvers": [{"type": "hohmann_transfer" | "impulsive_burn", "trigger": "periapsis" | "apoapsis" | "elapsed_seconds", "targetRadiusKm": number or null, "elapsedSecs": number or null, "deltaVKmS": [number, number, number] or null}]
}

Quantity meanings: "altitude" is the height above the surface of a circular orbit; "periapsis_altitude" is the height of the lowest point of an elliptical orbit; "semi_major_axis" is a stated semi-major axis; "radius" is a distance from the centre of the body (for a circular orbit it equals the semi-major axis). A bare circular-orbit distance is a radius only if the sentence says radius or distance from the centre, and an altitude only if it says altitude or height above the surface; otherwise leave orbit null. Spacecraft and experiment names are never extracted.

User: 200 kg satellite in a circular orbit at 550 km altitude around Mars for 10 days.
Assistant: {"centralBody": "Mars", "dryMassKg": 200, "orbit": {"quantity": "altitude", "valueKm": 550, "eccentricity": null}, "inclinationDeg": null, "raanDeg": null, "argumentOfPeriapsisDeg": null, "trueAnomalyDeg": null, "duration": {"value": 10, "unit": "days"}, "maneuvers": []}

User: 950 kg spacecraft around Jupiter with periapsis altitude 1200 km and eccentricity 0.15, propagated for 60 days.
Assistant: {"centralBody": "Jupiter", "dryMassKg": 950, "orbit": {"quantity": "periapsis_altitude", "valueKm": 1200, "eccentricity": 0.15}, "inclinationDeg": null, "raanDeg": null, "argumentOfPeriapsisDeg": null, "trueAnomalyDeg": null, "duration": {"value": 60, "unit": "days"}, "maneuvers": []}

User: 1500 kg probe around Mercury with semi-major axis 3500 km, eccentricity 0.1, inclination 45 degrees, propagated for 2 orbits.
Assistant: {"centralBody": "Mercury", "dryMassKg": 1500, "orbit": {"quantity": "semi_major_axis", "valueKm": 3500, "eccentricity": 0.1}, "inclinationDeg": 45, "raanDeg": null, "argumentOfPeriapsisDeg": null, "trueAnomalyDeg": null, "duration": {"value": 2, "unit": "orbits"}, "maneuvers": []}

User: 420 kg satellite at 250 km altitude above Venus with 10 degrees inclination for 8 hours.
Assistant: {"centralBody": "Venus", "dryMassKg": 420, "orbit": {"quantity": "altitude", "valueKm": 250, "eccentricity": null}, "inclinationDeg": 10, "raanDeg": null, "argumentOfPeriapsisDeg": null, "trueAnomalyDeg": null, "duration": {"value": 8, "unit": "hours"}, "maneuvers": []}

User: 60 kg spacecraft around the Moon in a circular orbit at 200 km altitude, propagated for 3 days.
Assistant: {"centralBody": "Moon", "dryMassKg": 60, "orbit": {"quantity": "altitude", "valueKm": 200, "eccentricity": null}, "inclinationDeg": null, "raanDeg": null, "argumentOfPeriapsisDeg": null, "trueAnomalyDeg": null, "duration": {"value": 3, "unit": "days"}, "maneuvers": []}

User: 2500 kg satellite around Mars in a 4200 km circular orbit, Hohmann transfer to 6000 km at apoapsis, propagated for 7 days.
Assistant: {"centralBody": "Mars", "dryMassKg": 2500, "orbit": {"quantity": "radius", "valueKm": 4200, "eccentricity": 0}, "inclinationDeg": null, "raanDeg": null, "argumentOfPeriapsisDeg": null, "trueAnomalyDeg": null, "duration": {"value": 7, "unit": "days"}, "maneuvers": [{"type": "hohmann_transfer", "trigger": "apoapsis", "targetRadiusKm": 6000, "elapsedSecs": null, "deltaVKmS": null}]}

User: A 900 kg spacecraft around the Sun.
Assistant: {"centralBody": "Sun", "dryMassKg": 900, "orbit": null, "inclinationDeg": null, "raanDeg": null, "argumentOfPeriapsisDeg": null, "trueAnomalyDeg": null, "duration": null, "maneuvers": []}"""

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

EXTRACTOR_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "centralBody": {"anyOf": [{"enum": ["Earth", "Moon", "Mars", "Mercury", "Venus", "Jupiter", "Sun"]}, {"type": "null"}]},
        "dryMassKg": {"type": ["number", "null"]},
        "orbit": {"anyOf": [{"type": "null"}, {"type": "object",
            "properties": {
                "quantity": {"type": "string", "enum": ["altitude", "periapsis_altitude", "semi_major_axis", "radius"]},
                "valueKm": {"type": "number"},
                "eccentricity": {"type": ["number", "null"]}},
            "required": ["quantity", "valueKm", "eccentricity"],
            "additionalProperties": False}]},
        "inclinationDeg": {"type": ["number", "null"]},
        "raanDeg": {"type": ["number", "null"]},
        "argumentOfPeriapsisDeg": {"type": ["number", "null"]},
        "trueAnomalyDeg": {"type": ["number", "null"]},
        "duration": {"anyOf": [{"type": "null"}, {"type": "object",
            "properties": {
                "value": {"type": "number"},
                "unit": {"type": "string", "enum": ["seconds", "hours", "days", "orbits"]}},
            "required": ["value", "unit"],
            "additionalProperties": False}]},
        "maneuvers": {"type": "array", "items": {"type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["hohmann_transfer", "impulsive_burn"]},
                "trigger": {"type": "string", "enum": ["periapsis", "apoapsis", "elapsed_seconds"]},
                "targetRadiusKm": {"type": ["number", "null"]},
                "elapsedSecs": {"type": ["number", "null"]},
                "deltaVKmS": {"anyOf": [{"type": "null"}, {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3}]}},
            "required": ["type", "trigger", "targetRadiusKm", "elapsedSecs", "deltaVKmS"],
            "additionalProperties": False}},
    },
    "required": ["centralBody", "dryMassKg", "orbit", "inclinationDeg", "raanDeg", "argumentOfPeriapsisDeg", "trueAnomalyDeg", "duration", "maneuvers"],
    "additionalProperties": False,
}

_NULL_STRINGS = frozenset(["", "unnamed", "none", "null"])


def _nullify_strings(obj):
    if isinstance(obj, dict):
        return {k: _nullify_strings(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_nullify_strings(v) for v in obj]
    if isinstance(obj, str) and obj.strip().lower() in _NULL_STRINGS:
        return None
    return obj


def _num_or_none(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        try:
            f = float(s)
            return f
        except (TypeError, ValueError):
            return None
    return None


def _has_number(v):
    if v is None or isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return True
    if isinstance(v, str):
        try:
            float(v.strip())
            return True
        except (TypeError, ValueError):
            return False
    return False


_LEGACY_ORBIT_KINDS = frozenset([
    "semiMajorAxisKm", "circularAltitudeKm", "circularAltitude",
    "periapsisAltitudeKm", "apsisAltitudes", "apoPeriRadii", "circularRadiusKm",
])

_NEW_QUANTITY_TO_KIND = {
    "altitude": "circularAltitudeKm",
    "periapsis_altitude": "periapsisAltitudeKm",
    "semi_major_axis": "semiMajorAxisKm",
    "radius": "circularRadiusKm",
}

_DURATION_UNIT_MAP = {
    "seconds": "seconds", "second": "seconds", "secs": "seconds", "sec": "seconds", "s": "seconds",
    "hours": "hours", "hour": "hours", "hrs": "hours", "hr": "hours", "h": "hours",
    "days": "days", "day": "days", "d": "days",
    "orbits": "orbits", "orbit": "orbits", "orbital periods": "orbits", "orbital period": "orbits",
}


def _norm_orbit(o):
    if o is None:
        return None
    if not isinstance(o, dict):
        return o
    qty = o.get("quantity", o.get("kind"))
    if qty in _NEW_QUANTITY_TO_KIND:
        kind = _NEW_QUANTITY_TO_KIND[qty]
        out = {"kind": kind, "value": o.get("valueKm", o.get("value")), "unit": "km"}
        ecc = o.get("eccentricity")
        if ecc is not None:
            out["eccentricity"] = ecc
        if kind == "periapsisAltitudeKm" and "eccentricity" not in out:
            out["eccentricity"] = 0
        return out
    if isinstance(o.get("kind"), str) and o.get("kind") not in _LEGACY_ORBIT_KINDS and "semiMajorAxisKm" not in o and "sma" not in o:
        vals = o.get("values", o.get("value"))
        if isinstance(vals, dict):
            if "periapsisAltitudeKm" in vals:
                out = {"kind": "periapsisAltitudeKm", "value": vals.get("periapsisAltitudeKm"), "unit": vals.get("unit", "km")}
                ev = vals.get("eccentricity", o.get("eccentricity", None))
                if ev is not None:
                    out["eccentricity"] = ev
                return out
            if "semiMajorAxisKm" in vals:
                out = {"kind": "semiMajorAxisKm", "value": vals.get("semiMajorAxisKm"), "unit": vals.get("unit", "km")}
                ev = vals.get("eccentricity", o.get("eccentricity", None))
                if ev is not None:
                    out["eccentricity"] = ev
                return out
        return {"kind": o.get("kind"), "values": vals, "unit": o.get("unit", "km")}
    return dict(o)


def _norm_maneuver(m, idx):
    if isinstance(m, str):
        low = m.lower()
        if "hohmann" in low:
            import re as _re
            r = None
            mt = _re.search(r"to\s+(\d+(?:\.\d+)?)\s*km", low)
            if mt:
                try:
                    r = float(mt.group(1))
                except (TypeError, ValueError):
                    r = None
            apsis = "apoapsis" if "apoapsis" in low or _re.search(r"\bapo\b", low) else "periapsis"
            return {"type": "Hohmann", "id": "M%d" % (idx + 1), "targetOrbitRadiusKm": r, "apsis": apsis}
        return None
    if not isinstance(m, dict):
        return None
    mtype = m.get("type")
    if isinstance(mtype, str) and mtype.lower() in ("hohmann_transfer", "impulsive_burn"):
        trig = m.get("trigger")
        if mtype.lower() == "hohmann_transfer":
            apsis = "apoapsis" if trig == "apoapsis" else "periapsis"
            out = {"type": "Hohmann", "id": m.get("id") or "M%d" % (idx + 1), "targetOrbitRadiusKm": m.get("targetRadiusKm"), "apsis": apsis}
            return out
        if trig == "elapsed_seconds":
            out = {"type": "ImpulsiveBurn", "id": m.get("id") or "M%d" % (idx + 1), "trigger": "ElapsedTimeSecs", "elapsedSecs": m.get("elapsedSecs"), "deltaV": list(m.get("deltaVKmS")) if isinstance(m.get("deltaVKmS"), list) else None}
        elif trig in ("periapsis", "apoapsis"):
            out = {"type": "ImpulsiveBurn", "id": m.get("id") or "M%d" % (idx + 1), "trigger": "AtPeriapsis" if trig == "periapsis" else "AtApoapsis", "apsis": trig, "deltaV": list(m.get("deltaVKmS")) if isinstance(m.get("deltaVKmS"), list) else None}
        else:
            out = {"type": "ImpulsiveBurn", "id": m.get("id") or "M%d" % (idx + 1), "trigger": "AtPeriapsis", "apsis": "periapsis", "deltaV": list(m.get("deltaVKmS")) if isinstance(m.get("deltaVKmS"), list) else None}
        return out
    return dict(m)


def _norm_duration(d, raw):
    if d is None:
        return None
    if isinstance(d, dict):
        value = d.get("value")
        unit = d.get("unit")
        if value is None:
            return {"value": None, "unit": unit}
        if not _has_number(value):
            return {"value": value, "unit": unit}
        if unit is None:
            return {"value": value, "unit": None}
        u = str(unit).strip().lower() if isinstance(unit, str) else str(unit).strip().lower()
        return {"value": value, "unit": _DURATION_UNIT_MAP.get(u, unit)}
    if isinstance(d, bool):
        return None
    if isinstance(d, (int, float)):
        unit = None
        if isinstance(raw, dict):
            unit = raw.get("durationUnit", raw.get("unit"))
        return {"value": d, "unit": unit}
    if isinstance(d, str):
        import re as _re
        s = d.strip()
        m = _re.match(r"^\s*([0-9]*\.?[0-9]+)\s*([A-Za-z ]+?)\s*$", s)
        if m:
            try:
                value = float(m.group(1))
            except (TypeError, ValueError):
                return {"value": s, "unit": None}
            u = m.group(2).strip().lower()
            return {"value": value, "unit": _DURATION_UNIT_MAP.get(u, u)}
        return {"value": s, "unit": None}
    return None


def normalize_extracted(raw):
    """Map model output (strict schema or tolerant variants) to converter input.

    Never invents values; unknown shapes pass through for the converter to
    clarify or fail on honestly.
    """
    if not isinstance(raw, dict):
        return {} if raw is None else raw
    out = dict(_nullify_strings(raw))
    out["orbit"] = _norm_orbit(out.get("orbit"))
    d = out.get("duration")
    if d is not None and not (isinstance(d, dict) and "value" in d and "unit" in d and _has_number(d.get("value")) and isinstance(d.get("unit"), str)):
        out["duration"] = _norm_duration(d, out)
    mans = out.get("maneuvers")
    if isinstance(mans, list):
        normed = []
        for idx, m in enumerate(mans):
            nm = _norm_maneuver(m, idx)
            if nm is not None:
                normed.append(nm)
        out["maneuvers"] = normed
    return out


class OpenAIExtractor(IFieldExtractor):
    def __init__(self, base_url=None, api_key=None, model=None, json_mode=None, timeout_s=None):
        s=get_settings()
        self.base_url=base_url or s.EXTRACTOR_BASE_URL
        self.api_key=api_key or s.EXTRACTOR_API_KEY
        self.model=model or s.EXTRACTOR_MODEL
        self.json_mode=(json_mode if json_mode is not None else getattr(s, "EXTRACTOR_JSON_MODE", "prompt") or "prompt").strip().lower()
        self.timeout_s=float(timeout_s) if timeout_s is not None else 30.0
        self.last_raw = None
        self.last_parsed = None
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
        elif self.json_mode=="json_schema":
            payload["response_format"]={"type":"json_schema","json_schema":{"name":"orbitlab_extraction","strict":True,"schema":EXTRACTOR_JSON_SCHEMA}}
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            r=await client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            data=r.json()
            content=data["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise ValueError("Unexpected content type: %s" % type(content))
            return content
    async def extract(self, user_text: str) -> Dict[str, Any]:
        raw = await self.extract_raw(user_text)
        self.last_raw = raw
        parsed = extract_json_object(raw)
        self.last_parsed = parsed
        return parsed
    def extract_sync(self, user_text: str) -> Dict[str, Any]:
        import asyncio
        return asyncio.run(self.extract(user_text))

def get_extractor() -> IFieldExtractor:
    s=get_settings()
    try:
        return OpenAIExtractor()
    except RuntimeError:
        return MockExtractor()
