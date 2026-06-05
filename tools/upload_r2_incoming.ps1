param(
  [string]$Bucket = "uoga-data",
  [string]$Prefix = "",
  [string]$IncomingDir = "pipeline/R2_OFFLOAD/incoming",
  [string]$ManifestDir = "pipeline/R2_OFFLOAD/manifests"
)

$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

if (!(Test-Path $IncomingDir)) {
  New-Item -ItemType Directory -Force -Path $IncomingDir | Out-Null
}
if (!(Test-Path $ManifestDir)) {
  New-Item -ItemType Directory -Force -Path $ManifestDir | Out-Null
}

$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$manifest = Join-Path $ManifestDir "r2_upload_$stamp.csv"
$rows = @()

$files = Get-ChildItem -LiteralPath $IncomingDir -File -Recurse
foreach ($file in $files) {
  $relative = Resolve-Path -LiteralPath $file.FullName -Relative
  $relative = $relative -replace '^\.\\', ''
  $objectKey = ($relative -replace '^pipeline\\R2_OFFLOAD\\incoming\\?', '') -replace '\\', '/'
  if ($Prefix) {
    $objectKey = ($Prefix.Trim('/') + '/' + $objectKey).Trim('/')
  }

  $target = "$Bucket/$objectKey"
  Write-Host "Uploading $relative -> r2://$target"
  $output = & npx.cmd wrangler r2 object put $target --file $file.FullName --remote 2>&1
  $status = if ($LASTEXITCODE -eq 0) { "UPLOADED" } else { "FAILED" }
  $sha = (Get-FileHash -Algorithm SHA256 -LiteralPath $file.FullName).Hash.ToLowerInvariant()
  $rows += [pscustomobject]@{
    timestamp_utc = (Get-Date).ToUniversalTime().ToString("o")
    status = $status
    local_path = $relative
    bucket = $Bucket
    object_key = $objectKey
    size_bytes = $file.Length
    sha256 = $sha
    wrangler_output = ($output -join " ").Trim()
  }
  if ($LASTEXITCODE -ne 0) {
    throw "R2 upload failed for $relative"
  }
}

$rows | Export-Csv -NoTypeInformation -Path $manifest
Write-Host "Wrote manifest: $manifest"
Write-Host "Local files were not deleted."
