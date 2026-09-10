#!/usr/bin/env python3
"""Freeze one isolated source-only yearly truth candidate without promotion."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
KEY_FIELDS = (
    "actual_draw_year",
    "model_target_year",
    "source_scope",
    "hunt_code",
    "points",
    "record_type",
)


def clean(value: object) -> str:
    return str(value or "").strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def repo_path(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draw-year", type=int, required=True)
    parser.add_argument("--model-target-year", type=int, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--fresh-manifest", type=Path, required=True)
    parser.add_argument(
        "--folder-comparison-summary",
        type=Path,
        help="Optional independent user-folder comparison when the user supplied a local year folder.",
    )
    parser.add_argument("--canonical-comparison-summary", type=Path, required=True)
    parser.add_argument(
        "--difference-resolution",
        default="",
        help="Source-backed explanation for intentional differences from the retained canonical.",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    inputs = {
        "candidate": args.candidate.resolve(),
        "fresh_manifest": args.fresh_manifest.resolve(),
        "canonical_comparison_summary": args.canonical_comparison_summary.resolve(),
    }
    if args.folder_comparison_summary is not None:
        inputs["folder_comparison_summary"] = args.folder_comparison_summary.resolve()
    output_dir = args.output_dir.resolve()
    for name, path in inputs.items():
        if not path.is_relative_to(ROOT):
            raise ValueError(f"{name} must remain inside this repository: {path}")
        if not path.is_file():
            raise FileNotFoundError(path)

    rows = read_csv(inputs["candidate"])
    if not rows:
        raise ValueError("Candidate contains no rows")
    if {clean(row.get("actual_draw_year")) for row in rows} != {str(args.draw_year)}:
        raise ValueError("Candidate actual_draw_year does not match the requested draw year")
    if {clean(row.get("model_target_year")) for row in rows} != {str(args.model_target_year)}:
        raise ValueError("Candidate model_target_year does not match the requested target year")
    key_counts = Counter(tuple(clean(row.get(field)) for field in KEY_FIELDS) for row in rows)
    duplicate_keys = sum(count - 1 for count in key_counts.values() if count > 1)
    if duplicate_keys:
        raise ValueError(f"Candidate has {duplicate_keys} duplicate official table identities")

    source_rows = read_csv(inputs["fresh_manifest"])
    source_failures = [row for row in source_rows if clean(row.get("download_status")) != "OK"]
    if source_failures:
        raise ValueError(f"Fresh source manifest has {len(source_failures)} failed downloads")
    folder_summary = (
        read_json(inputs["folder_comparison_summary"])
        if "folder_comparison_summary" in inputs
        else {"status": "NOT_APPLICABLE_NO_USER_FOLDER_SUPPLIED"}
    )
    if (
        "folder_comparison_summary" in inputs
        and clean(folder_summary.get("status")) != "PASS_COMPLETE_FOLDER_EQUIVALENCE"
    ):
        raise ValueError("Independent local-folder equivalence did not pass")
    canonical_comparison = read_json(inputs["canonical_comparison_summary"])

    output_dir.mkdir(parents=True, exist_ok=True)
    frozen_candidate = output_dir / f"draw_results_{args.draw_year}_for_{args.model_target_year}_source_truth_candidate_frozen.csv"
    if frozen_candidate.exists() and sha256(frozen_candidate) != sha256(inputs["candidate"]):
        raise RuntimeError(f"Refusing to replace a different frozen candidate: {frozen_candidate}")
    if not frozen_candidate.exists():
        shutil.copy2(inputs["candidate"], frozen_candidate)
    if sha256(frozen_candidate) != sha256(inputs["candidate"]):
        raise RuntimeError("Frozen candidate bytes do not match source candidate")

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "FROZEN_ISOLATED_SOURCE_TRUTH_READY_FOR_NEXT_YEAR_NOT_PROMOTED",
        "draw_year": args.draw_year,
        "model_target_year": args.model_target_year,
        "candidate_rows": len(rows),
        "candidate_unique_hunt_codes": len({clean(row.get("hunt_code")) for row in rows if clean(row.get("hunt_code"))}),
        "candidate_duplicate_keys": duplicate_keys,
        "official_pdf_count": len(source_rows),
        "source_families": dict(sorted(Counter(clean(row.get("source_family")) for row in source_rows).items())),
        "independent_folder_equivalence_status": folder_summary["status"],
        "canonical_comparison_status": canonical_comparison.get("status"),
        "canonical_difference_resolution": clean(args.difference_resolution),
        "canonical_comparison_counts": {
            key: canonical_comparison.get(key)
            for key in (
                "baseline_rows",
                "candidate_rows",
                "matched_keys",
                "baseline_only_rows",
                "candidate_only_rows",
                "matched_rows_with_official_value_differences",
            )
        },
        "inputs": {
            name: {"path": repo_path(path), "sha256": sha256(path)}
            for name, path in inputs.items()
        },
        "frozen_candidate": {
            "path": repo_path(frozen_candidate),
            "sha256": sha256(frozen_candidate),
            "bytes": frozen_candidate.stat().st_size,
        },
        "promotion_writes": [],
        "canonical_truth_changed": False,
        "unified_truth_changed": False,
        "prediction_runtime_changed": False,
        "hosted_action": "NONE",
    }
    manifest_path = output_dir / "SOURCE_TRUTH_FREEZE_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
