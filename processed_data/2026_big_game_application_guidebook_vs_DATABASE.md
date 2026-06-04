# 2026 Big Game Application Guidebook vs DATABASE Audit

Source PDF: `pipeline/RAW/hunt_unit_database/2026/pdf/regulations/2026 Big Game Application.pdf`

This is a regulation/reference audit. It does not promote guidebook text into draw odds, harvest features, or 2026 quota math.

## Summary

- Guidebook hunt codes extracted: `728`
- Guidebook hunt codes found in DATABASE.csv: `728`
- Guidebook hunt codes missing from DATABASE.csv: `0`
- Name review warnings: `6`
- Season review warnings: `0`
- Blockers: `0`
- Post-publication corrections checked: `4`
- Post-publication correction review items: `0`

## Post-Publication Corrections

| hunt_code | action | status | correction |
|---|---|---:|---|
| DB1276 | DELETE_HUNT_ROW | PASS | Plymouth Peak is no longer a CWMU and was combined with Washakie CWMU. |
| MB6264 | DELETE_HUNT_ROW | PASS | Sand Creek CWMU was included in error; there is no public moose permit this year on that CWMU. |
| DB1115 | RENAME_HUNT | PASS | Hunt name shortened from Henry Mtns, Little Rockies to Little Rockies. |
| DB1350 | DELETE_HUNT_ROW | PASS | Milburn CWMU withdrew from the program. |

## Significant Differences

| hunt_code | severity | reason | guidebook | database |
|---|---:|---|---|---|
| DB1009 | WARNING | NAME_NEEDS_REVIEW | Henry Mtns (any legal weapon) | Henry Mtns Management |
| DB1010 | WARNING | NAME_NEEDS_REVIEW | Paunsaugunt (any legal weapon) | Paunsaugunt Management |
| DB1090 | WARNING | NAME_NEEDS_REVIEW | Book Cliffs, Floy Canyon | HAMSS |
| DB1105 | WARNING | NAME_NEEDS_REVIEW | East Canyon | HAMSS |
| DB1116 | WARNING | NAME_NEEDS_REVIEW | San Juan, Mancos Mesa | HAMSS |
| DB1121 | WARNING | NAME_NEEDS_REVIEW | Antelope Island (any legal weapon) (new) | Antelope Island Management |

Full row-level comparison: `processed_data/2026_big_game_application_guidebook_vs_DATABASE.csv`
