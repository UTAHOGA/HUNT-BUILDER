# Youth Reserved Pool Tuning Audit

Generated UTC: 2026-06-19T07:13:32.180517+00:00

This is an audit-only probability candidate. It does not overwrite engine outputs.

The 20% rule was tested only for youth general-season deer and youth antlerless lanes.
Youth Dedicated Hunter and youth turkey were intentionally left as separate lanes.

## Best Candidates

- `ALL_ROWS`: `reserve_pool_bias_shift_minus_0_04` MAE `0.07732138578096781` -> `0.07783135423701706`, bias `0.020428151587200134` -> `0.01901698546746767`
- `YOUTH_ANTLERLESS_PREFERENCE`: `reserve_pool_bias_shift_minus_0_04` MAE `0.13978207772772452` -> `0.14473749667891245`, bias `0.05506148694792111` -> `0.032716689916387626`
- `YOUTH_BULL_ELK_BONUS`: `reserve_pool_scale_0_80` MAE `0.0029020868520758594` -> `0.0029020868520758594`, bias `0.0003893176393791123` -> `0.0003893176393791123`
- `YOUTH_DEDICATED_HUNTER_DEER_PREFERENCE`: `reserve_pool_scale_0_80` MAE `0.35720651896764705` -> `0.35720651896764705`, bias `-0.15132416602843138` -> `-0.15132416602843138`
- `YOUTH_GENERAL_SEASON_DEER_PREFERENCE`: `reserve_pool_bias_shift_minus_0_04` MAE `0.0790227587221059` -> `0.09747096162999623`, bias `0.038285935647001446` -> `0.0009713614562797739`
- `YOUTH_TURKEY_BONUS`: `reserve_pool_scale_0_80` MAE `0.10032865247036671` -> `0.10032865247036671`, bias `0.03328230025139048` -> `0.03328230025139048`
