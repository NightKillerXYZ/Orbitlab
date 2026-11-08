"""Step 6 tests: tolerant observed shapes + strict new-schema end-to-end conversion."""
import json

import pytest

from orbitlab_backend.clients.extractor_client import normalize_extracted, OpenAIExtractor
from orbitlab_backend.frontstep.extractor import FrontStepExtractor


class _FakeClient:
    """Stand-in for a model client: returns a RAW model-shaped dict."""

    def __init__(self, raw):
        import copy
        self._raw = copy.deepcopy(raw)

    async def extract(self, user_text):
        import copy
        return copy.deepcopy(self._raw)

    def extract_sync(self, user_text):
        import copy
        return copy.deepcopy(self._raw)


def _convert(raw, text="dummy probe text"):
    """Same pipeline path as production: process() -> normalize -> convert."""
    import asyncio
    from orbitlab_backend.frontstep.extractor import FrontStepExtractor
    return asyncio.run(FrontStepExtractor(extractor_client=_FakeClient(raw)).process(text))


# ---------- Step 6a: observed tolerant shapes ----------

def test_tolerant_s1_bare_circular_needs_quantity():
    raw = {"centralBody": "Earth", "dryMassKg": 500,
           "orbit": {"kind": "circular", "values": 400}, "duration": 1}
    res = _convert(raw, "Put a 500 kg satellite in a circular orbit at 400 km altitude around Earth for 1 day.")
    assert res.status == "needs_clarification"
    assert res.missing == ["orbit.quantity (is it an altitude or a radius?)"]


def test_tolerant_s2_periapsis_dict_works():
    raw = {"centralBody": "Mars", "dryMassKg": 1200,
           "orbit": {"kind": "elliptical", "values": {"periapsisAltitudeKm": 300, "eccentricity": 0.2}},
           "duration": "3 days"}
    res = _convert(raw, "Create a 1200 kg spacecraft around Mars with periapsis altitude 300 km and eccentricity 0.2 for 3 days.")
    assert res.status == "ok", res.missing
    assert res.data["semiMajorAxisKm"] == pytest.approx(4611.875, abs=1e-6)
    assert res.data["eccentricity"] == pytest.approx(0.2)
    assert res.data["stopConditionType"] == "ElapsedDays" and res.data["durationValue"] == 3


def test_tolerant_s3_sma_dict_works():
    raw = {"centralBody": "Venus", "dryMassKg": 800,
           "orbit": {"kind": "elliptical", "values": {"semiMajorAxisKm": 9000}},
           "eccentricity": 0.05, "inclinationDeg": 30, "duration": "5 orbits"}
    res = _convert(raw, "A 800 kg probe around Venus, semi-major axis 9000 km, eccentricity 0.05, inclination 30 degrees, for 5 orbits.")
    assert res.status == "ok", res.missing
    assert res.data["semiMajorAxisKm"] == 9000
    assert res.data["eccentricity"] == pytest.approx(0.05)
    assert res.data["inclinationDeg"] == 30
    assert res.data["stopConditionType"] == "OrbitPeriods" and res.data["durationValue"] == 5


def test_tolerant_s4_bare_circular_needs_quantity():
    raw = {"centralBody": "Earth", "dryMassKg": 300,
           "orbit": {"kind": "circular", "values": 150}, "duration": 12}
    res = _convert(raw, "Simulate a 300 kg satellite at 150 km altitude above the Earth with 4 degrees inclination for 12 hours.")
    assert res.status == "needs_clarification"
    assert res.missing == ["orbit.quantity (is it an altitude or a radius?)"]


def test_tolerant_s5_list_value_needs_quantity():
    raw = {"centralBody": "Moon", "dryMassKg": 500,
           "orbit": {"kind": "circular", "values": [150]}, "duration": "6 hours"}
    res = _convert(raw, "Moon orbit, 100 km altitude, 500 kg, 6 hours.")
    assert res.status == "needs_clarification"
    assert res.missing == ["orbit.quantity (is it an altitude or a radius?)"]


def test_tolerant_s6_bare_circular_needs_quantity():
    raw = {"centralBody": "Earth", "dryMassKg": 500,
           "orbit": {"kind": "circular", "values": 7000},
           "maneuvers": "Hohmann transfer to 9000 km at periapsis",
           "duration": "2 days"}
    res = _convert(raw, "500 kg satellite around Earth in a 7000 km circular orbit, Hohmann transfer to 9000 km at periapsis, 2 days.")
    assert res.status == "needs_clarification"
    assert res.missing == ["orbit.quantity (is it an altitude or a radius?)"]


