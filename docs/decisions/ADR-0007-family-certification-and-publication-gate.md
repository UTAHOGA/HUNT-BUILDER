# ADR-0007: Family Certification And Publication Gate

- Status: Accepted
- Date: 2026-09-07

## Decision

Statistical certification is independent of runtime implementation status.
`PROMOTED_TO_RUNTIME` means that a family is routed and materialized; it does
not mean its probability forecast passed the blind acceptance standard.

Every forecastable draw design receives one of three evidence statuses from a
machine-generated registry:

- `CERTIFIED`: every ADR-0006 threshold passes, including source-classified
  coverage of every non-joined scoreable official actual.
- `EXPERIMENTAL_NOT_CERTIFIED`: enough evidence exists to judge the family, but
  at least one accuracy, tail, false-guarantee, or coverage gate fails.
- `INSUFFICIENT_EVIDENCE`: the family lacks the required independent folds,
  joined rows, or complete gate evidence.

For designs with separate resident and nonresident draw lanes, the same
acceptance metrics are also computed independently for each residency. A
combined design score cannot conceal a failing residency population. Full
design promotion requires every applicable residency slice to pass; a future
residency-limited publication must declare that scope explicitly in its
registry and public contract.

Raw `p_draw` fields remain available for development and blind scoring. A
certification-aware public contract may expose future probability only through
`certified_p_draw`, `certified_p_draw_mean`, or `certified_p_draw_pct`. Those
fields must be blank for every non-certified row. Local or hosted promotion is
blocked when that contract is absent or violated.

Bear limited-entry hunting and restricted pursuit remain separate
certification populations. An untyped or combined `BEAR_DRAW` population
cannot certify either program.

The 2026-09-22 supplemental eight-fold review scored Resident and Nonresident
lanes separately for all four certified designs. All eight residency/design
slices pass the unchanged thresholds with zero false guarantees and zero
unclassified official-actual gaps. The evidence is retained under
`audits/prediction_release_candidates/residency_lane_acceptance_20260922/`.
This adds a stricter publication gate; it does not change any forecast
probability, certify another design, or admit the diagnostic 2025→2026 fold
into the adopted acceptance window.

The prior `guaranteed_at_*` fields remain temporary compatibility aliases.
New materializations also emit `projected_draw_line_2025` and
`projected_draw_line_2026`. A projected line estimates future draw structure;
it never converts a row to 100% probability and never promises that an
applicant will draw.

## Current Result

The following promotion is a historical deployment record. The stricter
2026-09-19 completion audit described below supersedes it for new promotion
decisions, without rewriting the retained production registry.

The gate was rerun against nine source-only adjacent folds from 2017→2018
through 2025→2026. The review counts every scoreable official actual lacking a
forecast, requires an explicit source classification for every gap, and uses
only pre-draw identity evidence for target-year crosswalk exceptions.

Four designs pass every ADR-0006 metric, coverage, false-certainty, and evidence
gate: `BONUS_LE_BIG_GAME`, `BONUS_OIL_BIG_GAME`, `BONUS_PLE_BIG_GAME`, and
`PREFERENCE_GENERAL_SEASON_BUCK_DEER`. They were promoted on 2026-09-10 through
the `certified_p_draw*`-only public contract. Bear, CWMU, turkey, antlerless,
Dedicated Hunter, and under-evidenced youth designs remain experimental or
insufficient-evidence and have no displayed future probability.

## Consequences

### 2026-09-19 completion requirements

Family certification alone cannot authorize an incomplete runtime population.
The release gate must independently inventory eligible current hunt/residency
lanes, verify every source-backed successor point and matching public detail,
and browser-test every current lane (including honest suppression), not only
the 13 smoke examples. The ten historical-only classifications must reconcile
to their source canonicals with no forecast probability.

Historical accuracy evidence must score the exact final website calculation
through `engine.utah_predictive_mixed.materialize.mixed_row`. Hash-link the final
file to the scoring projection and bind its implementation hash to the release.
The four core families preserve their family-engine probability at this final
step; prior realized winners, quota proxies and harvest context may not re-blend
it. This changes the declared owner in place; it does not add an engine stack.

A scoreable official actual with a present-but-blank forecast is also a coverage
gap. It must be source-classified under the same standard as an absent row;
neither may disappear from certification. The nine-fold completion rerun found
32 unresolved LE gaps and three general-deer accuracy failures. Only OIL and
premium LE passed that retained baseline's stricter review; its public candidate
suppresses both failed designs. The later separately frozen
`core_le_deer_repair_20260919` resolves all 32 through independent source-only
replay of the existing no-certainty safeguard, without filling their blank
probabilities. Excluding duplicate hunt-total awards from the historical deer
quota adapter brings deer within all frozen limits without a formula change.
The exact final nine-fold registry certifies all four core designs. Numeric
errors, including later quota changes, remain in the score; no limit is relaxed.

General-deer Board/Planner totals cannot be split 90/10 as if they were regular
round quotas. Lifetime, Dedicated Hunter and youth allocations precede that
round. Current builds may explicitly ingest the official UtahDraws
`ResidentRegularRoundQuota` and `NonResidentRegularRoundQuota` fields with exact
identity and season checks, retained source hash and separate `target_permits_*`
scope. Historical folds remain source-year-only and cannot consume this current
payload or DATABASE.csv. Existing public permit-reference fields are preserved.

- The hosted Research release publishes certified probability only for the four
  approved designs and withholds it for every other family.
- Historical evidence and projected lines remain visible for non-certified
  families without implying a certified future probability.
- Certification is granted per draw design, never by aggregate score.
- Resident and nonresident evidence is retained as separate acceptance slices;
  neither lane inherits the other lane's accuracy result.
- Public lookup must use the exact requested residency and must return no
  prediction when that lane is absent; cross-residency fallback is prohibited.
- Closing a coverage gap requires a source-backed classification or a real
  forecast; deleting or silently dropping the official actual is prohibited.
- Upload, deployment, and production promotion still require Tyler's separate
  explicit authorization.
