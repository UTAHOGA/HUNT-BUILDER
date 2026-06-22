param(
    [string]$FreshDir = "audits/2025_canonical_finalization/fresh_live_pulls_20260621_192945"
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path ".").Path
$outDir = Join-Path $root $FreshDir
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$supplementPath = Join-Path $outDir "utahdraws_draw_odds_supplement_data.json"
if (!(Test-Path $supplementPath)) {
    Invoke-WebRequest -Uri "https://www.utahdraws.com/internetsales/Home/DrawOddsSupplementData" -UseBasicParsing -TimeoutSec 30 -OutFile $supplementPath
}

$supplement = Get-Content -Raw -Path $supplementPath | ConvertFrom-Json
$rows = @($supplement.Data.DrawNameAvailableLicenseYears)
$manifest = @()

foreach ($row in $rows) {
    $drawName = [string]$row.DrawName
    $licenseYear = [string]$row.LicenseYear
    $masterHuntTypeID = [string]$row.MasterHuntTypeID
    $masterHuntTypeName = [string]$row.MasterHuntTypeName

    $safeDraw = ($drawName.ToLowerInvariant() -replace '[^a-z0-9]+','_' -replace '^_|_$','')
    $safeType = ($masterHuntTypeName.ToLowerInvariant() -replace '[^a-z0-9]+','_' -replace '^_|_$','')
    $fileName = "utahdraws_${safeDraw}_${licenseYear}_${safeType}_mht${masterHuntTypeID}.json"
    $outPath = Join-Path $outDir $fileName
    $uri = "https://www.utahdraws.com/internetsales/Home/DrawOddsData?drawName=$([uri]::EscapeDataString($drawName))&licenseYear=$licenseYear&masterHuntTypeID=$masterHuntTypeID"

    $status = "ok"
    $errorMessage = ""
    try {
        Invoke-WebRequest -Uri $uri -UseBasicParsing -TimeoutSec 60 -OutFile $outPath
    } catch {
        $status = "error"
        $errorMessage = $_.Exception.Message
    }

    $length = 0
    $recordCount = ""
    if (Test-Path $outPath) {
        $length = (Get-Item $outPath).Length
        try {
            $parsed = Get-Content -Raw -Path $outPath | ConvertFrom-Json
            if ($null -ne $parsed.Data) {
                $recordCount = @($parsed.Data).Count
            }
        } catch {
            $recordCount = ""
        }
    }

    $manifest += [pscustomobject]@{
        source = "utahdraws_draw_odds_matrix"
        draw_name = $drawName
        license_year = $licenseYear
        master_hunt_type_id = $masterHuntTypeID
        master_hunt_type_name = $masterHuntTypeName
        status = $status
        records = $recordCount
        bytes = $length
        file = $fileName
        url = $uri
        error = $errorMessage
    }
}

$manifestPath = Join-Path $outDir "utahdraws_draw_odds_full_matrix_manifest.csv"
$manifest | Export-Csv -NoTypeInformation -Path $manifestPath

$summary = [pscustomobject]@{
    out_dir = $outDir
    manifest = $manifestPath
    pulls = $manifest.Count
    ok = @($manifest | Where-Object { $_.status -eq "ok" }).Count
    errors = @($manifest | Where-Object { $_.status -ne "ok" }).Count
    records = (@($manifest | ForEach-Object { if ($_.records -ne "") { [int]$_.records } else { 0 } }) | Measure-Object -Sum).Sum
}

$summary | ConvertTo-Json -Depth 3
