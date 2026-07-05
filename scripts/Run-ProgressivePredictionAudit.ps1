<#
Run progressive year-to-year prediction artifacts and write a compact report.

Example from repo root:
  powershell -ExecutionPolicy Bypass -File ".\scripts\Run-ProgressivePredictionAudit.ps1" `
    -Repo "D:\DESKTOP\GitHub\HUNT-BUILDER" `
    -StartPermitYear 2019 `
    -EndPermitYear 2026 `
    -OpenReport

StartPermitYear and EndPermitYear are target/permit years. A 2019 start runs
2018->2019, because the prediction source year is the prior permit year.
#>
[CmdletBinding()]
param(
    [string]$Repo = (Resolve-Path ".").Path,
    [int]$StartPermitYear = 2019,
    [int]$EndPermitYear = 2026,
    [switch]$OpenReport,
    [switch]$SkipRuntimeGate
)

$ErrorActionPreference = "Stop"

function Resolve-Python {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return $python.Source
    }
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        return $py.Source
    }
    throw "Could not find python or py on PATH."
}

function Invoke-Checked {
    param(
        [string]$Exe,
        [string[]]$ArgumentList,
        [string]$WorkingDirectory
    )
    Write-Host ">> $Exe $($ArgumentList -join ' ')" -ForegroundColor Cyan
    Push-Location $WorkingDirectory
    try {
        & $Exe @ArgumentList
    } finally {
        Pop-Location
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE`: $Exe $($ArgumentList -join ' ')"
    }
}

$Repo = (Resolve-Path $Repo).Path
Set-Location $Repo

$Runner = Join-Path $Repo "scripts\run_full_engine_all_year_validation.py"
if (-not (Test-Path $Runner)) {
    throw "Missing runner: $Runner"
}

if ($StartPermitYear -lt 2011) {
    throw "StartPermitYear looks wrong: $StartPermitYear"
}
if ($EndPermitYear -lt $StartPermitYear) {
    throw "EndPermitYear must be >= StartPermitYear."
}

$SourceStart = $StartPermitYear - 1
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$AuditDir = Join-Path $Repo ("audits\progressive_prediction_audit\" + $Stamp)
New-Item -ItemType Directory -Force -Path $AuditDir | Out-Null

$Python = Resolve-Python
$env:PYTHONPATH = $Repo

Write-Host ""
Write-Host "Progressive prediction audit" -ForegroundColor Green
Write-Host "Repo: $Repo"
Write-Host "Target years: $StartPermitYear-$EndPermitYear"
Write-Host "Source start year: $SourceStart"
Write-Host "Audit dir: $AuditDir"
Write-Host ""

$pythonArgs = @(
    $Runner,
    "--source-start", [string]$SourceStart,
    "--target-end", [string]$EndPermitYear,
    "--audit-dir", $AuditDir
)
Invoke-Checked -Exe $Python -ArgumentList $pythonArgs -WorkingDirectory $Repo

$GateDir = ""
if (-not $SkipRuntimeGate) {
    $Gate = Join-Path $Repo "tools\runtime_production_gate.py"
    if (Test-Path $Gate) {
        $gateArgs = @(
            $Gate,
            "--mode", "fast",
            "--write-audits",
            "--no-promote",
            "--target-years", [string]$EndPermitYear,
            "--skip-pytest"
        )
        Invoke-Checked -Exe $Python -ArgumentList $gateArgs -WorkingDirectory $Repo
    } else {
        Write-Warning "Runtime gate not found, skipped: $Gate"
    }
}

$CountsPath = Join-Path $AuditDir "all_year_family_prediction_counts.csv"
$LeakagePath = Join-Path $AuditDir "leakage_check.csv"
$ReportPath = Join-Path $AuditDir "PROGRESSIVE_PREDICTION_AUDIT_REPORT.md"

$Counts = @()
if (Test-Path $CountsPath) {
    $Counts = Import-Csv $CountsPath
}
$Leakage = @()
if (Test-Path $LeakagePath) {
    $Leakage = Import-Csv $LeakagePath
}

$StatusGroups = $Counts | Group-Object status | Sort-Object Name
$LeakageGroups = $Leakage | Group-Object leakage_status | Sort-Object Name
$PredictionRows = 0
foreach ($row in $Counts) {
    $value = 0
    [void][int]::TryParse([string]$row.prediction_rows, [ref]$value)
    $PredictionRows += $value
}
$Classified = @($Counts | Where-Object { $_.status -eq "CLASSIFIED" })
$Failed = @($Counts | Where-Object { $_.status -eq "FAIL" })

$Lines = New-Object System.Collections.Generic.List[string]
$Lines.Add("# Progressive Prediction Audit")
$Lines.Add("")
$Lines.Add("Created: $(Get-Date -Format s)")
$Lines.Add("")
$Lines.Add("Repo: ``$Repo``")
$Lines.Add("Audit dir: ``$AuditDir``")
$Lines.Add("Target years: ``$StartPermitYear-$EndPermitYear``")
$Lines.Add("Source start year: ``$SourceStart``")
$Lines.Add("")
$Lines.Add("## Result")
$Lines.Add("")
$Lines.Add("- Family/year rows: ``$($Counts.Count)``")
$Lines.Add("- Prediction rows: ``$PredictionRows``")
$Lines.Add("- Failed rows: ``$($Failed.Count)``")
$Lines.Add("- Classified rows: ``$($Classified.Count)``")
$Lines.Add("")
$Lines.Add("## Status Counts")
$Lines.Add("")
if ($StatusGroups.Count -eq 0) {
    $Lines.Add("- No status rows found.")
} else {
    foreach ($group in $StatusGroups) {
        $Lines.Add("- $($group.Name): ``$($group.Count)``")
    }
}
$Lines.Add("")
$Lines.Add("## Leakage Counts")
$Lines.Add("")
if ($LeakageGroups.Count -eq 0) {
    $Lines.Add("- No leakage rows found.")
} else {
    foreach ($group in $LeakageGroups) {
        $Lines.Add("- $($group.Name): ``$($group.Count)``")
    }
}
$Lines.Add("")
$Lines.Add("## Classified / Failed Rows")
$Lines.Add("")
if (($Classified.Count + $Failed.Count) -eq 0) {
    $Lines.Add("- None.")
} else {
    foreach ($row in @($Classified + $Failed)) {
        $Lines.Add("- $($row.source_year)->$($row.target_year) $($row.family): $($row.status) / $($row.blocker_if_failed)")
    }
}
$Lines.Add("")
$Lines.Add("## Files")
$Lines.Add("")
$Lines.Add("- ``$CountsPath``")
$Lines.Add("- ``$LeakagePath``")
$Lines.Add("- ``$ReportPath``")

$Lines | Set-Content -Path $ReportPath -Encoding UTF8

Write-Host ""
Write-Host "Audit complete." -ForegroundColor Green
Write-Host "Report: $ReportPath"
Write-Host "Counts: $CountsPath"
Write-Host "Leakage: $LeakagePath"

if ($OpenReport) {
    Invoke-Item $ReportPath
}
