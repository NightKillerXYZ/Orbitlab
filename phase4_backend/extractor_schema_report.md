# Extractor schema report (`fix-extractor`)

## Step 1 — what the converter reads today (read-only)

`FrontStepExtractor.deterministic_convert` (`phase4_backend/orbitlab_backend/frontstep/extractor.py`) reads:

- `centralBody` (string; must be a key of `BODY_RADII_KM`, else `needs_clarification ["centralBody"]`).
- `dryMassKg` (number or numeric string via `float()`; `None`/missing → `needs_clarification ["dryMassKg"]`).
- `orbit`: dict with `kind` in `semiMajorAxisKm | circularAltitudeKm | circularAltitude | periapsisAltitudeKm | apsisAltitudes | apoPeriRadii | circularRadiusKm`, carrying `value` (+ `unit` in km/miles/m/AU, default km) and `eccentricity` where applicable; or fallback dict keys `semiMajorAxisKm` / `sma` (+ `eccentricity`); or a bare `{"value": N}` (treated as circular-altitude); anything else → `needs_clarification ["orbit"]`. `cartesian` dict bypasses orbit math (`sma=None`).
- `eccentricity` (top-level or inside orbit; number, numeric string, or `{value, unit:"rad"}` dict).
- `inclinationDeg`, `raanDeg`, `argumentOfPeriapsisDeg` (or alias `aopDeg`), `trueAnomalyDeg` (number, numeric string, or rad-dict; default 0).
- `duration` dict `{"value", "unit"}` (unit lowercased; seconds/minutes->`ElapsedSeconds`, hours->`ElapsedHours`, days->`ElapsedDays`, orbit-ish->`OrbitPeriods`; non-dict / null value / unknown unit now → `needs_clarification ["duration"]`).
- `integrator` (`RungeKutta89`|`PrinceDormand78`, else default `RungeKutta89`); `forces` passed through untouched; `maneuvers` list passed through untouched.
- Maneuver shapes the converter reads (front-step form, NOT validator form): `Hohmann {type:"Hohmann", id, targetOrbitRadiusKm, apsis: periapsis|apoapsis, targetEccentricity?}` and `ImpulsiveBurn {type:"ImpulsiveBurn", id, trigger: ElapsedTimeSecs|AtApoapsis|AtPeriapsis, elapsedSecs?, apsis?, deltaV:[x,y,z]}`. The `verify` step maps these onto `TargetedHohmannTransfer`/`ImpulsiveBurn` validator objects.
- Names: previously read `experimentName`/`spacecraftName` from the model output when present. Removed (Python owns names: always generated + sanitised).

`_fallback_extract` regexes (`_fallback_extract` in the same file): body keyword; `dryMass` from `(\d) kg`; orbit only from `N km circular` -> circular-altitude, `altitude N km` (+ optional `e N`) -> periapsis-altitude, or `sma N`; `eccentricity N`; duration from `propagate ... N <unit>` or `for N <unit>` with units hours|days|seconds|minutes|orbit(s)|(orbital )period(s); integrator from "prince"/"runge" keywords. Anything else (e.g. "400 km altitude" order, singular "day") yields missing fields.
