#!/usr/bin/env python3
"""Read-only repo hygiene check for large tracked files and staged risks."""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "audits" / "repo_hygiene"
OUT_CSV = OUT_DIR / "tracked_large_files.csv"
THRESHOLD = 10 * 1024 * 1024


def git(args: list[str]) -> str:
    return subprocess.run(["git", *args], cwd=REPO, check=True, text=True, stdout=subprocess.PIPE).stdout


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for raw in git(["ls-files"]).splitlines():
        path = raw.strip()
        if not path:
            continue
        full = REPO / path
        if not full.exists() or not full.is_file():
            continue
        size = full.stat().st_size
        if size >= THRESHOLD:
            rows.append({"path": path, "size_bytes": size, "size_mb": round(size / (1024 * 1024), 2)})

    with OUT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "size_bytes", "size_mb"])
        writer.writeheader()
        writer.writerows(rows)

    staged_check = subprocess.run([sys.executable, str(REPO / "tools" / "git_size_guard.py"), "--warn-only"], cwd=REPO)
    print(f"Tracked files >= 10 MB: {len(rows)}")
    print(f"Wrote {OUT_CSV}")
    return staged_check.returncode


if __name__ == "__main__":
    raise SystemExit(main())
