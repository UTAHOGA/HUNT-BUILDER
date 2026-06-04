# Current Online Missing Hunt Codes 2026

- Snapshot UTC: `2026-05-26T17:12:46+00:00`
- Live DWR hunt-number count: `1422`
- Live selected table rows: `227`
- DATABASE row count: `1394`
- DATABASE codes not present in live DWR Hunt Planner list: `0`
- Missing-code rows with blank DATABASE boundary IDs: `0`
- User-reported missing codes still in DATABASE and absent online: `none`
- User-reported missing codes retired from DATABASE: `EA1007, EA1053, PD1039`

This is a hunt-code presence problem, not a boundary-ID gap. All rows remaining in this audit have a populated DATABASE boundary ID.

## High Priority

- No high-priority user-reported missing codes remain in DATABASE.

## Full Missing Set


## Recommendation

Treat these rows as RAC/local evidence only until a current online DWR export confirms the hunt codes. Do not delete numeric cells from DATABASE.csv based on this audit alone, but do not promote these codes as live-online-current rows either.
