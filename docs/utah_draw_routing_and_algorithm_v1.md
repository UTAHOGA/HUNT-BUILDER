# Utah Draw Routing And Algorithm V1

This document is the active `HUNT-BUILDER` contract for how a selected hunt row is routed into the correct Utah draw model. It explains why `hunt_class` exists, when it should be visible to the user, and what separate engine family should be used after the final hunt is selected.

The core rule is:

```text
species -> sex_type -> hunt_type -> weapon -> optional hunt_class -> hunt_code
```

`hunt_class` is not a duplicate label. It is only useful when it further separates rows that otherwise look the same but must route to different draw behavior. If `hunt_type` already fully explains the family, `hunt_class` should be hidden from the selector and carried only as metadata.

## Engine Families

The routing layer should hand each row to one of these separate engines:

- `Preference` engine for general-season, Dedicated Hunter, and other preference-point rows
- `Max/Weighted Split` engine for limited-entry and once-in-a-lifetime rows that split permits between a max-point pass and a weighted random pass
- `Random` engine for Sportsman rows
- `O.T.C.` / allotment engine for cougar, bear status rows, youth OTC rows, and other rule/status rows that are not true draw-odds rows

These are separate model paths, not just different labels on one generic probability engine.

Surface label rule for capped-permit rows:

- `hunt_type` displays as `O.T.C.`
- `draw_system` / `draw_design` displays as `Capped Permits`

## Source Anchors

Official DWR sources checked for this contract:

- Utah DWR permit drawings page: `https://wildlife.utah.gov/licenses/permits`
- Utah DWR bonus/preference points page: `https://wildlife.utah.gov/licenses/points`
- Utah DWR group applications page: `https://wildlife.utah.gov/group-applications`
- Utah DWR sportsman permits page: `https://wildlife.utah.gov/sportsmanpermits`
- Utah Admin Rule R657-5, youth elk sections: `https://wildlife.utah.gov/index.php/r657-5.html`
- Utah Admin Rule R657-55a, expo drawing procedures: `https://wildlife.utah.gov/r657-55a.html`

Important DWR rule facts:

- Limited-entry, CWMU, once-in-a-lifetime, antlerless moose, ewe bighorn, turkey, and most bear draw rows use max/weighted split routing.
- General-season buck deer, Dedicated Hunter deer, antlerless deer, antlerless elk, and doe pronghorn use preference-point style routing.
- Dedicated Hunter stays visible as a hunt-type label, but its draw system is preference.
- Group applications average points and round down.
- Youth-only groups can receive reserved youth quotas for general-season buck deer, antlerless deer, antlerless elk, doe pronghorn, turkey, and some bird permits.
- Draw-only youth any bull/hunter's choice elk is a separate Big Game draw family; preference points are not awarded or used for it.
- General-season youth elk is a purchase/availability family, not the same as draw-only youth elk.
- Sportsman permits are a separate resident-only random draw; max/weighted split and preference points are not used.
- Expo permits are random selection rows; max/weighted split and preference points are not used and no resident/nonresident quota split is imposed unless the rule/source explicitly says otherwise.

## Routing Algorithm

Every hunt row should be routed before any odds math happens:

```text
route_key = (
  species,
  sex_type,
  hunt_type,
  weapon,
  hunt_class_if_it_changes_the_result,
  hunt_code
)
```

Then apply the first matching family:

```text
if hunt_type is Statewide and row is a sportsman permit:
    draw_system_type = SPORTSMAN_PERMIT
elif hunt_type is Expo or source is expo permit:
    draw_system_type = EXPO_RANDOM_ONLY
elif hunt_type is Limited Entry, Premium Limited Entry, Once-in-a-lifetime, CWMU bonus, antlerless moose, ewe bighorn, limited-entry turkey, or true limited-entry bear:
    draw_system_type = BONUS_*
elif hunt_type is General Season buck deer or Dedicated Hunter deer:
    draw_system_type = PREFERENCE_*_DEER
elif species/sex is antlerless deer, antlerless elk, or doe pronghorn in the antlerless draw:
    draw_system_type = PREFERENCE_ANTLERLESS_OR_DOE
elif hunt_code is draw-only youth any bull/hunter's choice elk:
    draw_system_type = YOUTH_DRAW_ONLY_ELK
elif hunt_code is general-season youth elk:
    draw_system_type = YOUTH_OTC_OR_AVAILABILITY
elif row is private-lands-only antlerless elk:
    draw_system_type = PRIVATE_LANDS_ONLY_ANTLERLESS_ELK
elif DWR/Hunt Planner does not publish permit numbers for a private-land, landowner, or reviewed no-quota row:
    draw_system_type = NO_PUBLIC_DRAW_ODDS_NO_PUBLISHED_PERMIT_DATA
elif row is cougar/mountain lion O.T.C. / allotment:
    draw_system_type = MOUNTAIN_LION_OTC_ALLOTMENT
else:
    draw_system_type = REVIEW_REQUIRED
```

