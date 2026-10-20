====== TASKING START ======
TASK: OrbitLab v9 close-out. Work inside the Phase3 folder (phase3_ai_interpreter\, orbitlab_core\, body_expansion\).
Do NOT start phase 2 (the v10 dataset). Do NOT touch the UI folder.

RULES
1. FROZEN: every v9 and v9b dataset file, its manifest and its hashes. Read only. If a task seems to need a change there, skip that task and list it under "needs decision" in the report.
2. No invented numbers. Physical values come only from orbitlab_core\bodies.json (values below) or from a file and line you cite.
3. One task at a time. After each task run its check. If the check fails, fix it or stop that task and record it. Never stack new work on a failing step.
4. Never delete files. Move anything obsolete into _to_delete\ and list it.
5. If a spec, design note or earlier decision for a task cannot be found in the existing files (search all .md and .json files under Phase3 for the keywords given), do not guess. Write "spec not found" for that task and move on.
6. Write all new notes and reports into a new folder closeout\.

STEP 0: AUDIT (read only, edit nothing) -> closeout\status.md
For every item in the list below write DONE, PARTIAL or NOT DONE, with evidence (file:line, or the command you ran and its output) and what is missing.

ITEMS
 1. bodies.json final values. Seven bodies: Earth, Moon, Mars, Mercury, Venus, Jupiter, Sun.
    Legacy values stay frozen:  Earth radius 6378.1363, mu 398600.4415, min altitude 100;  Moon 1737.4, 4902.800066, 20;  Mars 3389.5, 42828.375214, 20.
    New bodies use the GMAT read-back mu, with ALL digits:  Mercury 22032.080486;  Venus 324858.598827;  Jupiter 126712767.857614;  Sun 132712440017.746521. Each has muSource "GMAT read-back, task B".
    New radii:  Mercury 2440.53;  Venus 6051.8;  Jupiter 71492;  Sun 695700.
    Minimum periapsis altitudes (design settings, say so in muNotes/notes):  Mercury 20;  Venus 100;  Jupiter 1000;  Sun 6261300.
    Point-mass-only: Sun, Mercury, Jupiter. Moon's GMAT name is "Luna".
    body_expansion\mu_readback.json and .md must match bodies.json exactly.
 2. orbitlab_core\constants.py loads the table, and every previously public name still works.
 3. Validator: per-body minimum altitude from the table; a warning when the central body is point-mass-only and a gravity degree/order was given (it is ignored); SOI rule soiRadiusKm = d * (mu_body / mu_parent)^(2/5), with d measured from GMAT at epoch 01 Jan 2026 12:00:00.000 UTCGregorian; the Sun has no limit. Apply the SOI rule only if no v9b row newly fails because of it. Otherwise leave soiRadiusKm null and record that in the report.
 4. Compiler: point-mass-only bodies emit CentralBody=<body>, PrimaryBodies={}, PointMasses={<body>}, and no GravityField. The central body appears once in PointMasses. Do not create EarthMJ2000Eq (it is built in). ReportFile paths are absolute. ReportFile.Add is on one line.
 5. Front step (frontstep.py): enums and prompt handling for all seven bodies, including "x AU from the centre" for the Sun. A planet as the orbiting object is still rejected. test_frontstep case #10 (formerly "Sun unsupported") is updated to match.
 6. Golden diff: all 4300 v9b rows give the same success, errors, warnings and compiled-script SHA-256 as body_expansion\golden_before.json and golden_scripts_before.json. Use golden_snapshot.py. Zero differences allowed.
 7. body_expansion\implementation_report.md exists and matches the code.
 8. v9c leftovers (keywords: v9c, scorer, blind, SMA, manifest, overlap): (a) scorer artifacts, (b) the 20 blind rows per spec, (c) SMA audit coverage, (d) manifest hashes, (e) overlap tables. Everything for v9c goes into NEW files. Never edit v9 or v9b files.
 9. Sentence-style prompt builder: Python builds the prompt text for the interpreter from the extracted and converted fields (the LLM only extracts; Python does conversions, defaults and prompt building). Keywords: prompt builder, sentence.
10. Unsupported-status output patch: requests the schema cannot express must return an explicit status "unsupported" with readable reasons, not a crash or a bare JSON error. Keywords: unsupported, status.
11. Stage 4 end-to-end test (front step -> interpreter -> validator -> compiler). Find the Stage 4 test set. Run prompt 1 and answer one question: is the 270° value rejected, and with what reason text? Run the whole Stage 4 set if one exists.

STEP 1: FINISH
For every item that Step 0 marked PARTIAL or NOT DONE, in the order 1 to 11, do the work, run its check, and update closeout\status.md. For item 11 do not change code to make a test pass. Report the real result, and list any fix you think is needed as a proposal.

STEP 2: FINAL CHECKS
 - Run the project's full existing test suite. Report counts before Step 1 and after Step 1.
 - Re-run the golden diff (item 6). It must show zero differences.
 - Write closeout\report.md with: a table of items 1-11 (final status), test counts, the golden diff result, the list of files created, changed and moved, the full output of the Stage 4 prompt 1 run, and a "needs decision" list.
 - Your final message: at most 15 lines, with the table and the path to report.md.
====== TASKING END ======