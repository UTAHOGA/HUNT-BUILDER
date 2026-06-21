# Utah Draw System Scope

Formula and routing contract:

- See `docs/utah_draw_routing_and_algorithm_v1.md` for the active selector-to-engine routing rule, quota resolution formula, bonus/preference/youth formulas, and the `hunt_class` visibility rule.

## Target Scope

The approved predictive-engine universe is limited to:

- Big game
- Turkey
- Bear
- Mountain lion / cougar

Target-scope big-game families include:

- Deer
- Elk
- Pronghorn
- Moose
- Bison
- Bighorn sheep
- Mountain goat
- Antlerless deer
- Antlerless elk
- Doe pronghorn
- Antlerless moose
- Ewe bighorn sheep
- CWMU public big-game permits where present
- Limited-entry big game
- Premium limited-entry big game
- Once-in-a-lifetime big game
- General-season big-game draw categories
- Dedicated Hunter deer where present, with the hunt type kept visible even though the draw system resolves as preference
- Youth big-game draw categories where present
- Landowner big-game categories where present
- Mitigation / depredation big-game categories where present
- Remaining-permit big-game categories where present
- Private-lands-only antlerless elk where present

## Out Of Scope

These categories must be classified as `OUT_OF_SCOPE_NON_TARGET` when they appear:

- Swan
- Sandhill crane
- Grouse species categories such as sharp-tailed grouse and sage grouse
- Waterfowl
- Upland game other than turkey
- Small game
- Fishing
- Other non-target wildlife categories

Important guardrail:

- Geographic names must not trigger out-of-scope classification by themselves.
- Example: `Box Elder, Grouse Creek` elk rows remain target-scope big-game rows.
- `OUT_OF_SCOPE_NON_TARGET` rows stay in coverage and audit artifacts, but they must not appear in the standard Hunt Research prediction view unless audit/debug mode is enabled.

## Classifier Values

- `BONUS_OIL_BIG_GAME`
- `BONUS_LE_BIG_GAME`
- `BONUS_PLE_BIG_GAME`
- `BONUS_CWMU_BIG_GAME`
- `BONUS_ANTLERLESS_MOOSE`
- `BONUS_EWE_BIGHORN`
- `BONUS_TURKEY`
- `SPORTSMAN_PERMIT`
- `PREFERENCE_GENERAL_SEASON_BUCK_DEER`
- `PREFERENCE_DEDICATED_HUNTER_DEER`
- `PREFERENCE_ANTLERLESS_DEER`
- `PREFERENCE_ANTLERLESS_ELK`
- `PREFERENCE_DOE_PRONGHORN`
- `GENERAL_BIG_GAME_OTHER`
- `BEAR_DRAW`
- `MOUNTAIN_LION_DRAW`
- `PRIVATE_LANDS_ONLY_ANTLERLESS_ELK`
- `YOUTH_GENERAL_DEER_RESERVE`
- `YOUTH_ANTLERLESS_OR_DOE_RESERVE`
- `YOUTH_DRAW_ONLY_ELK`
- `YOUTH_OTC_OR_AVAILABILITY`
- `RANDOM_ONLY_TARGET`
- `OTC_OR_REMAINING_TARGET`
- `LANDOWNER_BIG_GAME`
- `MITIGATION_OR_DEPREDATION_BIG_GAME`
- `UNKNOWN_TARGET`
- `OUT_OF_SCOPE_NON_TARGET`

## Algorithm Status Values

- `MODELED_BONUS`
- `MODELED_PREFERENCE`
- `MODELED_ALLOCATION`
- `MODELED_AVAILABILITY`
- `MODELED_RANDOM_ONLY`
- `IN_SCOPE_MODEL_PENDING`
- `EXCLUDED_NOT_PREDICTIVE_DRAW`
- `OUT_OF_SCOPE_NON_TARGET`
- `UNKNOWN_TARGET_NEEDS_REVIEW`

## Current Bonus Engine Usage

The accepted production predictive engine currently models:

- `BONUS_OIL_BIG_GAME`
- `BONUS_LE_BIG_GAME`
- `BONUS_PLE_BIG_GAME`

Preserved behavior:

