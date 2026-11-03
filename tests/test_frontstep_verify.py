from orbitlab_backend.frontstep.extractor import FrontStepExtractor
from orbitlab_backend.frontstep.verify import verify_experiment, normalize_maneuver_ids
from orbitlab_backend.frontstep.conversions import BODY_RADII_KM

def test_missing_info():
    ext=FrontStepExtractor()
    # No extractor client, fallback extract with missing body/mass etc will be incomplete
    # Use deterministic_convert directly
    extracted={"centralBody":None,"dryMassKg":None,"orbit":None,"duration":None}
    res=ext.deterministic_convert(extracted, "do something in space")
    assert res.status=="needs_clarification"
    assert "centralBody" in res.missing
    assert "dryMassKg" in res.missing
    assert "orbit" in res.missing
    assert "duration" in res.missing

def test_verify_match():
    sent={"centralBody":"Earth","dryMassKg":500,"semiMajorAxisKm":6778.136,"eccentricity":0.01,"inclinationDeg":28.5,"raanDeg":0,"argumentOfPeriapsisDeg":0,"trueAnomalyDeg":0,"integrator":"RungeKutta89","durationValue":2,"durationUnit":"hours","stopConditionType":"ElapsedHours","forces":None,"maneuvers":[]}
    returned={"centralBody":"Earth","spacecraft":{"name":"SC_Test","dryMassKg":500},"initialOrbit":{"type":"Keplerian","elements":{"semiMajorAxisKm":6778.136,"eccentricity":0.01,"inclinationDeg":28.5,"raanDeg":0,"argumentOfPeriapsisDeg":0,"trueAnomalyDeg":0}},"propagation":{"integrator":"RungeKutta89","stopCondition":{"type":"ElapsedHours","value":2}},"forceModel":{"gravityDegree":4,"gravityOrder":4},"maneuvers":[]}
    mismatches=verify_experiment(sent, returned)
    assert mismatches==[]

def test_verify_mismatch_sma():
    sent={"centralBody":"Earth","dryMassKg":500,"semiMajorAxisKm":6778.136,"eccentricity":0.01,"inclinationDeg":28.5,"raanDeg":0,"argumentOfPeriapsisDeg":0,"trueAnomalyDeg":0,"integrator":"RungeKutta89","durationValue":2,"durationUnit":"hours","stopConditionType":"ElapsedHours","forces":None,"maneuvers":[]}
    returned={"centralBody":"Earth","spacecraft":{"name":"SC_Test","dryMassKg":500},"initialOrbit":{"type":"Keplerian","elements":{"semiMajorAxisKm":7000,"eccentricity":0.01,"inclinationDeg":28.5,"raanDeg":0,"argumentOfPeriapsisDeg":0,"trueAnomalyDeg":0}},"propagation":{"integrator":"RungeKutta89","stopCondition":{"type":"ElapsedHours","value":2}},"forceModel":{"gravityDegree":4},"maneuvers":[]}
    mismatches=verify_experiment(sent, returned)
    assert any(m["field"]=="semiMajorAxisKm" for m in mismatches)

def test_maneuver_id_normalization():
    exp={"maneuvers":[{"id":"weird1","type":"ImpulsiveBurn"},{"id":"other","type":"ImpulsiveBurn"}]}
    out=normalize_maneuver_ids(exp)
    assert out["maneuvers"][0]["id"]=="M1"
    assert out["maneuvers"][1]["id"]=="M2"

def test_edge_case_pass_through():
    ext=FrontStepExtractor()
    extracted={"centralBody":"Earth","dryMassKg":500,"orbit":{"kind":"periapsisAltitudeKm","value":50,"unit":"km","eccentricity":0.1},"eccentricity":0.1,"duration":{"value":1,"unit":"hours"},"integrator":"RungeKutta89","forces":None,"maneuvers":[],"cartesian":None}
    res=ext.deterministic_convert(extracted, "test")
    assert res.status=="ok"
    # Check SMA not crash and computed
    assert res.data["semiMajorAxisKm"] is not None
