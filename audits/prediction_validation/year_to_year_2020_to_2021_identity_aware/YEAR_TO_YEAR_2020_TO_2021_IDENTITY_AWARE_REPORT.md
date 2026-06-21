# 2020 to 2021 Identity-Aware Prediction Validation

Generated UTC: 2026-06-19T05:07:34.313714+00:00

Join key: `hunt_code + residency + point_level + normalized_source_scope + draw_family; grouped by hunt_code + species + sex_type + weapon`

Identity source: 2021 clean parent-PDF extraction when available; deterministic code/name parse only for audit fallback

## Summary

- joined_rows: `4570`
- duplicate_join_key_groups: `0`
- identity_unknown_rows: `72`
- identity_conflict_rows: `0`
- mae: `0.1594578465989059`
- rmse: `0.29067916265689536`
- bias: `-0.013606175815185998`
- failure_count_abs_error_gt_0_25: `957`
