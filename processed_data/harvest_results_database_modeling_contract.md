# Harvest Results Database Modeling Contract

Harvest data is a quality, demand-signal, effort, trend, and explanatory metadata source. It is not a public draw-odds source and it is not a current-year quota/allotment source.

## Harvest Data May Model
- applicant demand pressure
- hunt quality trend
- hunter effort trend
- hunter satisfaction trend
- trophy/age trend
- sex-structure trend
- population/trend-count signal
- pursuit pressure signal
- fallback quality features for new or renamed hunt codes
- calibration and explanatory metadata

## Harvest Data May Not Model Directly
- public draw odds
- p_draw
- p_random_mean
- p_max_pool_mean
- p_preference_draw
- p_bonus_pool
- 2026 official quota
- 2026 public draw permit allotment
- max-point pool permit count
- random-pool permit count

Harvest report permit counts remain historical harvest-report context. They must not overwrite `permits_2026_*`, `permit_allotment_2026_*`, `quota_2026_*`, or any active public draw allotment field.

Expo, Conservation, Sportsman, and CWMU permit overlays are retained for total-permit reconciliation and audit traceability only. They must not be merged into public draw odds or `p_draw` math.

Any feature materialization that joins harvest features onto predictive rows must assert that probability fields and 2026 quota/allotment fields are unchanged before and after the join.
