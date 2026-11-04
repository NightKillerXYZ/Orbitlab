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


def test_names_owned_by_frontstep_experiment():
    from orbitlab_backend.frontstep.verify import apply_frontstep_names, verify_experiment
    sent={"experimentName":"OrbT01","spacecraftName":"OrbT01","centralBody":"Earth","dryMassKg":500,"semiMajorAxisKm":6778.136,"eccentricity":0,"inclinationDeg":28.5,"raanDeg":0,"argumentOfPeriapsisDeg":0,"trueAnomalyDeg":0,"integrator":"RungeKutta89","durationValue":2,"durationUnit":"hours","stopConditionType":"ElapsedHours","forces":None,"maneuvers":[]}
    returned={"experimentName":"SC_OrbT01","spacecraft":{"name":"SC_OrbT01","dryMassKg":500},"centralBody":"Earth","initialOrbit":{"type":"Keplerian","elements":{"semiMajorAxisKm":6778.136,"eccentricity":0,"inclinationDeg":28.5,"raanDeg":0,"argumentOfPeriapsisDeg":0,"trueAnomalyDeg":0}},"propagation":{"integrator":"RungeKutta89","stopCondition":{"type":"ElapsedHours","value":2}},"forceModel":{"gravityDegree":4,"gravityOrder":4},"maneuvers":[]}
    out, overrides = apply_frontstep_names(sent, returned)
    assert out["experimentName"]=="OrbT01"
    assert any(o["field"]=="experimentName" for o in overrides)
    # names never cause mismatch
    assert verify_experiment(sent, out)==[]

def test_names_owned_by_frontstep_spacecraft():
    from orbitlab_backend.frontstep.verify import apply_frontstep_names, verify_experiment
    sent={"experimentName":"OrbT01","spacecraftName":"OrbT01","centralBody":"Earth","dryMassKg":500,"semiMajorAxisKm":6778.136,"eccentricity":0,"inclinationDeg":28.5,"raanDeg":0,"argumentOfPeriapsisDeg":0,"trueAnomalyDeg":0,"integrator":"RungeKutta89","durationValue":2,"durationUnit":"hours","stopConditionType":"ElapsedHours","forces":None,"maneuvers":[]}
    returned={"experimentName":"OrbT01","spacecraft":{"name":"DryMass850","dryMassKg":500},"centralBody":"Earth","initialOrbit":{"type":"Keplerian","elements":{"semiMajorAxisKm":6778.136,"eccentricity":0,"inclinationDeg":28.5,"raanDeg":0,"argumentOfPeriapsisDeg":0,"trueAnomalyDeg":0}},"propagation":{"integrator":"RungeKutta89","stopCondition":{"type":"ElapsedHours","value":2}},"forceModel":{"gravityDegree":4,"gravityOrder":4},"maneuvers":[]}
    out, overrides = apply_frontstep_names(sent, returned)
    assert out["spacecraft"]["name"]=="SC_OrbT01"
    assert any(o["field"]=="spacecraft.name" for o in overrides)
    assert verify_experiment(sent, out)==[]

def test_names_equal_no_warning():
    from orbitlab_backend.frontstep.verify import apply_frontstep_names
    sent={"experimentName":"OrbT01","spacecraftName":"OrbT01","centralBody":"Earth","dryMassKg":500,"semiMajorAxisKm":6778.136,"eccentricity":0,"inclinationDeg":28.5,"raanDeg":0,"argumentOfPeriapsisDeg":0,"trueAnomalyDeg":0,"integrator":"RungeKutta89","durationValue":2,"durationUnit":"hours","stopConditionType":"ElapsedHours","forces":None,"maneuvers":[]}
    returned={"experimentName":"OrbT01","spacecraft":{"name":"SC_OrbT01","dryMassKg":500}}
    out, overrides = apply_frontstep_names(sent, returned)
    assert overrides==[]
    assert out["experimentName"]=="OrbT01" and out["spacecraft"]["name"]=="SC_OrbT01"

def test_spacecraft_name_sanitised_to_pattern():
    import re
    from orbitlab_backend.frontstep.verify import sanitize_identifier, frontstep_expected_names
    assert re.match(r"^[A-Za-z0-9_]{1,30}$", sanitize_identifier("bad-name! here"))
    exp, sc = frontstep_expected_names({"experimentName":"OrbT01","spacecraftName":"bad name!"})
    assert re.match(r"^[A-Za-z0-9_]{1,30}$", sc)

def test_stop_seconds_passthrough_prompt():
    from orbitlab_backend.frontstep.extractor import FrontStepExtractor
    from orbitlab_backend.frontstep.prompt_builder import build_canonical_prompt
    ext = FrontStepExtractor()
    res = ext.deterministic_convert({"centralBody":"Earth","dryMassKg":500,"orbit":{"kind":"circularAltitudeKm","value":400,"unit":"km"},"duration":{"value":7200,"unit":"seconds"},"integrator":"RungeKutta89","forces":None,"maneuvers":[],"cartesian":None}, "Earth 500 kg 400 km circular propagate for 7200 seconds")
    assert res.status=="ok"
    assert res.data["stopConditionType"]=="ElapsedSeconds" and res.data["durationValue"]==7200 and res.data["durationUnit"]=="seconds"
    p = build_canonical_prompt(res.data)
    assert "propagate for 7200 seconds using integrator RungeKutta89." in p

def test_stop_orbits_passthrough_prompt():
    # "3 orbits" passes through unchanged as OrbitPeriods value 3.
    from orbitlab_backend.frontstep.extractor import FrontStepExtractor
    from orbitlab_backend.frontstep.prompt_builder import build_canonical_prompt
    ext = FrontStepExtractor()
    res = ext.deterministic_convert({"centralBody":"Earth","dryMassKg":500,"orbit":{"kind":"circularAltitudeKm","value":400,"unit":"km"},"duration":{"value":3,"unit":"orbits"},"integrator":"RungeKutta89","forces":None,"maneuvers":[],"cartesian":None}, "Earth 500 kg 400 km circular for 3 orbits")
    assert res.status=="ok"
    assert res.data["stopConditionType"]=="OrbitPeriods" and res.data["durationValue"]==3
    assert res.data["durationUnit"]=="orbital periods"
    p = build_canonical_prompt(res.data)
    assert "propagate for 3 orbital periods using integrator RungeKutta89." in p
