$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$OutDir = Join-Path $Root "audits/2025_canonical_finalization/fresh_live_pulls_$Stamp"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$Requests = @(
  @{
    Name = "dwr_huntboundary_pronghorn_buck.json"
    Uri = "https://dwrapps.utah.gov/huntboundary/HuntTableData?species=Pronghorn&gender=Buck"
  },
  @{
    Name = "dwr_huntboundary_deer_buck.json"
    Uri = "https://dwrapps.utah.gov/huntboundary/HuntTableData?species=Deer&gender=Buck"
  },
  @{
    Name = "dwr_huntboundary_rocky_mountain_bighorn_sheep_male_only.json"
    Uri = "https://dwrapps.utah.gov/huntboundary/HuntTableData?species=Rocky+Mountain+Bighorn+Sheep&gender=Male+Only"
  },
  @{
    Name = "dwr_huntboundary_home.html"
    Uri = "https://dwrapps.utah.gov/huntboundary/"
  },
  @{
    Name = "huntbuilder_dwr_iframe.html"
    Uri = "https://huntbuilder.uoga.org/#dwr"
  },
  @{
    Name = "utahdraws_drawodds.html"
    Uri = "https://www.utahdraws.com/internetsales/home/drawodds"
  }
)

$ManifestRows = @()
foreach ($Request in $Requests) {
  $Target = Join-Path $OutDir $Request.Name
  $Started = Get-Date
  try {
    Invoke-WebRequest -Uri $Request.Uri -UseBasicParsing -TimeoutSec 30 -OutFile $Target
    $Status = "OK"
    $ErrorMessage = ""
  } catch {
    $Status = "ERROR"
    $ErrorMessage = $_.Exception.Message
    Set-Content -Path $Target -Value $ErrorMessage -Encoding UTF8
  }

  $Item = Get-Item $Target
  $ManifestRows += [PSCustomObject]@{
    name = $Request.Name
    uri = $Request.Uri
    status = $Status
    bytes = $Item.Length
    pulled_at = $Started.ToString("o")
    error = $ErrorMessage
  }
}

$ManifestPath = Join-Path $OutDir "fresh_live_pull_manifest.csv"
$ManifestRows | Export-Csv -NoTypeInformation -Path $ManifestPath

Write-Output "out_dir=$OutDir"
Write-Output "manifest=$ManifestPath"
