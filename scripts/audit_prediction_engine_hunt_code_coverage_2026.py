from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from engine.utah_draw_predictive.classifier import classify_runtime_row

DATABASE = REPO / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
PROCESSED = REPO / "processed_data"

PREDICTION_SURFACES = [
    PROCESSED / "ml_draw_predictions_v1.csv",
    PROCESSED / "sportsman_permit_predictions_v1.csv",
    PROCESSED / "youth_draw_predictions_v1.csv",
    PROCESSED / "bear_draw_predictions_v1.csv",
    PROCESSED / "turkey_bonus_predictions_v1.csv",
    PROCESSED / "youth_turkey_predictions_v1.csv",
    PROCESSED / "phase6_bonus_special_predictions_v1.csv",
    PROCESSED / "dedicated_hunter_predictions_v1.csv",
    PROCESSED / "mountain_lion_availability_predictions_v1.csv",
    PROCESSED / "private_lands_antlerless_elk_predictions_v1.csv",
]

PUBLIC_PROBABILITY_STATUSES = {
    "MODELED_BONUS",
    "MODELED_PREFERENCE",
    "MODELED_RANDOM_ONLY",
    "MODELED_SPORTSMAN_DRAW",
}

ACCOUNTED_NO_PUBLIC_ODDS_STATUSES = {
    "MODELED_ALLOCATION",
    "MODELED_AVAILABILITY",
    "EXCLUDED_NOT_PREDICTIVE_DRAW",
    "OUT_OF_SCOPE_NON_TARGET",
}

ACCOUNTED_NO_PUBLIC_TEXT = (
    "conservation",
    "expo",
    "cwmu",
    "contact operator",
    "private land only",
    "landowner",
    "mitigation",
    "depredation",
    "remaining permit",
    "over the counter",
    "otc",
    "harvest objective",
    "unlimited pursuit",
)

DRAW_SYSTEM_ALIASES = {
    "YOUTH_DRAW_ONLY_ELK": "YOUTH_GENERAL_ANY_BULL_ELK",
    "YOUTH_RANDOM_ELK_GENERAL_BULL": "YOUTH_GENERAL_ANY_BULL_ELK",
    "SPORTSMAN_RANDOM_ONLY": "SPORTSMAN_PERMIT",
}


def clean(value: object) -> str:
    text = str(value or "").strip()
    return "" if text.lower() == "nan" else text


def norm_draw_system(value: object) -> str:
    text = clean(value)
    return DRAW_SYSTEM_ALIASES.get(text, text)


def to_int(value: object) -> int | None:
    text = clean(value).replace(",", "")
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def joined_text(row: Mapping[str, object]) -> str:
    return " ".join(
        clean(row.get(key)).lower()
        for key in (
            "hunt_code",
            "hunt_name",
            "species",
            "sex_type",
            "weapon",
            "hunt_type",
            "hunt_class",
            "season",
            "NOTES",
            "permit_allotment_2026_status",
            "permits_2026_status",
        )
        if clean(row.get(key))
    )


def db_classification(row: Mapping[str, object]) -> dict[str, object]:
    working = dict(row)
    working["source_dataset"] = "predictive"
    if clean(working.get("draw_2026_system_type")) and not clean(working.get("draw_system_type")):
        working["draw_system_type"] = norm_draw_system(working.get("draw_2026_system_type"))
    classification = classify_runtime_row(working)
    classification["draw_system_type"] = norm_draw_system(classification["draw_system_type"])
    return classification


def prediction_index() -> dict[str, dict[str, object]]:
    by_code: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "prediction_rows": 0,
            "prediction_sources": set(),
            "draw_system_types": Counter(),
            "algorithm_statuses": Counter(),
            "residencies": set(),
            "points": set(),
            "p_draw_nonnull_rows": 0,
            "p_draw_zero_rows": 0,
            "p_draw_one_rows": 0,
            "sample_display_odds_text": "",
            "sample_reason_codes": "",
            "sample_model_strategy": "",
            "sample_engine_reason": "",
        }
    )
    for path in PREDICTION_SURFACES:
        for row in read_csv(path):
            code = clean(row.get("hunt_code")).upper()
            if not code:
                continue
            item = by_code[code]
            item["prediction_rows"] += 1
            item["prediction_sources"].add(path.name)
            item["draw_system_types"][norm_draw_system(row.get("draw_system_type"))] += 1
            item["algorithm_statuses"][clean(row.get("algorithm_status"))] += 1
            if clean(row.get("residency")):
                item["residencies"].add(clean(row.get("residency")))
            if clean(row.get("points")):
                item["points"].add(clean(row.get("points")))
            p_draw = clean(row.get("p_draw") or row.get("p_draw_mean") or row.get("p_sportsman_draw"))
            if p_draw:
                item["p_draw_nonnull_rows"] += 1
                try:
                    p_value = float(p_draw)
                except ValueError:
                    p_value = None
                if p_value == 0:
                    item["p_draw_zero_rows"] += 1
                if p_value == 1:
                    item["p_draw_one_rows"] += 1
            for source_key, dest_key in (
                ("display_odds_text", "sample_display_odds_text"),
                ("reason_codes", "sample_reason_codes"),
                ("model_strategy", "sample_model_strategy"),
                ("reason", "sample_engine_reason"),
            ):
                if not item[dest_key] and clean(row.get(source_key)):
                    item[dest_key] = clean(row.get(source_key))
    return by_code


