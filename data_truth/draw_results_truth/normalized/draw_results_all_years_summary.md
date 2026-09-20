# Draw Results All Years Cumulative Truth

This validation layer finalizes the cumulative draw-results truth table without rewriting the runtime long CSV.

## Validation

- Rows: 338574
- Unique draw years: 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026
- Unique hunt codes: 1544
- Source audit rows: 155
- Blank hunt-code rows: 0
- Invalid year rows: 0
- Coarse-key collisions across all source scopes: 11111
- Cross-scope-only collisions: 11111
- Unresolved same-source identity collisions: 0
- Blockers: 0

## Draw Year Counts

- 2017: 26310
- 2018: 31031
- 2019: 33478
- 2020: 33363
- 2021: 33789
- 2022: 34876
- 2023: 36507
- 2024: 37158
- 2025: 39228
- 2026: 32834

## Guardrails

- Draw year is treated as reported_hunt_year_inferred for historical draw-result rows.
- Model target year is draw/result year + 1 for predictive alignment summaries.
- Cross-scope records remain distinct official evidence and are not silently merged.
- This validation layer does not rewrite current hunt codes or probability math.
