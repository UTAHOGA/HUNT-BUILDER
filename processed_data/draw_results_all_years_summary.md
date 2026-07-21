# Draw Results All Years Cumulative Truth

This validation layer finalizes the cumulative draw-results truth table without rewriting the runtime long CSV.

## Validation

- Rows: 341970
- Unique draw years: 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026
- Unique hunt codes: 1544
- Source audit rows: 201
- Blank hunt-code rows: 0
- Invalid year rows: 0
- Duplicate draw-result keys: 39667
- Blockers: 1

## Draw Year Counts

- 2017: 29503
- 2018: 31031
- 2019: 33478
- 2020: 33370
- 2021: 33788
- 2022: 34876
- 2023: 35834
- 2024: 43175
- 2025: 38120
- 2026: 28795

## Guardrails

- Draw year is treated as reported_hunt_year_inferred for historical draw-result rows.
- Model target year is draw/result year + 1 for predictive alignment summaries.
- This validation layer does not rewrite current hunt codes or probability math.
