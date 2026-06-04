# Specific 2026 Sportsman / DB1109 / DB1121 Source Comparison

## Finding

- `EX1000` is not a sportsman permit code. It is `Elk Extended Archery` in DATABASE/DWR with no quota published.
- `DB1109` and `DB1121` are active 2026 deer buck hunts. They match DATABASE, DWR HuntTable, HaNumber/current reconciliation, UtahDraws, and the user-supplied deer buck source on total `2`.
- `CG1000` is a historical sportsman cougar code, not the current 2026 cougar row.
- Current cougar rolls into `CG9999`, and `CG9999` has unlimited permits rather than a numbered quota.
- The current numbered sportsman set excludes `CG1000`; the current cougar row is statewide/unlimited.
- Conservation permit table rows are kept separate and are not counted as sportsman support when a hunt code overlaps.

## Outputs

- Detail CSV: `processed_data/audits/specific_2026_sportsman_db1109_db1121_source_comparison.csv`
- Summary JSON: `processed_data/audits/specific_2026_sportsman_db1109_db1121_source_comparison_summary.json`

## Code Summary

- `BI1000`: Bison - Statewide Permit; matches `UTAHDRAWS_HAS_VALUE`
- `BR1000`: Black Bear - Statewide Permit; matches `UTAHDRAWS_HAS_VALUE`
- `CG1000`: not in DATABASE; matches `NO_MATCHING_PERMIT_SOURCE_FOUND`
- `CG9999`: Cougar - Statewide; matches `NO_MATCHING_PERMIT_SOURCE_FOUND`
- `DB0007`: Buck Deer - Statewide Permit; matches `UTAHDRAWS_MATCHES_DATABASE|DEER_BUCK_DB_DIRECT_MATCH`
- `DS1000`: Desert Bighorn Sheep - Statewide Permit; matches `UTAHDRAWS_TOTAL_MATCHES_DATABASE`
- `EB1000`: Elk - Statewide Permit; matches `UTAHDRAWS_HAS_VALUE`
- `GO1000`: Mountain Goat - Statewide Permit; matches `UTAHDRAWS_MATCHES_DATABASE`
- `MB1000`: Moose - Statewide Permit; matches `UTAHDRAWS_HAS_VALUE`
- `PB1000`: Pronghorn - Statewide Permit; matches `UTAHDRAWS_HAS_VALUE`
- `RS0001`: Rocky Mountain Bighorn Sheep - Statewide Permit; matches `UTAHDRAWS_TOTAL_MATCHES_DATABASE`
- `TK0001`: Turkey - Statewide Permit; matches `UTAHDRAWS_HAS_VALUE`
- `EX1000`: Elk Extended Archery; matches `NO_MATCHING_PERMIT_SOURCE_FOUND`
- `DB1109`: Thousand Lakes; matches `DWR_HUNTTABLE_MATCHES_DATABASE|HANUMBER_MATCHES_DATABASE|UTAHDRAWS_MATCHES_DATABASE|DEER_BUCK_DB_DIRECT_MATCH`
- `DB1121`: Antelope Island Management; matches `DWR_HUNTTABLE_MATCHES_DATABASE|HANUMBER_MATCHES_DATABASE|UTAHDRAWS_MATCHES_DATABASE|DEER_BUCK_DB_DIRECT_MATCH`
