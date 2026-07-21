#!/usr/bin/env python3
"""Repair source alias manifest paths after raw PDF renames.

The repair is conservative:

- match renamed files by manifest SHA-256, not by guessed title
- make a timestamped backup before writing a manifest
- copy missing truth-store mirror files from the active pipeline source
- never overwrite an existing truth-store file with different bytes
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
ALIASES_DIR = REPO / "data_truth" / "draw_results_truth" / "source_file_aliases"
PIPELINE_ROOT = REPO / "pipeline" / "RAW" / "hunt_unit_database"
TRUTH_ROOT = REPO / "data_truth" / "draw_results_truth" / "raw_pdfs"
AUDIT_ROOT = REPO / "audits" / "source_alias_path_repair"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clean(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def parse_manifest_years(path: Path) -> tuple[int, int]:
    base = path.name.replace("_source_alias_manifest.csv", "")
    source_text, rest = base.split("_PERMITS=", 1)
    target_text = rest.split("_MODEL", 1)[0]
    return int(source_text), int(target_text)


def manifest_paths(years: set[int] | None) -> list[Path]:
    paths = sorted(ALIASES_DIR.glob("*_source_alias_manifest.csv"))
    if years is None:
        return paths
    filtered = []
    for path in paths:
        source_year, _target_year = parse_manifest_years(path)
        if source_year in years:
            filtered.append(path)
    return filtered


def build_pipeline_indexes(source_year: int) -> tuple[dict[str, list[Path]], dict[str, list[Path]]]:
    draw_dir = PIPELINE_ROOT / str(source_year) / "pdf" / "draw_odds"
    hash_index: dict[str, list[Path]] = defaultdict(list)
    title_index: dict[str, list[Path]] = defaultdict(list)
    if not draw_dir.exists():
        return hash_index, title_index
    for path in sorted(draw_dir.rglob("*.pdf")):
        if path.is_file():
            hash_index[sha256(path)].append(path)
            title_index[title_key(path.name)].append(path)
    return hash_index, title_index


def title_key(value: str) -> str:
    text = Path(value).name.upper()
    text = text.replace(".PDF", "")
    text = text.replace("PERMITS", "")
    text = text.replace("MODEL", "")
    text = text.replace("DRAWING", "DRAW")
    return "".join(ch for ch in text if ch.isalnum())


def relative_to_draw_odds(source_year: int, path: Path) -> str:
    draw_dir = PIPELINE_ROOT / str(source_year) / "pdf" / "draw_odds"
    return path.relative_to(draw_dir).as_posix()


def truth_path(source_year: int, target_year: int, relative_path: str) -> Path:
    return TRUTH_ROOT / f"{source_year}_PERMITS={target_year}_MODEL" / relative_path


def repair_manifest(path: Path, stamp: str, apply: bool, allow_title_match: bool) -> dict[str, object]:
    source_year, target_year = parse_manifest_years(path)
    fields, rows = read_csv(path)
    hash_index, title_index = build_pipeline_indexes(source_year)
    draw_dir = PIPELINE_ROOT / str(source_year) / "pdf" / "draw_odds"
    changed_rows = 0
    copied_truth_files = 0
    unresolved_rows = []
    conflict_rows = []
    row_reports = []

    for row in rows:
        old_rel = clean(row.get("standardized_raw_pdf_relative_path")) or clean(row.get("canonical_source_value"))
        row_hash = clean(row.get("sha256")).lower()
        pipeline_path = draw_dir / old_rel
        new_rel = old_rel
        repair_method = "unchanged"

        if row_hash and (not pipeline_path.exists() or sha256(pipeline_path).lower() != row_hash):
            candidates = hash_index.get(row_hash, [])
            if len(candidates) == 1:
                new_rel = relative_to_draw_odds(source_year, candidates[0])
                repair_method = "sha256_pipeline_match"
            elif len(candidates) > 1:
                conflict_rows.append(
                    {
                        "manifest": str(path),
                        "canonical_source_value": clean(row.get("canonical_source_value")),
                        "old_relative_path": old_rel,
                        "issue": "multiple_pipeline_hash_matches",
                        "candidate_count": len(candidates),
                    }
                )
            else:
                if allow_title_match:
                    title_candidates = title_index.get(title_key(old_rel), [])
                    if len(title_candidates) == 1:
                        new_rel = relative_to_draw_odds(source_year, title_candidates[0])
                        repair_method = "title_normalized_pipeline_match"
                    elif len(title_candidates) > 1:
                        conflict_rows.append(
                            {
                                "manifest": str(path),
                                "canonical_source_value": clean(row.get("canonical_source_value")),
                                "old_relative_path": old_rel,
                                "issue": "multiple_pipeline_title_matches",
                                "candidate_count": len(title_candidates),
                            }
                        )
                    else:
                        unresolved_rows.append(
                            {
                                "manifest": str(path),
                                "canonical_source_value": clean(row.get("canonical_source_value")),
                                "old_relative_path": old_rel,
                                "issue": "no_pipeline_hash_or_title_match",
                            }
                        )
                else:
                    unresolved_rows.append(
                        {
                            "manifest": str(path),
                            "canonical_source_value": clean(row.get("canonical_source_value")),
                            "old_relative_path": old_rel,
                            "issue": "no_pipeline_hash_match",
                        }
                    )

        if new_rel != old_rel:
            changed_rows += 1
            row["standardized_raw_pdf_relative_path"] = new_rel

        resolved_pipeline = draw_dir / new_rel
        resolved_truth = truth_path(source_year, target_year, new_rel)
        truth_action = "none"
        if resolved_pipeline.exists():
            if "size_bytes" in row:
                row["size_bytes"] = str(resolved_pipeline.stat().st_size)
            if row_hash and "sha256" in row:
                row["sha256"] = sha256(resolved_pipeline)
            if not resolved_truth.exists():
                truth_action = "copy_truth_mirror"
                copied_truth_files += 1
                if apply:
                    resolved_truth.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(resolved_pipeline, resolved_truth)
            elif row_hash and sha256(resolved_truth).lower() != sha256(resolved_pipeline).lower():
                truth_action = "truth_hash_conflict"
                conflict_rows.append(
                    {
                        "manifest": str(path),
                        "canonical_source_value": clean(row.get("canonical_source_value")),
                        "old_relative_path": old_rel,
                        "new_relative_path": new_rel,
                        "issue": "truth_hash_conflict",
                    }
                )

        row_reports.append(
            {
                "manifest": str(path),
                "source_year": source_year,
                "target_year": target_year,
                "canonical_source_value": clean(row.get("canonical_source_value")),
                "old_relative_path": old_rel,
                "new_relative_path": new_rel,
                "repair_method": repair_method,
                "truth_action": truth_action,
            }
        )

    backup_path = ""
    if apply and changed_rows:
        backup = path.with_name(f"{path.stem}.backup_{stamp}{path.suffix}")
        shutil.copy2(path, backup)
        backup_path = str(backup)
        write_csv(path, fields, rows)

    return {
        "manifest": str(path),
        "source_year": source_year,
        "target_year": target_year,
        "rows": len(rows),
        "changed_rows": changed_rows,
        "copied_truth_files": copied_truth_files,
        "unresolved_rows": unresolved_rows,
        "conflict_rows": conflict_rows,
        "backup_path": backup_path,
        "row_reports": row_reports,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write repaired manifests and copy missing truth mirrors.")
    parser.add_argument(
        "--allow-title-match",
        action="store_true",
        help="If SHA-256 cannot match, allow a unique normalized-title match and update the manifest hash to pipeline bytes.",
    )
    parser.add_argument("--year", action="append", type=int, help="Limit to a source year. Can be repeated.")
    args = parser.parse_args()

    years = set(args.year) if args.year else None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
    report_dir = AUDIT_ROOT / stamp
    report_dir.mkdir(parents=True, exist_ok=True)

    reports = [
        repair_manifest(path, stamp, apply=args.apply, allow_title_match=args.allow_title_match)
        for path in manifest_paths(years)
    ]
    summary = [
        {
            key: value
            for key, value in report.items()
            if key not in {"row_reports", "unresolved_rows", "conflict_rows"}
        }
        for report in reports
    ]
    detail_rows = [row for report in reports for row in report["row_reports"]]
    unresolved_rows = [row for report in reports for row in report["unresolved_rows"]]
    conflict_rows = [row for report in reports for row in report["conflict_rows"]]

    (report_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    for filename, rows, fields in (
        (
            "details.csv",
            detail_rows,
            [
                "manifest",
                "source_year",
                "target_year",
                "canonical_source_value",
                "old_relative_path",
                "new_relative_path",
                "repair_method",
                "truth_action",
            ],
        ),
        (
            "unresolved.csv",
            unresolved_rows,
            ["manifest", "canonical_source_value", "old_relative_path", "issue"],
        ),
        (
            "conflicts.csv",
            conflict_rows,
            ["manifest", "canonical_source_value", "old_relative_path", "new_relative_path", "issue", "candidate_count"],
        ),
    ):
        with (report_dir / filename).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

    print(
        json.dumps(
            {
                "ok": True,
                "apply": args.apply,
                "report_dir": str(report_dir),
                "manifests": len(reports),
                "changed_rows": sum(int(report["changed_rows"]) for report in reports),
                "copied_truth_files": sum(int(report["copied_truth_files"]) for report in reports),
                "unresolved_rows": len(unresolved_rows),
                "conflict_rows": len(conflict_rows),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
