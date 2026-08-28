# Utah Draw Design Baseline and Engine Evaluation

Status: Current official baseline
Verified: 2026-08-26
Scope: Utah DWR public permit systems represented by Hunt Builder

This document is the source-backed design authority for draw-family routing. It does not replace annual permit tables, official results, or normalized scoring truth. Annual facts such as hunt codes, permit counts, resident/nonresident allotments, and season dates must come from the applicable current official source.

## Non-negotiable model order

1. Identify the official permit program and whether it is a drawing, availability system, allocation, or reference row.
2. Identify the parent draw design: bonus, preference, random-only, or no draw.
3. Apply youth, Dedicated Hunter, CWMU, residency, group, and choice-order rules as overlays on the parent design.
4. Use the official current resident and nonresident quota lanes. An explicit official split controls. A total permit count may be split only when the draw family has a documented annual allocation rule; special allocations and unsupported total-only rows must block.
5. Roll the latest unsuccessful applicants forward one point. The just-missed high-point cohort is the primary applicant-demand anchor because it is the most mechanically and behaviorally stable population.
6. Estimate lower-point additions, switching, and attrition only from earlier year-to-year evidence. They are secondary to the latest unsuccessful cohort.
7. Score predictions only against following-year official scorable draw results. Retention, switching, calibration, and any blend weight must survive blind backtesting.

## Official design matrix

| Permit program | Parent design | Point and selection mechanics | Residency and overlay rules | Engine owner | Current evaluation |
|---|---|---|---|---|---|
| Limited-entry buck deer, bull elk, and buck pronghorn, including management and eligible public CWMU lanes | Bonus | Odd permit pools round toward the max-point side; remaining permits use weighted random numbers, one for the application plus one per bonus point | Resident and nonresident quotas are separate. Nonresidents cannot apply for CWMU permits through the big-game drawing. Eligible leftover limited-entry deer, elk, and pronghorn quotas may cross over only in the later official evaluation | `engine/utah_bonus_predictive` plus family routing | Substantially implemented; unsupported total-only rows now block instead of using historical winner share |
| Once-in-a-lifetime bull moose, bison, ram bighorn sheep, and mountain goat | Bonus | Same max-point plus weighted-random mechanics; group applications are not accepted | Separate resident/nonresident lanes; lifetime restrictions remain an eligibility rule | `engine/utah_bonus_predictive` | Substantially implemented; residency-source guardrail still required |
| Antlerless moose and ewe Rocky Mountain or desert bighorn sheep | Bonus | Same bonus-point mechanics | Youth preference reserve does not apply | `engine/utah_draw_predictive/special_bonus.py` | Implemented, subject to hydrated official history and residency quota evidence |
| Black bear limited-entry hunting permits | Bonus | Bear hunting bonus points; max-point plus weighted-random drawing | Resident/nonresident lanes are separate; no group applications | `engine/utah_draw_predictive/bear.py` | Implemented; official bear reports are hydrated and subtype/history scoring remains subject to normal canonical validation |
| Black bear restricted pursuit permits | Bonus | Restricted pursuit has its own bonus point and is awarded through the black bear drawing | This is not the same as a hunting permit. In 2026, spring pursuit on Book Cliffs, La Sal, and San Juan is restricted for nonresidents and draw-only, while resident spring pursuit there is available by purchased pursuit permit. Summer restricted pursuit remains permit-specific | `engine/utah_draw_predictive/bear.py` | Implemented as a source-corrected bear subtype; durable routing previously under-described and now explicit |
| Bear harvest-objective hunting permits | No draw; quota-controlled availability | Permit purchase is not a draw probability; a unit closes when its harvest objective is met or the season ends | Available to eligible residents and nonresidents; closure risk is not `p_draw` | `engine/utah_draw_predictive/bear.py` | Correctly separated from draw probability |
| General bear pursuit permits | No draw; purchased availability | Permit authorizes pursuit, not harvest, on nonrestricted opportunity described by the guidebook | Resident and nonresident use restrictions differ on restricted units and seasons | `engine/utah_draw_predictive/bear.py` | Correctly separated, but output naming should consistently say general pursuit rather than imply a draw |
| Limited-entry wild turkey | Bonus | Turkey bonus points and a max-point pass followed by weighted selection without replacement from applicants still unawarded | Adult and youth source pools remain distinct even when DWR uses the same hunt code. Youth applicants are considered in the up-to-15% youth set-aside and use bonus points there | `engine/utah_draw_predictive/turkey.py` | Implemented with a separate youth set-aside overlay |
| General-season buck deer | Preference | Highest preference-point applicants are processed first. All first choices are evaluated before later choices | Lifetime and Dedicated Hunter lanes are processed first; up to 20% of the remaining general deer permits are reserved for youth, and unsuccessful youth continue into the main draw | `engine/utah_draw_predictive/preference_general_deer.py` and `youth.py` | Parent design is correct; public reports cover first-choice odds, so later-choice public probability remains limited |
| Dedicated Hunter buck deer | Preference | Separate Dedicated Hunter preference points and draw lane | Up to 15% of the general deer quota is used by the program, inclusive of active enrollments; youth receive up to 20% of the remaining Dedicated Hunter allotment | `engine/utah_draw_predictive/dedicated_hunter.py` | Separate lane is implemented; quota derivation must be checked against the 15% rule rather than inferred solely from winners |
| Antlerless deer, antlerless elk, and doe pronghorn | Preference | Highest preference-point applicants first, then later choices | Up to 20% is reserved for youth; unsuccessful youth continue into the main preference draw | `engine/utah_draw_predictive/preference_antlerless.py` and `youth.py` | Implemented with explicit split precedence and allowlisted official total-allocation fallback |
| Youth draw-only general any-bull or hunter's-choice elk | Random-only | Preference points are neither awarded nor used | Youth-only eligibility; separate from over-the-counter youth elk permits | `engine/utah_draw_predictive/youth.py` | Correct design exists; EB1007 materialization drift remains open |
| Sportsman permits | Random-only | One permit for each current species; no bonus points | Resident-only; an applicant may draw no more than one Sportsman species | `engine/utah_draw_predictive/sportsman.py` | Current 10-species design is correct; historical cougar applies only through 2022 and must remain year-aware |
| Private-lands-only antlerless elk, remaining permits, general-season elk sold over the counter, and similar capped sales | No original draw probability | First-come, capped, or remaining availability | Residency restrictions come from the sale/program source, not draw odds | allocation and availability modules | Correctly excluded from `p_draw`; status naming drift remains open |
| Cougar hunting in 2026 | No drawing | A valid hunting or combination license authorizes opportunity under current cougar rules | No current cougar permit drawing or current cougar bonus-point probability | `engine/utah_draw_predictive/mountain_lion.py` | Correctly modeled as license-based reference, not draw probability |

