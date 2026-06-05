# Harvest To Draw Results Reconciliation

This is a read-only comparison of harvest-result hunt/year rows against draw-result hunt/year rows.

## Key Rule

Harvest `permits` are historical harvest-report context. Draw `total_permits` are draw-result context. This report can identify blanks, matches, and conflicts, but it does not overwrite draw truth, harvest truth, `DATABASE.csv`, or runtime files.

## Counts

- Harvest input rows: `68657`
- Draw input rows: `176753`
- Current DATABASE hunt codes: `1471`
- Harvest hunt/year keys: `5151`
- Draw hunt/year keys: `4765`
- Union hunt/year keys: `6089`

## Overall Status

- `DRAW_ONLY_YEAR`: `938`
- `HARVEST_ONLY_YEAR`: `1324`
- `MATCHED_HARVEST_AND_DRAW_YEAR`: `3827`

## Permit Status

- `DRAW_PERMIT_BLANK_HARVEST_AVAILABLE`: `1308`
- `HARVEST_PERMIT_BLANK_DRAW_AVAILABLE`: `390`
- `NO_PERMIT_VALUES`: `564`
- `PERMIT_CONFLICT_REVIEW`: `3058`
- `PERMIT_MATCH`: `769`

## Metadata Status

- `METADATA_CONFLICT`: `3686`
- `METADATA_FILL_CANDIDATE`: `1079`
- `NO_METADATA_TO_COMPARE`: `1324`

## Reconciliation Guidance

- `RECONCILED`: harvest and draw agree at the hunt/year grain.
- `SOURCE_BACKED_FILL_CANDIDATE`: draw metadata or draw permits can explain a harvest blank, but this still needs a controlled repair script before mutation.
- `REVIEW_CONFLICT_DO_NOT_AUTOFILL`: harvest and draw disagree; do not force either side without checking the source PDF/table.
- `DRAW_ONLY_YEAR` and `HARVEST_ONLY_YEAR`: expected in some families due to differing coverage, discontinued hunts, OTC/availability rows, or source package gaps.

- Source-backed fill candidates: `958`
- Conflict review rows: `3807`
