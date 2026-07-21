#!/usr/bin/env python3
"""Reconcile the 2017 source alias manifest with the live PDF inventory.

This script keeps the legacy canonical_source_value columns intact, but rewrites
the standardized path column so it points at the actual files in the 2017
pipeline folder. It also mirrors any missing source PDFs into the pipeline and
truth raw_pdf trees so the yearly alias audit can resolve every row.
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / "data_truth" / "draw_results_truth" / "source_file_aliases" / "2017_PERMITS=2018_MODEL_source_alias_manifest.csv"
PIPELINE_ROOT = REPO / "pipeline" / "RAW" / "hunt_unit_database" / "2017" / "pdf" / "draw_odds"
TRUTH_ROOT = REPO / "data_truth" / "draw_results_truth" / "raw_pdfs" / "2017_PERMITS=2018_MODEL"
AUDIT_ROOT = REPO / "audits" / "2017_source_alias_reconciliation"


def clean(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def index_files(root: Path) -> dict[str, list[Path]]:
    by_hash: dict[str, list[Path]] = defaultdict(list)
    for path in root.rglob("*.pdf"):
        if path.is_file():
            by_hash[sha256(path)].append(path)
    return by_hash


def relative_to(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def pick_existing(paths: list[Path], preferred_root: Path) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def mirror_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if sha256(target) == sha256(source):
            return
    shutil.copy2(source, target)


def main() -> int:
    if not MANIFEST.exists():
        raise FileNotFoundError(MANIFEST)

    AUDIT_ROOT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = AUDIT_ROOT / f"{MANIFEST.stem}.backup_before_reconcile_{stamp}.csv"
    shutil.copy2(MANIFEST, backup)

    rows = read_csv(MANIFEST)
    pipeline_index = index_files(PIPELINE_ROOT)
    truth_index = index_files(TRUTH_ROOT)

    chosen_rows: list[dict[str, object]] = []
    mirror_actions: list[dict[str, str]] = []
    unresolved: list[dict[str, str]] = []

    for row in rows:
        canonical = clean(row.get("canonical_source_value"))
        manifest_rel = clean(row.get("standardized_raw_pdf_relative_path")) or canonical
        expected_pipeline = PIPELINE_ROOT / manifest_rel
        expected_truth = TRUTH_ROOT / manifest_rel
        row_hash = clean(row.get("sha256"))

        resolved_pipeline: Path | None = expected_pipeline if expected_pipeline.exists() else None
        resolved_truth: Path | None = expected_truth if expected_truth.exists() else None

        if row_hash:
            if resolved_pipeline is None:
                resolved_pipeline = pick_existing(pipeline_index.get(row_hash, []), PIPELINE_ROOT)
            if resolved_truth is None:
                resolved_truth = pick_existing(truth_index.get(row_hash, []), TRUTH_ROOT)

        if resolved_pipeline is None and resolved_truth is not None:
            resolved_pipeline = PIPELINE_ROOT / relative_to(TRUTH_ROOT, resolved_truth)
        if resolved_pipeline is not None:
            resolved_truth = TRUTH_ROOT / relative_to(PIPELINE_ROOT, resolved_pipeline)

        if resolved_pipeline is None or resolved_truth is None:
            unresolved.append(
                {
                    "canonical_source_value": canonical,
                    "manifest_relative_path": manifest_rel,
                    "reason": "could_not_resolve_to_pipeline_and_truth",
                }
            )
            chosen_rows.append(row)
            continue

        pipeline_exists = resolved_pipeline.exists()
        truth_exists = resolved_truth.exists()
        if pipeline_exists and not truth_exists:
            mirror_file(resolved_pipeline, resolved_truth)
        elif truth_exists and not pipeline_exists:
            mirror_file(resolved_truth, resolved_pipeline)
        elif pipeline_exists and truth_exists:
            if sha256(resolved_pipeline) != sha256(resolved_truth):
                mirror_file(resolved_pipeline, resolved_truth)

        resolved_rel = relative_to(PIPELINE_ROOT, resolved_pipeline)
        row["standardized_raw_pdf_relative_path"] = resolved_rel
        row["sha256"] = sha256(resolved_pipeline)
        row["size_bytes"] = str(resolved_pipeline.stat().st_size)
        chosen_rows.append(row)
        mirror_actions.append(
            {
                "canonical_source_value": canonical,
                "resolved_pipeline_relative_path": resolved_rel,
                "pipeline_path": str(resolved_pipeline),
                "truth_path": str(resolved_truth),
            }
        )

    write_csv(
        MANIFEST,
        chosen_rows,
        [
            "source_year",
            "target_year",
            "canonical_source_value",
            "canonical_source_leaf",
            "canonical_source_slug",
            "source_columns",
            "canonical_row_count",
            "standardized_raw_pdf_relative_path",
            "source_family",
            "source_role",
            "active_for_scoring",
            "resolution_method",
            "sha256",
            "size_bytes",
        ],
    )

    summary = {
        "manifest": str(MANIFEST),
        "backup": str(backup),
        "rows": len(rows),
        "resolved_rows": len(chosen_rows) - len(unresolved),
        "unresolved_rows": unresolved,
        "mirror_actions": mirror_actions,
    }
    (AUDIT_ROOT / f"reconcile_2017_source_alias_manifest_{stamp}.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
