#!/usr/bin/env python3
import csv
import gzip
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

OUT_JSON = ROOT / "processed_data" / "hunt_research_2026.json"
OUT_AUDIT_CSV = ROOT / "processed_data" / "audits" / "hunt_research_2026_rebuild_coverage.csv"
OUT_NOTES_MD = ROOT / "docs" / "hunt_research_2026_rebuild_notes.md"

DB_PATH = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
MASTER_CANDIDATES = [
    ROOT / "processed_data" / "hunt_master_enriched.csv",
    ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "hunt_master_canonical_2026_built.csv",
]
LADDER_PATH = ROOT / "processed_data" / "point_ladder_view.csv"
DRAW_HISTORY_CANDIDATES = [
    ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv",
    ROOT / "processed_data" / "draw_reality_engine_v2.csv",
    ROOT / "processed_data" / "draw_reality_engine.csv",
]
HARVEST_CANDIDATES = [
    ROOT / "data_truth" / "harvest_results_truth" / "normalized" / "harvest_results_2025_for_2026_long.csv",
    ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2025" / "csv" / "harvest data" / "harvest_results_2025_for_2026_hunt_code_keyed.csv",
    ROOT / "processed_data" / "harvest_quality_features_all_years_by_hunt_code.csv",
    ROOT / "data_model" / "harvest_quality" / "harvest_quality_features_all_years_by_hunt_code.csv",
    ROOT / "data_truth" / "harvest_results_truth" / "normalized" / "harvest_quality_features_all_years_by_hunt_code.csv",
]
AGE_PATH = ROOT / "data_model" / "harvest_quality" / "harvest_average_age_global_merge_database.csv"
MANAGEMENT_PATH = ROOT / "processed_data" / "management_context" / "hunt_management_objective_context.json"
DWR_HANUMBER_PATH = ROOT / "processed_data" / "dwr_huntplanner_hanumber_2026.csv"
DRAW_2025_BREAKDOWN_PATH = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "Draw Odds" / "draw_breakdown_2025.csv"
DRAW_2025_PRIVATE_POINTS_PATH = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "Draw Odds" / "2025_big_game_private_lands_points.csv"
DRAW_2025_PRIVATE_TOTALS_PATH = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "Draw Odds" / "2025_big_game_private_lands_totals.csv"
DRAW_2025_TRUTH_PATH = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"


def clean(value):
    text = "" if value is None else str(value).strip()
    if text.upper() in {"", "N/A", "NA", "NULL", "NONE", "UNDEFINED", "NOT AVAILABLE"}:
        return ""
    return text


def upper(value):
    return clean(value).upper()


def to_number(value):
    text = clean(value)
    if not text or not re.search(r"\d", text):
        return None
    try:
        return float(re.sub(r"[^0-9.\-]", "", text))
    except Exception:
        return None


def number_text(value, digits=4):
    n = to_number(value)
    if n is None:
        return ""
    if abs(n - round(n)) < 1e-9:
        return str(int(round(n)))
    return f"{round(n, digits)}".rstrip("0").rstrip(".")


def pct_text(value):
    n = to_number(value)
    if n is None:
        return ""
    pct = n * 100 if 0 <= n <= 1 else n
    if abs(pct - round(pct)) < 1e-9:
        return str(int(round(pct)))
    return f"{round(pct, 2)}".rstrip("0").rstrip(".")


def pct_from_draw_display(value):
    text = clean(value)
    if not text:
        return ""
    # Supports strings like "~1 in 6.5 or 15.4%" and "33.3%".
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*%", text)
    if m:
        return number_text(m.group(1))
    return ""


def pct_from_success_ratio(value):
    text = clean(value)
    if not text:
        return ""
    # Common source format: "1 in X" -> percent = 100 / X
    m = re.search(r"1\s*in\s*([0-9]+(?:\.[0-9]+)?)", text, re.IGNORECASE)
    if m:
        denom = to_number(m.group(1))
        if denom and denom > 0:
            return pct_text(100.0 / denom)
    return ""


def format_draw_result_display(value):
    pct = to_number(value)
    if pct is None or pct <= 0:
        return ""
    if 0 <= pct <= 1:
        pct *= 100
    if pct <= 0:
        return ""
    one_in = 100.0 / pct
    return f"1 in {round(one_in, 1)} or {pct_text(pct)}%"


def normalize_draw_result_display(display_value, odds_value):
    display = clean(display_value)
    if display:
        if re.search(r"[0-9]\s*in\s*[0-9]", display, re.IGNORECASE):
            cleaned = re.sub(r"^[~=]+\s*", "", display).strip()
            return cleaned
        pct = pct_from_draw_display(display)
        if pct:
            return format_draw_result_display(pct)
    return format_draw_result_display(odds_value)


def first_text(*values):
    for value in values:
        t = clean(value)
        if t:
            return t
    return ""


