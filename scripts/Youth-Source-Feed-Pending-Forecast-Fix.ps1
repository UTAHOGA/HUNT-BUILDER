# Youth-Source-Feed-Pending-Forecast-Fix.ps1
# Named fix: Youth-Source-Feed-Pending-Forecast-Fix
# Purpose: Copy to correct place, Import corrected_species_routing() and _pending_forecast_path() in draw reality builder, Re-run scripts

$ErrorActionPreference = "Stop"
$repoRoot = Get-Location
$downloads = [Environment]::GetFolderPath("UserProfile") + "\Downloads"
$sourceDir = $downloads
if (-not (Test-Path "$sourceDir\Youth-Source-Feed-Pending-Forecast-Fix.py")) {
    if (Test-Path "$repoRoot\Youth-Source-Feed-Pending-Forecast-Fix.py") { $sourceDir = $repoRoot }
    elseif (Test-Path "$repoRoot\..\mnt\data\Youth-Source-Feed-Pending-Forecast-Fix.py") { $sourceDir = "$repoRoot\..\mnt\data" }
    else { $sourceDir = $repoRoot }
}

Write-Host "=== Youth-Source-Feed-Pending-Forecast-Fix ===" -ForegroundColor Cyan
Write-Host "Source: $sourceDir"
Write-Host "Repo: $repoRoot"

# 1. Copy to correct place
New-Item -ItemType Directory -Force -Path "engine\utah\quality" | Out-Null
New-Item -ItemType Directory -Force -Path "engine\utah_draw_predictive" | Out-Null

Copy-Item "$sourceDir\Youth-Source-Feed-Pending-Forecast-Fix.py" "engine\utah\quality\species_routing.py" -Force
Copy-Item "$sourceDir\Youth-Source-Feed-Pending-Forecast-Fix.py" "engine\utah_draw_predictive\species_routing.py" -Force
if (Test-Path "$sourceDir\bear.py") { Copy-Item "$sourceDir\bear.py" "engine\utah_draw_predictive\bear.py" -Force }

Write-Host "Copied Youth-Source-Feed-Pending-Forecast-Fix.py -> engine/utah/quality/species_routing.py" -ForegroundColor Green

# 2. Import in draw reality builder
$patchCode = @'
# --- Youth-Source-Feed-Pending-Forecast-Fix ---
from engine.utah.quality.species_routing import corrected_species_routing, _pending_forecast_path, _build_youth_isolated_ladders, PENDING_NO_HISTORY_2026
# --- End Fix ---
'@

$targets = @("scripts\build_source_mapping_and_hunt_crosswalk.py", "engine\utah\quality\build_source_mapping_and_hunt_crosswalk.py")
foreach ($t in $targets) {
    if (Test-Path $t) {
        $content = Get-Content $t -Raw
        if ($content -notmatch "corrected_species_routing") {
            $content = $patchCode + "`n" + $content
            Set-Content $t $content
            Write-Host "Patched $t" -ForegroundColor Yellow
        }
    }
}

# 3. Re-run
Write-Host "`n=== Re-running ===" -ForegroundColor Cyan
python scripts/build_source_mapping_and_hunt_crosswalk.py
python scripts/score_blind_folds.py --candidate processed_data/draw_reality_engine_predictive_v2.csv --truth data_truth/draw_results_truth/normalized/draw_results_long.csv --output-dir audit_output_real_final/verified_outcome_rescore_20260921_v2 --folds 2017,2018,2019,2020,2021,2022,2023,2024,2025 --verified-outcome-audit

Write-Host "`nDone - Youth-Source-Feed-Pending-Forecast-Fix applied" -ForegroundColor Green
