TASK: OrbitLab v9 close-out, part 2 (verification of the 7-body work). Work in the Phase3 folder. New notes and reports go into closeout2\.
Do NOT start phase 2 (v10 dataset). Do NOT touch the UI folder.

RULES
1. FROZEN, read only: every v9 and v9b dataset file, manifest and hash; body_expansion\golden_before.json and golden_scripts_before.json.
2. No invented numbers. Values come only from orbitlab_core\bodies.json or from a file and line you cite, or from a GMAT run you actually did.
3. One task at a time; run its check after each. If a check fails, fix it or stop that task and record it. Never stack work on a failing step.
4. Never delete files. Obsolete files go to closeout2\_to_delete\ and are listed.
5. If something cannot be done (for example GMAT cannot be launched), stop that task, write exactly why, and move on. Do not guess.
6. Existing Earth, Moon and Mars compiled scripts must stay byte-identical (golden diff).

T1. PERMANENT TESTS FOR THE NEW BODIES  ✅ DONE — orbitlab_core\tests\test_new_bodies.py (12 new tests); full suite 48 tests OK; golden diff re-run 0 mismatches (closeout\step2_golden_diff.json, 4300 rows)
Create orbitlab_core\tests\test_new_bodies.py (same test framework as the existing tests there). Use the old throwaway scripts in closeout\_to_delete\check_item3.py and check_item4.py as a starting point (leave them where they are). Cover all 7 bodies (Earth, Moon, Mars, Mercury, Venus, Jupiter, Sun):
 a) Validator: periapsis altitude just below the body's minimum -> invalid; just above -> valid.
 b) Validator: for Sun, Mercury, Jupiter with gravity degree > 0 -> a warning containing "point mass" and "ignored". For Earth, Moon, Mars, Venus -> no such warning. Sun with degree 0 -> no such warning.
 c) Compiler: point-mass-only bodies emit "PrimaryBodies = {};", the central body exactly once in PointMasses, no GravityField line, no potential file. Other bodies emit a GravityField block and a potential file. Venus must use the potentialFile named in bodies.json (do not hardcode it; if the generator hardcodes by body name, fix it so it reads bodies.json). ReportFile.Add is on one line.
 d) SOI containment: Jupiter apoapsis inside its limit -> valid, outside -> invalid with the SOI reason text; Sun never limited.
Check: run the whole suite. Report the new test count. Then run the golden diff again (closeout\step2_golden_after.py); it must show 0 mismatches.

T2. REAL GMAT RUN FOR EVERY BODY  ✅ DONE — closeout2\gmat_runs.md: 7/7 PASS (return 0, telemetry, distance & speed within 0.5%)
Find how orbitlab_core\tests\test_gmat_execution.py launches GMAT and reuse it (do not invent paths). For each body compile and run a circular orbit, ReportFile with an ABSOLUTE path:
 Mercury 500 km altitude, 1 day; Venus 400 km, 1 day; Earth 400 km, 1 day; Moon 100 km, 1 day; Mars 300 km, 1 day; Jupiter 5000 km, 1 day; Sun at 0.5 AU from the centre (use the AU_KM constant from the code), 10 days.
For each run record: GMAT exit status, any error or warning in the GMAT log, whether the report file was written, the smallest and largest distance from the centre in the report, and the speed at the first row. Compare with the expectation from bodies.json: radius = body radius + altitude (Sun: the AU distance), speed = sqrt(mu / radius). Pass if both are within 0.5%.
Write closeout2\gmat_runs.md with one table row per body plus the raw log paths. Do not change a script to make a run pass without recording the change and the reason.

T3. SOI PROVENANCE  ✅ DONE — see closeout2\soi_check.md; all six replaced (user-approved), bodies.json updated, T1 suite re-run (48 tests OK), golden diff re-run (0 mismatches, 4300 rows)
List every soiRadiusKm value now in bodies.json (or wherever the validator gets them) and where each came from. For each body that has one, recompute soiRadiusKm = d * (mu_body / mu_parent)^(2/5), with d = the distance from the parent body measured in GMAT at epoch 01 Jan 2026 12:00:00.000 UTCGregorian (planets relative to the Sun, the Moon relative to Earth) and mu from bodies.json. Write closeout2\soi_check.md with a table: body, current value, recomputed value, difference in %, source. If a current value has no source or differs by more than 1%, replace it with the recomputed value, record that, then re-run T1 and the golden diff. The Sun has no limit.

T4. GOLDEN DIFF FOR WARNINGS  ✅ DONE — closeout2\warnings_diff.json: 0 differences across all 4,300 rows; see closeout2\warnings_diff.md
The earlier golden diff did not compare per-row warnings. Export the old code with:  git archive 4d5d3e8 orbitlab_core | tar -x -C closeout2\old_core
Write closeout2\warnings_diff.py that runs the same v9b master file through the OLD orbitlab_core (put closeout2\old_core first on sys.path in a separate process) and through the CURRENT one, recording for every row: is_valid, the error list and the warning list. Compare row by row. Write the result to closeout2\warnings_diff.json. Required: 0 differences.

T5. SMA AUDIT COVERAGE  ✅ DONE — 1711 N/A broken down by reason; new audit_v9c_sma_all.py/.json: 3687 pass, 0 fail, 613 still-N/A (612 full-Cartesian + 1 maneuver row); see change_notes.md Step 3
Read datasets\v9\audit_v9c_sma.py and audit_v9c_sma.json. The audit has 2589 pass and 1711 N/A. Report the 1711 by reason (for example: orbit given by altitude, by period, by gravity fraction). For the groups where the semi-major axis can be derived from the row's own values and bodies.json radius, write a NEW script datasets\v9\audit_v9c_sma_all.py and a NEW output audit_v9c_sma_all.json that audits them too. Do not edit the existing files. Report pass, fail and still-N/A counts.

T6. REPORT  ✅ DONE — closeout2\report.md (status table, test counts, golden diff, GMAT table, SOI table, file inventory, needs-decision, item-9 label-mismatch note at top)
Write closeout2\report.md: a table of T1 to T5 (status, evidence), the final test counts, the golden diff result, the full GMAT table from T2, the SOI table from T3, the list of files created, changed and moved, and a "needs decision" list. Correct the item 9 label mismatch you find between closeout\status.md and closeout\report.md in a note at the top. Final message: at most 15 lines with the table and the path to report.md.
