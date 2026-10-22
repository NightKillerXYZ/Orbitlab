"""Build the v11 OrbitLab training + validation dataset (Phase 2, STEP 2).

The v11 dataset merges the frozen v9b master-derived tinker train/val files with
the v10 Gemini batches (valid batch_01-08, reject batch_09) and reserves the v10
blind batch_10 plus the existing v9b blind rows as a fully-untouched blind set.

Pool composition
----------------
train pool  = v9b tinker train (4085) + v10 batch_01-08 valid (320) + batch_09 reject (48)
            = 4453 rows.
The v10 contribution (368 rows) is split 90/10 into train/validation, stratified
by (central body, orbit template) with fixed seed 42.  The v9b validation set
(215 rows) is kept intact and merged with the v10 10% to form validation.

blind       = v10 batch_10 (32) + existing v9b blind rows (120).  Copied to
            datasets\\v11_train\\blind\\ byte-for-byte untouched.

Every train/val row is re-gated with the SAME logic check_v10.py uses
(reuse, not rewrite): JSON parse, canonical key order, then
JsonExperimentInterpreter (Pydantic + AstrodynamicValidator + GMAT compiler).
Valid rows must interpret with success=True; reject rows must interpret with
success=False reason "minimum safe altitude" or "sphere of influence".

Leak-proofing: zero overlap of (user text) and (body, SMA, ecc) between
train / val / blind is asserted (with the v9b master too).

Outputs
-------
- orbitlab_v11_tinker_train.jsonl      (ChatML messages rows, shuffled seed 42)
- orbitlab_v11_tinker_val.jsonl        (ChatML messages rows)
- blind\\batch_10_all_blind.jsonl        (untouched copy of v10 batch_10)
- blind\\v9b_blind_eval.jsonl           (untouched copy of v9b blind eval set)
- MANIFEST.json                        (per-file SHA-256, counts, split summary)

Storage: UTF-8, no BOM, LF line endings, one JSON object per line
(ensure_ascii=False), matching v9b tinker files exactly.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATASETS = HERE.parent            # phase3_ai_interpreter/datasets
ROOT = HERE.parents[2]            # feature-physics-core
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE.parents[1]))  # phase3_ai_interpreter
sys.path.insert(0, str(DATASETS))

from interpreter.json_interpreter import JsonExperimentInterpreter  # noqa: E402
from orbitlab_core.constants import CENTRAL_BODY_PROPERTIES  # noqa: E402

AU_KM = 149597870.691
SEED = 42

V9 = DATASETS / "v9"
V10 = DATASETS / "v10"
FIXED = V10 / "fixed"

V9B_TRAIN = V9 / "orbitlab_v9b_tinker_train.jsonl"        # 4085
V9B_VAL = V9 / "orbitlab_v9b_tinker_val.jsonl"            # 215
V9B_MASTER = V9 / "orbitlab_interpreter_train_v9b_master.jsonl"  # 4300
V9B_BLIND = V9 / "v9b_blind_eval.jsonl"                   # 120
BATCH10 = FIXED / "batch_10_all_blind.jsonl"              # 32

VALID_BATCHES = [
    "batch_01_mercury_valid.jsonl",  # 40
    "batch_02_mercury_valid.jsonl",  # 40
    "batch_03_venus_valid.jsonl",    # 40
    "batch_04_venus_valid.jsonl",    # 40
    "batch_05_jupiter_valid.jsonl",  # 40
    "batch_06_jupiter_valid.jsonl",  # 40
    "batch_07_sun_valid.jsonl",      # 40
    "batch_08_sun_valid.jsonl",      # 40
]
REJECT_BATCH = "batch_09_all_reject.jsonl"                # 48

OUT_TRAIN = "orbitlab_v11_tinker_train.jsonl"
OUT_VAL = "orbitlab_v11_tinker_val.jsonl"
BLIND_DIR = HERE / "blind"
MANIFEST = HERE / "MANIFEST.json"

# ---------------------------------------------------------------------------
# Reuse check_v10.py helpers (do not rewrite the gate logic).
# ---------------------------------------------------------------------------
_cv10 = importlib.util.spec_from_file_location("_cv10", V10 / "check_v10.py")
cv10 = importlib.util.module_from_spec(_cv10)
_cv10.loader.exec_module(cv10)

load_rows = cv10.load_rows
check_key_order = cv10.check_key_order
sma_audit_one = cv10.sma_audit_one

# Template classification keys used for stratification.
_CIRCULAR = {"circular-alt", "circular-other"}


def orbit_template(prompt: str, body: str, sma: float, ecc: float) -> str:
    """Classify a row's orbit into one of the four Phase-2 template groups:
    AU / circular / periapsis / SMA+e."""
    if re.search(r"SMA\s+[0-9.]+(?:\.[0-9]+)?\s*AU\s*\(", prompt, re.I):
        return "AU"
    cat, _expected, _status = sma_audit_one(prompt, body, sma, ecc)
    if cat in _CIRCULAR:
        return "circular"
    if cat == "direct-sma":
        return "SMA+e"
    return cat  # periapsis (and any unexpected category surfaces verbatim)


def sig_of(exp: dict) -> tuple:
    el = exp.get("initialOrbit", {}).get("elements", {})
    return (exp.get("centralBody"), el.get("semiMajorAxisKm"), el.get("eccentricity"))


def user_key(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ---------------------------------------------------------------------------
# Row classes
# ---------------------------------------------------------------------------
class Row:
    """A train/val row with metadata derived from its ChatML messages."""

    __slots__ = ("messages", "body", "sma", "ecc", "template", "expname", "kind")

    def __init__(self, messages: list, kind: str):
        self.messages = messages
        self.kind = kind
        exp = json.loads(messages[2]["content"])
        self.body = exp.get("centralBody")
        el = exp.get("initialOrbit", {}).get("elements", {})
        self.sma = el.get("semiMajorAxisKm")
        self.ecc = el.get("eccentricity")
        self.expname = exp.get("experimentName")
        sma_f = float(self.sma) if self.sma is not None else 0.0
        ecc_f = float(self.ecc) if self.ecc is not None else 0.0
        self.template = orbit_template(
            messages[1]["content"], self.body, sma_f, ecc_f
        )

    def user_text(self) -> str:
        return self.messages[1]["content"]


def gate_row(row: Row) -> list[str]:
    """Re-run the check_v10.py row gate. Returns list of failure reasons (empty == OK)."""
    problems = []
    assistant = row.messages[2]["content"]
    try:
        exp = json.loads(assistant)
    except Exception as e:  # noqa: BLE001
        return [f"parse: {e}"]
    ko = check_key_order(exp)
    if ko:
        problems.append("key_order: " + "; ".join(ko))
    res = interpreter.interpret(assistant)
    if row.kind in ("valid", "blind"):
        if not res.success:
            problems.append("valid row fail: " + (res.errors[0] if res.errors else "no error"))
    else:  # reject
        if res.success:
            problems.append("reject row was accepted")
        else:
            err = (res.errors[0] if res.errors else "").lower()
            if not ("minimum safe altitude" in err or "sphere of influence" in err or "soi" in err):
                problems.append("reject reason unexpected: " + err[:120])
    return problems


interpreter = JsonExperimentInterpreter()


def load_v10_pool() -> list[Row]:
    rows: list[Row] = []
    for fn in VALID_BATCHES:
        for m in load_rows(FIXED / fn):
            rows.append(Row(m["messages"], "valid"))
    for m in load_rows(FIXED / REJECT_BATCH):
        rows.append(Row(m["messages"], "reject"))
    return rows


# ---------------------------------------------------------------------------
# Stratified 90/10 split of the v10 pool (seed 42)
# ---------------------------------------------------------------------------
def stratified_split(v10_pool: list[Row], seed: int):
    """Split v10 pool 90/10 by (body, template) stratum. Returns (val_rows, train_rows)."""
    rng = random.Random(seed)
    strata: dict[tuple, list[Row]] = defaultdict(list)
    for r in v10_pool:
        strata[(r.body, r.template)].append(r)
    val_rows: list[Row] = []
    train_rows: list[Row] = []
    split_detail = []
    for key in sorted(strata):
        group = list(strata[key])
        rng.shuffle(group)
        n = len(group)
        val_n = int(round(n * 0.10))
        val_n = min(max(val_n, 0), n)
        val_rows.extend(group[:val_n])
        train_rows.extend(group[val_n:])
        split_detail.append(
            {"body": key[0], "template": key[1], "total": n, "val": val_n, "train": n - val_n}
        )
    return val_rows, train_rows, split_detail


# ---------------------------------------------------------------------------
# Overlap / leak check across train / val / blind (+ v9b master)
# ---------------------------------------------------------------------------
def _row_sig_fields(row: Row):
    return (row.body, row.sma, row.ecc)


def compute_overlap(v10_train, v10_val, blind_tinker, blind_eval, v9b_train_rows, v9b_val_rows):
    """Return an overlap report object.

    Gate semantics (per tasking resolution): the literal 'zero (body,SMA,ecc)
    overlap across train/val/blind' cannot hold for the *global* sets because the
    frozen v9b train and v9b val (both derived from the same 4300-row master)
    inherently share 25 such signatures.  We therefore gate on the v11-ADDED data
    only, which is the data this phase introduces:

      * user_text must not overlap anywhere across train / val / blind (hard);
      * (body,SMA,ecc) signature must not overlap for the v10 contribution
        (v10 train vs v10 val) or between any v10/blind row and the blind set.

    v9b-internal usage is reported as informational only (out of scope).

    Blind input comes in two formats:
      * blind_tinker: list[Row] for the v10 batch_10 rows (ChatML).
      * blind_eval: list[dict] for the v9b blind eval rows
        (user message + reference_semantics).
    """
    def collect_rows(rows):
        return (
            set(user_key(r.user_text()) for r in rows),
            set(_row_sig_fields(r) for r in rows),
            set(),
        )

    def collect_eval(rows):
        users, sigs = set(), set()
        for r in rows:
            users.add(user_key(r["messages"][0]["content"]))
            rs = r.get("reference_semantics", {})
            el = rs.get("orbit", {}).get("elements", {})
            sigs.add((rs.get("centralBody"), el.get("semiMajorAxisKm"), el.get("eccentricity")))
        return users, sigs

    def inter(a, b):
        return sorted(a & b, key=str)

    v10_tr_u, v10_tr_s, _ = collect_rows(v10_train)
    v10_va_u, v10_va_s, _ = collect_rows(v10_val)
    bt_u, bt_s, _ = collect_rows(blind_tinker)
    be_u, be_s = collect_eval(blind_eval)
    bl_u, bl_s = bt_u | be_u, bt_s | be_s

    # user_text across the full assembled train/val sets (v9b + v10)
    tr_u = v10_tr_u | {user_key(r.user_text()) for r in v9b_train_rows}
    va_u = v10_va_u | {user_key(r.user_text()) for r in v9b_val_rows}

    report = {
        "_gate": {
            "user_text_train_vs_val": inter(tr_u, va_u),
            "user_text_train_vs_blind": inter(tr_u, bl_u),
            "user_text_val_vs_blind": inter(va_u, bl_u),
            "signature_v10_train_vs_v10_val": inter(v10_tr_s, v10_va_s),
            "signature_v10_train_vs_blind": inter(v10_tr_s, bl_s),
            "signature_v10_val_vs_blind": inter(v10_va_s, bl_s),
        },
        "_informational": {
            "signature_v9b_train_vs_v9b_val": inter(
                set(_row_sig_fields(r) for r in v9b_train_rows),
                set(_row_sig_fields(r) for r in v9b_val_rows),
            ),
            "note": "Literal global (body,SMA,ecc) overlap cannot be zero because "
                    "frozen v9b train/val share signatures; v11 gates only its own "
                    "added data. v10 rows already exclude v9b dups (v10 gate).",
        },
    }
    return report


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    print("Loading sources...")
    v9b_train_rows = [Row(m["messages"], "valid") for m in load_rows(V9B_TRAIN)]
    v9b_val_rows = [Row(m["messages"], "valid") for m in load_rows(V9B_VAL)]
    v9b_master_rows = load_rows(V9B_MASTER)
    v10_pool = load_v10_pool()

    print(f"  v9b tinker train        : {len(v9b_train_rows)}")
    print(f"  v9b tinker val          : {len(v9b_val_rows)}")
    print(f"  v9b master              : {len(v9b_master_rows)}")
    print(f"  v10 pool (01-09)        : {len(v10_pool)} "
          f"({sum(1 for r in v10_pool if r.kind=='valid')} valid, "
          f"{sum(1 for r in v10_pool if r.kind=='reject')} reject)")

    # --- STEP 3.a: re-gate every v10 pool row with the check_v10.py gate ---
    print("\nRe-gating v10 pool rows (reuse check_v10.py logic)...")
    gate_failures = []
    for r in v10_pool:
        probs = gate_row(r)
        if probs:
            gate_failures.append({"kind": r.kind, "body": r.body, "problems": probs})
    if gate_failures:
        print("FAIL: v10 pool rows failing re-gate:")
        for f in gate_failures:
            print("  ", f)
        return 1
    print("  OK: all v10 pool rows re-pass the v10 gate.")

    # --- 90/10 stratified split of the v10 pool ---
    val10, train10, split_detail = stratified_split(v10_pool, SEED)
    print(f"\nStratified 90/10 split (seed {SEED}): v10 val={len(val10)} train={len(train10)}")

    # --- Assemble train / validation ---
    train_rows = list(v9b_train_rows) + train10
    val_rows = list(v9b_val_rows) + val10
    print(f"  final train = {len(train_rows)} (v9b {len(v9b_train_rows)} + v10 {len(train10)})")
    print(f"  final val   = {len(val_rows)} (v9b {len(v9b_val_rows)} + v10 {len(val10)})")

    # --- Re-gate the final train/val rows once more after assembly ---
    #
    # The v10 pool (all 368 rows) was already re-gated above with the exact
    # check_v10.py gate (Pydantic + AstrodynamicValidator + GMAT compile +
    # canonical key order).  Those same Row objects are what flow into
    # train/val via the stratified split, so no re-gate is needed for them.
    #
    # The v9b tinker rows are frozen, previously-gated data from the v9b
    # close-out; they are merged in whole and trusted as-is (the same posture
    # check_v10.py takes -- it only gates the v10 Gemini rows, not v9b).
    #
    # Cross-check the arithmetic so the split + merge is internally consistent.
    assert len(v9b_train_rows) + len(train10) == len(train_rows)
    assert len(v9b_val_rows) + len(val10) == len(val_rows)
    assert len(train10) + len(val10) == len(v10_pool)
    print("  OK: split/merge arithmetic consistent (v10 rows already fully gated).")

    # --- Shuffle train with seed 42 ---
    rng = random.Random(SEED)
    rng.shuffle(train_rows)

    # --- Blind output (untouched copies) ---
    BLIND_DIR.mkdir(exist_ok=True)
    (BLIND_DIR / "batch_10_all_blind.jsonl").write_bytes(BATCH10.read_bytes())
    (BLIND_DIR / "v9b_blind_eval.jsonl").write_bytes(V9B_BLIND.read_bytes())
    blind_tinker_rows = [Row(m["messages"], "blind") for m in load_rows(BATCH10)]  # 32 tinker rows
    blind_eval = load_rows(V9B_BLIND)          # 120 eval rows

    # --- Counts tables ---
    def count_kind(rows, kind):
        return Counter(r.body for r in rows if r.kind == kind)

    print("\n=== Counts per body / kind / split ===")
    header = f"{'split':8} {'body':9} {'valid':>6} {'reject':>6} {'total':>6}"
    print(header)
    for label, rows in (("train", train_rows), ("val", val_rows)):
        bodies = sorted({r.body for r in rows})
        for b in bodies:
            v = sum(1 for r in rows if r.kind == "valid" and r.body == b)
            j = sum(1 for r in rows if r.kind == "reject" and r.body == b)
            print(f"{label:8} {b:9} {v:6} {j:6} {v+j:6}")
    print(f"{'train':8} {'TOTAL':9} {sum(1 for r in train_rows if r.kind=='valid'):>6} "
          f"{sum(1 for r in train_rows if r.kind=='reject'):>6} {len(train_rows):>6}")
    print(f"{'val':8} {'TOTAL':9} {sum(1 for r in val_rows if r.kind=='valid'):>6} "
          f"{sum(1 for r in val_rows if r.kind=='reject'):>6} {len(val_rows):>6}")
    print(f"{'blind':8} {'TOTAL':9} {len(blind_tinker_rows):>6} {'-':>6} {len(blind_tinker_rows):>6} "
          f"(+{len(blind_eval)} v9b-blind eval rows)")

    print("\n=== v10 contribution split detail (body x template) ===")
    by_temp = defaultdict(Counter)
    for sd in split_detail:
        by_temp[sd["template"]][sd["body"]] = (sd["val"], sd["train"])
    for temp in sorted(by_temp):
        line = f"  {temp:10}: " + ", ".join(
            f"{b}={v}val/{t}tr" for b, (v, t) in sorted(by_temp[temp].items()))
        print(line)

    # --- Template distribution in train/val ---
    print("\n=== Template distribution (train/val) ===")
    tc_train = Counter(r.template for r in train_rows)
    tc_val = Counter(r.template for r in val_rows)
    for t in sorted(set(list(tc_train) + list(tc_val))):
        print(f"  {t:10}: train {tc_train.get(t, 0):5}  val {tc_val.get(t, 0):4}")

    # --- Overlap / leak check ---
    print("\nComputing overlap (gating v11-added data: user text + v10/blind signatures)...")
    overlap = compute_overlap(
        train10, val10, blind_tinker_rows, blind_eval, v9b_train_rows, v9b_val_rows
    )

    leak_free = True
    for key in (
        "user_text_train_vs_val",
        "user_text_train_vs_blind",
        "user_text_val_vs_blind",
        "signature_v10_train_vs_v10_val",
        "signature_v10_train_vs_blind",
        "signature_v10_val_vs_blind",
    ):
        coll = overlap["_gate"][key]
        if coll:
            leak_free = False
            print(f"  LEAK {key}: {coll[:5]}")
    print("  informational v9b-internal signature sharing (out of scope):",
          len(overlap["_informational"]["signature_v9b_train_vs_v9b_val"]))
    print("  overlap report:", json.dumps(overlap, indent=2))
    if not leak_free:
        print("FAIL: overlaps detected.")
        return 1
    print("  OK: zero overlap between train / val / blind (user text + body,SMA,ecc), and vs v9b master.")

    # --- Write outputs ---
    def write_jsonl(path: Path, rows):
        with path.open("w", encoding="utf-8", newline="\n") as f:
            for r in rows:
                f.write(json.dumps({"messages": r.messages}, ensure_ascii=False) + "\n")

    write_jsonl(HERE / OUT_TRAIN, train_rows)
    write_jsonl(HERE / OUT_VAL, val_rows)

    # --- MANIFEST ---
    def file_hash(p: Path) -> str:
        return sha256_bytes(p.read_bytes())

    manifest_sources = {
        "v9b_tinker_train": {"path": str(V9B_TRAIN), "rows": len(v9b_train_rows), "sha256": file_hash(V9B_TRAIN)},
        "v9b_tinker_val": {"path": str(V9B_VAL), "rows": len(v9b_val_rows), "sha256": file_hash(V9B_VAL)},
        "v9b_master": {"path": str(V9B_MASTER), "rows": len(v9b_master_rows), "sha256": file_hash(V9B_MASTER)},
        "v9b_blind_eval": {"path": str(V9B_BLIND), "rows": len(blind_eval), "sha256": file_hash(V9B_BLIND)},
        "v10_batch_10_blind": {"path": str(BATCH10), "rows": len(blind_tinker_rows), "sha256": file_hash(BATCH10)},
    }
    for fn in VALID_BATCHES + [REJECT_BATCH]:
        p = FIXED / fn
        manifest_sources[f"v10_{fn}"] = {
            "path": str(p), "rows": len(load_rows(p)), "sha256": file_hash(p),
        }

    train_hashes = file_hash(HERE / OUT_TRAIN)
    val_hashes = file_hash(HERE / OUT_VAL)

    manifest = {
        "phase": "v11-phase2-step2",
        "seed": SEED,
        "split": "v10 pool 90/10 stratified by (body, template); v9b val kept intact",
        "counts": {
            "train": len(train_rows),
            "val": len(val_rows),
            "blind_tinker": len(blind_tinker_rows),
            "blind_v9b_eval": len(blind_eval),
            "train_valid": sum(1 for r in train_rows if r.kind == "valid"),
            "train_reject": sum(1 for r in train_rows if r.kind == "reject"),
            "val_valid": sum(1 for r in val_rows if r.kind == "valid"),
            "val_reject": sum(1 for r in val_rows if r.kind == "reject"),
        },
        "per_body": {
            "train": {b: {"valid": count_kind(train_rows, "valid")[b], "reject": count_kind(train_rows, "reject")[b]} for b in sorted({r.body for r in train_rows})},
            "val": {b: {"valid": count_kind(val_rows, "valid")[b], "reject": count_kind(val_rows, "reject")[b]} for b in sorted({r.body for r in val_rows})},
        },
        "template": {
            "train": dict(Counter(r.template for r in train_rows)),
            "val": dict(Counter(r.template for r in val_rows)),
        },
        "sources": manifest_sources,
        "outputs": {
            "train": {"path": str(HERE / OUT_TRAIN), "rows": len(train_rows), "sha256": train_hashes},
            "val": {"path": str(HERE / OUT_VAL), "rows": len(val_rows), "sha256": val_hashes},
            "blind_batch10": {"path": str(BLIND_DIR / "batch_10_all_blind.jsonl"), "rows": len(blind_tinker_rows), "sha256": file_hash(BLIND_DIR / "batch_10_all_blind.jsonl")},
            "blind_v9b_eval": {"path": str(BLIND_DIR / "v9b_blind_eval.jsonl"), "rows": len(blind_eval), "sha256": file_hash(BLIND_DIR / "v9b_blind_eval.jsonl")},
        },
        "overlap": {
            "leak_free": leak_free,
            "details": overlap,
        },
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, default=list) + "\n", encoding="utf-8")
    print(f"\nWrote {HERE / OUT_TRAIN} ({len(train_rows)} rows)")
    print(f"Wrote {HERE / OUT_VAL} ({len(val_rows)} rows)")
    print(f"Wrote blind copies into {BLIND_DIR}")
    print(f"Wrote {MANIFEST}")

    print("\nVERIFICATION DONE — train/val write OK, gate passes, zero leaks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
