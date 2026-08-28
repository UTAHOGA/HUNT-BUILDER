# Draw Results All Years Cumulative Truth

This validation layer finalizes the cumulative draw-results truth table without rewriting the runtime long CSV.

## Validation

- Rows: 309562
- Unique draw years: 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026
- Unique hunt codes: 1494
- Source audit rows: 195
- Blank hunt-code rows: 0
- Invalid year rows: 0
- Coarse-key collisions across all source scopes: 29247
- Cross-scope-only collisions: 29247
- Unresolved same-source identity collisions: 0
- Blockers: 0

## Draw Year Counts

- 2018: 28427
- 2019: 33478
- 2020: 33069
- 2021: 33788
- 2022: 34876
- 2023: 35834
- 2024: 43175
- 2025: 38120
- 2026: 28795

## Guardrails

- Draw year is treated as reported_hunt_year_inferred for historical draw-result rows.
- Model target year is draw/result year + 1 for predictive alignment summaries.
- Cross-scope records remain distinct official evidence and are not silently merged.
- This validation layer does not rewrite current hunt codes or probability math.
