TASK: Score my tests of the tuned OrbitLab interpreter (attempt 2, data v12) and compare with attempt 1. Save this tasking to training\realtime\TASKING_A2.md first. Do not modify any dataset, validator, compiler, schema or eval cases file.

INPUT: raw model outputs for T01-T12 below (each starts with its id line). Strip code fences and parse the JSON; record fences/pretty-printing as format notes only. Save the raw text unchanged to training\realtime\outputs_raw_A2.txt. Missing or invalid JSON = FAIL.

EXPECTED (default force settings unless stated: Earth/Moon/Mars/Venus gravity 4/4 pointMasses ["Luna","Sun"]; Mercury/Jupiter 0/0 ["Luna","Sun"]; Sun 0/0 []; atmosphericDrag {"enabled":false,"model":"JacchiaRoberts"}; SRP true; maneuvers []; stepSizeSecs 60.0; epoch "01 Jan 2026 12:00:00.000" UTCGregorian; spacecraft name "SC_"+run name, coefficients 2.2/1.0/1.8/1.0; frame <Body>MJ2000Eq, Moon: centralBody "Moon" with LunaMJ2000Eq):
T01 Earth circular alt 800 -> SMA 7178.1363 (accept 7178.136), inc 98.6, RAAN 25, aop 0, ta 0, 850 kg, 10 h, RungeKutta89
T02 Earth periapsis alt 300, ecc 0.65 -> SMA 19080.389, inc 41, RAAN 200, aop 45, ta 10, 2200 kg, 20 h, PrinceDormand78
T03 Moon circular alt 60 -> SMA 1797.4, inc 45, RAAN 10, aop 0, ta 0, 950 kg, 6 h, RungeKutta89
T04 Mars SMA 3900 ecc 0.02, inc 25, RAAN 80, aop 10, ta 0, 1200 kg, 24 h, RungeKutta89
T05 Venus circular alt 450 -> SMA 6501.8, inc 60, RAAN 0, aop 0, ta 0, 700 kg, 8 h, PrinceDormand78
T06 Mercury SMA 3000 ecc 0.1, inc 88, RAAN 10, aop 0, ta 0, 350 kg, 12 h, RungeKutta89
T07 Jupiter circular alt 250000 -> SMA 321492.0, inc 12, RAAN 0, aop 0, ta 0, 2600 kg, 3 days, PrinceDormand78
T08 Sun SMA 0.5 AU = 74798935.346 km, ecc 0.1, inc 3, RAAN 0, aop 0, ta 0, 400 kg, 60 days, RungeKutta89
T09 Earth circular alt 70 -> SMA 6448.1363 (accept 6448.136), inc 51.6, 500 kg, 6 h, RungeKutta89; must NOT be changed to another altitude; pipeline must REJECT (minimum altitude)
T10 Earth circular alt 500, inclination 200 -> SMA 6878.1363 (accept 6878.136), inclinationDeg 200.0 kept; pipeline must REJECT (Pydantic)
T11 Moon SMA 80000 ecc 0.2, inc 30, 800 kg, 2 days, RungeKutta89 -> values kept; pipeline must REJECT (beyond SOI)
T12 Mars periapsis alt 8, ecc 0.05 -> SMA 3576.316 ((3389.5+8)/0.95), inc 70, 900 kg, 6 h, RungeKutta89; must NOT be changed; pipeline must REJECT (minimum altitude)
Common prompt fields not listed above are as written in the test prompt (RAAN/aop/ta 0 where not stated, run name = test id).

DO:
1. Parse each output; run Pydantic + AstrodynamicValidator (+ compiler for accepts); record verdict and the exact reason text.
2. Field-level scoring: for each test check these 14 parts (1 = correct): version, experimentName, spacecraft block, centralBody, epoch, frame inside initialOrbit, SMA (tolerance 0.002 km), eccentricity + four angles, gravity degree/order, pointMasses, atmosphericDrag object, solarRadiationPressure, maneuvers key present, propagation block (integrator, stopCondition, step). Report per test, per field, per group (structure / copied numbers / SMA / defaults / Earth-Moon-Mars vs new bodies) and the overall percentage, and the number of tests with all 14 correct. For comparison, attempt 1 scored 137/168 (81.5%) with 0 fully correct tests, SMA 4/12, maneuvers key 5/12, drag object 8/12, propagation block 9/12.
3. List every failure with got vs expected, classified as: wrong schema key / wrong default / arithmetic error / invalid value changed (clamped) / missing key / invalid JSON / format only.
4. Write training\realtime\report_A2.md with the tables, the classes of failure with counts, a comparison with attempt 1, and a "next change" section: ONE recommended change for attempt 3 backed by the failure evidence. Update ATTEMPTS.md with the realistic and blind results. Back up to the SSD. Commit scripts/report only.
RULES: run everything, no guessing, do not fix or edit the outputs.

