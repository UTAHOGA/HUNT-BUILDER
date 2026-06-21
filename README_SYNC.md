# Hunt Prediction Ingestion Sync Bundle

This bundle contains the generated Utah hunt prediction ingestion data plus scripts for two operations:

1. Sync the generated data into a GitHub repository.
2. Submit the generated JSON or ZIP payload to a prediction-engine HTTP ingestion endpoint.

## Current package

Primary data directory: `data/`

Primary machine-readable payload: `data/hunt_engine_ingestion_2024.json`

Compact archive payload: `hunt_prediction_ingestion_2024.zip`

Manifest: `engine_payload_manifest.json`

## Included row counts

- `big_game_draw_point_level.csv`: 37,618 rows
- `big_game_draw_hunt_totals.csv`: 1,122 rows
- `black_bear_draw_point_level.csv`: 4,312 rows
- `black_bear_draw_hunt_totals.csv`: 196 rows
- `sportsman_draw_odds_2025.csv`: 10 rows
- `annual_report_key_metrics.csv`: 13 rows
- `mule_deer_statewide_harvest_history.csv`: 100 rows

## Validate locally

```bash
python3 validate_ingestion.py
```

## Sync to GitHub

Recommended target path:

```text
data/ingestion/utah/2024
```

Example:

```bash
./sync_to_github.sh UTAHOGA/HUNT-PLANNER data/ingestion/utah/2024 ingest/utah-2024-hunt-data main
```

Then open a pull request:

```bash
gh pr create --fill --base main --head ingest/utah-2024-hunt-data
```

You can also target one of the other accessible repositories:

```bash
./sync_to_github.sh UTAHOGA/HUNTS data/ingestion/utah/2024 ingest/utah-2024-hunt-data main
./sync_to_github.sh UTAHOGA/uoga-hunt-planner data/ingestion/utah/2024 ingest/utah-2024-hunt-data main
```

## Submit to prediction engine

This script submits either the JSON payload or ZIP payload as a raw HTTP POST. The engine endpoint may require a different route or headers, so adjust the endpoint and additional headers as needed.

Dry run:

```bash
export PREDICTION_ENGINE_URL="https://your-engine.example.com/ingest"
export PREDICTION_ENGINE_TOKEN="YOUR_TOKEN"
python3 submit_to_engine.py --dry-run
```

Submit JSON:

```bash
python3 submit_to_engine.py   --engine-url "$PREDICTION_ENGINE_URL"   --token "$PREDICTION_ENGINE_TOKEN"   --payload data/hunt_engine_ingestion_2024.json
```

Submit ZIP:

```bash
python3 submit_to_engine.py   --engine-url "$PREDICTION_ENGINE_URL"   --token "$PREDICTION_ENGINE_TOKEN"   --payload hunt_prediction_ingestion_2024.zip   --content-type application/zip
```

## Notes

- The prediction-engine endpoint was not included in the source materials, so the submit script is endpoint-agnostic.
- The GitHub sync script requires local GitHub credentials or an authenticated GitHub CLI session.
- The generated JSON payload is about 30 MB uncompressed; the ZIP payload is much smaller and may be preferable for HTTP upload.
