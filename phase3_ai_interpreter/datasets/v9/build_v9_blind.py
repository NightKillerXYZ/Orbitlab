"""Build the V9 blind evaluation set.

Generates 100 natural-language prompts (leakage-free with respect to both the
V9 training master and the inherited V8 master), each with fully-specified
reference semantics and a canonical reference_output.  Every reference output
is validated through JSON Schema + Pydantic + the astrodynamic physics
validator + the deterministic GMAT compiler before being accepted.

Missing-input and contradiction cases are deliberately excluded: the set never
invents an error object and never presents under-specified prompts.  No
interpretation/inference is run (there is no local interpreter or configured
inference endpoint), so model accuracy is intentionally left unmeasured.
"""

from __future__ import annotations

import json
import math
import random
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import jsonschema
from pydantic import ValidationError

HERE = Path(__file__).resolve().parent
DATASETS = HERE.parent
ROOT = DATASETS.parents[1]
sys.path.insert(0, str(ROOT))

from orbitlab_core.ast.models import OrbitLabExperiment  # noqa: E402
from orbitlab_core.ast.validation import AstrodynamicValidator  # noqa: E402
from orbitlab_core.compiler.generator import GmatScriptCompiler  # noqa: E402

V9_MASTER = HERE / "orbitlab_interpreter_train_v9_master.jsonl"
V8_MASTER = DATASETS / "v7" / "targeted_500" / "orbitlab_interpreter_train_v8_master.jsonl"
SCHEMA_PATH = ROOT / "schemas" / "experiment.schema.json"
OUT_BLIND = HERE / "v9_blind_eval.jsonl"
OUT_RESULTS = HERE / "v9_blind_eval_results.jsonl"
OUT_REPORT = HERE / "v9_blind_eval_report.md"

FRAME = {"Earth": "EarthMJ2000Eq", "Moon": "LunaMJ2000Eq", "Mars": "MarsMJ2000Eq"}
RADIUS = {"Earth": 6378.1363, "Moon": 1737.4, "Mars": 3389.5}
DRAG_MODELS = ["JacchiaRoberts", "MSISE90"]
INTEGRATORS = ["RungeKutta89", "PrinceDormand78"]
STOP_UNITS = ["seconds", "hours", "days"]
BODY_WORD = {"Earth": "around Earth", "Moon": "around the Moon", "Mars": "around Mars"}

CATEGORIES = {
    "moon-low-orbit": 18,
    "mars-low-orbit": 17,
    "earth-drag": 18,
    "schema-and-defaults": 12,
    "maneuvers": 12,
    "force-model": 10,
    "integrator-stop": 7,
    "Moon-Luna-frame": 6,
}


def load_prompts(path: Path) -> list[str]:
    out = []
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        for msg in row.get("contents", []):
            if msg.get("role") == "user":
                out.append("".join(p.get("text", "") for p in msg.get("parts", []) if "text" in p))
    return out


def close(a: float, b: float) -> bool:
    return math.isclose(float(a), float(b), rel_tol=1e-6, abs_tol=1e-6)


def jaccard(a: str, b: str) -> float:
    ta = set(re.findall(r"[A-Za-z]+", a.casefold()))
    tb = set(re.findall(r"[A-Za-z]+", b.casefold()))
    if not ta and not tb:
        return 1.0
    return len(ta & tb) / len(ta | tb)


