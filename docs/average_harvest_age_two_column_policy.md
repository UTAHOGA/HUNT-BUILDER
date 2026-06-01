# Average Harvest Age Two-Column Policy

## Final Definitions

- `Average Harvest Age`: observed harvested-age value from annual-report age evidence and validated carry-forward families.
- `Current Age (3-Yr Avg)`: Utah DWR Hunt Planner current three-year average age context value.

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

## Further Source Work Needed

- Expand reviewed annual-report age extraction for species currently classified as `REVIEW_REQUIRED` or `NOT_SUPPORTED`.
- Improve hunt-code join coverage where canonical values exist but public rows remain blank.
