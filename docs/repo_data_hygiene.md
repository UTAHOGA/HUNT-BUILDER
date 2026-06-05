# Repo Data Hygiene

## Hard Rule

GitHub is for code, small contracts, docs, tests, and small manifests.
Cloudflare R2 is for raw files, large generated data, large runtime feeds, PDFs,
workbooks, archives, SQLite databases, and GeoJSON/KML/KMZ boundary payloads.

GitHub Desktop can still show checkboxes because Git has no pre-stage hook.
The repo guard blocks the dangerous part: commits and pushes fail when unsafe
files are staged.

## Safe Git Files

- Source code under `app.js`, `config.js`, `scripts/`, `tools/`, `engine/`,
  `tests/`, and `docs/`
- Small public/runtime manifests such as `public/data/runtime-manifest.json`
  and `data/runtime-manifest.json`
- Small JSON public contracts under `processed_data/public_contracts/*.json`
- R2 upload manifests under `pipeline/R2_OFFLOAD/manifests/`

## R2 Files

Place files for upload under:

```text
pipeline/R2_OFFLOAD/incoming/
```

Upload them with:

```powershell
powershell -ExecutionPolicy Bypass -File tools/upload_r2_incoming.ps1
```

The script writes a committed manifest under:

```text
pipeline/R2_OFFLOAD/manifests/
```

It does not delete local files.

## Unstage Without Deleting

If GitHub Desktop accidentally stages a large/raw file, run:

```powershell
git restore --staged -- "path/to/file"
```

That removes it from the commit only. It does not delete the local file.

To clear every unsafe staged large/raw/data file at once:

```powershell
powershell -ExecutionPolicy Bypass -File tools/unstage_unsafe_files.ps1
```

That script only unstages unsafe additions/modifications. It does not delete
local files and it does not undo intentional Git removals caused by `git rm
--cached`.

## Install The Guard

Run once per clone:

```powershell
powershell -ExecutionPolicy Bypass -File tools/install_repo_hygiene_hooks.ps1
```

After this, every commit and push runs:

```powershell
python tools/git_size_guard.py
```
