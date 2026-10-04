# OrbitLab Simulation Engine

Phase 2 executes already-compiled GMAT scripts in isolated temporary directories,
parses their `ReportFile` telemetry, and produces full and visualization-ready
trajectories. It does not validate experiments or generate/modify GMAT scripts.
Each run uses a sandbox-local GMAT startup configuration so relative GMAT output
is redirected into that run directory without modifying the GMAT installation.

The required telemetry fields are `ElapsedSecs`, `X`, `Y`, `Z`, `VX`, `VY`,
`VZ`, `SMA`, `ECC`, `INC`, and `Altitude`. Phase 1 compiler output includes this
complete contract.
