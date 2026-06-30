"""Audit targeted 2026 black bear hunt-code crosswalk candidates.

This is intentionally narrow.  It checks the seven 2026 bear codes that can
look like history gaps in a blind 2025->2026 run and separates true recodes
from new/current split rows that should not borrow a neighboring hunt's
history.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd


REPO = Path(__file__).resolve().parents[1]
TARGET_CODES = ["BR7021", "BR7126", "BR7238", "BR7022", "BR7127", "BR7239", "BR7326"]
RELATED_CODES = TARGET_CODES + ["BR7008", "BR7108", "BR7208", "BR7307"]
LOCKED_HAND_AUDITED_CROSSWALK = {
    "BR7022": "BR7008",
    "BR7127": "BR7108",
    "BR7239": "BR7208",
    "BR7326": "BR7307",
}

DATABASE = REPO / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
DRAW_RESULTS_LONG = REPO / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
BEAR_CROSSWALK = REPO / "data_truth" / "crosswalk_truth" / "normalized" / "black_bear_BR_2024_2025_2026_crosswalk.csv"
HUNT_PLANNER_XLSX = (
    REPO
    / "outputs"
    / "20260626_fresh_2026_source_species_docs"
    / "hunt_planner_xlsx"
    / "2026_HUNTPLANNER__black_bear.xlsx"
)
DRAW_ODDS_XLSX = (
    REPO
    / "outputs"
    / "20260626_fresh_2026_source_species_docs"
    / "draw_odds_xlsx"
    / "2026_DRAWDODDS__black_bear.xlsx"
)

OUT_CSV = REPO / "processed_data" / "bear_2026_target_hunt_code_crosswalk_audit.csv"
OUT_JSON = REPO / "processed_data" / "bear_2026_target_hunt_code_crosswalk_audit_summary.json"
OUT_MD = REPO / "processed_data" / "bear_2026_target_hunt_code_crosswalk_audit.md"


def clean(value: object) -> str:
    return str(value or "").strip()


def norm_text(value: object) -> str:
    text = clean(value).lower()
    text = text.replace("&", " and ")
    text = re.sub(r"\bmtns?\b", "mountains", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def norm_hunt_name(value: object) -> str:
    text = norm_text(value)
    text = re.sub(r"\bblack bear\b", "", text)
    text = re.sub(r"\bany legal weapon\b", "", text)
    text = re.sub(r"\blimited entry\b", "", text)
    text = re.sub(r"\bmultiseason\b|\bmulti season\b", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if text in {"la sal mountains", "la sal mtns"}:
        return "la sal"
    return text


def norm_weapon(value: object, hunt_type: object = "", season: object = "") -> str:
    joined = " ".join([clean(value), clean(hunt_type), clean(season)]).lower()
    if "multi" in joined and "season" in joined:
        return "any legal weapon"
    if "any legal weapon" in joined:
        return "any legal weapon"
    if "pursuit" in joined:
        return "pursuit only"
    return norm_text(value)


def season_family(code: object, hunt_type: object = "", season: object = "") -> str:
    text = " ".join([clean(hunt_type), clean(season)]).lower()
    code_text = clean(code).upper()
    if "multi" in text or code_text.startswith("BR73"):
        return "multiseason"
    if "spring" in text or code_text.startswith("BR70"):
        return "spring"
    if "summer" in text or code_text.startswith("BR71"):
        return "summer"
    if "fall" in text or code_text.startswith("BR72"):
        return "fall"
    if "pursuit" in text or code_text.startswith("BR10"):
        return "pursuit"
    return ""


def to_int(value: object) -> int:
    text = clean(value)
    if not text:
        return 0
    try:
        return int(float(text))
    except Exception:
        return 0


def quota_tuple(row: pd.Series, prefix: str) -> tuple[int, int, int]:
    return (
        to_int(row.get(f"{prefix}_res")),
        to_int(row.get(f"{prefix}_nr")),
        to_int(row.get(f"{prefix}_total")),
    )


def load_target_sources() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    db = pd.read_csv(DATABASE, low_memory=False)
    db = db[db["hunt_code"].astype(str).str.upper().isin(TARGET_CODES)].copy()

    crosswalk = pd.read_csv(BEAR_CROSSWALK, low_memory=False)
    crosswalk = crosswalk[
        crosswalk["current_2026_code"].astype(str).str.upper().isin(RELATED_CODES)
        | crosswalk["historical_2025_code"].astype(str).str.upper().isin(RELATED_CODES)
        | crosswalk["historical_2024_code"].astype(str).str.upper().isin(RELATED_CODES)
    ].copy()

    hp = pd.read_excel(HUNT_PLANNER_XLSX, sheet_name="Table 1")
    hp = hp[hp["hunt_code"].astype(str).str.upper().isin(TARGET_CODES)].copy()

    odds = pd.read_excel(DRAW_ODDS_XLSX, sheet_name="Table 1")
    odds = odds[odds["hunt_code"].astype(str).str.upper().isin(TARGET_CODES)].copy()

    long_cols = [
        "actual_draw_year",
        "hunt_code",
        "hunt_name",
        "species",
        "sex_type",
        "hunt_type",
        "weapon",
        "season",
        "residency",
        "points",
        "eligible_applicants",
        "total_permits",
        "source_file",
    ]
    long = pd.read_csv(DRAW_RESULTS_LONG, usecols=lambda c: c in long_cols, low_memory=False)
    long = long[long["hunt_code"].astype(str).str.upper().str.startswith("BR", na=False)].copy()
    return db, crosswalk, hp, odds, long


def summarize_2026_odds(odds: pd.DataFrame) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    if odds.empty:
        return summary
    odds = odds.copy()
    odds["hunt_code"] = odds["hunt_code"].astype(str).str.upper()
    for code, group in odds.groupby("hunt_code"):
        summary[code] = {
            "draw_odds_rows_2026": int(len(group)),
            "draw_odds_resident_applicants_2026": int(group.loc[group["residency"].astype(str).str.lower() == "resident", "eligible_applicants"].fillna(0).sum()),
            "draw_odds_nonresident_applicants_2026": int(group.loc[group["residency"].astype(str).str.lower() == "nonresident", "eligible_applicants"].fillna(0).sum()),
            "draw_odds_successful_2026": int(group["successful_total"].fillna(0).sum()),
        }
    return summary


def historical_candidate_summary(long: pd.DataFrame) -> dict[str, list[dict[str, object]]]:
    related = long[long["hunt_code"].astype(str).str.upper().isin(RELATED_CODES)].copy()
    related["actual_draw_year"] = pd.to_numeric(related["actual_draw_year"], errors="coerce").fillna(0).astype(int)
    related = related[related["actual_draw_year"] <= 2025]
    out: dict[str, list[dict[str, object]]] = {}
    for code, group in related.groupby(related["hunt_code"].astype(str).str.upper()):
        years = sorted(int(y) for y in group["actual_draw_year"].dropna().unique())
        latest_year = max(years) if years else 0
        latest = group[group["actual_draw_year"] == latest_year].iloc[0] if latest_year else group.iloc[0]
        out[code] = [
            {
                "historical_code": code,
                "history_years": ",".join(str(y) for y in years),
                "latest_history_year": latest_year,
                "historical_hunt_name": clean(latest.get("hunt_name")),
                "historical_hunt_type": clean(latest.get("hunt_type")),
                "historical_weapon": clean(latest.get("weapon")),
                "historical_season_family": season_family(code, latest.get("hunt_type"), latest.get("season")),
                "historical_name_norm": norm_hunt_name(latest.get("hunt_name")),
                "historical_weapon_norm": norm_weapon(latest.get("weapon"), latest.get("hunt_type"), latest.get("season")),
            }
        ]
    return out


def main() -> None:
    db, crosswalk, hp, odds, long = load_target_sources()
    odds_summary = summarize_2026_odds(odds)
    historical = historical_candidate_summary(long)

    crosswalk_by_current = {
        clean(row.current_2026_code).upper(): row
        for row in crosswalk.itertuples(index=False)
        if clean(getattr(row, "current_2026_code", "")).upper()
    }

    live_current_codes = set(
        pd.read_csv(DATABASE, usecols=["hunt_code"], low_memory=False)["hunt_code"].astype(str).str.upper()
    )

    rows: list[dict[str, object]] = []
    for code in TARGET_CODES:
        db_row = db[db["hunt_code"].astype(str).str.upper() == code]
        hp_row = hp[hp["hunt_code"].astype(str).str.upper() == code]
        source_row = hp_row.iloc[0] if not hp_row.empty else db_row.iloc[0]
        current_name = clean(source_row.get("hunt_name"))
        current_hunt_type = clean(source_row.get("hunt_type"))
        current_weapon = clean(source_row.get("weapon"))
        current_season = clean(source_row.get("season"))
        current_name_norm = norm_hunt_name(current_name)
        current_weapon_norm = norm_weapon(current_weapon, current_hunt_type, current_season)
        current_season_family = season_family(code, current_hunt_type, current_season)

        cw = crosswalk_by_current.get(code)
        status = clean(getattr(cw, "mapping_status", "")) if cw is not None else "NO_CROSSWALK_ROW"
        confidence = clean(getattr(cw, "mapping_confidence", "")) if cw is not None else ""
        candidate_code = clean(getattr(cw, "historical_2025_code", "")) if cw is not None else ""
        if not candidate_code:
            candidate_code = clean(getattr(cw, "historical_2024_code", "")) if cw is not None else ""

        candidate = {}
        if candidate_code:
            candidate_list = historical.get(candidate_code.upper(), [])
            candidate = candidate_list[0] if candidate_list else {}

        locked_history_code = LOCKED_HAND_AUDITED_CROSSWALK.get(code, "")
        if locked_history_code:
            engine_action = "ALIAS_TO_HISTORICAL_CODE"
            engine_history_code = locked_history_code
            reason = f"Hand-audited DWR source lock: historical {locked_history_code} crosswalks to current {code}."
            if code == "BR7326":
                reason += " BR7307 is reused for conservation in 2026."
        elif status == "CURRENT_SPLIT_CHILD_NO_PRIOR_DRAW_ROW":
            engine_action = "DO_NOT_ALIAS_CURRENT_SPLIT_CHILD"
            engine_history_code = ""
            reason = "No tight historical hunt-name/code predecessor; treat as current 2026 split/addition and use 2026 draw-result history for 2027+."
        else:
            engine_action = "DO_NOT_ALIAS_ACTIVE_CODE_COLLISION"
            engine_history_code = ""
            reason = "A plausible older La Sal code still exists as an active 2026 hunt code, so borrowing that history would double-feed two current hunts."

        if code == "BR7326":
            collision_code = "BR7307"
        elif current_season_family == "spring":
            collision_code = "BR7008"
        elif current_season_family == "summer":
            collision_code = "BR7108"
        elif current_season_family == "fall":
            collision_code = "BR7208"
        else:
            collision_code = ""

        if collision_code and collision_code in live_current_codes and engine_action != "ALIAS_TO_HISTORICAL_CODE":
            reason += f" Related historical-looking code {collision_code} is not used as this row's predecessor under the hand-audited crosswalk lock."

        q = quota_tuple(source_row, "permits")
        rows.append(
            {
                "current_2026_code": code,
                "current_hunt_name": current_name,
                "current_hunt_name_norm": current_name_norm,
                "species": clean(source_row.get("species")),
                "sex_type": clean(source_row.get("sex_type")),
                "current_hunt_type": current_hunt_type,
                "current_weapon": current_weapon,
                "current_weapon_norm": current_weapon_norm,
                "current_season_family": current_season_family,
                "current_season": current_season,
                "current_permits_res": q[0],
                "current_permits_nr": q[1],
                "current_permits_total": q[2],
                "crosswalk_status": status,
                "crosswalk_confidence": confidence,
                "candidate_historical_code": candidate_code.upper(),
                "candidate_history_years": candidate.get("history_years", ""),
                "candidate_hunt_name": candidate.get("historical_hunt_name", ""),
                "candidate_hunt_name_norm": candidate.get("historical_name_norm", ""),
                "candidate_weapon": candidate.get("historical_weapon", ""),
                "candidate_weapon_norm": candidate.get("historical_weapon_norm", ""),
                "candidate_season_family": candidate.get("historical_season_family", ""),
                "engine_action": engine_action,
                "engine_history_code": engine_history_code,
                "draw_odds_rows_2026": odds_summary.get(code, {}).get("draw_odds_rows_2026", 0),
                "draw_odds_resident_applicants_2026": odds_summary.get(code, {}).get("draw_odds_resident_applicants_2026", 0),
                "draw_odds_nonresident_applicants_2026": odds_summary.get(code, {}).get("draw_odds_nonresident_applicants_2026", 0),
                "draw_odds_successful_2026": odds_summary.get(code, {}).get("draw_odds_successful_2026", 0),
                "reason": reason,
            }
        )

    out = pd.DataFrame(rows)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_CSV, index=False)

    summary = {
        "target_codes": TARGET_CODES,
        "row_count": int(len(out)),
        "engine_action_counts": out["engine_action"].value_counts().to_dict(),
        "alias_rows": out[out["engine_action"] == "ALIAS_TO_HISTORICAL_CODE"][["current_2026_code", "engine_history_code"]].to_dict("records"),
        "source_files": {
            "database": str(DATABASE.relative_to(REPO)).replace("\\", "/"),
            "draw_results_long": str(DRAW_RESULTS_LONG.relative_to(REPO)).replace("\\", "/"),
            "bear_crosswalk": str(BEAR_CROSSWALK.relative_to(REPO)).replace("\\", "/"),
            "hunt_planner_xlsx": str(HUNT_PLANNER_XLSX.relative_to(REPO)).replace("\\", "/"),
            "draw_odds_xlsx": str(DRAW_ODDS_XLSX.relative_to(REPO)).replace("\\", "/"),
        },
        "weapon_normalization_rule": "Any Legal Weapon and multiseason/multi-season rows normalize to any legal weapon for alignment; season family remains confidence metadata.",
    }
    OUT_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    md_lines = [
        "# Bear 2026 Target Hunt-Code Crosswalk Audit",
        "",
        f"- Target rows audited: `{len(out)}`.",
        f"- Alias to historical code: `{summary['engine_action_counts'].get('ALIAS_TO_HISTORICAL_CODE', 0)}`.",
        f"- Current split/new rows not aliased: `{summary['engine_action_counts'].get('DO_NOT_ALIAS_CURRENT_SPLIT_CHILD', 0)}`.",
        f"- Active-code collision rows not aliased: `{summary['engine_action_counts'].get('DO_NOT_ALIAS_ACTIVE_CODE_COLLISION', 0)}`.",
        "",
        "Weapon normalization: Any Legal Weapon and multiseason/multi-season normalize together for alignment; season family remains confidence metadata.",
        "",
        "| current code | current hunt | season family | permits | action | history code | reason |",
        "|---|---|---:|---:|---|---|---|",
    ]
    for row in rows:
        permits = f"{row['current_permits_res']}/{row['current_permits_nr']}/{row['current_permits_total']}"
        md_lines.append(
            f"| {row['current_2026_code']} | {row['current_hunt_name']} | {row['current_season_family']} | "
            f"{permits} | {row['engine_action']} | {row['engine_history_code']} | {row['reason']} |"
        )
    OUT_MD.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
