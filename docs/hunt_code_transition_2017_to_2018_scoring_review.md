# Hunt Code Alignment Review: 2017 Source Year -> 2018 Actual Year

Purpose: support the 2017=2018 prediction-scoring audit by identifying which 2018 actual rows should be scored, which rows have an approved 2017 source-year predecessor, which rows are target-only, and which rows should be treated as reference/support diagnostics instead of accuracy misses.

The scoring direction is:

`2017 official scorable truth -> prediction engine -> 2018 predicted rows -> compare to 2018 official actual truth`

This file is not prediction input. It is an audit note for scoring alignment after the 2018 actuals exist.

## Source Files

Official 2017 DWR PDFs present under `pipeline/RAW/hunt_unit_database/2017/pdf/regulations/`:

| File | Source URL | Role |
| --- | --- | --- |
| `2017_field_regs.pdf` | `https://wildlife.utah.gov/guidebooks/2017_field_regs.pdf` | Big game field regulations, including antlerless field guidance |
| `2017-18_cougar.pdf` | `https://wildlife.utah.gov/guidebooks/2017-18_cougar.pdf` | Cougar guidebook |
| `2017-18_furbearer.pdf` | `https://wildlife.utah.gov/guidebooks/2017-18_furbearer.pdf` | Furbearer guidebook |
| `2017-18_upland-turkey.pdf` | `https://wildlife.utah.gov/guidebooks/2017-18_upland-turkey.pdf` | Upland game and turkey guidebook |

Manifest:

`pipeline/RAW/hunt_unit_database/2017/pdf/regulations/2017_regulation_pdf_download_manifest.csv`

DWR site caveat:

- The 2017 field regulations refer to a companion 2017 Big Game Application Guidebook at `wildlife.utah.gov/guidebooks`.
- The DWR Big Game page exposes previous Big Game Application editions back to 2018, but not 2017.
- Tested DWR URL patterns for `2017_biggameapp.pdf`, `2017_biggame.pdf`, `2017_bear.pdf`, and similar variants returned 404 on `wildlife.utah.gov`.
- Because Tyler constrained the online pull to `wildlife.utah.gov`, do not import a mirrored 2017 Big Game Application PDF into the official raw folder unless Tyler explicitly approves that source.

Useful 2018 actual-year comparison PDFs already present under `pipeline/RAW/hunt_unit_database/2018/pdf/regulations/`:

- `2018_biggameapp.pdf`
- `2018_field_regs.pdf`
- `2018_bear.pdf`
- `2018-19_cougar.pdf`
- `2018-19_furbearer.pdf`
- `2018-19_upland-turkey.pdf`

## Locked Universe Alignment

Inputs:

- `data_truth/hunt_code_universe_truth/locked/2017/LOCKED_2017_ACTIVE_YEAR_TRUTH_WITH_BOUNDARY_ID.csv`
- `data_truth/hunt_code_universe_truth/locked/2018/LOCKED_2018_ACTIVE_YEAR_TRUTH_WITH_BOUNDARY_ID.csv`
- `data_truth/hunt_code_universe_truth/locked/2018/LOCKED_2018_CANONICAL_LONG_RECONCILIATION.csv`

Active-year alignment:

| Measure | Count |
| --- | ---: |
| 2017 active truth codes | 982 |
| 2018 active truth codes | 1,042 |
| Same-code active rows | 945 |
| Target-only active rows | 97 |
| Source-only active rows | 37 |

Scorable-code alignment:

| Measure | Count |
| --- | ---: |
| 2017 scorable codes | 982 |
| 2018 scorable codes | 1,010 |
| Same-code scorable rows | 939 |
| Target-only scorable rows | 71 |
| Source-only scorable rows | 43 |

2018 active reference/non-scorable rows:

- Count: 32
- Prefixes: `CG=27`, `PB=5`
- Codes: `CG1002`, `CG1003`, `CG1004`, `CG1005`, `CG1006`, `CG1007`, `CG1008`, `CG1009`, `CG1010`, `CG1011`, `CG1014`, `CG1015`, `CG1017`, `CG1018`, `CG1019`, `CG1020`, `CG1021`, `CG1022`, `CG1023`, `CG1024`, `CG1025`, `CG1026`, `CG1027`, `CG1028`, `CG1031`, `CG1032`, `CG7601`, `PB5010`, `PB5014`, `PB5023`, `PB5036`, `PB5043`

