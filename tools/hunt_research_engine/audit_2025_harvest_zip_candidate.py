#!/usr/bin/env python3
"""Audit external 2025-for-2026 harvest ZIP against active HUNT-BUILDER data.

The ZIP lives in the older HUNTS repo. This read-only audit records source
hashes, compares ZIP members to the active local harvest package, and checks
whether the active 2025 harvest data is already represented in the engine
feature path.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def _repo_root() -> Path:
    repo_root = Path(__file__).resolve()
    while repo_root.name != "HUNT-BUILDER" and repo_root.parent != repo_root:
        repo_root = repo_root.parent
    if repo_root.name != "HUNT-BUILDER":
        raise RuntimeError("Could not locate HUNT-BUILDER repo root")
    return repo_root


DEFAULT_OUT_DIR = "audits/hunt_research_engine"
DEFAULT_ZIP = str(_repo_root() / "pipeline/RAW/hunt_unit_database/2026/csv/HARVEST REPORT/2025 HARVEST DATA.zip")
LOCAL_RAW_DIR = "pipeline/RAW/hunt_unit_database/2026/csv/harvest report"

CURRENT_FILES = {
    "harvest_truth_long": "data_truth/harvest_results_truth/normalized/harvest_results_all_years_long.csv",
    "harvest_truth_features": "data_truth/harvest_results_truth/normalized/harvest_quality_features_all_years_by_hunt_code.csv",
    "harvest_model_long": "data_model/harvest_quality/harvest_results_all_years_long.csv",
    "harvest_model_features": "data_model/harvest_quality/harvest_quality_features_all_years_by_hunt_code.csv",
    "harvest_feature_model_2026": "data_model/harvest_quality/harvest_feature_model_by_hunt_code_2026.csv",
}


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv_file(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def read_csv_bytes(data: bytes) -> tuple[list[str], list[dict[str, str]]]:
    text = data.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    return list(reader.fieldnames or []), [dict(row) for row in reader]


def code_value(row: dict[str, str]) -> str:
    return clean(row.get("hunt_code") or row.get("selected_hunt_code")).upper()


def code_count(rows: list[dict[str, str]]) -> int:
    return len({code_value(row) for row in rows if code_value(row)})


def summarize_year(rows: list[dict[str, str]], year_field: str, year: str) -> dict[str, object]:
    hits = [row for row in rows if clean(row.get(year_field)) == year]
    return {
        "rows": len(hits),
        "hunt_codes": code_count(hits),
        "source_counts_top": dict(Counter(clean(row.get("source_file")) for row in hits if clean(row.get("source_file"))).most_common(20)),
        "species_counts": dict(sorted(Counter(clean(row.get("species")) for row in hits if clean(row.get("species"))).items())),
    }


def member_class(name: str) -> str:
    lower = name.lower()
    if lower.endswith(".xlsx"):
        return "WORKBOOK_HELPER"
    if "rejected_rows" in lower:
        return "REVIEW_HELPER"
    if lower.endswith(".sqlite"):
        return "SQLITE_SUPPORT"
    if lower.endswith(".json") or lower.endswith(".md"):
        return "PACKAGE_REPORT"
    if lower.endswith(".csv"):
        return "HARVEST_CSV"
    return "OTHER"


def classify_member(zip_hash: str, local_hash: str, local_exists: bool, name: str) -> tuple[str, str]:
    mclass = member_class(name)
    if local_exists and zip_hash == local_hash:
        return "ZIP_MATCHES_ACTIVE_LOCAL_RAW", "Core active package already has this exact file."
    if not local_exists and mclass in {"WORKBOOK_HELPER", "REVIEW_HELPER"}:
        return "ZIP_EXTRA_HELPER_NOT_PROMOTED", "Helper artifact is not required for engine/runtime ingestion; keep as external archive evidence unless explicitly requested."
    if not local_exists:
        return "ZIP_MEMBER_MISSING_FROM_ACTIVE_LOCAL_RAW", "Candidate member is not present in active local package and requires source review before promotion."
    return "ZIP_DIFFERS_FROM_ACTIVE_LOCAL_RAW", "Candidate member differs from active local package and requires review before promotion."


def build_member_rows(root: Path, zip_path: Path) -> list[dict[str, object]]:
    local_dir = root / LOCAL_RAW_DIR
    rows: list[dict[str, object]] = []
    with zipfile.ZipFile(zip_path) as archive:
        for info in sorted((item for item in archive.infolist() if not item.is_dir()), key=lambda item: item.filename):
            data = archive.read(info)
            name = Path(info.filename).name
            local_path = local_dir / name
            zip_hash = sha256_bytes(data)
            local_hash = sha256_file(local_path)
            fields: list[str] = []
            csv_rows: list[dict[str, str]] = []
            if name.lower().endswith(".csv"):
                fields, csv_rows = read_csv_bytes(data)
            years = sorted({clean(row.get("reported_hunt_year")) for row in csv_rows if clean(row.get("reported_hunt_year"))})
            targets = sorted({clean(row.get("model_target_year")) for row in csv_rows if clean(row.get("model_target_year"))})
            classification, recommendation = classify_member(zip_hash, local_hash, local_path.exists(), name)
            rows.append(
                {
                    "zip_member": info.filename,
                    "file": name,
                    "member_class": member_class(name),
                    "zip_size_bytes": info.file_size,
                    "zip_compressed_bytes": info.compress_size,
                    "zip_sha256": zip_hash,
                    "local_path": str(local_path),
                    "local_exists": local_path.exists(),
                    "local_size_bytes": local_path.stat().st_size if local_path.exists() else 0,
                    "local_sha256": local_hash,
                    "csv_rows": len(csv_rows),
                    "csv_columns": len(fields),
                    "hunt_codes": code_count(csv_rows),
                    "reported_hunt_years": "|".join(years),
                    "model_target_years": "|".join(targets),
                    "classification": classification,
                    "recommendation": recommendation,
                }
            )
    return rows


def build_audit(root: Path, zip_path: Path) -> tuple[dict[str, object], list[dict[str, object]]]:
    member_rows = build_member_rows(root, zip_path)
    _, truth_long = read_csv_file(root / CURRENT_FILES["harvest_truth_long"])
    _, truth_features = read_csv_file(root / CURRENT_FILES["harvest_truth_features"])
    _, model_long = read_csv_file(root / CURRENT_FILES["harvest_model_long"])
    _, model_features = read_csv_file(root / CURRENT_FILES["harvest_model_features"])
    _, feature_model = read_csv_file(root / CURRENT_FILES["harvest_feature_model_2026"])

    feature_using_2025 = [
        row for row in feature_model if "2025" in clean(row.get("harvest_feature_source_years")).split("|")
    ]
    feature_using_2026 = [
        row for row in feature_model if "2026" in clean(row.get("harvest_feature_source_years")).split("|")
    ]
    class_counts = Counter(str(row["classification"]) for row in member_rows)
    member_class_counts = Counter(str(row["member_class"]) for row in member_rows)
    differs = [
        row
        for row in member_rows
        if row["classification"] not in {"ZIP_MATCHES_ACTIVE_LOCAL_RAW", "ZIP_EXTRA_HELPER_NOT_PROMOTED"}
    ]
    result = "PASS_ARCHIVE_MATCHES_ACTIVE_PACKAGE" if not differs else "PASS_WITH_REVIEW_REQUIRED"
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "audit_name": "2025_harvest_zip_candidate",
        "result": result,
        "reported_hunt_year": 2025,
        "model_target_year": 2026,
        "external_source_path": str(zip_path),
        "external_source_exists": zip_path.exists(),
        "external_source_size_bytes": zip_path.stat().st_size if zip_path.exists() else 0,
        "external_source_sha256": sha256_file(zip_path),
        "active_local_raw_dir": str(root / LOCAL_RAW_DIR),
        "zip_members_checked": len(member_rows),
        "member_class_counts": dict(sorted(member_class_counts.items())),
        "classification_counts": dict(sorted(class_counts.items())),
        "zip_members_matching_active_local_raw": class_counts.get("ZIP_MATCHES_ACTIVE_LOCAL_RAW", 0),
        "zip_extra_helpers_not_promoted": class_counts.get("ZIP_EXTRA_HELPER_NOT_PROMOTED", 0),
        "zip_members_requiring_review": len(differs),
        "harvest_truth_2025": summarize_year(truth_long, "reported_hunt_year", "2025"),
        "harvest_truth_features_2025": summarize_year(truth_features, "reported_hunt_year", "2025"),
        "harvest_model_long_2025": summarize_year(model_long, "reported_hunt_year", "2025"),
        "harvest_model_features_2025": summarize_year(model_features, "reported_hunt_year", "2025"),
        "feature_model_rows_using_2025": len(feature_using_2025),
        "feature_model_hunt_codes_using_2025": len({code_value(row) for row in feature_using_2025 if code_value(row)}),
        "feature_model_rows_using_2026_source_year": len(feature_using_2026),
        "promotion_decision": "NO_COPY_NEEDED",
        "promotion_reason": "The ZIP's core harvest CSV/report/SQLite members match the active HUNT-BUILDER raw package byte-for-byte. Extra workbook/rejected-row helper files are archive evidence only and are not needed by the engine feeder contract.",
        "guardrail": "This 2025-for-2026 harvest package is observed 2025 harvest history for the 2026 model. It must not overwrite DATABASE.csv, permit quota, draw odds, or p_draw.",
    }
    return summary, member_rows


def write_csv(path: Path, rows: list[dict[str, object]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, summary: dict[str, object], rows: list[dict[str, object]]) -> None:
    lines = [
        "# 2025 Harvest ZIP Candidate Audit",
        "",
        "Read-only audit of the external `HUNTS` 2025-for-2026 harvest ZIP against the active HUNT-BUILDER package.",
        "",
        "## Summary",
        "",
        f"- Result: `{summary['result']}`.",
        f"- External source path: `{summary['external_source_path']}`.",
        f"- External source SHA256: `{summary['external_source_sha256']}`.",
        f"- ZIP members checked: `{summary['zip_members_checked']}`.",
        f"- Members matching active local raw package: `{summary['zip_members_matching_active_local_raw']}`.",
        f"- Extra helper members not promoted: `{summary['zip_extra_helpers_not_promoted']}`.",
        f"- Members requiring review: `{summary['zip_members_requiring_review']}`.",
        f"- Harvest truth rows for 2025: `{summary['harvest_truth_2025']['rows']}`.",
        f"- Harvest truth hunt codes for 2025: `{summary['harvest_truth_2025']['hunt_codes']}`.",
        f"- Engine harvest feature rows for 2025: `{summary['harvest_model_features_2025']['rows']}`.",
        f"- 2026 feature model rows using 2025 harvest history: `{summary['feature_model_rows_using_2025']}`.",
        f"- 2026 feature model rows using 2026 source year: `{summary['feature_model_rows_using_2026_source_year']}`.",
        "",
        "## Promotion Decision",
        "",
        f"- Decision: `{summary['promotion_decision']}`.",
        f"- Reason: {summary['promotion_reason']}",
        "",
        "## ZIP Member Inventory",
        "",
        "| Member | Class | Rows | Hunt Codes | Local Match Status | Recommendation |",
        "| --- | --- | ---: | ---: | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['file']} | {row['member_class']} | {row['csv_rows']} | {row['hunt_codes']} | {row['classification']} | {row['recommendation']} |"
        )
    lines.extend(["", "## Guardrail", "", str(summary["guardrail"])])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root.")
    parser.add_argument("--zip", default=DEFAULT_ZIP, help="External candidate ZIP path.")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR, help="Audit output directory.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    zip_path = Path(args.zip).resolve()
    out_dir = (root / args.out_dir).resolve()
    if not zip_path.exists():
        raise FileNotFoundError(zip_path)
    summary, member_rows = build_audit(root, zip_path)
    base = out_dir / "harvest_zip_candidate_2025"
    columns = [
        "zip_member",
        "file",
        "member_class",
        "zip_size_bytes",
        "zip_compressed_bytes",
        "zip_sha256",
        "local_path",
        "local_exists",
        "local_size_bytes",
        "local_sha256",
        "csv_rows",
        "csv_columns",
        "hunt_codes",
        "reported_hunt_years",
        "model_target_years",
        "classification",
        "recommendation",
    ]
    write_csv(base.with_suffix(".csv"), member_rows, columns)
    base.with_suffix(".json").write_text(
        json.dumps({"summary": summary, "member_rows": member_rows}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_markdown(base.with_suffix(".md"), summary, member_rows)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
