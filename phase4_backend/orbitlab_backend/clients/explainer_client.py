"""IPhysicsExplainer with mock and OpenAI-compatible impl."""
from __future__ import annotations
import asyncio
import logging
import math
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from orbitlab_backend.config import get_settings
try:
    import httpx
    HAS_HTTPX=True
except ImportError:
    httpx=None  # type: ignore
    HAS_HTTPX=False

logger = logging.getLogger("orbitlab.explainer")

EXPLAIN_SYSTEM = ("You are an orbital mechanics tutor. Using ONLY the numbers given, "
                  "explain in 4 to 6 short plain-English sentences what this simulation shows "
                  "and what the student should notice. Do not invent numbers. No markdown headings.")

EXPLAIN_MAX_TOKENS = 400
USER_MESSAGE_CAP = 1500
ERROR_TEXT_CAP = 600


def _num(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _first(mapping: Any, *keys: str) -> Any:
    if not isinstance(mapping, dict):
        return None
    for key in keys:
        if mapping.get(key) is not None:
            return mapping.get(key)
    return None


def _body_constants(central_body: Any) -> tuple[Optional[float], Optional[float]]:
    """Return (radius_km, mu_km3_s2) using the repo's body tables. Never raises."""
    try:
        if isinstance(central_body, str) and central_body:
            try:
                from orbitlab_core.ast.validation import get_body_constants
                radius, mu = get_body_constants(central_body)
                return float(radius), float(mu)
            except Exception:
                pass
            try:
                from orbitlab_backend.frontstep.conversions import BODY_RADII_KM
                radius = BODY_RADII_KM.get(central_body)
                return (float(radius), None) if radius else (None, None)
            except Exception:
                pass
    except Exception:
        pass
    return None, None


def _fmt_period(seconds: Optional[float]) -> Optional[str]:
    if seconds is None or seconds <= 0:
        return None
    hours = seconds / 3600.0
    if hours >= 1.0:
        return "about %.2f hours" % hours
    minutes = seconds / 60.0
    if minutes >= 1.0:
        return "about %.1f minutes" % minutes
    return "about %.0f seconds" % seconds


def _digest_values(experiment: Any, stage: Any, error: Any,
                   warnings: Any, trajectory_summary: Any) -> Dict[str, Any]:
    """Pull a small structured digest out of the raw dicts. Never raises."""
    out: Dict[str, Any] = {}
    try:
        exp = experiment if isinstance(experiment, dict) else {}
        out["body"] = exp.get("centralBody") if isinstance(exp.get("centralBody"), str) else None
        sc = exp.get("spacecraft") if isinstance(exp.get("spacecraft"), dict) else {}
        out["mass"] = _num(sc.get("dryMassKg"))
        orb = exp.get("initialOrbit") if isinstance(exp.get("initialOrbit"), dict) else {}
        out["orbit_type"] = orb.get("type") if isinstance(orb.get("type"), str) else None
        els = orb.get("elements") if isinstance(orb.get("elements"), dict) else {}
        for key in ("semiMajorAxisKm", "eccentricity", "inclinationDeg", "raanDeg",
                    "argumentOfPeriapsisDeg", "trueAnomalyDeg"):
            out[key] = _num(els.get(key))
        prop = exp.get("propagation") if isinstance(exp.get("propagation"), dict) else {}
        out["integrator"] = prop.get("integrator") if isinstance(prop.get("integrator"), str) else None
        stop = prop.get("stopCondition") if isinstance(prop.get("stopCondition"), dict) else {}
        stop_type = stop.get("type") if isinstance(stop.get("type"), str) else None
        stop_val = _num(stop.get("value"))
        out["stop"] = "%s %s" % (stop_type, ("%g" % stop_val)) if stop_type and stop_val is not None else stop_type
        fm = exp.get("forceModel") if isinstance(exp.get("forceModel"), dict) else {}
        drag = fm.get("atmosphericDrag") if isinstance(fm.get("atmosphericDrag"), dict) else {}
        parts = []
        deg = _num(fm.get("gravityDegree")); order = _num(fm.get("gravityOrder"))
        if deg is not None and order is not None:
            parts.append("gravity %gx%g" % (deg, order))
        pm = fm.get("pointMasses")
        if isinstance(pm, list) and pm:
            parts.append("point masses " + ",".join(str(p) for p in pm[:4]))
        if isinstance(drag.get("enabled"), bool):
            parts.append("drag %s" % ("on" if drag.get("enabled") else "off"))
        if isinstance(fm.get("solarRadiationPressure"), bool):
            parts.append("SRP %s" % ("on" if fm.get("solarRadiationPressure") else "off"))
        out["forces"] = "; ".join(parts) or None
        out["maneuvers"] = []
        mans = exp.get("maneuvers")
        if isinstance(mans, list):
            for man in mans[:4]:
                if not isinstance(man, dict):
                    continue
                trig = man.get("trigger") if isinstance(man.get("trigger"), dict) else {}
                burn = man.get("burnVector") if isinstance(man.get("burnVector"), dict) else {}
                vec = burn.get("deltaVVectorKmS")
                dv = None
                if isinstance(vec, (list, tuple)) and len(vec) == 3:
                    comps = [_num(c) for c in vec]
                    if all(c is not None for c in comps):
                        dv = math.sqrt(sum(c * c for c in comps))  # type: ignore
                tgt = man.get("targetObjectives") if isinstance(man.get("targetObjectives"), dict) else {}
                out["maneuvers"].append({
                    "type": man.get("type") if isinstance(man.get("type"), str) else None,
                    "trigger": trig.get("condition") if isinstance(trig.get("condition"), str) else None,
                    "dv": dv,
                    "target": _num(tgt.get("targetOrbitRadiusKm")),
                })
        radius, mu = _body_constants(out["body"])
        out["radius"] = radius
        a = out.get("semiMajorAxisKm")
        e = out.get("eccentricity")
        if radius and a and a > 0:
            out["periapsis_alt"] = a * (1.0 - (e or 0.0)) - radius
            out["apoapsis_alt"] = a * (1.0 + (e or 0.0)) - radius
        else:
            out["periapsis_alt"] = None
            out["apoapsis_alt"] = None
        if mu and a and a > 0 and e is not None and 0.0 <= e < 1.0:
            out["period_s"] = 2.0 * math.pi * math.sqrt((a ** 3) / mu)
        else:
            out["period_s"] = None
        warns = warnings if isinstance(warnings, list) else []
        out["warnings"] = [str(w)[:200] for w in warns if w is not None][:5]
        ts = trajectory_summary if isinstance(trajectory_summary, dict) else {}
        out["traj_n"] = _first(ts, "num_points", "numPoints", "n", "count")
        if out["traj_n"] is not None:
            try:
                out["traj_n"] = int(out["traj_n"])
            except (TypeError, ValueError):
                out["traj_n"] = None
        out["traj_min_alt"] = _num(_first(ts, "min_altitude_km", "minAltitudeKm", "min_altitude"))
        out["traj_max_alt"] = _num(_first(ts, "max_altitude_km", "maxAltitudeKm", "max_altitude"))
        out["traj_final_alt"] = _num(_first(ts, "final_altitude_km", "finalAltitudeKm", "final_altitude"))
        out["traj_final_speed"] = _num(_first(ts, "final_speed_km_s", "finalSpeedKmS", "final_speed"))
        if isinstance(error, str) and error:
            out["error"] = error[:ERROR_TEXT_CAP]
        else:
            out["error"] = None
        out["stage"] = stage if isinstance(stage, str) else None
    except Exception:
        pass
    return out


def build_explain_digest(experiment: Any, stage: Any, error: Any,
                         warnings: Any, trajectory_summary: Any = None) -> str:
    """Small structured user message (~capped), never a raw dump. Never raises."""
    try:
        v = _digest_values(experiment, stage, error, warnings, trajectory_summary)
        bits: List[str] = []
        if v.get("body"):
            bits.append("central body %s" % v["body"])
        if v.get("mass") is not None:
            bits.append("dry mass %.1f kg" % v["mass"])
        if v.get("orbit_type"):
            bits.append("orbit type %s" % v["orbit_type"])
        if v.get("semiMajorAxisKm") is not None:
            bits.append("semi-major axis %.3f km" % v["semiMajorAxisKm"])
        if v.get("eccentricity") is not None:
            bits.append("eccentricity %g" % v["eccentricity"])
        if v.get("inclinationDeg") is not None:
            bits.append("inclination %.2f deg" % v["inclinationDeg"])
        if v.get("raanDeg") is not None:
            bits.append("RAAN %.2f deg" % v["raanDeg"])
        if v.get("argumentOfPeriapsisDeg") is not None:
            bits.append("argument of periapsis %.2f deg" % v["argumentOfPeriapsisDeg"])
        if v.get("trueAnomalyDeg") is not None:
            bits.append("true anomaly %.2f deg" % v["trueAnomalyDeg"])
        if v.get("periapsis_alt") is not None:
            bits.append("periapsis altitude %.1f km" % v["periapsis_alt"])
        if v.get("apoapsis_alt") is not None:
            bits.append("apoapsis altitude %.1f km" % v["apoapsis_alt"])
        period = _fmt_period(v.get("period_s"))
        if period:
            bits.append("orbital period %s" % period)
        if v.get("stop"):
            bits.append("stop condition %s" % v["stop"])
        for man in v.get("maneuvers") or []:
            desc = man.get("type") or "maneuver"
            if man.get("trigger"):
                desc += " triggered %s" % man["trigger"]
            if man.get("target") is not None:
                desc += " to radius %.1f km" % man["target"]
            if man.get("dv") is not None:
                desc += " delta-v %.3f km/s" % man["dv"]
            bits.append(desc)
        if v.get("forces"):
            bits.append("forces: %s" % v["forces"])
        for w in v.get("warnings") or []:
            bits.append("warning: %s" % w)
        if v.get("traj_n") is not None:
            bits.append("trajectory points %d" % v["traj_n"])
        if v.get("traj_min_alt") is not None:
            bits.append("min altitude %.1f km" % v["traj_min_alt"])
        if v.get("traj_max_alt") is not None:
            bits.append("max altitude %.1f km" % v["traj_max_alt"])
        if v.get("traj_final_alt") is not None:
            bits.append("final altitude %.1f km" % v["traj_final_alt"])
        if v.get("traj_final_speed") is not None:
            bits.append("final speed %.3f km/s" % v["traj_final_speed"])
        text = "Simulation facts: " + ("; ".join(bits) if bits else "no orbital data available") + "."
        if v.get("error"):
            text += " The run failed at stage '%s': %s." % (v.get("stage") or "unknown", v["error"])
            text += " In 2 to 4 short sentences explain what went wrong and what the student should change."
        msg = text[:USER_MESSAGE_CAP]
        return msg
    except Exception:
        return "Simulation facts: unavailable."


def fallback_explanation(experiment: Any, stage: Any, error: Any,
                         warnings: Any, trajectory_summary: Any = None) -> str:
    """Deterministic model-free summary, 4-6 plain sentences. Never raises."""
    try:
        v = _digest_values(experiment, stage, error, warnings, trajectory_summary)
        sentences: List[str] = []
        body = v.get("body") or "the central body"
        if v.get("mass") is not None:
            sentences.append("This simulation flies a %.1f kg spacecraft around %s." % (v["mass"], body))
        else:
            sentences.append("This simulation flies a spacecraft around %s." % body)
        a = v.get("semiMajorAxisKm")
        e = v.get("eccentricity")
        if a is not None:
            shape = "nearly circular" if (e is not None and e < 0.05) else ("elliptical" if e else "nearly circular")
            if e is not None:
                sentences.append("The orbit is %s with a semi-major axis of %.3f km and eccentricity %g." % (shape, a, e))
            else:
                sentences.append("The orbit has a semi-major axis of %.3f km." % a)
        rp = v.get("periapsis_alt")
        ra = v.get("apoapsis_alt")
        if rp is not None and ra is not None:
            sentences.append("Periapsis altitude is %.1f km and apoapsis altitude is %.1f km." % (rp, ra))
        period = _fmt_period(v.get("period_s"))
        if period:
            sentences.append("One full orbit takes %s." % period)
        if v.get("inclinationDeg") is not None:
            sentences.append("The orbit is inclined %.2f degrees to the equator." % v["inclinationDeg"])
        if v.get("stop"):
            sentences.append("The simulation runs until %s." % v["stop"])
        for man in v.get("maneuvers") or []:
            if man.get("type") == "TargetedHohmannTransfer" and man.get("target") is not None:
                where = (" at %s" % man["trigger"]) if man.get("trigger") else ""
                sentences.append("It includes a Hohmann transfer%s to a %.1f km radius orbit." % (where, man["target"]))
            elif man.get("dv") is not None:
                sentences.append("It includes a maneuver with a delta-v of %.3f km/s." % man["dv"])
        for w in (v.get("warnings") or [])[:2]:
            sentences.append("Validator note: %s." % w)
        if v.get("traj_final_alt") is not None:
            sentences.append("The trajectory ends at %.1f km altitude." % v["traj_final_alt"])
        text = " ".join(sentences) if sentences else "The simulation completed."
        return text
    except Exception:
        return "The simulation completed."


def failure_explanation(stage: Any, error: Any) -> str:
    """Deterministic one-sentence error summary. Never raises."""
    try:
        name = stage if isinstance(stage, str) and stage else "unknown"
        detail = error if isinstance(error, str) and error else "an error occurred"
        return "The run stopped at the %s stage: %s." % (name, detail[:ERROR_TEXT_CAP])
    except Exception:
        return "The run stopped with an error."


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
    def __init__(self, base_url=None, api_key=None, model=None, timeout_s=None):
        s=get_settings()
        self.base_url=base_url or s.EXTRACTOR_BASE_URL
        self.api_key=api_key or s.EXTRACTOR_API_KEY
        self.model=model or s.EXTRACTOR_MODEL
        try:
            self.timeout_s=float(timeout_s) if timeout_s is not None else float(getattr(s, "EXTRACTOR_TIMEOUT_S", 150.0) or 150.0)
        except (TypeError, ValueError):
            self.timeout_s=150.0
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
        failed = error is not None or (isinstance(stage, str) and stage != "success")
        user_message=build_explain_digest(experiment, stage, error, warnings, trajectory_summary)
        payload={"model": self.model, "messages":[{"role":"system","content": EXPLAIN_SYSTEM},{"role":"user","content": user_message}], "temperature": 0 if failed else 0.2, "max_tokens": EXPLAIN_MAX_TOKENS}
        last=None
        # Retry exactly once, and only for timeouts or HTTP 502/503/504.
        # All other errors propagate immediately. Any final failure logs ONE
        # warning line (exception class + first 200 chars; never headers/keys).
        try:
            for attempt in range(2):
                try:
                    async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                        r=await client.post(url, json=payload, headers=headers)
                    if r.status_code in (502,503,504):
                        last=RuntimeError(f"explainer returned HTTP {r.status_code}")
                        if attempt==0:
                            await asyncio.sleep(1)
                            continue
                        break
                    r.raise_for_status()
                    data=r.json()
                    try:
                        content=data["choices"][0]["message"]["content"]
                    except (KeyError, IndexError, TypeError) as e:
                        raise ValueError(f"Unexpected chat-completions response shape: {str(data)[:200]}") from e
                    if not isinstance(content, str):
                        raise ValueError(f"Unexpected content type: {type(content)}")
                    return content
                except httpx.TimeoutException as e:
                    last=e
                    if attempt==0:
                        await asyncio.sleep(1)
                        continue
                    break
                except Exception:
                    raise
            if last is None:
                last=RuntimeError("explainer unavailable")
            raise last
        except Exception as e:
            logger.warning("explainer failed: %s: %s", type(e).__name__, str(e)[:200])
            raise

def get_explainer()->IPhysicsExplainer:
    s=get_settings()
    if getattr(s, "ORBITLAB_DEMO_MODE", False):
        return MockExplainer()
    try:
        return OpenAIExplainer()
    except RuntimeError:
        return MockExplainer()
