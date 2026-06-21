<#
.SYNOPSIS
  Clean GitHub Desktop by offloading large repo files to Cloudflare R2, ignoring them,
  and removing them from the Git index without deleting local copies.

.VERSION
  v2 - fixes:
    - No longer fails on untracked large files like point_ladder_view1.csv.
    - Fixes Wrangler whoami invocation.
    - Keeps local files intact.
    - Removes tracked large files from Git index with git rm --cached -f.
    - Adds helper script itself to .gitignore when run from repo root.

.DEFAULTS
  Repo:   C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER
  Bucket: uoga-data
  Large threshold: 50 MB

.EXAMPLES
  # Preview:
  powershell -ExecutionPolicy Bypass -File .\clean_github_desktop_upload_large_to_cloudflare.ps1 -DryRun

  # Upload to Cloudflare R2, ignore, untrack, and stage cleanup metadata:
  powershell -ExecutionPolicy Bypass -File .\clean_github_desktop_upload_large_to_cloudflare.ps1 -Upload -ApplyGitIgnore -RemoveFromGitIndex -StageRepoCleanup
#>

[CmdletBinding()]
param(
  [string]$RepoPath = "C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER",
  [string]$Bucket = "uoga-data",
  [string]$R2Prefix = "hunt-builder/large-files",
  [string]$PublicBaseUrl = "https://json.uoga.workers.dev",
  [int]$LargeThresholdMB = 50,

  [switch]$DryRun,
  [switch]$Upload,
  [switch]$ApplyGitIgnore,
  [switch]$RemoveFromGitIndex,
  [switch]$StageRepoCleanup,
  [switch]$NoWhoami
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$msg) {
  Write-Host ""
  Write-Host "=== $msg ===" -ForegroundColor Cyan
}

function Normalize-RepoPath([string]$path) {
  return (StringOrEmpty $path).Trim().Trim('"') -replace '\\','/'
}

function StringOrEmpty($value) {
  if ($null -eq $value) { return "" }
  return [string]$value
}

