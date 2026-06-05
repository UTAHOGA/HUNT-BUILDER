# 2025 Total Permit Cross-Compare

Read-only audit comparing selected 2025 draw-result total permits against the 2025 preliminary big-game harvest permit counts by exact `hunt_code`.

## Summary

- Draw year: `2025`.
- Harvest reported hunt year: `2025`.
- Selected draw hunt codes: `594`.
- Selected harvest hunt codes: `1120`.
- Compared hunt codes: `1120`.
- Expo rows loaded: `122`.
- Expo matched hunt codes: `56`.
- Draw-only match rate where both sides have totals: `160/594 (26.9%)`.
- Draw plus Expo match rate where both sides have totals: `186/594 (31.3%)`.
- Harvest-greater-than-draw rows resolved exactly by Expo: `26`.

## Status Counts

| Status | Rows |
| --- | ---: |
| DRAW_GREATER_THAN_HARVEST | 34 |
| HARVEST_GREATER_THAN_DRAW | 400 |
| HARVEST_ONLY_TOTAL | 526 |
| TOTAL_PERMIT_MATCH | 160 |

## Draw Plus Expo Status Counts

| Status | Rows |
| --- | ---: |
| HARVEST_GREATER_THAN_SOURCE | 361 |
| HARVEST_ONLY_TOTAL | 526 |
| SOURCE_GREATER_THAN_HARVEST | 47 |
| TOTAL_PERMIT_MATCH | 186 |

## Expo Match Decisions

| Decision | Rows |
| --- | ---: |
| AMBIGUOUS_EXPO_MATCH | 30 |
| EXPO_MATCHED_BY_EXACT_GAP_AND_SPECIES_UNIT | 29 |
| EXPO_MATCHED_BY_SPECIES_UNIT_TOKENS | 45 |
| NO_TOKEN_MATCH | 18 |

## Selected Draw Source Rows

| Source file | Rows |
| --- | ---: |
| 2025 LE Deer Draw Results.pdf | 12870 |
| 2025 LE Elk Draw Results(1).pdf | 13860 |
| 2025 LE Pronghorn Draw Results.pdf | 5808 |
| 2025 O.I.L. Draw Results(1).pdf | 6666 |

## What It Takes To Get Matches

- Exact same `hunt_code` plus summed 2025 draw totals already gives the clean matches.
- Adding Expo permits can explain additional harvest-field permit totals when the Expo unit heading maps cleanly to the same draw hunt code.
- Rows where harvest is higher than draw need an overlay channel test before they should be called conflicts; likely candidates are expo, conservation, CWMU, landowner, or other field-issued permits.
- Rows where draw is higher than harvest should not be filled automatically; those need source-scope/extraction-grain review.
- This pass only tests totals. It does not prove source authority for overwrites.

## Rows Resolved By Expo