def normalize_points(value):
    n = to_number(value)
    if n is None:
        return ""
    if abs(n - round(n)) < 1e-9:
        return str(int(round(n)))
    return f"{n}".rstrip("0").rstrip(".")


def normalize_residency(value):
    t = clean(value).lower()
    if not t:
        return ""
    if t.startswith("res"):
        return "Resident"
    if t.startswith("non"):
        return "Nonresident"
    return clean(value)


def detect_lfs_pointer(path: Path):
    if not path.exists():
        return False
    try:
        with path.open("rb") as f:
            head = f.read(256)
        return head.startswith(b"version https://git-lfs.github.com/spec/v1")
    except Exception:
        return False


def read_csv(path: Path):
    if not path.exists() or detect_lfs_pointer(path):
        return []
    try:
        with path.open("rb") as f:
            head = f.read(2)
    except Exception:
        return []
    opener = gzip.open if head == b"\x1f\x8b" else open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def read_json(path: Path):
    if not path.exists() or detect_lfs_pointer(path):
        return []
    obj = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        for key in ("rows", "data", "items"):
            if isinstance(obj.get(key), list):
                return obj[key]
    return []


def choose_existing(candidates):
    for candidate in candidates:
        if candidate.exists() and not detect_lfs_pointer(candidate):
            return candidate
    return candidates[0]


def build_draw_history_lookup(rows):
    by_key = {}
    by_code_res = {}
    for row in rows:
        code = upper(row.get("hunt_code"))
        if not code:
            continue
        year = int(to_number(row.get("year") or row.get("reported_hunt_year") or 0) or 0)
        # 2026 interpretation must use 2025 draw results only for historical ladder display.
        if year != 2025:
            continue
        residency = clean(row.get("residency"))
        points = clean(row.get("points"))
        odds = first_text(row.get("p_draw_pct"), row.get("p_draw_percent"))
        if not odds:
            odds = pct_from_success_ratio(row.get("success_ratio"))
        display = first_text(
            row.get("dwr_result_display"),
            row.get("display_2025_draw_results"),
            row.get("draw_result_display"),
            row.get("draw_result"),
            row.get("odds_display"),
        )
        key = (code, residency, points)
        current = by_key.get(key)
        if odds and (current is None or year > current["year"]):
            by_key[key] = {
                "year": year,
                "odds_2025_actual": pct_text(odds),
                "draw_result_display": normalize_draw_result_display(display, odds),
                "source_file": clean(row.get("source_file")),
                "source_page": clean(row.get("page_number")),
                "availability_status": first_text(row.get("availability_status"), row.get("allocation_status"), row.get("status"), row.get("draw_outlook")),
            }
        res_key = (code, residency)
        current_res = by_code_res.get(res_key)
        if odds and (current_res is None or year > current_res["year"]):
            by_code_res[res_key] = {
                "year": year,
                "odds_2025_actual": pct_text(odds),
                "draw_result_display": normalize_draw_result_display(display, odds),
                "source_file": clean(row.get("source_file")),
                "source_page": clean(row.get("page_number")),
                "availability_status": first_text(row.get("availability_status"), row.get("allocation_status"), row.get("status"), row.get("draw_outlook")),
            }
    return by_key, by_code_res


def build_draw_2025_supplement_lookup():
    by_code_point = {}
    by_code = {}

    def ensure_slot(code, points):
        key = (code, points)
        slot = by_code_point.get(key)
        if slot is None:
            slot = {
                "res": "",
                "nr": "",
                "total": "",
                "sources": set(),
            }
            by_code_point[key] = slot
        return slot

    def set_values(code, points, res="", nr="", total="", source=""):
        code = upper(code)
        points = normalize_points(points)
        if not code:
            return
        slot = ensure_slot(code, points)
        if res != "":
            slot["res"] = number_text(res)
        if nr != "":
            slot["nr"] = number_text(nr)
        if total != "":
            slot["total"] = number_text(total)
        if source:
            slot["sources"].add(source)
        if slot["total"] == "":
            res_n = to_number(slot["res"])
            nr_n = to_number(slot["nr"])
            if res_n is not None and nr_n is not None:
                slot["total"] = number_text(res_n + nr_n)

    # 1) point-level breakdown (code + residency + points)
    for row in read_csv(DRAW_2025_BREAKDOWN_PATH):
        code = row.get("hunt_code")
        points = row.get("point_level")
        residency = normalize_residency(row.get("residency"))
        total = row.get("total_permits")
        if residency == "Resident":
            set_values(code, points, res=total, source="draw_breakdown_2025")
        elif residency == "Nonresident":
            set_values(code, points, nr=total, source="draw_breakdown_2025")

    # 2) private lands point-level rows with both resident/nonresident in same row
    for row in read_csv(DRAW_2025_PRIVATE_POINTS_PATH):
        set_values(
            row.get("hunt_code"),
            row.get("Resident Applicants Points"),
            res=row.get("Resident Applicants Total # Permits"),
            nr=row.get("Nonresident Applicants Total # Permits"),
            source="private_lands_points_2025",
        )

    # 3) private lands totals (code-level fallback)
    for row in read_csv(DRAW_2025_PRIVATE_TOTALS_PATH):
        set_values(
            row.get("hunt_code"),
            "",
            res=row.get("Resident Applicants Total # Permits"),
            nr=row.get("Nonresident Applicants Total # Permits"),
            total=row.get("Combined Total # Permits"),
            source="private_lands_totals_2025",
        )

    # 4) normalized truth long (year 2025) as additional point-level support
    for row in read_csv(DRAW_2025_TRUTH_PATH):
        if clean(row.get("year")) != "2025":
            continue
        code = row.get("hunt_code")
        points = row.get("points")
        residency = normalize_residency(row.get("residency"))
        total = row.get("total_permits")
        if residency == "Resident":
            set_values(code, points, res=total, source="draw_results_long_2025")
        elif residency == "Nonresident":
            set_values(code, points, nr=total, source="draw_results_long_2025")

    for (code, points), slot in by_code_point.items():
        base = by_code.get(code)
        if base is None:
            base = {
                "res": "",
                "nr": "",
                "total": "",
                "sources": set(),
            }
            by_code[code] = base
        for k in ("res", "nr", "total"):
            if base[k] == "" and slot[k] != "":
                base[k] = slot[k]
        base["sources"].update(slot["sources"])

    return by_code_point, by_code


