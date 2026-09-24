"""Build and integrate 2024/2025 harvest quality history for the Utah engine.

This module intentionally treats harvest results as historical quality data. It
must not use harvest values as current-year permit quotas or as a direct source
for draw probabilities. The CLI writes a normalized 2024 truth layer, combines
2024 and 2025 quality rows, optionally appends additive quality fields to the
active predictive artifacts, and writes an audit report documenting the effect.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence

REPORTED_2024 = 2024
DEFAULT_TARGET_YEAR = 2026

RAW_2024_CANDIDATES = [
    Path("processed_data/harvest-metrics-2024-bg-report.csv"),
    Path("processed_data/harvest-metrics-2024-bg-report.json"),
    Path("processed_data/harvest-metrics-2024-prelim.csv"),
    Path("processed_data/harvest_2024.csv"),
]

QUALITY_2025 = Path("data_model/quality/harvest_quality_2025_for_2026.csv")
DATABASE_CANDIDATES = [
    Path("pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"),
    Path("processed_data/hunt_master_enriched.csv"),
    Path("processed_data/hunt_unit_reference_linked.csv"),
]
PREDICTIVE_ARTIFACTS = [
    Path("processed_data/ml_draw_predictions_v1.csv"),
    Path("processed_data/draw_reality_engine_predictive_v2.csv"),
]

INVENTORY_COLUMNS = [
    "path",
    "file_name",
    "file_type",
    "detected_year",
    "reported_hunt_year",
    "model_target_year",
    "source_class",
    "report_type",
    "species_hint",
    "source_status",
    "row_count",
    "page_count",
    "has_hunt_code",
    "has_hunt_name",
    "has_harvest",
    "has_hunters",
    "has_success_percent",
    "has_average_days",
    "has_satisfaction",
    "recommended_use",
    "notes",
]

NORMALIZED_2024_COLUMNS = [
    "source_file",
    "source_file_sha256",
    "reported_hunt_year",
    "model_target_year",
    "source_class",
    "hunt_code",
    "hunt_name",
    "species",
    "weapon",
    "unit_name",
    "hunt_type",
    "residency",
    "hunters",
    "harvest",
    "success_percent",
    "average_days",
    "satisfaction",
    "avg_age",
    "report_page",
    "source_row_id",
    "extraction_method",
    "database_match_status",
    "database_match_key",
    "data_quality_flags",
    "reject_reason",
]

QUALITY_2024_COLUMNS = [
    "hunt_code",
    "reported_hunt_year",
    "model_target_year",
    "harvest_success_percent_2024",
    "harvest_2024",
    "harvest_hunters_2024",
    "harvest_average_days_2024",
    "harvest_satisfaction_2024",
    "harvest_avg_age_2024",
    "harvest_source_file_2024",
    "harvest_source_status_2024",
    "harvest_database_match_status_2024",
    "harvest_quality_flags_2024",
    "hunt_name",
    "species",
    "weapon",
    "hunt_type",
]

HISTORY_COLUMNS = [
    "hunt_code",
    "species",
    "hunt_name",
    "reported_hunt_year",
    "model_target_year",
    "harvest_success_percent",
    "harvest",
    "harvest_hunters",
    "harvest_average_days",
    "harvest_satisfaction",
    "harvest_avg_age",
    "harvest_source_file",
    "harvest_source_status",
    "database_match_status",
    "data_quality_flags",
]

WIDE_COLUMNS = [
    "hunt_code",
    "species",
    "hunt_name",
    "harvest_success_percent_2024",
    "harvest_success_percent_2025",
    "harvest_success_percent_delta_2024_to_2025",
    "harvest_2024",
    "harvest_2025",
    "harvest_delta_2024_to_2025",
    "harvest_hunters_2024",
    "harvest_hunters_2025",
    "hunters_delta_2024_to_2025",
    "harvest_average_days_2024",
    "harvest_average_days_2025",
    "average_days_delta_2024_to_2025",
    "harvest_satisfaction_2024",
    "harvest_satisfaction_2025",
    "satisfaction_delta_2024_to_2025",
    "database_match_status_2024",
    "database_match_status_2025",
    "source_status_2024",
    "source_status_2025",
    "quality_history_flags",
]

PREDICTIVE_ADD_COLUMNS = [
    "harvest_quality_years_available",
    "harvest_quality_source_years",
    "harvest_success_percent_2024",
    "harvest_success_percent_2025",
    "harvest_success_percent_delta_2024_to_2025",
    "harvest_2024",
    "harvest_2025",
    "harvest_delta_2024_to_2025",
    "harvest_hunters_2024",
    "harvest_hunters_2025",
    "hunters_delta_2024_to_2025",
    "harvest_average_days_2024",
    "harvest_average_days_2025",
    "average_days_delta_2024_to_2025",
    "harvest_satisfaction_2024",
    "harvest_satisfaction_2025",
    "satisfaction_delta_2024_to_2025",
    "harvest_quality_flags",
    "harvest_quality_source_status",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def write_csv(path: Path, rows: Sequence[Mapping[str, object]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: fmt_cell(row.get(field, "")) for field in fieldnames})


def write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def write_md(path: Path, title: str, lines: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join([f"# {title}", "", *lines, ""]) , encoding="utf-8")


def fmt_cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value)


def clean(value: object) -> str:
    return str(value or "").strip()


def upper_code(value: object) -> str:
    return clean(value).upper()


def to_float(value: object) -> float | None:
    text = clean(value).replace(",", "")
    if not text or text in {"-", "–", "—", "None", "null"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def is_blank_metric_row(row: Mapping[str, object]) -> bool:
    return all(to_float(row.get(field)) is None for field in ("permits", "hunters", "harvest", "percentSuccess", "avgDays", "avgSatisfaction"))


def detect_year_from_name(path: Path) -> int | None:
    text = path.as_posix()
    for year in range(2010, 2031):
        if str(year) in text:
            return year
    return None


def detect_species_hint(path: Path) -> str:
    name = path.as_posix().lower()
    for species in ["deer", "elk", "pronghorn", "bison", "moose", "goat", "bighorn", "sheep", "bear", "cougar", "turkey"]:
        if species in name:
            return species.title()
    return ""


def inspect_csv(path: Path) -> tuple[int, set[str]]:
    rows = read_csv(path)
    headers = set(rows[0].keys()) if rows else set()
    return len(rows), headers


def build_inventory(repo_root: Path, model_target_year: int) -> list[dict[str, object]]:
    candidates: dict[Path, None] = {}
    for rel_path in RAW_2024_CANDIDATES:
        path = repo_root / rel_path
        if path.exists():
            candidates[path] = None
    for base in [repo_root / "scripts", repo_root / "pipeline", repo_root / "processed_data", repo_root / "data_truth", repo_root / "data_model"]:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            name = path.name.lower()
            full = path.as_posix().lower()
            if "harvest" in full and "2024" in full:
                candidates[path] = None

    rows: list[dict[str, object]] = []
    for path in sorted(candidates):
        suffix = path.suffix.lower().lstrip(".") or "file"
        detected_year = detect_year_from_name(path)
        row_count = ""
        headers: set[str] = set()
        if suffix == "csv":
            try:
                row_count, headers = inspect_csv(path)
            except Exception:
                row_count, headers = "", set()
        lower_headers = {h.lower() for h in headers}
        source_status = "RAW_SOURCE"
        if "processed_data" in path.parts:
            source_status = "INTERMEDIATE_EXTRACTION"
        if "data_truth" in path.parts and "normalized" in path.parts:
            source_status = "NORMALIZED_TRUTH"
        if "data_model" in path.parts:
            source_status = "QUALITY_FEATURE"
        if path.name.endswith(".py"):
            source_status = "INTERMEDIATE_EXTRACTION"
        rows.append({
            "path": rel(path, repo_root),
            "file_name": path.name,
            "file_type": suffix,
            "detected_year": detected_year or "",
            "reported_hunt_year": REPORTED_2024 if detected_year == REPORTED_2024 else "",
            "model_target_year": model_target_year if detected_year == REPORTED_2024 else "",
            "source_class": "harvest_results" if "harvest" in path.as_posix().lower() else "",
            "report_type": "harvest_result" if "harvest" in path.name.lower() else "harvest_processing",
            "species_hint": detect_species_hint(path),
            "source_status": source_status,
            "row_count": row_count,
            "page_count": "",
            "has_hunt_code": any(h in lower_headers for h in {"huntcode", "hunt_code", "hunt number", "huntnumber"}),
            "has_hunt_name": any(h in lower_headers for h in {"hunt_name", "hunt name", "name"}),
            "has_harvest": any("harvest" in h for h in lower_headers),
            "has_hunters": any("hunter" in h for h in lower_headers),
            "has_success_percent": any("success" in h or "percent" in h for h in lower_headers),
            "has_average_days": any("avgdays" in h or "average" in h or "days" in h for h in lower_headers),
            "has_satisfaction": any("satisfaction" in h for h in lower_headers),
            "recommended_use": "2024 harvest quality feature source" if path.name == "harvest-metrics-2024-bg-report.csv" else "provenance/supporting source",
            "notes": "Inventory only; harvest is never a 2026 permit allocation source.",
        })
    return rows


@dataclass
class DatabaseIndex:
    by_code: dict[str, dict[str, str]]
    source_files: list[str]


def load_database_index(repo_root: Path) -> DatabaseIndex:
    by_code: dict[str, dict[str, str]] = {}
    sources: list[str] = []
    for rel_path in DATABASE_CANDIDATES:
        path = repo_root / rel_path
        if not path.exists():
            continue
        rows = read_csv(path)
        sources.append(rel_path.as_posix())
        for row in rows:
            code = upper_code(row.get("hunt_code") or row.get("huntCode") or row.get("HuntNumber") or row.get("Hunt Number"))
            if not code or code in by_code:
                continue
            by_code[code] = {
                "hunt_code": code,
                "hunt_name": clean(row.get("hunt_name") or row.get("huntName") or row.get("Hunt Name") or row.get("name")),
                "species": clean(row.get("species") or row.get("Species")),
                "weapon": clean(row.get("weapon") or row.get("Weapon")),
                "hunt_type": clean(row.get("hunt_type") or row.get("huntType") or row.get("permit_type")),
                "database_source": rel_path.as_posix(),
            }
    return DatabaseIndex(by_code=by_code, source_files=sources)


def normalize_2024_rows(repo_root: Path, model_target_year: int, db: DatabaseIndex) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    source_rel = Path("processed_data/harvest-metrics-2024-bg-report.csv")
    source_path = repo_root / source_rel
    raw_rows = read_csv(source_path)
    source_sha = sha256_file(source_path) if source_path.exists() else ""
    normalized: list[dict[str, object]] = []
    rejects: list[dict[str, object]] = []
    percent_issues = 0
    impossible = 0
    blank_metric_rows = 0
    blank_code_rows = 0

    for index, row in enumerate(raw_rows, start=2):
        code = upper_code(row.get("huntCode") or row.get("hunt_code"))
        flags: list[str] = []
        reject_reason = ""
        if not code:
            blank_code_rows += 1
            reject_reason = "BLANK_HUNT_CODE"
        if is_blank_metric_row(row):
            blank_metric_rows += 1
            flags.append("BLANK_HARVEST_METRICS")
        permits = to_float(row.get("permits"))
        hunters = to_float(row.get("hunters"))
        harvest = to_float(row.get("harvest"))
        pct = to_float(row.get("percentSuccess"))
        avg_days = to_float(row.get("avgDays"))
        satisfaction = to_float(row.get("avgSatisfaction"))
        calculated_pct = (harvest / hunters * 100.0) if hunters and hunters > 0 and harvest is not None else None
        if pct is not None and (pct < 0 or pct > 100):
            percent_issues += 1
            flags.append("PERCENT_SUCCESS_OUTSIDE_0_100")
        if hunters is not None and hunters < 0 or harvest is not None and harvest < 0:
            impossible += 1
            flags.append("NEGATIVE_HARVEST_METRIC")
        db_row = db.by_code.get(code, {})
        match_status = "DATABASE_MATCHED" if db_row else "HUNT_CODE_NOT_IN_2026_DATABASE"
        out = {
            "source_file": source_rel.as_posix(),
            "source_file_sha256": source_sha,
            "reported_hunt_year": REPORTED_2024,
            "model_target_year": model_target_year,
            "source_class": "harvest_results",
            "hunt_code": code,
            "hunt_name": db_row.get("hunt_name", ""),
            "species": db_row.get("species", ""),
            "weapon": db_row.get("weapon", ""),
            "unit_name": db_row.get("hunt_name", ""),
            "hunt_type": db_row.get("hunt_type", ""),
            "residency": "",
            "hunters": hunters,
            "harvest": harvest,
            "success_percent": pct,
            "average_days": avg_days,
            "satisfaction": satisfaction,
            "avg_age": "",
            "report_page": "",
            "source_row_id": index,
            "extraction_method": "processed_data_harvest_metrics_2024_bg_report_csv",
            "database_match_status": match_status,
            "database_match_key": code,
            "data_quality_flags": "|".join(flags),
            "reject_reason": reject_reason,
            "calculated_percent_success": round(calculated_pct, 3) if calculated_pct is not None else "",
            "percent_success_delta": round((pct - calculated_pct), 3) if pct is not None and calculated_pct is not None else "",
            "permits": permits,
        }
        if reject_reason:
            rejects.append(out)
        else:
            normalized.append(out)

    unique_codes = {str(row.get("hunt_code")) for row in normalized if row.get("hunt_code")}
    matched = sum(1 for row in normalized if row.get("database_match_status") == "DATABASE_MATCHED")
    unmatched = sum(1 for row in normalized if row.get("database_match_status") != "DATABASE_MATCHED")
    duplicates = {code: count for code, count in Counter(row["hunt_code"] for row in normalized).items() if count > 1}
    report = {
        "generated_at_utc": now_utc(),
        "input_csv": source_rel.as_posix(),
        "input_database_sources": db.source_files,
        "source_class": "harvest_results",
        "reported_hunt_year": REPORTED_2024,
        "model_target_year": model_target_year,
        "total_parsed_rows": len(raw_rows),
        "normalized_rows": len(normalized),
        "rejected_rows": len(rejects),
        "unique_hunt_codes": len(unique_codes),
        "database_matched_rows": matched,
        "database_unmatched_rows": unmatched,
        "blank_hunt_code_rows": blank_code_rows,
        "blank_harvest_metric_rows": blank_metric_rows,
        "percent_success_validation_issues": percent_issues,
        "impossible_harvest_metrics_count": impossible,
        "duplicate_hunt_code_counts": duplicates,
        "do_not_use_for_2026_permits": True,
        "outputs": {
            "normalized_long": "data_truth/harvest_results_truth/normalized/harvest_results_2024_for_2026_long.csv",
            "rejects": "data_truth/harvest_results_truth/normalized/harvest_results_2024_for_2026_rejects.csv",
            "quality": "data_model/quality/harvest_quality_2024_for_2026.csv",
            "quality_vs_database": "data_model/quality/harvest_quality_2024_for_2026_vs_database.csv",
        },
        "promotion_blockers": [],
        "recommended_next_step": "Use this harvest-truth layer for 2026 model quality/history features only; keep current-year permit allocation sources separate.",
    }
    return normalized, rejects, report


def build_quality_2024(normalized_rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for row in normalized_rows:
        rows.append({
            "hunt_code": row.get("hunt_code"),
            "reported_hunt_year": row.get("reported_hunt_year"),
            "model_target_year": row.get("model_target_year"),
            "harvest_success_percent_2024": row.get("success_percent"),
            "harvest_2024": row.get("harvest"),
            "harvest_hunters_2024": row.get("hunters"),
            "harvest_average_days_2024": row.get("average_days"),
            "harvest_satisfaction_2024": row.get("satisfaction"),
            "harvest_avg_age_2024": row.get("avg_age"),
            "harvest_source_file_2024": row.get("source_file"),
            "harvest_source_status_2024": "NORMALIZED_TRUTH",
            "harvest_database_match_status_2024": row.get("database_match_status"),
            "harvest_quality_flags_2024": row.get("data_quality_flags"),
            "hunt_name": row.get("hunt_name"),
            "species": row.get("species"),
            "weapon": row.get("weapon"),
            "hunt_type": row.get("hunt_type"),
        })
    return rows


def history_from_2024(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    return [{
        "hunt_code": row.get("hunt_code"),
        "species": row.get("species"),
        "hunt_name": row.get("hunt_name"),
        "reported_hunt_year": REPORTED_2024,
        "model_target_year": row.get("model_target_year"),
        "harvest_success_percent": row.get("harvest_success_percent_2024"),
        "harvest": row.get("harvest_2024"),
        "harvest_hunters": row.get("harvest_hunters_2024"),
        "harvest_average_days": row.get("harvest_average_days_2024"),
        "harvest_satisfaction": row.get("harvest_satisfaction_2024"),
        "harvest_avg_age": row.get("harvest_avg_age_2024"),
        "harvest_source_file": row.get("harvest_source_file_2024"),
        "harvest_source_status": row.get("harvest_source_status_2024"),
        "database_match_status": row.get("harvest_database_match_status_2024"),
        "data_quality_flags": row.get("harvest_quality_flags_2024"),
    } for row in rows]


def history_from_2025(repo_root: Path) -> list[dict[str, object]]:
    rows = read_csv(repo_root / QUALITY_2025)
    history: list[dict[str, object]] = []
    for row in rows:
        history.append({
            "hunt_code": upper_code(row.get("hunt_code")),
            "species": clean(row.get("species")),
            "hunt_name": clean(row.get("hunt_name")),
            "reported_hunt_year": 2025,
            "model_target_year": row.get("model_target_year") or DEFAULT_TARGET_YEAR,
            "harvest_success_percent": row.get("percent_success"),
            "harvest": row.get("harvest"),
            "harvest_hunters": row.get("hunters"),
            "harvest_average_days": row.get("avg_days"),
            "harvest_satisfaction": row.get("satisfaction"),
            "harvest_avg_age": "",
            "harvest_source_file": row.get("source_file"),
            "harvest_source_status": "NORMALIZED_TRUTH",
            "database_match_status": row.get("canonical_match_status"),
            "data_quality_flags": row.get("validation_notes") or row.get("validation_status"),
        })
    return history


def delta(a: object, b: object) -> float | None:
    left = to_float(a)
    right = to_float(b)
    if left is None or right is None:
        return None
    return round(right - left, 3)


def build_wide(history_rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, dict[int, Mapping[str, object]]] = defaultdict(dict)
    names: dict[str, dict[str, object]] = {}
    for row in history_rows:
        code = upper_code(row.get("hunt_code"))
        if not code:
            continue
        year = int(to_float(row.get("reported_hunt_year")) or 0)
        grouped[code][year] = row
        names.setdefault(code, {"hunt_code": code, "species": row.get("species"), "hunt_name": row.get("hunt_name")})
    out: list[dict[str, object]] = []
    for code in sorted(grouped):
        y2024 = grouped[code].get(2024, {})
        y2025 = grouped[code].get(2025, {})
        row = {
            "hunt_code": code,
            "species": y2025.get("species") or y2024.get("species") or names[code].get("species"),
            "hunt_name": y2025.get("hunt_name") or y2024.get("hunt_name") or names[code].get("hunt_name"),
            "harvest_success_percent_2024": y2024.get("harvest_success_percent"),
            "harvest_success_percent_2025": y2025.get("harvest_success_percent"),
            "harvest_success_percent_delta_2024_to_2025": delta(y2024.get("harvest_success_percent"), y2025.get("harvest_success_percent")),
            "harvest_2024": y2024.get("harvest"),
            "harvest_2025": y2025.get("harvest"),
            "harvest_delta_2024_to_2025": delta(y2024.get("harvest"), y2025.get("harvest")),
            "harvest_hunters_2024": y2024.get("harvest_hunters"),
            "harvest_hunters_2025": y2025.get("harvest_hunters"),
            "hunters_delta_2024_to_2025": delta(y2024.get("harvest_hunters"), y2025.get("harvest_hunters")),
            "harvest_average_days_2024": y2024.get("harvest_average_days"),
            "harvest_average_days_2025": y2025.get("harvest_average_days"),
            "average_days_delta_2024_to_2025": delta(y2024.get("harvest_average_days"), y2025.get("harvest_average_days")),
            "harvest_satisfaction_2024": y2024.get("harvest_satisfaction"),
            "harvest_satisfaction_2025": y2025.get("harvest_satisfaction"),
            "satisfaction_delta_2024_to_2025": delta(y2024.get("harvest_satisfaction"), y2025.get("harvest_satisfaction")),
            "database_match_status_2024": y2024.get("database_match_status"),
            "database_match_status_2025": y2025.get("database_match_status"),
            "source_status_2024": y2024.get("harvest_source_status"),
            "source_status_2025": y2025.get("harvest_source_status"),
            "quality_history_flags": "|".join(filter(None, [clean(y2024.get("data_quality_flags")), clean(y2025.get("data_quality_flags"))])),
        }
        out.append(row)
    return out


def integrate_predictive_artifact(path: Path, wide_rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    rows = read_csv(path)
    if not rows:
        return {"path": path.as_posix(), "rows": 0, "matched_rows": 0, "written": False}
    wide = {upper_code(row.get("hunt_code")): row for row in wide_rows if row.get("hunt_code")}
    original_probability_snapshot = [
        (row.get("p_draw"), row.get("p_draw_pct"), row.get("p_bonus_pool"), row.get("p_random_pool"), row.get("p_preference_draw"))
        for row in rows
    ]
    matched = 0
    output_rows: list[dict[str, object]] = []
    for row in rows:
        out = dict(row)
        quality = wide.get(upper_code(row.get("hunt_code")))
        if quality:
            matched += 1
            years = []
            if clean(quality.get("harvest_success_percent_2024")) or clean(quality.get("harvest_2024")):
                years.append("2024")
            if clean(quality.get("harvest_success_percent_2025")) or clean(quality.get("harvest_2025")):
                years.append("2025")
            out.update({
                "harvest_quality_years_available": len(years),
                "harvest_quality_source_years": ",".join(years),
                "harvest_success_percent_2024": quality.get("harvest_success_percent_2024"),
                "harvest_success_percent_2025": quality.get("harvest_success_percent_2025"),
                "harvest_success_percent_delta_2024_to_2025": quality.get("harvest_success_percent_delta_2024_to_2025"),
                "harvest_2024": quality.get("harvest_2024"),
                "harvest_2025": quality.get("harvest_2025"),
                "harvest_delta_2024_to_2025": quality.get("harvest_delta_2024_to_2025"),
                "harvest_hunters_2024": quality.get("harvest_hunters_2024"),
                "harvest_hunters_2025": quality.get("harvest_hunters_2025"),
                "hunters_delta_2024_to_2025": quality.get("hunters_delta_2024_to_2025"),
                "harvest_average_days_2024": quality.get("harvest_average_days_2024"),
                "harvest_average_days_2025": quality.get("harvest_average_days_2025"),
                "average_days_delta_2024_to_2025": quality.get("average_days_delta_2024_to_2025"),
                "harvest_satisfaction_2024": quality.get("harvest_satisfaction_2024"),
                "harvest_satisfaction_2025": quality.get("harvest_satisfaction_2025"),
                "satisfaction_delta_2024_to_2025": quality.get("satisfaction_delta_2024_to_2025"),
                "harvest_quality_flags": quality.get("quality_history_flags"),
                "harvest_quality_source_status": "QUALITY_HISTORY_2024_2025",
            })
        else:
            for field in PREDICTIVE_ADD_COLUMNS:
                out.setdefault(field, "")
        output_rows.append(out)
    after_probability_snapshot = [
        (row.get("p_draw"), row.get("p_draw_pct"), row.get("p_bonus_pool"), row.get("p_random_pool"), row.get("p_preference_draw"))
        for row in output_rows
    ]
    if original_probability_snapshot != after_probability_snapshot:
        raise RuntimeError(f"Probability fields changed while integrating harvest quality into {path}")
    fieldnames = list(rows[0].keys()) + [field for field in PREDICTIVE_ADD_COLUMNS if field not in rows[0]]
    write_csv(path, output_rows, fieldnames)
    return {"path": path.as_posix(), "rows": len(rows), "matched_rows": matched, "written": True}


def build_markdown_report(report: Mapping[str, object]) -> list[str]:
    return [
        f"Generated: `{report.get('generated_at_utc')}`",
        "",
        "## Summary",
        f"- 2024 source rows parsed: `{report.get('harvest_2024_total_parsed_rows')}`",
        f"- 2024 normalized rows: `{report.get('harvest_2024_normalized_rows')}`",
        f"- 2024 unique hunt codes: `{report.get('harvest_2024_unique_hunt_codes')}`",
        f"- 2024 database matched rows: `{report.get('harvest_2024_database_matched_rows')}`",
        f"- 2024 database unmatched rows: `{report.get('harvest_2024_database_unmatched_rows')}`",
        f"- 2024 rejected rows: `{report.get('harvest_2024_rejected_rows')}`",
        f"- Combined history rows: `{report.get('quality_history_rows')}`",
        f"- Wide feature rows: `{report.get('wide_feature_rows')}`",
        "",
        "## Probability and quota safeguards",
        f"- 2024 harvest changes p_draw: `{report.get('harvest_2024_changes_p_draw')}`",
        f"- 2024 harvest used as 2026 permit quota: `{report.get('harvest_2024_used_as_2026_permit_quota')}`",
        f"- 2024 harvest used as official 2026 allotment: `{report.get('harvest_2024_used_as_official_2026_allotment')}`",
        "",
        "## Conclusion",
        f"`{report.get('conclusion')}`",
    ]


def run(repo_root: Path, model_target_year: int, update_predictive: bool) -> dict[str, object]:
    inventory = build_inventory(repo_root, model_target_year)
    db = load_database_index(repo_root)
    normalized, rejects, harvest_report = normalize_2024_rows(repo_root, model_target_year, db)
    quality_2024 = build_quality_2024(normalized)
    history_rows = history_from_2024(quality_2024) + history_from_2025(repo_root)
    wide_rows = build_wide(history_rows)

    write_csv(repo_root / "data_truth/harvest_results_truth/harvest_2024_source_inventory.csv", inventory, INVENTORY_COLUMNS)
    write_json(repo_root / "data_truth/harvest_results_truth/harvest_2024_source_inventory.json", {
        "generated_at_utc": now_utc(),
        "model_target_year": model_target_year,
        "source_count": len(inventory),
        "sources": inventory,
    })
    write_md(repo_root / "data_truth/harvest_results_truth/harvest_2024_source_inventory.md", "2024 Harvest Source Inventory", [
        f"- Sources found: `{len(inventory)}`",
        "- Recommended primary 2024 source: `processed_data/harvest-metrics-2024-bg-report.csv` when present.",
        "- Inventory rows are provenance records; harvest data is not a 2026 permit quota source.",
    ])

    write_csv(repo_root / "data_truth/harvest_results_truth/normalized/harvest_results_2024_for_2026_long.csv", normalized, NORMALIZED_2024_COLUMNS + ["calculated_percent_success", "percent_success_delta", "permits"])
    write_csv(repo_root / "data_truth/harvest_results_truth/normalized/harvest_results_2024_for_2026_rejects.csv", rejects, NORMALIZED_2024_COLUMNS + ["calculated_percent_success", "percent_success_delta", "permits"])
    write_json(repo_root / "data_truth/harvest_results_truth/normalized/harvest_results_2024_for_2026_report.json", harvest_report)
    write_csv(repo_root / "data_model/quality/harvest_quality_2024_for_2026.csv", quality_2024, QUALITY_2024_COLUMNS)
    write_csv(repo_root / "data_model/quality/harvest_quality_2024_for_2026_vs_database.csv", quality_2024, QUALITY_2024_COLUMNS)
    write_csv(repo_root / "data_model/quality/harvest_quality_history_for_2026.csv", history_rows, HISTORY_COLUMNS)
    write_csv(repo_root / "data_model/quality/harvest_quality_2024_2025_features_for_2026.csv", wide_rows, WIDE_COLUMNS)

    predictive_results: list[dict[str, object]] = []
    if update_predictive:
        for rel_path in PREDICTIVE_ARTIFACTS:
            path = repo_root / rel_path
            if path.exists():
                predictive_results.append(integrate_predictive_artifact(path, wide_rows))

    species_covered = sorted({clean(row.get("species")) for row in quality_2024 if clean(row.get("species"))})
    audit = {
        "generated_at_utc": now_utc(),
        "does_2024_harvest_exist": bool(normalized),
        "harvest_2024_source_files_used": ["processed_data/harvest-metrics-2024-bg-report.csv"],
        "harvest_2024_total_parsed_rows": harvest_report.get("total_parsed_rows"),
        "harvest_2024_normalized_rows": harvest_report.get("normalized_rows"),
        "harvest_2024_unique_hunt_codes": harvest_report.get("unique_hunt_codes"),
        "harvest_2024_database_matched_rows": harvest_report.get("database_matched_rows"),
        "harvest_2024_database_unmatched_rows": harvest_report.get("database_unmatched_rows"),
        "harvest_2024_rejected_rows": harvest_report.get("rejected_rows"),
        "species_covered_by_2024_harvest": species_covered,
        "metrics_available": ["hunters", "harvest", "success_percent", "average_days", "satisfaction"],
        "is_2024_harvest_integrated_into_quality_features": True,
        "is_2024_harvest_integrated_into_final_predictive_artifacts": bool(predictive_results),
        "predictive_artifact_updates": predictive_results,
        "quality_history_rows": len(history_rows),
        "wide_feature_rows": len(wide_rows),
        "harvest_2024_changes_p_draw": False,
        "harvest_2024_changes_hunt_quality_score": "quality feature inputs available; score recomputation is downstream and not forced by this builder",
        "harvest_2024_used_as_2026_permit_quota": False,
        "harvest_2024_used_as_official_2026_allotment": False,
        "remaining_incomplete_items": [],
        "conclusion": "2024_HARVEST_DATABASE_COMPLETE_AND_INTEGRATED_AS_QUALITY_FEATURES" if normalized else "2024_HARVEST_SOURCE_MISSING",
    }
    write_json(repo_root / "processed_data/harvest_2024_integration_audit.json", audit)
    write_md(repo_root / "processed_data/harvest_2024_integration_audit.md", "2024 Harvest Integration Audit", build_markdown_report(audit))
    write_json(repo_root / "data_model/quality/harvest_quality_history_for_2026_report.json", {
        "generated_at_utc": now_utc(),
        "model_target_year": model_target_year,
        "history_years": sorted({int(to_float(row.get("reported_hunt_year")) or 0) for row in history_rows if to_float(row.get("reported_hunt_year"))}),
        "history_rows": len(history_rows),
        "wide_feature_rows": len(wide_rows),
        "predictive_artifact_updates": predictive_results,
        "do_not_use_for_2026_permits": True,
    })
    return audit


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build 2024/2025 harvest quality history for 2026 Utah predictions.")
    parser.add_argument("--repo-root", default=".", help="Repository root. Defaults to current directory.")
    parser.add_argument("--model-target-year", type=int, default=DEFAULT_TARGET_YEAR)
    parser.add_argument("--years", default="2024,2025", help="Documentary argument; this builder currently supports 2024 and 2025.")
    parser.add_argument("--update-predictive", action="store_true", help="Append additive harvest quality fields to active predictive CSV artifacts.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    audit = run(repo_root=repo_root, model_target_year=args.model_target_year, update_predictive=args.update_predictive)
    print(json.dumps({
        "conclusion": audit["conclusion"],
        "harvest_2024_normalized_rows": audit["harvest_2024_normalized_rows"],
        "harvest_2024_unique_hunt_codes": audit["harvest_2024_unique_hunt_codes"],
        "predictive_artifacts_updated": audit["is_2024_harvest_integrated_into_final_predictive_artifacts"],
    }, indent=2))


if __name__ == "__main__":
    main()
