# Historical Draw Year Availability Audit

This audit is read-only against production truth and raw sources. It only reports whether early years can safely feed the retrospective materializer.

## Results

| Target year | Needed draw year | Readiness | Main normalized rows | Rebuilt candidate rows | Extra normalized rows | Source files | Blocker |
| --- | ---: | --- | ---: | ---: | ---: | ---: | --- |
| 2020 | 2019 | READY_WITH_EXTRA_NORMALIZED_SOURCE | 0 | 57313 | 58155 | 69 |  |
| 2021 | 2020 | READY_WITH_EXTRA_NORMALIZED_SOURCE | 0 | 0 | 6659 | 50 |  |
| 2022 | 2021 | READY_IN_MAIN_NORMALIZED_SOURCE | 27519 | 27519 | 27519 | 48 |  |

## Safe Process Update

- Target 2020 can run only by passing the 2019-for-2020 normalized candidate file as an extra retrospective source.
- Target 2021 is blocked until 2020-for-2021 draw-result rows are normalized and promoted into a materializer-readable CSV.
- Target 2022 is already covered by `draw_results_long.csv` year 2021 rows.
- The audit also inspects `audits/draw_truth_rebuild/draw_results_long_REBUILT_CANDIDATE.csv`; target 2021 remains blocked unless that candidate contains `year=2020` rows.

No production feeder, raw source, website, manifest, R2, or normalized truth file was edited by this audit.
