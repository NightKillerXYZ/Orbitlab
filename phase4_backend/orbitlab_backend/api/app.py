"""FastAPI app for OrbitLab backend."""
from __future__ import annotations
import asyncio, logging, time
from pathlib import Path
from typing import Dict, Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from orbitlab_backend.config import get_settings
from orbitlab_backend.orchestrator.pipeline import Pipeline
from orbitlab_backend.orchestrator.errors import NeedsClarification, PipelineError
from orbitlab_backend.api.store import store

def _find_uiux_dir() -> Path | None:
    here = Path(__file__).resolve()
    for base in [here.parent.parent.parent.parent, Path.cwd(), Path.cwd() / "phase4_backend"]:
        cand = base / "UIUX"
        if cand.is_dir():
            return cand
    return None
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
        try:
            from orbitlab_backend.frontstep.demo import demo_enabled
            if demo_enabled():
                return {"status":"ok","mode":"demo"}
        except Exception:
            pass
        return {"status":"ok"}

    @app.post("/api/experiments")
    async def create_experiment(req: CreateExpRequest, background_tasks: BackgroundTasks):
        if not req.text or not req.text.strip():
            raise HTTPException(422, "text must be a non-empty string")
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

    @app.get("/api/experiments/{jid}/script", include_in_schema=False)
    async def experiment_script(jid: str):
        # jid is validated against known runs; the filesystem path is built
        # only from the server-side job id plus a fixed file name, so client
        # text can never become a path.
        if not isinstance(jid, str) or not jid or "/" in jid or "\\" in jid or ".." in jid:
            raise HTTPException(404, "script not found")
        job=store.get(jid)
        if not job:
            raise HTTPException(404, "script not found")
        try:
            _path=get_run_root(getattr(settings, 'ORBITLAB_RUN_DIR', None)) / job.id / "experiment.script"
        except Exception:
            raise HTTPException(404, "script not found")
        if not _path.is_file():
            raise HTTPException(404, "script not found")
        return PlainTextResponse(_path.read_text(encoding="utf-8"), media_type="text/plain; charset=utf-8")

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

    # Serve the static UIUX folder at "/". Registered AFTER the /api and /ws
    # routes so they keep priority. Same-origin: the UI uses relative URLs.
    ui_dir = _find_uiux_dir()
    if ui_dir is not None:
        adapter_src = Path(__file__).resolve().parent / "ui_adapter.js"

        @app.get("/", include_in_schema=False)
        async def ui_index():
            # Redirect (not a direct file response) so the page's relative
            # css/js/asset paths keep working.
            from fastapi.responses import RedirectResponse
            return RedirectResponse("/OrbitlabUI%20Main/")

        @app.get("/ui_adapter.js", include_in_schema=False)
        async def ui_adapter():
            return FileResponse(adapter_src, media_type="application/javascript")

        # Dev-only sample of a real successful run (fixed file, no listing:
        # exposes nothing else). Powers ?fixture=1 in the Main UI.
        @app.get("/sample-result", include_in_schema=False)
        async def sample_result():
            p = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "real_result_earth.json"
            if not p.is_file():
                raise HTTPException(404, "sample result not found")
            return FileResponse(p, media_type="application/json")

        # The finished Mission Assistant UI. Its folder name contains a space,
        # so redirect to the literal static path; relative css/js/assets then
        # resolve without extra routes.
        @app.get("/main", include_in_schema=False)
        async def ui_main():
            from fastapi.responses import RedirectResponse
            return RedirectResponse("/OrbitlabUI%20Main/")

        app.mount("/", StaticFiles(directory=ui_dir, html=True), name="ui")
        logger.info(f"serving UI from {ui_dir}")
    else:
        logger.warning("UIUX folder not found; serving API only")

    return app

async def run_job(jid: str, text: str):
    pipeline=Pipeline()
    # event callback pushes to store
    async def cb(event):
        ev={"type": event.type, "stage": event.stage, "duration": event.duration, "message": event.message, "details": event.details}
        if event.type == "progress" and isinstance(event.details, dict):
            for _k in ("elapsedSecs", "estimateSecs"):
                if _k in event.details:
                    ev[_k] = event.details[_k]
        store.add_event(jid, ev)
        # also log stage timings without secrets
        logger.info(f"job {jid} {event.stage} {event.type} {event.duration:.3f}s")

    try:
        result=await pipeline.run(text, event_cb=cb)
        try:
            _script=result.get("script") if isinstance(result, dict) else None
            if isinstance(_script, str) and _script:
                _s=get_settings()
                _root=get_run_root(getattr(_s, 'ORBITLAB_RUN_DIR', None))
                _jobdir=_root / jid
                _jobdir.mkdir(parents=True, exist_ok=True)
                (_jobdir / "experiment.script").write_text(_script, encoding="utf-8")
                result["hasScript"]=True
        except Exception:
            logger.warning(f"job {jid} script persist skipped")
        store.update(jid, status="success", result=result)
        store.add_event(jid, {"type":"final","result":result})
    except NeedsClarification as e:
        err={"stage": e.stage, "code": e.code, "message": e.message, "details": e.details}
        try:
            expl=(e.details or {}).get("explanation")
            if expl:
                err={"stage": e.stage, "code": e.code, "message": e.message, "details": e.details, "explanation": expl}
        except Exception:
            pass
        store.update(jid, status="failed", error=err)
        store.add_event(jid, {"type":"final","error":err})
    except PipelineError as e:
        err={"stage": e.stage, "code": e.code, "message": e.message, "details": e.details}
        try:
            expl=(e.details or {}).get("explanation")
            if expl:
                err={"stage": e.stage, "code": e.code, "message": e.message, "details": e.details, "explanation": expl}
        except Exception:
            pass
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
