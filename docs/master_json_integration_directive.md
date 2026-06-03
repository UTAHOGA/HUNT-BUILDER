# Master JSON Integration Directive

This directive governs integration of cleaned year-by-year hunt-code data into the master JSON layer.

Do not guess. Do not overwrite historical meaning. Do not silently collapse distinct hunt codes. Preserve provenance for every inserted or updated row.

## Primary Goal

Integrate normalized yearly hunt-code records into the master JSON so downstream systems can use:

- historical year tracking
- current active code comparison
- permit-count reconciliation
- crosswalk and successor logic

The integration layer must preserve original source meaning.

## Master JSON Principle

The master JSON is not just a row dump. It is the canonical structured integration layer.

It must preserve:

- source-year truth
- current active code mapping
- historical continuity
- family grouping
- permit-count reconciliation
- successor rules

Never reduce it to one flat record if multiple meanings must be preserved.

## Required Record Identity

Each record must be uniquely identified by at least:

- `draw_year`
- `model_year`
- `hunt_code`
- `source_file`

If the same `hunt_code` appears in different years, those are separate historical records. Do not overwrite prior-year rows.

Recommended stable key:

```text
record_key = "{draw_year}|{hunt_code}|{source_file}"
```

If the same hunt code appears more than once in the same year because of different source roles, preserve both only if they serve different purposes and mark them clearly.

## Required JSON Fields

Each record must include at minimum:

- `draw_year`
- `model_year`
- `hunt_name`
- `hunt_code`
- `sex_type`
- `species`
- `weapon`
- `hunt_type`
- `season`
- `season_type`
- `season_dates`
- `permits_res`
- `permits_nr`
- `permits_total`
- `source_file`
- `source_type`
- `source_priority`
- `family_group`
- `current_or_historical`
- `current_active_code`
- `historical_code`
- `crosswalk_status`
- `notes`

Recommended additional fields:

- `unit_name`
- `source_folder`
- `source_role`
- `is_truth_source`
- `is_derived`
- `derived_from_file`
- `derived_from_pages`
- `is_grouped_master_file`
- `parent_master_file`
- `validation_status`
- `permit_count_reconciled`
- `integration_timestamp`
- `integrated_by`

## Field Rules

- `draw_year`: year permits were actually drawn.
- `model_year`: next year the file informs.
- `hunt_name`: preserve official source wording unless a separate normalization layer is clearly defined.
- `hunt_code`: preserve exactly as published and always store as a string.
- `sex_type`: preserve from source or normalized lookup.
- `species`: preserve exact species-family meaning.
- `weapon`: preserve exact source wording unless verified normalization exists.
- `hunt_type`: examples include `limited entry`, `O.I.L.`, `general season`, `youth`, `sportsman`, `antlerless`, `permit-only`, and `unlimited`.
- `season`: human-readable season text if present.
- `season_type`: examples include `early`, `mid`, `late`, `multi-season`, `extended`, `statewide`, `unlimited`, and `point-only`.
- `season_dates`: exact date text when known.
- `permits_res`: resident permits only.
- `permits_nr`: nonresident permits only.
- `permits_total`: normally `permits_res + permits_nr`; if unlimited, record according to project rule and explain in `notes`.
- `source_file`: exact file name used for integration.
- `source_type`: one of `truth_source_pdf`, `extracted_subset_pdf`, `structured_xlsx`, `structured_csv`, `current_database`, or `crosswalk_reference`.
- `source_priority`: numeric authority ranking where lower number means stronger authority.
- `family_group`: examples include `LE_SUBSET`, `OIL_SUBSET`, `LE_MASTER`, `OIL_MASTER`, `GENERAL_SEASON`, `YOUTH`, `SPORTSMAN`, `TURKEY`, `BEAR`, `COUGAR_HISTORICAL`, and `COUGAR_SUCCESSOR`.
- `current_or_historical`: `CURRENT` or `HISTORICAL`.
- `current_active_code`: current mapped code if known.
- `historical_code`: original historical code if applicable.
- `crosswalk_status`: one of `EXACT_MATCH`, `RENAMED_MATCH`, `STRUCTURE_CHANGED`, `HISTORICAL_ONLY`, `CURRENT_ONLY`, or `NEEDS_MANUAL_REMAP`.
- `notes`: required for ambiguity, successor rules, structure changes, unlimited permits, or naming anomalies.

Recommended `source_priority` values:

- `1`: `truth_source_pdf`
- `2`: `extracted_subset_pdf`
- `3`: `structured_xlsx` or `structured_csv`
- `4`: `current_database`
- `5`: helper or reference file

## Source Hierarchy For Integration

When integrating, use this precedence:

