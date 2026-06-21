[CmdletBinding()]
param(
    [string]$Repo = "C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER",
    [string]$Bucket = "uoga-data",
    [string]$Prefix = "hunt-builder",
    [string]$PublicBaseUrl = "https://json.uoga.workers.dev",
    [int]$MinMB = 25,
    [switch]$UploadAllStagedExisting,
    [switch]$CommitChanges,
    [string]$CommitMessage = "Move large artifacts to Cloudflare R2 and ignore locally",
    [switch]$Execute
)

$ErrorActionPreference = "Stop"

function Write-Step($msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

function Invoke-Checked {
    param(
        [string]$Exe,
        [string[]]$Args
    )

    $printable = "$Exe " + (($Args | ForEach-Object {
        if ($_ -match '\s') { '"' + $_ + '"' } else { $_ }
    }) -join " ")

    if (-not $Execute) {
        Write-Host "[DRY RUN] $printable" -ForegroundColor Yellow
        return
    }

    Write-Host $printable -ForegroundColor DarkGray
    & $Exe @Args

    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $printable"
    }
}

function Invoke-Git {
    param([string[]]$Args)
    Invoke-Checked -Exe "git" -Args $Args
}

function Invoke-Wrangler {
    param([string[]]$Args)

    $wrangler = Get-Command wrangler -ErrorAction SilentlyContinue
    if ($wrangler) {
        Invoke-Checked -Exe "wrangler" -Args $Args
        return
    }

    $npx = Get-Command npx -ErrorAction SilentlyContinue
    if ($npx) {
        Invoke-Checked -Exe "npx" -Args (@("wrangler") + $Args)
        return
    }

    throw "Wrangler was not found. Install/login first, then rerun: npm install -g wrangler ; wrangler login"
}

function Get-ContentType {
    param([string]$Path)

    switch ([System.IO.Path]::GetExtension($Path).ToLowerInvariant()) {
        ".csv"     { return "text/csv" }
        ".json"    { return "application/json" }
        ".jsonl"   { return "application/x-ndjson" }
        ".geojson" { return "application/geo+json" }
        ".kml"     { return "application/vnd.google-earth.kml+xml" }
        ".kmz"     { return "application/vnd.google-earth.kmz" }
        ".pdf"     { return "application/pdf" }
        ".zip"     { return "application/zip" }
        ".xlsx"    { return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }
        ".xls"     { return "application/vnd.ms-excel" }
        ".png"     { return "image/png" }
        ".jpg"     { return "image/jpeg" }
        ".jpeg"    { return "image/jpeg" }
        ".webp"    { return "image/webp" }
        default    { return "application/octet-stream" }
    }
}

Write-Step "Opening repo"
Set-Location $Repo

$RepoRoot = (& git rev-parse --show-toplevel).Trim()
if (-not $RepoRoot) {
    throw "Not inside a Git repository: $Repo"
}

Set-Location $RepoRoot
Write-Host "Repo: $RepoRoot"
Write-Host "Bucket: $Bucket"
Write-Host "Prefix: $Prefix"

Write-Step "Capturing current GitHub Desktop staged files"
$InitialStaged = @(& git diff --cached --name-only)
$TrackedFiles = @(& git ls-files)

$AllowedExtensions = @(
    ".csv", ".json", ".jsonl", ".geojson",
    ".kml", ".kmz",
    ".pdf", ".zip",
    ".xlsx", ".xls",
    ".parquet", ".sqlite", ".db",
    ".pkl", ".bin",
    ".png", ".jpg", ".jpeg", ".webp"
)

$MinBytes = [int64]$MinMB * 1MB
$Targets = @{}

