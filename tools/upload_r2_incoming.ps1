param(
    [string]$Bucket = "uoga-data",
    [string]$Prefix = "processed_data",
    [string]$Incoming = ".\pipeline\R2_OFFLOAD\incoming",
    [string]$ManifestDir = ".\pipeline\R2_OFFLOAD\manifests",
    [string]$PublicBaseUrl = "https://json.uoga.workers.dev"
)

$ErrorActionPreference = "Stop"

$incomingPath = (Resolve-Path -LiteralPath $Incoming -ErrorAction SilentlyContinue)
if (-not $incomingPath) {
    New-Item -ItemType Directory -Force -Path $Incoming | Out-Null
    $incomingPath = Resolve-Path -LiteralPath $Incoming
}

New-Item -ItemType Directory -Force -Path $ManifestDir | Out-Null

$files = @(Get-ChildItem -LiteralPath $incomingPath.Path -Recurse -File)

if (-not $files) {
    Write-Host "No files found in $($incomingPath.Path). Nothing uploaded."
    exit 0
}

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$manifest = Join-Path $ManifestDir "r2_upload_manifest_$stamp.csv"
$manifestRows = New-Object System.Collections.Generic.List[object]

foreach ($file in $files) {
    $relativeName = $file.FullName.Substring($incomingPath.Path.Length).TrimStart("\", "/")
    $relativeName = $relativeName -replace "\\", "/"
    $cleanPrefix = $Prefix.Trim("/")
    $r2Key = if ($cleanPrefix) { "$cleanPrefix/$relativeName" } else { $relativeName }
    $publicUrl = "$($PublicBaseUrl.TrimEnd('/'))/$r2Key"
    $sha256 = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()

    Write-Host "Uploading $($file.FullName) -> r2://$Bucket/$r2Key"
    npx wrangler r2 object put "$Bucket/$r2Key" --file "$($file.FullName)"

    $manifestRows.Add([pscustomobject]@{
        uploaded_at_utc = (Get-Date).ToUniversalTime().ToString("o")
        local_path      = $file.FullName
        bucket          = $Bucket
        r2_key          = $r2Key
        public_url      = $publicUrl
        size_bytes      = $file.Length
        sha256          = $sha256
        last_write_time = $file.LastWriteTime.ToString("o")
    })
}

$manifestRows | Export-Csv -LiteralPath $manifest -NoTypeInformation -Encoding UTF8

Write-Host ""
Write-Host "Manifest written:"
Write-Host $manifest
Write-Host ""
Write-Host "Local files were not deleted."
