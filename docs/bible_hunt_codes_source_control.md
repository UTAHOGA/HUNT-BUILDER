# BIBLE HUNT CODES / Hunt Engine Source Control

This document locks the handling rules for `C:\Users\tyler\Desktop\BIBLE HUNT CODES`.

Codex must preserve the established naming logic, year logic, source hierarchy, and family structure. Do not invent alternate structure.

## Draw Year And Model Year

Every file must be interpreted with two years:

- `draw_year`: the year permits were actually drawn.
- `model_year`: the next year this file is intended to inform or predict.

Canonical filename pattern:

```text
DRAWYEAR_PERMITS=MODELYEAR_MODEL__DOCUMENT NAME.pdf
```

Example:

```text
2025_PERMITS=2026_MODEL__ANTLERLESS DRAW RESULTS.pdf
```

Folder placement rule:

- Files live in the folder for `draw_year`.
- The engine must use `model_year` as the prediction/forward-use year.
- Do not infer `model_year` from folder alone when the filename supplies both years.

## Folder Purpose

`BIBLE HUNT CODES` is a historical/reference library. Treat it as:

- canonical year-by-year hunt-code lookup library
- naming-normalized source archive
- crosswalk reference for hunt code, hunt family, species, weapon, and section structure

Do not assume every file in this folder is active current-state runtime truth.

Primary uses:

- historical reference
- source auditing
- cross-year comparison
- feed preparation

## Required Naming Convention

Preferred naming baseline is the cleaned 2025 style.

Rules:

- Use spaces, not underscores, in document names.
- Keep the prefix `DRAWYEAR_PERMITS=MODELYEAR_MODEL__`.
- `GENERAL-SEASON` must normalize to `G.S.`.
- `DEDICATED HUNTER` must normalize to `D.H.`.
- `LIMITED ENTRY` must normalize to `L.E.`.
- O.I.L. species must be explicitly labeled `O.I.L.`.
- Result-family files should end in `DRAW RESULTS`.

Examples:

```text
2025_PERMITS=2026_MODEL__L.E. DEER DRAW RESULTS.pdf
2025_PERMITS=2026_MODEL__L.E. ELK DRAW RESULTS.pdf
2025_PERMITS=2026_MODEL__L.E. PRONGHORN DRAW RESULTS.pdf
2025_PERMITS=2026_MODEL__O.I.L. BISON DRAW RESULTS.pdf
2025_PERMITS=2026_MODEL__O.I.L. BULL MOOSE DRAW RESULTS.pdf
2025_PERMITS=2026_MODEL__O.I.L. DESERT BIGHORN SHEEP DRAW RESULTS.pdf
2025_PERMITS=2026_MODEL__O.I.L. ROCKY MTN SHEEP DRAW RESULTS.pdf
2025_PERMITS=2026_MODEL__O.I.L. MTN GOAT DRAW RESULTS.pdf
2025_PERMITS=2026_MODEL__L.E. BIG GAME DRAW RESULTS.pdf
2025_PERMITS=2026_MODEL__O.I.L. DRAW RESULTS.pdf
```

Do not create alternate naming variants once a preferred name exists.

## File Family Logic

Expected L.E. subsection families:

- `L.E. DEER DRAW RESULTS`
- `L.E. ELK DRAW RESULTS`
- `L.E. PRONGHORN DRAW RESULTS`

Expected O.I.L. subsection families:

- `O.I.L. BISON DRAW RESULTS`
- `O.I.L. BULL MOOSE DRAW RESULTS`
- `O.I.L. DESERT BIGHORN SHEEP DRAW RESULTS`
- `O.I.L. ROCKY MTN SHEEP DRAW RESULTS`
- `O.I.L. MTN GOAT DRAW RESULTS`

Comprehensive comparison files:

- `L.E. DRAW RESULTS`
- `O.I.L. DRAW RESULTS`

Master umbrella big-game file:

- `L.E. BIG GAME DRAW RESULTS`

If a year has a master big-game file, use it to derive/check subset files. If subset files exist, they must reconcile back to comprehensive files. Comprehensive files are validation/cross-check sources, not a substitute for preserving subset files.

## Truth Source Hierarchy

When building engine feeds or dependent databases, use this priority order:

1. Tier 1: direct truth-source PDF for that family/year, especially original published reports, master big-game truth-source PDFs, and one-page official tables.
2. Tier 2: clean extracted subset PDFs derived from the truth-source, only when cut from the correct master PDF with verified section boundaries.
3. Tier 3: normalized library copies, acceptable for lookup/reference but not preferred over direct truth-source if there is a discrepancy.
4. Tier 4: derived CSV/XLSX helper files, only when they are faithful structured extraction of an official PDF and never overriding the official PDF.

If sources disagree, the official published PDF wins and the derived file must be corrected.

## Hunt Engine Feed Rules

The hunt engine must not blindly ingest every PDF in `BIBLE HUNT CODES`.

Structured year documents and adjacent-year comparisons must follow:

```text
docs/year_to_year_hunt_code_tracking_directive.md
```

