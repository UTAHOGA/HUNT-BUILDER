# Draw Results Truth Official Table Schema

This document defines the durable truth shape for Utah DWR draw-result data.

The goal is not to redesign Utah DWR's system. The goal is to represent the
official DWR draw-results table shape faithfully in canonical truth files.

## Official Source Shape

Utah DWR draw-result reports present one hunt table with:

- one hunt header
- one point ladder
- resident applicant and permit columns on the left
- nonresident applicant and permit columns on the right
- a shared point level row when both resident and nonresident data exist
- a totals row at the bottom

Therefore durable truth files should not use separate resident and nonresident
rows as their primary shape. Separate residency rows are a parser artifact and
belong only in temporary extraction/audit files.

## Canonical Row Identity

Canonical draw-result rows are keyed by the DWR table row, not by residency.

Primary row identity:

- `actual_draw_year`
- `model_target_year`
- `source_file`
- `hunt_code`
- `points`
- `record_type`
- `hunt_type`
- `draw_design`
- `weapon`
- `season`

Resident and nonresident values live in separate columns on that same row.

## Required Front Columns

Canonical yearly files and long/master/research feeds should use these columns
first where applicable:

- `actual_draw_year`
- `model_target_year`
- `boundary_id`
- `hunt_code`
- `hunt_name`
- `sex_type`
- `species`
- `hunt_type`
- `weapon`
- `season`
- `draw_design`
- `points`
- `record_type`

## DWR Table Metric Columns

Resident side:

- `resident_eligible_applicants`
- `resident_bonus_permits`
- `resident_regular_permits`
- `resident_total_permits`
- `resident_success_ratio`
- `resident_p_draw`
- `resident_p_draw_percent`

Nonresident side:

- `nonresident_eligible_applicants`
- `nonresident_bonus_permits`
- `nonresident_regular_permits`
- `nonresident_total_permits`
- `nonresident_success_ratio`
- `nonresident_p_draw`
- `nonresident_p_draw_percent`

Optional combined values:

- `total_eligible_applicants`
- `total_bonus_permits`
- `total_regular_permits`
- `total_permits`

## Year Permit Columns

Keep every year-specific permit set in the multi-year long file:

- `permits_2019_res`, `permits_2019_nr`, `permits_2019_total`
- `permits_2020_res`, `permits_2020_nr`, `permits_2020_total`
- `permits_2021_res`, `permits_2021_nr`, `permits_2021_total`
- `permits_2022_res`, `permits_2022_nr`, `permits_2022_total`
- `permits_2023_res`, `permits_2023_nr`, `permits_2023_total`
- `permits_2024_res`, `permits_2024_nr`, `permits_2024_total`
- `permits_2025_res`, `permits_2025_nr`, `permits_2025_total`
- `permits_2026_res`, `permits_2026_nr`, `permits_2026_total`

The yearly canonical file for a single year may include only that year's permit
set, plus source/audit fields.

## Source And Audit Columns

Canonical rows should retain enough source metadata to trace back to raw truth:

- `source_scope`
- `source_namespace`
- `draw_source_namespace`
- `source_file`
- `pdf_page`
- `page_kind`
- `source_dataset`
- `extraction_status`
- `parse_method`
- `qa_status`
- `algorithm_status`
- `notes`

## File-Class Rule

Parser scratch may be residency-split.

Durable truth should be DWR-table-shaped.

Public, master, enriched, ladder, research JSON, and prediction feeds should
derive from the DWR-table-shaped truth unless a source-specific audit explicitly
requires preserving split parser rows.
