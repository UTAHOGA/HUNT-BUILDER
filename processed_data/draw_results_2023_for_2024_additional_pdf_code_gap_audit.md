# 2023 For 2024 Additional Draw PDF Code Gap Audit

This audit extracts hunt codes from the four supplied PDFs and checks whether those codes are already covered by the current 2023-for-2024 source artifacts, the global 2024 long table, and canonical `DATABASE.csv`.

## Results

- Unique hunt codes across supplied PDFs: `410`
- Missing from 2023-for-2024 source artifacts: `0`
- Missing from global 2024 long table: `32`
- Missing from `DATABASE.csv`: `24`

## Source Family Counts

- `ELK_AND_OTHER_BIG_GAME`: `392` codes; missing source-artifact `0`; missing global-2024 `14`
- `OIL_SPECIES_SUBSET`: `50` codes; missing source-artifact `0`; missing global-2024 `1`
- `SPORTSMAN`: `11` codes; missing source-artifact `0`; missing global-2024 `11`
- `TURKEY_BONUS`: `7` codes; missing source-artifact `0`; missing global-2024 `7`

## Missing From 2023-For-2024 Source Artifacts

None.

## Missing From Global 2024 Long Table

`BI1000`, `BI6533`, `BR1000`, `CG1000`, `DB0007`, `DS1000`, `EB1000`, `EB3510`, `EB3542`, `EB3563`, `EB3612`, `GO1000`, `MB1000`, `MB6210`, `MB6225`, `MB6226`, `MB6252`, `MB6257`, `MB6262`, `PB1000`, `PB5303`, `PB5307`, `PB5338`, `RS0001`, `TK0001`, `TK1003`, `TK1004`, `TK1005`, `TK1006`, `TK1007`, `TK1018`, `TK1021`

## Missing From DATABASE.csv

`BI6530`, `BI6533`, `CG1000`, `DB1343`, `DS6602`, `EB3510`, `EB3542`, `EB3561`, `EB3563`, `EB3609`, `EB3612`, `EB3616`, `MB6207`, `MB6210`, `MB6223`, `MB6224`, `MB6225`, `MB6226`, `MB6252`, `MB6257`, `MB6259`, `PB5303`, `PB5307`, `PB5341`

## PDF Hashes

- `2023 _turkey_2023_turkey_bonus_points_draw_results.pdf`: exists `True`, pages `9`, codes `7`, sha256 `173678409a659135eff98438a06bbd1bda558d73b0b76d911ce28434bc529300`
- `2023 ELK + OTHER BIG GAME.pdf`: exists `True`, pages `399`, codes `392`, sha256 `66a38f69c535fe4e9128ada6c0f8253db58581ca4e924837b086c9f176249a6d`
- `2022-23 Sportsman draw odds report.pdf`: exists `True`, pages `1`, codes `11`, sha256 `fc7c64978355dfaa859b884dcb66ab67c3c9daefa595d2e5cdbf3a5917a2000a`
- `O.I.L. Species.pdf`: exists `True`, pages `50`, codes `50`, sha256 `433c2531f9942c4a630d0184a0042f5668c1e3cec08c073190d62250c8e260a2`

## Guardrail

This is a code-presence audit only. It does not promote values, modify DATABASE.csv, modify runtime feeds, or merge rows into the global draw truth table.
