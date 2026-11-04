"""FastAPI app for OrbitLab backend."""
from __future__ import annotations
import asyncio, logging, time
from typing import Dict, Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from orbitlab_backend.config import get_settings
from orbitlab_backend.orchestrator.pipeline import Pipeline
from orbitlab_backend.orchestrator.errors import NeedsClarification, PipelineError
from orbitlab_backend.api.store import store
from orbitlab_backend.api.run_cleanup import get_run_root, cleanup_old_run_dirs

logger=logging.getLogger("orbitlab.api")

class CreateExpRequest(BaseModel):
    text: str

def create_app() -> FastAPI:
    settings=get_settings()
    app=FastAPI(title="OrbitLab Backend", version="1.0")
    try:
        _root = get_run_root(getattr(settings, 'ORBITLAB_RUN_DIR', None))
        _n = cleanup_old_run_dirs(_root, getattr(settings, 'ORBITLAB_RUN_RETENTION_HOURS', 24.0))
        logger.info(f"run cleanup at startup: removed {_n} old dirs")
    except Exception as _e:
        logger.warning(f"run cleanup at startup skipped: {_e}")
    # CORS
    origins=settings.cors_origins_list()
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

    @app.get("/api/health")
    async def health():
        return {"status":"ok"}

    @app.post("/api/experiments")
    async def create_experiment(req: CreateExpRequest, background_tasks: BackgroundTasks):
        job=store.create(req.text)
        job.status="running"
        # log stage timings without secrets
        logger.info(f"created job {job.id}")
        # run pipeline as background task
        background_tasks.add_task(run_job, job.id, req.text)
        return {"id": job.id}

    @app.get("/api/experiments/{jid}")
    async def get_experiment(jid: str):
        job=store.get(jid)
        if not job:
            raise HTTPException(404, "job not found")
        resp={"id": job.id, "status": job.status, "events": job.events}
        if job.result:
            resp["result"]=job.result
        if job.error:
            resp["error"]=job.error
        return resp

    @app.websocket("/ws/experiments/{jid}")
    async def ws_experiments(ws: WebSocket, jid: str):
        await ws.accept()
        job=store.get(jid)
        if not job:
            await ws.close(code=4404)
            return
        q=store.subscribe(jid)
        # send existing events first
        for ev in job.events:
            await ws.send_json(ev)
        # if already finished, send final and close
        if job.status in ("success","failed"):
            if job.result:
                await ws.send_json({"type":"final","result":job.result})
            elif job.error:
                await ws.send_json({"type":"final","error":job.error})
            await ws.close()
            store.unsubscribe(jid,q)
            return
        try:
            while True:
                try:
                    event=await asyncio.wait_for(q.get(), timeout=60)
                    await ws.send_json(event)
                    if event.get("type")=="final":
                        break
                except asyncio.TimeoutError:
                    # check if job done
                    job=store.get(jid)
                    if job and job.status in ("success","failed"):
                        break
                    # keep alive
                    await ws.send_json({"type":"ping"})
                # also handle client messages (ignore)
                # check ws closed
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.warning(f"ws error {e}")
        finally:
            store.unsubscribe(jid,q)
            try:
                await ws.close()
            except Exception:
                pass

    return app

async def run_job(jid: str, text: str):
    pipeline=Pipeline()
    # event callback pushes to store
    async def cb(event):
        ev={"type": event.type, "stage": event.stage, "duration": event.duration, "message": event.message, "details": event.details}
        store.add_event(jid, ev)
        # also log stage timings without secrets
        logger.info(f"job {jid} {event.stage} {event.type} {event.duration:.3f}s")

    try:
        result=await pipeline.run(text, event_cb=cb)
        store.update(jid, status="success", result=result)
        store.add_event(jid, {"type":"final","result":result})
    except NeedsClarification as e:
        err={"stage": e.stage, "code": e.code, "message": e.message, "details": e.details}
        store.update(jid, status="failed", error=err)
        store.add_event(jid, {"type":"final","error":err})
    except PipelineError as e:
        err={"stage": e.stage, "code": e.code, "message": e.message, "details": e.details}
        store.update(jid, status="failed", error=err)
        store.add_event(jid, {"type":"final","error":err})
    except Exception as e:
        err={"stage":"unknown","code":"unknown","message":str(e)}
        store.update(jid, status="failed", error=err)
        store.add_event(jid, {"type":"final","error":err})
    finally:
        try:
            from orbitlab_backend.config import get_settings as _gs
            _s = _gs()
            cleanup_old_run_dirs(get_run_root(getattr(_s, 'ORBITLAB_RUN_DIR', None)), getattr(_s, 'ORBITLAB_RUN_RETENTION_HOURS', 24.0))
        except Exception:
            pass

# Default app instance
app=create_app()
