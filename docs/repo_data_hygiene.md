# Repo Data Hygiene

HUNT-BUILDER uses GitHub for code, docs, small manifests, and small public contracts.
Large raw, generated, archive, database, and runtime data belongs in Cloudflare R2.

## GitHub vs R2 Rule

Commit to GitHub:
- source code
- tests
- docs
- small audit manifests
- `pipeline/R2_OFFLOAD/manifests/*.csv`
- intentional small public contract JSON files in `processed_data/public_contracts/`
- intentional small public contract JSON files in `pages-dist/processed_data/public_contracts/`

Do not commit to GitHub:
- `pipeline/RAW/**`
- `pipeline/INGEST/inbox/**`
- `pipeline/INGEST/archive/**`
- `pipeline/R2_OFFLOAD/incoming/**`
- `pipeline/R2_OFFLOAD/uploaded/**`
- large generated files under `data_model/harvest_quality/`
- large generated files under `data_model/runtime_drafts/`
- generated comparison outputs under `data_truth/comparison_outputs/`
- archives, PDFs, spreadsheets, SQLite/database files, Parquet files, or gzip files
- any staged file larger than 10 MB unless it is explicitly approved and small-public-contract safe

## Where To Put Files

Put files that need R2 upload here:

```powershell
pipeline\R2_OFFLOAD\incoming\
```

After upload, the files can stay local. They are ignored by Git.

Commit upload manifests from:

```powershell
pipeline\R2_OFFLOAD\manifests\
```

## Unstage Without Deleting

If GitHub Desktop stages a large file, unstage it without deleting the local file:

```powershell
git restore --staged -- "path\to\large-file.csv"
```

Then move the local file to the R2 inbox:

```powershell
New-Item -ItemType Directory -Force .\pipeline\R2_OFFLOAD\incoming | Out-Null
Move-Item -LiteralPath "path\to\large-file.csv" -Destination ".\pipeline\R2_OFFLOAD\incoming\large-file.csv"
```

## Upload To R2

Upload every file currently in the R2 inbox:

```powershell
.\tools\upload_r2_incoming.ps1
```

Defaults:
- bucket: `uoga-data`
- R2 key prefix: `processed_data`
- public base URL: `https://json.uoga.workers.dev`

Override the prefix when needed:

```powershell
.\tools\upload_r2_incoming.ps1 -Prefix "data/boundaries"
```

The upload script writes a manifest CSV and does not delete local files.

## Pre-Commit Guard

Before committing, run:

```powershell
python tools\git_size_guard.py
```

If blocked, follow the printed instructions. The guard checks staged files only and blocks:
- files larger than 10 MB
- archive/document/database extensions
- raw/generated R2-only paths

## Hard Commit Block

Install the local repo hook once per clone:

```powershell
.\tools\install_repo_hygiene_hooks.ps1
```

This sets:

```powershell
git config core.hooksPath .githooks
```

After that, Git and GitHub Desktop will run `tools/git_size_guard.py` before a commit.
The hook does not delete files and does not upload anything. It only blocks the commit when staged files belong in R2 or exceed the size limit.

Important: Git hooks block commits, not the GitHub Desktop staging checkbox itself. If GitHub Desktop stages a large file, unstage it safely and move it to the R2 inbox.

## Validation

Check that the hygiene rules and helper files exist:

```powershell
python tools\check_repo_hygiene.py
```
