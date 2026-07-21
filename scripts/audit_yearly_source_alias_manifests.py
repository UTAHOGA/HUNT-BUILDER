#!/usr/bin/env python3
"""Audit yearly source alias manifests against live PDF folders.

This is a read-only audit. It verifies that the standardized child PDFs written
into the active draw-odds folders are also represented in the yearly source
alias manifests and mirrored under the truth-store raw PDF tree.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
ALIASES_DIR = REPO / "data_truth" / "draw_results_truth" / "source_file_aliases"
PIPELINE_ROOT = REPO / "pipeline" / "RAW" / "hunt_unit_database"
TRUTH_ROOT = REPO / "data_truth" / "draw_results_truth" / "raw_pdfs"
AUDIT_ROOT = REPO / "audits" / "yearly_source_alias_audit"


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


def manifest_paths() -> list[Path]:
    return sorted(ALIASES_DIR.glob("*_source_alias_manifest.csv"))


def expected_pipeline_path(source_year: int, relative_path: str) -> Path:
    return PIPELINE_ROOT / str(source_year) / "pdf" / "draw_odds" / relative_path


def expected_truth_path(source_year: int, target_year: int, relative_path: str) -> Path:
    return TRUTH_ROOT / f"{source_year}_PERMITS={target_year}_MODEL" / relative_path


def audit_manifest(path: Path) -> dict[str, object]:
    rows = read_csv(path)
    base = path.name.replace("_source_alias_manifest.csv", "")
    source_year = 0
    target_year = 0
    if "_PERMITS=" in base:
        source_text, rest = base.split("_PERMITS=", 1)
        target_text = rest.split("_MODEL", 1)[0]
        if source_text.isdigit():
            source_year = int(source_text)
        if target_text.isdigit():
            target_year = int(target_text)

    active_rows = [row for row in rows if clean(row.get("active_for_scoring")).lower() == "true"]
    inactive_rows = [row for row in rows if clean(row.get("active_for_scoring")).lower() != "true"]
    unresolved = []
    active_unresolved = []
    missing_pipeline = []
    missing_truth = []
    hash_mismatch = []
    active_hash_mismatch = []
    inactive_outside_primary = []
    inactive_phantom_registry = []
    duplicate_canonical = Counter()
    family_counts = Counter()

    for row in rows:
        canonical = clean(row.get("canonical_source_value"))
        rel = clean(row.get("standardized_raw_pdf_relative_path")) or canonical
        family = clean(row.get("source_family"))
        duplicate_canonical[canonical] += 1
        if family:
            family_counts[family] += 1
        pipeline_path = expected_pipeline_path(source_year, rel)
        truth_path = expected_truth_path(source_year, target_year, rel)
        row_hash = clean(row.get("sha256"))
        is_active = clean(row.get("active_for_scoring")).lower() == "true"
        source_role = clean(row.get("source_role"))
        inactive_lineage_only = (
            not is_active
            and truth_path.exists()
            and not pipeline_path.exists()
            and (
                "PARENT" in source_role.upper()
                or "REFERENCE" in source_role.upper()
                or "DIAGNOSTIC" in source_role.upper()
                or "INACTIVE" in source_role.upper()
                or "RAW_PDF_REGISTRY" in source_role.upper()
            )
        )
        if inactive_lineage_only:
            inactive_outside_primary.append(
                {
                    "canonical_source_value": canonical,
                    "standardized_raw_pdf_relative_path": rel,
                    "pipeline_exists": False,
                    "truth_exists": True,
                    "active_for_scoring": False,
                    "source_family": family,
                    "source_role": source_role,
                }
            )
            continue
        inactive_phantom = (
            not is_active
            and not pipeline_path.exists()
            and not truth_path.exists()
            and "RAW_PDF_REGISTRY" in source_role.upper()
        )
        if inactive_phantom:
            inactive_phantom_registry.append(
                {
                    "canonical_source_value": canonical,
                    "standardized_raw_pdf_relative_path": rel,
                    "pipeline_exists": False,
                    "truth_exists": False,
                    "active_for_scoring": False,
                    "source_family": family,
                    "source_role": source_role,
                }
            )
            continue
        if not pipeline_path.exists() or not truth_path.exists():
            unresolved_row = {
                "canonical_source_value": canonical,
                "standardized_raw_pdf_relative_path": rel,
                "pipeline_exists": pipeline_path.exists(),
                "truth_exists": truth_path.exists(),
                "active_for_scoring": is_active,
                "source_family": family,
                "source_role": source_role,
            }
            unresolved.append(unresolved_row)
            if unresolved_row["active_for_scoring"]:
                active_unresolved.append(unresolved_row)
            if not pipeline_path.exists():
                missing_pipeline.append(rel)
            if not truth_path.exists():
                missing_truth.append(rel)
            continue
        if row_hash:
            pipeline_hash = sha256(pipeline_path)
            truth_hash = sha256(truth_path)
            if row_hash != pipeline_hash or row_hash != truth_hash:
                mismatch_row = {
                    "canonical_source_value": canonical,
                    "standardized_raw_pdf_relative_path": rel,
                "manifest_sha256": row_hash,
                "pipeline_sha256": pipeline_hash,
                "truth_sha256": truth_hash,
                "active_for_scoring": is_active,
                "source_family": family,
                "source_role": source_role,
            }
                hash_mismatch.append(mismatch_row)
                if mismatch_row["active_for_scoring"]:
                    active_hash_mismatch.append(mismatch_row)

    return {
        "manifest": str(path),
        "source_year": source_year,
        "target_year": target_year,
        "rows": len(rows),
        "active_rows": len(active_rows),
        "inactive_rows": len(inactive_rows),
        "duplicate_canonical_values": sum(1 for count in duplicate_canonical.values() if count > 1),
        "family_counts": dict(sorted(family_counts.items())),
        "unresolved_count": len(unresolved),
        "active_unresolved_count": len(active_unresolved),
        "missing_pipeline_count": len(missing_pipeline),
        "missing_truth_count": len(missing_truth),
        "hash_mismatch_count": len(hash_mismatch),
        "active_hash_mismatch_count": len(active_hash_mismatch),
        "inactive_outside_primary_count": len(inactive_outside_primary),
        "inactive_phantom_registry_count": len(inactive_phantom_registry),
        "unresolved_rows": unresolved,
        "active_unresolved_rows": active_unresolved,
        "inactive_outside_primary_rows": inactive_outside_primary,
        "inactive_phantom_registry_rows": inactive_phantom_registry,
        "hash_mismatch_rows": hash_mismatch,
        "active_hash_mismatch_rows": active_hash_mismatch,
    }


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", action="append", type=Path, help="Specific manifest path to audit. Can be repeated.")
    args = parser.parse_args()

    AUDIT_ROOT.mkdir(parents=True, exist_ok=True)
    manifests = args.manifest or manifest_paths()
    summaries = [audit_manifest(path) for path in manifests]

    stamp = AUDIT_ROOT / "latest"
    stamp.mkdir(parents=True, exist_ok=True)
    summary_path = stamp / "yearly_source_alias_manifest_audit_summary.json"
    summary_path.write_text(json.dumps(summaries, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    detail_rows = []
    for summary in summaries:
        for row in summary["unresolved_rows"]:
            detail_rows.append(
                {
                    "manifest": summary["manifest"],
                    "source_year": summary["source_year"],
                    "target_year": summary["target_year"],
                    "canonical_source_value": row["canonical_source_value"],
                    "standardized_raw_pdf_relative_path": row["standardized_raw_pdf_relative_path"],
                    "pipeline_exists": row["pipeline_exists"],
                    "truth_exists": row["truth_exists"],
                    "active_for_scoring": row["active_for_scoring"],
                    "source_family": row["source_family"],
                    "source_role": row["source_role"],
                    "issue": "unresolved",
                }
            )
        for row in summary["inactive_outside_primary_rows"]:
            detail_rows.append(
                {
                    "manifest": summary["manifest"],
                    "source_year": summary["source_year"],
                    "target_year": summary["target_year"],
                    "canonical_source_value": row["canonical_source_value"],
                    "standardized_raw_pdf_relative_path": row["standardized_raw_pdf_relative_path"],
                    "pipeline_exists": row["pipeline_exists"],
                    "truth_exists": row["truth_exists"],
                    "active_for_scoring": row["active_for_scoring"],
                    "source_family": row["source_family"],
                    "source_role": row["source_role"],
                    "issue": "inactive_outside_primary",
                }
            )
        for row in summary["inactive_phantom_registry_rows"]:
            detail_rows.append(
                {
                    "manifest": summary["manifest"],
                    "source_year": summary["source_year"],
                    "target_year": summary["target_year"],
                    "canonical_source_value": row["canonical_source_value"],
                    "standardized_raw_pdf_relative_path": row["standardized_raw_pdf_relative_path"],
                    "pipeline_exists": row["pipeline_exists"],
                    "truth_exists": row["truth_exists"],
                    "active_for_scoring": row["active_for_scoring"],
                    "source_family": row["source_family"],
                    "source_role": row["source_role"],
                    "issue": "inactive_phantom_registry",
                }
            )
        for row in summary["hash_mismatch_rows"]:
            detail_rows.append(
                {
                    "manifest": summary["manifest"],
                    "source_year": summary["source_year"],
                    "target_year": summary["target_year"],
                    "canonical_source_value": row["canonical_source_value"],
                    "standardized_raw_pdf_relative_path": row["standardized_raw_pdf_relative_path"],
                    "pipeline_exists": "true",
                    "truth_exists": "true",
                    "active_for_scoring": row["active_for_scoring"],
                    "source_family": row["source_family"],
                    "source_role": row["source_role"],
                    "issue": "sha256_mismatch",
                }
            )

    write_csv(
        stamp / "yearly_source_alias_manifest_audit_details.csv",
        detail_rows,
        [
            "manifest",
            "source_year",
            "target_year",
            "canonical_source_value",
            "standardized_raw_pdf_relative_path",
            "pipeline_exists",
            "truth_exists",
            "active_for_scoring",
            "source_family",
            "source_role",
            "issue",
        ],
    )

    print(json.dumps({"ok": True, "manifests": len(manifests), "audit_dir": str(stamp), "summaries": summaries}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
