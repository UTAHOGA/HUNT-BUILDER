from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine.utah_bonus_predictive.materialize import expand_collapsed_truth_rows_for_engine
from engine.utah_draw_predictive.preference_antlerless import (
    build_preference_antlerless_predictions,
)


CANONICAL_YEARLY_DIR = REPO_ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"
DRAW_RESULTS_LONG = REPO_ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
DATABASE_CSV = REPO_ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
OUTPUT_DIR = REPO_ROOT / "processed_data"

YEAR_RE = re.compile(r"draw_results_(\d{4})_for_(\d{4})_canonical_yearly_draw_results\.csv$", re.I)


def clean(value: object) -> str:
    return str(value or "").strip()


def clean_lower(value: object) -> str:
    return clean(value).lower()


def to_int(value: object) -> int:
    text = clean(value)
    if not text:
        return 0
    try:
        return int(float(text))
    except Exception:
        return 0


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def actual_year(row: dict[str, object], fallback_year: int | None = None) -> int:
    for key in ("actual_draw_year", "draw_year", "year"):
        year = to_int(row.get(key))
        if year:
            return year
    return fallback_year or 0


def target_draw_system_type(row: dict[str, object]) -> str | None:
    text = " ".join(
        clean_lower(row.get(key))
        for key in ("hunt_name", "species", "sex_type", "hunt_type", "hunt_class", "weapon", "draw_pool", "draw_design")
    )
    if any(
        token in text
        for token in (
            "youth",
            "cwmu",
            "dedicated hunter",
            "private land",
            "landowner",
            "conservation",
            "control",
            "mitigation",
            "depredation",
            "sportsman",
            "expo",
        )
    ):
        return None
    sex = clean_lower(row.get("sex_type"))
    if "pronghorn" in text and ("doe" in text or sex in {"antlerless", "doe"}):
        return "PREFERENCE_DOE_PRONGHORN"
    if "deer" in text and ("antlerless" in text or sex in {"antlerless", "doe"}):
        return "PREFERENCE_ANTLERLESS_DEER"
    if "elk" in text and ("antlerless" in text or sex in {"antlerless", "cow", "cow only"}):
        return "PREFERENCE_ANTLERLESS_ELK"
    return None


def looks_like_standard_pool(row: dict[str, object]) -> bool:
    draw_pool = clean_lower(row.get("draw_pool"))
    hunt_class = clean_lower(row.get("hunt_class"))
    draw_design = clean_lower(row.get("draw_design"))
    return draw_pool in {"", "standard"} and hunt_class in {"", "adult", "public", "preference"} and draw_design in {"", "preference"}


def is_antlerless_engine_truth(row: dict[str, object]) -> bool:
    return bool(target_draw_system_type(row)) and looks_like_standard_pool(row) and bool(clean(row.get("hunt_code")))


def row_key(row: dict[str, object], fallback_year: int | None = None) -> tuple[int, str, str, str, str, str]:
    return (
        actual_year(row, fallback_year),
        target_draw_system_type(row) or "",
        clean(row.get("hunt_code")).upper(),
        clean(row.get("residency")) or "UNSPECIFIED",
        clean(row.get("points")),
        clean(row.get("draw_pool")) or "standard",
    )


def summarize_codes(rows: list[dict[str, object]], fallback_year: int | None = None) -> dict[int, set[str]]:
    out: dict[int, set[str]] = defaultdict(set)
    for row in rows:
        if is_antlerless_engine_truth(row):
            out[actual_year(row, fallback_year)].add(clean(row.get("hunt_code")).upper())
    return out


