# Database Hunt-Code Model Gap Audit

## Summary

- Canonical database file used: `pipeline\RAW\hunt_unit_database\2026\csv\DATABASE.csv`
- Database unique hunt-code count: `1645`
- Modeled target hunt-code count: `859`
- Database-to-modeled gap count: `786`
- Coverage target-scope hunt-code count: `1539`
- Coverage-to-database overage count: `-106`

## Bucket Counts

- `in_database_and_modeled`: `807`
- `in_database_not_modeled`: `838`
- `modeled_not_in_database`: `52`
- `coverage_seen_not_in_database`: `209`
- `historical_or_observed_only`: `644`
- `pending_or_non_probability_status`: `186`
- `out_of_scope_or_excluded`: `2`

## Top Gap Reasons

- `OBSERVED_HISTORY_ONLY`: `487`
- `MISSING_FROM_ACTIVE_2026_SOURCE`: `309`
- `IN_SCOPE_MODEL_PENDING`: `34`
- `DATABASE_ONLY_NOT_IN_ACTIVE_FEED`: `5`
- `EXCLUDED_NOT_PREDICTIVE_DRAW`: `2`
- `SOURCE_SUPPORT_INSUFFICIENT`: `1`

## Count Note

- No canonical database candidate in the current repo produced 1,294 unique hunt codes; selected canonical source reports 1645 unique hunt codes.