The selector should never show two steps that mean the same thing. Example: `Bison -> Hunters Choice -> Once-in-a-lifetime -> Once-in-a-lifetime -> Weapon` is wrong because the second `Once-in-a-lifetime` adds nothing. But `Elk -> Bull -> General Season -> Any Legal Weapon -> Youth` is useful because `Youth` changes the draw family.

## Quota Resolution Formula

For each hunt code and residency lane:

```text
Q_res = permits_2026_draw_res if populated else permits_2026_res else permit_allotment_2026_res
Q_nr = permits_2026_draw_nr if populated else permits_2026_nr else permit_allotment_2026_nr
Q_total = permits_2026_draw_total if populated else permits_2026_total else permit_allotment_2026_total
```

Rules:

- If DWR publishes resident and nonresident values, keep the split.
- If DWR publishes only total, keep it total-only. Do not invent a resident/nonresident split.
- A total-only row displays the total permit value while resident and nonresident permit cells remain blank. This is expected for General Season preference totals, O.T.C. / capped rows, CWMU totals, conservation/reference rows, tribal/reference rows, and reviewed total-only turkey rows when the source does not publish a residency split.
- When a runtime prediction row is keyed to `Resident` or `Nonresident`, total-only permit authority must not be copied into that lane as `Q_res` or `Q_nr`. The engine may preserve `Q_total` for display/audit, but it must not create lane max-pool/random-pool quotas from that value.
- If DWR/Hunt Planner does not publish permit numbers at all, keep all 2026 permit columns blank, do not render a total, and exclude the row from public prediction odds.
- CWMU and many private/overlay rows are total-only unless DWR publishes a split.
- Conservation, landowner, mitigation, and expo overlays must not be merged into public draw quotas unless a source explicitly says they are public draw permits.

## Max/Weighted Split Formula

Used for `BONUS_*` rows and the corresponding max/weighted split families. This is where the specific permit availability / allotment for a hunt and residency lane is split between the top-point pool and the weighted random pool.

Let:

```text
Q = quota for the residency lane
A[p] = applicant count at point level p
G[p] = group-size-adjusted application count at point level p
```

Quota split:

```text
if Q == 0:
    Q_max = 0
    Q_random = 0
elif Q == 1:
    Q_max = 0
    Q_random = 1
else:
    Q_max = ceil(Q / 2)
    Q_random = Q - Q_max
```

Interpretation:

- `Q_max` is the permit allotment reserved for the highest-point pass.
- `Q_random` is the remaining permit allotment assigned to the weighted random pass.
- If the source publishes a total-only row, preserve the total for display/audit, but do not split it into resident or nonresident lane quotas unless DWR publishes an actual residency split.
- If the source publishes no permit count for a private-land, landowner, or reviewed no-quota row, no max-pool or random-pool quota is created.
- The split happens per hunt code and residency lane, using the official published quota or allotment as the input.
- If resident and nonresident allotments differ, each lane gets its own split instead of sharing a combined pool.

Max-point pass:

```text
remaining = Q_max
for p from highest points down:
    if remaining >= G[p]:
        p_max[p] = 1.0
        remaining -= G[p]
    elif remaining > 0:
        p_max[p] = remaining / G[p]
        remaining = 0
    else:
        p_max[p] = 0.0
```

Random pass:

```text
tickets[p] = points[p] + 1
weighted_pool = sum(remaining_applicants[p] * tickets[p])
p_random[p] ~= 1 - (1 - tickets[p] / weighted_pool) ^ Q_random
p_draw[p] = p_max[p] + (1 - p_max[p]) * p_random[p]
```

The public-data MVP can use the formula above as a stable approximation. The simulator should use the exact ticket draw process when true application-level data is available.