def build_dwr_lookup(rows):
    lookup = {}
    for row in rows:
        code = upper(row.get("hunt_code"))
        if not code:
            continue
        lookup[code] = {
            "current_age_3yr_average": number_text(row.get("current_age_3yr_average")),
            "permits_2026_res": number_text(row.get("permits_2026_res")),
            "permits_2026_nr": number_text(row.get("permits_2026_nr")),
            "permits_2026_total": number_text(row.get("permits_2026_total")),
        }
    return lookup


def build_harvest_lookup(rows):
    lookup = {}
    for row in rows:
        code = upper(row.get("hunt_code") or row.get("current_hunt_code"))
        if not code:
            continue
        year = int(to_number(row.get("reported_hunt_year") or 0) or 0)
        current = lookup.get(code)
        if current and year < current["year"]:
            continue
        lookup[code] = {
            "year": year,
            "harvest_success_pct": pct_text(first_text(row.get("percent_success"), row.get("harvest_success_percent"), row.get("success_percent"))),
            "average_days_hunted": number_text(first_text(row.get("avg_days"), row.get("average_days"), row.get("avg_days_hunted"), row.get("average_days_hunted"))),
            "average_age": number_text(first_text(row.get("average_age"), row.get("average_harvest_age"))),
            "harvest_source_file": clean(row.get("source_file")),
            "harvest_source_page": clean(row.get("source_page")),
        }
    return lookup


def build_age_lookup(rows):
    lookup = {}
    for row in rows:
        code = upper(row.get("hunt_code") or row.get("current_hunt_code"))
        if not code:
            continue
        year = int(to_number(row.get("reported_hunt_year") or 0) or 0)
        age = to_number(row.get("average_harvest_age"))
        if age is None or age <= 0:
            continue
        current = lookup.get(code)
        if current and year < current["year"]:
            continue
        lookup[code] = {
            "year": year,
            "average_harvest_age": number_text(age),
            "age_source_file": clean(row.get("source_file") or row.get("age_source_file")),
            "age_source_page": clean(row.get("source_page") or row.get("age_source_page")),
            "age_source_table_title": clean(row.get("source_table_title")),
            "age_review_status": clean(row.get("review_status")),
        }
    return lookup


