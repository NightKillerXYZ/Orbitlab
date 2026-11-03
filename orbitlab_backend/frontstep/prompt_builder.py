"""Canonical prompt builder with exact sentence forms."""
from __future__ import annotations
from typing import Any, Dict, Optional

def _fmt_num(v: float) -> str:
    # Keep exact, no rounding beyond 6 decimals, but SMA formatted to 3 decimals elsewhere
    if isinstance(v, int):
        return str(v)
    # Use repr without scientific if possible
    s = f"{v:.6f}"
    # Trim trailing zeros but keep at least one decimal if needed? Spec says keep exact, no rounding beyond 6 decimals
    s = s.rstrip('0').rstrip('.')
    if s == '-0':
        s='0'
    if s=='':
        s='0'
    return s

def _fmt_sma(a: float) -> str:
    return f"{round(a,3):.3f}"

def build_canonical_prompt(data: Dict[str, Any]) -> str:
    """
    data must contain normalized fields:
    experimentName, spacecraftName, dryMassKg, centralBody,
    semiMajorAxisKm, eccentricity, inclinationDeg, raanDeg, aopDeg, trueAnomalyDeg,
    durationValue, durationUnit (hours|days), integrator (RungeKutta89|PrinceDormand78),
    forces: None or dict with gravityDegree, gravityOrder, pointMasses, srp flag
    maneuvers: list of dicts with type and params
    cartesian: optional dict with x,y,z,vx,vy,vz
    """
    exp_name = data.get("experimentName") or "DefaultExp"
    sc_name = data.get("spacecraftName") or exp_name
    # SC_<Name> convention: if sc_name doesn't start with SC_, prefix
    sc_full = sc_name if sc_name.startswith("SC_") else f"SC_{sc_name}"
    dry_mass = _fmt_num(data.get("dryMassKg", 500))
    body = data.get("centralBody", "Earth")
    integrator = data.get("integrator", "RungeKutta89")
    # Duration
    dur_val = data.get("durationValue")
    dur_unit = data.get("durationUnit", "hours")
    # Cartesian special case
    cartesian = data.get("cartesian")
    if cartesian:
        x=cartesian.get("x"); y=cartesian.get("y"); z=cartesian.get("z")
        vx=cartesian.get("vx"); vy=cartesian.get("vy"); vz=cartesian.get("vz")
        base = f"Configure experiment {exp_name} for {sc_full}, dry mass {dry_mass} kg, in a {body} orbit with Cartesian state: Initial state: r = [{x}, {y}, {z}] km; v = [{vx}, {vy}, {vz}] km/s in Cartesian coordinates; propagate for {dur_val} {dur_unit} using integrator {integrator}."
        # Still need to handle forces/maneuvers after
    else:
        sma = _fmt_sma(data.get("semiMajorAxisKm", 6778.136))
        ecc = _fmt_num(data.get("eccentricity", 0))
        inc = _fmt_num(data.get("inclinationDeg", 0))
        raan = _fmt_num(data.get("raanDeg", 0))
        aop = _fmt_num(data.get("argumentOfPeriapsisDeg", 0))
        ta = _fmt_num(data.get("trueAnomalyDeg", 0))
        base = f"Configure experiment {exp_name} for {sc_full}, dry mass {dry_mass} kg, in a {body} orbit with semi-major axis {sma} km and eccentricity {ecc}, inclination {inc} degrees, RAAN {raan} degrees, argument of periapsis {aop} degrees, and true anomaly {ta} degrees; propagate for {dur_val} {dur_unit} using integrator {integrator}."
    # Forces
    forces = data.get("forces")
    if forces is None or forces == "defaults":
        forces_sentence = " Use the model's default force settings."
    else:
        deg = forces.get("gravityDegree", 8)
        order = forces.get("gravityOrder", 8)
        pms = forces.get("pointMasses", ["Luna","Sun"])
        # point masses may be like ["Luna","Sun"] -> format as "Luna and Sun"
        if len(pms)==0:
            pm_str="none"
        elif len(pms)==1:
            pm_str=pms[0]
        elif len(pms)==2:
            pm_str=f"{pms[0]} and {pms[1]}"
        else:
            pm_str=", ".join(pms[:-1])+f" and {pms[-1]}"
        srp = forces.get("solarRadiationPressure", True)
        srp_str="on" if srp else "off"
        forces_sentence = f" Use a degree-{deg} and order-{order} gravity field, point masses {pm_str}, and solar radiation pressure {srp_str}."
        # Note: spec example: Use a degree-8 and order-8 gravity field, point masses Luna and Sun, and solar radiation pressure off.
    prompt = base + forces_sentence
    # Maneuvers
    maneuvers = data.get("maneuvers", [])
    for m in maneuvers:
        mtype=m.get("type")
        if mtype=="Hohmann":
            target_r = _fmt_num(m.get("targetOrbitRadiusKm"))
            apsis = m.get("apsis", "periapsis")
            sent = f" add maneuver {m.get('id','M1')}: a Hohmann transfer at {apsis} to a target orbit radius of {target_r} km."
            if m.get("targetEccentricity") is not None and float(m.get("targetEccentricity"))!=0:
                sent = sent.rstrip(" .") + f" and target eccentricity {_fmt_num(m.get('targetEccentricity'))}."
                # close sentence: need period
                if not sent.endswith("."):
                    sent+="."
            prompt += sent
        elif mtype=="ImpulsiveBurn":
            # Determine elapsed vs apsis
            if m.get("trigger")=="ElapsedTimeSecs":
                sec=_fmt_num(m.get("elapsedSecs",0))
                v,n,b = m.get("deltaV",[0,0,0])
                prompt+= f" Give it a small prograde/radial/normal impulse once {sec} sec have elapsed: LocalVNB components [{v}, {n}, {b}] km/s."
            else:
                apsis=m.get("apsis","apoapsis")
                v,n,b = m.get("deltaV",[0,0,0])
                prompt+= f" At the next {apsis}, apply the LocalVNB burn with V-N-B delta-v [{v}, {n}, {b}] km/s."
        else:
            # generic
            prompt+= f" Maneuver {m.get('id')}: {mtype}."
    return prompt