Master JSON integration of those year documents must follow:

```text
docs/master_json_integration_directive.md
```

Preferred engine feed units:

- one normalized family file per draw family/year
- or a clean extracted CSV/XLSX generated directly from the family PDF

Required feed metadata fields:

- `draw_year`
- `model_year`
- `document_family`
- `source_role`
- `source_file`
- `is_truth_source`
- `is_derived`
- `derived_from_file`
- `family_group`
- `current_or_historical`

Additional engine feed fields should include:

- `source_family`
- `hunt_code`
- `hunt_name`
- `species`
- `weapon`
- permit/result fields
- `source_priority`

Allowed `family_group` examples:

- `LE_SUBSET`
- `OIL_SUBSET`
- `LE_MASTER`
- `OIL_MASTER`
- `GENERAL_SEASON`
- `YOUTH`
- `SPORTSMAN`
- `TURKEY`
- `BEAR`
- `COUGAR_HISTORICAL`
- `COUGAR_SUCCESSOR`

Allowed `source_role` examples:

- `truth_source_pdf`
- `extracted_subset_pdf`
- `comprehensive_check_pdf`
- `structured_extract_xlsx`
- `structured_extract_csv`

## Dependent Database Rules

Dependent databases must separate:

- historical family evidence
- current active code truth
- normalized lookup/crosswalk

Maintain at least these concepts:

- `historical_source_library`
- `normalized_family_feed`
- `current_active_database`
- `hunt_code_crosswalk`
- `engine_runtime_inputs`

Historical rows should preserve old unit-level codes even when the current database has moved on. Current active database should reflect the current official active structure.

## Cougar Rule

Historical local cougar draw results continue through:

```text
2022_PERMITS=2023_MODEL
```

After that, cougar no longer uses the old local draw-results family structure.

Successor structure:

- Hunt code: `CG9999`
- Hunt name: `Cougar - Statewide`
- Sex: `Either Sex`
- Species: `Cougar`
- Weapon: `Any Legal Weapon`
- Unit: `Statewide`
- Permits: `Unlimited`

Therefore:

- `COUGAR DRAW RESULTS` is expected only through `2022_PERMITS=2023_MODEL`.
- After that, do not flag missing local cougar draw-results files.
- Map forward to the statewide successor structure.
- Sportsman Cougar rows are part of the `SPORTSMAN` report family, not the local cougar draw-results family. If a clean sportsman source provides `CG1000` or another Sportsman Cougar row, preserve that row with sportsman provenance and do not treat it as discontinued merely because the current cougar structure is statewide.

## Sportsman Rule

Sportsman is a mixed-year style report, but for file management:

- Place it in the `draw_year` folder.
- File name follows `DRAWYEAR_PERMITS=MODELYEAR_MODEL__SPORTSMAN DRAW RESULTS.pdf`.

Sportsman files are one-page/odd-format tables. Prefer clean structured XLSX/CSV extracts generated directly from the PDF. Do not let OCR garbage or line breaks create broken rows.

## Known Special Cases

- Youth Elk naming variants such as `YOUTH DRAW-ONLY ELK DRAW RESULTS` and `YOUTH ELK DRAW RESULTS` are the same family unless source evidence proves otherwise.
- Moose naming variants such as `LIMITED ENTRY MOOSE`, `BULL MOOSE`, and `O.I.L. BULL MOOSE` are the same O.I.L. moose family unless source evidence proves otherwise.
- `L.E. AND O.I.L. DRAW RESULTS` may be a combined master-style comparison file, not a distinct family. Do not duplicate its contents into separate family counts unless intentionally derived.

## Prohibited Actions

Do not:

- invent missing hunt families
- rename files unless they violate the established convention
- merge family files without recording provenance
- treat current database rows as proof historical source files were wrong
- replace official PDFs with guessed CSV values
- silently drop pages or first-page cover sections
- assume one weird file is correct because its name looks cleaner

When ambiguous:

- report it
- preserve both possibilities
- identify which file is truth source and which is derived

## Required Outputs When Cleaning A Year

For each cleaned year, produce:

1. normalized PDF inventory
2. family inventory table
3. truth-source vs derived-source manifest
4. missing/extra family report
5. crosswalk report if any family changed naming or structure
6. clean structured XLSX/CSV for odd-format or one-page reports
7. comprehensive L.E. and O.I.L. comparison files where applicable

## Validation Checklist

Before saying a year is complete, verify:

- `draw_year`/`model_year` naming is correct
- no underscore-heavy leftover naming where spaces should be used
- subset files reconcile to comprehensive files
- master file section boundaries are correct
- no mis-cut fragments at beginning/end of section PDFs
- no duplicate family files with conflicting names
- one-page reports are structured cleanly for Codex ingestion
- cougar logic follows historical cutoff and statewide successor mapping
- youth elk is not lost under generic youth naming
- sportsman rows are extracted cleanly without broken wrapped lines

## Operational Default

If uncertain:

- prefer official PDF truth source
- preserve provenance
- normalize names only, not substance
- never guess hunt-family equivalence without documenting it