1. Official truth-source PDF.
2. Clean extracted subset PDF cut from the truth-source PDF.
3. Clean structured XLSX/CSV built directly from the official PDF.
4. Current database for active-code mapping only.
5. Helper/reference files.

If two sources disagree:

- official PDF wins
- derived data must be corrected to match
- conflicting values must not be silently merged

## Preferred JSON Structure

Preferred top-level structure:

```json
{
  "metadata": {},
  "records": [],
  "crosswalks": [],
  "successor_rules": [],
  "validation_log": []
}
```

Use:

- `metadata`: schema version, last updated timestamp, source root, naming convention, and integration rules version.
- `records`: one object per integrated hunt/year/source row.
- `crosswalks`: explicit historical-to-current mappings; do not bury these only in notes.
- `successor_rules`: structural family transitions, especially cougar and other discontinued families.
- `validation_log`: warnings, unresolved mappings, years completed, and discrepancies found.

## Record Insertion Rules

When adding a new row:

- never delete prior-year rows
- append a new record if it is a new year or new source role
- update only if the same `record_key` already exists and the new source is higher priority or clearly corrected

When updating an existing row:

- preserve old values in a change log if the update changes substance
- do not overwrite permit counts without documenting why

## Permit Count Integration Rules

Permit fields must be normalized before insertion.

Rules:

- continuation rows like `nonres: xx` must be moved into `permits_nr`
- blank continuation rows should be deleted before integration
- `permits_total` should be recomputed as resident plus nonresident when both are numeric
- if source says unlimited, store according to project rule, note `unlimited`, and do not force a fake numeric total

Recommended helper flags:

- `permit_count_reconciled`
- `permit_count_source`

## Master File Versus Subset File Rule

If integrating from a master grouped PDF:

- do not insert one generic master row as if it were a hunt record
- insert the derived section rows or hunt rows from that master
- preserve `parent_master_file`

If integrating comprehensive files:

- use them for validation and cross-check
- do not use them as replacements for actual individual hunt rows

## Year-By-Year Integration Method

For each year:

1. Load the truth-source files.
2. Normalize file naming and year interpretation.
3. Extract hunt-level records.
4. Normalize permit counts.
5. Map `family_group`.
6. Map `current_active_code` where possible.
7. Apply successor rules.
8. Insert records into the master JSON.
9. Write validation log entries.
10. Save without deleting prior-year records.

## Cougar Successor Rule

Historical local cougar draw-results family ends at:

```text
2022_PERMITS=2023_MODEL
```

After that, do not expect local cougar draw-results family rows.

Successor record logic:

- `current_active_code = CG9999`
- `hunt_name = Cougar - Statewide`
- `sex_type = Either Sex`
- `species = Cougar`
- `weapon = Any Legal Weapon`
- `unit_name = Statewide`
- `permits_total = Unlimited`
- `family_group = COUGAR_SUCCESSOR`
- `crosswalk_status = STRUCTURE_CHANGED`

Do not flag post-2023 missing local cougar tables as missing data. Map them through `successor_rules`.

## Sportsman Rule

Sportsman files are one-page wrapped tables. Do not parse them as raw PDF text during integration if a clean XLSX/CSV exists.

Preferred integration source:

- cleaned sportsman XLSX/CSV derived from the official PDF

Store sportsman rows as regular hunt-code records with:

- `family_group = SPORTSMAN`
- `source_type = structured_xlsx` or `structured_csv`
- `source_priority = 3`
- `source_file = exact cleaned file name`
- `notes = derived from official one-page sportsman report`

## Validation Before Save

Before writing the master JSON:

- verify no duplicate `record_key` values
- verify `hunt_code` is stored as a string
- verify permit fields are in correct columns
- verify `permits_total` reconciles where numeric
- verify `current_active_code` does not overwrite `historical_code`
- verify `family_group` is assigned
- verify `crosswalk_status` is assigned
- verify successor rules are applied
- verify unresolved items are logged

## Prohibited Actions

Do not:

- flatten all years into one row per `hunt_code`
- overwrite historical codes with current codes
- delete rows because later years changed structure
- invent permit counts
- silently resolve ambiguous mappings
- treat master grouped files as hunt-level records
- let cleaned helper files override official PDFs
- drop notes for unusual cases

## Required Validation Log Entries

For every integration batch, write a validation log entry including:

- `draw_year`
- `files_used`
- `records_added`
- `records_updated`
- `discrepancies_found`
- `unresolved_count`
- `successor_rules_applied`
- `timestamp`

## Output Expectation

After integration:

- master JSON remains append-safe
- every historical row is traceable to source
- current active mappings are explicit
- structural transitions are documented
- downstream tools can filter by year, family, current code, or source confidence
