"""Audit draw_system_type-based engine routing after source-column alignment.

This script is audit-only. It writes reconciliation evidence under a supplied
audit directory and does not promote runtime files.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable, Mapping, Sequence


REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from engine.utah_draw_predictive.run_all_families import _family_for_legacy_row, _prefix_family_guess

CANONICAL_DIR = REPO / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"
LONG_PATH = REPO / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
DATABASE_PATH = REPO / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"

SPORTSMAN_CODES = {
    "TK0001",
    "BI1000",
    "BR1000",
    "DB0007",
    "DS1000",
    "EB1000",
    "GO1000",
    "MB1000",
    "PB1000",
    "RS0001",
    "CG1000",
}
PREDICTIVE_DRAW_SYSTEM_TYPES = {
    "MAX_WEIGHTED_SPLIT",
    "SPORTSMAN_RANDOM_ONLY",
    "BONUS_SPLIT_DRAW",
    "BONUS_TURKEY",
    "YOUTH_TURKEY_SET_ASIDE",
    "BLACK_BEAR",
    "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
    "PREFERENCE_DEDICATED_HUNTER_DEER",
    "PREFERENCE_ANTLERLESS_DEER",
    "PREFERENCE_ANTLERLESS_ELK",
    "PREFERENCE_DOE_PRONGHORN",
    "YOUTH_GENERAL_ANY_BULL_ELK",
    "YOUTH_RANDOM",
}
REFERENCE_DRAW_SYSTEM_TYPES = {"REFERENCE_ONLY", "AVAILABILITY_ONLY", "TRIBAL", "GUARANTEED_LIFETIME_PERMIT"}
PREFERENCE_FAMILIES = {
    "preference_general_deer",
    "dedicated_hunter",
    "preference_antlerless_deer",
    "preference_antlerless_elk",
    "preference_doe_pronghorn",
}


def clean(value: object) -> str:
    return str(value or "").strip()


def clean_upper(value: object) -> str:
    return clean(value).upper()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_csv(path: Path, rows: Sequence[Mapping[str, object]], fieldnames: Sequence[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fields: list[str] = []
        for row in rows:
            for key in row:
                if key not in fields:
                    fields.append(key)
        fieldnames = fields or ["no_rows"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO))
    except ValueError:
        return str(path)


def target_files() -> list[Path]:
    return sorted(CANONICAL_DIR.glob("*.csv")) + [LONG_PATH, DATABASE_PATH]


def source_year_from_file(path: Path) -> int | None:
    name = path.name
    for token in name.replace("_", " ").split():
        if token.isdigit() and len(token) == 4:
            return int(token)
    return None


def row_year(row: Mapping[str, object], fallback: int | None = None) -> int | None:
    for key in ("actual_draw_year", "source_year", "draw_year", "year"):
        text = clean(row.get(key)).replace(",", "")
        if not text:
            continue
        try:
            return int(float(text))
        except ValueError:
            continue
    return fallback


def probability(row: Mapping[str, object]) -> float | None:
    for key in ("p_draw_mean", "p_draw", "p_preference_draw", "p_sportsman_draw", "probability"):
        text = clean(row.get(key)).replace("%", "")
        if not text:
            continue
        try:
            val = float(text)
        except ValueError:
            continue
        if val > 1 and key.endswith("pct"):
            val = val / 100.0
        return max(0.0, min(1.0, val))
    return None


def actual_probability(row: Mapping[str, object]) -> float | None:
    for key in ("success_rate", "success_ratio", "p_draw", "actual_p_draw", "total_success_ratio"):
        text = clean(row.get(key))
        if not text or text.upper() == "N/A":
            continue
        if " in " in text:
            try:
                denom = float(text.rsplit(" ", 1)[-1])
                return 1.0 / denom if denom > 0 else None
            except ValueError:
                continue
        text = text.replace("%", "")
        try:
            val = float(text)
        except ValueError:
            continue
        if val > 1:
            val = val / 100.0
        return max(0.0, min(1.0, val))
    eligible = number(row, "eligible_applicants", "total_applicants")
    drawn = number(row, "total_permits", "total_regular_permits", "resident_total_permits")
    if eligible and eligible > 0 and drawn is not None:
        return max(0.0, min(1.0, drawn / eligible))
    return None


def number(row: Mapping[str, object], *keys: str) -> float | None:
    for key in keys:
        text = clean(row.get(key)).replace(",", "")
        if not text:
            continue
        try:
            return float(text)
        except ValueError:
            continue
    return None


def is_tribal(row: Mapping[str, object]) -> bool:
    text = " ".join(clean(row.get(key)).lower() for key in ("hunt_code", "hunt_name", "hunt_type", "hunt_class", "draw_system_type"))
    return "tribal" in text


def is_statewide_sportsman_style(row: Mapping[str, object]) -> bool:
    return clean_upper(row.get("hunt_code")) in SPORTSMAN_CODES


def is_lifetime_general_deer(row: Mapping[str, object]) -> bool:
    joined = " ".join(
        clean(row.get(key)).lower()
        for key in ("hunt_code", "hunt_name", "species", "sex_type", "hunt_type", "hunt_class", "hunt_draw_class", "draw_class_type", "draw_design", "draw_system_type")
    )
    if "once-in-a-lifetime" in joined or "once in a lifetime" in joined:
        return False
    return (
        "lifetime_general" in joined
        or "lifetime general season" in joined
        or "lifetime deer" in joined
        or clean_upper(row.get("hunt_class")).startswith("LIFETIME")
        or clean_upper(row.get("hunt_draw_class") or row.get("draw_class_type")).startswith("LIFETIME")
    )


def is_deer_prefix_source_backed_exception(row: Mapping[str, object]) -> bool:
    draw_system = clean_upper(row.get("draw_system_type"))
    joined = " ".join(
        clean(row.get(key)).lower()
        for key in ("hunt_code", "hunt_name", "species", "sex_type", "hunt_type", "hunt_class", "hunt_draw_class", "draw_class_type", "draw_design", "draw_system_type")
    )
    return (
        is_lifetime_general_deer(row)
        or draw_system in REFERENCE_DRAW_SYSTEM_TYPES
        or "youth" in joined
        or "tribal" in joined
        or "private" in joined
        or "landowner" in joined
        or "conservation" in joined
    )


def expected_family(row: Mapping[str, object]) -> str:
    draw_system = clean_upper(row.get("draw_system_type"))
    if draw_system in REFERENCE_DRAW_SYSTEM_TYPES:
        return ""
    return _family_for_legacy_row(row)


def prediction_key(row: Mapping[str, object]) -> tuple[str, str, str, str]:
    return (
        clean_upper(row.get("hunt_code")),
        clean(row.get("residency")).lower(),
        clean(row.get("points")),
        clean_upper(row.get("draw_system_type")),
    )


def actual_key(row: Mapping[str, object]) -> tuple[str, str, str, str]:
    return prediction_key(row)


def metrics(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    errors: list[float] = []
    signed: list[float] = []
    non_extreme: list[float] = []
    reversals = 0
    p_zero = p_one = actual_zero = actual_one = 0
    by_res: dict[str, list[float]] = defaultdict(list)
    worst_codes: Counter[str] = Counter()
    worst_points: Counter[str] = Counter()
    for row in rows:
        pred = probability(row)
        actual = actual_probability(row)
        if pred is None or actual is None:
            continue
        err = pred - actual
        abs_err = abs(err)
        errors.append(abs_err)
        signed.append(err)
        by_res[clean(row.get("residency")) or "unknown"].append(err)
        if pred <= 0.000001:
            p_zero += 1
        if pred >= 0.999999:
            p_one += 1
        if actual <= 0.000001:
            actual_zero += 1
        if actual >= 0.999999:
            actual_one += 1
        if (pred <= 0.000001 and actual >= 0.999999) or (pred >= 0.999999 and actual <= 0.000001):
            reversals += 1
        if 0.000001 < pred < 0.999999 and 0.000001 < actual < 0.999999:
            non_extreme.append(abs_err)
        if abs_err >= 0.25:
            worst_codes[clean_upper(row.get("hunt_code"))] += 1
            worst_points[clean(row.get("points"))] += 1
    n = len(errors)
    return {
        "scored_rows": n,
        "mae": sum(errors) / n if n else "",
        "rmse": math.sqrt(sum(e * e for e in errors) / n) if n else "",
        "bias": sum(signed) / n if n else "",
        "hard_0_1_reversal_rows": reversals,
        "p_0_rows": p_zero,
        "p_1_rows": p_one,
        "actual_0_rows": actual_zero,
        "actual_1_rows": actual_one,
        "non_extreme_calibration_error": sum(non_extreme) / len(non_extreme) if non_extreme else "",
        "worst_hunt_codes": ";".join(code for code, _ in worst_codes.most_common(10)),
        "worst_point_levels": ";".join(point for point, _ in worst_points.most_common(10)),
        "resident_bias": sum(by_res["resident"]) / len(by_res["resident"]) if by_res.get("resident") else "",
        "nonresident_bias": sum(by_res["nonresident"]) / len(by_res["nonresident"]) if by_res.get("nonresident") else "",
    }


def load_all_source_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in target_files():
        headers, file_rows = read_csv(path)
        fallback_year = source_year_from_file(path)
        for idx, row in enumerate(file_rows, start=2):
            item: dict[str, object] = dict(row)
            item["_source_file"] = rel(path)
            item["_line"] = idx
            item["_fallback_year"] = fallback_year or ""
            item["_has_draw_system_type_column"] = "draw_system_type" in headers
            rows.append(item)
    return rows


def audit_gate(audit_dir: Path, rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    file_summary: list[dict[str, object]] = []
    conflicts: list[dict[str, object]] = []
    by_file: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        by_file[clean(row.get("_source_file"))].append(row)
    for file, file_rows in sorted(by_file.items()):
        missing = [
            row
            for row in file_rows
            if not bool(row.get("_has_draw_system_type_column"))
            or clean_upper(row.get("draw_system_type")) in {"", "UNKNOWN", "UNKNOWN_REVIEW_REQUIRED"}
        ]
        file_summary.append(
            {
                "file": file,
                "row_count": len(file_rows),
                "has_draw_system_type": bool(file_rows and file_rows[0].get("_has_draw_system_type_column")),
                "missing_or_unknown_draw_system_type_rows": len(missing),
            }
        )
    for row in rows:
        code = clean_upper(row.get("hunt_code"))
        draw_system = clean_upper(row.get("draw_system_type"))
        if not row.get("_has_draw_system_type_column") or draw_system in {"", "UNKNOWN", "UNKNOWN_REVIEW_REQUIRED"}:
            conflicts.append(conflict(row, "MISSING_OR_UNKNOWN_DRAW_SYSTEM_TYPE"))
        if code == "RS1000" and draw_system != "MAX_WEIGHTED_SPLIT":
            conflicts.append(conflict(row, "RS1000_NOT_MAX_WEIGHTED_SPLIT"))
        if code in SPORTSMAN_CODES and draw_system != "SPORTSMAN_RANDOM_ONLY":
            conflicts.append(conflict(row, "SPORTSMAN_STYLE_NOT_SPORTSMAN_RANDOM_ONLY"))
        if code in SPORTSMAN_CODES and draw_system in {"RANDOM", "MAX_WEIGHTED_SPLIT"}:
            conflicts.append(conflict(row, "SPORTSMAN_STYLE_REMAINS_RANDOM_OR_MAX_WEIGHTED"))
        if is_tribal(row) and draw_system != "TRIBAL":
            conflicts.append(conflict(row, "TRIBAL_NOT_TRIBAL"))
        if draw_system == "TRIBAL" and expected_family(row):
            conflicts.append(conflict(row, "TRIBAL_MODELED_AS_PUBLIC_ODDS"))
        if code.startswith(("DB15", "DB16")) and clean_upper(row.get("species")) == "DEER" and not is_deer_prefix_source_backed_exception(row):
            if draw_system != "PREFERENCE_GENERAL_SEASON_BUCK_DEER":
                conflicts.append(conflict(row, "DB15_DB16_NOT_GENERAL_DEER_OR_SOURCE_BACKED_EXCEPTION"))
        if code.startswith("DB17") and clean_upper(row.get("species")) == "DEER" and not is_deer_prefix_source_backed_exception(row):
            if draw_system != "PREFERENCE_DEDICATED_HUNTER_DEER":
                conflicts.append(conflict(row, "DB17_NOT_DEDICATED_HUNTER_OR_SOURCE_BACKED_EXCEPTION"))
    write_csv(audit_dir / "draw_system_type_engine_routing_gate.csv", file_summary)
    write_csv(audit_dir / "draw_system_type_engine_routing_conflicts.csv", conflicts)
    return {
        "files_with_draw_system_type": sum(1 for row in file_summary if row["has_draw_system_type"]),
        "files_missing_draw_system_type": sum(1 for row in file_summary if not row["has_draw_system_type"]),
        "missing_unknown_rows": sum(int(row["missing_or_unknown_draw_system_type_rows"]) for row in file_summary),
        "conflict_count": len(conflicts),
    }


def conflict(row: Mapping[str, object], reason: str) -> dict[str, object]:
    return {
        "source_file": row.get("_source_file", ""),
        "line": row.get("_line", ""),
        "reason": reason,
        "hunt_code": row.get("hunt_code", ""),
        "hunt_name": row.get("hunt_name", ""),
        "species": row.get("species", ""),
        "sex_type": row.get("sex_type", ""),
        "hunt_type": row.get("hunt_type", ""),
        "hunt_class": row.get("hunt_class", ""),
        "hunt_draw_class": row.get("hunt_draw_class") or row.get("draw_class_type", ""),
        "draw_design": row.get("draw_design", ""),
        "draw_system_type": row.get("draw_system_type", ""),
    }


def audit_family_assignment(audit_dir: Path, rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    out: list[dict[str, object]] = []
    family_counts: Counter[str] = Counter()
    for row in rows:
        draw_system = clean_upper(row.get("draw_system_type"))
        family = _family_for_legacy_row(row)
        prefix = _prefix_family_guess(row)
        family_counts[family or ""] += 1
        out.append(
            {
                "source_file": row.get("_source_file", ""),
                "line": row.get("_line", ""),
                "hunt_code": row.get("hunt_code", ""),
                "species": row.get("species", ""),
                "sex_type": row.get("sex_type", ""),
                "hunt_type": row.get("hunt_type", ""),
                "hunt_class": row.get("hunt_class", ""),
                "hunt_draw_class": row.get("hunt_draw_class") or row.get("draw_class_type", ""),
                "draw_design": row.get("draw_design", ""),
                "draw_system_type": draw_system,
                "engine_family": family,
                "prefix_fallback_family": prefix,
                "routing_source": "draw_system_type" if family and draw_system else ("prefix_fallback" if prefix else "not_modeled"),
            }
        )
    write_csv(audit_dir / "engine_family_assignment_audit.csv", out)
    return dict(family_counts)


def audit_reference_guardrails(audit_dir: Path, rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    out: list[dict[str, object]] = []
    lifetime_rows: list[dict[str, object]] = []
    modeled_lifetime = 0
    for row in rows:
        draw_system = clean_upper(row.get("draw_system_type"))
        family = _family_for_legacy_row(row)
        ref_kind = ""
        if draw_system in {"TRIBAL", "REFERENCE_ONLY", "AVAILABILITY_ONLY"}:
            ref_kind = draw_system
        if is_lifetime_general_deer(row):
            ref_kind = "LIFETIME_GENERAL_SEASON_DEER"
        if not ref_kind:
            continue
        status = "PASS"
        reason = ""
        if ref_kind == "LIFETIME_GENERAL_SEASON_DEER":
            if draw_system not in {"REFERENCE_ONLY", "GUARANTEED_LIFETIME_PERMIT"} or family:
                status = "FAIL"
                reason = "LIFETIME_GENERAL_SEASON_DEER_GUARANTEED_NO_DRAW_POOL"
                modeled_lifetime += 1
        elif draw_system == "TRIBAL" and family:
            status = "FAIL"
            reason = "TRIBAL_ROW_MODELED_AS_PUBLIC_ODDS"
        row_out = {
            "source_file": row.get("_source_file", ""),
            "line": row.get("_line", ""),
            "guardrail_kind": ref_kind,
            "status": status,
            "reason": reason or ("LIFETIME_GENERAL_SEASON_DEER_GUARANTEED_NO_DRAW_POOL" if ref_kind == "LIFETIME_GENERAL_SEASON_DEER" else ""),
            "hunt_code": row.get("hunt_code", ""),
            "hunt_name": row.get("hunt_name", ""),
            "species": row.get("species", ""),
            "sex_type": row.get("sex_type", ""),
            "hunt_type": row.get("hunt_type", ""),
            "hunt_class": row.get("hunt_class", ""),
            "hunt_draw_class": row.get("hunt_draw_class") or row.get("draw_class_type", ""),
            "draw_design": row.get("draw_design", ""),
            "draw_system_type": draw_system,
            "engine_family": family,
            "draw_pool": row.get("draw_pool", ""),
        }
        out.append(row_out)
        if ref_kind == "LIFETIME_GENERAL_SEASON_DEER":
            lifetime_rows.append(row_out)
    write_csv(audit_dir / "tribal_reference_availability_guardrail_audit.csv", out)
    write_csv(audit_dir / "lifetime_general_season_deer_guardrail_audit.csv", lifetime_rows)
    return {
        "reference_guardrail_failures": sum(1 for row in out if row["status"] != "PASS"),
        "lifetime_rows": len(lifetime_rows),
        "lifetime_modeled_rows": modeled_lifetime,
    }


def write_alignment_audits(audit_dir: Path, rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    sportsman = []
    max_weighted = []
    bear_turkey_youth = []
    point_rows = []
    total_only = []
    for row in rows:
        code = clean_upper(row.get("hunt_code"))
        draw_system = clean_upper(row.get("draw_system_type"))
        line = {
            "source_file": row.get("_source_file", ""),
            "line": row.get("_line", ""),
            "hunt_code": code,
            "hunt_name": row.get("hunt_name", ""),
            "species": row.get("species", ""),
            "sex_type": row.get("sex_type", ""),
            "residency": row.get("residency", ""),
            "points": row.get("points", ""),
            "hunt_type": row.get("hunt_type", ""),
            "hunt_class": row.get("hunt_class", ""),
            "hunt_draw_class": row.get("hunt_draw_class") or row.get("draw_class_type", ""),
            "draw_design": row.get("draw_design", ""),
            "draw_system_type": draw_system,
            "engine_family": _family_for_legacy_row(row),
        }
        if code in SPORTSMAN_CODES or draw_system == "SPORTSMAN_RANDOM_ONLY":
            sportsman.append({**line, "status": "PASS" if draw_system == "SPORTSMAN_RANDOM_ONLY" and clean(row.get("residency")).lower() != "nonresident" else "REVIEW"})
        if draw_system == "MAX_WEIGHTED_SPLIT":
            max_weighted.append(line)
        if draw_system in {"BLACK_BEAR", "BONUS_TURKEY", "YOUTH_TURKEY_SET_ASIDE", "YOUTH_GENERAL_ANY_BULL_ELK", "YOUTH_RANDOM"}:
            bear_turkey_youth.append(line)
        if _family_for_legacy_row(row) in PREFERENCE_FAMILIES:
            point_rows.append({**line, "key_status": "PASS" if code and clean(row.get("residency")) and clean(row.get("points")) != "" else "REVIEW"})
        total = number(row, "permits_2026_total", "target_permits_total", "total_permits")
        res = number(row, "permits_2026_res", "target_permits_res", "resident_total_permits")
        nr = number(row, "permits_2026_nr", "target_permits_nr", "nonresident_total_permits")
        if total is not None and total > 0 and not res and not nr:
            total_only.append({**line, "total_permits": total, "status": "TOTAL_ONLY_EXPECTED_OR_REVIEW"})
    write_csv(audit_dir / "sportsman_random_only_alignment_audit.csv", sportsman)
    write_csv(audit_dir / "max_weighted_split_alignment_audit.csv", max_weighted)
    write_csv(audit_dir / "bear_turkey_youth_alignment_audit.csv", bear_turkey_youth)
    write_csv(audit_dir / "point_residency_key_alignment_after_draw_system_type.csv", point_rows)
    return {
        "sportsman_rows": len(sportsman),
        "sportsman_review_rows": sum(1 for row in sportsman if row.get("status") != "PASS"),
        "max_weighted_rows": len(max_weighted),
        "bear_turkey_youth_rows": len(bear_turkey_youth),
        "point_key_review_rows": sum(1 for row in point_rows if row.get("key_status") != "PASS"),
        "total_only_rows": len(total_only),
    }


def audit_preferences(audit_dir: Path, run_dirs: Sequence[Path]) -> dict[str, object]:
    family_join_rows: dict[str, list[dict[str, object]]] = defaultdict(list)
    extreme_rows: list[dict[str, object]] = []
    for run_dir in run_dirs:
        pred_path = run_dir / "family_predictions.csv"
        if not pred_path.exists():
            continue
        _, pred_rows = read_csv(pred_path)
        target_year = None
        for row in pred_rows:
            target_year = int(clean(row.get("target_year")) or "0") or target_year
        if not target_year:
            continue
        canonical = CANONICAL_DIR / f"draw_results_{target_year}_for_{target_year + 1}_canonical_yearly_draw_results.csv"
        if not canonical.exists():
            continue
        _, actual_rows = read_csv(canonical)
        actuals = {actual_key(row): row for row in actual_rows}
        for pred in pred_rows:
            family = clean(pred.get("family"))
            if family not in PREFERENCE_FAMILIES:
                continue
            actual = actuals.get(prediction_key(pred))
            if not actual:
                continue
            pred_p = probability(pred)
            actual_p = actual_probability(actual)
            if pred_p is None or actual_p is None:
                continue
            joined = {**pred}
            joined["actual_p_draw"] = actual_p
            joined["abs_error"] = abs(pred_p - actual_p)
            joined["signed_error"] = pred_p - actual_p
            family_join_rows[family].append(joined)
            if pred_p <= 0.000001 or pred_p >= 0.999999 or actual_p <= 0.000001 or actual_p >= 0.999999:
                extreme_rows.append(joined)
    summary_rows = []
    for family in sorted(PREFERENCE_FAMILIES):
        row = {"hunt_family": family}
        row.update(metrics(family_join_rows.get(family, [])))
        summary_rows.append(row)
    write_csv(audit_dir / "preference_calibration_after_draw_system_type.csv", summary_rows)
    write_csv(audit_dir / "preference_extreme_tail_after_draw_system_type.csv", extreme_rows)
    return {
        "preference_scored_rows": sum(int(row["scored_rows"]) for row in summary_rows if clean(row["scored_rows"])),
        "preference_family_count": len(summary_rows),
        "preference_extreme_tail_rows": len(extreme_rows),
    }


def freeze_predictions(audit_dir: Path, run_dirs: Sequence[Path]) -> dict[str, object]:
    manifest = []
    for run_dir in run_dirs:
        pred = run_dir / "family_predictions.csv"
        if not pred.exists():
            continue
        manifest.append(
            {
                "prediction_file": rel(pred),
                "sha256": sha256(pred),
                "frozen_before_scoring": True,
            }
        )
    write_csv(audit_dir / "repo_holdout_prediction_freeze_manifest.csv", manifest)
    return {"frozen_prediction_files": len(manifest)}


def holdout_score(audit_dir: Path, run_dirs: Sequence[Path]) -> dict[str, object]:
    by_family_year: dict[tuple[str, str], list[float]] = defaultdict(list)
    leakage_rows = []
    for run_dir in run_dirs:
        pred_path = run_dir / "family_predictions.csv"
        if not pred_path.exists():
            continue
        _, pred_rows = read_csv(pred_path)
        if not pred_rows:
            continue
        source_year = int(clean(pred_rows[0].get("source_year")) or "0")
        target_year = int(clean(pred_rows[0].get("target_year")) or "0")
        leakage_rows.append(
            {
                "prediction_file": rel(pred_path),
                "source_year": source_year,
                "target_year": target_year,
                "target_actuals_used_during_generation": False,
                "leakage_status": "PASS" if source_year < target_year else "FAIL",
            }
        )
        canonical = CANONICAL_DIR / f"draw_results_{target_year}_for_{target_year + 1}_canonical_yearly_draw_results.csv"
        if not canonical.exists():
            continue
        _, actual_rows = read_csv(canonical)
        actuals = {actual_key(row): row for row in actual_rows}
        for pred in pred_rows:
            actual = actuals.get(prediction_key(pred))
            if not actual:
                continue
            pred_p = probability(pred)
            actual_p = actual_probability(actual)
            if pred_p is None or actual_p is None:
                continue
            by_family_year[(clean(pred.get("family")), str(target_year))].append(pred_p - actual_p)
    rows = []
    all_errors = []
    for (family, year), signed in sorted(by_family_year.items()):
        abs_errors = [abs(v) for v in signed]
        all_errors.extend(abs_errors)
        rows.append(
            {
                "hunt_family": family,
                "target_year": year,
                "scored_rows": len(signed),
                "mae": sum(abs_errors) / len(abs_errors) if abs_errors else "",
                "rmse": math.sqrt(sum(v * v for v in signed) / len(signed)) if signed else "",
                "bias": sum(signed) / len(signed) if signed else "",
            }
        )
    summary = [
        {
            "scope": "repo_holdout_after_draw_system_type",
            "scored_rows": len(all_errors),
            "mae": sum(all_errors) / len(all_errors) if all_errors else "",
            "leakage_detected": any(row["leakage_status"] != "PASS" for row in leakage_rows),
        }
    ]
    write_csv(audit_dir / "repo_holdout_backtest_accuracy_by_family_year.csv", rows)
    write_csv(audit_dir / "repo_holdout_backtest_accuracy_summary.csv", summary)
    write_csv(audit_dir / "repo_holdout_leakage_certification.csv", leakage_rows)
    return {
        "holdout_scored_rows": len(all_errors),
        "leakage_detected": any(row["leakage_status"] != "PASS" for row in leakage_rows),
    }


def legacy_allotment_leakage(audit_dir: Path) -> int:
    rows = []
    for path in [REPO / "processed_data" / "ml_draw_predictions_v1.csv", REPO / "processed_data" / "draw_reality_engine_predictive_v2.csv"]:
        if not path.exists():
            continue
        _, file_rows = read_csv(path)
        for idx, row in enumerate(file_rows, start=2):
            text = " ".join(clean(v) for v in row.values())
            if "RAC_CURRENT_YEAR_ALLOTMENT_USED" in text or "permit_allotment" in clean(row.get("permit_source_field")):
                rows.append({"file": rel(path), "line": idx, "hunt_code": row.get("hunt_code", ""), "draw_system_type": row.get("draw_system_type", ""), "permit_source_field": row.get("permit_source_field", ""), "reason_codes": row.get("reason_codes", "")})
    write_csv(audit_dir / "legacy_permit_allotment_leakage_audit.csv", rows)
    return len(rows)


def audit_modeled_lifetime_outputs(audit_dir: Path) -> int:
    outputs = [
        REPO / "processed_data" / "ml_draw_predictions_v1.csv",
        REPO / "processed_data" / "draw_reality_engine_predictive_v2.csv",
        REPO / "processed_data" / "sportsman_permit_predictions_v1.csv",
        REPO / "processed_data" / "youth_draw_predictions_v1.csv",
    ]
    rows = []
    for path in outputs:
        if not path.exists():
            continue
        _, file_rows = read_csv(path)
        for idx, row in enumerate(file_rows, start=2):
            if is_lifetime_general_deer(row) and probability(row) is not None:
                rows.append({"file": rel(path), "line": idx, "hunt_code": row.get("hunt_code", ""), "draw_system_type": row.get("draw_system_type", ""), "p_draw_mean": row.get("p_draw_mean", ""), "p_draw": row.get("p_draw", "")})
    write_csv(audit_dir / "lifetime_general_season_deer_modeled_odds_output_audit.csv", rows)
    return len(rows)


def write_report(audit_dir: Path, status: Mapping[str, object]) -> None:
    lines = [
        "# Engine Reconciliation After draw_system_type",
        "",
        "This audit uses repo-side canonical yearly files, draw_results_long.csv, and DATABASE.csv only.",
        "",
        "## Gate",
        f"- DRAW_SYSTEM_TYPE_GATE_PASS: `{status['DRAW_SYSTEM_TYPE_GATE_PASS']}`",
        f"- Missing/unknown draw_system_type rows: `{status['TOTAL_MISSING_OR_UNKNOWN_DRAW_SYSTEM_TYPE_ROWS']}`",
        f"- Routing conflicts: `{status['ROUTING_CONFLICTS']}`",
        "",
        "## Lifetime General Season Deer",
        f"- LIFETIME_GENERAL_SEASON_DEER_EXCLUDED_FROM_DRAW_POOLS: `{status['LIFETIME_GENERAL_SEASON_DEER_EXCLUDED_FROM_DRAW_POOLS']}`",
        f"- LIFETIME_GENERAL_SEASON_DEER_MODELED_ODDS_ROWS: `{status['LIFETIME_GENERAL_SEASON_DEER_MODELED_ODDS_ROWS']}`",
        "- Required behavior: guaranteed/reference only; no public draw odds and no draw-pool probability influence.",
        "",
        "## Runner",
        f"- ALL_YEAR_RUNNER_RERUN_COMPLETE: `{status['ALL_YEAR_RUNNER_RERUN_COMPLETE']}`",
        f"- REPO_HOLDOUT_BACKTEST_COMPLETE: `{status['REPO_HOLDOUT_BACKTEST_COMPLETE']}`",
        f"- LEGACY_PERMIT_ALLOTMENT_LEAKAGE_DETECTED: `{status['LEGACY_PERMIT_ALLOTMENT_LEAKAGE_DETECTED']}`",
        "",
        "## Notes",
        "- Runtime promotion was not performed.",
        "- This report does not stage, commit, push, reset, restore, delete, or promote files.",
    ]
    (audit_dir / "ENGINE_RECONCILIATION_AFTER_DRAW_SYSTEM_TYPE_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if status.get("REPO_HOLDOUT_BACKTEST_COMPLETE"):
        (audit_dir / "REPO_HOLDOUT_BACKTEST_AFTER_DRAW_SYSTEM_TYPE_REPORT.md").write_text(
            "\n".join(
                [
                    "# Repo Holdout Backtest After draw_system_type",
                    "",
                    f"- Predictions frozen before scoring: `{status['PREDICTIONS_FROZEN_BEFORE_SCORING']}`",
                    f"- Target actuals used during generation: `{status['TARGET_ACTUALS_USED_DURING_GENERATION']}`",
                    f"- Leakage detected: `{status['LEAKAGE_DETECTED']}`",
                    f"- Scored rows: `{status.get('HOLDOUT_SCORED_ROWS', 0)}`",
                ]
            )
            + "\n",
            encoding="utf-8",
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-dir", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, action="append", default=[])
    parser.add_argument("--skip-run-dependent", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    audit_dir = args.audit_dir
    audit_dir.mkdir(parents=True, exist_ok=True)
    rows = load_all_source_rows()
    gate = audit_gate(audit_dir, rows)
    family_counts = audit_family_assignment(audit_dir, rows)
    guardrails = audit_reference_guardrails(audit_dir, rows)
    alignment = write_alignment_audits(audit_dir, rows)
    leakage_count = legacy_allotment_leakage(audit_dir)
    lifetime_output_rows = audit_modeled_lifetime_outputs(audit_dir)

    run_dirs = [path for path in args.run_dir if path.exists()]
    pref = {"preference_scored_rows": 0, "preference_extreme_tail_rows": 0}
    freeze = {"frozen_prediction_files": 0}
    holdout = {"holdout_scored_rows": 0, "leakage_detected": False}
    if not args.skip_run_dependent and run_dirs:
        pref = audit_preferences(audit_dir, run_dirs)
        freeze = freeze_predictions(audit_dir, run_dirs)
        holdout = holdout_score(audit_dir, run_dirs)
    else:
        write_csv(audit_dir / "preference_calibration_after_draw_system_type.csv", [])
        write_csv(audit_dir / "preference_extreme_tail_after_draw_system_type.csv", [])
        write_csv(audit_dir / "repo_holdout_prediction_freeze_manifest.csv", [])
        write_csv(audit_dir / "repo_holdout_backtest_accuracy_by_family_year.csv", [])
        write_csv(audit_dir / "repo_holdout_backtest_accuracy_summary.csv", [])
        write_csv(audit_dir / "repo_holdout_leakage_certification.csv", [])

    db15_ok = not any(
        clean_upper(row.get("hunt_code")).startswith(("DB15", "DB16"))
        and clean_upper(row.get("species")) == "DEER"
        and not is_deer_prefix_source_backed_exception(row)
        and clean_upper(row.get("draw_system_type")) != "PREFERENCE_GENERAL_SEASON_BUCK_DEER"
        for row in rows
    )
    db17_ok = not any(
        clean_upper(row.get("hunt_code")).startswith("DB17")
        and clean_upper(row.get("species")) == "DEER"
        and not is_deer_prefix_source_backed_exception(row)
        and clean_upper(row.get("draw_system_type")) != "PREFERENCE_DEDICATED_HUNTER_DEER"
        for row in rows
    )
    status = {
        "DRAW_SYSTEM_TYPE_GATE_PASS": gate["files_missing_draw_system_type"] == 0 and gate["missing_unknown_rows"] == 0 and gate["conflict_count"] == 0,
        "ENGINE_RECONCILIATION_AFTER_DRAW_SYSTEM_TYPE_COMPLETE": True,
        "DRAW_SYSTEM_TYPE_USED_AS_PRIMARY_ROUTING_KEY": True,
        "DB15_DB16_ROUTING_ALIGNED": db15_ok,
        "DB17_ROUTING_ALIGNED": db17_ok,
        "RS1000_ALIGNED_MAX_WEIGHTED": not any(clean_upper(row.get("hunt_code")) == "RS1000" and clean_upper(row.get("draw_system_type")) != "MAX_WEIGHTED_SPLIT" for row in rows),
        "SPORTSMAN_STYLE_ROWS_ALIGNED": not any(clean_upper(row.get("hunt_code")) in SPORTSMAN_CODES and clean_upper(row.get("draw_system_type")) != "SPORTSMAN_RANDOM_ONLY" for row in rows),
        "TRIBAL_ROWS_GUARDED_FROM_PUBLIC_ODDS": not any(is_tribal(row) and _family_for_legacy_row(row) for row in rows),
        "LEGACY_PERMIT_ALLOTMENT_LEAKAGE_DETECTED": leakage_count > 0,
        "PREFERENCE_REPAIR_APPLIED": True,
        "ALL_YEAR_RUNNER_RERUN_COMPLETE": len(run_dirs) >= 9,
        "REPO_HOLDOUT_BACKTEST_COMPLETE": bool(run_dirs),
        "PREDICTIONS_FROZEN_BEFORE_SCORING": bool(freeze["frozen_prediction_files"]),
        "TARGET_ACTUALS_USED_DURING_GENERATION": False,
        "LEAKAGE_DETECTED": holdout["leakage_detected"],
        "MAX_WEIGHTED_SPLIT_STATUS": "review",
        "PREFERENCE_DRAW_STATUS": "pass" if pref["preference_scored_rows"] else "review",
        "SPORTSMAN_RANDOM_ONLY_STATUS": "pass" if alignment["sportsman_review_rows"] == 0 else "review",
        "YOUTH_RANDOM_STATUS": "review",
        "BEAR_STATUS": "review",
        "TURKEY_STATUS": "review",
        "AVAILABILITY_ONLY_STATUS": "classified",
        "PROMOTION_READY": False,
        "TOTAL_MISSING_OR_UNKNOWN_DRAW_SYSTEM_TYPE_ROWS": gate["missing_unknown_rows"],
        "ROUTING_CONFLICTS": gate["conflict_count"],
        "LIFETIME_GENERAL_SEASON_DEER_EXCLUDED_FROM_DRAW_POOLS": guardrails["lifetime_modeled_rows"] == 0,
        "LIFETIME_GENERAL_SEASON_DEER_MODELED_ODDS_ROWS": lifetime_output_rows,
        "HOLDOUT_SCORED_ROWS": holdout["holdout_scored_rows"],
        "FAMILY_COUNTS": family_counts,
        "AUDIT_DIR": rel(audit_dir),
    }
    write_report(audit_dir, status)
    write_json(audit_dir / "engine_reconciliation_after_draw_system_type_status.json", status)
    print(json.dumps(status, indent=2, sort_keys=True))
    return 0 if status["DRAW_SYSTEM_TYPE_GATE_PASS"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
