param(
    [Parameter(Mandatory = $true)]
    [string]$OutDir,
    [switch]$Apply
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$rawRoot = (Resolve-Path -LiteralPath (Join-Path $repoRoot 'pipeline\RAW\hunt_unit_database')).Path
$truthRoot = (Resolve-Path -LiteralPath (Join-Path $repoRoot 'data_truth\draw_results_truth\normalized\canonical_yearly')).Path
$outPath = [IO.Path]::GetFullPath((Join-Path $repoRoot $OutDir))
$allowedAuditRoot = [IO.Path]::GetFullPath((Join-Path $repoRoot 'audit_output_real_final'))
if (-not $outPath.StartsWith($allowedAuditRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'OutDir must be a new child of audit_output_real_final.'
}
if (Test-Path -LiteralPath $outPath) { throw "OutDir already exists: $outPath" }

function Get-NormalizedPath([string]$Path) {
    return [IO.Path]::GetFullPath($Path).TrimEnd('\').ToLowerInvariant()
}

$canonicalRefs = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
$canonicalSourceReader = @'
import csv
import pathlib
import re
import sys

truth_root = pathlib.Path(sys.argv[1])
for canonical in sorted(truth_root.glob("draw_results_*_for_*.csv")):
    match = re.match(r"draw_results_(20\d{2})_for_", canonical.name)
    if not match:
        continue
    year = match.group(1)
    sources = set()
    with canonical.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            source = (row.get("source_file") or "").strip()
            if source:
                sources.add(source)
    for source in sorted(sources):
        print(f"{year}\t{source}")
'@
$canonicalSourceLines = @($canonicalSourceReader | python - $truthRoot)
if ($LASTEXITCODE -ne 0) { throw 'Python failed while reading exact canonical source_file values.' }
foreach ($line in $canonicalSourceLines) {
    $parts = $line -split "`t", 2
    if ($parts.Count -ne 2) { continue }
    $year = $parts[0]
    $source = $parts[1]
    if (-not $source.EndsWith('.pdf', [StringComparison]::OrdinalIgnoreCase)) { continue }
    $drawDir = Join-Path $rawRoot "$year\pdf\draw_odds"
    if (-not (Test-Path -LiteralPath $drawDir)) { continue }
    try {
        if ([IO.Path]::IsPathRooted($source)) {
            $candidate = [IO.Path]::GetFullPath($source)
        } else {
            $candidate = [IO.Path]::GetFullPath((Join-Path $drawDir $source))
        }
    } catch {
        continue
    }
    if ($candidate.StartsWith($drawDir + '\', [StringComparison]::OrdinalIgnoreCase) -and
        (Test-Path -LiteralPath $candidate -PathType Leaf)) {
        [void]$canonicalRefs.Add((Get-NormalizedPath $candidate))
    }
}

$pdfs = Get-ChildItem -LiteralPath $rawRoot -Directory |
    Where-Object { $_.Name -match '^20(1[7-9]|2[0-6])$' } |
    ForEach-Object {
        $drawDir = Join-Path $_.FullName 'pdf\draw_odds'
        if (Test-Path -LiteralPath $drawDir) {
            Get-ChildItem -LiteralPath $drawDir -Filter '*.pdf' -File -Recurse
        }
    } |
    ForEach-Object {
        [pscustomobject]@{
            FullPath = $_.FullName
            RelativePath = $_.FullName.Substring($repoRoot.Length + 1)
            Year = [int](($_.FullName.Substring($rawRoot.Length + 1) -split '\\')[0])
            Bytes = $_.Length
            Hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
            CanonicalReference = $canonicalRefs.Contains((Get-NormalizedPath $_.FullName))
            OfficialArchive = $_.FullName -like '*\official_dwr_archive\*'
        }
    }

$plan = [Collections.Generic.List[object]]::new()
$blocked = [Collections.Generic.List[object]]::new()
$groups = @($pdfs | Group-Object Hash | Where-Object Count -gt 1)
foreach ($group in $groups) {
    $items = @($group.Group | Sort-Object RelativePath)
    $canonicalKeepers = @($items | Where-Object CanonicalReference)
    if ($canonicalKeepers.Count -eq 1) {
        $keeper = $canonicalKeepers[0]
        $reason = 'CANONICAL_REFERENCED_EXACT_COPY'
    } elseif ($canonicalKeepers.Count -eq 0) {
        $archiveKeepers = @($items | Where-Object OfficialArchive)
        if ($archiveKeepers.Count -eq 1) {
            $keeper = $archiveKeepers[0]
            $reason = 'SOLE_OFFICIAL_ARCHIVE_EXACT_COPY'
        } else {
            $blocked.Add([pscustomobject]@{hash=$group.Name; reason='KEEPER_AMBIGUOUS'; paths=($items.RelativePath -join ' | ')})
            continue
        }
    } else {
        $blocked.Add([pscustomobject]@{hash=$group.Name; reason='MULTIPLE_CANONICAL_REFERENCES'; paths=($canonicalKeepers.RelativePath -join ' | ')})
        continue
    }
    foreach ($target in $items) {
        if ($target.FullPath -eq $keeper.FullPath) { continue }
        $plan.Add([pscustomobject]@{
            hash = $group.Name
            bytes = $target.Bytes
            year = $target.Year
            keeper = $keeper.RelativePath
            target = $target.RelativePath
            keeper_reason = $reason
            target_was_canonical_reference = $target.CanonicalReference
            target_was_official_archive = $target.OfficialArchive
        })
    }
}

New-Item -ItemType Directory -Path $outPath | Out-Null
$plan | Export-Csv -LiteralPath (Join-Path $outPath 'deletion_plan.csv') -NoTypeInformation -Encoding UTF8
$blocked | Export-Csv -LiteralPath (Join-Path $outPath 'blocked_groups.csv') -NoTypeInformation -Encoding UTF8

$receipt = [Collections.Generic.List[object]]::new()
if ($Apply) {
    if ($blocked.Count -gt 0) { throw "Cleanup blocked by $($blocked.Count) ambiguous groups." }
    [void][Reflection.Assembly]::LoadWithPartialName('Microsoft.VisualBasic')
    foreach ($row in $plan) {
        $target = [IO.Path]::GetFullPath((Join-Path $repoRoot $row.target))
        $keeper = [IO.Path]::GetFullPath((Join-Path $repoRoot $row.keeper))
        if (-not $target.StartsWith($rawRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw "Target escaped RAW: $target" }
        if (-not $keeper.StartsWith($rawRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw "Keeper escaped RAW: $keeper" }
        if (-not (Test-Path -LiteralPath $target -PathType Leaf)) { throw "Target missing before deletion: $target" }
        if (-not (Test-Path -LiteralPath $keeper -PathType Leaf)) { throw "Keeper missing before deletion: $keeper" }
        $targetHash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
        $keeperHash = (Get-FileHash -LiteralPath $keeper -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($targetHash -ne $row.hash -or $keeperHash -ne $row.hash) { throw "Fresh hash mismatch: $($row.target)" }
        [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile(
            $target,
            [Microsoft.VisualBasic.FileIO.UIOption]::OnlyErrorDialogs,
            [Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin
        )
        $receipt.Add([pscustomobject]@{target=$row.target; hash=$row.hash; bytes=$row.bytes; keeper=$row.keeper; disposition='RECYCLE_BIN'})
    }
}
$receipt | Export-Csv -LiteralPath (Join-Path $outPath 'deletion_receipt.csv') -NoTypeInformation -Encoding UTF8

$remaining = Get-ChildItem -LiteralPath $rawRoot -Directory |
    Where-Object { $_.Name -match '^20(1[7-9]|2[0-6])$' } |
    ForEach-Object {
        $drawDir = Join-Path $_.FullName 'pdf\draw_odds'
        if (Test-Path -LiteralPath $drawDir) { Get-ChildItem -LiteralPath $drawDir -Filter '*.pdf' -File -Recurse }
    } |
    ForEach-Object {
        [pscustomobject]@{Path=$_.FullName; Hash=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}
    }
$remainingDuplicateGroups = @($remaining | Group-Object Hash | Where-Object Count -gt 1)
$annual = @($remaining | ForEach-Object {
    [pscustomobject]@{year=[int](($_.Path.Substring($rawRoot.Length + 1) -split '\\')[0]); hash=$_.Hash}
} | Group-Object year | Sort-Object Name | ForEach-Object {
    [pscustomobject]@{year=[int]$_.Name; pdf_paths=$_.Count; unique_hashes=@($_.Group.hash | Sort-Object -Unique).Count}
})
$summary = [ordered]@{
    status = if ($blocked.Count -gt 0) {'BLOCKED'} elseif ($Apply -and $remainingDuplicateGroups.Count -eq 0) {'APPLIED_ZERO_EXACT_DUPLICATES'} elseif ($Apply) {'APPLIED_REVIEW_REMAINING_DUPLICATES'} else {'DRY_RUN_READY'}
    apply = [bool]$Apply
    original_pdf_paths = $pdfs.Count
    original_unique_hashes = @($pdfs.Hash | Sort-Object -Unique).Count
    duplicate_hash_groups = $groups.Count
    planned_deletions = $plan.Count
    planned_bytes = ($plan | Measure-Object bytes -Sum).Sum
    deleted_to_recycle_bin = $receipt.Count
    blocked_groups = $blocked.Count
    remaining_pdf_paths = $remaining.Count
    remaining_unique_hashes = @($remaining.Hash | Sort-Object -Unique).Count
    remaining_duplicate_hash_groups = $remainingDuplicateGroups.Count
    annual_after = $annual
    canonicals_modified = $false
    deletion_is_recoverable = $true
}
$summary | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $outPath 'summary.json') -Encoding UTF8
$summary | ConvertTo-Json -Depth 6
if ($blocked.Count -gt 0 -or ($Apply -and $remainingDuplicateGroups.Count -gt 0)) { exit 1 }
