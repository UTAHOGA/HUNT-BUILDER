$ErrorActionPreference = "Continue"

$bucket = "uoga-data"
$log = "audits\prediction_engine_full_audit\PHASE8_REMOTE_WRANGLER_UPLOAD_LOG.txt"

"PHASE 8 REMOTE Wrangler upload started $(Get-Date -Format o)" | Set-Content $log -Encoding UTF8

$uploads = @(
  @{ path="processed_data/draw_reality_engine_predictive_v2.csv"; key="processed_data/draw_reality_engine_predictive_v2.csv" },
  @{ path="processed_data/draw_reality_engine_v2.csv"; key="processed_data/draw_reality_engine_v2.csv" },
  @{ path="processed_data/draw_reality_view.csv"; key="processed_data/draw_reality_view.csv" },
  @{ path="processed_data/ml_draw_predictions_v1.csv"; key="processed_data/ml_draw_predictions_v1.csv" },
  @{ path="processed_data/public_contracts/hunt_predictions.json"; key="processed_data/public_contracts/hunt_predictions.json" },
  @{ path="processed_data/public_contracts/hunt_odds_history.csv"; key="processed_data/public_contracts/hunt_odds_history.csv" },
  @{ path="public/hard-copy/data/documents.json"; key="public/hard-copy/data/documents.json" },
  @{ path="public/hard-copy/data/library_page_data.json"; key="public/hard-copy/data/library_page_data.json" },
  @{ path="public/hard-copy/data/library_page_hunts.csv"; key="public/hard-copy/data/library_page_hunts.csv" },
  @{ path="public/hard-copy/data/library_page_summary.json"; key="public/hard-copy/data/library_page_summary.json" },
  @{ path="public/hard-copy/manifests/hard_data_manifest.json"; key="public/hard-copy/manifests/hard_data_manifest.json" },
  @{ path="audits/prediction_engine_full_audit/PHASE7_PROMOTION_MANIFEST.json"; key="audits/prediction_engine_full_audit/PHASE7_PROMOTION_MANIFEST.json" }
)

foreach ($u in $uploads) {
  if (Test-Path $u.path) {
    Write-Host "REMOTE uploading $($u.path)" -ForegroundColor Green
    "REMOTE uploading $($u.path) -> r2://$bucket/$($u.key)" | Add-Content $log
    npx wrangler r2 object put "$bucket/$($u.key)" --file "$($u.path)" --remote | Tee-Object -Append -FilePath $log
  } else {
    Write-Host "MISSING: $($u.path)" -ForegroundColor Red
    "MISSING: $($u.path)" | Add-Content $log
  }
}

Write-Host "`nREMOTE UPLOAD COMPLETE"
Get-Content $log | Select-Object -Last 80
git status --short
