"""Front-step extractor orchestrating deterministic conversions."""
from __future__ import annotations
import logging
import re
from typing import Any, Dict, List, Optional
from .conversions import BODY_RADII_KM, sma_from_circular_altitude, sma_from_periapsis_altitude, sma_and_ecc_from_apses_altitudes, convert_miles_to_km, convert_m_to_km, convert_au_to_km, radians_to_degrees, convert_duration_to_hours_or_days
from .verify import sanitize_identifier

_logger = logging.getLogger("orbitlab.frontstep")

def _safe_summary(exc):
    kind = type(exc).__name__
    msg = str(exc)
    return kind, msg[:200]

def _log_extractor_failure(exc):
    kind, summary = _safe_summary(exc)
    _logger.warning("extractor failed (%s); falling back to regex: %s", kind, summary)

def _log_extractor_ok(extracted):
    try:
        names = sorted(k for k in dict(extracted or {}).keys())
    except Exception:
        names = []
    _logger.info("extractor ok; fields: %s", ",".join(names))


def _usable_delta_v(m):
    """True when a normalized maneuver carries a usable 3-component delta-V."""
    try:
        dv = m.get("deltaV") if isinstance(m, dict) else None
    except AttributeError:
        return False
    if not isinstance(dv, (list, tuple)) or len(dv) < 3:
        return False
    try:
        return all(float(x) == float(x) for x in dv[:3])
    except (TypeError, ValueError):
        return False


def _missing_burn_size(maneuvers):
    """ImpulsiveBurn entries without a usable delta-V cannot run.

    Burns defined by a target radius/altitude alone carry deltaV=None
    (which verify.py treats as "do not check the vector"), so the front
    step stops here with a missing-field result instead of letting the
    prompt builder invent numbers. Hohmann transfers need no delta-V.
    """
    try:
        mans = maneuvers if isinstance(maneuvers, list) else []
    except Exception:
        return []
    for m in mans:
        if not isinstance(m, dict):
            continue
        mtype = m.get("type")
        if isinstance(mtype, str) and mtype.lower() == "impulsiveburn" and not _usable_delta_v(m):
            return ["deltaV"]
    return []


class ExtractionResult:
    def __init__(self, status: str, data: Optional[Dict[str,Any]]=None, missing: Optional[List[str]]=None, prompt: Optional[str]=None, extracted: Optional[Dict]=None):
        self.status=status; self.data=data; self.missing=missing or []; self.prompt=prompt; self.extracted=extracted
    def to_dict(self):
        if self.status=="needs_clarification":
            return {"status":"needs_clarification","missing":self.missing}
        return {"status":"ok","prompt":self.prompt,"data":self.data, "extracted":self.extracted}

def _orbit_numbers_ok(orbit: Any) -> bool:
    """True when an orbit dict carries parseable numbers for its kind.

    Null or non-numeric values count as missing (never silently defaulted).
    Dict shapes without a "kind" key are handled by downstream fallbacks.
    """
    if not isinstance(orbit, dict):
        return True
    need = {
        "semiMajorAxisKm": ["value"],
        "circularAltitudeKm": ["value"], "circularAltitude": ["value"],
        "periapsisAltitudeKm": ["value"],
        "apsisAltitudes": ["apoapsisAltitude", "periapsisAltitude"],
        "apoPeriRadii": ["apoapsisRadius", "periapsisRadius"],
        "circularRadiusKm": ["value"],
    }
    kind = orbit.get("kind")
    if kind not in need:
        return True
    for key in need[kind]:
        val = orbit.get(key)
        if val is None:
            return False
        try:
            float(val)
        except (TypeError, ValueError):
            return False
    return True

