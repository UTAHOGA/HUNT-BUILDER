param(
    [string]$FreshDir = "audits/2025_canonical_finalization/fresh_live_pulls_20260621_192945"
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path ".").Path
$outDir = Join-Path $root $FreshDir
$archiveDir = Join-Path $outDir "older_years_bear_cougar_turkey_odds"
New-Item -ItemType Directory -Force -Path $archiveDir | Out-Null

$pagePath = Join-Path $outDir "utah_wildlife_odds_bear_cougar_turkey_older_years.html"
if (!(Test-Path $pagePath)) {
    Invoke-WebRequest -Uri "https://wildlife.utah.gov/odds" -UseBasicParsing -TimeoutSec 30 -OutFile $pagePath
}

$html = Get-Content -Raw -Path $pagePath
$matches = [regex]::Matches($html, '<a\s+[^>]*href=["'']([^"'']+\.pdf)["''][^>]*>([\s\S]*?)</a>', 'IgnoreCase')
$rows = @()
$seen = @{}

foreach ($match in $matches) {
    $href = [System.Net.WebUtility]::HtmlDecode($match.Groups[1].Value)
    $text = [regex]::Replace($match.Groups[2].Value, '<[^>]+>', '')
    $text = [System.Net.WebUtility]::HtmlDecode(([regex]::Replace($text, '\s+', ' ')).Trim())

    $species = ""
    if ($href -match '/pdf/bear/') {
        $species = "bear"
    } elseif ($href -match '/pdf/cougar/') {
        $species = "cougar"
    } elseif ($href -match '/pdf/uplandgame/turkey/' -or ($href -match 'turkey' -and $text -match 'turkey|Drawing|Bonus|Youth|Harvest')) {
        $species = "turkey"
    } else {
        continue
    }

    $year = ""
    $yearMatch = [regex]::Match($href, '(?:/|_)(20\d{2}|\d{2})(?=[^/]*\.pdf)')
    if ($yearMatch.Success) {
        $rawYear = $yearMatch.Groups[1].Value
        if ($rawYear.Length -eq 2) {
            $year = "20$rawYear"
        } else {
            $year = $rawYear
        }
    }

    if ($href.StartsWith("http")) {
        $url = $href
    } else {
        $url = "https://wildlife.utah.gov$href"
    }

    $uriPath = ([uri]$url).AbsolutePath
    $baseName = [System.IO.Path]::GetFileName($uriPath)
    if ([string]::IsNullOrWhiteSpace($baseName)) {
        $baseName = "download.pdf"
    }

    $yearDir = Join-Path (Join-Path $archiveDir $species) $year
    New-Item -ItemType Directory -Force -Path $yearDir | Out-Null
    $fileName = $baseName
    $dedupeKey = "$species/$year/$fileName"
    if ($seen.ContainsKey($dedupeKey)) {
        $seen[$dedupeKey] += 1
        $stem = [System.IO.Path]::GetFileNameWithoutExtension($baseName)
        $fileName = "${stem}__dup$($seen[$dedupeKey]).pdf"
    } else {
        $seen[$dedupeKey] = 1
    }

    $outPath = Join-Path $yearDir $fileName
    $status = "ok"
    $errorMessage = ""
    try {
        Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 60 -OutFile $outPath
    } catch {
        $status = "error"
        $errorMessage = $_.Exception.Message
    }

    $length = 0
    if (Test-Path $outPath) {
        $length = (Get-Item $outPath).Length
    }

    $rows += [pscustomobject]@{
        source = "utah_wildlife_bear_cougar_turkey_odds_archive"
        species = $species
        year = $year
        title = $text
        status = $status
        bytes = $length
        file = "older_years_bear_cougar_turkey_odds/$species/$year/$fileName"
        url = $url
        error = $errorMessage
    }
}

$manifestPath = Join-Path $outDir "utah_wildlife_bear_cougar_turkey_odds_archive_manifest.csv"
$rows | Export-Csv -NoTypeInformation -Path $manifestPath

$summaryPath = Join-Path $outDir "utah_wildlife_bear_cougar_turkey_odds_archive_summary.json"
$bySpecies = $rows | Group-Object species | Sort-Object Name | ForEach-Object {
    [pscustomobject]@{
        species = $_.Name
        count = $_.Count
        ok = @($_.Group | Where-Object { $_.status -eq "ok" }).Count
        errors = @($_.Group | Where-Object { $_.status -ne "ok" }).Count
        years = @($_.Group | Select-Object -ExpandProperty year -Unique | Sort-Object)
    }
}
$summary = [pscustomobject]@{
    source_page = "https://wildlife.utah.gov/odds#bearReports"
    out_dir = $archiveDir
    manifest = $manifestPath
    total_links = $rows.Count
    ok = @($rows | Where-Object { $_.status -eq "ok" }).Count
    errors = @($rows | Where-Object { $_.status -ne "ok" }).Count
    by_species = $bySpecies
}
$summary | ConvertTo-Json -Depth 6 | Set-Content -Path $summaryPath -Encoding UTF8

$summary | ConvertTo-Json -Depth 6
