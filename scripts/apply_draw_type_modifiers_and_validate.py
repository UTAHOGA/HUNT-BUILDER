import csv
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREDICTIONS = ROOT / "engine_rebuild_from_truth" / "engine" / "prediction_outputs.csv"
ODDS_TABLES = ROOT / "engine_rebuild_from_truth" / "engine" / "odds_tables.csv"
TRUTH = ROOT / "data_truth" / "finalized_point_distribution.csv"
OUT_PREDICTIONS = ROOT / "engine_rebuild_from_truth" / "engine" / "prediction_outputs_with_modifiers.csv"
OUT_ODDS = ROOT / "engine_rebuild_from_truth" / "engine" / "odds_tables_with_modifiers.csv"
AUDIT = ROOT / "audits" / "prediction_validation"


def clean(value):
    return "" if value is None else str(value).strip()


def norm_year(value):
    text = clean(value)
    return text[:-2] if text.endswith(".0") else text


def norm_code(value):
    return clean(value).upper()


def norm_residency(value):
    text = clean(value).lower().replace("-", "").replace("_", "").replace(" ", "")
    if text in {"r", "res", "resident"}:
        return "Resident"
    if text in {"nr", "nonres", "nonresident", "noresident"}:
        return "Nonresident"
    if text == "all":
        return "All"
    return clean(value) or "UNKNOWN_RESIDENCY"


def norm_point(value):
    text = clean(value)
    return text[:-2] if text.endswith(".0") else (text or "UNKNOWN_POINT")


def to_float(value):
    text = clean(value).replace(",", "").replace("%", "")
    if not text or text.upper() == "N/A":
        return None
    try:
        return float(text)
    except Exception:
        return None


def format_probability(value):
    if value is None:
        return ""
    value = max(0.0, min(1.0, float(value)))
    return f"{value:.10f}".rstrip("0").rstrip(".")


def format_percent(value):
    if value is None:
        return ""
    return f"{max(0.0, min(1.0, float(value))) * 100.0:.6f}".rstrip("0").rstrip(".")


def source_scope(source_file, hunt_code=""):
    source = clean(source_file).lower().replace(" ", "_")
    code = norm_code(hunt_code)
    if "youth_antlerless" in source:
        return "YOUTH_ANTLERLESS"
    if "antlerless" in source or "doe_pronghorn" in source:
        return "ADULT_ANTLERLESS"
    if "cougar" in source:
        return "COUGAR"
    if "youth_turkey" in source:
        return "YOUTH_TURKEY"
    if "turkey" in source:
        return "TURKEY"
    if "bear" in source or re.match(r"^20_drawing_odds", source):
        return "BEAR"
    if "youth_bull_elk" in source or "youth_g.s._mature_bull_elk" in source:
        return "YOUTH_BULL_ELK"
    if "youth_d.h" in source or "youth_dh" in source or "youth_dedicated_hunter" in source:
        return "YOUTH_DH_DEER"
    if "d.h" in source or "dh_odds" in source or "dedicated_hunter" in source:
        return "DEDICATED_HUNTER_DEER"
    if "lifetime_g.s" in source or "lifetime_deer" in source:
        return "LIFETIME_GS_DEER"
    if "youth_g.s" in source or "youth_deer" in source:
        return "YOUTH_GS_DEER"
    if "g.s" in source or "general-season" in source or "general_season" in source or "deer_odds" in source:
        return "GENERAL_SEASON_DEER"
    if (
        "bg-odds" in source
        or "bg_odds" in source
        or "limited-entry" in source
        or "limited_entry" in source
        or "l.e." in source
        or "o.i.l" in source
        or "bull_moose" in source
        or "bighorn_sheep" in source
        or "mtn_goat" in source
        or "bison" in source
    ):
        return "BIG_GAME_BONUS"
    if code.startswith("BR"):
        return "BEAR"
    if code.startswith("CG"):
        return "COUGAR"
    if code.startswith("TK"):
        return "TURKEY"
    if code.startswith(("DA", "EA", "MA", "PD")):
        return "ADULT_ANTLERLESS"
    if code.startswith(("DB", "EB", "PB", "BI", "GO", "MB", "DS", "RS")):
        return "BIG_GAME_BONUS"
    return "UNKNOWN_SOURCE_SCOPE"


def hunt_program(scope):
    if scope.startswith("YOUTH_"):
        return "YOUTH"
    if scope.startswith("LIFETIME_"):
        return "LIFETIME"
    if scope == "SPORTSMAN":
        return "SPORTSMAN"
    return "ADULT"


