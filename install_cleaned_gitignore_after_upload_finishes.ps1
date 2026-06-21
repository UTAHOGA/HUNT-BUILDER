param(
  [string]$RepoPath = "C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER",
  [string]$CleanedGitignorePath = "$env:USERPROFILE\Downloads\gitignore_cleaned_from_current_upload.txt"
)

$ErrorActionPreference = "Stop"

if (!(Test-Path $RepoPath)) {
  throw "Repo path not found: $RepoPath"
}
if (!(Test-Path $CleanedGitignorePath)) {
  throw "Cleaned .gitignore file not found: $CleanedGitignorePath"
}

Set-Location $RepoPath
Copy-Item -LiteralPath $CleanedGitignorePath -Destination ".gitignore" -Force
git add .gitignore

if (Test-Path "processed_data/cloudflare_large_file_manifest.csv") {
  git add processed_data/cloudflare_large_file_manifest.csv
}
if (Test-Path "processed_data/cloudflare_large_file_manifest.json") {
  git add processed_data/cloudflare_large_file_manifest.json
}

git status --short
git diff --cached --name-status
