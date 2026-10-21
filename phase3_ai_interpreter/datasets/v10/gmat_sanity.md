# v10 GMAT sanity (Step 4)

GMAT console: `C:\Users\canit\XY\Downloads\gmat-win-R2026a\bin\GmatConsole.exe`
12 runs = 3 validated rows (circular / periapsis / SMA+e) x 4 new bodies.
Numbers from validated experiments and `orbitlab_core/bodies.json`.

Two-body prediction: circular `v=sqrt(mu/SMA)`, `r=SMA`; elliptical vis-viva `v=sqrt(mu(2/r-1/SMA))` with `r in [a(1-e), a(1+e)]`.
PASS = GMAT returncode 0, telemetry produced, distance & speed within 0.5%.

| Body | Type | Rows | Name | SMA (km) | e | r rel % | v rel % | Status | Notes |
|---|---|---|---|---|---|---|---|---|---|
| Mercury | circular | 1 | MercB1_001 | 2525.5300 | 0.0000 | 0.000 | 0.000 | PASS | ok |
| Mercury | periapsis | 1 | MercB1_015 | 2614.5830 | 0.0400 | 0.000 | 0.000 | PASS | ok |
| Mercury | direct-sma | 1 | MercB1_027 | 2650.0000 | 0.0320 | 0.000 | 0.000 | PASS | ok |
| Venus | circular | 1 | VenB3_001 | 6231.8000 | 0.0000 | 0.001 | 0.004 | PASS | ok |
| Venus | periapsis | 1 | VenB3_015 | 7000.0000 | 0.1000 | 0.001 | 0.001 | PASS | ok |
| Venus | direct-sma | 1 | VenB3_027 | 6520.5000 | 0.0250 | 0.004 | 0.001 | PASS | ok |
| Jupiter | circular | 1 | JupB5_001 | 73342.0000 | 0.0000 | 0.000 | 0.000 | PASS | ok |
| Jupiter | periapsis | 1 | JupB5_015 | 80000.0000 | 0.0500 | 0.000 | 0.000 | PASS | ok |
| Jupiter | direct-sma | 1 | JupB5_027 | 82400.5000 | 0.0450 | 0.000 | 0.000 | PASS | ok |
| Sun | circular | 1 | SunB7_001 | 14959787.0690 | 0.0000 | 0.001 | 0.001 | PASS | ok |
| Sun | periapsis | 1 | SunB7_015 | 20000000.0000 | 0.1000 | 0.000 | 0.000 | PASS | ok |
| Sun | direct-sma | 1 | SunB7_027 | 25400000.0000 | 0.0450 | 0.000 | 0.000 | PASS | ok |

**Result: 12/12 runs PASS.**
