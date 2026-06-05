# Field Permit Overlay Hypothesis Audit

This read-only audit tests Tyler's hypothesis that harvest-report `permits` often represent permits in the field after adding Expo, Conservation, and related overlay permits to public draw results.

## Verdict

`SUPPORTED_FOR_SOME_ROWS_REQUIRES_REVIEW`

The model should add a separate `field_permits_total` concept, not overwrite public draw permits. Public draw permits feed draw odds; field permits explain harvest reports and fall field totals.

## Counts

- Overlay rows loaded: `757`
- Permit conflict rows tested: `3058`

## Overlay Families

- `CONSERVATION_2025_2027`: `194`
- `CONSERVATION_LIBRARY_MASTER`: `318`
- `EXPO_2025_NAME_ONLY`: `122`
- `EXPO_2026_NAME_ONLY`: `123`

## Gap Status

- `FIELD_PERMIT_GAP_EXPLAINED_BY_OVERLAYS`: `96`
- `FIELD_PERMIT_GAP_PARTIALLY_EXPLAINED_BY_OVERLAYS`: `183`
- `NOT_OVERLAY_EXPLAINED_DRAW_GE_HARVEST`: `735`
- `NO_OVERLAY_MATCH_FOUND`: `1814`
- `OVERLAY_CANDIDATES_EXCEED_GAP_REVIEW`: `230`

## Recommended Data Contract

- Keep `draw_public_permits_total` for draw odds and ladder math.
- Keep `harvest_report_permits` as source-reported harvest context.
- Add derived/reviewed `field_permits_total = draw_public_permits_total + overlay_permits_total` only when overlay evidence is source-backed.
- Track `overlay_permits_total`, `overlay_families`, `overlay_source_files`, and `field_permits_reconciliation_status`.
- Do not let Expo/Conservation/Sportsman overlays inflate public draw odds probability denominators.
