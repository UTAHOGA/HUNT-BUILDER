# Black Bear Hunt-Lane Transition Evidence Contract

## Purpose

This contract defines the only source class that may identify Black Bear
applicant movement into a specific future public-draw hunt lane. It is an
optional, privacy-preserving input to the existing Bear cohort model. It does
not alter yearly draw-result canonicals, `draw_results_long.csv`, current
Planner quota reference, or the default production forecast.

## Why the public sources are insufficient

The retained public DWR Black Bear draw-odds reports provide aggregate
applicants and successful applicants by hunt, residency, and point level. The
retained statewide point-purchase reports provide aggregate purchasers by
residency and point level. Neither source identifies the same applicant across
two drawings or states the hunt chosen in the next drawing.

This distinction is intentional:

- Utah Administrative Rule R657-62-8 awards a bonus point for a valid
  unsuccessful limited-entry application or a valid bonus-point application,
  prohibits applying for both a permit and a bonus point for the same species,
  and states that DWR tracks bonus points by an applicant identifier.
- The 2025 Utah Black Bear & Cougar Guidebook states that, to protect
  applicants' privacy and comply with government-records access laws, an
  applicant may access only that applicant's own drawing results.
- The current public UtahDraws endpoint exposes aggregate point rows and
  success counts; `AllChoicesSuccessfulCount` is an aggregate success count,
  not an applicant-to-next-hunt or choice-rank transition record.

Accordingly, a statewide point-purchase total may corroborate that a population
exists at a point level, but it may not be apportioned among hunts. The current
`source_calibrated_tail_mixture` may use it only as an evidence gate for an
already observed historical same-lane arrival. It cannot establish a direct
future-hunt transition.

## Required DWR aggregate transition extract

The acceptable source is a DWR-produced, de-identified aggregate derived from
the retained electronic applications. It must contain no customer ID, name,
date of birth, address, license number, application number, or other personal
identifier.

One row represents an aggregate count of applicants sharing all of these
fields:

| Field | Meaning |
| --- | --- |
| `source_draw_year` | Drawing in which the source activity occurred. |
| `target_draw_year` | Following Black Bear drawing; must equal source year plus one. |
| `residency` | Resident or Nonresident, held as separate lanes. |
| `source_activity` | `UNSUCCESSFUL_BEAR_PERMIT_APPLICATION` or `BEAR_BONUS_POINT_APPLICATION`. |
| `source_hunt_code` | The source public-draw hunt code; blank only for a bonus-point-only application. |
| `source_points` | Point level used in the source drawing/application. |
| `target_hunt_code` | First-choice public-draw hunt code in the following drawing. |
| `target_points` | Point level used in the following drawing. |
| `target_choice_rank` | Numeric choice rank; the production odds contract must use first choice only unless DWR releases complete later-choice denominator evidence. |
| `target_application_outcome` | At minimum, selected versus not selected; a result count is sufficient. |
| `applicant_count` | DWR-suppressed aggregate count, with the suppression rule and all suppressed values documented. |
| `source_release_id` | DWR release identifier, extract date, data owner, and applicable retention/suppression policy. |

The extract must separately account for an applicant who did not reapply in the
following year. This is necessary to distinguish attrition from a switch to a
different hunt. Rows must not mix Bear hunting permits with restricted-pursuit,
harvest-objective, general-pursuit, Sportsman, CWMU, conservation, Expo, or
remaining-permit programs.

## Validation required before model use

1. Retain the original DWR export, a SHA-256 hash, release metadata, and a
   data dictionary under a new `data_truth` source scope. Do not put it in a
   draw-result canonical.
2. Verify every row is physically adjacent (`target_draw_year =
   source_draw_year + 1`) and preserves residency as a separate lane.
3. Verify the stated point progression for each source activity. Any
   exception, including permit surrender, correction, waiting-period, or
   eligibility event, must be source-labelled rather than silently assigned.
4. Reconcile target first-choice counts against the dated official draw-odds
   applicant ladders at hunt, residency, and point level. Suppressed counts
   remain suppressed; they must never be reconstructed from statewide totals.
5. Freeze a source-year-only transition matrix for every historical fold. A
   forecast for year N+1 may use only transitions whose target year is no later
   than N.
6. Run the ADR-0006 adjacent-year review with the matrix as the sole changed
   input. It must improve multiple held-out folds without reducing score
   coverage, creating duplicate identities, or introducing a false guarantee.

## Permitted engine behavior

When DWR supplies the aggregate transition matrix, the existing Bear engine may
sample its observed, source-year-only distribution for the exact
`residency + source activity + source/target hunt + point` lane. The matrix is
an uncertainty distribution, not a deterministic assignment. It may lower a
draw probability when documented incoming demand competes for a lane; it may
not raise a probability, create an applicant, split a quota, or convert a
statewide point-purchase count into a hunt-level count.

Until then, public draw-result ladders do support a narrower, auditable cohort
candidate in the existing Bear engine:

1. Calculate each source rung's actual unsuccessful cohort from official
   eligible applicants minus official successful applicants.
2. Use adjacent-year, same-code, same-residency, point-plus-one ladders as an
   aggregate proxy for same-lane reapplication. Individual applicants are not
   identified or inferred.
3. Decompose an observed next-year count into at most the source unsuccessful
   cohort (reapplication) plus a separately recorded residual arrival. The
   residual is not relabelled as a returning applicant.
4. Smooth a thin exact lane only toward source-derived Bear subtype,
   residency, and point-band evidence, leaving the exact rung out of its own
   fallback prior.
5. Run this only as a source-year-only, simulation-mean audit candidate. A
   fallback-derived thin lane must retain posterior uncertainty and may not
   create a deterministic visitor-facing guarantee.

The separately recorded arrival component must also be sampled as a discrete
count with its source-derived posterior mean. Rounding a fractional expected
arrival into every simulation is not an uncertainty model and must not be used
to create or remove a public draw guarantee.

This candidate does not claim to identify a person who switched hunts or
entered after a point-only year. The DWR aggregate matrix remains the required
source for that more specific distinction.

## Primary source references

- Utah Administrative Rule R657-62-8, Bonus Points:
  <https://wildlife.utah.gov/rules/r657-62>
- 2025 Utah Black Bear & Cougar Guidebook, application privacy and points:
  `pipeline/RAW/hunt_unit_database/2025/pdf/guidebooks/black-bear-and-cougar-guidebook-2025.pdf`
- Retained public statewide point-purchase evidence:
  `black_bear_limited_entry_bonus_point_purchases_2018_2025.csv`
- Retained public UtahDraws aggregate endpoint snapshot:
  `pipeline/RAW/hunt_unit_database/2026/json/draw_results/utahdraws_2026_20260902_fresh_2345/utahdraws_2026/csv/2026_black_bear_01_black_bear.csv`