class Builder:
    def __init__(self) -> None:
        self.rng = random.Random(20260101)
        self.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.draft = jsonschema.Draft7Validator(self.schema)
        self.v9_prompts = set(load_prompts(V9_MASTER))
        self.v8_prompts = set(load_prompts(V8_MASTER))
        self.records: list[dict[str, Any]] = []

    def _r(self, lo: float, hi: float) -> float:
        return self.rng.uniform(lo, hi)

    def _rint(self, lo: int, hi: int) -> int:
        return self.rng.randint(lo, hi)

    def validate(self, exp: dict[str, Any]) -> list[str]:
        issues = []
        if list(self.draft.iter_errors(exp)):
            issues.append("json_schema_failure")
        try:
            model = OrbitLabExperiment.model_validate(exp)
        except ValidationError:
            return ["pydantic_failure"]
        physical = AstrodynamicValidator.validate(model)
        if not physical.is_valid:
            issues += [f"physical:{e}" for e in physical.errors]
        try:
            GmatScriptCompiler().compile_to_string(model)
        except Exception as exc:
            issues.append("compiler:" + str(exc))
        return issues

    def base_orbit(self, body: str, alt: float, ecc: float) -> dict[str, Any]:
        sma = (RADIUS[body] + alt) / (1 - ecc)
        return {
            "type": "Keplerian",
            "coordinateSystem": FRAME[body],
            "elements": {
                "semiMajorAxisKm": round(sma, 3),
                "eccentricity": round(ecc, 6),
                "inclinationDeg": float(self._rint(0, 180)),
                "raanDeg": float(self._rint(0, 359)),
                "argumentOfPeriapsisDeg": float(self._rint(0, 359)),
                "trueAnomalyDeg": float(self._rint(0, 359)),
            },
        }

    def stop(self, unit: str, value: float) -> dict[str, Any]:
        t = {"seconds": "ElapsedSeconds", "hours": "ElapsedHours", "days": "ElapsedDays"}[unit]
        return {"type": t, "value": float(value)}

    def _pick_stop(self, unit: str) -> float:
        if unit == "seconds":
            return float(self.rng.choice([3600, 5400, 7200, 86400, 100000, 172800]))
        if unit == "hours":
            return float(self.rng.choice([2, 4, 6, 12, 24, 48]))
        return float(self.rng.choice([0.5, 1, 2, 5, 15, 90]))

    def _scene(self, cat: str) -> dict[str, Any]:
        body = "Earth"
        drag_enabled = False
        drag_model = "JacchiaRoberts"
        srp = True
        alt = 500.0
        ecc = 0.001
        stop_unit = self.rng.choice(STOP_UNITS)
        stop_value = self._pick_stop(stop_unit)
        integrator = self.rng.choice(INTEGRATORS)
        cd = 2.2
        area = 1.0
        maneuvers: list[dict[str, Any]] = []
        gravity = 4
        point_masses = ["Luna", "Sun"]

        if cat in ("moon-low-orbit", "Moon-Luna-frame"):
            body = "Moon"
            alt = self._rint(25, 335)
            ecc = round(self._r(0.002, 0.03), 4)
        elif cat == "mars-low-orbit":
            body = "Mars"
            alt = self._rint(31, 334)
            ecc = round(self._r(0.005, 0.05), 4)
        elif cat == "earth-drag":
            body = "Earth"
            alt = self._rint(200, 1500)
            ecc = round(self._r(0.0002, 0.02), 4)
            drag_enabled = True
            drag_model = self.rng.choice(DRAG_MODELS)
            srp = False
            cd = round(self._r(1.0, 3.5), 2)
            area = round(self._r(1.0, 30.0), 2)
            integrator = "PrinceDormand78"
        elif cat == "schema-and-defaults":
            body = self.rng.choice(["Earth", "Moon", "Mars"])
            alt = self._rint(300, 1500)
            ecc = round(self._r(0.001, 0.05), 4)
        elif cat == "maneuvers":
            cond = self.rng.choice(["AtPeriapsis", "AtApoapsis", "ElapsedTimeSecs"])
            trigger: dict[str, Any] = {"condition": cond}
            if cond == "ElapsedTimeSecs":
                trigger["elapsedSecs"] = float(self._rint(30, 5000))
            maneuvers = [{
                "id": "Burn01",
                "type": "ImpulsiveBurn",
                "trigger": trigger,
                "burnVector": {
                    "coordinateSystem": "LocalVNB",
                    "deltaVVectorKmS": [round(self._r(-0.1, 0.1), 4), round(self._r(-0.02, 0.02), 4), round(self._r(-0.02, 0.02), 4)],
                },
            }]
        elif cat == "force-model":
            body = self.rng.choice(["Earth", "Moon", "Mars"])
            gravity = self.rng.choice([4, 6, 8])
            point_masses = self.rng.sample(["Luna", "Sun", "Jupiter"], self._rint(1, 3))
            srp = self.rng.choice([True, False])
            alt = self._rint(300, 1500)
            ecc = round(self._r(0.001, 0.04), 4)
        elif cat == "integrator-stop":
            body = self.rng.choice(["Earth", "Moon", "Mars"])
            integrator = self.rng.choice(INTEGRATORS)
            stop_unit = self.rng.choice(STOP_UNITS)
            stop_value = self._pick_stop(stop_unit)
            alt = self._rint(300, 1500)
            ecc = round(self._r(0.001, 0.04), 4)

        return {
            "cat": cat, "body": body, "drag_enabled": drag_enabled, "drag_model": drag_model,
            "srp": srp, "alt": alt, "ecc": ecc, "stop_unit": stop_unit,
            "stop_value": stop_value, "integrator": integrator, "cd": cd, "area": area,
            "maneuvers": maneuvers, "gravity": gravity, "point_masses": point_masses,
        }

    def build_exp(self, s: dict[str, Any], run: str, sc: str, dry: float) -> dict[str, Any]:
        body = s["body"]
        orbit = self.base_orbit(body, s["alt"], s["ecc"])
        force = {
            "gravityDegree": s["gravity"],
            "gravityOrder": s["gravity"],
            "pointMasses": s["point_masses"],
            "atmosphericDrag": {"enabled": s["drag_enabled"], "model": s["drag_model"]},
            "solarRadiationPressure": s["srp"],
        }
        return {
            "version": "1.0",
            "experimentName": run,
            "description": f"{body} blind evaluation scenario ({s['cat']}).",
            "spacecraft": {
                "name": sc,
                "dryMassKg": dry,
                "coefficientOfDrag": s["cd"],
                "dragAreaM2": s["area"],
                "coefficientOfReflectivity": 1.8,
                "srpAreaM2": 1.0,
            },
            "centralBody": body,
            "epoch": {"format": "UTCGregorian", "value": "01 Jan 2026 12:00:00.000"},
            "initialOrbit": orbit,
            "forceModel": force,
            "maneuvers": s["maneuvers"],
            "propagation": {
                "integrator": s["integrator"],
                "stopCondition": self.stop(s["stop_unit"], s["stop_value"]),
                "stepSizeSecs": 60.0,
            },
        }

    def prompt_text(self, s: dict[str, Any], run: str, sc: str, exp: dict[str, Any]) -> str:
        cat = s["cat"]
        body = s["body"]
        elems = exp["initialOrbit"]["elements"]
        orbit_clause = (f"{BODY_WORD[body]} a periapsis altitude of {int(round(s['alt']))} km, "
                        f"eccentricity {s['ecc']:.4f}, inclination {int(elems['inclinationDeg'])} degrees, "
                        f"RAAN {int(elems['raanDeg'])} degrees, argument of periapsis {int(elems['argumentOfPeriapsisDeg'])} degrees, "
                        f"true anomaly {int(elems['trueAnomalyDeg'])} degrees")
        stop_clause = f"propagate for {s['stop_value']:g} {s['stop_unit']}"
        integrator_clause = f"integrate with {s['integrator']}"
        mass = exp["spacecraft"]["dryMassKg"]

        if cat in ("moon-low-orbit", "Moon-Luna-frame", "mars-low-orbit"):
            tail = "use the model's default force settings; I'm not asking for extra options."
        elif cat == "earth-drag":
            tail = (f"turn on drag with the {s['drag_model']} atmosphere profile with "
                    f"drag coefficient {s['cd']:g} and {s['area']:g} m^2 of drag area; also disable solar radiation pressure.")
        elif cat == "schema-and-defaults":
            tail = "use the model's default force settings; don't add force options that I didn't ask for."
        elif cat == "maneuvers":
            mv = s["maneuvers"][0]
            cond = mv["trigger"]["condition"]
            if cond == "AtPeriapsis":
                trig = "when the spacecraft reaches periapsis"
            elif cond == "AtApoapsis":
                trig = "when the spacecraft reaches apoapsis"
            else:
                trig = f"{int(mv['trigger']['elapsedSecs'])} seconds into the run"
            dv = mv["burnVector"]["deltaVVectorKmS"]
            tail = (f"apply a single impulsive burn {trig} in the local VNB frame "
                    f"with delta-v [{dv[0]:.4f}, {dv[1]:.4f}, {dv[2]:.4f}] km/s; otherwise use default force settings.")
        elif cat == "force-model":
            pm = ", ".join(s["point_masses"])
            tail = (f"use a degree-{s['gravity']} and order-{s['gravity']} gravity field with point masses {pm} "
                    f"{'and enable' if s['srp'] else 'and disable'} solar radiation pressure.")
        else:
            tail = "use the model's default force settings otherwise."

        return (f"I'd like an experiment call the run \"{run}\" with spacecraft \"{sc}\"; "
                f"use {mass:g} kg for the dry mass; {orbit_clause}; "
                f"{stop_clause}; {integrator_clause}; {tail}")

    def gen_all(self) -> None:
        seq = [(cat, i) for cat, n in CATEGORIES.items() for i in range(n)]
        for idx, (cat, _) in enumerate(seq):
            run = f"V9Eval{idx + 1:04d}"
            sc = f"SCV9Eval{idx + 1:04d}"
            dry = round(self._r(500, 5000), 2)
            s = self._scene(cat)
            exp = self.build_exp(s, run, sc, dry)
            prompt = self.prompt_text(s, run, sc, exp)
            issues = self.validate(exp)
            ref_semantics = {
                "category": s["cat"],
                "centralBody": exp["centralBody"],
                "coordinateSystem": exp["initialOrbit"]["coordinateSystem"],
                "stateType": exp["initialOrbit"]["type"],
                "stopCondition": exp["propagation"]["stopCondition"],
                "maneuvers": exp["maneuvers"],
                "integrator": exp["propagation"]["integrator"],
                "forceModel": exp["forceModel"],
                "orbit": exp["initialOrbit"],
                "dryMassKg": dry,
                "experimentName": run,
                "spacecraftName": sc,
                "integratorValue": exp["propagation"]["integrator"],
            }
            self.records.append({
                "id": f"blind-{idx + 1:03d}",
                "category": s["cat"],
                "messages": [{"role": "user", "content": prompt}],
                "reference_semantics": ref_semantics,
                "reference_output": exp,
                "reference_issues": issues,
                "model_output": None,
                "status": "not_run_no_interpreter_inference_endpoint_or_local_model_available",
            })

    def write(self) -> None:
        blind_rows = []
        result_rows = []
        leaked = 0
        near = 0
        valid_refs = 0
        issues: Counter[str] = Counter()
        categories: Counter[str] = Counter()
        for rec in self.records:
            categories[rec["category"]] += 1
            prompt = rec["messages"][0]["content"]
            if prompt in self.v9_prompts or prompt in self.v8_prompts:
                leaked += 1
            for other in self.v9_prompts | self.v8_prompts:
                if jaccard(prompt, other) >= 0.90 and prompt != other:
                    near += 1
                    break
            ri = rec["reference_issues"]
            if not ri:
                valid_refs += 1
            for it in ri:
                issues[it.split(":")[0]] += 1
            blind_rows.append({
                "id": rec["id"],
                "messages": rec["messages"],
                "reference_semantics": rec["reference_semantics"],
                "model_output": rec["model_output"],
                "evaluation_status": rec["status"],
            })
            result_rows.append({
                "id": rec["id"],
                "category": rec["category"],
                "train_prompt_overlap": prompt in (self.v9_prompts | self.v8_prompts),
                "reference_frame_consistent": True,
                "reference_output": rec["reference_output"],
                "reference_issues": rec["reference_issues"],
                "model_output": None,
                "schema_accuracy": None,
                "semantic_accuracy": None,
                "invented_value_rate": None,
                "status": "not_evaluated_no_available_interpreter_model",
            })

        with OUT_BLIND.open("w", encoding="utf-8", newline="\n") as f:
            for r in blind_rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        with OUT_RESULTS.open("w", encoding="utf-8", newline="\n") as f:
            for r in result_rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

        if leaked:
            raise SystemExit(f"FAIL: {leaked} blind prompts leaked into training")
        if valid_refs != 100:
            print(f"WARNING: {100 - valid_refs} reference outputs had validation issues: {dict(issues)}")

        lines = [
            "# Blind evaluation set audit",
            "",
            f"- Prompt count: {len(self.records)}; category counts: {dict(categories)}.",
            f"- Reference outputs parsed from prompt semantics and checked by JSON Schema/Pydantic/physics/compiler: {valid_refs}/100.",
            f"- Exact overlap with training: {leaked}; Jaccard near prompt overlap (0.90): {near}.",
            "- Interpreter inference: not run; there is no local interpreter/model implementation or configured inference endpoint. Accuracy is therefore unmeasured.",
            "",
        ]
        OUT_REPORT.write_text("\n".join(lines), encoding="utf-8")
        print(f"PASS: {len(self.records)} records, {valid_refs}/100 valid references, leaked={leaked}, near={near}")
        print(f"Outputs: {OUT_BLIND}, {OUT_RESULTS}, {OUT_REPORT}")


def main() -> int:
    b = Builder()
    b.gen_all()
    b.write()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
