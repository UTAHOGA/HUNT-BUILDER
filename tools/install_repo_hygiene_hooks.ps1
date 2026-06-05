$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

git config core.hooksPath .githooks

Write-Host "Installed repo hygiene hooks:"
Write-Host "  core.hooksPath=.githooks"
Write-Host ""
Write-Host "GitHub Desktop may still show staged checkboxes, but commits and pushes now run:"
Write-Host "  python tools/git_size_guard.py"