def main():
    generated_at = datetime.now().isoformat()
    data_as_of = datetime.now().strftime("%Y-%m-%d")

    db_rows = read_csv(DB_PATH)
    master_path = choose_existing(MASTER_CANDIDATES)
    master_rows = read_csv(master_path)
    ladder_rows = read_csv(LADDER_PATH)
    draw_history_path = choose_existing(DRAW_HISTORY_CANDIDATES)
    draw_rows = read_csv(draw_history_path)
    harvest_path = choose_existing(HARVEST_CANDIDATES)
    harvest_rows = read_csv(harvest_path)
    age_rows = read_csv(AGE_PATH)
    management_rows = read_json(MANAGEMENT_PATH)
    dwr_rows = read_csv(DWR_HANUMBER_PATH)

    db_map = {upper(r.get("hunt_code")): r for r in db_rows if upper(r.get("hunt_code"))}
    master_map = {upper(r.get("hunt_code")): r for r in master_rows if upper(r.get("hunt_code"))}
    management_map = {upper(r.get("hunt_code")): r for r in management_rows if upper(r.get("hunt_code"))}
    draw_by_key, draw_by_code_res = build_draw_history_lookup(draw_rows)
    draw2025_by_code_point, draw2025_by_code = build_draw_2025_supplement_lookup()
    dwr_map = build_dwr_lookup(dwr_rows)
    harvest_map = build_harvest_lookup(harvest_rows)
    age_map = build_age_lookup(age_rows)

    expected_fields = [
        "algorithm_status", "applicants", "average_harvest_age", "data_quality_flags", "delta_gap",
        "display_2025_draw_results", "display_2026_max_point_pool", "display_2026_random_draw",
        "display_odds_pct", "draw_2026_system_type", "draw_outlook", "draw_pool", "draw_system",
        "draw_system_type", "dwr_result_display", "eligible_applicants", "gap", "guaranteed_at_2026",
        "guaranteed_marker", "guaranteed_probability", "hunt_class", "length", "management_direction",
        "management_objective_max", "management_objective_min", "management_objective_note",
        "management_objective_range", "management_objective_type", "max_point_permits_2026", "notes",
        "objective_status", "objective_status_rule", "objective_unit", "odds_2025_actual",
        "p_bonus_pool_pct", "p_draw", "p_draw_mean", "p_draw_p10", "p_draw_p90", "p_draw_pct",
        "p_max_pool_mean", "p_max_pool_mean_pct", "p_max_pool_pct", "p_random_pool", "p_random_pool_pct",
        "permit_direction_watch", "point_pool_zone", "points", "preference_model_note", "permits_2025_res",
        "permits_2025_nr", "permits_2025_total",
        "projected_2026_max_cutoff_point", "push", "quota_source_status", "random_permits_2026", "reason",
        "residency", "some", "total_permits", "trend", "year", "hunt_code", "hunt_name", "species", "weapon",
        "availability_status", "current_age_3yr_average",
    ]

    rows = []
    ladder_codes = set()

    for row in ladder_rows:
        code = upper(row.get("hunt_code"))
        if not code:
            continue
        ladder_codes.add(code)
        db = db_map.get(code, {})
        master = master_map.get(code, {})
        mgmt = management_map.get(code, {})
        dwr = dwr_map.get(code, {})
        residency = clean(row.get("residency"))
        points = clean(row.get("points"))

        hist = draw_by_key.get((code, residency, points)) or draw_by_code_res.get((code, residency), {})
        draw2025 = draw2025_by_code_point.get((code, normalize_points(points))) or draw2025_by_code.get(code, {})
        harvest = harvest_map.get(code, {})
        age = age_map.get(code, {})

        p_draw_mean = first_text(row.get("p_draw_mean"))
        p_draw_pct = first_text(row.get("p_draw_pct"), row.get("display_odds_pct"))
        if not p_draw_pct and p_draw_mean:
            p_draw_pct = pct_text(p_draw_mean)
        display_odds_raw = clean(row.get("display_odds_pct"))
        if display_odds_raw:
            # point_ladder_view display_odds_pct is already a percent-format display field.
            display_odds_pct = number_text(display_odds_raw, digits=4)
        else:
            display_odds_pct = pct_text(p_draw_pct)

        p_draw = first_text(row.get("p_draw"))
        if not p_draw and p_draw_pct:
            p_draw = number_text((to_number(p_draw_pct) or 0) / 100)

        p_max = first_text(row.get("p_max_pool_mean"))
        p_random = first_text(row.get("p_random_mean"))

        mgmt_min = first_text(mgmt.get("management_objective_min"))
        mgmt_max = first_text(mgmt.get("management_objective_max"))
        mgmt_range = first_text(
            mgmt.get("management_objective_range"),
            f"{mgmt_min} to {mgmt_max} {first_text(mgmt.get('objective_unit'))}".strip() if mgmt_min or mgmt_max else "",
        )

        permit_2026_res = number_text(
            first_text(
                db.get("permit_allotment_2026_res"),
                dwr.get("permits_2026_res"),
            )
        )
        permit_2026_nr = number_text(
            first_text(
                db.get("permit_allotment_2026_nr"),
                dwr.get("permits_2026_nr"),
            )
        )
        permit_2026_total = number_text(
            first_text(
                db.get("permit_allotment_2026_total"),
                dwr.get("permits_2026_total"),
            )
        )
        # 2025 draw-results permit context for 2026 modeling:
        # Prefer explicit 2025 draw fields from ladder/runtime sources.
        permit_2025_res = number_text(
            first_text(
                row.get("permits_2025_draw_res"),
                draw2025.get("res"),
            )
        )
        permit_2025_nr = number_text(
            first_text(
                row.get("permits_2025_draw_nr"),
                draw2025.get("nr"),
            )
        )
        permit_2025_total = number_text(
            first_text(
                row.get("permits_2025_draw_total"),
                draw2025.get("total"),
            )
        )

        out = {
            "hunt_code": code,
            "hunt_name": first_text(row.get("hunt_name"), master.get("hunt_name"), db.get("hunt_name")),
            "species": first_text(row.get("species"), master.get("species"), db.get("species")),
            "sex_type": first_text(row.get("sex_type"), master.get("sex_type"), db.get("sex_type")),
            "weapon": first_text(row.get("weapon"), master.get("weapon"), db.get("weapon")),
            "hunt_type": first_text(row.get("hunt_type"), master.get("hunt_type"), db.get("hunt_type")),
            "hunt_class": first_text(row.get("hunt_class"), master.get("hunt_class"), db.get("hunt_class")),
            "boundary_id": first_text(row.get("boundary_id"), master.get("boundary_id"), db.get("boundary_id")),
            "unit_name": first_text(row.get("unit_name"), row.get("hunt_name"), master.get("unit_name")),
            "residency": residency,
            "points": points,
            "year": first_text(row.get("year"), "2026"),
            "draw_pool": first_text(row.get("draw_pool"), "standard"),
            "draw_2026_system_type": first_text(row.get("draw_2026_system_type"), row.get("draw_system_type"), db.get("draw_2026_system_type")),
            "draw_system_type": first_text(row.get("draw_system_type"), row.get("draw_2026_system_type"), db.get("draw_2026_system_type")),
            "draw_system": first_text(row.get("draw_system_type"), row.get("draw_2026_system_type"), db.get("draw_2026_system_type")),
            "draw_outlook": first_text(row.get("draw_outlook"), row.get("status")),
            "trend": first_text(row.get("trend")),
            "status": first_text(row.get("status"), row.get("data_status")),
            "availability_status": first_text(
                row.get("availability_status"),
                row.get("allocation_status"),
                hist.get("availability_status"),
                row.get("status"),
                row.get("draw_outlook"),
            ),
            "algorithm_status": first_text(row.get("algorithm_status"), row.get("draw_model_class"), row.get("probability_model"), row.get("draw_system_type")),
            "eligible_applicants": number_text(first_text(row.get("eligible_applicants"), row.get("forecast_applicants_at_level"), row.get("applicants_at_level"))),
            "applicants": number_text(first_text(row.get("forecast_applicants_at_level"), row.get("applicants_at_level"), row.get("applicants"))),
            "total_permits": number_text(
                first_text(
                    db.get("permit_allotment_2026_total"),
                    dwr.get("permits_2026_total"),
                )
            ),
            "max_point_permits_2026": number_text(row.get("max_point_permits_2026")),
            "random_permits_2026": number_text(row.get("random_permits_2026")),
            "permits_2026_res": permit_2026_res,
            "permits_2026_nr": permit_2026_nr,
            "permits_2026_total": permit_2026_total,
            "permits_2025_res": permit_2025_res,
            "permits_2025_nr": permit_2025_nr,
            "permits_2025_total": permit_2025_total,
            "p_draw": p_draw,
            "p_draw_mean": number_text(p_draw_mean, digits=6),
            "p_draw_pct": pct_text(p_draw_pct),
            "p_draw_p10": number_text(row.get("p_draw_p10"), digits=6),
            "p_draw_p90": number_text(row.get("p_draw_p90"), digits=6),
            "display_odds_pct": display_odds_pct,
            "p_max_pool_mean": number_text(p_max),
            "p_max_pool_mean_pct": pct_text(p_max),
            "p_max_pool_pct": pct_text(first_text(row.get("p_max_pool_pct"), p_max)),
            "p_random_pool": number_text(p_random),
            "p_random_pool_pct": pct_text(first_text(row.get("p_random_pool_pct"), p_random)),
            "p_bonus_pool_pct": pct_text(row.get("p_bonus_pool_pct")),
            "guaranteed_at_2026": number_text(first_text(row.get("guaranteed_at_2026"), row.get("projected_2026_max_cutoff_point"))),
            "projected_2026_max_cutoff_point": number_text(row.get("projected_2026_max_cutoff_point")),
            "guaranteed_probability": first_text(
                number_text(row.get("guaranteed_probability")),
                "1" if clean(points) and clean(points) == clean(first_text(row.get("guaranteed_at_2026"), row.get("projected_2026_max_cutoff_point"))) else "",
            ),
            "guaranteed_marker": "TRUE" if clean(points) and clean(points) == clean(first_text(row.get("guaranteed_at_2026"), row.get("projected_2026_max_cutoff_point"))) else "",
            "odds_2025_actual": first_text(
                pct_from_draw_display(row.get("display_2025_draw_results")),
                pct_from_draw_display(row.get("dwr_result_display")),
                hist.get("odds_2025_actual"),
            ),
            "delta_gap": number_text(row.get("guaranteed_delta_2025_to_2026")),
            "gap": number_text(row.get("guaranteed_delta_2025_to_2026")),
            "point_pool_zone": first_text(row.get("point_pool_zone")),
            "quota_source_status": first_text(
                db.get("permit_allotment_2026_status"),
                row.get("quota_source_status"),
                row.get("permit_allotment_2026_status"),
                row.get("permit_status"),
            ),
            "preference_model_note": first_text(row.get("probability_model"), row.get("draw_model_class")),
            "data_quality_flags": first_text(row.get("reason_codes"), row.get("data_quality_grade")),
            "reason": first_text(row.get("status"), row.get("draw_outlook")),
            "permit_direction_watch": first_text(mgmt.get("permit_direction_watch")),
            "management_objective_type": first_text(mgmt.get("management_objective_type")),
            "management_objective_min": mgmt_min,
            "management_objective_max": mgmt_max,
            "management_objective_range": mgmt_range,
            "management_objective_note": first_text(mgmt.get("notes")),
            "objective_status": first_text(mgmt.get("objective_status")),
            "objective_status_rule": first_text(mgmt.get("objective_status_rule"), mgmt.get("notes"), mgmt.get("objective_status")),
            "objective_unit": first_text(mgmt.get("objective_unit")),
            "management_direction": first_text(mgmt.get("management_direction")),
            "average_harvest_age": first_text(age.get("average_harvest_age"), harvest.get("average_age"), db.get("average_harvest_age")),
            "current_age_3yr_average": first_text(
                dwr.get("current_age_3yr_average"),
                number_text(row.get("current_age_3yr_average")),
                number_text(db.get("current_age_3yr_average")),
            ),
            "harvest_success_pct": first_text(harvest.get("harvest_success_pct")),
            "average_days_hunted": first_text(harvest.get("average_days_hunted")),
            "source_file": first_text(hist.get("source_file"), harvest.get("harvest_source_file"), age.get("age_source_file")),
            "source_page": first_text(hist.get("source_page"), harvest.get("harvest_source_page"), age.get("age_source_page")),
            "truth_source_file": first_text(row.get("truth_source_file"), hist.get("source_file"), age.get("age_source_file")),
            "average_harvest_age_source_file": first_text(age.get("age_source_file"), db.get("average_harvest_age_source_file")),
            "average_harvest_age_review_status": first_text(age.get("age_review_status"), db.get("average_harvest_age_review_status")),
            "model_version": first_text(row.get("model_version")),
            "rule_version": first_text(row.get("rule_version")),
            "source_freshness": data_as_of,
            "generated_at": generated_at,
            "data_as_of": data_as_of,
            "runtime_contract_version": "hunt_research_2026.v2",
            "dwr_result_display": first_text(
                row.get("dwr_result_display"),
                row.get("display_2025_draw_results"),
                hist.get("draw_result_display"),
                format_draw_result_display(hist.get("odds_2025_actual")),
            ),
            "display_2025_draw_results": first_text(
                row.get("display_2025_draw_results"),
                row.get("dwr_result_display"),
                hist.get("draw_result_display"),
                format_draw_result_display(hist.get("odds_2025_actual")),
            ),
            "display_2026_max_point_pool": number_text(row.get("max_point_permits_2026")),
            "display_2026_random_draw": number_text(row.get("random_permits_2026")),
            "notes": first_text(mgmt.get("notes")),
            "some": "",
            "push": "",
            "length": "",
        }

        missing = []
        if not out["p_draw_pct"]:
            missing.append("P_DRAW_MISSING")
        if not out["guaranteed_at_2026"]:
            missing.append("GUARANTEED_LINE_MISSING")
        if not out["average_harvest_age"]:
            missing.append("AGE_MISSING")
        out["missing_value_classification"] = "|".join(missing) if missing else "COMPLETE_KEY_FIELDS"
        rows.append(out)

    missing_codes = sorted(set(db_map.keys()) - ladder_codes)
    for code in missing_codes:
        db = db_map.get(code, {})
        master = master_map.get(code, {})
        mgmt = management_map.get(code, {})
        dwr = dwr_map.get(code, {})
        harvest = harvest_map.get(code, {})
        age = age_map.get(code, {})
        draw2025 = draw2025_by_code.get(code, {})
        rows.append({
            "hunt_code": code,
            "hunt_name": first_text(master.get("hunt_name"), db.get("hunt_name")),
            "species": first_text(master.get("species"), db.get("species")),
            "sex_type": first_text(master.get("sex_type"), db.get("sex_type")),
            "weapon": first_text(master.get("weapon"), db.get("weapon")),
            "hunt_type": first_text(master.get("hunt_type"), db.get("hunt_type")),
            "hunt_class": first_text(master.get("hunt_class"), db.get("hunt_class")),
            "boundary_id": first_text(master.get("boundary_id"), db.get("boundary_id")),
            "unit_name": first_text(master.get("unit_name"), db.get("hunt_name")),
            "residency": "All",
            "points": "",
            "year": "2026",
            "draw_pool": "",
            "draw_2026_system_type": first_text(db.get("draw_2026_system_type")),
            "draw_system_type": first_text(db.get("draw_2026_system_type")),
            "draw_system": first_text(db.get("draw_2026_system_type")),
            "draw_outlook": "NO_LADDER_ROWS",
            "trend": "",
            "status": "NO_LADDER_ROWS",
            "availability_status": "NO_LADDER_ROWS",
            "algorithm_status": "",
            "eligible_applicants": "",
            "applicants": "",
            "total_permits": "",
            "max_point_permits_2026": "",
            "random_permits_2026": "",
            "permits_2026_res": number_text(db.get("permit_allotment_2026_res")),
            "permits_2026_nr": number_text(db.get("permit_allotment_2026_nr")),
            "permits_2026_total": number_text(first_text(db.get("permit_allotment_2026_total"), dwr.get("permits_2026_total"))),
            "permits_2025_res": number_text(first_text(draw2025.get("res"))),
            "permits_2025_nr": number_text(first_text(draw2025.get("nr"))),
            "permits_2025_total": number_text(first_text(draw2025.get("total"))),
            "p_draw": "",
            "p_draw_mean": "",
            "p_draw_pct": "",
            "p_draw_p10": "",
            "p_draw_p90": "",
            "display_odds_pct": "",
            "p_max_pool_mean": "",
            "p_max_pool_mean_pct": "",
            "p_max_pool_pct": "",
            "p_random_pool": "",
            "p_random_pool_pct": "",
            "p_bonus_pool_pct": "",
            "guaranteed_at_2026": "",
            "projected_2026_max_cutoff_point": "",
            "guaranteed_probability": "",
            "guaranteed_marker": "",
            "odds_2025_actual": "",
            "delta_gap": "",
            "gap": "",
            "point_pool_zone": "",
            "quota_source_status": "",
            "preference_model_note": "",
            "data_quality_flags": "NO_LADDER_ROWS",
            "reason": "No point ladder rows available for this hunt code.",
            "permit_direction_watch": first_text(mgmt.get("permit_direction_watch")),
            "management_objective_type": first_text(mgmt.get("management_objective_type")),
            "management_objective_min": first_text(mgmt.get("management_objective_min")),
            "management_objective_max": first_text(mgmt.get("management_objective_max")),
            "management_objective_range": "",
            "management_objective_note": first_text(mgmt.get("notes")),
            "objective_status": first_text(mgmt.get("objective_status")),
            "objective_status_rule": first_text(mgmt.get("objective_status_rule"), mgmt.get("notes"), mgmt.get("objective_status")),
            "objective_unit": first_text(mgmt.get("objective_unit")),
            "management_direction": first_text(mgmt.get("management_direction")),
            "average_harvest_age": first_text(age.get("average_harvest_age"), harvest.get("average_age"), db.get("average_harvest_age")),
            "current_age_3yr_average": first_text(
                dwr.get("current_age_3yr_average"),
                number_text(db.get("current_age_3yr_average")),
            ),
            "harvest_success_pct": first_text(harvest.get("harvest_success_pct")),
            "average_days_hunted": first_text(harvest.get("average_days_hunted")),
            "source_file": "",
            "source_page": "",
            "truth_source_file": "",
            "average_harvest_age_source_file": first_text(age.get("age_source_file"), db.get("average_harvest_age_source_file")),
            "average_harvest_age_review_status": first_text(age.get("age_review_status"), db.get("average_harvest_age_review_status")),
            "model_version": "",
            "rule_version": "",
            "source_freshness": data_as_of,
            "generated_at": generated_at,
            "data_as_of": data_as_of,
            "runtime_contract_version": "hunt_research_2026.v2",
            "dwr_result_display": "",
            "display_2025_draw_results": "",
            "display_2026_max_point_pool": "",
            "display_2026_random_draw": "",
            "notes": first_text(mgmt.get("notes")),
            "some": "",
            "push": "",
            "length": "",
            "missing_value_classification": "NO_LADDER_ROWS",
        })

    # Ensure all expected runtime fields are present on every row.
    for row in rows:
        for field in expected_fields:
            row.setdefault(field, "")

    # Sort for stable output.
    rows.sort(key=lambda r: (upper(r.get("hunt_code")), upper(r.get("residency")), to_number(r.get("points")) if to_number(r.get("points")) is not None else -1))

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    # Coverage/audit table
    db_codes = set(db_map.keys())
    contract_codes = {upper(r.get("hunt_code")) for r in rows if upper(r.get("hunt_code"))}
    missing_codes = sorted(db_codes - contract_codes)
    extra_codes = sorted(contract_codes - db_codes)

    key_fields = [
        "hunt_code", "species", "residency", "points", "p_draw_pct", "guaranteed_at_2026",
        "permits_2026_total", "average_harvest_age", "harvest_success_pct", "average_days_hunted",
        "management_objective_type", "model_version", "rule_version", "source_freshness",
    ]
    field_presence = []
    for field in expected_fields:
        nonblank = sum(1 for r in rows if clean(r.get(field)))
        field_presence.append((field, nonblank))

    coverage_rows = []
    coverage_rows.append({"section": "summary", "metric": "rows", "value": str(len(rows)), "pct": "", "notes": ""})
    coverage_rows.append({"section": "summary", "metric": "database_codes", "value": str(len(db_codes)), "pct": "", "notes": ""})
    coverage_rows.append({"section": "summary", "metric": "contract_codes", "value": str(len(contract_codes)), "pct": "", "notes": ""})
    coverage_rows.append({"section": "summary", "metric": "missing_codes_vs_database", "value": str(len(missing_codes)), "pct": "", "notes": ";".join(missing_codes[:100])})
    coverage_rows.append({"section": "summary", "metric": "extra_codes_not_in_database", "value": str(len(extra_codes)), "pct": "", "notes": ";".join(extra_codes[:100])})
    coverage_rows.append({"section": "source", "metric": "master_source_path", "value": str(master_path.relative_to(ROOT).as_posix()), "pct": "", "notes": "LFS-safe fallback used when required."})
    coverage_rows.append({"section": "source", "metric": "harvest_source_path", "value": str(harvest_path.relative_to(ROOT).as_posix()), "pct": "", "notes": ""})

    for field in key_fields:
        nonblank = sum(1 for r in rows if clean(r.get(field)))
        pct = round((nonblank / len(rows)) * 100, 2) if rows else 0
        coverage_rows.append({"section": "key_field", "metric": field, "value": str(nonblank), "pct": str(pct), "notes": ""})

    for field, nonblank in field_presence:
        pct = round((nonblank / len(rows)) * 100, 2) if rows else 0
        coverage_rows.append({"section": "runtime_field", "metric": field, "value": str(nonblank), "pct": str(pct), "notes": ""})

    classification_counts = Counter(clean(r.get("missing_value_classification")) for r in rows)
    for key, count in sorted(classification_counts.items()):
        coverage_rows.append({"section": "missing_value_classification", "metric": key or "BLANK", "value": str(count), "pct": "", "notes": ""})

    OUT_AUDIT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_AUDIT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["section", "metric", "value", "pct", "notes"])
        writer.writeheader()
        writer.writerows(coverage_rows)

    missing_runtime_fields = [field for field in expected_fields if not any(clean(r.get(field)) for r in rows)]
    completeness_status = "COMPLETE" if not missing_codes and not missing_runtime_fields else "PARTIAL"

    notes = f"""# hunt_research_2026 Rebuild Notes

Generated: {generated_at}

## Contract rebuild goal
- Rebuilt `processed_data/hunt_research_2026.json` from canonical sources with full 2026 hunt-code coverage and runtime-aligned field set.

## Sources used
- DATABASE truth: `{DB_PATH.relative_to(ROOT).as_posix()}`
- Master reference resolved: `{master_path.relative_to(ROOT).as_posix()}`
- Point ladder: `{LADDER_PATH.relative_to(ROOT).as_posix()}`
- Draw history: `{draw_history_path.relative_to(ROOT).as_posix()}`
- Harvest features: `{harvest_path.relative_to(ROOT).as_posix()}`
- Age features: `{AGE_PATH.relative_to(ROOT).as_posix()}`
- Management context: `{MANAGEMENT_PATH.relative_to(ROOT).as_posix()}`

## Coverage summary
- Contract rows: {len(rows)}
- Unique contract hunt codes: {len(contract_codes)}
- DATABASE hunt codes: {len(db_codes)}
- Missing hunt codes vs DATABASE: {len(missing_codes)}
- Missing runtime fields with zero population: {len(missing_runtime_fields)}

## Runtime field status
- Expected runtime field set size: {len(expected_fields)}
- Fields with no populated values: {", ".join(missing_runtime_fields[:120]) if missing_runtime_fields else "None"}

## Notes
- `DATABASE.csv` was treated as truth and not modified.
- Missing values are explicit via `missing_value_classification` (not silently dropped).
- Completeness status: **{completeness_status}**
"""
    OUT_NOTES_MD.write_text(notes, encoding="utf-8")

    print(json.dumps({
        "rows": len(rows),
        "contract_codes": len(contract_codes),
        "database_codes": len(db_codes),
        "missing_codes_vs_database": len(missing_codes),
        "missing_runtime_fields": len(missing_runtime_fields),
        "status": completeness_status,
    }, indent=2))


if __name__ == "__main__":
    main()
