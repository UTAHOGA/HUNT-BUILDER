from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
PROCESSED = REPO / "processed_data"

ENGINE_PATH = PROCESSED / "draw_reality_engine_predictive_v2.csv"
LADDER_PATH = PROCESSED / "point_ladder_view.csv"
MASTER_PATH = PROCESSED / "hunt_master_enriched.csv"
REFERENCE_PATH = PROCESSED / "hunt_unit_reference_linked.csv"
DATABASE_PATH = REPO / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"

OUT_JSON = PROCESSED / "online_runtime_crosscheck.json"
OUT_MD = PROCESSED / "online_runtime_crosscheck.md"


def _read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def _write_csv(path: Path, rows: list[dict[str, str]], headers: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({header: row.get(header, "") for header in headers})


def _clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def _norm_code(value: object) -> str:
    return _clean(value).upper()


def _norm_residency(value: object) -> str:
    raw = _clean(value).lower()
    return "Nonresident" if raw == "nonresident" else "Resident"


def _norm_draw_pool(value: object) -> str:
    raw = _clean(value).lower()
    return raw or "standard"


def _norm_draw_system_type(value: object) -> str:
    raw = _clean(value)
    if raw in {"YOUTH_DRAW_ONLY_ELK", "YOUTH_RANDOM_ELK_GENERAL_BULL"}:
        return "YOUTH_GENERAL_ANY_BULL_ELK"
    return raw


def _group_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (
        _norm_code(row.get("hunt_code")),
        _norm_residency(row.get("residency")),
        _norm_draw_pool(row.get("draw_pool")),
    )


def _row_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (*_group_key(row), _clean(row.get("points")))


def _dup_count(rows: list[dict[str, str]], key_fn) -> int:
    keys = [key_fn(row) for row in rows]
    return len(keys) - len(set(keys))


def _prefer(*values: object, default: str = "") -> str:
    for value in values:
        text = _clean(value)
        if text:
            return text
    return default


def _build_database_lookup(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}
    for row in rows:
        code = _norm_code(row.get("hunt_code"))
        if code and code not in lookup:
            lookup[code] = row
    return lookup


def _base_row_for(
    hunt_code: str,
    residency: str,
    rows: list[dict[str, str]],
    by_group: dict[tuple[str, str, str], dict[str, str]],
    by_code_res: dict[tuple[str, str], dict[str, str]],
    by_code: dict[str, dict[str, str]],
) -> dict[str, str]:
    return (
        by_group.get((hunt_code, residency, "standard"))
        or by_code_res.get((hunt_code, residency))
        or by_code.get(hunt_code)
        or {}
    )


def _synth_master_row(
    engine_row: dict[str, str],
    base: dict[str, str],
    db_row: dict[str, str],
    headers: list[str],
) -> dict[str, str]:
    row = {header: _clean(base.get(header)) for header in headers}
    p_draw_pct = _prefer(engine_row.get("p_draw_pct"), engine_row.get("display_odds_pct"))
    row.update({
        "hunt_code": _clean(engine_row.get("hunt_code")),
        "boundary_id": _prefer(base.get("boundary_id"), db_row.get("boundary_id")),
        "hunt_name": _prefer(engine_row.get("hunt_name"), base.get("hunt_name"), db_row.get("hunt_name")),
        "weapon": _prefer(engine_row.get("weapon"), base.get("weapon"), db_row.get("weapon"), default="Any Legal Weapon"),
        "hunt_type": _prefer(engine_row.get("hunt_type"), base.get("hunt_type"), db_row.get("hunt_type")),
        "access_type": _prefer(engine_row.get("access_type"), base.get("access_type"), default="Public"),
        "residency": _norm_residency(engine_row.get("residency")),
        "points": _clean(engine_row.get("points")),
        "public_permits_2025": _prefer(engine_row.get("public_permits_2025"), base.get("public_permits_2025")),
        "public_permits_2026": _prefer(engine_row.get("public_permits_2026"), base.get("public_permits_2026")),
        "public_permits_2026_source": _prefer(engine_row.get("public_permits_2026_source"), base.get("public_permits_2026_source")),
        "applicants_2025": _prefer(engine_row.get("applicants_2025"), base.get("applicants_2025")),
        "projected_applicants_2026": _prefer(engine_row.get("projected_applicants_2026"), base.get("projected_applicants_2026")),
        "projected_applicants_2026_source": _prefer(engine_row.get("projected_applicants_2026_source"), base.get("projected_applicants_2026_source")),
        "odds_2025": _prefer(engine_row.get("odds_2025"), base.get("odds_2025")),
        "odds_2026_projected": _prefer(p_draw_pct, engine_row.get("odds_2026_projected"), base.get("odds_2026_projected")),
        "max_point_permits_2026": _prefer(engine_row.get("max_point_permits_2026"), base.get("max_point_permits_2026")),
        "random_permits_2026": _prefer(engine_row.get("random_permits_2026"), base.get("random_permits_2026")),
        "success_hunters": _prefer(base.get("success_hunters")),
        "success_harvest": _prefer(base.get("success_harvest")),
        "success_percent": _prefer(base.get("success_percent")),
        "missing_draw_data": "FALSE" if _clean(engine_row.get("p_draw")) else _prefer(base.get("missing_draw_data"), "TRUE"),
        "missing_projection": _prefer(base.get("missing_projection"), "FALSE"),
        "missing_permits": "FALSE" if _prefer(engine_row.get("public_permits_2026"), engine_row.get("permits_2026_total"), base.get("public_permits_2026")) else _prefer(base.get("missing_permits"), "TRUE"),
        "permits_2026_res": _prefer(engine_row.get("permits_2026_res"), base.get("permits_2026_res")),
        "permits_2026_nr": _prefer(engine_row.get("permits_2026_nr"), base.get("permits_2026_nr")),
        "permits_2026_total": _prefer(engine_row.get("permits_2026_total"), base.get("permits_2026_total")),
        "permits_2026_source": _prefer(engine_row.get("permits_2026_source"), base.get("permits_2026_source")),
        "permit_status": _prefer(engine_row.get("permit_status"), base.get("permit_status")),
        "permit_allocation_type": _prefer(engine_row.get("permit_allocation_type"), base.get("permit_allocation_type")),
        "permit_source_authority": _prefer(engine_row.get("permit_source_authority"), base.get("permit_source_authority")),
        "permit_note": _prefer(engine_row.get("permit_note"), base.get("permit_note")),
        "permit_overlay_source": _prefer(engine_row.get("permit_overlay_source"), base.get("permit_overlay_source")),
        "data_status": _prefer(engine_row.get("data_status"), base.get("data_status")),
        "draw_2026_system_type": _prefer(engine_row.get("draw_system_type"), base.get("draw_2026_system_type")),
        "draw_system_type": _prefer(engine_row.get("draw_system_type"), base.get("draw_system_type")),
        "algorithm_status": _prefer(engine_row.get("algorithm_status"), base.get("algorithm_status")),
        "draw_routing_reason": _prefer(engine_row.get("reason"), base.get("draw_routing_reason")),
        "permits_2026_conservation": _prefer(base.get("permits_2026_conservation")),
        "permits_2026_expo": _prefer(base.get("permits_2026_expo")),
        "permits_2026_sportsman": _prefer(engine_row.get("sportsman_permit_count"), base.get("permits_2026_sportsman")),
        "special_permit_area_id": _prefer(base.get("special_permit_area_id")),
        "special_permit_category": _prefer(base.get("special_permit_category")),
        "special_permit_note": _prefer(base.get("special_permit_note")),
        "special_permit_overlay_source": _prefer(base.get("special_permit_overlay_source")),
        "draw_pool": _norm_draw_pool(engine_row.get("draw_pool")),
    })
    return row


def _synth_reference_row(
    engine_row: dict[str, str],
    base: dict[str, str],
    db_row: dict[str, str],
    headers: list[str],
) -> dict[str, str]:
    row = {header: _clean(base.get(header)) for header in headers}
    residency = _norm_residency(engine_row.get("residency"))
    draw_pool = _norm_draw_pool(engine_row.get("draw_pool"))
    has_draw_source = "TRUE" if _clean(engine_row.get("p_draw")) else _prefer(base.get("has_bg_odds_page"), "FALSE")
    row.update({
        "hunt_code": _clean(engine_row.get("hunt_code")),
        "residency": residency,
        "hunt_name": _prefer(engine_row.get("hunt_name"), base.get("hunt_name"), db_row.get("hunt_name")),
        "species": _prefer(engine_row.get("species"), base.get("species"), db_row.get("species")),
        "weapon": _prefer(engine_row.get("weapon"), base.get("weapon"), db_row.get("weapon"), default="Any Legal Weapon"),
        "hunt_type": _prefer(engine_row.get("hunt_type"), base.get("hunt_type"), db_row.get("hunt_type")),
        "access_type": _prefer(engine_row.get("access_type"), base.get("access_type"), default="Public"),
        "public_permits_2025": _prefer(engine_row.get("public_permits_2025"), base.get("public_permits_2025")),
        "public_permits_2026": _prefer(engine_row.get("public_permits_2026"), base.get("public_permits_2026")),
        "permits_2025_res": _prefer(base.get("permits_2025_res")),
        "permits_2025_nr": _prefer(base.get("permits_2025_nr")),
        "permits_2025_total": _prefer(base.get("permits_2025_total")),
        "permits_2026_res": _prefer(engine_row.get("permits_2026_res"), base.get("permits_2026_res")),
        "permits_2026_nr": _prefer(engine_row.get("permits_2026_nr"), base.get("permits_2026_nr")),
        "permits_2026_total": _prefer(engine_row.get("permits_2026_total"), base.get("permits_2026_total")),
        "applicants_2025": _prefer(engine_row.get("applicants_2025"), base.get("applicants_2025")),
        "projected_applicants_2026": _prefer(engine_row.get("projected_applicants_2026"), base.get("projected_applicants_2026")),
        "max_point_permits_2026": _prefer(engine_row.get("max_point_permits_2026"), base.get("max_point_permits_2026")),
        "random_permits_2026": _prefer(engine_row.get("random_permits_2026"), base.get("random_permits_2026")),
        "guaranteed_at_2026": _prefer(engine_row.get("guaranteed_at_2026"), base.get("guaranteed_at_2026")),
        "delta_gap": _prefer(engine_row.get("delta_gap"), base.get("delta_gap")),
        "trend": _prefer(engine_row.get("trend"), base.get("trend")),
        "coverage_status": "MODELED_ENGINE_GROUP",
        "coverage_reason": _prefer(engine_row.get("model_strategy"), engine_row.get("draw_system_type"), "predictive_engine_runtime_sync"),
        "bg_odds_pdf_page_index": _prefer(base.get("bg_odds_pdf_page_index")),
        "bg_odds_printed_page": _prefer(base.get("bg_odds_printed_page")),
        "bg_odds_hunt_title": _prefer(base.get("bg_odds_hunt_title"), engine_row.get("hunt_name")),
        "has_bg_odds_page": has_draw_source,
        "rac_page": _prefer(base.get("rac_page")),
        "rac_section": _prefer(base.get("rac_section")),
        "source_pdf": _prefer(base.get("source_pdf")),
        "harvest_hunters_2025": _prefer(base.get("harvest_hunters_2025")),
        "harvest_2025": _prefer(base.get("harvest_2025")),
        "harvest_success_percent_2025": _prefer(base.get("harvest_success_percent_2025")),
        "harvest_average_days_2025": _prefer(base.get("harvest_average_days_2025")),
        "harvest_satisfaction_2025": _prefer(base.get("harvest_satisfaction_2025")),
        "source_file_2026": _prefer(base.get("source_file_2026"), _clean(db_row.get("source_file_2026"))),
        "link_key": f"{_clean(engine_row.get('hunt_code')).upper()}_{residency.upper()}_{draw_pool.upper()}",
        "antlerless_odds_sheet": _prefer(base.get("antlerless_odds_sheet")),
        "antlerless_odds_row_start": _prefer(base.get("antlerless_odds_row_start")),
        "antlerless_odds_title": _prefer(base.get("antlerless_odds_title")),
        "has_antlerless_odds_page": _prefer(base.get("has_antlerless_odds_page"), "FALSE"),
        "has_any_odds_source": "TRUE" if has_draw_source == "TRUE" else _prefer(base.get("has_any_odds_source"), "FALSE"),
        "permits_2026_source": _prefer(engine_row.get("permits_2026_source"), base.get("permits_2026_source")),
        "public_permits_2026_source": _prefer(engine_row.get("public_permits_2026_source"), base.get("public_permits_2026_source")),
        "permit_status": _prefer(engine_row.get("permit_status"), base.get("permit_status")),
        "permit_allocation_type": _prefer(engine_row.get("permit_allocation_type"), base.get("permit_allocation_type")),
        "permit_source_authority": _prefer(engine_row.get("permit_source_authority"), base.get("permit_source_authority")),
        "permit_note": _prefer(engine_row.get("permit_note"), base.get("permit_note")),
        "permit_overlay_source": _prefer(engine_row.get("permit_overlay_source"), base.get("permit_overlay_source")),
        "data_status": _prefer(engine_row.get("data_status"), base.get("data_status")),
        "permits_2026_conservation": _prefer(base.get("permits_2026_conservation")),
        "permits_2026_expo": _prefer(base.get("permits_2026_expo")),
        "permits_2026_sportsman": _prefer(engine_row.get("sportsman_permit_count"), base.get("permits_2026_sportsman")),
        "special_permit_area_id": _prefer(base.get("special_permit_area_id")),
        "special_permit_category": _prefer(base.get("special_permit_category")),
        "special_permit_note": _prefer(base.get("special_permit_note")),
        "special_permit_overlay_source": _prefer(base.get("special_permit_overlay_source")),
        "boundary_id": _prefer(base.get("boundary_id"), db_row.get("boundary_id")),
        "draw_pool": draw_pool,
    })
    return row


def _synth_ladder_row(
    engine_row: dict[str, str],
    base: dict[str, str],
    db_row: dict[str, str],
    headers: list[str],
) -> dict[str, str]:
    row = {header: _clean(base.get(header)) for header in headers}
    draw_pool = _norm_draw_pool(engine_row.get("draw_pool"))
    p_draw_pct = _prefer(engine_row.get("p_draw_pct"), engine_row.get("display_odds_pct"))
    row.update({
        "hunt_code": _clean(engine_row.get("hunt_code")),
        "residency": _norm_residency(engine_row.get("residency")),
        "points": _clean(engine_row.get("points")),
        "public_permits_2025": _prefer(engine_row.get("public_permits_2025"), base.get("public_permits_2025")),
        "public_permits_2026": _prefer(engine_row.get("public_permits_2026"), base.get("public_permits_2026")),
        "public_permits_2026_source": _prefer(engine_row.get("public_permits_2026_source"), base.get("public_permits_2026_source")),
        "max_point_permits_2025": _prefer(base.get("max_point_permits_2025")),
        "max_point_permits_2026": _prefer(engine_row.get("max_point_permits_2026"), base.get("max_point_permits_2026")),
        "random_permits_2025": _prefer(base.get("random_permits_2025")),
        "random_permits_2026": _prefer(engine_row.get("random_permits_2026"), base.get("random_permits_2026")),
        "guaranteed_at_2025": _prefer(base.get("guaranteed_at_2025")),
        "guaranteed_at_2026": _prefer(engine_row.get("guaranteed_at_2026"), base.get("guaranteed_at_2026")),
        "permit_delta_2025_to_2026": _prefer(base.get("permit_delta_2025_to_2026")),
        "projected_applicants_2026_source": _prefer(engine_row.get("projected_applicants_2026_source"), base.get("projected_applicants_2026_source")),
        "guaranteed_delta_2025_to_2026": _prefer(base.get("guaranteed_delta_2025_to_2026")),
        "applicants_above": _prefer(engine_row.get("applicants_above"), base.get("applicants_above")),
        "applicants_at_level": _prefer(engine_row.get("applicants_at_level"), base.get("applicants_at_level")),
        "random_draw_odds_2026": _prefer(p_draw_pct, base.get("random_draw_odds_2026")),
        "gap": _prefer(engine_row.get("gap"), base.get("gap")),
        "delta_gap": _prefer(engine_row.get("delta_gap"), base.get("delta_gap")),
        "status": _prefer(engine_row.get("algorithm_status"), base.get("status")),
        "algorithm_status": _prefer(engine_row.get("algorithm_status"), base.get("algorithm_status")),
        "trend": _prefer(engine_row.get("trend"), base.get("trend")),
        "draw_outlook": _prefer(engine_row.get("draw_outlook"), base.get("draw_outlook"), "MODEL PENDING"),
        "permits_2026_res": _prefer(engine_row.get("permits_2026_res"), base.get("permits_2026_res")),
        "permits_2026_nr": _prefer(engine_row.get("permits_2026_nr"), base.get("permits_2026_nr")),
        "permits_2026_total": _prefer(engine_row.get("permits_2026_total"), base.get("permits_2026_total")),
        "permits_2026_source": _prefer(engine_row.get("permits_2026_source"), base.get("permits_2026_source")),
        "permit_status": _prefer(engine_row.get("permit_status"), base.get("permit_status")),
        "permit_allocation_type": _prefer(engine_row.get("permit_allocation_type"), base.get("permit_allocation_type")),
        "permit_source_authority": _prefer(engine_row.get("permit_source_authority"), base.get("permit_source_authority")),
        "permit_note": _prefer(engine_row.get("permit_note"), base.get("permit_note")),
        "permit_overlay_source": _prefer(engine_row.get("permit_overlay_source"), base.get("permit_overlay_source"), str(DATABASE_PATH.relative_to(REPO)).replace("\\", "/")),
        "data_status": _prefer(engine_row.get("data_status"), base.get("data_status")),
        "permits_2026_conservation": _prefer(base.get("permits_2026_conservation")),
        "permits_2026_expo": _prefer(base.get("permits_2026_expo")),
        "permits_2026_sportsman": _prefer(engine_row.get("sportsman_permit_count"), base.get("permits_2026_sportsman")),
        "special_permit_area_id": _prefer(base.get("special_permit_area_id")),
        "special_permit_category": _prefer(base.get("special_permit_category")),
        "special_permit_note": _prefer(base.get("special_permit_note")),
        "special_permit_overlay_source": _prefer(base.get("special_permit_overlay_source")),
        "boundary_id": _prefer(base.get("boundary_id"), db_row.get("boundary_id")),
        "draw_pool": draw_pool,
        "draw_2026_system_type": _prefer(engine_row.get("draw_system_type"), base.get("draw_2026_system_type")),
        "draw_system_type": _prefer(engine_row.get("draw_system_type"), base.get("draw_system_type")),
        "display_odds_text": _prefer(engine_row.get("display_odds_text"), base.get("display_odds_text")),
    })
    return row


def _is_targeted_youth_any_bull_row(row: dict[str, str]) -> bool:
    if _norm_code(row.get("hunt_code")) != "EB1007":
        return False
    draw_system_type = _norm_draw_system_type(row.get("draw_system_type") or row.get("draw_2026_system_type"))
    return draw_system_type in {"", "YOUTH_GENERAL_ANY_BULL_ELK"}


def main() -> None:
    engine_rows, _ = _read_csv(ENGINE_PATH)
    ladder_rows, ladder_headers = _read_csv(LADDER_PATH)
    master_rows, master_headers = _read_csv(MASTER_PATH)
    reference_rows, reference_headers = _read_csv(REFERENCE_PATH)
    database_rows, _ = _read_csv(DATABASE_PATH)

    if "draw_pool" not in master_headers:
        master_headers.append("draw_pool")

    ladder_rows = [row for row in ladder_rows if not _is_targeted_youth_any_bull_row(row)]
    master_rows = [row for row in master_rows if not _is_targeted_youth_any_bull_row(row)]
    reference_rows = [row for row in reference_rows if not _is_targeted_youth_any_bull_row(row)]

    db_lookup = _build_database_lookup(database_rows)

    master_by_group = {_group_key(row): row for row in master_rows}
    master_by_code_res = {(_norm_code(row.get("hunt_code")), _norm_residency(row.get("residency"))): row for row in master_rows}
    master_by_code = {}
    for row in master_rows:
        code = _norm_code(row.get("hunt_code"))
        if code and code not in master_by_code:
            master_by_code[code] = row

    reference_by_group = {_group_key(row): row for row in reference_rows}
    reference_by_code_res = {(_norm_code(row.get("hunt_code")), _norm_residency(row.get("residency"))): row for row in reference_rows}
    reference_by_code = {}
    for row in reference_rows:
        code = _norm_code(row.get("hunt_code"))
        if code and code not in reference_by_code:
            reference_by_code[code] = row

    ladder_group_keys = {_group_key(row) for row in ladder_rows}
    master_group_keys = {_group_key(row) for row in master_rows}
    reference_group_keys = {_group_key(row) for row in reference_rows}

    missing_ladder_groups_before = sorted({_group_key(row) for row in engine_rows if _group_key(row) not in ladder_group_keys})
    missing_master_groups_before = sorted({_group_key(row) for row in engine_rows if _group_key(row) not in master_group_keys})
    missing_reference_groups_before = sorted({_group_key(row) for row in engine_rows if _group_key(row) not in reference_group_keys})

    appended_master = 0
    appended_reference = 0
    appended_ladder = 0

    for engine_row in engine_rows:
        group = _group_key(engine_row)
        code, residency, _ = group
        db_row = db_lookup.get(code, {})

        if group not in master_group_keys:
            base = _base_row_for(code, residency, master_rows, master_by_group, master_by_code_res, master_by_code)
            master_rows.append(_synth_master_row(engine_row, base, db_row, master_headers))
            master_group_keys.add(group)
            appended_master += 1

        if group not in ladder_group_keys:
            base = _base_row_for(code, residency, ladder_rows, {}, {}, master_by_code)
            ladder_rows.append(_synth_ladder_row(engine_row, base, db_row, ladder_headers))
            ladder_group_keys.add(group)
            appended_ladder += 1

        if group not in reference_group_keys:
            base = _base_row_for(code, residency, reference_rows, reference_by_group, reference_by_code_res, reference_by_code)
            reference_rows.append(_synth_reference_row(engine_row, base, db_row, reference_headers))
            reference_group_keys.add(group)
            appended_reference += 1

    master_rows.sort(key=lambda row: (_norm_code(row.get("hunt_code")), _norm_residency(row.get("residency")), _norm_draw_pool(row.get("draw_pool")), _clean(row.get("points"))))
    ladder_rows.sort(key=lambda row: (_norm_code(row.get("hunt_code")), _norm_residency(row.get("residency")), _norm_draw_pool(row.get("draw_pool")), _clean(row.get("points"))))
    reference_rows.sort(key=lambda row: (_norm_code(row.get("hunt_code")), _norm_residency(row.get("residency")), _norm_draw_pool(row.get("draw_pool"))))

    _write_csv(MASTER_PATH, master_rows, master_headers)
    _write_csv(LADDER_PATH, ladder_rows, ladder_headers)
    _write_csv(REFERENCE_PATH, reference_rows, reference_headers)

    master_group_keys_after = {_group_key(row) for row in master_rows}
    ladder_group_keys_after = {_group_key(row) for row in ladder_rows}
    reference_group_keys_after = {_group_key(row) for row in reference_rows}

    missing_master_groups_after = sorted({_group_key(row) for row in engine_rows if _group_key(row) not in master_group_keys_after})
    missing_ladder_groups_after = sorted({_group_key(row) for row in engine_rows if _group_key(row) not in ladder_group_keys_after})
    missing_reference_groups_after = sorted({_group_key(row) for row in engine_rows if _group_key(row) not in reference_group_keys_after})

    missing_draw_systems_before = Counter(
        _clean(row.get("draw_system_type")) for row in engine_rows if _group_key(row) in set(missing_master_groups_before) | set(missing_ladder_groups_before) | set(missing_reference_groups_before)
    )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "active_repo": str(REPO),
        "source_files": {
            "engine": str(ENGINE_PATH.relative_to(REPO)).replace("\\", "/"),
            "ladder": str(LADDER_PATH.relative_to(REPO)).replace("\\", "/"),
            "master": str(MASTER_PATH.relative_to(REPO)).replace("\\", "/"),
            "reference": str(REFERENCE_PATH.relative_to(REPO)).replace("\\", "/"),
            "database": str(DATABASE_PATH.relative_to(REPO)).replace("\\", "/"),
        },
        "rows": {
            "engine": len(engine_rows),
            "ladder": len(ladder_rows),
            "master": len(master_rows),
            "reference": len(reference_rows),
        },
        "engine_group_count": len({_group_key(row) for row in engine_rows}),
        "engine_hunt_code_count": len({_norm_code(row.get("hunt_code")) for row in engine_rows if _norm_code(row.get("hunt_code"))}),
        "missing_groups_before": {
            "ladder": len(missing_ladder_groups_before),
            "master": len(missing_master_groups_before),
            "reference": len(missing_reference_groups_before),
            "draw_system_type_counts": dict(sorted(missing_draw_systems_before.items())),
        },
        "appended_rows": {
            "ladder": appended_ladder,
            "master": appended_master,
            "reference": appended_reference,
        },
        "missing_groups_after": {
            "ladder": len(missing_ladder_groups_after),
            "master": len(missing_master_groups_after),
            "reference": len(missing_reference_groups_after),
        },
        "families_promoted_online": {
            "sportsman_groups": sum(1 for row in engine_rows if _clean(row.get("draw_system_type")) == "SPORTSMAN_PERMIT"),
            "mountain_lion_groups": len({group for group in {_group_key(row) for row in engine_rows} if group[0].startswith("CG")}),
            "dedicated_hunter_groups": len({group for group in {_group_key(row) for row in engine_rows} if group[2] == "dedicated_hunter"}),
            "youth_groups": len({group for group in {_group_key(row) for row in engine_rows} if group[2] == "youth"}),
        },
        "duplicate_keys": {
            "engine_hunt_residency_points": _dup_count(engine_rows, lambda row: (_norm_code(row.get("hunt_code")), _norm_residency(row.get("residency")), _clean(row.get("points")))),
            "ladder_hunt_residency_points_draw_pool": _dup_count(ladder_rows, _row_key),
            "master_hunt_residency_points_draw_pool": _dup_count(master_rows, _row_key),
            "reference_hunt_residency_draw_pool": _dup_count(reference_rows, _group_key),
        },
        "status": "PASS" if not (missing_master_groups_after or missing_ladder_groups_after or missing_reference_groups_after) else "FAIL",
        "sample_groups_added": {
            "ladder": [list(group) for group in missing_ladder_groups_before[:10]],
            "master": [list(group) for group in missing_master_groups_before[:10]],
            "reference": [list(group) for group in missing_reference_groups_before[:10]],
        },
    }

    OUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# Online Runtime Cross-Check",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- Status: `{report['status']}`",
        f"- Engine groups: `{report['engine_group_count']}`",
        f"- Missing before sync: ladder `{report['missing_groups_before']['ladder']}`, master `{report['missing_groups_before']['master']}`, reference `{report['missing_groups_before']['reference']}`",
        f"- Appended rows: ladder `{appended_ladder}`, master `{appended_master}`, reference `{appended_reference}`",
        f"- Missing after sync: ladder `{report['missing_groups_after']['ladder']}`, master `{report['missing_groups_after']['master']}`, reference `{report['missing_groups_after']['reference']}`",
        "",
        "## Draw-System Counts",
        "",
    ]
    for draw_system_type, count in report["missing_groups_before"]["draw_system_type_counts"].items():
        lines.append(f"- `{draw_system_type}`: `{count}`")
    lines.extend(
        [
            "",
            "## Duplicate Keys",
            "",
        ]
    )
    for key, value in report["duplicate_keys"].items():
        lines.append(f"- `{key}`: `{value}`")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
