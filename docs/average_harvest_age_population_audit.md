# average_harvest_age Population Audit

Generated: 2026-06-01 (America/Denver)

## 1. Scope and file purpose
- Focused audit of `average_harvest_age` population in public hunt table exports.
- Audited exports:
  - `processed_data/research_page/hunt_application_outlook.json` (upstream public hunt table surface)
  - `processed_data/public_contracts/hunt_application_outlook.json` (public contract export)

## 2. Pipeline path populating average_harvest_age
- Primary population script: `scripts/build-hunt-research-classification-layer.js`
- Contract pass-through script: `scripts/build-public-data-contracts.js`
- Current age population order in upstream builder:
  1. direct hunt-code age from base/master/database/ladder context where present
  2. direct hunt-code harvest age (`average_age`) from harvest quality feed
  3. direct hunt-code reviewed age feed (`harvest_average_age_global_merge_database.csv`)
  4. **repair added in this task**: strict unit+species fallback from latest-year harvest age when direct values are blank and unit-level evidence is stable

## 3. Source lineage status (current export)
- Total rows: `2898`
- Rows with populated `average_harvest_age`: `1268`
- Rows blank: `1630`
- Unique hunt codes: `1449`
- Unique hunt codes with blank age: `815`
- Direct hunt-code source rows: `1112`
- Unit-level repeated source rows: `156`
- Management-unit-level source rows: `0`
- Unavailable rows: `0`

## 4. Blank classification (required categories)
- SOURCE_MISSING: `1616`
- MAPPING_FAILURE: `0`
- JOIN_FAILURE: `0`
- VALIDATION_BLOCK: `0`
- INTENTIONAL_BLANK: `14`
- Blank rows with harvest success and/or avg days hunted populated (likely should have age if evidence exists): `1430`

## 5. Repair performed
- Repaired a valid upstream mapping defect in `scripts/build-hunt-research-classification-layer.js`:
  - Added strict unit+species fallback for `average_harvest_age` only when:
    - direct hunt-code age is blank
    - latest-year unit+species age evidence exists
    - latest-year age values are stable (spread <= 0.2)
- Preserved guardrails:
  - no invented ages
  - no loose fuzzy inference
  - no `DATABASE.csv` truth edits
  - no prediction math edits

## 6. Repair outcome
- Previous nonblank rows (HEAD baseline): `1112`
- Current nonblank rows: `1268`
- Delta: `+156 nonblank rows`
- Previous blank rows (HEAD baseline): `1786`
- Current blank rows: `1630`

## 7. Required regenerated sample public output
- Regenerated upstream public hunt table output:
  - `processed_data/research_page/hunt_application_outlook.json`
- Regenerated public contract output derived from it:
  - `processed_data/public_contracts/hunt_application_outlook.json`

## 8. Notes
- Remaining blanks are dominated by `SOURCE_MISSING` (no direct or safe unit-level age evidence under current strict rules).
- No direct-hunt-code join failures remained after this pass (`JOIN_FAILURE = 0`).
