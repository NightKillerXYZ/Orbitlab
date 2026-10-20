# SOI Provenance and Recomputation (T3)

Formula: **soiRadiusKm = d * (mu_body / mu_parent)^(2/5)**

- `d` measured by NASA GMAT at epoch **01 Jan 2026 12:00:00.000 UTCGregorian**
  (planets relative to the Sun, Moon relative to Earth).
- `mu_body` and `mu_parent` from `orbitlab_core/bodies.json`.
- GMAT console: `C:\Users\canit\XY\Downloads\gmat-win-R2026a\bin\GmatConsole.exe`; probe script `closeout2/soi_work/soi_probe.script`, log `closeout2/soi_work/gmat.log`.
- Current `soiRadiusKm` read from `orbitlab_core/bodies.json` (via `constants.BODY_SOI_RADIUS_KM`).
- **Source of every current value:** none is recorded under Phase3 — `body_expansion/implementation_report.md` l.103-105 & l.176 record the SOI formula as *deferred / spec-not-found*; the static values have no `soiSource` field.

| Body | Parent | d@epoch (km) | mu_body (km3/s2) | mu_parent (km3/s2) | Current SOI (km) | Recomputed SOI (km) | Diff % | Action |
|---|---|---|---|---|---|---|---|---|
| Mercury | Sun | 69304633.3 | 22032.080486 | 132712440017.746521 | 112000.000 | 134530.210 | 20.116% | replace (no source) |
| Venus | Sun | 108818682.7 | 324858.598827 | 132712440017.746521 | 616000.000 | 619750.031 | 0.609% | replace (no source) |
| Earth | Sun | 147102351.3 | 398600.441500 | 132712440017.746521 | 925000.000 | 909222.284 | -1.706% | replace (no source) |
| Moon | Earth | 360486.1 | 4902.800066 | 398600.441500 | 66200.000 | 62065.619 | -6.245% | replace (no source) |
| Mars | Sun | 213652311.5 | 42828.375214 | 132712440017.746521 | 577000.000 | 541047.733 | -6.231% | replace (no source) |
| Jupiter | Sun | 779715403.5 | 126712767.857614 | 132712440017.746521 | 48200000.000 | 48294715.423 | 0.197% | replace (no source) |

**Decision:** replace all six. Per the T3 recompute rule, any value with **no documented source** or **>1% difference** is replaced. Every current value has no recorded source, so all six were replaced with the recomputed GMAT values in `orbitlab_core/bodies.json` (decision: user-approved).
The three legacy frozen constants (Earth/Moon/Mars **radius & mu**) are untouched — only the SOI radius (an added, non-frozen check parameter) is affected.

**Dataset impact (verified, 0):** a pass/fail sweep of all 4,300 v9b master rows against the old vs. new `soiRadiusKm` found **zero rows newly fail**. v9b contains only Earth/Moon/Mars rows (1492/1424/1384); none has an apoapsis in the shrink bands (Earth 909222–925000, Moon 62066–66200, Mars 541048–577000 km). Mercury/Venus/Jupiter have no v9b rows, and their SOI only grew (no new failures possible). The prior guard condition ("apply only if no v9b row newly fails") is satisfied.

**GMAT probe:** returncode=0, telemetry produced, no warnings logged.