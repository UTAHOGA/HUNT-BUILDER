# DATABASE(2) vs Public Age/Export Universe Gap Report

## Purpose
Audit and explain the reported 55-hunt-code difference between:

- `DATABASE(2).csv` universe: **1,394** hunt codes
- public age/export universe: **1,449** hunt codes

## Source Resolution Used
There is no file named `DATABASE(2).csv` in the active repo path.  
To match your stated `1,394` count, this audit used:

- `data/hunt-master-canonical-2026-foundation.json` (**1,394** unique hunt codes)

Public export universe source:

- `processed_data/audits/average_harvest_age_two_column_audit.csv` (**1,449** unique hunt codes)

Canonical database truth cross-check source:

- `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv` (**1,449** unique hunt codes)

## Findings

1. `public_export_universe - database2_1394_universe = 55` hunt codes.
2. `database2_1394_universe - public_export_universe = 0` hunt codes.
3. All 55 gap codes are present in canonical `DATABASE.csv` (1,449/1,449 truth universe).
4. All 55 are also missing from:
   - `data/hunt-master-canonical-2026-source-of-truth.json` (1,411 universe)
5. Pattern of 55 missing codes:
   - `CWMU`: 36
   - `General Season`: 6
   - `Limited Entry`: 6
   - `Once-in-a-lifetime`: 3
   - `Black Bear seasonal LE variants`: 4 (`Spring/Summer/Fall`)

Species distribution in the 55:

- Deer: 15
- Moose: 15
- Elk: 10
- Pronghorn: 9
- Black Bear: 4
- Bison: 1
- Desert Bighorn Sheep: 1

## Conclusion
The 55-code difference is not an intentional public-export expansion beyond truth.

It is a **stale canonical baseline issue**:

- the 1,394 universe (foundation baseline) is stale/incomplete
- the public age/export universe is aligned to the current `DATABASE.csv` truth universe of 1,449

## Determination Requested

- Is the public export universe stale? **No** (it matches current `DATABASE.csv` hunt-code universe)
- Is DATABASE(2) missing active canonical rows? **Yes**, if DATABASE(2) refers to the 1,394 baseline
- Is the difference intentional? **Not supported by evidence**
- Should export pipeline be realigned to DATABASE(2).csv? **No**

Recommended realignment:

- Use `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv` (1,449) as canonical universe for exports.
- Retire or explicitly mark `data/hunt-master-canonical-2026-foundation.json` and 1,411 source-of-truth JSON as stale unless regenerated from current `DATABASE.csv`.

## Artifact
Detailed per-code breakdown is in:

- `processed_data/audits/database_vs_public_export_universe_gap.csv`
