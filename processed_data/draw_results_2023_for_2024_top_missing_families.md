# 2023 Draw Results For 2024 Modeling - Top Missing Families

This completion package normalizes the three focused 2023 draw-result source families supplied for the 2024 modeling/render year.

## Scope

- Reported draw year: `2023`
- Model target year: `2024`
- Long point-ladder rows normalized: `23286`
- Unique hunt-code permit rows: `489`
- Source total public draw permits: `6331`

## Family Counts

- `ANTLERLESS_BIG_GAME`: `204` hunt codes, `7344` ladder rows, `5458` public permits
- `LIMITED_ENTRY_DEER`: `189` hunt codes, `11718` ladder rows, `562` public permits
- `BLACK_BEAR`: `96` hunt codes, `4224` ladder rows, `311` public permits

## Validation

- Duplicate long row keys: `0`
- Duplicate permit rows: `0`
- Source row keys missing from existing global long table: `12064`
- Source hunt codes with no matching global key: `308`

## Source Hashes

- `2023 Antlerless big game draw results.pdf`: pages `209`, hash match `TRUE`, codes `204`
- `2023 DEER ODDS.pdf`: pages `190`, hash match `TRUE`, codes `189`
- `23_drawing_odds.pdf`: pages `100`, hash match `TRUE`, codes `96`

## Guardrail

This artifact normalizes 2023 draw-result sources for 2024 modeling without modifying DATABASE.csv, runtime feeds, website files, or the ambiguous global draw_results_long.csv.