2018 database next-year support rows:

- Count: 65
- Prefixes: `BR=16`, `EA=11`, `PD=9`, `DA=6`, `DB=6`, `BI=4`, `PB=4`, `MB=3`, `EB=2`, `RS=2`, `CG=1`, `GO=1`
- These are retained for future-year support and lookup, but are excluded from active-year prediction accuracy.

## PDF Evidence Policy

Use the 2017 DWR PDFs for source-year terms, table rows, hunt codes, hunt names, permit structure, and year-specific context. Those terms were knowable to a 2017-source prediction engine.

Use the 2018 DWR PDFs only after prediction, as actual-year audit context. Do not feed target-year summary language into the prediction engine.

For scoring, the relevant evidence is:

- source-year row exists in official scorable truth,
- target-year row exists in official actual truth,
- row is canonical/scorable rather than reference-only,
- row has an exact key or an approved source-to-target crosswalk,
- row has real applicants and a real actual probability.

## 2017 Source-Year PDF Term Hits

The 2017 field regulations contain source-year language that directly supports structural review before scoring 2017=2018:

- `2017_field_regs.pdf`, pages 2-3: source-year management buck deer structure includes Henry Mountains archery and muzzleloader rows.
- `2017_field_regs.pdf`, pages 2-3: youth any-bull elk hunters may harvest either a bull elk or an antlerless elk.
- `2017_field_regs.pdf`, pages 2-3: source-year late-season limited-entry muzzleloader deer rows exist on general-season units.
- `2017_field_regs.pdf`, pages 2-3: source-year limited-entry bull elk rows overlap the general-season spike elk hunt on six units.
- `2017_field_regs.pdf`, page 3: source-year big-game and antlerless unit boundaries/names require map verification in the Hunt Planner.
- `2017_field_regs.pdf`, page 2: antlerless elk-control hunt structure was discontinued on spike bull elk hunting units.

The 2017 cougar guidebook contains source-year cougar structure terms:

- `2017-18_cougar.pdf`, page 2: source-year Wasatch Mtns, Salt Lake cougar harvest-objective row appears as an archery-only unit.
- `2017-18_cougar.pdf`, pages 17 and 19: `CG7506` Wasatch Mtns, West-Strawberry is marked for boundary review.
- `2017-18_cougar.pdf`, page 17: 2017 source-year split-unit rows include `CG7600` Beaver and `CG7601` Box Elder, Desert.

These source-year terms are valid for classification and crosswalk review. They still do not prove a specific source-to-target hunt-code mapping by themselves; approved crosswalk rows should be explicit.

## 2017 Source-Year New Hunt Marks

These rows should be marked as **new hunts or new hunt category rows in the 2017 source year**. They are not target-year leakage for a 2017=2018 prediction run because they were already available in 2017 source material and are present in the locked 2017 scorable roster.

Secondary locator source: `https://www.ksl.com/article/news/utah/utah-wildlife-board-approves-new-big-game-hunts-changes-for-2017-season/42707602`

The full 2017 source-year late-season limited-entry muzzleloader deer category has 15 hunt codes:

