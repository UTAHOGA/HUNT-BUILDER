# Research Feeder Permit Sync From DATABASE

Generated: `2026-06-27T06:06:17+00:00`

## Scope

Synced the runtime/reference feeder surfaces against cleaned `DATABASE.csv` permit fields. This pass did not change draw odds or probability math.

## Results

| Feeder | Rows | Matched rows | Changed rows | Changed cells | Added columns | Status |
|---|---:|---:|---:|---:|---|---|
| `hunt_master_enriched` | 56153 | 56049 | 0 | 0 | none | REAL_LOCAL_FILE |
| `hunt_unit_reference_linked` | 3776 | 3670 | 500 | 2388 | none | REAL_LOCAL_FILE |
| `point_ladder_view` | 92436 | 92332 | 91438 | 258686 | none | REAL_LOCAL_FILE |
| `point_ladder_runtime_actual_draw_v2026` | 78162 | 78094 | 0 | 0 | none | REAL_LOCAL_FILE |
| `point_ladder_allocation_complete_v2026` | 91588 | 91588 | 9768 | 12408 | none | REAL_LOCAL_FILE |
| `point_ladder_unified_runtime_v2026` | 153220 | 153152 | 9768 | 12408 | none | REAL_LOCAL_FILE |

## Notes

- `processed_data/hunt_master_enriched.csv` was replaced from the real local Cloudfare copy only because the repo copy was a Git LFS pointer.
- Existing machine fields were preserved for runtime compatibility.
- `permits_2026_*` in feeder files now mirrors current `DATABASE.csv` published 2026 permit values and is labeled as the 2027-model current permit field.

## Outputs

- Audit CSV: `processed_data\audits\research_feeder_database_permit_sync_audit.csv`
- Summary JSON: `processed_data\audits\research_feeder_database_permit_sync_summary.json`
