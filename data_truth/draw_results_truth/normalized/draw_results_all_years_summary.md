# Draw Results All Years Cumulative Truth

This validation layer finalizes the cumulative draw-results truth table without rewriting the runtime long CSV.

## Validation

- Rows: 176753
- Unique draw years: 2021, 2022, 2023, 2024, 2025, 2026
- Unique hunt codes: 1616
- Source audit rows: 50
- Blank hunt-code rows: 0
- Invalid year rows: 0
- Duplicate draw-result keys: 0
- Blockers: 0

## Draw Year Counts

- 2021: 27519
- 2022: 18688
- 2023: 17128
- 2024: 37128
- 2025: 75194
- 2026: 1096

## Guardrails

- Draw year is treated as reported_hunt_year_inferred for historical draw-result rows.
- Model target year is draw/result year + 1 for predictive alignment summaries.
- This validation layer does not rewrite current hunt codes or probability math.
