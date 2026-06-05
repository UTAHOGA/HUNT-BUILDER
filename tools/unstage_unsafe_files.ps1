$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

$blockedExtensions = @(
  ".zip", ".7z", ".rar", ".tar", ".gz", ".pdf", ".xlsx", ".xls",
  ".parquet", ".sqlite", ".db", ".gpkg", ".mbtiles", ".tif", ".tiff",
  ".shp", ".shx", ".dbf", ".prj", ".kml", ".kmz"
)

$blockedPrefixes = @(
  "pipeline/RAW/",
  "pipeline/INGEST/inbox/",
  "pipeline/INGEST/archive/",
  "pipeline/R2_OFFLOAD/incoming/",
  "pipeline/R2_OFFLOAD/uploaded/",
  "processed_data/backups/",
  "processed_data/hunt_research_2026_split/",
  "data_model/runtime_drafts/",
  "data_model/harvest_quality/",
  "data_truth/comparison_outputs/"
)

$maxBytes = 10MB
$staged = git diff --cached --name-only
$unsafe = New-Object System.Collections.Generic.List[string]

foreach ($path in $staged) {
  if (-not $path) { continue }
  $normalized = $path -replace "\\", "/"
  $statusLine = git diff --cached --name-status -- "$path" | Select-Object -First 1
  if ($statusLine -match "^D\\s") { continue }

  $blocked = $false
  foreach ($prefix in $blockedPrefixes) {
    if ($normalized.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
      $blocked = $true
    }
  }
  if ($blockedExtensions -contains ([System.IO.Path]::GetExtension($normalized).ToLowerInvariant())) {
    $blocked = $true
  }
  if (Test-Path -LiteralPath $path -PathType Leaf) {
    if ((Get-Item -LiteralPath $path).Length -gt $maxBytes) {
      $blocked = $true
    }
  }
  if ($blocked) {
    $unsafe.Add($path)
  }
}

if ($unsafe.Count -eq 0) {
  Write-Host "No unsafe staged additions/modifications found."
  exit 0
}

foreach ($path in $unsafe) {
  Write-Host "Unstaging unsafe file: $path"
  git restore --staged -- "$path"
}

Write-Host "Unstaged $($unsafe.Count) unsafe file(s). Local files were not deleted."