## Resident and nonresident rules the engines must preserve

- Only residents may apply in a resident lane and only nonresidents may apply in a nonresident lane.
- The same hunt code can have different resident and nonresident quotas, applicant ladders, max-point pools, and random pools. Probabilities must be calculated within the applicable lane.
- An odd bonus pool gives the extra permit to the max-point side. A one-permit nonresident pool is the documented exception: that permit is issued randomly after the bonus-point round.
- A mixed resident/nonresident group is constrained by the nonresident quota. A group cannot consume a one-permit nonresident lane when its nonresident membership exceeds the available lane.
- Public CWMU drawing access is resident-only; nonresidents obtain CWMU opportunity from the operator, not the public drawing.
- Sportsman permits are resident-only.
- Cross-over is not a general license to merge residency pools. For the eligible limited-entry big-game programs, it occurs only after the separate resident and nonresident evaluations leave permits.
- Historical resident/nonresident winner share is prohibited as current quota authority. The shared resolver accepts an explicit official split first, then an allowlisted source-backed allocation rule for supported total-only families; every other total-only family blocks.

## Applicant behavior priority

The current cohort architecture is directionally correct:

- prior winners are removed;
- prior unsuccessful applicants advance one point;
- high-point bands use higher reapplication priors than low-point bands;
- the mixed cutoff and just-missed cohort receive their own retention calibration;
- lower-point additions and switching are estimated separately.

