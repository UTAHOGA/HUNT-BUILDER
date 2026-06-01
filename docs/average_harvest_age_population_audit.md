# average_harvest_age Source Family + Label Accuracy Audit

Generated: 2026-06-01T09:38:36.920021

## 1. Current public export source usage
Audited current export: `processed_data/public_contracts/hunt_application_outlook.json` (with upstream lineage from `processed_data/research_page/hunt_application_outlook.json`).

Source family counts:
- ANNUAL_HARVEST_REPORT_AGE: 974
- UNIT_LEVEL_REPEATED_ANNUAL_AGE: 156
- FALLBACK_MERGED_AGE: 138
- HUNT_PLANNER_CURRENT_3YR_AVG: 6
- SOURCE_MISSING: 1624

Interpretation:
- The export age value is primarily annual-harvest-report based (direct + repeated + annual-derived merged fallbacks).
- Hunt Planner 3-year age is separate context (`current_age_3yr_average`) and not the primary source for the export age field.

## 2. Label accuracy: "Average Harvest Age Prior Year"
Assumption: 2026 contract context => "prior year" = reported hunt year 2025.

Among populated age rows (1268):
- ACCURATE: 0
- NOT_ACCURATE: 904
- UNKNOWN: 364

Conclusion:
- "Average Harvest Age Prior Year" is **not generally accurate** for this export.
- Recommended label: **"Verified Harvest Age (Most Recent Annual Report)"**.

## 3. Valid annual data loss check
- Join status: {'NO_DIRECT_ANNUAL_SOURCE': 1630, 'JOIN_SUCCESS': 1268}
- Mapping status: {'NO_UNIT_LEVEL_ANNUAL_SOURCE': 1630, 'MAPPING_SUCCESS': 156, 'NOT_NEEDED': 1112}
- Validation status: {'NO_VALIDATED_AGE': 1630, 'PASS': 1268}
- Rows with direct annual evidence but blank export age (`JOIN_FAILURE`): 0 rows / 0 hunt codes.

Conclusion:
- No direct annual-report age loss found in current join path (0 join failures with valid direct annual evidence).

## 4. Coverage vs harvest success / avg days
- Total rows: 2898
- Blank export age rows: 1630
- Blank age rows with harvest success and/or avg days present: 1430

## 5. EB3038 sample comparison
[
  {
    "residency": "Resident",
    "public_export_value_average_harvest_age": "6",
    "annual_harvest_report_age_value": 6.0,
    "annual_harvest_report_reported_hunt_year": 2024,
    "hunt_planner_current_3yr_avg": "6.3",
    "upstream_age_source_file": "",
    "upstream_harvest_source_file": "2026-03-06-2025-preliminary-bg-harvest.pdf"
  },
  {
    "residency": "Nonresident",
    "public_export_value_average_harvest_age": "6",
    "annual_harvest_report_age_value": 6.0,
    "annual_harvest_report_reported_hunt_year": 2024,
    "hunt_planner_current_3yr_avg": "6.3",
    "upstream_age_source_file": "",
    "upstream_harvest_source_file": "2026-03-06-2025-preliminary-bg-harvest.pdf"
  }
]

## 6. Recommendation
- Keep export `average_harvest_age` annual-report based.
- Keep Hunt Planner 3-year age in separate field (`current_age_3yr_average`), not as replacement.
- If any UI/export label currently says "Prior Year", relabel to "Most Recent Annual Report".