foreach ($rel in ($InitialStaged + $TrackedFiles | Sort-Object -Unique)) {
    if ([string]::IsNullOrWhiteSpace($rel)) { continue }

    $full = Join-Path $RepoRoot $rel

    if (-not (Test-Path -LiteralPath $full -PathType Leaf)) {
        continue
    }

    $item = Get-Item -LiteralPath $full
    $ext = [System.IO.Path]::GetExtension($item.Name).ToLowerInvariant()
    $isLargeAllowed = ($item.Length -ge $MinBytes -and $AllowedExtensions -contains $ext)
    $isStagedExisting = ($UploadAllStagedExisting -and ($InitialStaged -contains $rel))

    if ($isLargeAllowed -or $isStagedExisting) {
        $normalizedRel = $rel.Replace("\", "/")
        $Targets[$normalizedRel] = $item
    }
}

if ($Targets.Count -eq 0) {
    Write-Host "No upload targets found."
    Write-Host "Lower -MinMB or add -UploadAllStagedExisting if you want all currently staged existing files uploaded."
    exit 0
}

Write-Step "Targets selected"
foreach ($rel in ($Targets.Keys | Sort-Object)) {
    $mb = [Math]::Round($Targets[$rel].Length / 1MB, 2)
    Write-Host "$mb MB  $rel"
}

Write-Step "Clearing current staged area safely"
Invoke-Git @("restore", "--staged", ".")

Write-Step "Uploading files to Cloudflare R2"
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$ManifestDir = Join-Path $RepoRoot "audits\r2_large_file_handoff\$Stamp"
$ManifestPath = Join-Path $ManifestDir "r2_upload_manifest.csv"

if ($Execute) {
    New-Item -ItemType Directory -Force -Path $ManifestDir | Out-Null
}

$ManifestRows = @()
$UploadedRelPaths = @()

foreach ($rel in ($Targets.Keys | Sort-Object)) {
    $item = $Targets[$rel]

    $cleanPrefix = $Prefix.Trim("/")
    if ($cleanPrefix.Length -gt 0) {
        $key = "$cleanPrefix/$rel"
    } else {
        $key = $rel
    }

    $objectPath = "$Bucket/$key"
    $contentType = Get-ContentType $item.FullName
    $publicUrl = ""

    if (-not [string]::IsNullOrWhiteSpace($PublicBaseUrl)) {
        $publicUrl = $PublicBaseUrl.TrimEnd("/") + "/" + $key
    }

    Write-Host ""
    Write-Host "Uploading: $rel" -ForegroundColor Green
    Write-Host "R2: r2://$Bucket/$key"

    Invoke-Wrangler @(
        "r2", "object", "put", $objectPath,
        "--file", $item.FullName,
        "--content-type", $contentType,
        "--remote",
        "--force"
    )

    $UploadedRelPaths += $rel

    $ManifestRows += [pscustomobject]@{
        local_path   = $rel
        bytes        = $item.Length
        mb           = [Math]::Round($item.Length / 1MB, 2)
        content_type = $contentType
        r2_uri       = "r2://$Bucket/$key"
        public_url   = $publicUrl
        uploaded_at  = (Get-Date).ToString("s")
    }
}

Write-Step "Writing upload manifest"
if ($Execute) {
    $ManifestRows | Export-Csv -Path $ManifestPath -NoTypeInformation -Encoding UTF8
    Write-Host "Manifest: $ManifestPath"
} else {
    Write-Host "[DRY RUN] Would write manifest to: $ManifestPath" -ForegroundColor Yellow
}

Write-Step "Adding uploaded files to .gitignore"
$GitIgnorePath = Join-Path $RepoRoot ".gitignore"

if ($Execute -and -not (Test-Path -LiteralPath $GitIgnorePath)) {
    New-Item -ItemType File -Path $GitIgnorePath | Out-Null
}

$ExistingIgnoreLines = @()
if (Test-Path -LiteralPath $GitIgnorePath) {
    $ExistingIgnoreLines = @(Get-Content -LiteralPath $GitIgnorePath)
}

$NewIgnoreLines = @()
foreach ($rel in ($UploadedRelPaths | Sort-Object -Unique)) {
    $ignoreLine = "/" + $rel.TrimStart("/")
    if ($ExistingIgnoreLines -notcontains $ignoreLine) {
        $NewIgnoreLines += $ignoreLine
    }
}

if ($NewIgnoreLines.Count -gt 0) {
    if ($Execute) {
        Add-Content -LiteralPath $GitIgnorePath -Value ""
        Add-Content -LiteralPath $GitIgnorePath -Value "# Cloudflare R2 local-only artifacts - $Stamp"
        foreach ($line in $NewIgnoreLines) {
            Add-Content -LiteralPath $GitIgnorePath -Value $line
        }
    } else {
        Write-Host "[DRY RUN] Would add these .gitignore entries:" -ForegroundColor Yellow
        $NewIgnoreLines | ForEach-Object { Write-Host "  $_" }
    }
} else {
    Write-Host "No new .gitignore entries needed."
}

Write-Step "Removing uploaded files from Git tracking without deleting local files"
foreach ($rel in ($UploadedRelPaths | Sort-Object -Unique)) {
    Invoke-Git @("rm", "--cached", "--ignore-unmatch", "--", $rel)
}

Write-Step "Staging .gitignore and manifest"
Invoke-Git @("add", "--", ".gitignore")

if ($Execute) {
    $manifestRel = Resolve-Path -LiteralPath $ManifestPath -Relative
    $manifestRel = $manifestRel.TrimStart(".\").Replace("\", "/")
    Invoke-Git @("add", "--", $manifestRel)
} else {
    Write-Host "[DRY RUN] Would git add the manifest CSV." -ForegroundColor Yellow
}

if ($CommitChanges) {
    Write-Step "Committing cleanup"
    Invoke-Git @("commit", "-m", $CommitMessage)
} else {
    Write-Host ""
    Write-Host "Not committing because -CommitChanges was not supplied." -ForegroundColor Yellow
    Write-Host "GitHub Desktop will still show the cleanup changes until they are committed."
}

Write-Step "Final status"
& git status --short

Write-Host ""
if (-not $Execute) {
    Write-Host "DRY RUN ONLY. Nothing was changed." -ForegroundColor Yellow
    Write-Host "Run again with -Execute after reviewing the target list."
} else {
    Write-Host "Done. Local files were not deleted." -ForegroundColor Green
}