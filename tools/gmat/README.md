# tools/gmat — bundled GMAT (filled by the setup script)

This folder is intentionally empty in git. Run `scripts/setup_gmat.ps1`
(Windows) or `scripts/setup_gmat.sh` (Linux/macOS) with the release zip URL
to download and extract a GMAT build here. The backend then finds
`tools/gmat/**/bin/GmatConsole(.exe)` automatically when `GMAT_PATH` is not
set; an explicitly set `GMAT_PATH` always wins.

Do NOT commit GMAT binaries or archives: `tools/gmat/*` is git-ignored
except for this README.
