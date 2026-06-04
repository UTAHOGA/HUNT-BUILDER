# Engine Readiness Report

Generated: 2026-06-01T05:48:56.726Z

| Engine/Page | Status | Can Populate | Confidence | Critical Holes | Next Fix |
|---|---:|---:|---:|---|---|
| Hunt Builder selection/filter/map | READY | no | HIGH | None flagged in top audit | Keep DATABASE/reference/boundary IDs aligned. |
| Hunt Research core summary | READY | no | HIGH | None flagged in top audit | Maintain Cloudflare-first runtime CSV delivery. |
| Point ladder | READY | yes | HIGH | None flagged in top audit | Review current hunts missing ladder/status rows. |
| Predictive draw odds | BLOCKED | no | MEDIUM | None flagged in top audit | Resolve pending families after source sync; do not change formulas in audit task. |
| Comparable hunts | BLOCKED | no | MEDIUM | None flagged in top audit | Improve comparable scoring after field consistency audit. |
| Harvest quality | BLOCKED | no | MEDIUM | None flagged in top audit | Continue annual harvest crosswalk lineage repair. |
| Age quality | BLOCKED | no | MEDIUM | None flagged in top audit | Keep observed average_harvest_age separate from days and 3-year current age. |
| State management objective | NEEDS_SOURCE_SYNC | yes | MEDIUM | DA1001<br>DA1002<br>DA1003<br>DA1009<br>DA1018 | Render benchmark-only unless observed comparison exists. |
| Outfitter matching | READY | yes | MEDIUM | None flagged in top audit | Add reviewed coverage/boundary links. |
| Public library | READY | yes | MEDIUM | None flagged in top audit | Keep library mapping statuses explicit and audit moved PDFs. |

## Summary Counts

- inventory_files: 3232
- sync_edges: 10
- data_holes: 2086
- year_to_year_flags: 2563
- runtime_sources_tested: 20
- runtime_sources_ok: 10
- engines_ready: 5
- engines_partial: 0
- engines_blocked: 4
- engines_placeholder_only: 0
- engines_needs_source_sync: 1
