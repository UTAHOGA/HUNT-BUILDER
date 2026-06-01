# Average Harvest Age Two-Column Policy

## Final Definitions

- `Average Harvest Age`: observed harvested-age value from annual-report age evidence and validated carry-forward families.
- `Current Age (3-Yr Avg)`: Utah DWR Hunt Planner current three-year average age context value.

## Production Behavior (Locked)

1. Blanks are intentional where no defensible source exists.
   - Do not zero-fill age fields.
   - Do not infer age from non-age metrics.
   - Do not backfill from age objectives.

2. Canonical public contract targets for age fields:
   - `processed_data/public_contracts/hunt_application_outlook.json`
   - `processed_data/research_page/hunt_application_outlook.json`

3. Field stability check (2026-06-01):
   - Both contract targets contain both keys on all rows:
     - `average_harvest_age`
     - `current_age_3yr_average`
   - Row counts and nonblank counts are aligned across both targets:
     - rows: `2898`
     - nonblank `average_harvest_age`: `1268`
     - nonblank `current_age_3yr_average`: `440`

4. Non-canonical/stale copy warning:
   - `data/hunt_application_outlook.json` currently lags on `average_harvest_age` population (`1112` nonblank).
   - Treat this file as non-canonical until explicitly regenerated/synced.

## Source-Family Rules

- `Average Harvest Age` uses only: `ANNUAL_HARVEST_REPORT_AGE`, `UNIT_LEVEL_REPEATED_ANNUAL_AGE`, `FALLBACK_MERGED_AGE`.
- `Current Age (3-Yr Avg)` uses only: `HUNT_PLANNER_CURRENT_3YR_AVG` (from canonical 2026 DATABASE field `current_age_3yr_average`).
- `Age Objective` is not used for either column.
- Values `<= 0` are blanked.

## Species-by-Species Support Policy

| Species | Average Harvest Age Support | Current Age (3-Yr Avg) Support |
|---|---|---|
| Elk | SUPPORTED_UNIT_CROSSWALK | PARTIAL_SUPPORT |
| Black Bear | SUPPORTED_UNIT_CROSSWALK | NOT_SUPPORTED |
| Mountain Goat | PARTIAL_SUPPORT | NOT_SUPPORTED |
| Moose | SUPPORTED_UNIT_CROSSWALK | PARTIAL_SUPPORT |
| Pronghorn | SUPPORTED_UNIT_CROSSWALK | PARTIAL_SUPPORT |
| Deer | PARTIAL_SUPPORT | PARTIAL_SUPPORT |
| Desert Bighorn Sheep | PARTIAL_SUPPORT | NOT_SUPPORTED |
| Rocky Mountain Bighorn Sheep | PARTIAL_SUPPORT | NOT_SUPPORTED |
| Bison | NOT_SUPPORTED | NOT_SUPPORTED |
| Turkey | NOT_SUPPORTED | NOT_SUPPORTED |
| Cougar | NOT_SUPPORTED | NOT_SUPPORTED |

## Population Summary

- Rows audited: 2898
- Unique hunt codes audited: 1449
- Public `Average Harvest Age` populated rows: 1268
- Public `Current Age (3-Yr Avg)` populated rows: 440
- Canonical average-age code coverage: 634
- Canonical current-age code coverage: 219

### Blank Cause Breakdown (Average Harvest Age)

- MAPPING_FAILURE: 6
- SOURCE_MISSING: 1624

### Blank Cause Breakdown (Current Age 3-Yr Avg)

- MAPPING_FAILURE: 320
- NOT_SUPPORTED_FOR_SPECIES: 1260
- SOURCE_MISSING: 878

## Regenerated Sample Public Outputs

- `2026_BLACK_BEAR.xlsx`: UPDATED (rows=106, avg=96, current3yr=0)
- `2026_ELK_BULL_ALL.xlsx`: UPDATED (rows=353, avg=274, current3yr=143)
- `2026_DEER_BUCK_LIMITED_ENTRY.xlsx`: UPDATED (rows=67, avg=0, current3yr=0)

## Remaining Gaps

- Species and hunt families without defensible annual age evidence remain blank by design.
- Rows marked `JOIN_FAILURE` or `MAPPING_FAILURE` indicate pipeline alignment work still needed for fully consistent public rendering.

## Future Source Expansion (Species-By-Species Only)

- Expand only when a known, defensible missing source family can be added cleanly.
- Priority order by supportability:
  - Deer: expand annual harvest-report age-table extraction at unit/hunt crosswalk level.
  - Pronghorn: expand annual harvest-report age extraction and crosswalk coverage.
  - Moose: improve direct hunt-code annual age extraction beyond unit-level repeats.
  - Mountain Goat: add/normalize annual age tables already present in yearly species reports.
  - Bighorn (Desert/Rocky): improve annual report age-table extraction/crosswalk where evidence exists.
  - Black Bear: continue annual age-table standardization where available; keep 3-year field separate.
- Keep as not-supported until new defensible source family is added:
  - Bison
  - Turkey
  - Cougar