def test_hohmann_free_text_parsed():
    out = normalize_extracted({"maneuvers": ["Hohmann transfer to 9000 km at periapsis"]})
    assert out["maneuvers"] == [{"type": "Hohmann", "id": "M1",
                                 "targetOrbitRadiusKm": 9000.0, "apsis": "periapsis"}]


def test_minutes_string_to_seconds():
    res = _convert({"centralBody": "Earth", "dryMassKg": 500,
                    "orbit": {"kind": "circularAltitudeKm", "value": 400, "unit": "km"},
                    "duration": "90 minutes"}, "test")
    assert res.status == "ok"
    assert res.data["stopConditionType"] == "ElapsedSeconds"
    assert res.data["durationValue"] == 5400


# ---------- Step 6b: strict new-schema end-to-end ----------

def _strict(body, mass, orbit, inc, dur_val, dur_unit):
    return {"centralBody": body, "dryMassKg": mass, "orbit": orbit,
            "inclinationDeg": inc, "raanDeg": None, "argumentOfPeriapsisDeg": None,
            "trueAnomalyDeg": None,
            "duration": None if dur_val is None else {"value": dur_val, "unit": dur_unit},
            "maneuvers": []}


def test_strict_s1_altitude():
    raw = _strict("Earth", 500, {"quantity": "altitude", "valueKm": 400, "eccentricity": None},
                  None, 1, "days")
    res = _convert(raw, "Put a 500 kg satellite in a circular orbit at 400 km altitude around Earth for 1 day.")
    assert res.status == "ok", res.missing
    assert res.data["semiMajorAxisKm"] == pytest.approx(6778.136, abs=1e-3)
    assert res.data["eccentricity"] == 0
    assert (res.data["stopConditionType"], res.data["durationValue"], res.data["durationUnit"]) == ("ElapsedDays", 1, "days")


def test_strict_s2_periapsis():
    raw = _strict("Mars", 1200, {"quantity": "periapsis_altitude", "valueKm": 300, "eccentricity": 0.2},
                  None, 3, "days")
    res = _convert(raw, "Create a 1200 kg spacecraft around Mars with periapsis altitude 300 km and eccentricity 0.2 for 3 days.")
    assert res.status == "ok", res.missing
    assert res.data["semiMajorAxisKm"] == pytest.approx(4611.875, abs=1e-6)
    assert res.data["eccentricity"] == pytest.approx(0.2)


def test_strict_s3_sma_orbit_periods():
    raw = _strict("Venus", 800, {"quantity": "semi_major_axis", "valueKm": 9000, "eccentricity": 0.05},
                  30, 5, "orbits")
    res = _convert(raw, "A 800 kg probe around Venus, semi-major axis 9000 km, eccentricity 0.05, inclination 30 degrees, for 5 orbits.")
    assert res.status == "ok", res.missing
    assert res.data["semiMajorAxisKm"] == 9000
    assert res.data["eccentricity"] == pytest.approx(0.05)
    assert res.data["inclinationDeg"] == 30
    assert (res.data["stopConditionType"], res.data["durationValue"], res.data["durationUnit"]) == ("OrbitPeriods", 5, "orbital periods")


def test_strict_s4_altitude_hours():
    raw = _strict("Earth", 300, {"quantity": "altitude", "valueKm": 150, "eccentricity": None},
                  4, 12, "hours")
    res = _convert(raw, "Simulate a 300 kg satellite at 150 km altitude above the Earth with 4 degrees inclination for 12 hours.")
    assert res.status == "ok", res.missing
    assert res.data["semiMajorAxisKm"] == pytest.approx(6528.136, abs=1e-3)
    assert res.data["inclinationDeg"] == 4
    assert res.data["stopConditionType"] == "ElapsedHours"


def test_strict_s5_moon():
    raw = _strict("Moon", 500, {"quantity": "altitude", "valueKm": 100, "eccentricity": None},
                  None, 6, "hours")
    res = _convert(raw, "Moon orbit, 100 km altitude, 500 kg, 6 hours.")
    assert res.status == "ok", res.missing
    assert res.data["semiMajorAxisKm"] == pytest.approx(1837.4, abs=1e-9)
    assert res.data["dryMassKg"] == 500


def test_strict_s6_radius_hohmann():
    raw = _strict("Earth", 500, {"quantity": "radius", "valueKm": 7000, "eccentricity": 0},
                  None, 2, "days")
    raw["maneuvers"] = [{"type": "hohmann_transfer", "trigger": "periapsis",
                         "targetRadiusKm": 9000, "elapsedSecs": None, "deltaVKmS": None}]
    res = _convert(raw, "500 kg satellite around Earth in a 7000 km circular orbit, Hohmann transfer to 9000 km at periapsis, 2 days.")
    assert res.status == "ok", res.missing
    assert res.data["semiMajorAxisKm"] == 7000
    assert res.data["eccentricity"] == 0
    assert res.data["maneuvers"] == [{"type": "Hohmann", "id": "M1",
                                     "targetOrbitRadiusKm": 9000, "apsis": "periapsis"}]
    assert (res.data["stopConditionType"], res.data["durationValue"]) == ("ElapsedDays", 2)


