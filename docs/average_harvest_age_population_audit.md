# average_harvest_age Population Audit (Continuation)

Generated: 2026-06-01 (America/Denver)

## 1. Bottleneck test: stale primary source path
- Expected primary age source path: `processed_data/harvest_age_features_by_hunt_code_latest.csv`
- Primary path exists: `false`
- Runtime-resolved age source used by builder: `data_model/harvest_quality/harvest_average_age_global_merge_database.csv`
- Resolved path differs from stale primary: `true`

### Bottleneck quantification
- Current populated `average_harvest_age` rows: `1268`
- Current blank rows: `1630`
- Prior committed populated rows before this continuation: `1268`
- Delta after path repair: `0`
- Rows attributable to stale primary path as a completeness bottleneck: `0`

Conclusion: missing primary path is a **real configuration defect** but **not** the current completeness bottleneck because fallback source resolution preserves coverage (delta `0`).

## 2. Required blank-age cause breakdown
- SOURCE_MISSING: `1616`
- STALE_SOURCE_PATH: `0`
- JOIN_FAILURE: `0`
- MAPPING_FAILURE: `0`
- VALIDATION_BLOCK: `0`
- INTENTIONAL_BLANK: `14`

## 3. Coverage comparison vs harvest success and avg days hunted
- Total rows: `2898`
- Rows with age populated: `1268`
- Rows with age blank: `1630`
- Rows with harvest_success and/or avg_days_hunted populated while age is blank: `1430`

## 4. Defect repair applied (limited scope)
- Repaired stale primary source path in:
  - `scripts/build-hunt-research-classification-layer.js`
- Change:
  - `paths.age` now points to existing canonical file `data_model/harvest_quality/harvest_average_age_global_merge_database.csv`
  - stale path retained only as fallback candidate
- Regenerated sample export:
  - `processed_data/research_page/hunt_application_outlook.json`

## 5. Guardrails
- No DATABASE.csv edits.
- No broad pipeline refactor.
- No prediction/draw math changes.
