# Database Hunt-Code Model Gap Audit

## Summary

- Canonical database file used: `pipeline\RAW\hunt_unit_database\2026\csv\DATABASE.csv`
- Database unique hunt-code count: `1645`
- Modeled target hunt-code count: `791`
- Database-to-modeled gap count: `854`
- Coverage target-scope hunt-code count: `1522`
- Coverage-to-database overage count: `-123`

## Bucket Counts

- `in_database_and_modeled`: `791`
- `in_database_not_modeled`: `854`
- `modeled_not_in_database`: `0`
- `coverage_seen_not_in_database`: `209`
- `historical_or_observed_only`: `655`
- `pending_or_non_probability_status`: `110`
- `out_of_scope_or_excluded`: `2`

## Top Gap Reasons

- `OBSERVED_HISTORY_ONLY`: `498`
- `MISSING_FROM_ACTIVE_2026_SOURCE`: `323`
- `IN_SCOPE_MODEL_PENDING`: `14`
- `SOURCE_SUPPORT_INSUFFICIENT`: `9`
- `DATABASE_ONLY_NOT_IN_ACTIVE_FEED`: `8`
- `EXCLUDED_NOT_PREDICTIVE_DRAW`: `2`

## Count Note

- No canonical database candidate in the current repo produced 1,294 unique hunt codes; selected canonical source reports 1645 unique hunt codes.