def dominant(counter: Counter[str]) -> str:
    if not counter:
        return ""
    return counter.most_common(1)[0][0]


def decide_outcome(db_row: Mapping[str, object], classification: Mapping[str, object], pred: Mapping[str, object] | None) -> tuple[str, str, str]:
    text = joined_text(db_row)
    total = to_int(db_row.get("permits_2026_total"))
    res = to_int(db_row.get("permits_2026_res"))
    nr = to_int(db_row.get("permits_2026_nr"))
    has_permit_authority = any(value is not None for value in (total, res, nr))
    no_quota_status = any(
        token in text
        for token in (
            "no_quota_published",
            "no permit data",
            "not published",
            "no published",
            "source_confirmed_no_quota",
        )
    )
    non_public_text = any(token in text for token in ACCOUNTED_NO_PUBLIC_TEXT)
    db_status = clean(classification.get("algorithm_status"))
    pred_statuses = set((pred or {}).get("algorithm_statuses", Counter()).keys())
    p_rows = int((pred or {}).get("p_draw_nonnull_rows", 0))
    prediction_rows = int((pred or {}).get("prediction_rows", 0))

    if p_rows > 0 and (pred_statuses & PUBLIC_PROBABILITY_STATUSES):
        return "MODELED_PUBLIC_P_DRAW", "engine_output_present", "Public probability rows are present."
    if prediction_rows > 0 and pred_statuses <= ACCOUNTED_NO_PUBLIC_ODDS_STATUSES:
        return "ACCOUNTED_NO_PUBLIC_P_DRAW", "non_probability_engine_surface", "Rows are represented by availability/allocation/exclusion logic."
    if prediction_rows > 0 and "IN_SCOPE_MODEL_PENDING" in pred_statuses:
        if not has_permit_authority:
            return (
                "ACCOUNTED_NO_PUBLIC_P_DRAW",
                "pending_row_has_no_2026_permit_authority",
                "Prediction surface contains pending rows, but DATABASE has no 2026 permit authority for this hunt code.",
            )
        if total == 0 or no_quota_status or non_public_text:
            return "ACCOUNTED_NO_PUBLIC_P_DRAW", "pending_is_no_public_or_zero_quota", "Pending rows align with no-public/zero-quota/non-public permit semantics."
        return "ENGINE_INPUT_REVIEW_REQUIRED", "pending_prediction_rows", "In-scope rows exist but at least one lane is pending."
    if db_status in ACCOUNTED_NO_PUBLIC_ODDS_STATUSES:
        return "ACCOUNTED_NO_PUBLIC_P_DRAW", "database_classified_non_probability", clean(classification.get("reason"))
    if total == 0:
        return "ACCOUNTED_NO_PUBLIC_P_DRAW", "zero_permit_authority", "2026 published total is zero; no public draw probability should be emitted."
    if not has_permit_authority and prediction_rows == 0:
        return (
            "ACCOUNTED_NO_PUBLIC_P_DRAW",
            "no_2026_permit_authority_or_historical_reference",
            "No 2026 permit authority and no active prediction row; retained as historical/reference until DWR publishes an active permit row.",
        )
    if no_quota_status or (non_public_text and not has_permit_authority):
        return "ACCOUNTED_NO_PUBLIC_P_DRAW", "no_published_or_non_public_authority", "Source semantics indicate no public draw odds or no published quota."
    if non_public_text and clean(db_row.get("hunt_type")).lower() in {"conservation", "expo", "cwmu"}:
        return "ACCOUNTED_NO_PUBLIC_P_DRAW", "special_or_cwmu_not_public_odds", "Special permit/CWMU rows are not public draw odds."
    if clean(classification.get("target_scope")) != "TARGET":
        return "ACCOUNTED_OUT_OF_SCOPE", "non_target_species_or_document", clean(classification.get("reason"))
    return "NO_ENGINE_OUTPUT_REVIEW_REQUIRED", "active_target_missing_output", "Target-scope hunt code has no prediction/accounting row."


