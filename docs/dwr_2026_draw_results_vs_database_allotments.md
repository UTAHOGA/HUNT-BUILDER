# DWR 2026 Draw Results vs DATABASE Allotment Audit

## Scope
- Compared the provisional 2026 DWR/UtahDraws draw-results pull to `DATABASE.csv` allotment fields.
- Source fields: `QuotaQuantity`, `ResidentQuotaQuantity`, `NonResidentQuotaQuantity` from the generated 2026 CSV exports.
- DATABASE fields: `permit_allotment_2026_total`, `permit_allotment_2026_res`, `permit_allotment_2026_nr`.
- This audit does not promote the 2026 draw-results pull as truth and does not modify `DATABASE.csv`.

## Key Counts
- Input source CSV files: `25`
- Source hunt codes: `834`
- DATABASE hunt codes: `1449`
- Union hunt codes compared: `1449`

## Comparison Status Counts
- `DATABASE_HAS_VALUE_SOURCE_BLANK`: `2`
- `DATABASE_ONLY_NOT_IN_SOURCE_PULL`: `615`
- `MATCH_ALL_COMPARABLE`: `580`
- `MISMATCH_NR_TOTAL`: `8`
- `MISMATCH_RES_NR_TOTAL`: `32`
- `MISMATCH_RES_TOTAL`: `68`
- `MISMATCH_TOTAL`: `137`
- `SOURCE_HAS_VALUE_DATABASE_BLANK`: `7`

## Important Interpretation
- `DATABASE.csv` remains authoritative for current allotment values.
- The 2026 draw-results pull appears to cover a narrower draw-results universe than the full current hunt-code universe.
- `DATABASE_ONLY_NOT_IN_SOURCE_PULL` rows are not automatically defects; they may be current application/allotment rows that are absent from this provisional draw-results pull.
- `SOURCE_ONLY_NOT_IN_DATABASE` rows need review before promotion or crosswalk action.

## Source-Only Hunt Codes
- None.

