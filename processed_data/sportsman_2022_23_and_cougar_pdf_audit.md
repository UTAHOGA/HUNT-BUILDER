# Sportsman 2022-23 Normalization And Cougar PDF Audit

This pass uses the reviewed sportsman table text supplied by Tyler and audits the local cougar PDF without promoting ambiguous year-labeled cougar rows.

## Sportsman

- Rows normalized: `11`
- Total applications: `57199`
- Total quota: `11`
- Codes missing current `DATABASE.csv`: `1`

## Cougar PDF

- Cougar codes found: `9`
- Codes already in global draw long table: `9`
- Codes in current `DATABASE.csv`: `0`
- Year status: `FILENAME_2023_BUT_PDF_TEXT_2022_DRAW_AND_COUGAR_2022_2023`

## Sportsman Codes

`BI1000`, `BR1000`, `CG1000`, `DB0007`, `DS1000`, `EB1000`, `GO1000`, `MB1000`, `PB1000`, `RS0001`, `TK0001`

## Cougar Codes

`CG1029`, `CG1034`, `CG7502`, `CG7506`, `CG7602`, `CG7603`, `CG7605`, `CG7610`, `CG7612`

## Guardrail

Sportsman rows are normalized from reviewed table text into a source artifact only. Cougar PDF rows are lineage evidence only because the filename and report text disagree. No DATABASE.csv, runtime feed, website file, or global draw truth table was modified.
