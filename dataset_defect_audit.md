# Dataset defect audit — `orbitlab_v13f_main_train.jsonl` (READ-ONLY)

File: `phase3_ai_interpreter/datasets/v13_build/orbitlab_v13f_main_train.jsonl`
Method: full-file pass, 3690 lines, no writes to the file. Assistant message parsed as
Experiment JSON on every line (0 non-JSON assistant lines). Line numbers below are
1-based file lines. Nothing in this report changes the dataset.

## 0. Context — records per central body (total 3690)

| centralBody | records |
|---|---|
| Earth | 1101 |
| Moon | 943 |
| Mars | 881 |
| Venus | 199 |
| Sun | 197 |
| Mercury | 192 |
| Jupiter | 177 |

## 1. Point-mass perturber defects

### 1a. Moon-centered records listing Luna as a perturber: 710 / 943 (75.3%)

A Moon-centered run with `Luna` in `forceModel.pointMasses` lists the central body as
its own perturber. Example lines: **1**, **7**, **12**.

- Line 1: `centralBody Moon`, `pointMasses ['Luna', 'Sun']`, no maneuvers.
- Line 7: `centralBody Moon`, `pointMasses ['Luna', 'Sun']`, maneuver `Course_Adjust_Rangin`.
- Line 12: `centralBody Moon`, `pointMasses ['Luna', 'Sun']`, maneuvers
  `Dawn_Shift_Naviga` + `Kineti_Vector_Scienc`.

Moon `pointMasses` distribution for context: `('Luna','Sun')` 689, `('Sun','Jupiter')` 101,
`('Sun',)` 60, `('Jupiter',)` 46, `()` 26, `('Luna',)` 10, `('Luna','Sun','Jupiter')` 10,
`('Luna','Jupiter')` 1. So 710 = 689 + 10 + 10 + 1.

### 1b. Mars-centered records omitting Earth: 881 / 881 (100%)

No Mars record lists Earth as a perturber. Example lines: **3**, **4**, **9**.

- Line 3: `centralBody Mars`, `pointMasses ['Luna', 'Sun']`, maneuver `Zenith_Shift_Visibi`.
- Line 4: `centralBody Mars`, `pointMasses ['Luna', 'Sun']`, no maneuvers.
- Line 9: `centralBody Mars`, `pointMasses ['Luna', 'Sun']`, no maneuvers.

Mars `pointMasses` distribution: `('Luna','Sun')` 678, `('Sun',)` 52, `('Jupiter',)` 52,
`('Sun','Jupiter')` 44, `()` 29, `('Luna',)` 13, `('Luna','Sun','Jupiter')` 13.
Dominant pattern (678) is Luna+Sun with no Earth — the same default the pipeline
applies to every body (see `defaults_fix_report.md` Part 2).

## 2. Maneuver names truncated to 6 characters per word: 635 / 3690 records (17.2%)

Maneuver `id`s of the form `Word_Word_Word` with every word cut to at most 6 characters.
Detection: id contains `_`, splits into ≥2 words, all words ≤ 6 chars
(plain ids such as `M1`, `MSGNA82Y` do not match). 835 of 1443 total maneuver entries
contain `_`. Example lines: **3**, **5**, **7**.

- Line 3: `Zenith_Shift_Visibi` (TargetedHohmannTransfer).
- Line 5: `Inclin_Lift_Highla`, `Meridi_Change_Dawn` (ImpulsiveBurns).
- Line 7: `Course_Adjust_Rangin` (ImpulsiveBurn).
- Further specimens: `Dawn_Shift_Naviga`, `Kineti_Vector_Scienc`, `Meridi_Trim_Tracki`,
  `Vector_Maneuv_Waypoi`, `Quasar_Raise_Apsis`, `Kineti_Burn_Naviga`, `Apsis_Trim_Beacon`,
  `Rendez_Lift_Cartog` (lines 12, 14, 17, 19, 20, 23).

## 3. Content fractions (denominator 3690)

| content | records | share |
|---|---|---|
| non-empty `maneuvers` | 1184 | 32.1% |
| Cartesian state (`initialOrbit.type == Cartesian`) | 488 | 13.2% |
| `description` present (assistant JSON) | 380 | 10.3% |
| multi-turn (anything other than exactly system/user/assistant) | 0 | 0% |
| clarification content (user asks for clarification, or assistant ends with `?` / `please provide` / `need more`) | 0 | 0% |

Every record is exactly 3 messages (system, user, assistant) with a single user turn;
no record contains a clarification exchange by the above heuristics.

## 4. JSON skeletons (keys only, values ignored)

Recursive key structure of the assistant Experiment JSON, lists collapsed to one
element slot: **29 distinct skeletons**. Top 5 hold **2771 / 3690 = 75.1%**:

| rank | records | share | example line | shape |
|---|---|---|---|---|
| 1 | 1752 | 47.5% | 1 | Keplerian, no maneuvers, no description |
| 2 | 338 | 9.2% | 19 | Keplerian, no maneuvers, no description, variant element set |
| 3 | 237 | 6.4% | 9 | Cartesian elements, no maneuvers |
| 4 | 229 | 6.2% | 11 | Keplerian, no maneuvers, no description, variant element set |
| 5 | 215 | 5.8% | 2 | Keplerian, no maneuvers, with `description` |

(Coarse grouping by top-level keys + orbit type + maneuver presence gives 8 shapes:
1981 Keplerian/none, 908 Keplerian/maneuvers, 248 Cartesian/none, 221 Keplerian +
description/none, 173 Cartesian/maneuvers, 92 Keplerian + description/maneuvers,
56 Cartesian + description/none, 11 Cartesian + description/maneuvers; top 5 = 95.7%.)