## Preference-Point Formula

Used for `PREFERENCE_*` rows.

Let:

```text
Q = quota after any reserved sub-pools are removed
A[p, choice] = applications at preference-point level p for choice rank 1..5
```

Preference draw:

```text
remaining = Q
for choice in 1..5:
    for p from highest points down:
        if remaining <= 0:
            p_preference[p, choice] = 0
        elif remaining >= A[p, choice]:
            p_preference[p, choice] = 1
            remaining -= A[p, choice]
        else:
            p_preference[p, choice] = remaining / A[p, choice]
            remaining = 0
```

For a row-level public prediction:

```text
p_draw = p_preference[first_choice]
```

If second-through-fifth choice behavior is available, the full draw probability becomes:

```text
p_draw = 1 - product(1 - p_preference[choice] for each eligible choice)
```

Public DWR draw PDFs often expose first-choice behavior more reliably than full application-level choices, so the engine must mark first-choice-only modeling with a reason code.

## Youth Routing

Youth is not one draw model.

Youth rows split into four practical families:

```text
YOUTH_GENERAL_DEER_RESERVE
YOUTH_ANTLERLESS_OR_DOE_RESERVE
YOUTH_DRAW_ONLY_ELK
YOUTH_OTC_OR_AVAILABILITY
```

General youth deer and youth antlerless/doe:

```text
Q_youth = floor_or_source(up_to_20_percent_of_draw_quota)
p_youth = preference_algorithm(Q_youth, youth_only_applicants)
```

Draw-only youth any bull/hunter's choice elk:

```text
Q_youth_elk = published draw-only youth elk quota
p_youth_elk = random_or_bonus-style draw from youth applicants only
```

Because DWR states preference points are not awarded or used for draw-only youth any bull/hunter's choice elk, this row must not be modeled as adult preference. It also must not be mixed into limited-entry bull elk bonus pools.

General-season youth elk:

```text
draw odds = null
availability_status = source-supported purchase/remaining-permit status
```

## Sportsman And Expo

Sportsman:

```text
Q = 1 per species unless source says otherwise
p_draw = 1 / eligible_applicants
```

Sportsman rows do not use max/weighted split points, preference points, max-pool quotas, random-pool tickets, or resident/nonresident splits. They are Utah-resident-only unless DWR changes the rule.

Expo:

```text
p_draw = permits_for_expo_row / eligible_expo_applications
```

Expo rows do not use max/weighted split or preference points and should not impose resident/nonresident splits unless a rule/source explicitly provides one.

## Mixed Public-Data Prediction Formula

The active public-data model should keep deterministic draw rules separate from demand forecasting:

```text
p_rule = deterministic_draw_formula(draw_system_type, quota, applicant_stack)
p_prior = prior_year_observed_probability
p_quota = quota_change_adjustment
p_rollover = applicant_rollover_adjustment
p_quality = capped_harvest_quality_demand_adjustment

p_draw_mean = clamp(
    0.60 * p_prior +
    0.20 * p_rule_or_quota_adjusted +
    0.15 * p_rollover +
    0.05 * p_quality,
    0,
    1
)
```

Guardrails:

- `p_quality` is only a small demand-pressure nudge; it cannot invent permits or overwrite quota.
- `MAX POOL` is descriptive only. It does not force 100 percent odds.
- If the row is an O.T.C. / allotment family, keep draw probability null and use status/allotment fields instead.
- If the row has only total permits and no published residency split, do not fabricate resident/nonresident odds.
- If the row has only total permits and the runtime surface is split into resident/nonresident rows, mark the row with total-only/no-split reason codes and skip quota-ratio adjustment for that residency lane.
- If the row is historical-only, discontinued, or lacks a definite current crosswalk, do not route it to a current prediction model.

## Recommended Engine Changes

The current classifier should be tightened so youth rows do not drift:

- `EB1007` should route to a youth draw-only elk family.
- `EB1011` should route to O.T.C. / allotment or remaining/OTC, not the draw-only youth elk model.
- Youth general deer and youth antlerless/doe rows should be reserve-pool variants of the preference family.
- Youth limited-entry turkey can remain under the turkey bonus family if the source draw report uses bonus/regular columns, or it can be split into a named youth-turkey bonus family for reporting clarity.

The database selection matrix should keep using `hunt_class` as a visible selector only when it changes one of those engine routes.
