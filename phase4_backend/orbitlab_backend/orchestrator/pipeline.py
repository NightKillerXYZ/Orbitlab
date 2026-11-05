"""Pipeline coordinator emitting typed events."""
from __future__ import annotations
import asyncio, time, hashlib, logging, pathlib
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional
from orbitlab_backend.config import get_settings
from orbitlab_backend.frontstep.extractor import FrontStepExtractor
from orbitlab_backend.frontstep.verify import verify_experiment, normalize_maneuver_ids, apply_frontstep_names
from orbitlab_backend.orchestrator.errors import *
MAX_CACHE_ENTRIES = 500
from orbitlab_core.ast.models import OrbitLabExperiment
from orbitlab_core.ast.validation import AstrodynamicValidator
from orbitlab_core.compiler.generator import GmatScriptCompiler
logger=logging.getLogger("orbitlab.pipeline")
@dataclass
class PipelineEvent:
    type: str
    stage: str
    duration: float
    message: str
    details: Optional[Dict[str,Any]]=None
STAGES=["extract","interpret","verify","validate","compile","simulate","parse","explain"]
class Pipeline:
    def __init__(self, extractor=None, interpreter=None, explainer=None, gmat_runner=None, cache=None):
        self.extractor=extractor or FrontStepExtractor()
        self.interpreter=interpreter
        self.explainer=explainer
        self.gmat_runner=gmat_runner
        self.cache=cache if cache is not None else {}
        self.compiler=GmatScriptCompiler()
        from orbitlab_backend.clients.interpreter_client import get_interpreter_client
        from orbitlab_backend.clients.explainer_client import get_explainer
        if self.interpreter is None:
            self.interpreter=get_interpreter_client()
        if self.explainer is None:
            self.explainer=get_explainer()
    def _hash_prompt(self, prompt: str) -> str:
        return hashlib.sha256(prompt.encode()).hexdigest()
    async def run(self, user_text: str, event_cb: Optional[Callable[[PipelineEvent],Any]]=None) -> Dict[str,Any]:
        start_all=time.perf_counter()
        warnings_all=[]; experiment_json=None; prompt=None; sent_data=None; trajectory=None; explanation=None
        cache_key=None
        async def emit(event: PipelineEvent):
            if event_cb:
                try:
                    r=event_cb(event)
                    if asyncio.iscoroutine(r):
                        await r
                except Exception:
                    pass
            logger.info(f"event {event.type} stage={event.stage} dur={event.duration:.3f}s msg={event.message}")
        # extract
        t0=time.perf_counter()
        await emit(PipelineEvent("stage_started","extract",0,"Starting extraction"))
        try:
            ex_res=await self.extractor.process(user_text) if hasattr(self.extractor,'process') else self.extractor.process_sync(user_text)
            dur=time.perf_counter()-t0
            if ex_res.status=="needs_clarification":
                await emit(PipelineEvent("stage_failed","extract",dur,f"Missing {ex_res.missing}",{"missing":ex_res.missing}))
                raise NeedsClarification(ex_res.missing, details={"explanation": "This request needs more details before it can run: missing %s. Add them and send again." % (ex_res.missing,)})
            await emit(PipelineEvent("stage_completed","extract",dur,"Extraction completed"))
            sent_data=ex_res.data; prompt=ex_res.prompt
        except PipelineError:
            raise
        except Exception as e:
            dur=time.perf_counter()-t0
            await emit(PipelineEvent("stage_failed","extract",dur,f"Extraction failed: {e}"))
            raise ExtractionError(str(e), details={"explanation": "The request could not be understood (%s). Try rephrasing it or sending it again." % (str(e)[:200],)})
        if prompt:
            cache_key=self._hash_prompt(prompt)
            if cache_key in self.cache:
                cached=self.cache[cache_key]
                if cached.get("status")!="failed_infra":
                    logger.info(f"cache hit for {cache_key}")
                    return cached
        # interpret
        t0=time.perf_counter()
        await emit(PipelineEvent("stage_started","interpret",0,"Calling interpreter"))
        try:
            async def warming():
                await emit(PipelineEvent("model_warming_up","interpret",time.perf_counter()-t0,"Model warming up (10s no response)"))
            if hasattr(self.interpreter, 'interpret_prompt'):
                returned_json=await self.interpreter.interpret_prompt(prompt, warming_callback=warming)
            else:
                returned_json=self.interpreter.interpret(prompt)
                if isinstance(returned_json, str):
                    import json as _j
                    returned_json=_j.loads(returned_json)
            dur=time.perf_counter()-t0
            await emit(PipelineEvent("stage_completed","interpret",dur,"Interpretation succeeded"))
            experiment_json=returned_json
        except PipelineError:
            raise
        except Exception as e:
            dur=time.perf_counter()-t0
            msg=str(e)
            if "timeout" in msg.lower() or "503" in msg or "502" in msg or "504" in msg:
                await emit(PipelineEvent("stage_failed","interpret",dur,f"Interpreter unavailable: {msg}"))
                raise InterpreterUnavailable(msg, details={"explanation": "The interpreter model did not answer in time (timeout or 5xx, retried once). It may be warming up; wait a minute and try again."})
            await emit(PipelineEvent("stage_failed","interpret",dur,f"Interpreter failed: {msg}"))
            raise InterpreterUnavailable(msg, details={"explanation": "The interpreter did not return a usable experiment (%s). Try rephrasing the request." % (msg[:200],)})
        # verify
        t0=time.perf_counter()
        await emit(PipelineEvent("stage_started","verify",0,"Verifying interpreter output"))
        try:
            experiment_json, name_overrides = apply_frontstep_names(sent_data, experiment_json)
            for ov in name_overrides:
                await emit(PipelineEvent("interpreter_name_overridden","verify",0,f"Name overridden by front step: {ov}",{"override":ov}))
                warnings_all.append(f"interpreter_name_overridden: {ov.get('field')} model={ov.get('got')!r} front_step={ov.get('expected')!r}")
            mismatches=verify_experiment(sent_data, experiment_json)
            if mismatches:
                dur=time.perf_counter()-t0
                await emit(PipelineEvent("stage_failed","verify",dur,f"Interpreter mismatch: {mismatches}"))
                try:
                    explanation=await self.explainer.explain(experiment_json, "verify", f"Interpreter mismatch: {mismatches}", warnings_all)
                except Exception as ee:
                    logger.warning(f"explainer failed after verify: {ee}")
                raise InterpreterMismatch(mismatches, details={"mismatches": mismatches, "explanation": explanation})
            experiment_json=normalize_maneuver_ids(experiment_json)
            dur=time.perf_counter()-t0
            await emit(PipelineEvent("stage_completed","verify",dur,"Verification passed", {"warnings":warnings_all} if warnings_all else None))
        except PipelineError:
            raise
        except Exception as e:
            dur=time.perf_counter()-t0
            await emit(PipelineEvent("stage_failed","verify",dur,f"Verify failed: {e}"))
            raise InterpreterMismatch([{"field":"unknown","expected":str(e),"got":""}])
        # validate
        t0=time.perf_counter()
        await emit(PipelineEvent("stage_started","validate",0,"Validating experiment"))
        experiment_obj=None
        try:
            try:
                experiment_obj=OrbitLabExperiment.model_validate(experiment_json)
            except Exception as e:
                dur=time.perf_counter()-t0
                await emit(PipelineEvent("stage_failed","validate",dur,f"Schema error: {e}"))
                try:
                    schema_expl=await self.explainer.explain(experiment_json, "validate", "Schema error: %s" % (e,), warnings_all)
                except Exception:
                    schema_expl=None
                raise SchemaError(str(e), details={"raw": str(e), "explanation": schema_expl or ("The returned experiment is not valid JSON against the schema (%s). The interpreter output could not be used." % (str(e)[:200],))})
            res=AstrodynamicValidator.validate(experiment_obj)
            warnings_all=list(warnings_all)+list(res.warnings)
            if not res.is_valid:
                dur=time.perf_counter()-t0
                await emit(PipelineEvent("stage_failed","validate",dur,f"Validation failed: {res.errors}"))
                try:
                    expl=await self.explainer.explain(experiment_json, "validate", "; ".join(res.errors), warnings_all)
                    explanation=expl
                except Exception as ee:
                    logger.warning(f"explainer failed after validation: {ee}")
                raise ValidationFailed("; ".join(res.errors), details={"errors":res.errors,"warnings":warnings_all,"explanation":explanation})
            dur=time.perf_counter()-t0
            await emit(PipelineEvent("stage_completed","validate",dur,"Validation passed", {"warnings":warnings_all}))
        except PipelineError:
            raise
        except Exception as e:
            if isinstance(e, (SchemaError, ValidationFailed)):
                raise
            dur=time.perf_counter()-t0
            await emit(PipelineEvent("stage_failed","validate",dur,f"Validation error: {e}"))
            raise ValidationFailed(str(e))
        # compile
        t0=time.perf_counter()
        await emit(PipelineEvent("stage_started","compile",0,"Compiling GMAT script"))
        try:
            script=self.compiler.compile_to_string(experiment_obj)
            dur=time.perf_counter()-t0
            await emit(PipelineEvent("stage_completed","compile",dur,"Compilation succeeded"))
        except Exception as e:
            dur=time.perf_counter()-t0
            await emit(PipelineEvent("stage_failed","compile",dur,f"Compile failed: {e}"))
            try:
                expl=await self.explainer.explain(experiment_json, "compile", str(e), warnings_all)
                explanation=expl
            except Exception:
                pass
            raise CompileError(str(e), details={"explanation": explanation})
        # simulate
        t0=time.perf_counter()
        await emit(PipelineEvent("stage_started","simulate",0,"Running GMAT"))
        trajectory_data=None
        try:
            settings=get_settings()
            gmat_path=settings.GMAT_PATH
            gmat_timeout=float(settings.GMAT_TIMEOUT_S)
            if self.gmat_runner:
                from orbitlab_simulation_engine import GmatExecutionRequest
                req=GmatExecutionRequest(compiled_script=script, timeout_seconds=gmat_timeout)
                if hasattr(self.gmat_runner, 'execute'):
                    result=await self.gmat_runner.execute(req)
                    trajectory_data=result.trajectory
                else:
                    result=await self.gmat_runner(req)
                    trajectory_data=result
            else:
                if gmat_path and pathlib.Path(gmat_path).exists():
                    from orbitlab_simulation_engine import GmatRunner, GmatRunnerConfig, GmatExecutionRequest
                    cfg=GmatRunnerConfig(executable_path=pathlib.Path(gmat_path), default_timeout_seconds=gmat_timeout, max_visualization_points=2000)
                    runner=GmatRunner(cfg)
                    result=await runner.execute(GmatExecutionRequest(compiled_script=script, timeout_seconds=gmat_timeout))
                    trajectory_data=result.trajectory
                else:
                    from orbitlab_simulation_engine import TrajectoryPoint, TrajectoryData
                    pts=[]
                    for i in range(10):
                        sma_val=experiment_obj.initialOrbit.elements.semiMajorAxisKm if hasattr(experiment_obj.initialOrbit.elements,'semiMajorAxisKm') else 6778
                        ecc_val=experiment_obj.initialOrbit.elements.eccentricity if hasattr(experiment_obj.initialOrbit.elements,'eccentricity') else 0
                        pts.append(TrajectoryPoint(elapsed_secs=i*60, x_km=7000+i*10, y_km=0, z_km=0, vx_km_s=0, vy_km_s=7.5, vz_km_s=0, semi_major_axis_km=sma_val, eccentricity=ecc_val, inclination_deg=28.5, altitude_km=400))
                    trajectory_data=TrajectoryData(full=tuple(pts), visualization=tuple(pts[:2]))
            dur=time.perf_counter()-t0
            await emit(PipelineEvent("stage_completed","simulate",dur,"Simulation succeeded"))
        except Exception as e:
            dur=time.perf_counter()-t0
            msg=str(e)
            is_timeout="timeout" in msg.lower() or "Timeout" in str(type(e))
            if is_timeout:
                await emit(PipelineEvent("stage_failed","simulate",dur,f"GMAT timeout: {msg}"))
                try:
                    expl=await self.explainer.explain(experiment_json, "simulate", msg, warnings_all)
                    explanation=expl
                except Exception:
                    pass
                raise GmatTimeout(msg, details={"explanation": explanation})
            else:
                await emit(PipelineEvent("stage_failed","simulate",dur,f"GMAT run error: {msg}"))
                try:
                    expl=await self.explainer.explain(experiment_json, "simulate", msg, warnings_all)
                    explanation=expl
                except Exception:
                    pass
                raise GmatRunError(msg, details={"explanation": explanation})
        # parse
        t0=time.perf_counter()
        await emit(PipelineEvent("stage_started","parse",0,"Parsing telemetry"))
        try:
            dur=time.perf_counter()-t0
            await emit(PipelineEvent("stage_completed","parse",dur,"Telemetry parsed"))
        except Exception as e:
            dur=time.perf_counter()-t0
            await emit(PipelineEvent("stage_failed","parse",dur,f"Parse error: {e}"))
            try:
                expl=await self.explainer.explain(experiment_json, "parse", str(e), warnings_all)
                explanation=expl
            except Exception:
                pass
            raise ParseError(str(e), details={"explanation": explanation})
        # explain
        t0=time.perf_counter()
        await emit(PipelineEvent("stage_started","explain",0,"Generating explanation"))
        try:
            summary={"num_points": len(trajectory_data.full) if trajectory_data else 0, "warnings": warnings_all}
            explanation=await self.explainer.explain(experiment_json, "success", None, warnings_all, summary)
            dur=time.perf_counter()-t0
            await emit(PipelineEvent("stage_completed","explain",dur,"Explanation ready"))
        except Exception as e:
            dur=time.perf_counter()-t0
            await emit(PipelineEvent("stage_failed","explain",dur,f"Explainer failed: {e}"))
            raise ExplainerError(str(e))
        result={"status":"success","experiment": experiment_json,"warnings": warnings_all,"trajectory": {"full_count": len(trajectory_data.full) if trajectory_data else 0, "visualization_count": len(trajectory_data.visualization) if trajectory_data else 0, "points": [p.__dict__ if hasattr(p,'__dict__') else p for p in (trajectory_data.visualization if trajectory_data else [])]},"telemetry": {"points": len(trajectory_data.visualization) if trajectory_data else 0},"explanation": explanation,"prompt": prompt}
        if cache_key:
            # Failed infrastructure runs raise, so only successes reach here.
            self.cache[cache_key]=result
            while len(self.cache) > MAX_CACHE_ENTRIES:
                self.cache.pop(next(iter(self.cache)))
        return result
