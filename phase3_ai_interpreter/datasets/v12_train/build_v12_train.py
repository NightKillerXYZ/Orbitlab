"""Build the v12 OrbitLab training + validation dataset (Phase 3, AI interpreter step).

The v12 dataset merges the v11 train/val rows (unchanged) with the newly generated
v12 gen rows. The 473 v12 gen rows are split 90/10 stratified by (body, form, class)
with fixed seed 42; the 90% goes to train (appended to v11 train, then shuffled seed
42) and the 10% to val (appended to v11 val, keeping v11 order).

Metadata (body / form / class) is taken from the authoritative spec dir
datasets/v12_gen/v12/*.jsonl, keyed by experimentName == spec id (verified 1:1).

Outputs
-------
- orbitlab_v12_tinker_train.jsonl      (ChatML messages rows, shuffled seed 42)
- orbitlab_v12_tinker_val.jsonl        (ChatML messages rows)
- orbitlab_v12_train_google.jsonl      (Google rows, 1:1 with ChatML train)
- orbitlab_v12_val_google.jsonl        (Google rows, 1:1 with ChatML val)
- MANIFEST_v12.json                    (sources, sha256, counts, split sizes,
                                        before/after front-step wording counts)

Leak-proofing: zero overlap of (user text) and (body, SMA, ecc) with v11
train / val / blind and the 30 realistic cases is asserted for every added X row.

Storage: UTF-8, no BOM, LF line endings, one JSON object per line
(ensure_ascii=False), matching v9b / v11 files exactly.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATASETS = HERE.parent            # phase3_ai_interpreter/datasets
PHASE = HERE.parents[1]           # phase3_ai_interpreter
ROOT = HERE.parents[2]            # feature-physics-core
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(PHASE))
sys.path.insert(0, str(DATASETS))

from interpreter.json_interpreter import JsonExperimentInterpreter  # noqa: E402

AU_KM = 149597870.691
SEED = 42

V11 = DATASETS / "v11_train"
V12GEN = DATASETS / "v12_gen"
V9 = DATASETS / "v9"

V11_TRAIN = V11 / "orbitlab_v11_tinker_train.jsonl"     # 4413
V11_VAL = V11 / "orbitlab_v11_tinker_val.jsonl"         # 255
V11_TRAIN_GOOGLE = V11 / "orbitlab_v11_train_google.jsonl"
BLIND_BATCH10 = V11 / "blind" / "batch_10_all_blind.jsonl"   # 32
V9B_BLIND = V9 / "v9b_blind_eval.jsonl"                 # 120
REALISTIC = DATASETS / "cases_realistic.jsonl"          # 30

GEN = V12GEN / "orbitlab_v12_gen.jsonl"                 # 473
SPEC_DIR = V12GEN / "v12"                               # 480 spec rows

OUT_CHATML_TRAIN = HERE / "orbitlab_v12_tinker_train.jsonl"
OUT_CHATML_VAL = HERE / "orbitlab_v12_tinker_val.jsonl"
OUT_GOOGLE_TRAIN = HERE / "orbitlab_v12_train_google.jsonl"
OUT_GOOGLE_VAL = HERE / "orbitlab_v12_val_google.jsonl"
MANIFEST = HERE / "MANIFEST_v12.json"


# ---------------------------------------------------------------------------
# Reuse v11 row / gate helpers (do not rewrite the gate logic).
# ---------------------------------------------------------------------------
_bv11 = importlib.util.spec_from_file_location("_bv11", V11 / "build_v11.py")
bv11 = importlib.util.module_from_spec(_bv11)
_bv11.loader.exec_module(bv11)

Row = bv11.Row
gate_row = bv11.gate_row
user_key = bv11.user_key
sha256_bytes = bv11.sha256_bytes
interpreter = JsonExperimentInterpreter()

# Reuse v12_gen compute_sma / bodies for sma reconstruction when needed.
_bv12 = importlib.util.spec_from_file_location(
    "_bv12", V12GEN / "build_v12_gen.py")
bv12 = importlib.util.module_from_spec(_bv12)
_bv12.loader.exec_module(bv12)
compute_sma = bv12.compute_sma


# ---------------------------------------------------------------------------
# Load helpers
# ---------------------------------------------------------------------------
def load_chatml(path: Path) -> list[dict]:
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            out.append(json.loads(line))
    return out


def load_spec_metadata() -> dict[str, dict]:
    """id -> spec dict, from the authoritative spec dir (480 rows)."""
    meta: dict[str, dict] = {}
    for f in sorted(SPEC_DIR.glob("*.jsonl")):
        for l in open(f, encoding="utf-8"):
            if not l.strip():
                continue
            d = json.loads(l)
            meta[d["id"]] = d
    return meta


def triple_of_experiment(exp: dict) -> tuple:
    el = exp["initialOrbit"]["elements"]
    return (exp["centralBody"], el["semiMajorAxisKm"], el["eccentricity"])


def triple_str(t: tuple) -> str:
    b, a, e = t
    return f"{b}|{a}|{e}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    spec_meta = load_spec_metadata()
    print(f"spec rows: {len(spec_meta)}")

    # ---- Load v11 bases ----
    v11_train = load_chatml(V11_TRAIN)
    v11_val = load_chatml(V11_VAL)
    print(f"v11 train: {len(v11_train)}  val: {len(v11_val)}")

    # ---- Load realistic cases (30) ----
    realistic = load_chatml(REALISTIC)
    assert len(realistic) == 30, len(realistic)

    # ---- Load gen rows + spec metadata, verify 1:1 ----
    gen = load_chatml(GEN)
    print(f"gen rows: {len(gen)}")
    gen_by_exp = {json.loads(d["messages"][2]["content"])["experimentName"]: d
                  for d in gen}
    gen_meta = []
    for d in gen:
        exp = json.loads(d["messages"][2]["content"])
        run = exp["experimentName"]
        assert run in spec_meta, f"no spec for {run}"
        body = spec_meta[run]["body"]
        assert exp["centralBody"] == body, f"body mismatch {run}"
        gen_meta.append({
            "exp": exp,
            "body": body,
            "form": spec_meta[run]["form"],
            "class": spec_meta[run]["class"],
            "id": run,
        })
    assert len(gen_meta) == 473, len(gen_meta)

    # ---- Re-gate all gen rows ----
    # Valid rows must interpret success=True. Reject rows must interpret
    # success=False (any rejection reason: minalt / soi / bad_incl pydantic).
    problems = 0
    for gm in gen_meta:
        d = gen_by_exp[gm["id"]]
        aid = d["messages"][2]["content"]
        res = interpreter.interpret(aid)
        if gm["class"] == "valid":
            if not res.success:
                problems += 1
                print("  GATE FAIL", gm["id"], "valid fail; err:",
                      (res.errors[0] if res.errors else "none")[:80])
        else:
            if res.success:
                problems += 1
                print("  GATE FAIL", gm["id"], gm["class"], "was ACCEPTED")
    print(f"re-gate problems: {problems}")
    assert problems == 0, "gen rows must re-gate clean"

    # ---- OVERLAP: (body,SMA,ecc) gen vs realistic ---- (Part A step 6)
    gen_triples = {triple_str(triple_of_experiment(gm["exp"])) for gm in gen_meta}
    real_triples = {}
    for d in realistic:
        ej = d["expect_json"]
        real_triples[triple_str(triple_of_experiment(ej))] = d["id"]
    gen_real_overlap = gen_triples & set(real_triples)
    print(f"Part A triple overlap gen vs realistic: {len(gen_real_overlap)}")
    for t in sorted(gen_real_overlap):
        print("   overlap triple", t, "case", real_triples[t])

    # ---- Collect v11 train/val/blind (user keys + triples) for leak check ----
    from orbitlab_core.constants import CENTRAL_BODY_PROPERTIES as _CBP

    def cart_to_elements(body, el):
        """Convert Cartesian state to (sma, ecc) using GM of body."""
        mu = _CBP[body][1]
        r = (el["xKm"], el["yKm"], el["zKm"])
        v = (el["vxKmS"], el["vyKmS"], el["vzKmS"])
        import math
        rmag = math.sqrt(sum(c * c for c in r))
        vmag = math.sqrt(sum(c * c for c in v))
        rdotv = sum(r[i] * v[i] for i in (0, 1, 2))
        eps = vmag * vmag / 2.0 - mu / rmag
        sma = -mu / (2.0 * eps)
        factor = vmag * vmag - mu / rmag
        ex = (factor * r[0] - rdotv * v[0]) / mu
        ey = (factor * r[1] - rdotv * v[1]) / mu
        ez = (factor * r[2] - rdotv * v[2]) / mu
        ecc = math.sqrt(ex * ex + ey * ey + ez * ez)
        return round(sma, 3), round(ecc, 6)

    def extract_triple_messages(msgs):
        exp = json.loads(msgs[2]["content"])
        io = exp["initialOrbit"]
        if io["type"] == "Cartesian":
            sma, ecc = cart_to_elements(exp["centralBody"], io["elements"])
            return (exp["centralBody"], sma, ecc)
        el = io["elements"]
        return (exp["centralBody"], el["semiMajorAxisKm"], el["eccentricity"])

    v11_user_keys = set()
    v11_triples = set()
    for d in v11_train:
        msgs = d["messages"]
        v11_user_keys.add(user_key(msgs[1]["content"]))
        v11_triples.add(triple_str(extract_triple_messages(msgs)))
    for d in v11_val:
        msgs = d["messages"]
        v11_user_keys.add(user_key(msgs[1]["content"]))
        v11_triples.add(triple_str(extract_triple_messages(msgs)))
    for d in load_chatml(BLIND_BATCH10):
        msgs = d["messages"]
        v11_user_keys.add(user_key(msgs[1]["content"]))
        v11_triples.add(triple_str(extract_triple_messages(msgs)))
    # v9b blind are eval-format rows (messages = [user prompt only])
    for d in load_chatml(V9B_BLIND):
        v11_user_keys.add(user_key(d["messages"][0]["content"]))
        el = d["reference_semantics"]["orbit"]["elements"]
        v11_triples.add(triple_str(
            (d["reference_semantics"]["centralBody"],
             el["semiMajorAxisKm"], el["eccentricity"])))
    print(f"v11 user keys: {len(v11_user_keys)}  triples: {len(v11_triples)}")

    real_user_keys = {user_key(d["user_text"]) for d in realistic}
    real_triples_set = set(real_triples.keys())

    # user-text / triple overlap of gen rows vs v11 + realistic
    gen_u_overlap = set()
    gen_t_overlap = set()
    for gm in gen_meta:
        d = gen_by_exp[gm["id"]]
        uk = user_key(d["messages"][1]["content"])
        tt = triple_str(triple_of_experiment(gm["exp"]))
        if uk in v11_user_keys or uk in real_user_keys:
            gen_u_overlap.add(gm["id"])
        if tt in v11_triples or tt in real_triples_set:
            gen_t_overlap.add(gm["id"])
    print(f"gen user-text overlaps: {len(gen_u_overlap)} triples: {len(gen_t_overlap)}")
    assert not gen_u_overlap, gen_u_overlap
    assert not gen_t_overlap, gen_t_overlap

    # ---- Stratified 90/10 split of gen rows by (body, form, class) seed 42 ----
    rng = random.Random(SEED)
    strata: dict[tuple, list[int]] = defaultdict(list)
    for i, gm in enumerate(gen_meta):
        strata[(gm["body"], gm["form"], gm["class"])].append(i)
    val_idx: set[int] = set()
    split_detail = []
    for key in sorted(strata):
        grp = list(strata[key])
        rng.shuffle(grp)
        n = len(grp)
        val_n = int(round(n * 0.10))
        val_n = min(max(val_n, 0), n)
        val_idx.update(grp[:val_n])
        split_detail.append((key, n, val_n, len(grp) - val_n))
    gen_train = [gen_meta[i] for i in range(len(gen_meta)) if i not in val_idx]
    gen_val = [gen_meta[i] for i in range(len(gen_meta)) if i in val_idx]
    print(f"gen split: train {len(gen_train)} val {len(gen_val)}")
    for key, n, vn, tn in sorted(split_detail):
        print(f"   {key}: n={n} val={vn} train={tn}")

    # ---- Merge ----
    # Build full train list (ChatML dicts) from v11 train + gen train rows
    train_rows = []
    for d in v11_train:
        train_rows.append(d["messages"])
    for gm in gen_train:
        train_rows.append(gen_by_exp[gm["id"]]["messages"])
    # Shuffle whole train with seed 42 (per tasking: shuffle train seed 42)
    rng.shuffle(train_rows)

    val_rows = []
    for d in v11_val:
        val_rows.append(d["messages"])
    for gm in gen_val:
        val_rows.append(gen_by_exp[gm["id"]]["messages"])
    # val keeps v11 order + gen appended (no shuffle)

    assert len(train_rows) == len(v11_train) + len(gen_train)
    assert len(val_rows) == len(v11_val) + len(gen_val)
    print(f"final train: {len(train_rows)}  val: {len(val_rows)}")

    # ---- Leak check on final sets ----
    # The 473 gen rows (all now present in train+val) must be disjoint from the
    # v11 train/val/blind user texts and the 30 realistic user texts.
    gen_user_keys = set()
    for gm in gen_meta:
        gen_user_keys.add(user_key(gen_by_exp[gm["id"]]["messages"][1]["content"]))
    assert len(gen_user_keys) == len(gen_meta), "gen user keys must be unique"
    assert not (gen_user_keys & v11_user_keys), "gen user overlap with v11"
    assert not (gen_user_keys & real_user_keys), "gen user overlap with realistic"
    train_g_keys = {user_key(m[1]["content"]) for m in train_rows} & gen_user_keys
    val_g_keys = {user_key(m[1]["content"]) for m in val_rows} & gen_user_keys
    assert len(train_g_keys) == len(gen_train), "train missing gen rows"
    assert len(val_g_keys) == len(gen_val), "val missing gen rows"

    # ---- Write ChatML files (LF, no BOM, ensure_ascii=False) ----
    def write_chatml(path, rows):
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            for m in rows:
                f.write(json.dumps({"messages": m}, ensure_ascii=False) + "\n")
    write_chatml(OUT_CHATML_TRAIN, train_rows)
    write_chatml(OUT_CHATML_VAL, val_rows)

    # ---- Write Google files 1:1 mapped ----
    def to_google(chatml_messages):
        sys_msgs = [m for m in chatml_messages if m["role"] == "system"]
        assert len(sys_msgs) == 1
        system = sys_msgs[0]["content"]
        contents = []
        for m in chatml_messages:
            if m["role"] == "system":
                continue
            role = "user" if m["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": m["content"]}]})
        return {
            "systemInstruction": {"role": "system", "parts": [{"text": system}]},
            "contents": contents,
        }

    def write_google(path, chatml_rows):
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            for m in chatml_rows:
                f.write(json.dumps(to_google(m), ensure_ascii=False) + "\n")
    write_google(OUT_GOOGLE_TRAIN, train_rows)
    write_google(OUT_GOOGLE_VAL, val_rows)

    # ---- Verify counts + Google 1:1 ----
    assert len(load_chatml(OUT_CHATML_TRAIN)) == len(train_rows) == len(load_chatml(OUT_GOOGLE_TRAIN))
    assert len(load_chatml(OUT_CHATML_VAL)) == len(val_rows) == len(load_chatml(OUT_GOOGLE_VAL))

    def verify_google(chat_path, google_path):
        cc = [json.loads(l) for l in open(chat_path, encoding="utf-8") if l.strip()]
        gg = [json.loads(l) for l in open(google_path, encoding="utf-8") if l.strip()]
        assert len(cc) == len(gg)
        for i, (c, g) in enumerate(zip(cc, gg)):
            cm = c["messages"]
            s = [m for m in cm if m["role"] == "system"][0]["content"]
            assert g["systemInstruction"]["parts"][0]["text"] == s, f"sys {i}"
            others = [m for m in cm if m["role"] != "system"]
            assert len(g["contents"]) == len(others), f"contents {i}"
            for gi, (gm_, cm_) in enumerate(zip(g["contents"], others)):
                erole = "user" if cm_["role"] == "user" else "model"
                assert gm_["role"] == erole, f"role {i}.{gi}"
                assert gm_["parts"][0]["text"] == cm_["content"], f"text {i}.{gi}"
    verify_google(OUT_CHATML_TRAIN, OUT_GOOGLE_TRAIN)
    verify_google(OUT_CHATML_VAL, OUT_GOOGLE_VAL)
    print("Google 1:1 verified (byte-for-byte contents).")

    # ---- Front-step wording counts (v11 vs v12) ----
    FRONT = r"I'd like an experiment call the run "
    def count_front(rows):
        n = 0
        for m in rows:
            if re.search(FRONT, m[1]["content"]):
                n += 1
        return n
    v11_front = count_front([d["messages"] for d in v11_train] +
                             [d["messages"] for d in v11_val])
    v12_front_train = count_front(train_rows)
    v12_front_val = count_front(val_rows)
    print(f"front-step wording: v11={v11_front}  v12train={v12_front_train} v12val={v12_front_val}")

    # ---- MANIFEST ----
    def file_hash(p):
        return sha256_bytes(p.read_bytes())

    per_body_orig = Counter()
    for gm in gen_meta:
        per_body_orig[gm["body"]] += 1
    train_body = Counter()
    val_body = Counter()
    for d in v11_train:
        train_body[json.loads(d["messages"][2]["content"])["centralBody"]] += 1
    for gm in gen_train:
        train_body[gm["body"]] += 1
    for d in v11_val:
        val_body[json.loads(d["messages"][2]["content"])["centralBody"]] += 1
    for gm in gen_val:
        val_body[gm["body"]] += 1

    manifest = {
        "phase": "v12-train",
        "seed": 42,
        "split": "v11 train/val unchanged + v12_gen 473 split 90/10 stratified by (body,form,class)",
        "counts": {
            "v11_train": len(v11_train),
            "v11_val": len(v11_val),
            "v12_gen_total": len(gen),
            "v12_gen_train": len(gen_train),
            "v12_gen_val": len(gen_val),
            "train": len(train_rows),
            "val": len(val_rows),
        },
        "gen_class_counts": dict(Counter(gm["class"] for gm in gen_meta)),
        "per_body_gen": dict(sorted(per_body_orig.items())),
        "per_body": {
            "train": dict(sorted((k, int(v)) for k, v in train_body.items())),
            "val": dict(sorted((k, int(v)) for k, v in val_body.items())),
        },
        "front_step_wording": {
            "regex": FRONT,
            "v11_total": v11_front,
            "v12_train": v12_front_train,
            "v12_val": v12_front_val,
        },
        "leak_check": {
            "gen_vs_realistic_triple_overlap": len(gen_real_overlap),
            "gen_user_text_overlap_vs_v11_or_realistic": 0,
            "gen_triple_overlap_vs_v11_or_realistic": 0,
        },
        "sources": {
            "v11_train": str(V11_TRAIN),
            "v11_val": str(V11_VAL),
            "v12_gen": str(GEN),
            "v12_spec_dir": str(SPEC_DIR),
            "realistic_cases": str(REALISTIC),
        },
        "files": {
            "orbitlab_v12_tinker_train.jsonl": {
                "count": len(train_rows), "sha256": file_hash(OUT_CHATML_TRAIN)},
            "orbitlab_v12_tinker_val.jsonl": {
                "count": len(val_rows), "sha256": file_hash(OUT_CHATML_VAL)},
            "orbitlab_v12_train_google.jsonl": {
                "count": len(load_chatml(OUT_GOOGLE_TRAIN)), "sha256": file_hash(OUT_GOOGLE_TRAIN)},
            "orbitlab_v12_val_google.jsonl": {
                "count": len(load_chatml(OUT_GOOGLE_VAL)), "sha256": file_hash(OUT_GOOGLE_VAL)},
        },
    }
    with open(MANIFEST, "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print("MANIFEST written:", MANIFEST)

    # ---- BOM / line-ending verification ----
    for p in [OUT_CHATML_TRAIN, OUT_CHATML_VAL, OUT_GOOGLE_TRAIN, OUT_GOOGLE_VAL]:
        b = p.read_bytes()
        assert not b.startswith(b"\xef\xbb\xbf"), f"BOM in {p}"
        assert b"\r\n" not in b, f"CRLF in {p}"
    print("No BOM / no CRLF verified on all 4 outputs.")
    print("DONE")


if __name__ == "__main__":
    main()
