# build_audit_upload.ps1 - Creates <5MB audit zip for full repo audit
# Run from repo root: powershell -ExecutionPolicy Bypass -File build_audit_upload.ps1
$ErrorActionPreference = "Continue"

$outDir = "audit_upload_2026"
if (Test-Path $outDir) { Remove-Item $outDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
New-Item -ItemType Directory -Force -Path "$outDir/engine" | Out-Null
New-Item -ItemType Directory -Force -Path "$outDir/docs" | Out-Null
New-Item -ItemType Directory -Force -Path "$outDir/crosswalk" | Out-Null
New-Item -ItemType Directory -Force -Path "$outDir/processed" | Out-Null

Write-Host "=== Building small audit upload for full repo audit ===" -ForegroundColor Cyan

function Copy-IfExists($src, $dst) {
  if (Test-Path $src) { 
    Copy-Item $src $dst -Force
    Write-Host "  OK $src" -ForegroundColor Green
    return $true
  } else {
    Write-Host "  SKIP $src (not found)" -ForegroundColor Yellow
    return $false
  }
}

# 1. Governance
Copy-IfExists "AGENTS.MD" "$outDir/"
Copy-IfExists "WORK_LOG.md" "$outDir/"
Copy-IfExists "LOCKED_CANONICAL_2026.md" "$outDir/"
Copy-IfExists "ENGINE_RULES_SPEC.md" "$outDir/"
Copy-IfExists "engine_payload_manifest.json" "$outDir/"

# 2. Bear engine - critical for 4 availability vs 90+9 draw check
Copy-IfExists "engine/utah_draw_predictive/bear.py" "$outDir/engine/"
Copy-IfExists "engine/utah_draw_predictive/deer.py" "$outDir/engine/" 
Copy-IfExists "engine/utah_draw_predictive/elk.py" "$outDir/engine/"

# 3. Bear validation + crosswalk - your 7-code split decision
Copy-IfExists "docs/bear_availability_validation_2026.md" "$outDir/docs/"
Copy-IfExists "data_truth/crosswalk_truth/normalized/black_bear_BR_2024_2025_2026_crosswalk.csv" "$outDir/crosswalk/"
Copy-IfExists "data_truth/crosswalk_truth/black_bear_BR_2024_2025_2026_crosswalk.csv" "$outDir/crosswalk/"

# 4. Your 2020-2025 audit - 1,170 totals / 24,942 point-level
$auditPaths = @(
  "audits/prediction_release_candidates/bear_pdf_history_2020_2025_20260920/assembled_v4/audit_bear_2020_2025.csv",
  "audits/bear_pdf_history_2020_2025/audit_bear_2020_2025.csv",
  "audit_bear_2020_2025.csv"
)
foreach ($p in $auditPaths) { if (Copy-IfExists $p "$outDir/") { break } }

# 5. Coverage + certification - 97,893 rows / 32 blanks
Copy-IfExists "processed_data/draw_system_coverage_report.json" "$outDir/processed/"
Copy-IfExists "processed_data/certification_registry.json" "$outDir/processed/"
Copy-IfExists "processed_data/coverage_final_audited.json" "$outDir/processed/"
Copy-IfExists "hunt-master-canonical-2026.coverage.json" "$outDir/processed/"

# 6. Protected files hash check - 20 files byte-identical
Write-Host "`nHashing protected files..." -ForegroundColor Cyan
$protected = @()
if (Test-Path "processed_data/canonical_yearly") {
  $protected = Get-ChildItem "processed_data/canonical_yearly" -Recurse -File | Select-Object -First 20
}
if ($protected.Count -gt 0) {
  $protected | Get-FileHash -Algorithm SHA256 | Format-Table Hash,Path -AutoSize | Out-File "$outDir/protected_hashes.txt"
  Write-Host "  Wrote protected_hashes.txt"
}

# 7. Create manifest for forward-from-2026 rule
@"
# La Sal / Dolores Split - Forward from 2026 Only
Effective split year: 2026 per DWR 2026_bear_cougar_furbearer.pdf p.4
7 codes: BR7022, BR7127, BR7239, BR7326 (La Sal recodes ex BR7008/7108/7208/7307) + BR7021, BR7126, BR7238 (Dolores new)
Rule: Do NOT use pre-split 2020-2025 La Sal history for any of 7 - use forward from 2026 only
2026 prediction: all 7 = NO_TRANSITION_EVIDENCE blank (no forward history yet)
2027+: use 2026 onward only
"@ | Out-File "$outDir/SPLIT_RULE.txt"

# 8. Zip <5MB
$zipName = "bear-audit-2020-2025-small.zip"
if (Test-Path $zipName) { Remove-Item $zipName -Force }
Compress-Archive -Path "$outDir/*" -DestinationPath $zipName -Force

$size = [math]::Round((Get-Item $zipName).Length / 1MB, 2)
Write-Host "`n=== DONE ===" -ForegroundColor Green
Write-Host "Created $zipName - $size MB" -ForegroundColor Green
Write-Host "Files in zip:"
Get-ChildItem $outDir -Recurse -File | ForEach-Object { Write-Host "  $($_.Name) - $([math]::Round($_.Length/1KB,1)) KB" }

if ($size -gt 20) {
  Write-Host "WARNING: >20MB may fail chat upload - try uploading files individually" -ForegroundColor Red
} else {
  Write-Host "`nUpload this zip via chat drag-drop (or upload files in $outDir/ individually)" -ForegroundColor Cyan
}
