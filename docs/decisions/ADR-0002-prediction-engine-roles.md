# ADR-0002: Prediction Engine Roles

- Status: Accepted
- Date: 2026-08-26

## Decision

The existing engine directories are cooperating layers:

- `engine/utah_predictive_mixed` owns post-family calibration of eligible family outputs. It does not replace the draw-family mechanics and passes random-only family probabilities through unchanged.
- `engine/utah_draw_predictive` owns family routing, family rules, exclusions, allocation, and availability semantics.
- `engine/utah_bonus_predictive` owns forecast orchestration, historical cohort modeling, uncertainty, backtest materialization, and artifact packaging.
- `engine/utah` owns deterministic Utah draw mechanics and base validation.

No new top-level prediction-engine stack may be created without Tyler's explicit approval.

The official parent design is routed before probability math. Bonus, preference, random-only, and no-draw programs do not share a universal formula. Youth, residency, Dedicated Hunter, CWMU, group, and choice-order rules are overlays on the appropriate parent design.

Black bear is explicitly subtype-routed: limited-entry hunting and restricted pursuit are bonus drawings; harvest-objective hunting and general pursuit are availability programs.

The latest official unsuccessful ladder advanced one point is the primary applicant-demand anchor. High-point just-missed cohorts receive the strongest history-calibrated retention. Lower-point entrants, switching, and attrition remain secondary and must be selected through blind following-year testing.

## Reason

The four directories implement different stages. Treating them as competing designs caused repeated restarts and inconsistent claims about the production owner.

## Consequences

Family defects are fixed in the family owner. Calibration defects are fixed in the mixed owner. Forecast or packaging defects are fixed in the materialization owner. Utah rule defects are fixed in the deterministic foundation. Residency lanes must remain separate through their official evaluation and may cross over only where the current rule authorizes it.
