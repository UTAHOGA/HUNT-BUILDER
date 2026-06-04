# Research Feeder Permit Sync From DATABASE

Generated: `2026-06-04T06:43:39+00:00`

## Scope

Synced the four Research feeder surfaces against cleaned `DATABASE.csv` permit fields. This pass did not change draw odds or probability math.

## Results

| Feeder | Rows | Matched rows | Changed rows | Changed cells | Added columns | Status |
|---|---:|---:|---:|---:|---|---|
| `hunt_master_enriched` | 53225 | 53225 | 52911 | 498551 | permits_2024_res, permits_2024_nr, permits_2024_total, permits_2024_source | REPLACED_LFS_POINTER_FROM::C:\Users\tyler\Desktop\GitHub\Cloudfare\hunt_master_enriched.csv |
| `hunt_unit_reference_linked` | 2997 | 2875 | 2751 | 22264 | permits_2024_res, permits_2024_nr, permits_2024_total, permits_2024_source | REAL_LOCAL_FILE |
| `draw_reality_engine` | 36892 | 32800 | 32662 | 339000 | permits_2024_res, permits_2024_nr, permits_2024_total, permits_2024_source | REAL_LOCAL_FILE |
| `point_ladder_view` | 91712 | 91712 | 81414 | 690886 | permits_2024_res, permits_2024_nr, permits_2024_total, permits_2024_source | REAL_LOCAL_FILE |

## Notes

- `processed_data/hunt_master_enriched.csv` was replaced from the real local Cloudfare copy only because the repo copy was a Git LFS pointer.
- Existing machine fields were preserved for runtime compatibility.
- `permits_2026_*` in feeder files now mirrors current `DATABASE.csv` 2026 allotment values and is labeled as the 2026 draw-results/current-permit field for 2027 model use.

## Outputs

- Audit CSV: `processed_data\audits\research_feeder_database_permit_sync_audit.csv`
- Summary JSON: `processed_data\audits\research_feeder_database_permit_sync_summary.json`
