"""Verify-after check and maneuver id normalization."""
from __future__ import annotations
import math
from typing import Any, Dict, List
import re as _re

def _rel_match(exp: float, got: float, tol=1e-9):
    if exp==0 and got==0:
        return True
    if exp==0 or got==0:
        return abs(exp-got) <= 1e-12
    return abs(exp-got)/abs(exp) <= tol
NAME_PATTERN = _re.compile(r"^[A-Za-z0-9_]{1,30}$")

def sanitize_identifier(name, default="Exp001"):
    """Sanitise to schema pattern ^[A-Za-z0-9_]{1,30}$: invalid chars -> _, truncate 30."""
    if name is None:
        return default
    s = str(name).strip()
    if not s:
        return default
    s = _re.sub(r"[^A-Za-z0-9_]", "_", s)
    if not s:
        return default
    return s[:30]

def frontstep_expected_names(sent):
    """Return (experimentName, spacecraft full name) owned by the front step."""
    exp = sanitize_identifier(sent.get("experimentName") or "DefaultExp", default="DefaultExp")
    base = sanitize_identifier(sent.get("spacecraftName") or exp, default=exp)
    full = base if base.startswith("SC_") else f"SC_{base}"
    full = sanitize_identifier(full, default="SC_DefaultExp")[:30]
    # ensure SC_ prefix survived truncation
    if not full.startswith("SC_"):
        full = ("SC_" + full)[-30:]
        full = sanitize_identifier(full, default="SC_DefaultExp")
    return exp, full

def apply_frontstep_names(sent, returned):
    """Override returned names with front-step values. Returns (updated, overrides list)."""
    exp, sc_full = frontstep_expected_names(sent)
    if not isinstance(returned, dict):
        return returned, []
    overrides = []
    got_exp = returned.get("experimentName")
    if got_exp != exp:
        overrides.append({"field": "experimentName", "expected": exp, "got": got_exp})
    returned["experimentName"] = exp
    sc = returned.get("spacecraft")
    if not isinstance(sc, dict):
        returned["spacecraft"] = {"name": sc_full}
        overrides.append({"field": "spacecraft.name", "expected": sc_full, "got": None})
    else:
        got_sc = sc.get("name")
        if got_sc != sc_full:
            overrides.append({"field": "spacecraft.name", "expected": sc_full, "got": got_sc})
        sc["name"] = sc_full
    return returned, overrides