- One permit by hunt/residency goes to the random/regular side, not max-point.
- `7` permits split `4 max / 3 random`.
- `9` permits split `5 max / 4 random`.
- EB3024 regression remains required.
- `MAX POOL` is descriptive only and must not force `100%`.
- UI odds precedence remains:
  1. `display_odds_pct`
  2. `p_draw_mean * 100`
  3. `odds_2026_projected`
  4. `max_pool_projection_2026`
  5. `random_draw_odds_2026`
  6. `random_draw_projection_2026`
  7. `Not available`
- User-facing draw odds should render in combined `~1 in X or Y%` format rather than percent-only text.

## Categories Requiring Preference Or Other Strategy

These categories must not use the OIL/LE/PLE bonus algorithm:

- `PREFERENCE_GENERAL_SEASON_BUCK_DEER`
- `PREFERENCE_DEDICATED_HUNTER_DEER`
- `PREFERENCE_ANTLERLESS_DEER`
- `PREFERENCE_ANTLERLESS_ELK`
- `PREFERENCE_DOE_PRONGHORN`
- `BEAR_DRAW`
- `MOUNTAIN_LION_DRAW`
- `PRIVATE_LANDS_ONLY_ANTLERLESS_ELK`
- `YOUTH_GENERAL_DEER_RESERVE`
- `YOUTH_ANTLERLESS_OR_DOE_RESERVE`
- `YOUTH_DRAW_ONLY_ELK`
- `YOUTH_OTC_OR_AVAILABILITY`

Reason:

- General-season deer and antlerless deer/elk/doe pronghorn are preference-point systems, not OIL/LE/PLE bonus systems.
- Mountain lion/cougar uses a rule-status and O.T.C. / allotment strategy for 2026, not a draw-odds model.

## Current State

The predictive stack is intentionally split into separate engines by draw family. The current contract does not treat these as one blended model:

- bonus / max-weighted split engine
- preference engine
- sportsman random engine
- O.T.C. / allotment engine

Completed:

- Phase 1: OIL / LE / PLE bonus engine
- Phase 2: target-scope classifier and guardrails
- Phase 3: general-season buck deer preference engine
- Phase 4: antlerless deer / antlerless elk / doe pronghorn preference engine
- Phase 5: Dedicated Hunter deer preference engine
- Phase 6: CWMU public + antlerless moose + ewe bighorn bonus families
- Phase 7: limited-entry turkey bonus strategy
- Phase 8: public bear bonus strategy + Sportsman permit classifier
- Phase 9: private-lands-only antlerless elk allocation / allotment strategy
- Phase 10: mountain lion / cougar rule-status + allotment strategy
- Phase 11: Sportsman permit odds strategy
- Phase 12: bear subtype-aware quota draw + allotment strategy
- Phase 13: mountain lion / cougar rule-status + allotment closeout
- Phase 14: private-lands-only antlerless elk allocation / allotment closeout
- Phase 15: youth family separation and pending-strategy closeout

Currently modeled as `MODELED_BONUS`:

- `BONUS_OIL_BIG_GAME`
- `BONUS_LE_BIG_GAME`
- `BONUS_PLE_BIG_GAME`
- `BONUS_CWMU_BIG_GAME`
- `BONUS_ANTLERLESS_MOOSE`
- `BONUS_EWE_BIGHORN`
- `BONUS_TURKEY`
- `BEAR_DRAW`

Currently modeled as `MODELED_PREFERENCE`:

- `PREFERENCE_GENERAL_SEASON_BUCK_DEER`
- `PREFERENCE_ANTLERLESS_DEER`
- `PREFERENCE_ANTLERLESS_ELK`
- `PREFERENCE_DOE_PRONGHORN`
- `PREFERENCE_DEDICATED_HUNTER_DEER`

Currently modeled as `MODELED_ALLOCATION`:

- `PRIVATE_LANDS_ONLY_ANTLERLESS_ELK`

Currently modeled as O.T.C. / allotment-status rows (`MODELED_AVAILABILITY`):

- `MOUNTAIN_LION_DRAW`
- Bear availability/status subtypes inside `BEAR_DRAW`
  - `HARVEST_OBJECTIVE_AVAILABILITY`
  - `UNLIMITED_PURSUIT_PERMIT`

Currently modeled as `MODELED_SPORTSMAN_DRAW`:

- `SPORTSMAN_PERMIT`

Still pending:

