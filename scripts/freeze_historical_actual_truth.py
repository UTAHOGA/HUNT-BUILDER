#!/usr/bin/env python3
"""Freeze one yearly canonical draw-results file for a blind backtest.

The snapshot is a byte-for-byte audit copy.  It records the canonical source
hash before the prediction phase starts and never changes the source canonical.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_stats(path: Path, target_year: int) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    years = {str(row.get("actual_draw_year", "")).strip() for row in rows}
    if years != {str(target_year)}:
        raise ValueError(
            f"Expected only actual_draw_year={target_year} in {path}; found {sorted(years)}"
        )
    return {
        "row_count": len(rows),
        "unique_hunt_codes": len({str(row.get("hunt_code", "")).strip() for row in rows if str(row.get("hunt_code", "")).strip()}),
        "source_scopes": len({str(row.get("source_file", "")).strip() for row in rows if str(row.get("source_file", "")).strip()}),
        "record_type_counts": {
            key: sum(1 for row in rows if str(row.get("record_type", "")).strip() == key)
            for key in sorted({str(row.get("record_type", "")).strip() for row in rows})
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-year", type=int, required=True)
    parser.add_argument("--target-year", type=int, required=True)
    parser.add_argument("--canonical", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    canonical = args.canonical.resolve()
    out_dir = args.out_dir.resolve()
    if not canonical.is_file():
        raise FileNotFoundError(f"Canonical file is missing: {canonical}")

    stats = canonical_stats(canonical, args.target_year)
    target = out_dir / "inputs" / f"official_{args.target_year}_canonical_actual_frozen.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and sha256(target) != sha256(canonical):
        raise RuntimeError(f"Refusing to overwrite a different frozen truth snapshot: {target}")
    if not target.exists():
        shutil.copy2(canonical, target)

    source_hash = sha256(canonical)
    frozen_hash = sha256(target)
    if source_hash != frozen_hash:
        raise RuntimeError("Frozen truth copy hash does not match the canonical source.")

    manifest = {
        "purpose": "blind_year_to_year_actual_truth_freeze",
        "source_year": args.source_year,
        "target_year": args.target_year,
        "source_canonical": str(canonical.relative_to(REPO)).replace("\\", "/"),
        "source_canonical_sha256": source_hash,
        "frozen_actual": str(target.relative_to(REPO)).replace("\\", "/"),
        "frozen_actual_sha256": frozen_hash,
        "source_bytes": canonical.stat().st_size,
        "frozen_bytes": target.stat().st_size,
        "freeze_status": "HASH_VERIFIED_BYTE_FOR_BYTE_COPY",
        **stats,
    }
    manifest_path = out_dir / "frozen_actual_truth_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