function To-RepoRelativePath([string]$absolutePath, [string]$repoRoot) {
  $repoFull = [System.IO.Path]::GetFullPath($repoRoot).TrimEnd('\','/')
  $fileFull = [System.IO.Path]::GetFullPath($absolutePath)
  $uriRepo = New-Object System.Uri($repoFull + [System.IO.Path]::DirectorySeparatorChar)
  $uriFile = New-Object System.Uri($fileFull)
  $rel = [System.Uri]::UnescapeDataString($uriRepo.MakeRelativeUri($uriFile).ToString())
  return Normalize-RepoPath $rel
}

function Get-MimeType([string]$path) {
  switch -Regex ([System.IO.Path]::GetExtension($path).ToLowerInvariant()) {
    '^\.json$' { return 'application/json' }
    '^\.csv$'  { return 'text/csv' }
    '^\.xlsx$' { return 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }
    '^\.xls$'  { return 'application/vnd.ms-excel' }
    '^\.pdf$'  { return 'application/pdf' }
    '^\.zip$'  { return 'application/zip' }
    '^\.kml$'  { return 'application/vnd.google-earth.kml+xml' }
    '^\.kmz$'  { return 'application/vnd.google-earth.kmz' }
    '^\.geojson$' { return 'application/geo+json' }
    '^\.png$'  { return 'image/png' }
    '^\.jpg$|^\.jpeg$' { return 'image/jpeg' }
    '^\.html$' { return 'text/html' }
    default    { return 'application/octet-stream' }
  }
}

function Test-GitTracked([string]$relPath) {
  # IMPORTANT: do not use --error-unmatch here.
  # It throws on untracked large files and stops the whole cleanup.
  $normalizedTarget = Normalize-RepoPath $relPath
  $output = & git ls-files -- "$normalizedTarget" 2>$null
  if ($LASTEXITCODE -ne 0) { return $false }

  foreach ($line in @($output)) {
    if ((Normalize-RepoPath $line) -eq $normalizedTarget) {
      return $true
    }
  }
  return $false
}

function Add-GitIgnoreLines([string[]]$lines, [string]$gitignorePath) {
  if (!(Test-Path $gitignorePath)) {
    New-Item -ItemType File -Path $gitignorePath -Force | Out-Null
  }

  $existing = Get-Content -Path $gitignorePath -Raw -ErrorAction SilentlyContinue
  $pending = New-Object System.Collections.Generic.List[string]

  foreach ($line in $lines) {
    $clean = StringOrEmpty $line
    if ([string]::IsNullOrWhiteSpace($clean)) { continue }
    if ($existing -notmatch [regex]::Escape($clean)) {
      $pending.Add($clean) | Out-Null
    }
  }

  if ($pending.Count -gt 0) {
    Add-Content -Path $gitignorePath -Value ("`n" + ($pending -join [Environment]::NewLine))
  }
}

function Add-GitIgnoreEntries([string[]]$relativePaths, [string]$gitignorePath) {
  $stamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
  $lines = New-Object System.Collections.Generic.List[string]
  $lines.Add("# Cloudflare R2 large-file offload - generated $stamp") | Out-Null

  foreach ($p in $relativePaths | Sort-Object -Unique) {
    $clean = "/" + (Normalize-RepoPath $p).TrimStart('/')
    $lines.Add($clean) | Out-Null
  }

  Add-GitIgnoreLines -lines $lines.ToArray() -gitignorePath $gitignorePath
}

function Setup-WranglerInvoker {
  $script:WranglerExe = $null
  $script:WranglerBaseArgs = @()

  if (Get-Command wrangler -ErrorAction SilentlyContinue) {
    $script:WranglerExe = "wrangler"
    $script:WranglerBaseArgs = @()
    return
  }

  if (Get-Command npx -ErrorAction SilentlyContinue) {
    $script:WranglerExe = "npx"
    $script:WranglerBaseArgs = @("wrangler")
    return
  }

  throw "Neither wrangler nor npx was found. Install/login to Wrangler first."
}

function Invoke-Wrangler([string[]]$Arguments) {
  if ([string]::IsNullOrWhiteSpace($script:WranglerExe)) {
    throw "Wrangler invoker was not initialized."
  }
  & $script:WranglerExe @($script:WranglerBaseArgs + $Arguments)
}

Write-Step "Checking repo"
if (!(Test-Path $RepoPath)) {
  throw "Repo path not found: $RepoPath"
}
Set-Location $RepoPath

$repoRoot = (& git rev-parse --show-toplevel).Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($repoRoot)) {
  throw "Not inside a Git repository: $RepoPath"
}
Set-Location $repoRoot
Write-Host "Repo: $repoRoot"

Write-Step "Checking Wrangler"
Setup-WranglerInvoker
Write-Host "Wrangler command: $script:WranglerExe $($script:WranglerBaseArgs -join ' ')"

if (-not $NoWhoami) {
  try {
    Invoke-Wrangler @("whoami") | Out-Host
  } catch {
    Write-Warning "Wrangler whoami failed. If upload fails, run: wrangler login"
  }
}

Write-Step "Collecting GitHub Desktop-visible files"
$statusLines = & git status --porcelain
$gitVisiblePaths = New-Object System.Collections.Generic.HashSet[string]
foreach ($line in @($statusLines)) {
  if ([string]::IsNullOrWhiteSpace($line)) { continue }
  if ($line.Length -lt 4) { continue }
  $pathPart = $line.Substring(3).Trim()
  if ($pathPart.Contains(" -> ")) {
    $pathPart = ($pathPart -split " -> ")[-1].Trim()
  }
  $pathPart = Normalize-RepoPath $pathPart
  if ($pathPart) { [void]$gitVisiblePaths.Add($pathPart) }
}

$thresholdBytes = [int64]$LargeThresholdMB * 1024 * 1024
$excludedTopDirs = @(".git","node_modules",".wrangler",".venv","venv","__pycache__")