## Mismatches
- `BI6503` `MISMATCH_RES_TOTAL`: source `3/2/5` vs DB `4/2/6`
- `BI6505` `MISMATCH_NR_TOTAL`: source `8/2/10` vs DB `8/3/11`
- `BI6531` `MISMATCH_RES_TOTAL`: source `9/0/9` vs DB `10/0/10`
- `BI6536` `MISMATCH_RES_TOTAL`: source `14/0/14` vs DB `15/0/15`
- `DB0008` `MISMATCH_TOTAL`: source `1781/197/2016` vs DB `//2000`
- `DB1001` `MISMATCH_RES_TOTAL`: source `25/3/28` vs DB `26/3/29`
- `DB1003` `MISMATCH_RES_TOTAL`: source `23/3/26` vs DB `24/3/27`
- `DB1004` `MISMATCH_RES_NR_TOTAL`: source `73/7/80` vs DB `75/8/83`
- `DB1006` `MISMATCH_RES_TOTAL`: source `25/3/28` vs DB `26/3/29`
- `DB1010` `MISMATCH_RES_TOTAL`: source `29/3/32` vs DB `30/3/33`
- `DB1011` `MISMATCH_RES_NR_TOTAL`: source `54/5/59` vs DB `55/6/61`
- `DB1015` `MISMATCH_RES_TOTAL`: source `21/2/23` vs DB `22/2/24`
- `DB1016` `MISMATCH_RES_NR_TOTAL`: source `44/4/48` vs DB `46/5/51`
- `DB1017` `MISMATCH_RES_NR_TOTAL`: source `134/14/148` vs DB `137/15/152`
- `DB1018` `MISMATCH_RES_NR_TOTAL`: source `32/3/35` vs DB `34/4/38`
- `DB1019` `MISMATCH_RES_TOTAL`: source `31/4/35` vs DB `33/4/37`
- `DB1022` `MISMATCH_RES_NR_TOTAL`: source `41/4/45` vs DB `42/5/47`
- `DB1023` `MISMATCH_RES_NR_TOTAL`: source `59/6/65` vs DB `61/7/68`
- `DB1024` `MISMATCH_RES_NR_TOTAL`: source `127/13/140` vs DB `130/14/144`
- `DB1025` `MISMATCH_RES_NR_TOTAL`: source `53/5/58` vs DB `55/6/61`
- `DB1026` `MISMATCH_RES_TOTAL`: source `7/1/8` vs DB `8/1/9`
- `DB1034` `MISMATCH_RES_TOTAL`: source `12/2/14` vs DB `13/2/15`
- `DB1038` `MISMATCH_RES_TOTAL`: source `21/2/23` vs DB `22/2/24`
- `DB1041` `MISMATCH_RES_TOTAL`: source `29/3/32` vs DB `30/3/33`
- `DB1042` `MISMATCH_RES_NR_TOTAL`: source `45/4/49` vs DB `46/5/51`
- `DB1043` `MISMATCH_RES_TOTAL`: source `14/2/16` vs DB `15/2/17`
- `DB1079` `MISMATCH_RES_TOTAL`: source `39/5/44` vs DB `40/5/45`
- `DB1087` `MISMATCH_RES_TOTAL`: source `35/4/39` vs DB `36/4/40`
- `DB1501` `MISMATCH_TOTAL`: source `802/89/909` vs DB `//1040`
- `DB1502` `MISMATCH_TOTAL`: source `836/93/991` vs DB `//1160`
- `DB1503` `MISMATCH_TOTAL`: source `1081/120/1341` vs DB `//1800`
- `DB1504` `MISMATCH_TOTAL`: source `683/76/782` vs DB `//1060`
- `DB1506` `MISMATCH_TOTAL`: source `274/31/338` vs DB `//460`
- `DB1508` `MISMATCH_TOTAL`: source `128/14/149` vs DB `//200`
- `DB1509` `MISMATCH_TOTAL`: source `220/25/265` vs DB `//360`
- `DB1510` `MISMATCH_TOTAL`: source `132/15/180` vs DB `//220`
- `DB1511` `MISMATCH_TOTAL`: source `45/5/53` vs DB `//80`
- `DB1512` `MISMATCH_TOTAL`: source `170/19/201` vs DB `//280`
- `DB1513` `MISMATCH_TOTAL`: source `424/47/513` vs DB `//620`
- `DB1514` `MISMATCH_TOTAL`: source `377/42/438` vs DB `//540`
- `DB1516` `MISMATCH_TOTAL`: source `295/33/410` vs DB `//500`
- `DB1517` `MISMATCH_TOTAL`: source `341/38/430` vs DB `//600`
- `DB1518` `MISMATCH_TOTAL`: source `457/51/557` vs DB `//720`
- `DB1519` `MISMATCH_TOTAL`: source `148/17/193` vs DB `//260`
- `DB1521` `MISMATCH_TOTAL`: source `392/44/464` vs DB `//560`
- `DB1522` `MISMATCH_TOTAL`: source `251/28/344` vs DB `//420`
- `DB1523` `MISMATCH_TOTAL`: source `166/19/211` vs DB `//280`
- `DB1524` `MISMATCH_TOTAL`: source `57/7/77` vs DB `//100`
- `DB1525` `MISMATCH_TOTAL`: source `802/89/953` vs DB `//1300`
- `DB1526` `MISMATCH_TOTAL`: source `1129/126/1324` vs DB `//1580`
- `DB1529` `MISMATCH_TOTAL`: source `392/44/470` vs DB `//675`
- `DB1531` `MISMATCH_TOTAL`: source `1603/178/2269` vs DB `//2080`
- `DB1533` `MISMATCH_TOTAL`: source `3241/360/5047` vs DB `//5400`
- `DB1534` `MISMATCH_TOTAL`: source `2045/227/3064` vs DB `//3180`
- `DB1536` `MISMATCH_TOTAL`: source `547/59/916` vs DB `//920`
- `DB1538` `MISMATCH_TOTAL`: source `254/28/394` vs DB `//400`
- `DB1539` `MISMATCH_TOTAL`: source `660/72/1010` vs DB `//1080`
- `DB1540` `MISMATCH_TOTAL`: source `393/42/637` vs DB `//660`
- `DB1541` `MISMATCH_TOTAL`: source `135/14/242` vs DB `//240`
- `DB1542` `MISMATCH_TOTAL`: source `336/36/564` vs DB `//560`
- `DB1543` `MISMATCH_TOTAL`: source `848/94/1280` vs DB `//1240`
- `DB1544` `MISMATCH_TOTAL`: source `1131/125/1646` vs DB `//1620`
- `DB1546` `MISMATCH_TOTAL`: source `588/64/905` vs DB `//1000`
- `DB1547` `MISMATCH_TOTAL`: source `680/75/1247` vs DB `//1200`
- `DB1549` `MISMATCH_TOTAL`: source `296/31/502` vs DB `//520`
- `DB1551` `MISMATCH_TOTAL`: source `1172/129/1661` vs DB `//1680`
- `DB1552` `MISMATCH_TOTAL`: source `417/45/638` vs DB `//700`
- `DB1553` `MISMATCH_TOTAL`: source `497/54/756` vs DB `//840`
- `DB1554` `MISMATCH_TOTAL`: source `170/17/285` vs DB `//300`
- `DB1555` `MISMATCH_TOTAL`: source `2404/267/3690` vs DB `//3900`
- `DB1556` `MISMATCH_TOTAL`: source `3386/375/4677` vs DB `//4740`
- `DB1559` `MISMATCH_TOTAL`: source `780/85/1407` vs DB `//1350`
- `DB1561` `MISMATCH_TOTAL`: source `802/89/909` vs DB `//1040`
- `DB1563` `MISMATCH_TOTAL`: source `1081/120/1437` vs DB `//1800`
- `DB1564` `MISMATCH_TOTAL`: source `683/76/803` vs DB `//1060`
- `DB1566` `MISMATCH_TOTAL`: source `274/31/365` vs DB `//460`
- `DB1568` `MISMATCH_TOTAL`: source `128/14/153` vs DB `//200`
- `DB1569` `MISMATCH_TOTAL`: source `220/25/297` vs DB `//360`
- `DB1570` `MISMATCH_TOTAL`: source `132/15/216` vs DB `//220`
- `DB1571` `MISMATCH_TOTAL`: source `45/5/71` vs DB `//80`
- `DB1572` `MISMATCH_TOTAL`: source `170/19/200` vs DB `//280`
- `DB1573` `MISMATCH_TOTAL`: source `424/47/518` vs DB `//620`
- `DB1574` `MISMATCH_TOTAL`: source `377/42/449` vs DB `//540`
- `DB1576` `MISMATCH_TOTAL`: source `295/33/443` vs DB `//500`
- `DB1577` `MISMATCH_TOTAL`: source `341/38/495` vs DB `//600`
- `DB1579` `MISMATCH_TOTAL`: source `148/17/231` vs DB `//260`
- `DB1581` `MISMATCH_TOTAL`: source `392/44/484` vs DB `//560`
- `DB1582` `MISMATCH_TOTAL`: source `168/19/252` vs DB `//280`
- `DB1583` `MISMATCH_TOTAL`: source `166/19/244` vs DB `//280`
- `DB1584` `MISMATCH_TOTAL`: source `57/7/91` vs DB `//100`
- `DB1585` `MISMATCH_TOTAL`: source `802/89/999` vs DB `//1300`
- `DB1586` `MISMATCH_TOTAL`: source `1129/126/1287` vs DB `//1580`
- `DB1589` `MISMATCH_TOTAL`: source `392/44/496` vs DB `//675`
- `DB1591` `MISMATCH_TOTAL`: source `274/31/401` vs DB `//460`
- `DB1592` `MISMATCH_TOTAL`: source `128/14/182` vs DB `//200`
- `DB1593` `MISMATCH_TOTAL`: source `170/19/242` vs DB `//280`
- `DB1594` `MISMATCH_TOTAL`: source `295/33/454` vs DB `//500`
- `DB1595` `MISMATCH_TOTAL`: source `341/38/533` vs DB `//600`
- `DB1596` `MISMATCH_TOTAL`: source `148/17/237` vs DB `//260`
- `DB1597` `MISMATCH_TOTAL`: source `392/44/577` vs DB `//675`

## Database-Only Coverage
- DATABASE-only rows: `615`
- Review the CSV for details; this is expected to include current rows outside this draw-results pull.

## Outputs
- `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\processed_data\audits\dwr_2026_draw_results_vs_database_allotments.csv`
- `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\processed_data\audits\dwr_2026_draw_results_vs_database_allotments_summary.json`