| Hunt code | Hunt name | Species | Draw total | Expo | Draw + Expo | Harvest permits | Expo source |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| DB1010 | Paunsaugunt | Deer | 26 | 3 | 29 | 29 | Buck Deer - Premium Limited Entry - Premium Any Weapon - Paunsaugunt - Permits: 3 |
| DB1026 | Cache, Crawford Mtn | Deer | 7 | 1 | 8 | 8 | Buck Deer - Limited Entry - Muzzleloader - Cache, Crawford Mtn - Permits: 1 |
| DB1034 | Pine Valley | Deer | 14 | 1 | 15 | 15 | Buck Deer - Limited Entry - Late-season Muzzleloader - Pine Valley - Permits: 1 |
| DB1037 | San Juan, Elk Ridge | Deer | 16 | 1 | 17 | 17 | Buck Deer - Limited Entry - Late-season Muzzleloader - Manti/San Rafael - Permits: 1 |
| DB1043 | Zion | Deer | 14 | 1 | 15 | 15 | Buck Deer - Limited Entry - Late-season Muzzleloader - Zion - Permits: 1 |
| DB1048 | West Desert, Vernon | Deer | 7 | 2 | 9 | 9 | Buck Deer - Limited Entry - Muzzleloader - West Desert, Vernon - Permits: 2 |
| EB3005 | Cache South | Elk | 9 | 1 | 10 | 10 | Bull Elk - Limited Entry - Archery - Cache, South - Permits: 1 |
| EB3015 | Panguitch Lake | Elk | 17 | 1 | 18 | 18 | Bull Elk - Limited Entry - Archery - Panguitch Lake - Permits: 1 |
| EB3020 | Diamond Mtn | Elk | 24 | 1 | 25 | 25 | Bull Elk - Limited Entry - Archery - Diamond Mtn - Permits: 1 |
| EB3022 | Wasatch Mtns | Elk | 176 | 6 | 182 | 182 | Bull Elk - Limited Entry - Archery - Wasatch Mtns - Permits: 6 |
| EB3038 | Manti | Elk | 70 | 2 | 72 | 72 | Bull Elk - Limited Entry - Any Weapon (early) - Manti - Permits: 2 |
| EB3039 | Manti | Elk | 117 | 5 | 122 | 122 | Bull Elk - Limited Entry - Any Weapon (mid) - Manti - Permits: 5 |
| EB3063 | Fishlake/Thousand Lakes | Elk | 35 | 3 | 38 | 38 | Bull Elk - Limited Entry - Archery - Fishlake/Thousand Lakes - Permits: 3 |
| EB3100 | Wasatch Mtns | Elk | 105 | 4 | 109 | 109 | Bull Elk - Limited Entry - Muzzleloader - Wasatch Mtns - Permits: 4 |
| EB3127 | Wasatch Mtns | Elk | 211 | 4 | 215 | 215 | Bull Elk - Limited Entry - Any Weapon (mid) - Wasatch Mtns - Permits: 4 |
| EB3148 | Boulder | Elk | 12 | 2 | 14 | 14 | Bull Elk - Limited Entry - Any Weapon (mid) - Boulder - Permits: 2 |
| EB3149 | Southwest Desert South | Elk | 16 | 2 | 18 | 18 | Bull Elk - Limited Entry - Any Weapon (mid) - Southwest Desert, South - Permits: 2 |
| EB3151 | Boulder | Elk | 21 | 1 | 22 | 22 | Bull Elk - Limited Entry - Any Weapon (early) - Boulder - Permits: 1 |
| GO6821 | Nebo | Mountain Goat | 11 | 1 | 12 | 12 | Mountain Goat - Once-in-a-lifetime - Hunter Choice Archery - Nebo - Permits: 1 |
| PB5008 | Fillmore, Oak Creek South | Pronghorn | 14 | 1 | 15 | 15 | Buck Pronghorn - Limited Entry - Archery - Fillmore, Oak Creek South - Permits: 1 |
| PB5018 | Southwest Desert | Pronghorn | 34 | 1 | 35 | 35 | Buck Pronghorn - Limited Entry - Archery - Southwest Desert - Permits: 1 |
| PB5024 | Southwest Desert | Pronghorn | 34 | 1 | 35 | 35 | Buck Pronghorn - Limited Entry - Muzzleloader - Southwest Desert - Permits: 1 |
| PB5047 | Diamond Mtn/Bonanza | Pronghorn | 53 | 3 | 56 | 56 | Buck Pronghorn - Limited Entry - Any Weapon - Diamond Mtn/Bonanza - Permits: 3 |
| PB5051 | West Desert, Rush Valley | Pronghorn | 36 | 1 | 37 | 37 | Buck Pronghorn - Limited Entry - Any Weapon - West Desert, Riverbed - Permits: 1 |
| PB5330 | George Creek CWMU | Pronghorn | 2 | 2 | 4 | 4 | Buck Pronghorn - Limited Entry - Any Weapon - Fillmore, Oak Creek South - Permits: 2 |
| RS6722 | Box Elder, Newfoundland Mtn | Rocky Mountain Bighorn Sheep | 2 | 1 | 3 | 3 | Rocky Mtn. Bighorn Sheep - Once-in-a-lifetime - - Box Elder, Newfoundland Mtn (early) - Permits: 1 |

## Top Total Gaps

