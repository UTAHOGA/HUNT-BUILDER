# Draw Results Year And Model Year Semantics

## Purpose

This document defines the year terminology used across Hunt Builder draw-result, permit-result, hunt-code lifecycle, and prediction-modeling work.

## Canonical Rule

For `BIBLE HUNT CODES` source packages:

```text
BIBLE HUNT CODES/YYYY = draw_results_year YYYY
draw_results_year = year the permits were drawn and the results were reported
permit_draw_year = draw_results_year
model_year = draw_results_year + 1
```

Example:

```text
C:\Users\tyler\Desktop\BIBLE HUNT CODES\2021.zip
draw_results_year = 2021
permit_draw_year = 2021
model_year = 2022
```

## Field Meanings

| Field | Meaning |
|---|---|
| `draw_results_year` | Actual year the draw results were reported for. |
| `permit_draw_year` | Actual year the permits in the result source were drawn. For these draw-result packages, this equals `draw_results_year`. |
| `report_year` | Legacy/short audit name for `draw_results_year`; use `draw_results_year` in new outputs where practical. |
| `reported_hunt_year` | Year the hunt/draw/harvest event occurred. For draw-result ledgers, this is the same year family as `draw_results_year` unless a source proves otherwise. |
| `model_year` | Predictive modeling year that consumes the historical draw results. Usually `draw_results_year + 1`. |
| `model_target_year` | Same concept as `model_year` in older pipeline outputs. |
| `source_model_year_label` | Filename text such as `PERMITS=2022_MODEL`; preserve as source evidence only. |
| `source_file` | The actual source filename/path and its original year labels. |

## Filename Label Rule

Filename fragments such as:

```text
PERMITS=2022_MODEL
PERMITS=2021_MODEL
2025_for_2026_modeling
```

are not allowed to override the reviewed year rule by themselves.

They should be stored as source-label evidence, then compared against:

```text
model_year = draw_results_year + 1
```

If a filename label disagrees with the reviewed rule, preserve the filename label and flag it for review rather than silently adopting it.

## Website And Public Wording

Public-facing wording should avoid ambiguous labels like `2025 permits` unless the year context is explicit.

Preferred labels:

- `2025 Draw Results`
- `2025 Permit Draw Results`
- `2025 Draw Results Used For 2026 Modeling`
- `Current 2026 Permit Allotment`

Avoid:

- `2025 permits` without context
- `2026 permits legacy`
- `model permits` without a draw-results year

## Required Audit Columns

New year-by-year draw-result or hunt-code identity outputs should include these columns where applicable:

```text
draw_results_year
permit_draw_year
model_year
source_model_year_label
source_file
source_page
hunt_code
```

Existing outputs that use `report_year` remain valid, but new work should either add `draw_results_year` or clearly document that `report_year = draw_results_year`.

## Non-Goals

This rule does not change `DATABASE.csv` values.

This rule does not promote historical values into current-year permit allotments.

This rule does not make source filename labels authoritative when they conflict with reviewed source-year logic.