def main() -> None:
    db_rows = read_csv(DATABASE)
    pred_by_code = prediction_index()
    out_rows: list[dict[str, object]] = []
    for row in db_rows:
        code = clean(row.get("hunt_code")).upper()
        classification = db_classification(row)
        pred = pred_by_code.get(code)
        outcome, reason_code, reason = decide_outcome(row, classification, pred)
        pred_statuses = (pred or {}).get("algorithm_statuses", Counter())
        pred_families = (pred or {}).get("draw_system_types", Counter())
        out_rows.append(
            {
                "hunt_code": code,
                "hunt_name": clean(row.get("hunt_name")),
                "species": clean(row.get("species")),
                "sex_type": clean(row.get("sex_type")),
                "weapon": clean(row.get("weapon")),
                "hunt_type": clean(row.get("hunt_type")),
                "hunt_class": clean(row.get("hunt_class")),
                "db_draw_system_type": norm_draw_system(row.get("draw_2026_system_type")),
                "classified_draw_system_type": clean(classification.get("draw_system_type")),
                "classified_algorithm_status": clean(classification.get("algorithm_status")),
                "classified_target_scope": clean(classification.get("target_scope")),
                "permits_2026_res": clean(row.get("permits_2026_res")),
                "permits_2026_nr": clean(row.get("permits_2026_nr")),
                "permits_2026_total": clean(row.get("permits_2026_total")),
                "permits_2026_source": clean(row.get("permits_2026_source")),
                "permit_allotment_2026_status": clean(row.get("permit_allotment_2026_status")),
                "engine_outcome": outcome,
                "engine_reconciliation_reason_code": reason_code,
                "engine_reconciliation_reason": reason,
                "prediction_row_count": int((pred or {}).get("prediction_rows", 0)),
                "prediction_p_draw_row_count": int((pred or {}).get("p_draw_nonnull_rows", 0)),
                "prediction_zero_p_draw_row_count": int((pred or {}).get("p_draw_zero_rows", 0)),
                "prediction_one_p_draw_row_count": int((pred or {}).get("p_draw_one_rows", 0)),
                "prediction_draw_system_types": "|".join(f"{k}:{v}" for k, v in sorted(pred_families.items())),
                "prediction_algorithm_statuses": "|".join(f"{k}:{v}" for k, v in sorted(pred_statuses.items())),
                "prediction_residencies": "|".join(sorted((pred or {}).get("residencies", set()))),
                "prediction_points": "|".join(sorted((pred or {}).get("points", set()), key=lambda value: int(value) if value.isdigit() else 999)),
                "prediction_sources": "|".join(sorted((pred or {}).get("prediction_sources", set()))),
                "sample_display_odds_text": (pred or {}).get("sample_display_odds_text", ""),
                "sample_model_strategy": (pred or {}).get("sample_model_strategy", ""),
                "sample_reason_codes": (pred or {}).get("sample_reason_codes", ""),
                "sample_engine_reason": (pred or {}).get("sample_engine_reason", ""),
            }
        )

    fields = list(out_rows[0].keys()) if out_rows else []
    detail_path = PROCESSED / "prediction_engine_hunt_code_line_audit_2026.csv"
    write_csv(detail_path, out_rows, fields)

    unmodeled_rows = [
        row
        for row in out_rows
        if row["engine_outcome"] in {"ENGINE_INPUT_REVIEW_REQUIRED", "NO_ENGINE_OUTPUT_REVIEW_REQUIRED"}
    ]
    unmodeled_path = PROCESSED / "prediction_engine_unmodeled_review_required_2026.csv"
    write_csv(unmodeled_path, unmodeled_rows, fields)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "database_rows": len(db_rows),
        "database_hunt_codes": len({clean(row.get("hunt_code")).upper() for row in db_rows if clean(row.get("hunt_code"))}),
        "prediction_surface_files_seen": [str(path.relative_to(REPO)) for path in PREDICTION_SURFACES if path.exists()],
        "engine_outcome_counts": dict(Counter(row["engine_outcome"] for row in out_rows)),
        "review_required_count": len(unmodeled_rows),
        "review_required_by_draw_system_type": dict(Counter(row["classified_draw_system_type"] for row in unmodeled_rows)),
        "review_required_by_reason_code": dict(Counter(row["engine_reconciliation_reason_code"] for row in unmodeled_rows)),
        "modeled_public_p_draw_hunt_codes": sum(1 for row in out_rows if row["engine_outcome"] == "MODELED_PUBLIC_P_DRAW"),
        "accounted_no_public_p_draw_hunt_codes": sum(1 for row in out_rows if row["engine_outcome"] == "ACCOUNTED_NO_PUBLIC_P_DRAW"),
        "accounted_out_of_scope_hunt_codes": sum(1 for row in out_rows if row["engine_outcome"] == "ACCOUNTED_OUT_OF_SCOPE"),
        "detail_csv": str(detail_path.relative_to(REPO)),
        "unmodeled_review_csv": str(unmodeled_path.relative_to(REPO)),
    }
    summary_path = PROCESSED / "prediction_engine_hunt_code_line_audit_2026_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    md = [
        "# Prediction Engine Hunt-Code Line Audit 2026",
        "",
        f"Generated: {summary['generated_at_utc']}",
        "",
        "## Outcome Counts",
        "",
    ]
    for key, value in summary["engine_outcome_counts"].items():
        md.append(f"- {key}: {value}")
    md.extend(
        [
            "",
            f"Review required: {summary['review_required_count']}",
            f"Detail CSV: `{summary['detail_csv']}`",
            f"Review CSV: `{summary['unmodeled_review_csv']}`",
            "",
            "## Review Required By Family",
            "",
        ]
    )
    for key, value in summary["review_required_by_draw_system_type"].items():
        md.append(f"- {key or '(blank)'}: {value}")
    (PROCESSED / "prediction_engine_hunt_code_line_audit_2026.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
