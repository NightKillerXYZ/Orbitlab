"""Fake interpreter HTTP server for tests."""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import json

app=FastAPI()
call_count={"n":0}
mode="correct"  # global for simple

# Scripted correct experiment
CORRECT_EXPERIMENT={
    "version":"1.0",
    "experimentName":"FakeExp",
    "spacecraft":{"name":"SC_FakeExp","dryMassKg":500},
    "centralBody":"Earth",
    "initialOrbit":{"type":"Keplerian","coordinateSystem":"EarthMJ2000Eq","elements":{"semiMajorAxisKm":6778.136,"eccentricity":0,"inclinationDeg":28.5,"raanDeg":0,"argumentOfPeriapsisDeg":0,"trueAnomalyDeg":0}},
    "forceModel":{"gravityDegree":4,"gravityOrder":4,"pointMasses":["Luna","Sun"],"atmosphericDrag":{"enabled":False,"model":"JacchiaRoberts"},"solarRadiationPressure":True},
    "propagation":{"integrator":"RungeKutta89","stopCondition":{"type":"ElapsedHours","value":2},"stepSizeSecs":60},
    "maneuvers":[]
}

MISMATCH_EXPERIMENT={**CORRECT_EXPERIMENT, "initialOrbit":{"type":"Keplerian","coordinateSystem":"EarthMJ2000Eq","elements":{"semiMajorAxisKm":7000,"eccentricity":0,"inclinationDeg":28.5,"raanDeg":0,"argumentOfPeriapsisDeg":0,"trueAnomalyDeg":0}}}

@app.post("/interpreter")
async def interpreter(request: Request):
    global mode
    body=await request.json()
    prompt=body.get("prompt","")
    # Use header or body to select mode via custom header X-Mode
    m=request.headers.get("X-Mode", mode)
    # Also allow mode via prompt substring
    if "mode:" in prompt:
        # e.g. "mode: mismatch"
        try:
            m=prompt.split("mode:")[1].split()[0]
        except:
            pass
    if m=="correct":
        return {"output": CORRECT_EXPERIMENT}
    elif m=="mismatch":
        return {"output": MISMATCH_EXPERIMENT}
    elif m=="json_string":
        return {"output": json.dumps(CORRECT_EXPERIMENT)}
    elif m=="503_then_success":
        call_count["n"]+=1
        if call_count["n"]==1:
            return JSONResponse(status_code=503, content={"error":"service unavailable"})
        else:
            return {"output": CORRECT_EXPERIMENT}
    elif m=="timeout":
        import asyncio
        await asyncio.sleep(5)
        return {"output": CORRECT_EXPERIMENT}
    elif m=="invalid_json":
        return {"output": "not json {{{"}
    elif m=="schema_invalid":
        bad={**CORRECT_EXPERIMENT, "spacecraft":{"name":"bad","dryMassKg":-10}}
        return {"output": bad}
    else:
        return {"output": CORRECT_EXPERIMENT}

@app.post("/reset")
async def reset():
    call_count["n"]=0
    return {"ok":True}
