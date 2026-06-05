# Hunt Research Harvest Feature Promotion Audit

This is a read-only audit. It does not mutate `DATABASE.csv`, draw truth, engine code, probability fields, quota fields, or runtime manifests.

## Verdict

Harvest results are already ingested. The correct next step is not raw harvest ingestion; it is controlled promotion of reviewed harvest quality/context features into Hunt Research.

## Counts

- Current DATABASE hunt codes: `1471`
- Harvest feature rows: `1411`
- Harvest feature unique hunt codes: `1411`
- Harvest truth rows: `68657`
- Harvest truth unique hunt codes: `1424`
- Hunt Research summary unique hunt codes: `1471`

## Promotion Status

- `NO_HARVEST_HISTORY_FOUND`: `5`
- `RAW_HISTORY_EXISTS_FEATURE_MISSING`: `56`
- `READY_FOR_HUNT_RESEARCH_CONTEXT`: `1410`

## Harvest Feature Grades

- `A`: `964`
- `B`: `25`
- `C`: `350`
- `D`: `70`
- `F`: `1`
- `NOT_APPLICABLE`: `61`

## Safe Hunt Research Uses

- Quality cards: harvest success, harvest trend, hunter effort, average age, harvest-quality index.
- Demand context: pressure signal, effort signal, harvest trend, point-creep quality adjustment.
- Sleeper hunt logic: high quality / lower demand / tolerable odds, with draw odds still produced by draw engine.
- Point-creep explanation: demand pressure and quality adjustment can explain why a hunt is heating up or cooling off.

## Forbidden Uses

- Do not use harvest data to overwrite `p_draw`, `p_draw_pct`, `display_odds_pct`, max-pool odds, random-pool odds, 2026 permits, or 2026 allotments.
- Do not infer current quotas from historical harvest reports.
- Do not treat missing harvest history as zero quality.

## Engine Architecture Placement

1. `DATABASE.csv` defines the current hunt universe, boundary IDs, current permit/allotment truth, and current hunt metadata.
2. Draw truth and point ladder files define observed historical draw behavior and ladder rows.
3. Harvest truth defines quality, effort, demand, and age context.
4. The prediction engine should forecast applicant pressure and quota environment, then route rows into deterministic Utah draw mechanics.
5. Hunt Research should display draw-ladder math separately from harvest-quality context so users know what is odds math and what is hunt-quality evidence.

## Recommended Next Step

Promote only PROMOTE_CONTEXT_ONLY fields into Hunt Research display/scoring after reviewing FEATURE_READY_SUMMARY_MISSING and RAW_HISTORY_EXISTS_FEATURE_MISSING rows.