def draw_family(scope):
    return {
        "BIG_GAME_BONUS": "LE_OIL_BIG_GAME_BONUS",
        "ADULT_ANTLERLESS": "ANTLERLESS_PREFERENCE",
        "YOUTH_ANTLERLESS": "YOUTH_ANTLERLESS_PREFERENCE",
        "GENERAL_SEASON_DEER": "GENERAL_SEASON_DEER_PREFERENCE",
        "YOUTH_GS_DEER": "YOUTH_GENERAL_SEASON_DEER_PREFERENCE",
        "LIFETIME_GS_DEER": "LIFETIME_GENERAL_SEASON_DEER_PREFERENCE",
        "DEDICATED_HUNTER_DEER": "DEDICATED_HUNTER_DEER_PREFERENCE",
        "YOUTH_DH_DEER": "YOUTH_DEDICATED_HUNTER_DEER_PREFERENCE",
        "YOUTH_BULL_ELK": "YOUTH_BULL_ELK_BONUS",
        "BEAR": "BEAR_BONUS",
        "COUGAR": "COUGAR_BONUS",
        "TURKEY": "TURKEY_BONUS",
        "YOUTH_TURKEY": "YOUTH_TURKEY_BONUS",
        "SPORTSMAN": "SPORTSMAN_RANDOM_ONLY",
    }.get(scope, "UNKNOWN_DRAW_FAMILY")


def draw_type(scope, method):
    method_upper = clean(method).upper()
    family = draw_family(scope)
    if "SPORTSMAN_RANDOM" in method_upper or family == "SPORTSMAN_RANDOM_ONLY":
        return "RANDOM"
    if "PREFERENCE" in method_upper or family.endswith("_PREFERENCE"):
        return "PREFERENCE"
    if "BONUS" in method_upper or family.endswith("_BONUS") or family == "LE_OIL_BIG_GAME_BONUS":
        return "BONUS"
    return "RANDOM"


def species_from(hunt_code, hunt_name=""):
    code = norm_code(hunt_code)
    haystack = f"{code} {clean(hunt_name)}".upper()
    if code.startswith("BI") or "BISON" in haystack:
        return "BISON"
    if code.startswith("BR") or "BLACK BEAR" in haystack:
        return "BLACK_BEAR"
    if code.startswith("CG") or "COUGAR" in haystack:
        return "COUGAR"
    if code.startswith("TK") or "TURKEY" in haystack:
        return "TURKEY"
    if code.startswith("GO") or "GOAT" in haystack:
        return "MOUNTAIN_GOAT"
    if code.startswith("MB") or "MOOSE" in haystack:
        return "MOOSE"
    if code.startswith("DS") or "DESERT BIGHORN" in haystack:
        return "DESERT_BIGHORN_SHEEP"
    if code.startswith("RS") or ("ROCKY" in haystack and "SHEEP" in haystack):
        return "ROCKY_MOUNTAIN_BIGHORN_SHEEP"
    if code.startswith(("PB", "PD")) or "PRONGHORN" in haystack:
        return "PRONGHORN"
    if code.startswith(("EB", "EA")) or "ELK" in haystack:
        return "ELK"
    if code.startswith(("DB", "DA")) or "DEER" in haystack:
        return "DEER"
    return "UNKNOWN"


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def group_key(row):
    scope = source_scope(row.get("source_file"), row.get("hunt_code"))
    return (
        norm_code(row.get("hunt_code")),
        norm_year(row.get("model_year")),
        norm_residency(row.get("residency")),
        hunt_program(scope),
        draw_family(scope),
        scope,
        clean(row.get("source_file")),
    )


def output_key(row):
    return (
        norm_code(row.get("hunt_code")),
        norm_year(row.get("model_year")),
        norm_residency(row.get("residency")),
        hunt_program(source_scope(row.get("source_file"), row.get("hunt_code"))),
        norm_point(row.get("point_level") or row.get("points")),
        draw_family(source_scope(row.get("source_file"), row.get("hunt_code"))),
    )