def main() -> None:
    canonical_files = sorted(CANONICAL_YEARLY_DIR.glob("draw_results_*_canonical_yearly_draw_results.csv"))
    canonical_rows_by_year: dict[int, list[dict[str, object]]] = {}
    for path in canonical_files:
        match = YEAR_RE.match(path.name)
        if not match:
            continue
        draw_year = int(match.group(1))
        rows = read_csv(path)
        canonical_rows_by_year[draw_year] = rows

    long_rows_raw = read_csv(DRAW_RESULTS_LONG)
    long_rows = expand_collapsed_truth_rows_for_engine(long_rows_raw)
    db_rows = read_csv(DATABASE_CSV)

    canonical_code_sets = {
        year: {clean(row.get("hunt_code")).upper() for row in rows if is_antlerless_engine_truth(row)}
        for year, rows in canonical_rows_by_year.items()
    }
    long_code_sets = summarize_codes(long_rows)

    yearly_rows: list[dict[str, object]] = []
    yearly_detail_rows: list[dict[str, object]] = []
    for year in sorted(canonical_rows_by_year):
        canonical_engine_rows = [row for row in canonical_rows_by_year[year] if is_antlerless_engine_truth(row)]
        long_engine_rows = [row for row in long_rows if actual_year(row) == year and is_antlerless_engine_truth(row)]
        canonical_codes = canonical_code_sets.get(year, set())
        long_codes = long_code_sets.get(year, set())
        missing_in_long = sorted(canonical_codes - long_codes)
        extra_in_long = sorted(long_codes - canonical_codes)
        yearly_rows.append(
            {
                "actual_draw_year": year,
                "canonical_engine_rows": len(canonical_engine_rows),
                "canonical_engine_codes": len(canonical_codes),
                "long_engine_rows": len(long_engine_rows),
                "long_engine_codes": len(long_codes),
                "missing_in_long_count": len(missing_in_long),
                "extra_in_long_count": len(extra_in_long),
                "missing_in_long_sample": "|".join(missing_in_long[:30]),
                "extra_in_long_sample": "|".join(extra_in_long[:30]),
            }
        )
        for code in missing_in_long:
            yearly_detail_rows.append({"actual_draw_year": year, "hunt_code": code, "issue": "canonical_code_missing_in_long"})
        for code in extra_in_long:
            yearly_detail_rows.append({"actual_draw_year": year, "hunt_code": code, "issue": "long_code_missing_in_canonical"})

    history_years = [year for year in sorted(canonical_rows_by_year) if year < 2026]
    predictions = build_preference_antlerless_predictions(long_rows, db_rows, 2026, history_years)
    prediction_by_code: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in predictions:
        prediction_by_code[clean(row.get("hunt_code")).upper()].append(row)

    history_years_by_code: dict[str, set[int]] = defaultdict(set)
    history_rows_by_code: Counter[str] = Counter()
    for row in long_rows:
        if is_antlerless_engine_truth(row):
            year = actual_year(row)
            code = clean(row.get("hunt_code")).upper()
            if year < 2026:
                history_years_by_code[code].add(year)
                history_rows_by_code[code] += 1

    current_target_rows = []
    for row in db_rows:
        draw_system_type = target_draw_system_type(row)
        if not draw_system_type or not looks_like_standard_pool(row):
            continue
        code = clean(row.get("hunt_code")).upper()
        if not code:
            continue
        current_target_rows.append((draw_system_type, row))

    current_rows: list[dict[str, object]] = []
    for draw_system_type, row in sorted(current_target_rows, key=lambda item: clean(item[1].get("hunt_code")).upper()):
        code = clean(row.get("hunt_code")).upper()
        pred_rows = prediction_by_code.get(code, [])
        source_years_used = sorted({clean(pred.get("source_years_used")) for pred in pred_rows if clean(pred.get("source_years_used"))})
        model_notes = sorted({clean(pred.get("preference_model_note")) for pred in pred_rows if clean(pred.get("preference_model_note"))})
        same_code_years = sorted(history_years_by_code.get(code, set()))
        current_permit_total = (
            to_int(row.get("permits_2026_total"))
            or to_int(row.get("permits_2026_res"))
            + to_int(row.get("permits_2026_nr"))
        )
        if current_permit_total <= 0:
            outcome = "HOLD_NO_2026_PERMIT_AUTHORITY"
            reason = "historical ladder exists or code is recognized, but current DATABASE has no positive 2026 permit authority"
        elif pred_rows:
            outcome = "MODELED_FROM_LONG_AND_DATABASE"
            reason = "same-code historical ladder available"
        elif same_code_years:
            outcome = "REVIEW_HISTORY_EXISTS_BUT_NOT_MODELED"
            reason = "history exists, but engine guardrails rejected it"
        else:
            outcome = "HOLD_NO_PRIOR_LONG_LADDER"
            reason = "current DB/Hunt Planner quota exists, but draw_results_long has no pre-2026 same-code ladder"
        if "cwmu" in clean_lower(row.get("hunt_name")) or "contact operator" in clean_lower(row.get("season_dates")):
            outcome = "HOLD_CWMU_OR_CONTACT_OPERATOR"
            reason = "CWMU/contact-operator semantics stay out of public p_draw"
        current_rows.append(
            {
                "hunt_code": code,
                "hunt_name": clean(row.get("hunt_name")),
                "species": clean(row.get("species")),
                "sex_type": clean(row.get("sex_type")),
                "weapon": clean(row.get("weapon")),
                "hunt_type": clean(row.get("hunt_type")),
                "hunt_class": clean(row.get("hunt_class")),
                "draw_system_type": draw_system_type,
                "permits_2026_res": clean(row.get("permits_2026_res")),
                "permits_2026_nr": clean(row.get("permits_2026_nr")),
                "permits_2026_total": clean(row.get("permits_2026_total")),
                "same_code_history_years": ",".join(str(year) for year in same_code_years),
                "same_code_history_row_count": history_rows_by_code.get(code, 0),
                "prediction_row_count": len(pred_rows),
                "prediction_residencies": "|".join(sorted({clean(pred.get("residency")) for pred in pred_rows if clean(pred.get("residency"))})),
                "prediction_source_years_used": "|".join(source_years_used),
                "engine_outcome": outcome,
                "engine_reason": reason,
                "model_note_sample": " | ".join(model_notes[:3]),
            }
        )

    summary = {
        "canonical_yearly_files": len(canonical_files),
        "years_seen": sorted(canonical_rows_by_year),
        "draw_results_long_rows": len(long_rows_raw),
        "expanded_long_rows_for_engine": len(long_rows),
        "database_rows": len(db_rows),
        "history_years_used_for_forecast": history_years,
        "current_antlerless_preference_target_codes": len(current_rows),
        "current_modeled_codes": sum(1 for row in current_rows if row["engine_outcome"] == "MODELED_FROM_LONG_AND_DATABASE"),
        "current_hold_no_prior_ladder_codes": sum(1 for row in current_rows if row["engine_outcome"] == "HOLD_NO_PRIOR_LONG_LADDER"),
        "current_hold_no_2026_permit_authority_codes": sum(1 for row in current_rows if row["engine_outcome"] == "HOLD_NO_2026_PERMIT_AUTHORITY"),
        "current_hold_cwmu_contact_codes": sum(1 for row in current_rows if row["engine_outcome"] == "HOLD_CWMU_OR_CONTACT_OPERATOR"),
        "current_review_history_exists_not_modeled_codes": sum(1 for row in current_rows if row["engine_outcome"] == "REVIEW_HISTORY_EXISTS_BUT_NOT_MODELED"),
        "yearly_canonical_vs_long_conflict_count": len(yearly_detail_rows),
    }

    current_fields = [
        "hunt_code",
        "hunt_name",
        "species",
        "sex_type",
        "weapon",
        "hunt_type",
        "hunt_class",
        "draw_system_type",
        "permits_2026_res",
        "permits_2026_nr",
        "permits_2026_total",
        "same_code_history_years",
        "same_code_history_row_count",
        "prediction_row_count",
        "prediction_residencies",
        "prediction_source_years_used",
        "engine_outcome",
        "engine_reason",
        "model_note_sample",
    ]
    yearly_fields = [
        "actual_draw_year",
        "canonical_engine_rows",
        "canonical_engine_codes",
        "long_engine_rows",
        "long_engine_codes",
        "missing_in_long_count",
        "extra_in_long_count",
        "missing_in_long_sample",
        "extra_in_long_sample",
    ]
    detail_fields = ["actual_draw_year", "hunt_code", "issue"]
    write_csv(OUTPUT_DIR / "antlerless_preference_current_code_reconciliation_2026.csv", current_rows, current_fields)
    write_csv(OUTPUT_DIR / "antlerless_preference_yearly_canonical_vs_long_reconciliation.csv", yearly_rows, yearly_fields)
    write_csv(OUTPUT_DIR / "antlerless_preference_yearly_canonical_vs_long_conflicts.csv", yearly_detail_rows, detail_fields)
    (OUTPUT_DIR / "antlerless_preference_yearly_reconciliation_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )

    md_lines = [
        "# Antlerless Preference Yearly Reconciliation",
        "",
        "Source authority: `draw_results_long.csv` plus current `DATABASE.csv`.",
        "",
        f"- Canonical yearly files scanned: {summary['canonical_yearly_files']}",
        f"- Years scanned: {', '.join(str(year) for year in summary['years_seen'])}",
        f"- Current antlerless preference target codes: {summary['current_antlerless_preference_target_codes']}",
        f"- Modeled from long + database: {summary['current_modeled_codes']}",
        f"- Held because no pre-2026 same-code ladder exists: {summary['current_hold_no_prior_ladder_codes']}",
        f"- Held because current DB has no positive 2026 permit authority: {summary['current_hold_no_2026_permit_authority_codes']}",
        f"- Held as CWMU/contact-operator: {summary['current_hold_cwmu_contact_codes']}",
        f"- Review: history exists but guardrails rejected it: {summary['current_review_history_exists_not_modeled_codes']}",
        f"- Canonical-vs-long yearly code conflicts: {summary['yearly_canonical_vs_long_conflict_count']}",
        "",
        "Generated files:",
        "",
        "- `processed_data/antlerless_preference_current_code_reconciliation_2026.csv`",
        "- `processed_data/antlerless_preference_yearly_canonical_vs_long_reconciliation.csv`",
        "- `processed_data/antlerless_preference_yearly_canonical_vs_long_conflicts.csv`",
        "- `processed_data/antlerless_preference_yearly_reconciliation_summary.json`",
    ]
    (OUTPUT_DIR / "antlerless_preference_yearly_reconciliation.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
