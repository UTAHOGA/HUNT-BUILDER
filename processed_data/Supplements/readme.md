# 2026 Supplement Patches

Use this folder to add local/online corrections that fill empty or missing 2026 hunt data.

## Files
- `hunt_database_2026_patch.template.csv`: starter schema for patch rows.
- `hunt_database_2026_patch.csv`: your working patch file (create this from the template).

## How to run
1. Copy template:
   - `cp processed_data/supplements/hunt_database_2026_patch.template.csv processed_data/supplements/hunt_database_2026_patch.csv`
2. Add patch rows.
3. Apply patches:
   - `npm run apply:2026:supplements`
   - Optional custom file: `node apply-2026-supplements.js --patch=processed_data/supplements/my_patch.csv`
4. Re-audit completeness:
   - `npm run audit:2026`

## Patch row schema
- `hunt_code`
- `residency`
- `field` (must exactly match a column name in `processed_data/hunt_database_complete.csv`)
- `value`
- `force_overwrite` (`true` or `false`)
- `source_note` (optional provenance notes)

## Rules
- Match key is `hunt_code + residency`.
- Unknown hunts or fields are skipped.
- Existing values are only overwritten when `force_overwrite=true`.
