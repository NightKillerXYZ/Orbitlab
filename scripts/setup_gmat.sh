#!/usr/bin/env bash
# Download a GMAT release zip (URL you supply) and extract it into tools/gmat/.
# Usage: scripts/setup_gmat.sh --url <release-zip-link> [--sha256 <hex>] [--out-dir <dir>]
set -euo pipefail

URL=""
SHA256=""
OUT_DIR=""
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

while [ $# -gt 0 ]; do
  case "$1" in
    --url) URL="${2:-}"; shift 2 ;;
    --sha256) SHA256="${2:-}"; shift 2 ;;
    --out-dir) OUT_DIR="${2:-}"; shift 2 ;;
    -h|--help)
      echo "Usage: scripts/setup_gmat.sh --url <release-zip-link> [--sha256 <hex>] [--out-dir <dir>]"
      exit 0 ;;
    *) echo "error: unknown option: $1" >&2; exit 1 ;;
  esac
done

if [ -z "$URL" ]; then
  echo "error: --url is required (supply the release zip link)." >&2
  exit 1
fi
if [ -z "$OUT_DIR" ]; then
  OUT_DIR="$REPO_ROOT/tools/gmat"
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

echo "Downloading GMAT release..."
if ! curl -fSL --retry 3 -o "$TMP_DIR/gmat.zip" "$URL"; then
  echo "error: download failed." >&2
  exit 1
fi

if [ -n "$SHA256" ]; then
  ACTUAL="$(sha256sum "$TMP_DIR/gmat.zip" | awk '{print $1}')"
  WANT="$(printf '%s' "$SHA256" | tr '[:upper:]' '[:lower:]')"
  GOT="$(printf '%s' "$ACTUAL" | tr '[:upper:]' '[:lower:]')"
  if [ "$GOT" != "$WANT" ]; then
    echo "error: SHA-256 mismatch; setup stopped." >&2
    exit 1
  fi
  echo "SHA-256 verified."
fi

mkdir -p "$OUT_DIR"
echo "Extracting..."
unzip -q -o "$TMP_DIR/gmat.zip" -d "$OUT_DIR"

CONSOLE="$(find "$OUT_DIR" -type f \( -name GmatConsole -o -name GmatConsole.exe \) -path '*/bin/*' -print 2>/dev/null | head -n 1 || true)"
if [ -z "$CONSOLE" ]; then
  echo "error: bin/GmatConsole(.exe) not found after extracting. The archive layout is unexpected." >&2
  exit 1
fi
echo "GMAT ready: $CONSOLE"