def apply_preference_modifier(rows):
    sorted_rows = sorted(rows, key=lambda row: int(float(norm_point(row.get("point_level")))), reverse=True)
    total_permits = sum(to_float(row.get("permits")) or 0.0 for row in sorted_rows)
    remaining = total_permits
    cutoff = ""
    adjusted = {}
    for row in sorted_rows:
        points = norm_point(row.get("point_level"))
        applicants = to_float(row.get("applicants")) or 0.0
        if applicants <= 0:
            adjusted[id(row)] = (None, cutoff, "ZERO_APPLICANTS_UNCHANGED")
            continue
        if remaining >= applicants:
            prob = 0.98
            remaining -= applicants
            status = "PREFERENCE_ABOVE_CUTOFF_HIGH"
        elif remaining > 0:
            raw = remaining / applicants
            prob = max(0.05, min(0.95, raw))
            remaining = 0.0
            cutoff = points
            status = "PREFERENCE_CUTOFF_TRANSITION"
        else:
            prob = 0.02
            status = "PREFERENCE_BELOW_CUTOFF_LOW"
        adjusted[id(row)] = (prob, cutoff or points if status == "PREFERENCE_CUTOFF_TRANSITION" else cutoff, status)
    return adjusted


def apply_bonus_modifier(rows):
    total_permits = max(to_float(rows[0].get("hunt_permits_total")) or 0.0, sum(to_float(row.get("permits")) or 0.0 for row in rows))
    weighted_applicants = 0.0
    for row in rows:
        applicants = to_float(row.get("applicants")) or 0.0
        points = to_float(row.get("point_level")) or 0.0
        weighted_applicants += applicants * (points + 1.0)
    adjusted = {}
    for row in rows:
        applicants = to_float(row.get("applicants")) or 0.0
        if applicants <= 0 or weighted_applicants <= 0 or total_permits <= 0:
            adjusted[id(row)] = (None, "", "ZERO_OR_NO_WEIGHT_UNCHANGED")
            continue
        points = to_float(row.get("point_level")) or 0.0
        prob = min(1.0, total_permits * (points + 1.0) / weighted_applicants)
        adjusted[id(row)] = (prob, "", "BONUS_WEIGHT_POINTS_PLUS_ONE")
    return adjusted


def apply_random_modifier(rows):
    total_permits = max(to_float(rows[0].get("hunt_permits_total")) or 0.0, sum(to_float(row.get("permits")) or 0.0 for row in rows))
    total_applicants = max(to_float(rows[0].get("hunt_applicants_total")) or 0.0, sum(to_float(row.get("applicants")) or 0.0 for row in rows))
    prob = min(1.0, total_permits / total_applicants) if total_applicants > 0 else None
    status = "RANDOM_TOTAL_PERMITS_OVER_TOTAL_APPLICANTS" if prob is not None else "RANDOM_NO_APPLICANTS_UNCHANGED"
    return {id(row): (prob, "", status) for row in rows}


def build_modified_predictions():
    rows = read_csv(PREDICTIONS)
    grouped = defaultdict(list)
    for row in rows:
        grouped[group_key(row)].append(row)

    adjusted_by_id = {}
    for _, group_rows in grouped.items():
        scope = source_scope(group_rows[0].get("source_file"), group_rows[0].get("hunt_code"))
        dtype = draw_type(scope, group_rows[0].get("draw_method"))
        method = clean(group_rows[0].get("draw_method")).upper()
        if "NON_SCORABLE" in method or "UNCLASSIFIED" in method:
            for row in group_rows:
                adjusted_by_id[id(row)] = (None, "", "NON_SCORABLE_OR_UNCLASSIFIED_UNCHANGED")
            continue
        if dtype == "PREFERENCE":
            adjusted_by_id.update(apply_preference_modifier(group_rows))
        elif dtype == "BONUS":
            adjusted_by_id.update(apply_bonus_modifier(group_rows))
        else:
            adjusted_by_id.update(apply_random_modifier(group_rows))

    out_rows = []
    for row in rows:
        scope = source_scope(row.get("source_file"), row.get("hunt_code"))
        family = draw_family(scope)
        dtype = draw_type(scope, row.get("draw_method"))
        original = to_float(row.get("p_draw") or row.get("p_draw_percent"))
        if original is not None and original > 1:
            original /= 100.0
        modified, cutoff, status = adjusted_by_id.get(id(row), (None, "", "NOT_GROUPED"))
        new_row = dict(row)
        new_row["hunt_program"] = hunt_program(scope)
        new_row["source_scope"] = scope
        new_row["draw_family"] = family
        new_row["draw_type"] = dtype
        new_row["p_draw_original"] = format_probability(original)
        new_row["p_draw"] = format_probability(modified)
        new_row["p_draw_percent"] = format_percent(modified)
        new_row["modifier_status"] = status
        new_row["preference_cutoff_point"] = cutoff
        out_rows.append(new_row)

    fields = list(rows[0].keys()) + [
        "hunt_program",
        "source_scope",
        "draw_family",
        "draw_type",
        "p_draw_original",
        "modifier_status",
        "preference_cutoff_point",
    ]
    # p_draw and p_draw_percent already exist in the original field list.
    fields = list(dict.fromkeys(fields))
    write_csv(OUT_PREDICTIONS, out_rows, fields)
    return out_rows


