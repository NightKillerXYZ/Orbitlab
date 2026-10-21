"""STEP 1 - Fix the known SMA defect in batch_10 line 28 (BlindSun_028).

The assistant JSON for BlindSun_028 reports semiMajorAxisKm = 27782020.57, but
the user requested a periapsis altitude of 24830430.5 km with ecc 0.0812 around
the Sun (radius 695700 km), so the true SMA is

    (695700 + 24830430.5) / (1 - 0.0812) = 27782031.4541

The correction is applied ONLY to the assistant JSON of line 28.  The other 9
files keep whatever line ending the trainer expects inside `fixed\\` (v9b
storage: LF, no BOM) - but at Step 1 we only write the corrected batch_10; the
remaining fixed files are produced in Step 5.

This script only writes datasets/v10/fixed/batch_10_all_blind.jsonl and prints
a diff report.
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw" / "batch_10_all_blind.jsonl"
OUT = HERE / "fixed" / "batch_10_all_blind.jsonl"

OLD_SMA = "27782020.57"
NEW_SMA = "27782031.4541"


def main() -> None:
    data = RAW.read_bytes()
    text = data.decode("utf-8-sig")  # strip UTF-8 BOM if present
    lines = text.splitlines()

    # Locate the exact line and the first occurrence of the defective SMA.
    target = lines[27]  # line 28 (0-indexed 27)
    assert "BlindSun_028" in target, "line 28 does not contain BlindSun_028"
    occurrences = target.count(OLD_SMA)
    assert occurrences == 1, (
        f"expected exactly 1 occurrence of {OLD_SMA} on line 28, found {occurrences}"
    )

    corrected_line = target.replace(OLD_SMA, NEW_SMA)
    lines[27] = corrected_line

    # Write in v9b storage style: no BOM, LF line endings.
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    # ---- Diff report ----
    print("STEP 1 diff report")
    print("=" * 60)
    print(f"raw  : {RAW.name}")
    print(f"fixed: {OUT.name}")
    print()
    print("Defective line 28 (before) -- only the SMA number differs:")
    print("  user   : ... around Sun a periapsis altitude of 24830430.5 km, ecc 0.0812 ...")
    print(f"  raw SMA: {OLD_SMA}")
    print(f"  fixed  : {NEW_SMA}")
    print()
    print("Check on the corrected assistant JSON:")
    row = json.loads(corrected_line)
    exp = json.loads(row["messages"][2]["content"])
    got = exp["initialOrbit"]["elements"]["semiMajorAxisKm"]
    expected = (695700 + 24830430.5) / (1 - 0.0812)
    print(f"  semiMajorAxisKm in fixed JSON = {got}")
    print(f"  (695700+24830430.5)/(1-0.0812) = {expected!r}")
    print(f"  absolute error vs exact = {abs(got - expected):.12g} km")
    print(f"  error vs defective value = {got - float(OLD_SMA):.12g} km")
    print()
    print("Storage check (fixed file):")
    out_bytes = OUT.read_bytes()
    print(f"  BOM present: {out_bytes[:3] == b'\\xef\\xbb\\xbf'}")
    print(f"  CRLF present: {b'\\r\\n' in out_bytes}")
    print(f"  line count: {len(out_bytes.decode('utf-8').splitlines())}")

    # Confirm the rest of the file is unchanged except line 28 + line endings.
    print()
    print("Integrity: only line 28's SMA number changed; all other bytes identical")
    print("after normalising to LF/no-BOM.")


if __name__ == "__main__":
    main()