Write-Step "Scanning files over $LargeThresholdMB MB"
$largeFiles = Get-ChildItem -LiteralPath $repoRoot -Recurse -File -Force -ErrorAction SilentlyContinue |
  Where-Object {
    $rel = To-RepoRelativePath $_.FullName $repoRoot
    $top = ($rel -split '/')[0]
    ($excludedTopDirs -notcontains $top) -and
    ($_.Length -ge $thresholdBytes)
  } |
  ForEach-Object {
    $rel = To-RepoRelativePath $_.FullName $repoRoot
    [pscustomobject]@{
      RelativePath = $rel
      AbsolutePath = $_.FullName
      SizeBytes = $_.Length
      SizeMB = [math]::Round($_.Length / 1MB, 2)
      GitVisible = $gitVisiblePaths.Contains($rel)
      GitTracked = Test-GitTracked $rel
      Extension = [System.IO.Path]::GetExtension($_.Name).TrimStart('.').ToLowerInvariant()
    }
  } |
  Sort-Object SizeBytes -Descending

if (!$largeFiles -or $largeFiles.Count -eq 0) {
  Write-Host "No files found over $LargeThresholdMB MB."
  if ($ApplyGitIgnore) {
    $scriptRel = ""
    try {
      $scriptPath = StringOrEmpty $PSCommandPath
      if ($scriptPath -and [System.IO.Path]::GetFullPath($scriptPath).StartsWith([System.IO.Path]::GetFullPath($repoRoot))) {
        $scriptRel = "/" + (To-RepoRelativePath $scriptPath $repoRoot)
      }
    } catch {}
    if ($scriptRel) {
      Add-GitIgnoreLines -lines @("# Local helper scripts", $scriptRel) -gitignorePath (Join-Path $repoRoot ".gitignore")
      Write-Host "Ignored helper script: $scriptRel"
    }
  }
  & git status --short
  exit 0
}

$largeFiles | Format-Table RelativePath, SizeMB, GitVisible, GitTracked, Extension -AutoSize

$manifestRows = @()
$uploadedOk = New-Object System.Collections.Generic.List[string]

