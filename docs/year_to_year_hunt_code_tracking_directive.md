# Year-To-Year Hunt Code Tracking Directive

This directive governs historical hunt-code library work across draw years.

Do not guess. Do not silently rename, merge, or drop hunt codes. Track each hunt family year by year with explicit provenance.

## Primary Goal

Build and maintain one structured year document for every draw year so hunt codes can be followed forward and backward across years and reconciled against current truth sources.

## Required Core Fields

Every structured year document must include at minimum:

- `hunt_name`
- `hunt_code`
- `sex_type`
- `species`
- `weapon`
- `hunt_type`
- `season`
- `permits_res`
- `permits_nr`
- `permits_total`

## Standard Provenance And Crosswalk Fields

Every structured year document must also include:

- `draw_year`
- `model_year`
- `source_file`
- `source_type`
- `source_priority`
- `family_group`
- `current_or_historical`
- `unit_name`
- `season_type`
- `season_dates`
- `is_grouped_master_file`
- `derived_from_master_file`
- `current_active_code`
- `historical_code`
- `crosswalk_status`
- `notes`

## Field Definitions

- `draw_year`: year permits were actually drawn.
- `model_year`: following year the file informs.
- `source_file`: exact file name used.
- `source_type`: one of `truth_source_pdf`, `extracted_pdf`, `structured_xlsx`, `structured_csv`, or `current_database`.
- `source_priority`: lower number means stronger authority.
- `family_group`: one of `LE`, `OIL`, `ANTLERLESS`, `YOUTH`, `SPORTSMAN`, `TURKEY`, `BEAR`, `COUGAR_HISTORICAL`, `COUGAR_SUCCESSOR`, or `GENERAL_SEASON`.
- `current_or_historical`: `CURRENT` or `HISTORICAL`.
- `season_type`: verified label such as `early`, `mid`, `late`, `multi-season`, `extended`, `statewide`, `unlimited`, `point-only`, or `other`.
- `is_grouped_master_file`: `yes` or `no`.
- `derived_from_master_file`: exact parent file when applicable.
- `current_active_code`: active current code if crosswalked.
- `historical_code`: historical code if row is from an older source.
- `crosswalk_status`: one of `EXACT_MATCH`, `RENAMED_MATCH`, `STRUCTURE_CHANGED`, `HISTORICAL_ONLY`, `CURRENT_ONLY`, or `NEEDS_MANUAL_REMAP`.
- `notes`: explanation of ambiguity, source conflict, or rule exception.

## Source Hierarchy

Use sources in this order:

1. Official published truth-source PDF for that year/family.
2. Clean extracted section PDF cut from the truth-source PDF.
3. Structured XLSX/CSV created directly from the official PDF.
4. Current active database for current-state code comparison.
5. Prior normalized helper files.

If sources disagree, the official PDF wins and derived files must be corrected to match.

## Year-By-Year Method

For each `draw_year`:

1. Identify every file family present.
2. Identify grouped master files versus subset files.
3. Extract or verify subset families.
4. Build one structured year workbook/tab/document with one row per hunt code.
5. Preserve exact historical hunt codes.
6. Compare to the previous year.
7. Compare to the next year if available.
8. Compare to the current active database if needed.
9. Mark `crosswalk_status` for every row.
10. Record all exceptions in `notes`.

## Hunt Code Tracking Rules

- Never delete a historical code just because it no longer exists in a later year.
- Never assume a renamed hunt is a new hunt until species, sex type, weapon, hunt name, and season context are checked.
- Treat unit splits, unit merges, statewide conversions, and unlimited permits as structure changes, not simple renames.
- Preserve one row per actual published hunt code.
- If a master file contains multiple families, do not count the master file itself as a duplicate family row set.
- If a subset file is derived from a master file, record that provenance.

## Comparison Rules

When comparing year to year, test in this order:

1. Exact `hunt_code` match.
2. Same `hunt_name` plus `species`, `sex_type`, and `weapon`.
3. Same `species`, `sex_type`, and `weapon` plus near-identical unit or hunt wording.
4. Official crosswalk or current database mapping.
5. If still unclear, mark `NEEDS_MANUAL_REMAP`.

## Permit Number Rules

- `permits_res` means resident permits only.
- `permits_nr` means nonresident permits only.
- `permits_total` means resident plus nonresident unless the official source explicitly states another total.
- If a source is unlimited, record `unlimited` in `notes` and set permit fields consistently per project rule.
- If a continuation row exists, such as `nonres: xx`, normalize it into `permits_nr` before comparison.

## Naming Logic

Interpret filenames with both years:

```text
DRAWYEAR_PERMITS=MODELYEAR_MODEL__DOCUMENT NAME
```

Example:

```text
2025_PERMITS=2026_MODEL__L.E. DEER DRAW RESULTS.pdf
```

Do not infer year meaning from folder alone when the filename supplies the reviewed year labels.

## Special Rules

- Cougar historical local draw tables end at `2022_PERMITS=2023_MODEL`.
- After that, cougar moves to statewide successor handling and should not be flagged missing as a local table family.
- Sportsman files are one-page odd-format tables and should be converted into clean structured spreadsheets for ingestion.
- Youth elk may appear under naming variants; verify by content before treating as missing.
- Moose naming may vary between `LIMITED ENTRY MOOSE`, `BULL MOOSE`, and `O.I.L. BULL MOOSE`; treat as the same family only when source content proves it.

## Required Outputs For Each Year

Produce:

1. One structured workbook or CSV with all hunt-code rows for the year.
2. One missing/extra family report versus adjacent year.
3. One crosswalk report for changed or successor codes.
4. One notes log of ambiguities and manual decisions.
5. One validation summary.

## Validation Checklist

Before closing a year, verify:

- all expected families are accounted for
- master/subset relationships are documented
- no duplicate hunt-code rows exist
- no codes were silently dropped
- permit numbers are reconciled
- current/historical status is marked
- `crosswalk_status` is populated
- `notes` is populated where needed

## Non-Negotiables

- Do not guess.
- Do not overwrite historical codes.
- Do not normalize away meaningful differences.
- Do not silently change hunt names or permit counts.
- If uncertain, preserve both interpretations and flag `NEEDS_MANUAL_REMAP`.
