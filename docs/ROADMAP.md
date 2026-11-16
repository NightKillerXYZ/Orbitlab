# OrbitLab Roadmap

## v1 — done

Deterministic pipeline (extract → interpret → verify → validate → compile →
real GMAT), 7 central bodies, Keplerian/Cartesian states, Hohmann + impulsive
burns, demo mode, Main UI (3D, plots, ground track, Details, export), burn-size
clarification, per-body perturber defaults, guided-JSON trial.

## v2a — next (compiler/backend, light model data)

What-if/compare with multi-turn follow-ups; Saturn, Uranus, Neptune as central
bodies; higher-fidelity force models; more frames, state types, time scales;
eclipse and ground-station events; CCSDS/SPICE/STK export; sweeps; fuel and
delta-V budget.

## v2b — heavy

Fuel tank, thruster, finite burns; Target (differential corrector); mission
templates (Earth→Moon needs Target; Hohmann-type templates are analytic);
Walker constellations with multi-spacecraft viewer; two-body transfer view.

## v3 — later

Control-flow scripting, Optimize/CSALT. Cut line: if time is short, v2a plus
analytic templates ship and Target + finite burns move here.

## Out of scope (for now)

Orbit determination. Flight operations (research and education tool only).