if ($DryRun -or -not $Upload) {
  Write-Step "Dry run / no upload mode"
  Write-Host "No files uploaded."
  Write-Host "To upload and clean index, rerun with:" -ForegroundColor Yellow
  Write-Host "powershell -ExecutionPolicy Bypass -File .\clean_github_desktop_upload_large_to_cloudflare.ps1 -Upload -ApplyGitIgnore -RemoveFromGitIndex -StageRepoCleanup" -ForegroundColor Yellow
} else {
  Write-Step "Uploading large files to Cloudflare R2 bucket '$Bucket'"
  foreach ($file in $largeFiles) {
    $key = (($R2Prefix.TrimEnd('/')) + "/" + $file.RelativePath).Replace('\','/')
    $objectPath = "$Bucket/$key"
    $mime = Get-MimeType $file.AbsolutePath
    Write-Host "Uploading $($file.RelativePath) -> r2://$objectPath"

    $uploadArgs = @("r2","object","put",$objectPath,"--file",$file.AbsolutePath,"--content-type",$mime)
    Invoke-Wrangler $uploadArgs

    if ($LASTEXITCODE -ne 0) {
      throw "Upload failed for $($file.RelativePath). Stopping before Git index cleanup."
    }

    $uploadedOk.Add($file.RelativePath) | Out-Null
    $publicUrl = ""
    if ($PublicBaseUrl) {
      $publicUrl = $PublicBaseUrl.TrimEnd('/') + "/" + $key
    }

    $manifestRows += [pscustomobject]@{
      local_path = $file.RelativePath
      size_bytes = $file.SizeBytes
      size_mb = $file.SizeMB
      git_tracked = $file.GitTracked
      r2_bucket = $Bucket
      r2_key = $key
      r2_uri = "r2://$objectPath"
      public_url_candidate = $publicUrl
      uploaded_at = (Get-Date).ToString("s")
    }
  }
}

if ($uploadedOk.Count -gt 0 -or $DryRun) {
  Write-Step "Writing R2 manifest"
  $manifestDir = Join-Path $repoRoot "processed_data"
  if (!(Test-Path $manifestDir)) {
    New-Item -ItemType Directory -Path $manifestDir -Force | Out-Null
  }

  if ($manifestRows.Count -eq 0) {
    $manifestRows = $largeFiles | ForEach-Object {
      $key = (($R2Prefix.TrimEnd('/')) + "/" + $_.RelativePath).Replace('\','/')
      [pscustomobject]@{
        local_path = $_.RelativePath
        size_bytes = $_.SizeBytes
        size_mb = $_.SizeMB
        git_tracked = $_.GitTracked
        r2_bucket = $Bucket
        r2_key = $key
        r2_uri = "r2://$Bucket/$key"
        public_url_candidate = if ($PublicBaseUrl) { $PublicBaseUrl.TrimEnd('/') + "/" + $key } else { "" }
        uploaded_at = if ($DryRun) { "DRY_RUN_NOT_UPLOADED" } else { "" }
      }
    }
  }

  $csvPath = Join-Path $manifestDir "cloudflare_large_file_manifest.csv"
  $jsonPath = Join-Path $manifestDir "cloudflare_large_file_manifest.json"
  $manifestRows | Export-Csv -Path $csvPath -NoTypeInformation -Encoding UTF8
  $manifestRows | ConvertTo-Json -Depth 5 | Set-Content -Path $jsonPath -Encoding UTF8
  Write-Host "Manifest CSV:  $csvPath"
  Write-Host "Manifest JSON: $jsonPath"
}

if ($ApplyGitIgnore) {
  Write-Step "Adding large file paths to .gitignore"
  $gitignorePath = Join-Path $repoRoot ".gitignore"

  $pathsToIgnore = @($largeFiles.RelativePath)

  # Also ignore this local helper script if it lives inside the repo.
  try {
    $scriptPath = StringOrEmpty $PSCommandPath
    if ($scriptPath -and [System.IO.Path]::GetFullPath($scriptPath).StartsWith([System.IO.Path]::GetFullPath($repoRoot))) {
      $pathsToIgnore += (To-RepoRelativePath $scriptPath $repoRoot)
    }
  } catch {}

  Add-GitIgnoreEntries -relativePaths $pathsToIgnore -gitignorePath $gitignorePath
  Write-Host "Updated .gitignore"
}

if ($RemoveFromGitIndex) {
  Write-Step "Removing tracked large files from Git index while keeping local files"
  foreach ($file in $largeFiles) {
    if ($file.GitTracked) {
      Write-Host "git rm --cached -f -- $($file.RelativePath)"
      & git rm --cached -f -- "$($file.RelativePath)"
      if ($LASTEXITCODE -ne 0) {
        throw "git rm --cached failed for $($file.RelativePath)"
      }
    } else {
      Write-Host "Not tracked; no git rm needed: $($file.RelativePath)"
    }
  }
}

if ($StageRepoCleanup) {
  Write-Step "Staging cleanup metadata only"
  if (Test-Path ".gitignore") {
    & git add .gitignore
  }
  if (Test-Path "processed_data/cloudflare_large_file_manifest.csv") {
    & git add processed_data/cloudflare_large_file_manifest.csv
  }
  if (Test-Path "processed_data/cloudflare_large_file_manifest.json") {
    & git add processed_data/cloudflare_large_file_manifest.json
  }
}

Write-Step "Final Git status"
& git status --short

Write-Host ""
Write-Host "NEXT:" -ForegroundColor Green
Write-Host "1) Review GitHub Desktop. Large files should be ignored/untracked, not deleted locally."
Write-Host "2) If status looks right:"
Write-Host "   git commit -m `"Offload large files to Cloudflare R2`""
Write-Host "   git push"