def write_modified_odds(prediction_rows):
    modified_by_source_key = {
        (
            clean(row.get("year")),
            clean(row.get("model_year")),
            norm_code(row.get("hunt_code")),
            norm_residency(row.get("residency")),
            clean(row.get("source_file")),
            norm_point(row.get("point_level")),
        ): row
        for row in prediction_rows
    }
    odds_rows = read_csv(ODDS_TABLES)
    out_rows = []
    for row in odds_rows:
        key = (
            clean(row.get("year")),
            clean(row.get("model_year")),
            norm_code(row.get("hunt_code")),
            norm_residency(row.get("residency")),
            clean(row.get("source_file")),
            norm_point(row.get("point_level")),
        )
        pred = modified_by_source_key.get(key)
        new_row = dict(row)
        if pred:
            new_row["success_rate_original"] = clean(row.get("success_rate"))
            new_row["success_percent_original"] = clean(row.get("success_percent"))
            new_row["success_rate"] = clean(pred.get("p_draw"))
            new_row["success_percent"] = clean(pred.get("p_draw_percent"))
            new_row["draw_type"] = clean(pred.get("draw_type"))
            new_row["draw_family"] = clean(pred.get("draw_family"))
            new_row["hunt_program"] = clean(pred.get("hunt_program"))
            new_row["modifier_status"] = clean(pred.get("modifier_status"))
            new_row["odds_table_source"] = "DRAW_TYPE_MODIFIER_LAYER"
        out_rows.append(new_row)
    fields = list(odds_rows[0].keys()) + [
        "success_rate_original",
        "success_percent_original",
        "draw_type",
        "draw_family",
        "hunt_program",
        "modifier_status",
    ]
    write_csv(OUT_ODDS, out_rows, list(dict.fromkeys(fields)))


def validation_key(row, actual=False):
    scope = source_scope(row.get("source_file"), row.get("hunt_code"))
    return (
        norm_code(row.get("hunt_code")),
        norm_year(row.get("year") if actual else row.get("model_year")),
        norm_residency(row.get("residency")),
        hunt_program(scope),
        norm_point(row.get("point_level") or row.get("points")),
        draw_family(scope),
    )


def metrics(rows):
    if not rows:
        return {"row_count": 0, "mae": "", "rmse": "", "bias": "", "failure_count_abs_error_gt_0_25": 0}
    return {
        "row_count": len(rows),
        "mae": sum(row["abs_error"] for row in rows) / len(rows),
        "rmse": math.sqrt(sum(row["squared_error"] for row in rows) / len(rows)),
        "bias": sum(row["error"] for row in rows) / len(rows),
        "failure_count_abs_error_gt_0_25": sum(1 for row in rows if row["abs_error"] > 0.25),
    }


def group_metrics(rows, columns):
    grouped = defaultdict(list)
    for row in rows:
        grouped[tuple(row.get(column, "") for column in columns)].append(row)
    out = []
    for key, values in sorted(grouped.items(), key=lambda item: (-len(item[1]), str(item[0]))):
        metric = metrics(values)
        for column, value in zip(columns, key):
            metric[column] = value
        out.append(metric)
    return out