| Hunt code | Hunt name | Species | Draw total | Expo | Draw + Expo | Harvest permits | Delta after Expo | Status |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| BI6503 | Henry Mtns | Bison | 6 | 0 | 6 | 15 | 9 | HARVEST_GREATER_THAN_SOURCE |
| BI6504 | Henry Mtns | Bison | 7 | 0 | 7 | 13 | 6 | HARVEST_GREATER_THAN_SOURCE |
| BI6506 | Henry Mtns | Bison | 30 | 0 | 30 | 29 | -1 | SOURCE_GREATER_THAN_HARVEST |
| BI6509 | Henry Mtns | Bison | 4 | 0 | 4 | 3 | -1 | SOURCE_GREATER_THAN_HARVEST |
| BI6516 | Henry Mtns | Bison | 5 | 0 | 5 | 13 | 8 | HARVEST_GREATER_THAN_SOURCE |
| BI6529 | Book Cliffs, Little Creek/South | Bison | 8 | 0 | 8 | 5 | -3 | SOURCE_GREATER_THAN_HARVEST |
| BI6531 | Book Cliffs, Little Creek/South | Bison | 7 | 0 | 7 | 8 | 1 | HARVEST_GREATER_THAN_SOURCE |
| BI6532 | Book Cliffs, Bitter Creek | Bison | 5 | 0 | 5 | 4 | -1 | SOURCE_GREATER_THAN_HARVEST |
| BI6536 | Book Cliffs, Bitter Creek | Bison | 2 | 0 | 2 | 3 | 1 | HARVEST_GREATER_THAN_SOURCE |
| BI6537 | Book Cliffs, Little Creek/South | Bison | 10 | 0 | 10 | 11 | 1 | HARVEST_GREATER_THAN_SOURCE |
| DB1001 | Paunsaugunt | Deer | 28 | 0 | 28 | 34 | 6 | HARVEST_GREATER_THAN_SOURCE |
| DB1003 | Henry Mtns | Deer | 24 | 0 | 24 | 27 | 3 | HARVEST_GREATER_THAN_SOURCE |
| DB1004 | Paunsaugunt | Deer | 80 | 0 | 80 | 90 | 10 | HARVEST_GREATER_THAN_SOURCE |
| DB1005 | Henry Mtns | Deer | 9 | 0 | 9 | 10 | 1 | HARVEST_GREATER_THAN_SOURCE |
| DB1006 | Paunsaugunt | Deer | 28 | 0 | 28 | 30 | 2 | HARVEST_GREATER_THAN_SOURCE |
| DB1007 | Henry Mtns | Deer | 1 | 0 | 1 | 2 | 1 | HARVEST_GREATER_THAN_SOURCE |
| DB1008 | Paunsaugunt | Deer | 4 | 0 | 4 | 6 | 2 | HARVEST_GREATER_THAN_SOURCE |
| DB1010 | Paunsaugunt | Deer | 26 | 3 | 29 | 29 | 0 | TOTAL_PERMIT_MATCH |
| DB1011 | Book Cliffs | Deer | 48 | 0 | 48 | 52 | 4 | HARVEST_GREATER_THAN_SOURCE |
| DB1012 | Fillmore, Oak Creek LE | Deer | 12 | 0 | 12 | 13 | 1 | HARVEST_GREATER_THAN_SOURCE |
| DB1014 | San Juan, Elk Ridge | Deer | 16 | 0 | 16 | 17 | 1 | HARVEST_GREATER_THAN_SOURCE |
| DB1015 | Diamond Mtn | Deer | 21 | 1 | 22 | 23 | 1 | HARVEST_GREATER_THAN_SOURCE |
| DB1016 | West Desert, Vernon | Deer | 43 | 3 | 46 | 51 | 5 | HARVEST_GREATER_THAN_SOURCE |
| DB1017 | Book Cliffs, North | Deer | 123 | 0 | 123 | 128 | 5 | HARVEST_GREATER_THAN_SOURCE |
| DB1018 | Book Cliffs, South | Deer | 29 | 0 | 29 | 31 | 2 | HARVEST_GREATER_THAN_SOURCE |

## Guardrails

- `DATABASE.csv` was read only for current-code membership checks.
- Raw PDFs were not edited.
- Normalized draw and harvest truth tables were not edited.
- Runtime manifests and website files were not edited.
