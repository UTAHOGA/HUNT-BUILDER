# Two-Year Lane Tuning 2021-2023

Audit-only. No engine outputs modified.

## Recommendations

- `ANTLERLESS_PREFERENCE`: OVER in 2021?2022 bias `0.05771394568602173`, OVER in 2022?2023 bias `0.01728985110004663`. SMALL_TUNE_DOWN_OR_CUTOFF_CHECK; overpredicts but less severe than youth antlerless.
- `BEAR_BONUS`: UNDER in 2021?2022 bias `-0.009240689174696151`, UNDER in 2022?2023 bias `-0.01712104470099725`. SMALL_BEAR_BONUS_TUNE_DOWN_OR_POOL_CHECK; underpredicts both years but 2023 worse. inspect bonus/random split.
- `DEDICATED_HUNTER_DEER_PREFERENCE`: UNDER in 2021?2022 bias `-0.035189854751126584`, OVER in 2022?2023 bias `0.12484131400610154`. TUNE_DOWN_DH_PREFERENCE; overpredicts in 2022?2023 and remains high-error in both years; test exact DH quota/cutoff, not youth reserve.
- `GENERAL_SEASON_DEER_PREFERENCE`: OVER in 2021?2022 bias `0.05629795740003451`, OVER in 2022?2023 bias `0.020303076328864078`. LOW_PRIORITY; overpredicts mildly, but broad preference tuning may hurt.
- `TURKEY_BONUS`: OVER in 2021?2022 bias `0.03872035894116036`, OVER in 2022?2023 bias `0.060991242539066036`. TUNE_DOWN_TURKEY_BONUS; overpredicts both recent pass where present; youth turkey uses 15% rule not 20%.
- `YOUTH_ANTLERLESS_PREFERENCE`: OVER in 2021?2022 bias `0.05506148694792111`, UNDER in 2022?2023 bias `-0.0010890072601379573`. NO_SIMPLE_20_PERCENT_HAIRCUT; implement exact youth-reserved pool with rollback, then validate.
- `YOUTH_DEDICATED_HUNTER_DEER_PREFERENCE`: UNDER in 2021?2022 bias `-0.15132416602843138`, OVER in 2022?2023 bias `0.06788931788751609`. NO_GLOBAL_SCALAR; direction flips between years. Inspect Youth DH source grain/quota and cutoff logic.
- `YOUTH_GENERAL_SEASON_DEER_PREFERENCE`: OVER in 2021?2022 bias `0.038285935647001446`, NEUTRAL in 2022?2023 bias ``. LOW_PRIORITY; overpredicts mildly, but broad preference tuning may hurt.
- `YOUTH_TURKEY_BONUS`: OVER in 2021?2022 bias `0.03328230025139048`, OVER in 2022?2023 bias `0.08324087532513454`. TUNE_DOWN_TURKEY_BONUS; overpredicts both recent pass where present; youth turkey uses 15% rule not 20%.