| 2017 hunt code | Hunt name | Species | Hunt type | Weapon | 2017 source-year mark | Scoring treatment |
| --- | --- | --- | --- | --- | --- | --- |
| `DB1027` | Chalk Creek/East Canyon/Morgan-South Rich | Deer | Limited Entry | Muzzleloader | 2017 introduced late-season LE muzzleloader deer category row | Exact-code source row; score normally against target actual if target row exists |
| `DB1028` | Fillmore | Deer | Limited Entry | Muzzleloader | 2017 introduced late-season LE muzzleloader deer category row | Exact-code source row; score normally against target actual if target row exists |
| `DB1030` | Kamas | Deer | Limited Entry | Muzzleloader | 2017 introduced late-season LE muzzleloader deer category row | Exact-code source row; score normally against target actual if target row exists |
| `DB1032` | Monroe | Deer | Limited Entry | Muzzleloader | 2017 introduced late-season LE muzzleloader deer category row | Exact-code source row; score normally against target actual if target row exists |
| `DB1033` | Nine Mile | Deer | Limited Entry | Muzzleloader | 2017 introduced late-season LE muzzleloader deer category row | Exact-code source row; score normally against target actual if target row exists |
| `DB1034` | Pine Valley | Deer | Limited Entry | Muzzleloader | 2017 introduced late-season LE muzzleloader deer category row | Exact-code source row; score normally against target actual if target row exists |
| `DB1036` | Plateau, Thousand Lakes | Deer | Limited Entry | Muzzleloader | 2017 introduced late-season LE muzzleloader deer category row | Exact-code source row; score normally against target actual if target row exists |
| `DB1039` | South Slope, Yellowstone | Deer | Limited Entry | Muzzleloader | 2017 introduced late-season LE muzzleloader deer category row | Exact-code source row; score normally against target actual if target row exists |
| `DB1040` | Southwest Desert | Deer | Limited Entry | Muzzleloader | 2017 introduced late-season LE muzzleloader deer category row | Exact-code source row; score normally against target actual if target row exists |
| `DB1041` | Wasatch Mtns, East | Deer | Limited Entry | Muzzleloader | 2017 introduced late-season LE muzzleloader deer category row | Exact-code source row; score normally against target actual if target row exists |
| `DB1042` | West Desert, Vernon | Deer | Limited Entry | Muzzleloader | 2017 introduced late-season LE muzzleloader deer category row | Exact-code source row; score normally against target actual if target row exists |
| `DB1043` | Zion | Deer | Limited Entry | Muzzleloader | 2017 introduced late-season LE muzzleloader deer category row | Exact-code source row; score normally against target actual if target row exists |
| `DB1053` | Mt Dutton | Deer | Limited Entry | Muzzleloader | 2017 introduced late-season LE muzzleloader deer category row; also new by 2016->2017 exact-code harvest delta | Exact-code source row; score normally against target actual if target row exists |
| `DB1054` | Ogden | Deer | Limited Entry | Muzzleloader | 2017 introduced late-season LE muzzleloader deer category row; also new by 2016->2017 exact-code harvest delta | Exact-code source row; score normally against target actual if target row exists |
| `DB1055` | Plateau, Fishlake | Deer | Limited Entry | Muzzleloader | 2017 introduced late-season LE muzzleloader deer category row; also new by 2016->2017 exact-code harvest delta | Exact-code source row; score normally against target actual if target row exists |

The three `DB1053`/`DB1054`/`DB1055` rows are the subset that appears as new exact hunt codes when comparing the 2016 and 2017 LE/OIAL harvest reports. The full 15-code set is the 2017 source-year introduced hunt category.

Additional 2017 source-year new-hunt marks:

