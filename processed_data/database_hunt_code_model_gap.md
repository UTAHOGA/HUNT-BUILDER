# Database Hunt-Code Model Gap Audit

## Summary

- Canonical database file used: `pipeline\RAW\hunt_unit_database\2026\csv\DATABASE.csv`
- Database unique hunt-code count: `1411`
- Modeled target hunt-code count: `1015`
- Database-to-modeled gap count: `396`
- Coverage target-scope hunt-code count: `1668`
- Coverage-to-database overage count: `257`

## Bucket Counts

- `in_database_and_modeled`: `955`
- `in_database_not_modeled`: `456`
- `modeled_not_in_database`: `60`
- `coverage_seen_not_in_database`: `272`
- `historical_or_observed_only`: `603`
- `pending_or_non_probability_status`: `449`
- `out_of_scope_or_excluded`: `2`

## Top Gap Reasons

- `OBSERVED_HISTORY_ONLY`: `391`
- `IN_SCOPE_MODEL_PENDING`: `48`
- `SOURCE_SUPPORT_INSUFFICIENT`: `15`
- `EXCLUDED_NOT_PREDICTIVE_DRAW`: `2`

## Count Note

- No canonical database candidate in the current repo produced 1,294 unique hunt codes; selected canonical source reports 1411 unique hunt codes.
