import pytest, json
from orbitlab_backend.orchestrator.pipeline import Pipeline
from orbitlab_backend.frontstep.extractor import FrontStepExtractor
from orbitlab_backend.clients.interpreter_client import MockInterpreterClient
from orbitlab_backend.clients.explainer_client import MockExplainer

@pytest.mark.asyncio
async def test_successful_run():
    extracted={"centralBody":"Earth","dryMassKg":500,"orbit":{"kind":"circularAltitudeKm","value":400,"unit":"km"},"duration":{"value":2,"unit":"hours"},"integrator":"RungeKutta89","inclinationDeg":28.5,"raanDeg":0,"argumentOfPeriapsisDeg":0,"trueAnomalyDeg":0,"forces":None,"maneuvers":[],"cartesian":None}
    ext=FrontStepExtractor(); ext._fallback_extract=lambda t: extracted
    correct={"version":"1.0","experimentName":"TestExp","spacecraft":{"name":"SC_TestExp","dryMassKg":500},"centralBody":"Earth","initialOrbit":{"type":"Keplerian","coordinateSystem":"EarthMJ2000Eq","elements":{"semiMajorAxisKm":6778.136,"eccentricity":0,"inclinationDeg":28.5,"raanDeg":0,"argumentOfPeriapsisDeg":0,"trueAnomalyDeg":0}},"forceModel":{"gravityDegree":4,"gravityOrder":4,"pointMasses":["Luna","Sun"],"atmosphericDrag":{"enabled":False,"model":"JacchiaRoberts"},"solarRadiationPressure":True},"propagation":{"integrator":"RungeKutta89","stopCondition":{"type":"ElapsedHours","value":2},"stepSizeSecs":60},"maneuvers":[]}
    interp=MockInterpreterClient(canned_json=json.dumps(correct))
    pipeline=Pipeline(extractor=ext, interpreter=interp, explainer=MockExplainer(), gmat_runner=None)
    events=[]
    async def cb(ev): events.append(ev)
    res=await pipeline.run("dummy text 500 kg Earth 400 km circular 2 hours", event_cb=cb)
    assert res["status"]=="success"
    stages=[e.stage for e in events if e.type=="stage_completed"]
    assert stages==["extract","interpret","verify","validate","compile","simulate","parse","explain"]

@pytest.mark.asyncio
async def test_mismatch_error():
    extracted={"centralBody":"Earth","dryMassKg":500,"orbit":{"kind":"circularAltitudeKm","value":400,"unit":"km"},"duration":{"value":2,"unit":"hours"},"integrator":"RungeKutta89","inclinationDeg":28.5,"raanDeg":0,"argumentOfPeriapsisDeg":0,"trueAnomalyDeg":0,"forces":None,"maneuvers":[],"cartesian":None}
    ext=FrontStepExtractor(); ext._fallback_extract=lambda t: extracted
    mismatch={"version":"1.0","experimentName":"TestExp","spacecraft":{"name":"SC_TestExp","dryMassKg":500},"centralBody":"Earth","initialOrbit":{"type":"Keplerian","coordinateSystem":"EarthMJ2000Eq","elements":{"semiMajorAxisKm":7000,"eccentricity":0,"inclinationDeg":28.5,"raanDeg":0,"argumentOfPeriapsisDeg":0,"trueAnomalyDeg":0}},"forceModel":{"gravityDegree":4,"gravityOrder":4,"pointMasses":["Luna","Sun"],"atmosphericDrag":{"enabled":False,"model":"JacchiaRoberts"},"solarRadiationPressure":True},"propagation":{"integrator":"RungeKutta89","stopCondition":{"type":"ElapsedHours","value":2},"stepSizeSecs":60},"maneuvers":[]}
    interp=MockInterpreterClient(canned_json=json.dumps(mismatch))
    pipeline=Pipeline(extractor=ext, interpreter=interp, explainer=MockExplainer())
    with pytest.raises(Exception) as exc:
        await pipeline.run("dummy", event_cb=None)
    assert "mismatch" in str(exc.value).lower() or "InterpreterMismatch" in str(type(exc.value))

@pytest.mark.asyncio
async def test_schema_error():
    extracted={"centralBody":"Earth","dryMassKg":-5,"orbit":{"kind":"circularAltitudeKm","value":400,"unit":"km"},"duration":{"value":2,"unit":"hours"},"integrator":"RungeKutta89","inclinationDeg":28.5,"raanDeg":0,"argumentOfPeriapsisDeg":0,"trueAnomalyDeg":0,"forces":None,"maneuvers":[],"cartesian":None}
    ext=FrontStepExtractor(); ext._fallback_extract=lambda t: extracted
    bad={"version":"1.0","experimentName":"Bad","spacecraft":{"name":"SC_Bad","dryMassKg":-5},"centralBody":"Earth","initialOrbit":{"type":"Keplerian","coordinateSystem":"EarthMJ2000Eq","elements":{"semiMajorAxisKm":6778.136,"eccentricity":0,"inclinationDeg":28.5,"raanDeg":0,"argumentOfPeriapsisDeg":0,"trueAnomalyDeg":0}},"forceModel":{"gravityDegree":4,"gravityOrder":4,"pointMasses":["Luna","Sun"],"atmosphericDrag":{"enabled":False,"model":"JacchiaRoberts"},"solarRadiationPressure":True},"propagation":{"integrator":"RungeKutta89","stopCondition":{"type":"ElapsedHours","value":2},"stepSizeSecs":60},"maneuvers":[]}
    interp=MockInterpreterClient(canned_json=json.dumps(bad))
    pipeline=Pipeline(extractor=ext, interpreter=interp, explainer=MockExplainer())
    with pytest.raises(Exception) as exc:
        await pipeline.run("dummy")
    assert "schema" in str(exc.value).lower() or "validation" in str(exc.value).lower()