def validate(prediction_rows):
    pred_map = {}
    pred_dups = Counter()
    for row in prediction_rows:
        prob = to_float(row.get("p_draw"))
        if prob is None:
            continue
        key = validation_key(row, actual=False)
        pred_dups[key] += 1
        pred_map[key] = row

    actual_map = {}
    actual_dups = Counter()
    zero_excluded = 0
    for row in read_csv(TRUTH):
        applicants = to_float(row.get("applicants"))
        permits = to_float(row.get("permits_total") or row.get("permits"))
        if applicants is None or permits is None:
            continue
        if applicants == 0:
            zero_excluded += 1
            continue
        key = validation_key(row, actual=True)
        actual_dups[key] += 1
        actual_map[key] = row

    duplicate_rows = []
    for dataset, counter in (("prediction", pred_dups), ("actual", actual_dups)):
        for key, count in counter.items():
            if count > 1:
                duplicate_rows.append({"dataset": dataset, "join_key": "|".join(key), "duplicate_count": count})
    write_csv(AUDIT / "prediction_validation_with_modifiers_duplicate_key_audit.csv", duplicate_rows, ["dataset", "join_key", "duplicate_count"])

    if duplicate_rows:
        return {
            "validation_status": "STOPPED_DUPLICATE_KEYS",
            "duplicate_join_key_groups": len(duplicate_rows),
            "metrics_recomputed": False,
        }

    joined = []
    pred_only = []
    actual_only = []
    for key, pred in pred_map.items():
        actual = actual_map.get(key)
        if not actual:
            pred_only.append(pred)
            continue
        pred_prob = to_float(pred.get("p_draw"))
        applicants = to_float(actual.get("applicants"))
        permits = to_float(actual.get("permits_total") or actual.get("permits"))
        actual_prob = permits / applicants
        err = pred_prob - actual_prob
        scope = source_scope(pred.get("source_file"), pred.get("hunt_code"))
        joined.append(
            {
                "hunt_code": key[0],
                "model_year": key[1],
                "residency": key[2],
                "hunt_program": key[3],
                "point_level": key[4],
                "draw_family": key[5],
                "draw_type": clean(pred.get("draw_type")),
                "source_scope": scope,
                "species": species_from(pred.get("hunt_code"), pred.get("hunt_name")),
                "prediction_source_file": clean(pred.get("source_file")),
                "actual_source_file": clean(actual.get("source_file")),
                "predicted_probability": pred_prob,
                "actual_probability": actual_prob,
                "error": err,
                "abs_error": abs(err),
                "squared_error": err * err,
                "point_bucket": "0-2" if (to_float(key[4]) or 0) <= 2 else "3-5" if (to_float(key[4]) or 0) <= 5 else "6-10" if (to_float(key[4]) or 0) <= 10 else "10+",
                "failure_abs_error_gt_0_25": "TRUE" if abs(err) > 0.25 else "FALSE",
            }
        )
    for key, actual in actual_map.items():
        if key not in pred_map:
            actual_only.append(actual)

    full_fields = [
        "hunt_code",
        "model_year",
        "residency",
        "hunt_program",
        "point_level",
        "draw_family",
        "draw_type",
        "source_scope",
        "species",
        "prediction_source_file",
        "actual_source_file",
        "predicted_probability",
        "actual_probability",
        "error",
        "abs_error",
        "squared_error",
        "point_bucket",
        "failure_abs_error_gt_0_25",
    ]
    write_csv(AUDIT / "prediction_validation_with_modifiers.csv", joined, full_fields)
    write_csv(AUDIT / "prediction_validation_with_modifiers_by_draw_family.csv", group_metrics(joined, ["draw_family"]), ["draw_family", "row_count", "mae", "rmse", "bias", "failure_count_abs_error_gt_0_25"])
    write_csv(AUDIT / "prediction_validation_with_modifiers_by_year.csv", group_metrics(joined, ["model_year"]), ["model_year", "row_count", "mae", "rmse", "bias", "failure_count_abs_error_gt_0_25"])
    write_csv(AUDIT / "prediction_validation_with_modifiers_by_point_bucket.csv", group_metrics(joined, ["point_bucket"]), ["point_bucket", "row_count", "mae", "rmse", "bias", "failure_count_abs_error_gt_0_25"])

    return {
        "validation_status": "PASS",
        "metrics_recomputed": True,
        "zero_applicant_actual_rows_excluded": zero_excluded,
        "joined_rows": len(joined),
        "prediction_only_unmatched_rows": len(pred_only),
        "actual_only_unmatched_rows": len(actual_only),
        "duplicate_join_key_groups": 0,
        **metrics(joined),
    }


def main():
    AUDIT.mkdir(parents=True, exist_ok=True)
    modified_rows = build_modified_predictions()
    write_modified_odds(modified_rows)
    modifier_counts = Counter(row.get("modifier_status", "") for row in modified_rows)
    draw_type_counts = Counter(row.get("draw_type", "") for row in modified_rows)
    validation = validate(modified_rows)
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_prediction_file": str(PREDICTIONS),
        "output_prediction_file": str(OUT_PREDICTIONS),
        "output_odds_table_file": str(OUT_ODDS),
        "rows_written": len(modified_rows),
        "draw_type_counts": dict(sorted(draw_type_counts.items())),
        "modifier_status_counts": dict(sorted(modifier_counts.items())),
        "validation": validation,
    }
    (AUDIT / "prediction_validation_with_modifiers_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_csv(
        AUDIT / "prediction_validation_with_modifiers_summary.csv",
        [{"metric": key, "value": json.dumps(value) if isinstance(value, (dict, list)) else value} for key, value in summary.items()],
        ["metric", "value"],
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