| 2017 hunt code | Hunt name | Species | Hunt type | Weapon | 2017 source-year mark | Scoring treatment |
| --- | --- | --- | --- | --- | --- | --- |
| `GO6814` | Mt Dutton | Mountain Goat | Limited Entry | Any Legal Weapon | 2017 new mountain goat hunt | Exact-code source row; score normally against target actual if target row exists |
| `GO6815` | North Slope/South Slope, High Uintas Central | Mountain Goat | Limited Entry | Archery | 2017 new archery mountain goat hunt | Exact-code source row; score normally against target actual if target row exists |
| `BI6509` | Henry Mtns (hunter's Choice) | Bison | Limited Entry | Archery | 2017 new archery bison hunt | Exact-code source row; score normally against target actual if target row exists |

The 2017 late-season LE muzzleloader deer category should not be confused with 2018 target-year-only rows such as `DB1059` or `DB1065`.

## 2017 Harvest Report Confirmation

`pipeline/RAW/hunt_unit_database/2017/pdf/harvest_report/2017_le_oial_hr.pdf` confirms these same 2017 source-year rows by exact hunt code. Harvest-report presence is supporting row evidence only; it is not a draw-probability source.

| Hunt code | Harvest report page | Hunt name in harvest report | Hunt type in harvest report | Permits | Hunters afield | Harvest | Percent success |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: |
| `DB1053` | 1 | Mt Dutton | Muzzleloader | 5 | 5 | 4 | 80.0 |
| `DB1054` | 1 | Ogden | Muzzleloader | 5 | 5 | 3 | 60.0 |
| `DB1055` | 1 | Plateau, Fishlake | Muzzleloader | 5 | 5 | 2 | 40.0 |
| `GO6814` | 18 | Mt Dutton | OIAL | 1 | 1 | 1 | 100.0 |
| `GO6815` | 18 | North Slope/South Slope, High Uintas Central | Archery | 2 | 2 | 0 | 0.0 |
| `BI6509` | 15 | Henry Mtns (archery) | OIAL | 10 | 10 | 7 | 66.7 |

## 2016->2017 Harvest Delta Reconciliation

Comparison source:

- `pipeline/RAW/hunt_unit_database/2016/pdf/harvest_report/4B871A48__2016_le_oial_hr.pdf`
- `pipeline/RAW/hunt_unit_database/2017/pdf/harvest_report/2017_le_oial_hr.pdf`
- `pipeline/RAW/hunt_unit_database/2018/pdf/regulations/*.pdf`
- `data_truth/hunt_code_universe_truth/locked/2018/LOCKED_2018_ACTIVE_YEAR_TRUTH_WITH_BOUNDARY_ID.csv`
- `data_truth/hunt_code_universe_truth/locked/2018/LOCKED_2018_CANONICAL_LONG_RECONCILIATION.csv`

Harvest-code comparison:

| Measure | Count |
| --- | ---: |
| 2016 LE/OIAL harvest codes | 526 |
| 2017 LE/OIAL harvest codes | 551 |
| Same exact code in both reports | 497 |
| Appears in 2017, absent in 2016 | 54 |
| Appears in 2016, absent in 2017 | 29 |

Reconciliation of the 54 rows that appear in 2017 but not 2016:

| Status | Count | Treatment |
| --- | ---: | --- |
| Exact code persists to 2018 active scorable truth | 28 | Reconciled by exact code; no crosswalk needed |
| Explicit 2017 source-year new-hunt mark | 6 | Reconciled as 2017 source-year rows; no target leakage |
| 2018 database next-year support only | 1 | Not active-year scorable |
| Not seen in 2018 target materials searched | 19 | Mostly conservation/statewide/admin rows; keep out of accuracy unless canonical draw truth exists |

The six explicit 2017 source-year new-hunt marks are:

- `DB1053`
- `DB1054`
- `DB1055`
- `GO6814`
- `GO6815`
- `BI6509`

The 28 exact-code rows that persist into 2018 active scorable truth are:

- `BI6507`, `BI6508`
- `DB1051`, `DB1052`, `DB1320`, `DB1321`, `DB1322`, `DB1323`, `DB1324`
- `EB3126`, `EB3127`, `EB3565`, `EB3603`
- `MB6258`, `MB6259`
- `PB5053`, `PB5054`, `PB5055`, `PB5056`, `PB5325`, `PB5326`, `PB5327`, `PB5328`, `PB5329`, `PB5330`
- `RS6712`, `RS6713`, `RS6714`

The one 2017-new harvest row that is only 2018 database next-year support is:

- `MB6257`

Rows that appear in 2016 but not 2017 are not 2017 source-year rows. For 2017=2018 scoring, they should not be used as prediction input. Only one of those exact codes appears in 2018 active scorable truth:

- `RS6702` Box Elder, Pilot Mtn

Because `RS6702` is absent from the 2017 source-year harvest report and 2017 active scorable universe, treat it as target-year-only for 2017=2018 unless another 2017 source-year predecessor is explicitly approved.

## 2016 Harvest Rows Terminated Before 2017 Source Year

These 2016 LE/OIAL harvest-report rows are absent from the 2017 LE/OIAL harvest report. Mark them as **terminated/not carried forward into the 2017 source year** for 2017=2018 scoring. Conservation/statewide/admin rows remain non-scorable unless a canonical draw-result row says otherwise.

| 2016 hunt code | 2016 harvest-report label | Termination mark for 2017 source year | Scoring treatment |
| --- | --- | --- | --- |
| `BI6502` | Book Cliffs, Wild Horse Bench (hunter's choice) OIAL | Terminated before 2017 source year | Do not use as 2017 source prediction row |
| `BI6591` | Statewide Conservation | Terminated/annual conservation code not carried forward | Non-scorable/admin unless canonical draw truth exists |
| `DB1226` | Crab Creek CWMU | Terminated before 2017 source year | Do not use as 2017 source prediction row |
| `DB1254` | Jacob's Creek CWMU | Terminated before 2017 source year | Do not use as 2017 source prediction row |
| `DB1262` | Missouri Flat CWMU | Terminated before 2017 source year | Do not use as 2017 source prediction row |
| `DB1268` | New Harmony CWMU | Terminated before 2017 source year | Do not use as 2017 source prediction row |
| `DB1311` | Wood Canyon CWMU | Terminated before 2017 source year | Do not use as 2017 source prediction row |
| `DB1910` | Statewide Conservation | Terminated/annual conservation code not carried forward | Non-scorable/admin unless canonical draw truth exists |
| `DS6691` | Statewide Conservation | Terminated/annual conservation code not carried forward | Non-scorable/admin unless canonical draw truth exists |
| `DS6692` | Henry Mtns/Dirty Devil/La Sal/San Juan Conservation | Terminated/annual conservation code not carried forward | Non-scorable/admin unless canonical draw truth exists |
| `DS6693` | Kaiparowits Conservation | Terminated/annual conservation code not carried forward | Non-scorable/admin unless canonical draw truth exists |
| `DS6696` | San Rafael North and South Conservation | Terminated/annual conservation code not carried forward | Non-scorable/admin unless canonical draw truth exists |
| `EB3513` | Crab Creek CWMU | Terminated before 2017 source year | Do not use as 2017 source prediction row |
| `EB3530` | Jacob's Creek CWMU | Terminated before 2017 source year | Do not use as 2017 source prediction row |
| `EB3537` | Missouri Flat CWMU | Terminated before 2017 source year | Do not use as 2017 source prediction row |
| `EB3910` | Statewide Conservation | Terminated/annual conservation code not carried forward | Non-scorable/admin unless canonical draw truth exists |
| `GO6891` | Statewide Sportsman | Terminated/annual sportsman code not carried forward | Sportsman/admin recode review only; do not score as ordinary source row |
| `MB6252` | Jacob's Creek CWMU | Terminated before 2017 source year | Do not use as 2017 source prediction row |
| `MB6253` | Little Red Creek CWMU | Terminated before 2017 source year | Do not use as 2017 source prediction row |
| `MB6491` | Statewide Conservation | Terminated/annual conservation code not carried forward | Non-scorable/admin unless canonical draw truth exists |
| `PB5301` | Black Point CWMU | Terminated before 2017 source year | Do not use as 2017 source prediction row |
| `PB5910` | Statewide Conservation | Terminated/annual conservation code not carried forward | Non-scorable/admin unless canonical draw truth exists |
| `RS6702` | Box Elder, Pilot Mtn OIAL | Absent from 2017 source year; reappears in 2018 target truth | Treat as target-year-only for 2017=2018 unless a 2017 predecessor is approved |
| `RS6706` | Nine Mile, Range Creek OIAL | Terminated before 2017 source year | Do not use as 2017 source prediction row |
| `RS6707` | Nine Mile, Range Creek OIAL | Terminated before 2017 source year | Do not use as 2017 source prediction row |
| `RS6708` | North Slope, Three Corners-Bare Top OIAL | Terminated before 2017 source year | Do not use as 2017 source prediction row |
| `RS6709` | North Slope, West Daggett OIAL | Terminated before 2017 source year | Do not use as 2017 source prediction row |
| `RS6710` | Stansbury OIAL | Terminated before 2017 source year | Do not use as 2017 source prediction row |
| `RS6791` | Statewide Conservation | Terminated/annual conservation code not carried forward | Non-scorable/admin unless canonical draw truth exists |

## 2018 Regulation-Supported Crosswalk Candidates

These are the crosswalk candidates supported by the 2018 regulation PDFs. They still require explicit approval before being promoted into scorer normalization.

| 2017 source code | 2017 source name | 2018 target code(s) | 2018 evidence | Recommended treatment |
| --- | --- | --- | --- | --- |
| `CG7600` | Beaver | `CG1030`, `CG1031` | `2018-19_cougar.pdf` pages 17-18 lists Beaver East and Beaver West structures | One-to-many cougar split review; `CG1030` is scorable, `CG1031` is reference/harvest-objective |
| `CG7504` | Oquirrh-Stansbury | `CG1029`, `CG1032` | `2018-19_cougar.pdf` pages 17-18 lists Oquirrh-Stansbury East and West structures | One-to-many cougar split review; `CG1029` is scorable, `CG1032` is reference/harvest-objective |
| `GO6812` | Wasatch Mtns, Box Elder Peak/Lone Peak/Timpanogos | `GO6818`, `GO6819`, `GO6820` | `2018_biggameapp.pdf` page 30 lists separate Box Elder Peak, Lone Peak, and Timpanogos rows | One-to-many mountain goat split review |
| `RS6705` | Central Mtns, Nebo/Wasatch Mtns, West | `RS6719` | `2018_biggameapp.pdf` page 30 lists Central Mtns, Nebo/Wasatch Mtns as a target row | Same-area bighorn review |
| `PB5010`, `PB5014`, `PB5023`, `PB5036`, `PB5043` | Pronghorn boundary rows | Same exact code in 2018 regulation reference rows | `2018_biggameapp.pdf` pages 27-28 lists these rows, but locked 2018 treats them as reference-only | Do not score as active scorable unless canonical draw-result truth exists |

## Black Bear Original-Code Evidence

The bear scoring audit must distinguish original PDF hunt codes from crosswalk-resolved join codes.

2017 source evidence:

- `pipeline/RAW/hunt_unit_database/2017/pdf/harvest_report/Black Bear with Hunt Codes.pdf`
- `pipeline/RAW/hunt_unit_database/2017/pdf/draw_odds/17_bonus_points.pdf`

Both files carry full historical `BR####` codes. The harvest report confirms the 2017 La Sal code set:

| Season/block | 2017 original code | Unit/subunit |
| --- | --- | --- |
| Spring limited-entry | `BR7008` | La Sal |
| Summer limited-entry | `BR7108` | La Sal |
| Fall limited-entry | `BR7208` | La Sal |
| Multi-season/combined harvest section | `BR7307` | La Sal |

2018 target evidence:

- `pipeline/RAW/hunt_unit_database/2018/pdf/regulations/2018_bear.pdf`
- `pipeline/RAW/hunt_unit_database/2018/pdf/draw results/18_drawing_odds.pdf`

Those official 2018 bear sources also use the original La Sal codes `BR7008`, `BR7108`, `BR7208`, and `BR7307`. They do not print the later resolved/current codes `BR7022`, `BR7127`, `BR7239`, or `BR7326`.

The normalized black bear BR crosswalk maps:

| Original/historical code | Resolved join code |
| --- | --- |
| `BR7008` | `BR7022` |
| `BR7108` | `BR7127` |
| `BR7208` | `BR7239` |
| `BR7307` | `BR7326` |

Scorer output should therefore keep both fields visible:

- original PDF code: `BR7008`, `BR7108`, `BR7208`, `BR7307`
- resolved/join code: `BR7022`, `BR7127`, `BR7239`, `BR7326`

Do not describe these bear rows as missing when the black bear BR crosswalk is loaded. The correct audit status is crosswalk-reconciled.

## Target-Only Active 2018 Prefixes

| Prefix | Target-only active codes |
| --- | ---: |
| `CG` | 31 |
| `DA` | 14 |
| `DB` | 13 |
| `EA` | 8 |
| `MB` | 6 |
| `PD` | 6 |
| `PB` | 5 |
| `GO` | 4 |
| `RS` | 4 |
| `EB` | 2 |
| `TK` | 2 |
| `BR` | 1 |
| `MA` | 1 |

Target-only active rows that are scorable in 2018:

- `BR7016` Wasatch Mtns, West-central
- `CG1001` Book Cliffs, East
- `CG1012` Ogden
- `CG1013` Paunsaugunt
- `CG1029` Oquirrh-Stansbury, East
- `CG1030` Beaver, East
- `DA1012`, `DA1026`, `DA1027`, `DA1028`, `DA1029`, `DA1030`, `DA1031`, `DA1032`, `DA1033`, `DA1034`, `DA1035`, `DA1036`, `DA1037`, `DA1038`
- `DB0007`, `DB1058`, `DB1059`, `DB1065`, `DB1325`, `DB1326`, `DB1590`, `DB1591`, `DB1592`, `DB1593`, `DB1595`, `DB1596`, `DB1597`
- `EA1081`, `EA1193`, `EA1194`, `EA1195`, `EA1196`, `EA1197`, `EA1198`, `EA1199`
- `EB3604`, `EB3605`
- `GO6817`, `GO6818`, `GO6819`, `GO6820`
- `MA1004`
- `MB6200`, `MB6216`, `MB6217`, `MB6220`, `MB6223`, `MB6261`
- `PB5331`, `PB5332`, `PB5333`, `PB5334`, `PB5335`
- `PD1027`, `PD1028`, `PD1029`, `PD1030`, `PD1031`, `PD1032`
- `RS0001`, `RS6702`, `RS6719`, `RS6720`
- `TK0001`, `TK1018`

## Source-Only Active 2017 Prefixes

| Prefix | Source-only active codes |
| --- | ---: |
| `DB` | 8 |
| `EA` | 8 |
| `DA` | 6 |
| `EB` | 4 |
| `MB` | 3 |
| `RS` | 3 |
| `CG` | 2 |
| `GO` | 1 |
| `PD` | 1 |
| `TK` | 1 |

Source-only 2017 active rows:

- `CG7504` Stansbury
- `CG7600` Beaver
- `DA1003`, `DA1006`, `DA1008`, `DA1014`, `DA1015`, `DA1016`
- `DB1035`, `DB1214`, `DB1218`, `DB1235`, `DB1239`, `DB1284`, `DB1296`, `DB1310`
- `EA1057`, `EA1083`, `EA1123`, `EA1133`, `EA1169`, `EA1171`, `EA1173`, `EA1188`
- `EB3507`, `EB3518`, `EB3556`, `EB3560`
- `GO6812`
- `MB6221`, `MB6250`, `MB6257`
- `PD1013`
- `RS1000`, `RS6705`, `RS6711`
- `TK1000`

## Candidate Crosswalks Requiring Review

These are name/prefix candidates only. Do not promote them into a scoring crosswalk without official source evidence or Tyler approval.

| 2017 code | 2017 name | Candidate 2018 code(s) | Reason |
| --- | --- | --- | --- |
| `CG7504` | Stansbury | `CG1029` Oquirrh-Stansbury, East | Possible source-to-target geographic continuity |
| `CG7600` | Beaver | `CG1030` Beaver, East | Possible source-to-target geographic continuity |
| `DA1003` | Monroe/Plateau, Sevier Valley | `DA1038` Monroe/Plateau, Sevier Valley | Exact name continuity with different code |
| `DA1006` | Panguitch Lake, Cottonwood | `DA1032` Panguitch Lake, Parowan Front | Similar name; requires source identity review |
| `DA1008` | Panguitch Lake, Summit | `DA1032` Panguitch Lake, Parowan Front | Similar name; requires source identity review |
| `DA1016` | Monroe/Plateau, Angle | `DA1037` Plateau, East Angle; `DA1038` Monroe/Plateau, Sevier Valley | Similar name; possible split/relabel |
| `EA1083` | San Juan, North Elk Ridge | `EA1197` San Juan, Elk Ridge | Strong name continuity |
| `GO6812` | Wasatch Mtns, Box Elder Peak/Lone Peak/Timpanogos | `GO6818`, `GO6819`, `GO6820` | Apparent split into individual 2018 goat rows |
| `RS1000` | Sportsman Rocky Mountain Bighorn Sheep | `RS0001` Sportsman Rocky Mountain Bighorn Sheep | Exact sportsman name with different code |
| `RS6705` | Central Mtns, Nebo/Wasatch Mtns, West | `RS6719` Central Mtns, Nebo/Wasatch Mtns | Strong name continuity; requires source identity review |
| `TK1000` | Sportsman Wild Turkey | `TK0001` Sportsman Bearded | Sportsman turkey different-code candidate |

## Scoring Rules For 2017=2018

1. Score only official 2018 actual ladder rows that are canonical draw-result rows and have a real applicant/probability basis.
2. Do not score 2018 regulation-only/reference rows as misses. They are diagnostics unless canonical yearly draw-result truth also exists.
3. Do not require the 2017 engine to predict target-only 2018 rows unless there is a verified official crosswalk from a 2017 predecessor.
4. If a 2018 row is a likely same-hunt successor under a different code, join through an explicit crosswalk only after source review.
5. Sportsman different-code rows should be handled as recodes, not as real hunt demand disappearance/creation, when the same species and sportsman design are preserved.
6. Cougar split-unit rows need special care:
   - `CG7600` Beaver should not be blindly scored as missing against all Beaver East/West structure.
   - `CG7504` Stansbury should not be blindly scored as missing against all Oquirrh-Stansbury East/West structure.
   - If no official crosswalk is promoted, classify the related rows as structural alignment diagnostics.
7. 2018 `CG` and `PB` reference-only active rows should not contribute to accuracy denominator.
8. 2018 database next-year support rows should not contribute to active 2018 scoring denominator.

## Recommended Join Treatment

The scorer should still prefer:

`draw_design + hunt_code + residency + points`

For 2017=2018, add a pre-join normalization layer:

1. Load exact hunt-code identity.
2. Load approved 2017->2018 crosswalk rows if/when promoted.
3. Mark candidate/unapproved successor rows as `STRUCTURAL_ALIGNMENT_REVIEW`, not `MISSING_PREDICTION`.
4. Exclude official reference-only rows from the accuracy denominator.
5. Keep extra generated prediction rows as cleanup diagnostics.

Proposed `structural_join_status` values for this year:

- `EXACT_HUNT_CODE_MATCH`
- `APPROVED_HISTORICAL_CROSSWALK_MATCH`
- `TARGET_YEAR_ONLY_NO_SOURCE_YEAR_PREDECESSOR`
- `SOURCE_YEAR_ONLY_NO_TARGET_YEAR_SUCCESSOR`
- `STRUCTURAL_ALIGNMENT_REVIEW`
- `REFERENCE_ONLY_NOT_SCORABLE`
- `DATABASE_NEXT_YEAR_SUPPORT_NOT_SCORABLE`

## Why This Matters For "All Possible Rows Scored"

All possible rows does not mean every row in every PDF-like artifact. It means every official, scorable, actual ladder row that has a legitimate prediction-side structural target should either:

- score by exact key,
- score by approved historical crosswalk key,
- be classified as a target-only structural exception.

For 2017=2018, the denominator should increase when crosswalks are approved for real same-hunt/split rows. It should not increase because regulation-only cougar/pronghorn rows, support rows, allocation/reference rows, or target-only rows are forced into accuracy as misses.

## Next Implementation Step

Create a reviewed 2017->2018 crosswalk file only for source-confirmed transitions. Good first entries to review are:

- `RS1000 -> RS0001`
- `TK1000 -> TK0001`
- `DA1003 -> DA1038`
- `EA1083 -> EA1197`
- `GO6812 -> GO6818/GO6819/GO6820` as a split, if the engine can support one-to-many structural transitions
- `CG7600 -> CG1030` and possibly `CG1031` as a split, source-review required
- `CG7504 -> CG1029` and possibly `CG1032` as a split, source-review required

Until approved, those rows should be visible in diagnostics but not silently counted as ordinary missing predictions.
