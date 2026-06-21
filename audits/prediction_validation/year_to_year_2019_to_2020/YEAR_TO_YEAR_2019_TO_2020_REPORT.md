# 2019 Projection vs 2020 Actual Draw Results

Generated UTC: 2026-06-19T04:07:36.102222+00:00

Comparison: prediction rows with `year=2019, model_year=2020` vs actual truth rows with `year=2020`.
Actual probability uses published `success_rate / 100`; no permit/applicant-derived actuals.

## Summary

- Prediction rows filtered: `63950`
- Prediction rows with probability: `16547`
- Actual 2020 truth rows: `63808`
- Actual rows with published success_rate: `16954`
- Joined rows: `13859`
- Prediction-only unmatched rows: `2688`
- Actual-only unmatched rows: `3095`
- Duplicate join-key groups: `1300`
- MAE: `0.1053279376821704`
- RMSE: `0.25863938575909784`
- Bias: `0.023211070530081465`
- Failure rows > 0.25 abs error: `1819`

## Interpretation

This is the first true year-to-year validation pass, not same-year replay. It should be used to identify changed demand, code turnover, and model carry-forward weakness between the 2019 source surface and the 2020 actual surface.
