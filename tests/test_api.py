import pytest, json
from fastapi.testclient import TestClient
from orbitlab_backend.api.app import create_app
from orbitlab_backend.frontstep.extractor import FrontStepExtractor
from orbitlab_backend.clients.interpreter_client import MockInterpreterClient
from orbitlab_backend.orchestrator.pipeline import Pipeline

# Provide a pipeline with mocked extractor/interpreter for API tests
@pytest.fixture
def client():
    app=create_app()
    return TestClient(app)

def test_health(client):
    r=client.get("/api/health")
    assert r.status_code==200
    assert r.json()["status"]=="ok"

def test_create_and_get_experiment(client):
    # Use mock via env var already
    r=client.post("/api/experiments", json={"text": "Earth 400 km circular 500 kg for 2 hours"})
    assert r.status_code==200
    jid=r.json()["id"]
    # Need to wait a bit for background task
    import time
    time.sleep(0.2)
    r2=client.get(f"/api/experiments/{jid}")
    assert r2.status_code==200
    data=r2.json()
    assert data["id"]==jid

@pytest.mark.asyncio
async def test_websocket_event_order():
    # Test pipeline event order directly
    extracted={"centralBody":"Earth","dryMassKg":500,"orbit":{"kind":"circularAltitudeKm","value":400,"unit":"km"},"duration":{"value":2,"unit":"hours"},"integrator":"RungeKutta89","inclinationDeg":28.5,"raanDeg":0,"argumentOfPeriapsisDeg":0,"trueAnomalyDeg":0,"forces":None,"maneuvers":[],"cartesian":None}
    ext=FrontStepExtractor(); ext._fallback_extract=lambda t: extracted
    correct={"version":"1.0","experimentName":"TestExp","spacecraft":{"name":"SC_TestExp","dryMassKg":500},"centralBody":"Earth","initialOrbit":{"type":"Keplerian","coordinateSystem":"EarthMJ2000Eq","elements":{"semiMajorAxisKm":6778.136,"eccentricity":0,"inclinationDeg":28.5,"raanDeg":0,"argumentOfPeriapsisDeg":0,"trueAnomalyDeg":0}},"forceModel":{"gravityDegree":4,"gravityOrder":4,"pointMasses":["Luna","Sun"],"atmosphericDrag":{"enabled":False,"model":"JacchiaRoberts"},"solarRadiationPressure":True},"propagation":{"integrator":"RungeKutta89","stopCondition":{"type":"ElapsedHours","value":2},"stepSizeSecs":60},"maneuvers":[]}
    from orbitlab_backend.clients.interpreter_client import MockInterpreterClient
    from orbitlab_backend.clients.explainer_client import MockExplainer
    interp=MockInterpreterClient(canned_json=json.dumps(correct))
    pipeline=Pipeline(extractor=ext, interpreter=interp, explainer=MockExplainer())
    events=[]
    async def cb(ev):
        events.append(ev.type+":"+ev.stage)
    res=await pipeline.run("dummy", event_cb=cb)
    # Check order for successful run: stage_completed for each in order
    expected=["stage_started:extract","stage_completed:extract","stage_started:interpret","stage_completed:interpret","stage_started:verify","stage_completed:verify","stage_started:validate","stage_completed:validate","stage_started:compile","stage_completed:compile","stage_started:simulate","stage_completed:simulate","stage_started:parse","stage_completed:parse","stage_started:explain","stage_completed:explain"]
    assert events==expected

@pytest.mark.asyncio
async def test_websocket_event_order_failing():
    extracted={"centralBody":"Earth","dryMassKg":500,"orbit":{"kind":"circularAltitudeKm","value":400,"unit":"km"},"duration":{"value":2,"unit":"hours"},"integrator":"RungeKutta89","inclinationDeg":28.5,"raanDeg":0,"argumentOfPeriapsisDeg":0,"trueAnomalyDeg":0,"forces":None,"maneuvers":[],"cartesian":None}
    ext=FrontStepExtractor(); ext._fallback_extract=lambda t: extracted
    mismatch={"version":"1.0","experimentName":"TestExp","spacecraft":{"name":"SC_TestExp","dryMassKg":500},"centralBody":"Earth","initialOrbit":{"type":"Keplerian","coordinateSystem":"EarthMJ2000Eq","elements":{"semiMajorAxisKm":7000,"eccentricity":0,"inclinationDeg":28.5,"raanDeg":0,"argumentOfPeriapsisDeg":0,"trueAnomalyDeg":0}},"forceModel":{"gravityDegree":4,"gravityOrder":4,"pointMasses":["Luna","Sun"],"atmosphericDrag":{"enabled":False,"model":"JacchiaRoberts"},"solarRadiationPressure":True},"propagation":{"integrator":"RungeKutta89","stopCondition":{"type":"ElapsedHours","value":2},"stepSizeSecs":60},"maneuvers":[]}
    from orbitlab_backend.clients.interpreter_client import MockInterpreterClient
    from orbitlab_backend.clients.explainer_client import MockExplainer
    interp=MockInterpreterClient(canned_json=json.dumps(mismatch))
    pipeline=Pipeline(extractor=ext, interpreter=interp, explainer=MockExplainer())
    events=[]
    async def cb(ev):
        events.append(ev.type+":"+ev.stage)
    try:
        await pipeline.run("dummy", event_cb=cb)
    except Exception:
        pass
    # Should have started extract, completed extract, started interpret, completed interpret, started verify, failed verify
    assert "stage_started:extract" in events
    assert "stage_failed:verify" in events
