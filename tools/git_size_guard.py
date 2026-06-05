from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass
from pathlib import Path


DEFAULT_MAX_MB = 10
DEFAULT_MAX_BYTES = DEFAULT_MAX_MB * 1024 * 1024

BLOCKED_EXTENSIONS = {
    ".7z",
    ".db",
    ".db3",
    ".gz",
    ".kmz",
    ".mbtiles",
    ".parquet",
    ".pdf",
    ".rar",
    ".sqlite",
    ".sqlite3",
    ".tar",
    ".xls",
    ".xlsx",
    ".zip",
}

R2_ONLY_PREFIXES = (
    "pipeline/RAW/",
    "pipeline/INGEST/inbox/",
    "pipeline/INGEST/archive/",
    "pipeline/R2_OFFLOAD/incoming/",
    "pipeline/R2_OFFLOAD/uploaded/",
    "data_model/harvest_quality/",
    "data_model/runtime_drafts/",
    "data_truth/comparison_outputs/",
)

PUBLIC_CONTRACT_PREFIXES = (
    "processed_data/public_contracts/",
    "pages-dist/processed_data/public_contracts/",
)

MANIFEST_PREFIX = "pipeline/R2_OFFLOAD/manifests/"


@dataclass(frozen=True)
class BlockedFile:
    path: Path
    reason: str
    size_bytes: int


def _git_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(result.stdout.strip())


def _staged_files() -> list[Path]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [Path(line.strip()) for line in result.stdout.splitlines() if line.strip()]


def _is_safe_public_contract(path: str) -> bool:
    return path.endswith(".json") and any(path.startswith(prefix) for prefix in PUBLIC_CONTRACT_PREFIXES)


def _is_manifest(path: str) -> bool:
    return path.startswith(MANIFEST_PREFIX) and path.endswith(".csv")


def _block_reason(path: Path, size_bytes: int, max_bytes: int) -> str | None:
    normalized = path.as_posix()

    if _is_safe_public_contract(normalized) or _is_manifest(normalized):
        return None

    if size_bytes > max_bytes:
        return f"larger than {max_bytes / 1024 / 1024:.0f} MB"

    if path.suffix.lower() in BLOCKED_EXTENSIONS:
        return f"blocked data/binary extension {path.suffix.lower()}"

    if any(normalized.startswith(prefix) for prefix in R2_ONLY_PREFIXES):
        return "R2-only source/generated path"

    return None


def _quote_ps(value: str) -> str:
    return '"' + value.replace('"', '`"') + '"'


def _print_instructions(blocked: list[BlockedFile]) -> None:
    print()
    print("BLOCKED: staged files include GitHub-hostile data artifacts.")
    print("Route these files to Cloudflare R2 and commit only code, docs, manifests, or small public contracts.")
    print()

    for item in blocked:
        size_mb = item.size_bytes / 1024 / 1024
        path = item.path.as_posix()
        destination = f".\\pipeline\\R2_OFFLOAD\\incoming\\{item.path.name}"
        print(f"- {path} | {size_mb:.2f} MB | {item.reason}")
        print(f"  unstage: git restore --staged -- { _quote_ps(path) }")
        print("  make inbox: New-Item -ItemType Directory -Force .\\pipeline\\R2_OFFLOAD\\incoming | Out-Null")
        print(f"  move local copy: Move-Item -LiteralPath { _quote_ps(path) } -Destination { _quote_ps(destination) }")
        print("  upload: .\\tools\\upload_r2_incoming.ps1")
        print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Block staged large/raw/generated files before GitHub commit.")
    parser.add_argument("--max-mb", type=int, default=DEFAULT_MAX_MB)
    args = parser.parse_args()

    root = _git_root()
    max_bytes = args.max_mb * 1024 * 1024
    blocked: list[BlockedFile] = []

    for rel_path in _staged_files():
        full_path = root / rel_path
        if not full_path.is_file():
            continue

        size_bytes = full_path.stat().st_size
        reason = _block_reason(rel_path, size_bytes, max_bytes)
        if reason:
            blocked.append(BlockedFile(rel_path, reason, size_bytes))

    if blocked:
        _print_instructions(blocked)
        return 1

    print(f"OK: staged files pass repo hygiene guard at {args.max_mb} MB.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