The 2025-to-2026 blind audit now performs this comparison. It scores the declared just-missed successor cohort against following-year actual applicant counts and against both prior-same-point and pure prior-unsuccessful-rollforward baselines. A proposed weight must improve paired rows by draw family and residency; an unpaired aggregate improvement is not promotion evidence.

## Evaluation findings

### Correct or substantially correct

- Separate bonus, preference, Sportsman/random-only, youth-overlay, allocation, and availability modules exist.
- Bear hunting, restricted pursuit, harvest-objective, and general pursuit subtypes exist in `bear.py`; the earlier project memory simply failed to state the distinction clearly.
- Current cougar, Sportsman, turkey youth, youth general-any-bull elk, and private-lands antlerless behavior are conceptually routed to the right kind of output.
- The forecast stack already rolls unsuccessful applicants forward and gives high-point bands stronger retention than low-point bands.

### Corrected in the 2026-08-26 baseline pass

- Semicolon-delimited design plus modifier labels are normalized to one parent design for routing.
- The bonus split is residency-aware: a resident one-permit pool is not globally forced to random-only, while the documented nonresident exception remains random-only.
- Odd bonus totals in the deterministic foundation round toward the max-point pool.
- Missing repo-external bear draw-odds evidence now creates an explicit blocker instead of crashing unrelated classification.
- The durable project memory now defines draw-family routing, bear subtypes, residency overlays, and last-year unsuccessful cohort priority.

### Still blocks certification

- Historical winner-share residency fallback has been removed from the family builders. Explicit official splits override all derived values; the central resolver applies approved total-allocation rules only to allowlisted standard preference families and blocks unsupported special families.
- The generic deterministic simulator has global bonus max/random counters layered over residency buckets; it does not yet perform a fully separate resident round, nonresident round, and later eligible cross-over sequence.
- Public preference reports state that published odds reflect first choices. Exact second-through-fifth-choice probabilities are not fully observable from those reports.
- The rebuilt output still contains duplicate bonus prediction identities and the blind join has unexpected key gaps; these block promotion.
- The official 2018 reports are hydrated, but their legacy table layout needs a dedicated parser before they can be promoted into canonical truth.

## Official sources

- Utah DWR permit drawing explanation: https://wildlife.utah.gov/licenses/permits
- Utah DWR bonus and preference points: https://wildlife.utah.gov/licenses/points
- Utah Administrative Rule R657-62: https://wildlife.utah.gov/rules/r657-62
- 2026 Utah Big Game Application Guidebook: https://wildlife.utah.gov/guidebooks/biggameapp.pdf
- 2026 Utah Antlerless Application Guidebook: https://wildlife.utah.gov/guidebooks/antlerless_guidebook.pdf
- 2026 Utah Black Bear, Cougar and Furbearer Guidebook: https://wildlife.utah.gov/guidebooks/black-bear-cougar-furbearer-guidebook.pdf
- Utah DWR group applications: https://wildlife.utah.gov/licenses/groups
- Utah Administrative Rule R657-5: https://wildlife.utah.gov/rules/r657-05
- Utah DWR Sportsman permits: https://wildlife.utah.gov/sportsmanpermits
- Utah DWR historical drawing odds: https://wildlife.utah.gov/odds
- Utah DWR historical big-game drawing odds: https://wildlife.utah.gov/biggame/odds
- Utah DWR current big-game guidebook hub: https://wildlife.utah.gov/biggame
- UtahDraws current drawing-odds portal: https://www.utahdraws.com/internetsales/home/drawodds
- Utah DWR limited-entry landowner association list: https://wildlife.utah.gov/landowners
- Utah DWR annual big-game, bear, cougar and furbearer reports: https://wildlife.utah.gov/hunting/reports
- Utah DWR big-game harvest and survey dashboards: https://wildlife.utah.gov/biggame/reports
- Utah Wildlife Board December 2021 packet documenting odd bonus-pool allocation: https://wildlife.utah.gov/public_meetings/board/2021-12-board-packet.pdf
- 2025 official black bear draw results showing resident bonus/regular allocations: https://wildlife.utah.gov/pdf/bear/25_drawing_odds.pdf
