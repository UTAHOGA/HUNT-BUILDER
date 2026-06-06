#!/usr/bin/env python3
"""Block unsafe staged files before GitHub Desktop can commit/push them.

Git cannot prevent a file from being selected in the GitHub Desktop UI, but this
guard makes unsafe staging non-deployable: commits and pushes fail with exact
unstage/R2 routing instructions.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
MAX_BYTES = 10 * 1024 * 1024

BLOCKED_EXTENSIONS = {
    ".zip",
    ".7z",
    ".rar",
    ".tar",
    ".gz",
    ".pdf",
    ".xlsx",
    ".xls",
    ".parquet",
    ".sqlite",
    ".db",
    ".gpkg",
    ".mbtiles",
    ".tif",
    ".tiff",
    ".shp",
    ".shx",
    ".dbf",
    ".prj",
    ".kml",
    ".kmz",
}

BLOCKED_PREFIXES = (
    "pipeline/RAW/",
    "pipeline/INGEST/inbox/",
    "pipeline/INGEST/archive/",
    "pipeline/R2_OFFLOAD/incoming/",
    "pipeline/R2_OFFLOAD/uploaded/",
    "processed_data/backups/",
    "data_model/runtime_drafts/",
    "data_model/harvest_quality/",
    "data_truth/comparison_outputs/",
)

ALLOWED_EXACT = {
    "public/data/runtime-manifest.json",
    "data/runtime-manifest.json",
    "data_model/runtime_drafts/POINT_LADDER_FILE_ROLES.md",
}

ALLOWED_PREFIX_SUFFIX = (
    ("processed_data/public_contracts/", ".json"),
    ("pages-dist/processed_data/public_contracts/", ".json"),
    ("pipeline/R2_OFFLOAD/manifests/", ".csv"),
    ("pipeline/R2_OFFLOAD/manifests/", ".json"),
    ("pipeline/R2_OFFLOAD/manifests/", ".md"),
)


def run_git(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout


def staged_paths() -> list[tuple[str, str]]:
    output = run_git(["diff", "--cached", "--name-status", "-z"])
    if not output:
        return []
    parts = output.split("\0")
    rows: list[tuple[str, str]] = []
    index = 0
    while index < len(parts) - 1:
        status = parts[index]
        index += 1
        if not status:
            continue
        code = status[0]
        if code in {"R", "C"}:
            old_path = parts[index]
            new_path = parts[index + 1]
            index += 2
            rows.append((code, new_path.replace("\\", "/")))
            rows.append((code, old_path.replace("\\", "/")))
        else:
            path = parts[index]
            index += 1
            rows.append((code, path.replace("\\", "/")))
    return rows


def is_allowed(path: str) -> bool:
    if path in ALLOWED_EXACT:
        return True
    return any(path.startswith(prefix) and path.endswith(suffix) for prefix, suffix in ALLOWED_PREFIX_SUFFIX)


def blob_size(path: str) -> int:
    try:
        value = run_git(["cat-file", "-s", f":{path}"]).strip()
    except subprocess.CalledProcessError:
        local = REPO / path
        return local.stat().st_size if local.exists() else 0
    return int(value or "0")


def classify(status: str, path: str) -> list[str]:
    if status == "D" or is_allowed(path):
        return []

    reasons: list[str] = []
    lower = path.lower()
    suffix = Path(path).suffix.lower()

    if any(lower.startswith(prefix.lower()) for prefix in BLOCKED_PREFIXES):
        reasons.append("protected data/raw/runtime path")
    if suffix in BLOCKED_EXTENSIONS:
        reasons.append(f"blocked file extension {suffix}")

    size = blob_size(path)
    if size > MAX_BYTES:
        reasons.append(f"file is {size / (1024 * 1024):.1f} MB, over 10 MB")

    return reasons


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-mb", type=float, default=10.0)
    parser.add_argument("--warn-only", action="store_true")
    args = parser.parse_args()

    global MAX_BYTES
    MAX_BYTES = int(args.max_mb * 1024 * 1024)

    blocked: list[tuple[str, str, list[str]]] = []
    for status, path in staged_paths():
        reasons = classify(status, path)
        if reasons:
            blocked.append((status, path, reasons))

    if not blocked:
        print("Git size guard: PASS. No unsafe staged files.")
        return 0

    print("\nGit size guard: BLOCKED unsafe staged files.\n")
    for status, path, reasons in blocked:
        print(f"- {status}\t{path}")
        for reason in reasons:
            print(f"  reason: {reason}")
        print(f"  unstage only: git restore --staged -- \"{path}\"")
        print(f"  route to R2: move \"{path}\" \"pipeline/R2_OFFLOAD/incoming/\"")
    print("\nCommit/push stopped. Keep code/docs/manifests in GitHub; route big/raw/runtime data to Cloudflare R2.")
    return 0 if args.warn_only else 1


if __name__ == "__main__":
    sys.exit(main())
