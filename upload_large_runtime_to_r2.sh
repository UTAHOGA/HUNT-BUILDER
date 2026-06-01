#!/usr/bin/env bash
set -euo pipefail

BUCKET="uoga-data"

upload() {
  local local_path="$1"
  local remote_key="$2"
  echo "Uploading $local_path -> $remote_key"
  wrangler r2 object put "$BUCKET/$remote_key" --file "$local_path"
}

upload "processed_data/public_contracts/hunt_odds_history.json" "processed_data/public_contracts/hunt_odds_history.json"
upload "processed_data/hunt_research_2026.json" "processed_data/hunt_research_2026.json"
upload "processed_data/statewide_composite_boundaries_2026.geojson" "processed_data/statewide_composite_boundaries_2026.geojson"
upload "processed_data/statewide_composite_boundaries_2026_final_locked.geojson" "processed_data/statewide_composite_boundaries_2026_final_locked.geojson"
upload "processed_data/composite_hunt_unit_mapping_2026.geojson" "processed_data/composite_hunt_unit_mapping_2026.geojson"
upload "processed_data/draw_reality_engine_predictive_v2.csv" "processed_data/draw_reality_engine_predictive_v2.csv"
upload "processed_data/draw_reality_engine.csv" "processed_data/draw_reality_engine.csv"
upload "processed_data/hunt_master_enriched.csv" "processed_data/hunt_master_enriched.csv"
upload "processed_data/hunt_master_enriched_2026_draw_subset.csv" "processed_data/hunt_master_enriched_2026_draw_subset.csv"
upload "processed_data/draw_system_coverage_report.csv" "processed_data/draw_system_coverage_report.csv"

echo "Done."
