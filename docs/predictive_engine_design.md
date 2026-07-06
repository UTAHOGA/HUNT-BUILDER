# Predictive Engine Design

This repository is moving from a legacy research-page lookup system to a Utah predictive draw engine.

## Scope

- Preserve the current research UI and row key `(hunt_code, residency, points)`.
- Replace the legacy `MAX POOL = 100%` behavior with modeled probability logic.
- Keep draw mechanics deterministic underneath the UI.
- Add a public-data MVP first, then grow toward true feed support.

## Layering

1. Deterministic Utah draw rules live in `engine/utah/simulator.py` and `engine/utah/rules.py`.
2. Baseline demand estimation lives in `engine/utah/demand.py`.
3. Quota forecasting lives in `engine/utah/quota_forecast.py`.
4. Truth-source permit promotion lives in `engine/utah/truth_source_promotion.py`.
5. Materialization into legacy-compatible CSVs lives in `engine/utah/materialize.py`.
6. Backtesting and calibration live in `engine/utah/backtest.py` and `engine/utah/calibration.py`.
7. The canonical fixture rebuild CLI is `python -m engine.utah.materialize ...` and it writes the four processed CSVs directly into the chosen output directory.

## Permit Truth Flow

- Permit-source promotion is a deterministic data-hygiene step that runs before any downstream runtime publication.
- The expected flow is:
  - RAC truth source
  - normalized truth table
  - audit
  - promote to runtime reference surfaces
  - regenerate processed outputs
  - audit again
  - zero mismatches for corrected families
- This flow updates permit overlays only. It does not change modeled draw math by itself.
- Current-year RAC allotment tables are the preferred source for available 2026 permits when a direct `hunt_code` row exists. They are active quota inputs for current-year draw-odds behavior. Runtime files also expose them separately from historical draw-result permit fields using `permit_allotment_2026_res`, `permit_allotment_2026_nr`, and `permit_allotment_2026_total`.
- When the RAC source provides only a total permit value, the resident/nonresident allotment fields stay blank. The engine must not infer a split from the total.
- When a direct RAC current-year allotment is unavailable, runtime files may fall back to existing `permits_2026_*` values and must mark that fallback in `permit_allotment_2026_source`.

## Runtime Promotion Rules

- The runtime contract still centers on `(hunt_code, residency, points)`, but permit-reference promotion is primarily keyed by `hunt_code` and `residency`.
- Permit promotion may add metadata fields such as `permit_source`, `quota_source`, `truth_source_file`, `truth_source_status`, and `reason_codes`.
- Existing columns should be preserved whenever possible; promotion is additive unless a stale permit value must be corrected.

## O.T.C. / Allotment Families

- O.T.C. / allotment families must not be treated as standard draw-probability rows.
- Private-lands-only antlerless elk is O.T.C. / allotment-only in the current design unless a source explicitly provides draw mechanics and a valid residency split.
- O.T.C. / allotment rows may appear in the runtime CSVs for lookup continuity, but they must not be assigned invented probabilities.
- `MODELED_AVAILABILITY` is a source-backed O.T.C. / allotment status classification, not draw-odds modeling.
- Mountain lion / cougar currently uses O.T.C. / allotment semantics rather than draw odds.
- Bear harvest-objective and pursuit-only subtypes currently use O.T.C. / allotment semantics rather than draw odds.
- O.T.C. / allotment review should run after predictive artifact regeneration so every such row is explicitly accounted for and no hidden non-draw family drifts into the runtime outputs.

## Overlay Exceptions

- Control-unit overlays are tracked separately from permit-row mismatches.
- Unresolved overlay items must remain unresolved rather than auto-filled with invented hunt codes.
- `Henry Mtns` in the 2026 antlerless elk control-unit list is the current tracked unresolved overlay item.

## Probability units

- `p_*` fields are decimal probabilities in `[0, 1]`.
- `*_pct` fields are percentages in `[0, 100]`.
- The UI should prefer `display_odds_pct`, then `p_draw_mean`, then `odds_2026_projected`, then `max_pool_projection_2026`, then `random_draw_odds_2026`, then `random_draw_projection_2026`.
- All user-facing draw odds should render in combined `~1 in X or Y%` format rather than percent-only text.
- `status = MAX POOL` is descriptive only and does not imply a guarantee.
- Permit-source promotion does not change probability formulas. When RAC current-year allotments exist, it changes the quota input used by the existing draw simulator and point-ladder probability calculations.

## Mixed Predictive Engine

The mixed predictive engine is materialized by
`scripts/build_mixed_predictive_engine_2026.py` and `engine/utah_predictive_mixed/`.
It combines:

- prior-year DWR draw-result behavior;
- official 2026 RAC/DATABASE quota/allotment;
- applicant rollover and point-pool mechanics;
- harvest quality / demand-pressure features;
- calibration and explanatory metadata.

Default weights are `0.60` prior-year behavior, `0.20` quota change, `0.15`
applicant rollover, and `0.05` harvest demand signal. Prior-year behavior is the
highest-weighted public signal. Harvest quality is a capped demand-pressure
nudge only; it must not directly create `p_draw`, `p_random_mean`,
`p_max_pool_mean`, or `p_preference_draw`.

Special permit overlays such as Expo, Conservation, Sportsman, CWMU
contact/operator, CWMU quota-only, CWMU reference, landowner, mitigation, and
private/boundary overlays are retained for total permit reconciliation and
source traceability only. They must not be merged into public draw quotas,
max-pool quotas, random-pool quotas, or public `p_draw` math. CWMU point-level
draw-result rows with published probabilities are scoreable under the CWMU
policy. Sportsman permits use the separate sportsman model.

## Current limitations

- Public data does not fully expose group membership, choice rank behavior, or current applicant pools.
- Fixture data is allowed for tests and local development.
- A true-feed engine requires administrative feed support.
