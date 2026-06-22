param(
    [string]$FreshDir = "audits/2025_canonical_finalization/fresh_live_pulls_20260621_192945"
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path ".").Path
$outDir = Join-Path $root $FreshDir
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$setupPath = Join-Path $outDir "dwr_huntboundary_hasetup.json"
if (!(Test-Path $setupPath)) {
    Invoke-WebRequest -Uri "https://dwrapps.utah.gov/huntboundary/HaSetup" -UseBasicParsing -TimeoutSec 30 -OutFile $setupPath
}

$setup = Get-Content -Raw -Path $setupPath | ConvertFrom-Json
$manifest = @()

foreach ($entry in $setup.gbsList) {
    $species = [string]$entry.species
    foreach ($genderValue in $entry.genderList) {
        $gender = [string]$genderValue
        $safeSpecies = ($species.ToLowerInvariant() -replace '[^a-z0-9]+','_' -replace '^_|_$','')
        $safeGender = ($gender.ToLowerInvariant() -replace '[^a-z0-9]+','_' -replace '^_|_$','')
        $fileName = "dwr_huntboundary_${safeSpecies}_${safeGender}.json"
        $outPath = Join-Path $outDir $fileName
        $uri = "https://dwrapps.utah.gov/huntboundary/HuntTableData?species=$([uri]::EscapeDataString($species))&gender=$([uri]::EscapeDataString($gender))"

        $status = "ok"
        $errorMessage = ""
        try {
            Invoke-WebRequest -Uri $uri -UseBasicParsing -TimeoutSec 30 -OutFile $outPath
        } catch {
            $status = "error"
            $errorMessage = $_.Exception.Message
        }

        $length = 0
        if (Test-Path $outPath) {
            $length = (Get-Item $outPath).Length
        }

        $manifest += [pscustomobject]@{
            source = "dwr_huntboundary_matrix"
            species = $species
            gender = $gender
            status = $status
            bytes = $length
            file = $fileName
            url = $uri
            error = $errorMessage
        }
    }
}

$manifestPath = Join-Path $outDir "dwr_huntboundary_full_matrix_manifest.csv"
$manifest | Export-Csv -NoTypeInformation -Path $manifestPath

$summary = [pscustomobject]@{
    out_dir = $outDir
    manifest = $manifestPath
    pulls = $manifest.Count
    ok = @($manifest | Where-Object { $_.status -eq "ok" }).Count
    errors = @($manifest | Where-Object { $_.status -ne "ok" }).Count
}

$summary | ConvertTo-Json -Depth 3