- `YOUTH_GENERAL_DEER_RESERVE`
- `YOUTH_ANTLERLESS_OR_DOE_RESERVE`
- `YOUTH_DRAW_ONLY_ELK`
- `YOUTH_OTC_OR_AVAILABILITY`
- `GENERAL_BIG_GAME_OTHER`
- `RANDOM_ONLY_TARGET`
- `OTC_OR_REMAINING_TARGET`
- `LANDOWNER_BIG_GAME`
- `MITIGATION_OR_DEPREDATION_BIG_GAME`

Private-lands-only antlerless elk note:

- This category stays in scope.
- It is modeled as an O.T.C. / allocation / allotment family, not a preference-draw probability model.
- Phase 14 closes this family as an O.T.C. / allotment-status strategy with explicit status semantics when source support exists.
- It must not receive `p_draw`, `p_draw_pct`, `p_bonus_pool`, `p_random_pool`, or `p_preference_draw`.
- Allocation fields such as `permits_allotted`, `allocation_status`, `p_availability`, and `availability_pct` populate only when source data supports them.

Sportsman permit note:

- Sportsman permits are classified as their own statewide draw family.
- They are modeled from the official Sportsman odds source, not from hunt-code suffix rules.
- They do not use max/weighted split pools, preference points, max-point pools, or bear-availability logic.
- `BR1000`, `DB0007`, `RS0001`, and `TK0001` are all Sportsman permits even though not every Sportsman code ends with `1000`.

Bear note:

- `BR1000` remains `SPORTSMAN_PERMIT`, not `BEAR_DRAW`.
- Harvest objective and pursuit-only bear rows are surfaced as availability/rule-status rows, not draw odds.
- Bear availability/status rows must keep `p_draw`, `p_draw_pct`, `p_bonus_pool`, `p_random_pool`, and `p_preference_draw` null.
- Bear availability/status rows may use `permit_availability_type`, `availability_status`, `unit_status`, `rule_status`, `p_availability`, `availability_pct`, and explicit `reason_codes`.
- Only true limited-entry bear hunts remain in the bear bonus-draw path.

Mountain lion / cougar note:

- Utah cougar hunting is treated as statewide O.T.C. rule-status and allotment, not draw odds.
- The local geometry source lists management/reporting units used for check-in and harvest reporting.
- Phase 13 closes this family as an O.T.C. / allotment strategy with explicit rule-status reporting, not a draw-odds strategy.
- `MOUNTAIN_LION_DRAW` rows must not receive `p_draw`, `p_draw_pct`, `p_bonus_pool`, `p_random_pool`, or `p_preference_draw`.
- Allotment/status fields such as `permit_availability_type`, `season_start`, `season_end`, `unit_name`, `unit_status`, `p_availability`, and `availability_pct` are the user-facing outputs for this family.
- `MODELED_AVAILABILITY` is not draw odds and must stay documented as O.T.C. / allotment semantics only.

O.T.C. / allotment semantics note:

- `MODELED_AVAILABILITY` means source-supported rule-status / allotment reporting, not modeled draw probability.
- O.T.C. / allotment rows must keep `p_draw` and `p_draw_pct` null.
- The system must not fabricate bonus, preference, or draw-probability fields for O.T.C. / allotment rows.
- Any non-mountain-lion and non-bear O.T.C. / allotment rows must be explicitly documented in the allotment review artifacts before they can remain `MODELED_AVAILABILITY`.

Youth note:

- Youth is not one bucket. Youth rows split into `YOUTH_GENERAL_DEER_RESERVE`, `YOUTH_ANTLERLESS_OR_DOE_RESERVE`, `YOUTH_DRAW_ONLY_ELK`, and `YOUTH_OTC_OR_AVAILABILITY`.
- Youth general deer reserve, youth antlerless/doe reserve, and draw-only youth elk stay in scope and stay separate from adult general deer, adult antlerless/doe, and OIL / LE / PLE bonus families.
- Phase 15 closes the youth classifier and reporting pass, but the families remain pending unless the active-year youth mechanics are source-proven.
- `EB1007` is the current draw-only youth elk row and routes to `YOUTH_DRAW_ONLY_ELK`.
- `EB1011` is general-season youth elk O.T.C./purchase behavior and routes to `YOUTH_OTC_OR_AVAILABILITY`, not youth draw odds.
- Youth rows must not receive `p_draw`, `p_draw_pct`, `p_preference_draw`, `p_bonus_pool`, or `p_random_pool` until a defensible youth-specific strategy is accepted.

Out of scope:

- swan
- crane
- grouse
- waterfowl
- small game
- fishing
- non-turkey upland game
- other non-target wildlife categories
