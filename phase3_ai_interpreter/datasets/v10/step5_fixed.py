"""v10 dataset gate -- Step 5: populate datasets/v10/fixed/.

The project stores v9/v9b JSONL as LF line endings with no BOM (verified: every
v9/v9b file has 0 CRLF and 0 BOM).  The final v10 `fixed\\` set therefore stores
all 10 files in that same convention:

  - batch_01..batch_08 and batch_09 are copied from `raw\\` with only the storage
    normalisation applied (strip UTF-8 BOM, convert CRLF -> LF).  Row JSON text is
    byte-identical.
  - batch_10 is the Step 1 corrected file (already written to fixed\\ with LF, no BOM).

This only changes storage bytes (line endings / BOM), never row content.
"""

from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
FIXED = HERE / "fixed"


def normalize(text: str) -> str:
    """Return text with LF line endings and no leading BOM char."""
    # read with utf-8-sig already strips BOM; normalise all newlines to \n.
    return text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n") + "\n"


def main():
    FIXED.mkdir(parents=True, exist_ok=True)
    files = [
        "batch_01_mercury_valid.jsonl",
        "batch_02_mercury_valid.jsonl",
        "batch_03_venus_valid.jsonl",
        "batch_04_venus_valid.jsonl",
        "batch_05_jupiter_valid.jsonl",
        "batch_06_jupiter_valid.jsonl",
        "batch_07_sun_valid.jsonl",
        "batch_08_sun_valid.jsonl",
        "batch_09_all_reject.jsonl",
        "batch_10_all_blind.jsonl",
    ]
    for fn in files:
        src = RAW / fn
        dst = FIXED / fn
        if fn == "batch_10_all_blind.jsonl":
            if not dst.exists():
                raise SystemExit(f"missing Step 1 corrected file: {dst}")
            print(f"batch_10_all_blind.jsonl  kept (Step 1 corrected, LF, no BOM)")
            continue
        text = src.read_text(encoding="utf-8-sig")
        dst.write_text(normalize(text), encoding="utf-8", newline="")
        print(f"{fn}  wrote {dst}")

    print("\nFixed set contents:")
    for f in sorted(FIXED.iterdir()):
        b = f.read_bytes()
        print(f"  {f.name}: crlf={b.count(chr(13).encode())} lf={b.count(chr(10).encode())} "
              f"bom={b.startswith(b'\xef\xbb\xbf')} rows={len(b.splitlines())}")


if __name__ == "__main__":
    main()