def verify_experiment(sent: Dict[str,Any], returned: Dict[str,Any]) -> List[Dict[str,Any]]:
    # Names are owned by Python (see apply_frontstep_names); never report them here.
    mismatches=[]
    # centralBody
    if sent.get("centralBody") != returned.get("centralBody"):
        mismatches.append({"field":"centralBody","expected":sent.get("centralBody"),"got":returned.get("centralBody")})
    # dryMassKg
    s_mass=sent.get("dryMassKg"); g_mass=(returned.get("spacecraft") or {}).get("dryMassKg") if isinstance(returned.get("spacecraft"), dict) else returned.get("dryMassKg")
    if s_mass is not None and g_mass is not None:
        if not _rel_match(float(s_mass), float(g_mass)):
            mismatches.append({"field":"dryMassKg","expected":s_mass,"got":g_mass})
    # orbit elements
    s_sma=sent.get("semiMajorAxisKm"); s_ecc=sent.get("eccentricity")
    # returned may have Keplerian
    orbit=returned.get("initialOrbit") or {}
    elems=orbit.get("elements") if isinstance(orbit, dict) else {}
    g_sma=elems.get("semiMajorAxisKm") if isinstance(elems, dict) else None
    g_ecc=elems.get("eccentricity") if isinstance(elems, dict) else None
    if s_sma is not None and g_sma is not None:
        if abs(float(s_sma)-float(g_sma)) > 0.001:
            mismatches.append({"field":"semiMajorAxisKm","expected":s_sma,"got":g_sma})
    if s_ecc is not None and g_ecc is not None:
        if not _rel_match(float(s_ecc), float(g_ecc)):
            mismatches.append({"field":"eccentricity","expected":s_ecc,"got":g_ecc})
    # inclination etc
    for field in ["inclinationDeg","raanDeg","argumentOfPeriapsisDeg","trueAnomalyDeg"]:
        s_val=sent.get(field)
        # map to returned elements keys
        key_map={"inclinationDeg":"inclinationDeg","raanDeg":"raanDeg","argumentOfPeriapsisDeg":"argumentOfPeriapsisDeg","trueAnomalyDeg":"trueAnomalyDeg"}
        g_val=elems.get(key_map[field]) if isinstance(elems, dict) else None
        if s_val is not None and g_val is not None:
            if not _rel_match(float(s_val), float(g_val)):
                mismatches.append({"field":field,"expected":s_val,"got":g_val})
    # integrator
    s_int=sent.get("integrator"); g_int=(returned.get("propagation") or {}).get("integrator") if isinstance(returned.get("propagation"), dict) else None
    if s_int and g_int and s_int != g_int:
        mismatches.append({"field":"integrator","expected":s_int,"got":g_int})
    # stopCondition
    s_dur=sent.get("durationValue"); s_unit=sent.get("durationUnit"); s_stop=sent.get("stopConditionType")
    g_stop=(returned.get("propagation") or {}).get("stopCondition") if isinstance(returned.get("propagation"), dict) else None
    if isinstance(g_stop, dict) and s_stop:
        if g_stop.get("type") != s_stop:
            mismatches.append({"field":"stopCondition.type","expected":s_stop,"got":g_stop.get("type")})
        # value check
        if s_dur is not None and g_stop.get("value") is not None:
            if not _rel_match(float(s_dur), float(g_stop.get("value"))):
                mismatches.append({"field":"stopCondition.value","expected":s_dur,"got":g_stop.get("value")})
    # forces if explicit
    s_forces=sent.get("forces")
    g_forces=returned.get("forceModel")
    if s_forces and isinstance(s_forces, dict) and isinstance(g_forces, dict):
        for k in ["gravityDegree","gravityOrder","solarRadiationPressure"]:
            if k in s_forces and k in g_forces:
                if s_forces[k] != g_forces[k]:
                    mismatches.append({"field":f"forceModel.{k}","expected":s_forces[k],"got":g_forces[k]})
        if "pointMasses" in s_forces and "pointMasses" in g_forces:
            if set(s_forces["pointMasses"]) != set(g_forces["pointMasses"]):
                mismatches.append({"field":"forceModel.pointMasses","expected":s_forces["pointMasses"],"got":g_forces["pointMasses"]})
    # maneuvers numbers
    s_mans=sent.get("maneuvers",[]) or []
    g_mans=returned.get("maneuvers",[]) or []
    # Compare count
    if len(s_mans) != len(g_mans):
        mismatches.append({"field":"maneuvers.count","expected":len(s_mans),"got":len(g_mans)})
    else:
        for i, (s_m, g_m) in enumerate(zip(s_mans, g_mans)):
            # check targetOrbitRadiusKm and deltaV etc
            if s_m.get("targetOrbitRadiusKm") is not None:
                g_val=None
                if isinstance(g_m, dict):
                    g_val=(g_m.get("targetObjectives") or {}).get("targetOrbitRadiusKm")
                    if g_val is None: g_val=g_m.get("targetOrbitRadiusKm")
                if g_val is not None and not _rel_match(float(s_m["targetOrbitRadiusKm"]), float(g_val)):
                    mismatches.append({"field":f"maneuvers[{i}].targetOrbitRadiusKm","expected":s_m["targetOrbitRadiusKm"],"got":g_val})
            if s_m.get("deltaV") is not None and isinstance(g_m, dict):
                g_dv=(g_m.get("burnVector") or {}).get("deltaVVectorKmS") if isinstance(g_m.get("burnVector"), dict) else g_m.get("deltaVVectorKmS")
                if g_dv and len(g_dv)==3:
                    for idx, (a,b) in enumerate(zip(s_m["deltaV"], g_dv)):
                        if not _rel_match(float(a), float(b)):
                            mismatches.append({"field":f"maneuvers[{i}].deltaV[{idx}]","expected":a,"got":b})
    return mismatches

def normalize_maneuver_ids(experiment: Dict[str,Any]) -> Dict[str,Any]:
    mans=experiment.get("maneuvers", [])
    for idx, m in enumerate(mans):
        # Assign M1, M2,... by order
        m["id"] = f"M{idx+1}"
    return experiment
