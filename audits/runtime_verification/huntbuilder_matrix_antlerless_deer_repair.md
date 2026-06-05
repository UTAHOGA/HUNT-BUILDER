# Hunt Builder Antlerless Deer Matrix Repair

Generated: `2026-06-05T08:38:48.528Z`
Status: `PASS`

## Scenario
- Mobile viewport: `390 x 844`
- Start with hunt-code search: `DA1051`
- Change matrix to Species `Deer` and Sex `Antlerless`

## Results
- Search cleared after matrix change: `true`
- Deer sex options: `All, Buck, Antlerless, Either Sex`
- Antlerless Deer hunt-type options: `All, General Season, CWMU`
- Matching card count after Apply: `22`
- CWMU antlerless deer present in result text: `true`
- Mobile horizontal overflow: `PASS`

## Interpretation
Changing the matrix now clears stale hunt-code search state, so Deer + Antlerless + All is no longer locked to DA1051. Hunter's Choice rows render as Either Sex.