def test_names_always_generated():
    raw = _strict("Earth", 500, {"quantity": "altitude", "valueKm": 400, "eccentricity": None},
                  None, 1, "days")
    raw["spacecraftName"] = "IgnoredOne"
    raw["experimentName"] = "IgnoredTwo"
    res = _convert(raw, "dummy probe text")
    assert res.status == "ok"
    assert "IgnoredOne" not in (res.data["spacecraftName"], res.data["experimentName"])
    assert "IgnoredTwo" not in (res.data["spacecraftName"], res.data["experimentName"])


# ---------- Step 6c: json_schema body ----------

@pytest.mark.asyncio
async def test_json_schema_body_sent(monkeypatch):
    from httpx import AsyncClient, MockTransport, Response, Request
    import orbitlab_backend.clients.extractor_client as ec
    seen = {}

    async def handler(request: Request):
        seen["body"] = json.loads(request.content.decode())
        return Response(200, json={"choices": [{"message": {"content": '{"a": 1}'}}]})

    real = ec.httpx.AsyncClient

    class PatchedClient(AsyncClient):
        def __init__(self, *a, **kw):
            super().__init__(transport=MockTransport(handler), timeout=kw.get("timeout"))

    monkeypatch.setattr(ec.httpx, "AsyncClient", PatchedClient)
    try:
        client = OpenAIExtractor(base_url="http://fake/extractor", api_key="k",
                                 model="m", json_mode="json_schema", timeout_s=5)
        await client.extract("anything")
    finally:
        ec.httpx.AsyncClient = real
    sent = seen["body"]["response_format"]
    assert sent["type"] == "json_schema"
    assert sent["json_schema"]["name"] == "orbitlab_extraction"
    assert sent["json_schema"]["strict"] is True
    for key in ("centralBody", "dryMassKg", "orbit", "duration", "maneuvers"):
        assert key in sent["json_schema"]["schema"]["properties"]
    assert sent["json_schema"]["schema"]["additionalProperties"] is False


@pytest.mark.asyncio
async def test_prompt_mode_sends_no_response_format(monkeypatch):
    from httpx import AsyncClient, MockTransport, Response, Request
    import orbitlab_backend.clients.extractor_client as ec
    seen = {}

    async def handler(request: Request):
        seen["body"] = json.loads(request.content.decode())
        return Response(200, json={"choices": [{"message": {"content": '{"a": 1}'}}]})

    real = ec.httpx.AsyncClient

    class PatchedClient(AsyncClient):
        def __init__(self, *a, **kw):
            super().__init__(transport=MockTransport(handler), timeout=kw.get("timeout"))

    monkeypatch.setattr(ec.httpx, "AsyncClient", PatchedClient)
    try:
        client = OpenAIExtractor(base_url="http://fake/extractor", api_key="k",
                                 model="m", json_mode="prompt", timeout_s=5)
        await client.extract("anything")
    finally:
        ec.httpx.AsyncClient = real
    assert "response_format" not in seen["body"]


def test_null_duration_needs_clarification():
    res = _convert({"centralBody": "Earth", "dryMassKg": 500,
                    "orbit": {"quantity": "altitude", "valueKm": 400, "eccentricity": None},
                    "duration": None}, "test")
    assert res.status == "needs_clarification"
    assert res.missing == ["duration"]


def test_unknown_keys_ignored():
    res = _convert({"centralBody": "Earth", "dryMassKg": 500, "spacecraft": "X",
                    "orbit": {"quantity": "altitude", "valueKm": 400, "eccentricity": None, "extra": 1},
                    "duration": {"value": 2, "unit": "hours"}, "mystery": [1, 2]}, "test")
    assert res.status == "ok"
    assert res.data["semiMajorAxisKm"] == pytest.approx(6778.136, abs=1e-3)


def test_process_sync_path_uses_normalizer():
    from orbitlab_backend.frontstep.extractor import FrontStepExtractor
    raw = {"centralBody": "Earth", "dryMassKg": 500,
           "orbit": {"kind": "circular", "values": 400}, "duration": 1}
    res = FrontStepExtractor(extractor_client=_FakeClient(raw)).process_sync("test")
    assert res.status == "needs_clarification"
    assert res.missing == ["orbit.quantity (is it an altitude or a radius?)"]