class FrontStepExtractor:
    def __init__(self, extractor_client=None):
        self.extractor_client=extractor_client
    def _safe_defaults(self, text: str, body: Optional[str]):
        base="Exp001"
        m=re.search(r"experiment\s+(\w+)", text, re.I)
        if m: base=m.group(1)
        else:
            words=re.findall(r"[A-Za-z0-9_]+", text)
            if words: base=words[0][:12]
        exp_name=sanitize_identifier(base, default="Exp001"); sc_name=sanitize_identifier(base, default="Exp001")
        return exp_name, sc_name
    def deterministic_convert(self, extracted: Dict[str,Any], user_text: str) -> ExtractionResult:
        central_body=extracted.get("centralBody"); dry_mass=extracted.get("dryMassKg"); orbit=extracted.get("orbit"); cartesian=extracted.get("cartesian"); duration=extracted.get("duration")
        missing=[]
        if not central_body: missing.append("centralBody")
        if dry_mass is None: missing.append("dryMassKg")
        if not orbit and not cartesian: missing.append("orbit")
        if not duration: missing.append("duration")
        if missing: return ExtractionResult("needs_clarification", missing=missing)
        if not cartesian and not _orbit_numbers_ok(orbit):
            return ExtractionResult("needs_clarification", missing=["orbit"])
        body_radius=BODY_RADII_KM.get(central_body)
        if body_radius is None: return ExtractionResult("needs_clarification", missing=["centralBody"])
        try: dry_mass_val=float(dry_mass)
        except: dry_mass_val=dry_mass
        sma=None; ecc=None
        if cartesian: sma=None
        else:
            kind=orbit.get("kind") if isinstance(orbit, dict) else None
            if isinstance(orbit, dict) and kind=="circular" and "semiMajorAxisKm" not in orbit and "sma" not in orbit:
                return ExtractionResult("needs_clarification", missing=["orbit.quantity (is it an altitude or a radius?)"])
            if kind=="semiMajorAxisKm":
                sma=float(orbit.get("value")); ecc=float(orbit.get("eccentricity", extracted.get("eccentricity",0)) or 0)
                unit=orbit.get("unit","km")
                if unit=="miles": sma=convert_miles_to_km(sma)
                elif unit=="m": sma=convert_m_to_km(sma)
                elif unit=="AU": sma=convert_au_to_km(sma)
            elif kind in ("circularAltitudeKm","circularAltitude"):
                alt=float(orbit.get("value")); unit=orbit.get("unit","km")
                if unit=="miles": alt=convert_miles_to_km(alt)
                elif unit=="m": alt=convert_m_to_km(alt)
                elif unit=="AU": alt=convert_au_to_km(alt)
                ecc=0; sma=sma_from_circular_altitude(body_radius, alt)
            elif kind=="periapsisAltitudeKm":
                alt=float(orbit.get("value")); unit=orbit.get("unit","km")
                if unit=="miles": alt=convert_miles_to_km(alt)
                elif unit=="m": alt=convert_m_to_km(alt)
                elif unit=="AU": alt=convert_au_to_km(alt)
                ecc=float(extracted.get("eccentricity", orbit.get("eccentricity",0)) or 0)
                sma=sma_from_periapsis_altitude(body_radius, alt, ecc)
            elif kind=="apsisAltitudes":
                alt_a=float(orbit.get("apoapsisAltitude")); alt_p=float(orbit.get("periapsisAltitude"))
                sma,ecc=sma_and_ecc_from_apses_altitudes(body_radius, alt_a, alt_p)
            elif kind=="apoPeriRadii":
                r_a=float(orbit.get("apoapsisRadius")); r_p=float(orbit.get("periapsisRadius"))
                sma=(r_a+r_p)/2.0; ecc=(r_a-r_p)/(r_a+r_p) if (r_a+r_p)!=0 else 0
            elif kind=="circularRadiusKm":
                r=float(orbit.get("value")); unit=orbit.get("unit","km")
                if unit=="miles": r=convert_miles_to_km(r)
                sma=r; ecc=0
            else:
                if isinstance(orbit, dict) and "semiMajorAxisKm" in orbit:
                    sma=float(orbit["semiMajorAxisKm"]); ecc=float(orbit.get("eccentricity",0))
                elif isinstance(orbit, dict) and "sma" in orbit:
                    sma=float(orbit["sma"]); ecc=float(orbit.get("eccentricity",0))
                else:
                    val=orbit.get("value") if isinstance(orbit, dict) else None
                    if val is not None: alt=float(val); sma=sma_from_circular_altitude(body_radius, alt); ecc=0
                    else: return ExtractionResult("needs_clarification", missing=["orbit"])
        inc=extracted.get("inclinationDeg")
        if isinstance(inc, dict) and inc.get("unit")=="rad": inc=radians_to_degrees(float(inc["value"]))
        elif isinstance(inc, dict): inc=float(inc.get("value",0))
        elif inc is not None: inc=float(inc)
        else: inc=0
        raan=extracted.get("raanDeg")
        if isinstance(raan, dict) and raan.get("unit")=="rad": raan=radians_to_degrees(float(raan["value"]))
        elif isinstance(raan, dict): raan=float(raan.get("value",0))
        elif raan is not None: raan=float(raan)
        else: raan=0
        aop=extracted.get("aopDeg") or extracted.get("argumentOfPeriapsisDeg")
        if isinstance(aop, dict) and aop.get("unit")=="rad": aop=radians_to_degrees(float(aop["value"]))
        elif isinstance(aop, dict): aop=float(aop.get("value",0))
        elif aop is not None: aop=float(aop)
        else: aop=0
        ta=extracted.get("trueAnomalyDeg")
        if isinstance(ta, dict) and ta.get("unit")=="rad": ta=radians_to_degrees(float(ta["value"]))
        elif isinstance(ta, dict): ta=float(ta.get("value",0))
        elif ta is not None: ta=float(ta)
        else: ta=0
        dur_val=None; dur_unit=None; stop_type=None
        if duration:
            if not isinstance(duration, dict):
                return ExtractionResult("needs_clarification", missing=["duration"])
            try:
                val=float(duration.get("value"))
            except (TypeError, ValueError):
                return ExtractionResult("needs_clarification", missing=["duration"])
            unit=duration.get("unit")
            if not isinstance(unit, str) or not unit.strip():
                return ExtractionResult("needs_clarification", missing=["duration"])
            try: conv_val, conv_unit, stop_type = convert_duration_to_hours_or_days(val, unit); dur_val=conv_val; dur_unit=conv_unit
            except ValueError:
                ul = str(unit).lower()
                if "sec" in ul or ul.strip() in ("s",): dur_val=round(float(val),6); dur_unit="seconds"; stop_type="ElapsedSeconds"
                elif "min" in ul: dur_val=round(float(val)*60.0,6); dur_unit="seconds"; stop_type="ElapsedSeconds"
                elif "hour" in ul: dur_val=round(float(val),6); dur_unit="hours"; stop_type="ElapsedHours"
                elif "day" in ul: dur_val=round(float(val),6); dur_unit="days"; stop_type="ElapsedDays"
                elif "orbit" in ul or "period" in ul: dur_val=round(float(val),6); dur_unit="orbital periods"; stop_type="OrbitPeriods"
                else: dur_val=round(float(val),6); dur_unit=str(unit); stop_type="ElapsedHours"
        integrator=extracted.get("integrator","RungeKutta89")
        if integrator not in ("RungeKutta89","PrinceDormand78"): integrator="RungeKutta89"
        forces=extracted.get("forces"); maneuvers=extracted.get("maneuvers",[])
        man_missing=_missing_burn_size(maneuvers)
        if man_missing:
            return ExtractionResult("needs_clarification", missing=man_missing)
        # Names are owned by Python, never by the model: any model-provided
        # spacecraftName/experimentName keys are ignored and generated instead.
        exp_name, sc_name = self._safe_defaults(user_text, central_body)
        normalized={"experimentName":exp_name,"spacecraftName":sc_name,"dryMassKg":dry_mass_val,"centralBody":central_body,"semiMajorAxisKm":sma,"eccentricity":ecc,"inclinationDeg":inc if inc is not None else 0,"raanDeg":raan,"argumentOfPeriapsisDeg":aop,"trueAnomalyDeg":ta,"durationValue":dur_val,"durationUnit":dur_unit,"stopConditionType":stop_type,"integrator":integrator,"forces":forces,"maneuvers":maneuvers,"cartesian":cartesian,"bodyRadiusKm":body_radius}
        from .prompt_builder import build_canonical_prompt
        prompt=build_canonical_prompt(normalized)
        return ExtractionResult("ok", data=normalized, prompt=prompt, extracted=extracted)
    async def process(self, user_text: str) -> ExtractionResult:
        extractor_failed=False
        if self.extractor_client:
            try:
                extracted=await self.extractor_client.extract(user_text)
                _log_extractor_ok(extracted)
            except Exception as e:
                _log_extractor_failure(e)
                extractor_failed=self._is_real_extractor()
                extracted=self._fallback_extract(user_text)
        else: extracted=self._fallback_extract(user_text)
        from orbitlab_backend.clients.extractor_client import normalize_extracted
        res=self.deterministic_convert(normalize_extracted(extracted), user_text)
        if extractor_failed and res.status!="ok":
            from orbitlab_backend.orchestrator.errors import ExtractorUnavailable
            raise ExtractorUnavailable()
        return res
    def process_sync(self, user_text: str) -> ExtractionResult:
        extractor_failed=False
        if self.extractor_client and hasattr(self.extractor_client, 'extract_sync'):
            try:
                extracted=self.extractor_client.extract_sync(user_text)
                _log_extractor_ok(extracted)
            except Exception as e:
                _log_extractor_failure(e)
                extractor_failed=self._is_real_extractor()
                extracted=self._fallback_extract(user_text)
        else: extracted=self._fallback_extract(user_text)
        from orbitlab_backend.clients.extractor_client import normalize_extracted
        res=self.deterministic_convert(normalize_extracted(extracted), user_text)
        if extractor_failed and res.status!="ok":
            from orbitlab_backend.orchestrator.errors import ExtractorUnavailable
            raise ExtractorUnavailable()
        return res
    @staticmethod
    def _is_real_extractor_static(client) -> bool:
        try:
            from orbitlab_backend.clients.extractor_client import OpenAIExtractor
            return isinstance(client, OpenAIExtractor)
        except Exception:
            return False
    def _is_real_extractor(self) -> bool:
        return self._is_real_extractor_static(self.extractor_client)
    def _fallback_extract(self, text: str) -> Dict[str,Any]:
        low=text.lower(); body=None
        for b in ["Earth","Moon","Mars","Mercury","Venus","Jupiter","Sun"]:
            if b.lower() in low: body=b; break
        dry=None
        import re as _re; m=_re.search(r"(\d+\.?\d*)\s*kg", low)
        if m: dry=float(m.group(1))
        orbit=None
        m=_re.search(r"(\d+\.?\d*)\s*km\s*circular", low)
        if m: orbit={"kind":"circularAltitudeKm","value":float(m.group(1)),"unit":"km"}
        else:
            m=_re.search(r"altitude\s*(\d+\.?\d*)\s*km", low)
            if m:
                e=None; me=_re.search(r"e(ccentricity)?\s*=?\s*(\d+\.?\d*)", low)
                if me: e=float(me.group(2))
                orbit={"kind":"periapsisAltitudeKm","value":float(m.group(1)),"unit":"km","eccentricity":e}
            else:
                m=_re.search(r"sma\s*(\d+\.?\d*)", low)
                if m: orbit={"kind":"semiMajorAxisKm","value":float(m.group(1)),"unit":"km"}
        ecc=None; me=_re.search(r"eccentricity\s*(\d+\.?\d*)", low)
        if me: ecc=float(me.group(1))
        duration=None; m=_re.search(r"propagate.*?(\d+\.?\d*)\s*(orbital periods|orbital period|orbits|orbit|hours|days|seconds|minutes|secs|seconds)", low)
        if m: duration={"value":float(m.group(1)),"unit":m.group(2)}
        else:
            m=_re.search(r"for\s+(\d+\.?\d*)\s*(orbital periods|orbital period|orbits|orbit|hours|days|seconds|minutes)", low)
            if m: duration={"value":float(m.group(1)),"unit":m.group(2)}
        integrator=None
        if "prince" in low: integrator="PrinceDormand78"
        elif "runge" in low: integrator="RungeKutta89"
        return {"centralBody":body,"dryMassKg":dry,"orbit":orbit,"eccentricity":ecc,"duration":duration,"integrator":integrator,"forces":None,"maneuvers":[],"cartesian":None,"raw_text":text}
