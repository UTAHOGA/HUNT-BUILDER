# Bear 2026 Target Hunt-Code Crosswalk Audit

- Target rows audited: `7`.
- Alias to historical code: `4`.
- Current split/new rows not aliased: `3`.
- Active-code collision rows not aliased: `0`.

Weapon normalization: Any Legal Weapon and multiseason/multi-season normalize together for alignment; season family remains confidence metadata.

| current code | current hunt | season family | permits | action | history code | reason |
|---|---|---:|---:|---|---|---|
| BR7021 | Dolores Triangle | spring | 2/0/2 | DO_NOT_ALIAS_CURRENT_SPLIT_CHILD |  | No tight historical hunt-name/code predecessor; treat as current 2026 split/addition and use 2026 draw-result history for 2027+. Related historical-looking code BR7008 is not used as this row's predecessor under the hand-audited crosswalk lock. |
| BR7126 | Dolores Triangle | summer | 6/0/6 | DO_NOT_ALIAS_CURRENT_SPLIT_CHILD |  | No tight historical hunt-name/code predecessor; treat as current 2026 split/addition and use 2026 draw-result history for 2027+. Related historical-looking code BR7108 is not used as this row's predecessor under the hand-audited crosswalk lock. |
| BR7238 | Dolores Triangle | fall | 2/0/2 | DO_NOT_ALIAS_CURRENT_SPLIT_CHILD |  | No tight historical hunt-name/code predecessor; treat as current 2026 split/addition and use 2026 draw-result history for 2027+. Related historical-looking code BR7208 is not used as this row's predecessor under the hand-audited crosswalk lock. |
| BR7022 | La Sal Mtns | spring | 40/3/43 | ALIAS_TO_HISTORICAL_CODE | BR7008 | Hand-audited DWR source lock: historical BR7008 crosswalks to current BR7022. |
| BR7127 | La Sal Mtns | summer | 25/2/27 | ALIAS_TO_HISTORICAL_CODE | BR7108 | Hand-audited DWR source lock: historical BR7108 crosswalks to current BR7127. |
| BR7239 | La Sal Mtns | fall | 6/0/6 | ALIAS_TO_HISTORICAL_CODE | BR7208 | Hand-audited DWR source lock: historical BR7208 crosswalks to current BR7239. |
| BR7326 | La Sal Mtns | multiseason | 13/1/14 | ALIAS_TO_HISTORICAL_CODE | BR7307 | Hand-audited DWR source lock: historical BR7307 crosswalks to current BR7326. BR7307 is reused for conservation in 2026. |
