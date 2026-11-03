import pytest, json
from orbitlab_backend.orchestrator.pipeline import Pipeline
from orbitlab_backend.frontstep.extractor import FrontStepExtractor
from orbitlab_backend.clients.interpreter_client import MockInterpreterClient
from orbitlab_backend.clients.explainer_client import MockExplainer

@pytest.mark.asyncio
async def test_validation_failed_but_explainer_called():
    extracted={"centralBody":"Earth","dryMassKg":500,"orbit":{"kind":"periapsisAltitudeKm","value":70,"unit":"km","eccentricity":0},"eccentricity":0,"duration":{"value":1,"unit":"hours"},"integrator":"RungeKutta89","inclinationDeg":28.5,"raanDeg":0,"argumentOfPeriapsisDeg":0,"trueAnomalyDeg":0,"forces":None,"maneuvers":[],"cartesian":None}
    ext=FrontStepExtractor(); ext._fallback_extract=lambda t: extracted
    exp={"version":"1.0","experimentName":"LowExp","spacecraft":{"name":"SC_LowExp","dryMassKg":500},"centralBody":"Earth","initialOrbit":{"type":"Keplerian","coordinateSystem":"EarthMJ2000Eq","elements":{"semiMajorAxisKm":6448.136,"eccentricity":0,"inclinationDeg":28.5,"raanDeg":0,"argumentOfPeriapsisDeg":0,"trueAnomalyDeg":0}},"forceModel":{"gravityDegree":4,"gravityOrder":4,"pointMasses":["Luna","Sun"],"atmosphericDrag":{"enabled":False,"model":"JacchiaRoberts"},"solarRadiationPressure":True},"propagation":{"integrator":"RungeKutta89","stopCondition":{"type":"ElapsedHours","value":1},"stepSizeSecs":60},"maneuvers":[]}
    interp=MockInterpreterClient(canned_json=json.dumps(exp))
    class RecordingExplainer(MockExplainer):
        called=False
        async def explain(self, experiment, stage, error, warnings, trajectory_summary=None):
            self.called=True
            return "explained failure"
    expl=RecordingExplainer()
    pipeline=Pipeline(extractor=ext, interpreter=interp, explainer=expl)
    with pytest.raises(Exception):
        await pipeline.run("dummy")
    assert expl.called

@pytest.mark.asyncio
async def test_needs_clarification():
    extracted={"centralBody":None,"dryMassKg":None,"orbit":None,"duration":None}
    ext=FrontStepExtractor(); ext._fallback_extract=lambda t: extracted
    pipeline=Pipeline(extractor=ext, interpreter=MockInterpreterClient(), explainer=MockExplainer())
    with pytest.raises(Exception) as exc:
        await pipeline.run("hello")
    assert "missing" in str(exc.value).lower() or "NeedsClarification" in str(type(exc.value))

@pytest.mark.asyncio
async def test_out_of_range_not_blocked_at_input_but_fails_later():
    extracted={"centralBody":"Earth","dryMassKg":500,"orbit":{"kind":"periapsisAltitudeKm","value":70,"unit":"km"},"eccentricity":0,"duration":{"value":1,"unit":"hours"},"integrator":"RungeKutta89","inclinationDeg":28.5,"raanDeg":0,"argumentOfPeriapsisDeg":0,"trueAnomalyDeg":0,"forces":None,"maneuvers":[],"cartesian":None}
    ext=FrontStepExtractor(); ext._fallback_extract=lambda t: extracted
    res=ext.deterministic_convert(extracted, "user text")
    assert res.status=="ok"
    exp={"version":"1.0","experimentName":"OutExp","spacecraft":{"name":"SC_OutExp","dryMassKg":500},"centralBody":"Earth","initialOrbit":{"type":"Keplerian","coordinateSystem":"EarthMJ2000Eq","elements":{"semiMajorAxisKm":6448.136,"eccentricity":0,"inclinationDeg":28.5,"raanDeg":0,"argumentOfPeriapsisDeg":0,"trueAnomalyDeg":0}},"forceModel":{"gravityDegree":4,"gravityOrder":4,"pointMasses":["Luna","Sun"],"atmosphericDrag":{"enabled":False,"model":"JacchiaRoberts"},"solarRadiationPressure":True},"propagation":{"integrator":"RungeKutta89","stopCondition":{"type":"ElapsedHours","value":1},"stepSizeSecs":60},"maneuvers":[]}
    interp=MockInterpreterClient(canned_json=json.dumps(exp))
    pipeline=Pipeline(extractor=ext, interpreter=interp, explainer=MockExplainer())
    with pytest.raises(Exception) as exc:
        await pipeline.run("dummy")
    assert exc.value.stage=="validate" or "validation" in str(exc.value).lower()
