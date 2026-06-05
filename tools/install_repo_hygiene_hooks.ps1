$ErrorActionPreference = "Stop"

$repoRoot = git rev-parse --show-toplevel
Set-Location $repoRoot

if (-not (Test-Path -LiteralPath ".githooks\pre-commit")) {
    throw "Missing .githooks\pre-commit. Cannot install repo hygiene hook."
}

git config core.hooksPath .githooks

Write-Host "Repo hygiene hooks installed for:"
Write-Host $repoRoot
Write-Host ""
Write-Host "Active hooks path:"
git config core.hooksPath
