from __future__ import annotations

import csv
import difflib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDITS = ROOT / "processed_data" / "audits"
DATABASE = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"

YEARS = [2020, 2021, 2022, 2023, 2024, 2025, 2026]
PRESENCE = AUDITS / "hunt_code_presence_matrix_comprehensive_2020_2026.csv"
ARTIFACT_FILTER = AUDITS / "hunt_code_lifecycle_prefix_artifact_filter_comprehensive_2020_2026.csv"

OUT_CROSSWALK = AUDITS / "hunt_code_year_to_year_crosswalk_2020_2026.csv"
OUT_CANDIDATES = AUDITS / "hunt_code_year_to_year_crosswalk_candidates_2020_2026.csv"
OUT_SUMMARY = AUDITS / "hunt_code_year_to_year_crosswalk_2020_2026_summary.json"
OUT_REVIEWED_DECISIONS = AUDITS / "hunt_code_year_to_year_reviewed_decisions_2020_to_2021.csv"
OUT_REVIEWED_DECISIONS_2021_2022 = AUDITS / "hunt_code_year_to_year_reviewed_decisions_2021_to_2022.csv"
OUT_REVIEWED_DECISIONS_2022_2023 = AUDITS / "hunt_code_year_to_year_reviewed_decisions_2022_to_2023.csv"
OUT_REPORT = ROOT / "docs" / "hunt_code_year_to_year_crosswalk_2020_2026.md"

REVIEWED_DISCONTINUED_AFTER_2020 = {
    "DB1009": "2021 big-game application guide explicitly states all Henry Mtns management buck deer hunts were discontinued for the 2021 season.",
    "DB1051": "2021 big-game application guide explicitly states all Henry Mtns management buck deer hunts were discontinued for the 2021 season.",
    "DB1052": "2021 big-game application guide explicitly states all Henry Mtns management buck deer hunts were discontinued for the 2021 season.",
    "PB5333": "2021 big-game application guide explicitly states Parker Mtn pronghorn hunts were discontinued for the 2021 season; do not crosswalk to Plateau Highlands.",
    "PB5334": "2021 big-game application guide explicitly states Parker Mtn pronghorn hunts were discontinued for the 2021 season; do not crosswalk to Plateau Highlands.",
    "PB5335": "2021 big-game application guide explicitly states Parker Mtn pronghorn hunts were discontinued for the 2021 season; do not crosswalk to Plateau Highlands.",
    "BI6515": "2020 bison source/harvest-confirmed; absent from 2021 regulation and year-document checks; no safe 2021 successor.",
    "BI6522": "2020 bison source/harvest-confirmed; absent from 2021 regulation and year-document checks; no safe 2021 successor.",
    "DA1005": "2020 antlerless deer harvest-confirmed; absent from 2021 regulation/year-document checks; no safe 2021 successor.",
    "DA1036": "2020 antlerless deer harvest-confirmed; absent from 2021 regulation/year-document checks; no safe 2021 successor.",
    "DS6619": "2020 application-guide and harvest-confirmed desert bighorn Zion archery row; absent from 2021 checks; no safe successor.",
    "MA1004": "2020 doe pronghorn harvest-confirmed; absent from 2021 regulation/year-document checks; no safe 2021 successor.",
    "PD1001": "2020 pronghorn doe harvest-confirmed; absent from 2021 regulation/year-document checks; no safe 2021 successor.",
    "PD1028": "2020 pronghorn doe harvest-confirmed; absent from 2021 regulation/year-document checks; no safe 2021 successor.",
    "PD1029": "2020 pronghorn doe harvest-confirmed; absent from 2021 regulation/year-document checks; no safe 2021 successor.",
    "PD1040": "2020 pronghorn doe harvest-confirmed; absent from 2021 regulation/year-document checks; no safe 2021 successor.",
    "RS6702": "2020 application-guide and harvest-confirmed Rocky Mountain bighorn Box Elder Pilot Mtn row; absent from 2021 checks; no safe successor.",
}

REVIEWED_2020_TO_2021_COUGAR_ACTIVE_CONTINUITY = {
    "CG1030": "Official 2020-21 cougar guide confirms exact-code active continuity.",
    "CG7613": "Official 2020-21 cougar guide confirms exact-code active continuity.",
    "CG7615": "Official 2020-21 cougar guide confirms exact-code active continuity.",
    "CG7619": "Official 2020-21 cougar guide confirms exact-code active continuity.",
}

REVIEWED_2021_TO_2022_SUCCESSORS = {
    "BR7226": ("BR7208", "2022 bear guide p20 confirms La Sal fall limited-entry replacement row."),
    "BR7227": ("BR7217", "2022 bear guide p20 confirms San Juan fall limited-entry replacement row."),
    "BR7230": ("BR7228", "2022 bear guide p20 confirms Cache/Ogden fall limited-entry replacement row."),
    "BR7231": ("BR7203", "2022 bear guide p20 confirms Central Mtns, Manti-North fall limited-entry replacement row."),
    "BR7232": ("BR7204", "2022 bear guide p20 confirms Central Mtns, Manti-South/San Rafael, North fall limited-entry replacement row."),
    "BR7233": ("BR7205", "2022 bear guide p20 confirms Central Mtns, Nebo fall limited-entry replacement row."),
    "BR7235": ("BR7229", "2022 bear guide p20 confirms Kamas/North Slope, Summit fall limited-entry replacement row."),
    "BR7236": ("BR7215", "2022 bear guide p20 confirms Plateau, Boulder/Kaiparowits fall limited-entry replacement row."),
}

REVIEWED_2021_TO_2022_COUGAR_ACTIVE_CONTINUITY = {
    "CG7503": "Official 2021-22 cougar guide confirms Morgan-South Rich exact-code active continuity.",
}

REVIEWED_2021_TO_2022_ARTIFACTS = {
    "CG9999": "Sportsman Cougar 2023* row appears in the 2021 BIBLE source set but statewide CG9999 is not the 2021->2022 cougar successor; rule says statewide cougar enters later.",
    "DS6612": "Source file is labeled 2021_PERMITS=2021_MODEL inside the 2021 folder; 2022 big-game app guide confirms Zion as DS6611, so DS6612 is treated as a source-year artifact rather than a true 2021 drop.",
}

REVIEWED_2021_TO_2022_ANTLERLESS_SUCCESSORS = {
    "DA1017": (
        "DA1009",
        "6",
        "2021 antlerless PDF confirms DA1017; 2022 antlerless draw-results PDF confirms reviewed successor DA1009 with exact same title/unit/weapon: Pine Valley, Enterprise any legal weapon. 2023 antlerless PDF confirms DA1009 persists.",
    ),
    "DA1029": (
        "DA1041",
        "19",
        "2021 antlerless PDF confirms DA1029; 2022 antlerless draw-results PDF confirms reviewed successor DA1041 for the same unit: Nine Mile, Green River Valley, with weapon structure changed from archery to any legal weapon. 2023 antlerless PDF confirms DA1041 persists.",
    ),
    "PD1027": (
        "PD1034|PD1035",
        "208|209",
        "2021 antlerless PDF confirms PD1027; 2022 antlerless draw-results PDF confirms reviewed split successor PD1034|PD1035 with exact same title/unit/weapon: Fillmore, Oak Creek South. 2023 antlerless PDF confirms both rows persist.",
    ),
}

REVIEWED_2021_TO_2022_ANTLERLESS_DISCONTINUED = {
    "DA1000": "2021 antlerless PDF confirms DA1000; 2022 and 2023 antlerless draw-results PDFs have no exact code and no same-unit successor for Beaver, Circleville North.",
    "DA1004": "2021 antlerless PDF confirms DA1004; 2022 and 2023 antlerless draw-results PDFs have no exact code and no same-unit successor for Mt Dutton, Circleville South.",
    "PD1013": "2021 antlerless PDF confirms PD1013; 2022 and 2023 antlerless draw-results PDFs have no exact code and no same-unit successor for CWMU Rabbit Creek doe pronghorn.",
    "PD1018": "2021 antlerless PDF confirms PD1018; 2022 and 2023 antlerless draw-results PDFs have no exact code and no same-unit successor for Mt Dutton/Paunsaugunt doe pronghorn.",
    "PD1023": "2021 antlerless PDF confirms PD1023; 2022 and 2023 antlerless draw-results PDFs have no exact code and no same-unit successor for CWMU George Creek doe pronghorn.",
    "PD1039": "2021 antlerless PDF confirms PD1039; 2022 and 2023 antlerless draw-results PDFs have no exact code and no same-unit successor for Panguitch Lake/Zion, North doe pronghorn.",
}

REVIEWED_2022_TO_2023_SPORTSMAN_ACTIVE_CONTINUITY = {
    "BI1000": "Sportsman Bison is a reviewed continuous sportsman permit hunt across analyzed years and remains an active sportsman permit family; preserve exact-code continuity.",
    "BR1000": "Sportsman Black Bear is a reviewed continuous sportsman permit hunt across analyzed years and remains an active sportsman permit family; preserve exact-code continuity.",
    "CG1000": "Sportsman Cougar is a reviewed continuous sportsman permit hunt across analyzed years and remains an active sportsman permit family; do not collapse it into CG9999 in the sportsman row set. Cougar regulations document the later general statewide/no-additional-permit structure separately from this sportsman draw-results row.",
    "DB0007": "Sportsman Deer is a reviewed continuous sportsman permit hunt across analyzed years and remains an active sportsman permit family; preserve exact-code continuity.",
    "DS1000": "Sportsman Desert Bighorn Sheep is a reviewed continuous sportsman permit hunt across analyzed years and remains an active sportsman permit family; preserve exact-code continuity.",
    "EB1000": "Sportsman Elk is a reviewed continuous sportsman permit hunt across analyzed years and remains an active sportsman permit family; preserve exact-code continuity.",
    "GO1000": "Sportsman Mountain Goat is a reviewed continuous sportsman permit hunt across analyzed years and remains an active sportsman permit family; preserve exact-code continuity.",
    "MB1000": "Sportsman Moose is a reviewed continuous sportsman permit hunt across analyzed years and remains an active sportsman permit family; preserve exact-code continuity.",
    "PB1000": "Sportsman Pronghorn is a reviewed continuous sportsman permit hunt across analyzed years and remains an active sportsman permit family; preserve exact-code continuity.",
    "RS0001": "Sportsman Rocky Mtn Bighorn Sheep is a reviewed continuous sportsman permit hunt across analyzed years and remains an active sportsman permit family; preserve exact-code continuity.",
    "TK0001": "Sportsman Bearded Turkey is a reviewed continuous sportsman permit hunt across analyzed years and remains an active sportsman permit family; preserve exact-code continuity.",
}

REVIEWED_2022_TO_2023_SPORTSMAN_SOURCE_FILES = {
    "CG1000": "C:/Users/tyler/Desktop/BIBLE HUNT CODES/2023/2023_sportsman_hunt_codes_clean.csv|C:/Users/tyler/Desktop/BIBLE HUNT CODES/2023/2023_sportsman_hunt_codes_clean_notes.md|C:/Users/tyler/Desktop/GitHub/HUNTS/pipeline/RAW/hunt_unit_database/2022/pdf/regulations/guidebook_2022-23_cougar.pdf|C:/Users/tyler/Desktop/GitHub/HUNTS/pipeline/RAW/hunt_unit_database/2023/pdf/regulations/2023-24_cougar.pdf|C:/Users/tyler/Desktop/GitHub/HUNTS/pipeline/RAW/hunt_unit_database/2024/pdf/regulation/2024_cougar.pdf",
}


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()


def norm_text(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", clean(value).lower()).strip()


def prefix_of(code: str) -> str:
    match = re.match(r"^([A-Z]+)", code or "")
    return match.group(1) if match else ""


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [{key: clean(value) for key, value in row.items()} for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = fieldnames or (list(rows[0].keys()) if rows else [])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def identity_key(row: dict[str, str]) -> str:
    return " | ".join(
        [
            norm_text(row.get("source_report_family")),
            norm_text(row.get("species")),
            norm_text(row.get("unit")),
            norm_text(row.get("weapon")),
            norm_text(row.get("hunt_name")),
        ]
    )


def identity_score(left: dict[str, str], right: dict[str, str]) -> float:
    left_key = identity_key(left)
    right_key = identity_key(right)
    if not left_key or not right_key:
        return 0.0
    return round(difflib.SequenceMatcher(None, left_key, right_key).ratio(), 4)


def match_quality(score: float, left: dict[str, str], right: dict[str, str]) -> str:
    same_species = norm_text(left.get("species")) and norm_text(left.get("species")) == norm_text(right.get("species"))
    same_unit = norm_text(left.get("unit")) and norm_text(left.get("unit")) == norm_text(right.get("unit"))
    same_weapon = norm_text(left.get("weapon")) and norm_text(left.get("weapon")) == norm_text(right.get("weapon"))
    if score >= 0.93 and same_species:
        return "HIGH_IDENTITY_MATCH"
    if score >= 0.84 and (same_species or same_unit):
        return "MEDIUM_IDENTITY_MATCH"
    if score >= 0.74:
        return "LOW_REVIEW_MATCH"
    if same_species and same_unit and same_weapon:
        return "STRUCTURE_MATCH_NAME_REVIEW"
    return "NO_SAFE_MATCH"


def read_presence() -> dict[int, set[str]]:
    rows = read_csv(PRESENCE)
    artifact_codes = artifact_filter_codes()
    by_year: dict[int, set[str]] = {year: set() for year in YEARS}
    for row in rows:
        code = row["hunt_code"]
        if code in artifact_codes:
            continue
        for year in YEARS:
            if row.get(f"present_report_year_{year}") == "YES":
                by_year[year].add(code)
    return by_year


def artifact_filter_codes() -> set[str]:
    rows = read_csv(ARTIFACT_FILTER)
    return {
        row["hunt_code"]
        for row in rows
        if row.get("hunt_code")
        and (
            row.get("action_taken", "").startswith("NORMALIZED_TO_")
            or row.get("action_taken") == "EXCLUDED_FROM_STRICT_LIFECYCLE_OUTPUTS"
        )
    }


def best_ledger_identity(rows: list[dict[str, str]]) -> dict[str, str]:
    if not rows:
        return {}
    # Prefer rows with parsed totals and strongest current DB name match if present.
    def score(row: dict[str, str]) -> tuple[int, float, int]:
        parse_ok = 1 if row.get("totals_parse_status") == "OK" else 0
        try:
            name_similarity = float(row.get("name_similarity_to_current_database") or 0)
        except ValueError:
            name_similarity = 0.0
        title_len = len(row.get("hunt_title_raw", ""))
        return parse_ok, name_similarity, title_len

    row = max(rows, key=score)
    return {
        "hunt_code": row.get("hunt_code", ""),
        "prefix": row.get("prefix") or prefix_of(row.get("hunt_code", "")),
        "hunt_name": row.get("hunt_title_raw") or row.get("current_database_hunt_name") or "",
        "species": row.get("species_inferred_from_prefix") or row.get("current_database_species") or "",
        "unit": row.get("unit_name_inferred") or row.get("current_database_hunt_name") or "",
        "weapon": row.get("weapon_or_last_segment_inferred") or row.get("current_database_weapon") or "",
        "source_report_family": row.get("source_report_family", ""),
        "source_file": row.get("source_file", ""),
        "source_page": row.get("source_report_page_printed") or row.get("source_pdf_page_index") or "",
        "identity_source": "BIBLE_HUNT_CODES_IDENTITY_LEDGER",
    }


def load_identities() -> dict[int, dict[str, dict[str, str]]]:
    identities: dict[int, dict[str, dict[str, str]]] = {year: {} for year in YEARS}
    for year in YEARS:
        ledger_path = AUDITS / f"hunt_code_year_identity_ledger_{year}.csv"
        if not ledger_path.exists():
            continue
        grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in read_csv(ledger_path):
            grouped[row["hunt_code"]].append(row)
        identities[year] = {code: best_ledger_identity(rows) for code, rows in grouped.items()}

    # The 2026 comprehensive source has code presence but no year-specific identity ledger.
    # Use current DATABASE identity only for codes that the comprehensive presence matrix says are present in 2026.
    by_year = read_presence()
    present_2026 = by_year[2026]
    db_rows = read_csv(DATABASE)
    for row in db_rows:
        code = row.get("hunt_code", "").upper()
        if not code or code not in present_2026:
            continue
        identities[2026][code] = {
            "hunt_code": code,
            "prefix": prefix_of(code),
            "hunt_name": row.get("hunt_name", ""),
            "species": row.get("species", ""),
            "unit": row.get("hunt_name", ""),
            "weapon": row.get("weapon", ""),
            "source_report_family": row.get("hunt_class") or row.get("hunt_type") or "",
            "source_file": "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv",
            "source_page": "",
            "identity_source": "CURRENT_DATABASE_2026_IDENTITY_FOR_PRESENT_2026_CODES",
        }
    return identities


def source_files_for(code: str, year: int) -> str:
    hits = read_csv(AUDITS / "hunt_code_source_hits_comprehensive_2020_2026.csv")
    return "|".join(sorted({row["source_file"] for row in hits if row["hunt_code"] == code and row["report_year"] == str(year)}))


def source_hit_maps() -> dict[tuple[str, int], dict[str, str]]:
    out: dict[tuple[str, int], dict[str, str]] = {}
    grouped: dict[tuple[str, int], dict[str, set[str]]] = defaultdict(lambda: {"files": set(), "pages": set(), "kinds": set()})
    for row in read_csv(AUDITS / "hunt_code_source_hits_comprehensive_2020_2026.csv"):
        key = (row["hunt_code"], int(row["report_year"]))
        grouped[key]["files"].add(row.get("source_file", ""))
        grouped[key]["pages"].add(row.get("source_page", ""))
        grouped[key]["kinds"].add(row.get("source_kind", ""))
    for key, values in grouped.items():
        out[key] = {
            "source_files": "|".join(sorted(value for value in values["files"] if value)),
            "source_pages": "|".join(sorted(value for value in values["pages"] if value)),
            "source_kinds": "|".join(sorted(value for value in values["kinds"] if value)),
        }
    return out


def candidate_links(
    from_code: str,
    to_codes: set[str],
    from_identity: dict[str, str],
    to_identities: dict[str, dict[str, str]],
    to_year: int,
) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    from_prefix = prefix_of(from_code)
    for to_code in sorted(to_codes):
        if prefix_of(to_code) != from_prefix:
            continue
        to_identity = to_identities.get(to_code, {})
        score = identity_score(from_identity, to_identity)
        quality = match_quality(score, from_identity, to_identity)
        if quality == "NO_SAFE_MATCH":
            continue
        candidates.append(
            {
                "to_hunt_code": to_code,
                "identity_score": score,
                "match_quality": quality,
                "to_hunt_name": to_identity.get("hunt_name", ""),
                "to_species": to_identity.get("species", ""),
                "to_unit": to_identity.get("unit", ""),
                "to_weapon": to_identity.get("weapon", ""),
            }
        )

    # Cougar successor rule is locked by docs/bible_hunt_codes_source_control.md.
    if from_prefix == "CG" and from_code != "CG9999" and "CG9999" in to_codes and to_year >= 2023:
        to_identity = to_identities.get("CG9999", {})
        candidates.append(
            {
                "to_hunt_code": "CG9999",
                "identity_score": 1.0,
                "match_quality": "COUGAR_SUCCESSOR_RULE",
                "to_hunt_name": to_identity.get("hunt_name") or "Cougar - Statewide",
                "to_species": to_identity.get("species") or "Cougar",
                "to_unit": to_identity.get("unit") or "Statewide",
                "to_weapon": to_identity.get("weapon") or "Any Legal Weapon",
            }
        )
    return sorted(candidates, key=lambda row: (str(row["match_quality"]) != "COUGAR_SUCCESSOR_RULE", -float(row["identity_score"]), str(row["to_hunt_code"])))


def build_crosswalk() -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    by_year = read_presence()
    identities = load_identities()
    source_hits = source_hit_maps()
    crosswalk_rows: list[dict[str, object]] = []
    candidate_rows: list[dict[str, object]] = []

    for from_year, to_year in zip(YEARS[:-1], YEARS[1:]):
        from_codes = by_year[from_year]
        to_codes = by_year[to_year]
        retained = from_codes & to_codes
        dropped = from_codes - to_codes
        added = to_codes - from_codes
        matched_added: set[str] = set()

        for code in sorted(retained):
            left = identities.get(from_year, {}).get(code, {})
            right = identities.get(to_year, {}).get(code, {})
            score = identity_score(left, right)
            quality = match_quality(score, left, right) if left and right else "EXACT_CODE_ONLY_IDENTITY_MISSING"
            hit_from = source_hits.get((code, from_year), {})
            hit_to = source_hits.get((code, to_year), {})
            crosswalk_rows.append(
                base_row(
                    from_year,
                    to_year,
                    code,
                    code,
                    "EXACT_CODE_RETAINED",
                    "EXACT_CODE",
                    score,
                    quality,
                    left,
                    right,
                    hit_from,
                    hit_to,
                    "Same hunt code observed in both adjacent report years.",
                )
            )

        for code in sorted(dropped):
            left = identities.get(from_year, {}).get(code, {"hunt_code": code, "prefix": prefix_of(code)})
            candidates = candidate_links(code, added, left, identities.get(to_year, {}), to_year)
            hit_from = source_hits.get((code, from_year), {})
            reviewed_discontinued_note = (
                REVIEWED_DISCONTINUED_AFTER_2020.get(code)
                if from_year == 2020 and to_year == 2021
                else None
            )
            reviewed_2020_2021_cougar_active_continuity_note = (
                REVIEWED_2020_TO_2021_COUGAR_ACTIVE_CONTINUITY.get(code)
                if from_year == 2020 and to_year == 2021
                else None
            )
            reviewed_2021_2022_successor = (
                REVIEWED_2021_TO_2022_SUCCESSORS.get(code)
                if from_year == 2021 and to_year == 2022
                else None
            )
            reviewed_2021_2022_cougar_active_continuity_note = (
                REVIEWED_2021_TO_2022_COUGAR_ACTIVE_CONTINUITY.get(code)
                if from_year == 2021 and to_year == 2022
                else None
            )
            reviewed_2021_2022_artifact_note = (
                REVIEWED_2021_TO_2022_ARTIFACTS.get(code)
                if from_year == 2021 and to_year == 2022
                else None
            )
            reviewed_2021_2022_antlerless_successor = (
                REVIEWED_2021_TO_2022_ANTLERLESS_SUCCESSORS.get(code)
                if from_year == 2021 and to_year == 2022
                else None
            )
            reviewed_2021_2022_antlerless_discontinued_note = (
                REVIEWED_2021_TO_2022_ANTLERLESS_DISCONTINUED.get(code)
                if from_year == 2021 and to_year == 2022
                else None
            )
            reviewed_2022_2023_sportsman_active_continuity_note = (
                REVIEWED_2022_TO_2023_SPORTSMAN_ACTIVE_CONTINUITY.get(code)
                if from_year == 2022 and to_year == 2023
                else None
            )
            if reviewed_discontinued_note:
                crosswalk_rows.append(
                    base_row(
                        from_year,
                        to_year,
                        code,
                        "",
                        "REVIEWED_DISCONTINUED_AFTER_2020_NO_SUCCESSOR",
                        "REVIEWED_DISCONTINUED",
                        "",
                        "NO_SAFE_MATCH_REVIEWED",
                        left,
                        {},
                        hit_from,
                        {},
                        reviewed_discontinued_note,
                    )
                )
            elif reviewed_2021_2022_successor:
                to_code, note = reviewed_2021_2022_successor
                matched_added.add(to_code)
                right = identities.get(to_year, {}).get(to_code, {"hunt_code": to_code, "prefix": prefix_of(to_code)})
                crosswalk_rows.append(
                    base_row(
                        from_year,
                        to_year,
                        code,
                        to_code,
                        "REVIEWED_SUCCESSOR_BY_2022_BEAR_GUIDE",
                        "REVIEWED_SUCCESSOR",
                        1.0,
                        "SAME_UNIT_SOURCE_GUIDE_MATCH",
                        left,
                        right,
                        hit_from,
                        {
                            "source_files": "C:/Users/tyler/Desktop/GitHub/HUNTS/pipeline/RAW/hunt_unit_database/2022/pdf/regulations/2022_bear.pdf",
                            "source_pages": "20",
                            "source_kinds": "regulations",
                        },
                        note,
                    )
                )
            elif reviewed_2021_2022_antlerless_successor:
                to_code, pages, note = reviewed_2021_2022_antlerless_successor
                to_codes = to_code.split("|")
                for matched_code in to_codes:
                    matched_added.add(matched_code)
                right = identities.get(to_year, {}).get(
                    to_codes[0],
                    {"hunt_code": to_codes[0], "prefix": prefix_of(to_codes[0])},
                )
                right = dict(right)
                right["hunt_code"] = to_code
                if "|" in to_code:
                    right["identity_source"] = "REVIEWED_2022_ANTLERLESS_DRAW_RESULTS_SPLIT_SUCCESSOR"
                crosswalk_rows.append(
                    base_row(
                        from_year,
                        to_year,
                        code,
                        to_code,
                        "REVIEWED_SUCCESSOR_BY_2022_ANTLERLESS_DRAW_RESULTS",
                        "REVIEWED_SUCCESSOR",
                        1.0,
                        "SAME_UNIT_SOURCE_GUIDE_MATCH",
                        left,
                        right,
                        hit_from,
                        {
                            "source_files": "C:/Users/tyler/Desktop/BIBLE HUNT CODES/2022/.pdf/2022_PERMITS=2023_MODEL__ANTLERLESS DRAW RESULTS.pdf",
                            "source_pages": pages,
                            "source_kinds": "draw_results",
                        },
                        note,
                    )
                )
            elif reviewed_2020_2021_cougar_active_continuity_note:
                right = dict(left)
                right["identity_source"] = "REVIEWED_2020_21_COUGAR_GUIDE"
                crosswalk_rows.append(
                    base_row(
                        from_year,
                        to_year,
                        code,
                        code,
                        "REVIEWED_2021_COUGAR_ACTIVE_CONTINUITY",
                        "REVIEWED_ACTIVE_COUGAR_GUIDE",
                        1.0,
                        "EXACT_CODE_EXTERNAL_SOURCE",
                        left,
                        right,
                        hit_from,
                        {
                            "source_files": "C:/Users/tyler/Desktop/GitHub/HUNTS/pipeline/RAW/hunt_unit_database/2021/pdf/regulations/2020-21_cougar.pdf",
                            "source_pages": "18",
                            "source_kinds": "regulations",
                        },
                        reviewed_2020_2021_cougar_active_continuity_note,
                    )
                )
            elif reviewed_2021_2022_cougar_active_continuity_note:
                right = dict(left)
                right["identity_source"] = "REVIEWED_2021_22_COUGAR_GUIDE"
                crosswalk_rows.append(
                    base_row(
                        from_year,
                        to_year,
                        code,
                        code,
                        "REVIEWED_2022_COUGAR_ACTIVE_CONTINUITY",
                        "REVIEWED_ACTIVE_COUGAR_GUIDE",
                        1.0,
                        "EXACT_CODE_EXTERNAL_SOURCE",
                        left,
                        right,
                        hit_from,
                        {
                            "source_files": "C:/Users/tyler/Desktop/GitHub/HUNTS/pipeline/RAW/hunt_unit_database/2022/pdf/regulations/2021-22_cougar.pdf",
                            "source_pages": "19|20",
                            "source_kinds": "regulations",
                        },
                        reviewed_2021_2022_cougar_active_continuity_note,
                    )
                )
            elif reviewed_2021_2022_artifact_note:
                crosswalk_rows.append(
                    base_row(
                        from_year,
                        to_year,
                        code,
                        "",
                        "REVIEWED_SOURCE_YEAR_ARTIFACT_NOT_TRUE_DROP",
                        "REVIEWED_ARTIFACT",
                        "",
                        "SOURCE_YEAR_ARTIFACT",
                        left,
                        {},
                        hit_from,
                        {},
                        reviewed_2021_2022_artifact_note,
                    )
                )
            elif reviewed_2021_2022_antlerless_discontinued_note:
                crosswalk_rows.append(
                    base_row(
                        from_year,
                        to_year,
                        code,
                        "",
                        "REVIEWED_DISCONTINUED_AFTER_2021_NO_2022_ANTLERLESS_SUCCESSOR",
                        "REVIEWED_DISCONTINUED",
                        "",
                        "NO_SAFE_MATCH_REVIEWED",
                        left,
                        {},
                        hit_from,
                        {
                            "source_files": "C:/Users/tyler/Desktop/BIBLE HUNT CODES/2022/.pdf/2022_PERMITS=2023_MODEL__ANTLERLESS DRAW RESULTS.pdf|C:/Users/tyler/Desktop/BIBLE HUNT CODES/2023/.pdf/2023_PERMITS=2024_MODEL__ANTLERLESS DRAW RESULTS.pdf",
                            "source_pages": "",
                            "source_kinds": "draw_results",
                        },
                        reviewed_2021_2022_antlerless_discontinued_note,
                    )
                )
            elif reviewed_2022_2023_sportsman_active_continuity_note:
                right = dict(left)
                right["identity_source"] = "REVIEWED_SPORTSMAN_ACTIVE_CONTINUITY"
                source_files = REVIEWED_2022_TO_2023_SPORTSMAN_SOURCE_FILES.get(
                    code,
                    "C:/Users/tyler/Desktop/BIBLE HUNT CODES/2023/.pdf/2023_PERMITS=2024_MODEL__SPORTSMAN DRAW RESULTS.pdf",
                )
                crosswalk_rows.append(
                    base_row(
                        from_year,
                        to_year,
                        code,
                        code,
                        "REVIEWED_SPORTSMAN_ACTIVE_CONTINUITY",
                        "REVIEWED_ACTIVE_SPORTSMAN_PERMIT_HUNT",
                        1.0,
                        "EXACT_CODE_EXTERNAL_SOURCE",
                        left,
                        right,
                        hit_from,
                        {
                            "source_files": source_files,
                            "source_pages": "1",
                            "source_kinds": "draw_results",
                        },
                        reviewed_2022_2023_sportsman_active_continuity_note,
                    )
                )
            elif candidates:
                top = candidates[0]
                matched_added.add(str(top["to_hunt_code"]))
                status = "COUGAR_SUCCESSOR_RULE" if top["match_quality"] == "COUGAR_SUCCESSOR_RULE" else "CANDIDATE_SUCCESSOR_BY_IDENTITY"
                confidence = str(top["match_quality"])
                right = identities.get(to_year, {}).get(str(top["to_hunt_code"]), {})
                crosswalk_rows.append(
                    base_row(
                        from_year,
                        to_year,
                        code,
                        str(top["to_hunt_code"]),
                        status,
                        confidence,
                        float(top["identity_score"]),
                        str(top["match_quality"]),
                        left,
                        right,
                        hit_from,
                        source_hits.get((str(top["to_hunt_code"]), to_year), {}),
                        "Dropped code has a same-prefix successor candidate in the next report year.",
                    )
                )
                for candidate in candidates[:5]:
                    candidate_rows.append(
                        {
                            "from_report_year": from_year,
                            "to_report_year": to_year,
                            "from_hunt_code": code,
                            "to_hunt_code": candidate["to_hunt_code"],
                            "identity_score": candidate["identity_score"],
                            "match_quality": candidate["match_quality"],
                            "from_hunt_name": left.get("hunt_name", ""),
                            "to_hunt_name": candidate["to_hunt_name"],
                            "from_unit": left.get("unit", ""),
                            "to_unit": candidate["to_unit"],
                            "from_weapon": left.get("weapon", ""),
                            "to_weapon": candidate["to_weapon"],
                            "notes": "Candidate only; requires review before treating as a real code replacement.",
                        }
                    )
            else:
                crosswalk_rows.append(
                    base_row(
                        from_year,
                        to_year,
                        code,
                        "",
                        "DROPPED_NO_SUCCESSOR_CANDIDATE",
                        "NO_SAFE_MATCH",
                        "",
                        "",
                        left,
                        {},
                        hit_from,
                        {},
                        "Code was observed in from-year and absent in to-year; no same-prefix identity successor candidate met threshold.",
                    )
                )

        for code in sorted(added - matched_added):
            right = identities.get(to_year, {}).get(code, {"hunt_code": code, "prefix": prefix_of(code)})
            crosswalk_rows.append(
                base_row(
                    from_year,
                    to_year,
                    "",
                    code,
                    "ADDED_NO_PREDECESSOR_CANDIDATE",
                    "NO_SAFE_MATCH",
                    "",
                    "",
                    {},
                    right,
                    {},
                    source_hits.get((code, to_year), {}),
                    "Code first appears in to-year relative to adjacent from-year; no predecessor candidate selected.",
                )
            )

    summary = summarize(crosswalk_rows, candidate_rows, by_year)
    return crosswalk_rows, candidate_rows, summary


def reviewed_decision_rows(crosswalk_rows: list[dict[str, object]], from_year: int, to_year: int) -> list[dict[str, object]]:
    rows = []
    for row in crosswalk_rows:
        if not str(row.get("crosswalk_status", "")).startswith("REVIEWED_"):
            continue
        if row.get("from_report_year") != from_year or row.get("to_report_year") != to_year:
            continue
        rows.append(
            {
                "from_report_year": row["from_report_year"],
                "to_report_year": row["to_report_year"],
                "from_model_year": row["from_model_year"],
                "to_model_year": row["to_model_year"],
                "hunt_code": row["from_hunt_code"],
                "species": row["from_species"],
                "unit": row["from_unit"],
                "weapon": row["from_weapon"],
                "reviewed_status": row["crosswalk_status"],
                "source_evidence": row["from_source_files"],
                "source_pages": row["from_source_pages"],
                "target_source_evidence": row["to_source_files"],
                "target_source_pages": row["to_source_pages"],
                "decision_basis": row["notes"],
            }
        )
    return rows


def base_row(
    from_year: int,
    to_year: int,
    from_code: str,
    to_code: str,
    status: str,
    confidence: str,
    score: object,
    identity_match_status: str,
    left: dict[str, str],
    right: dict[str, str],
    hit_from: dict[str, str],
    hit_to: dict[str, str],
    notes: str,
) -> dict[str, object]:
    return {
        "from_report_year": from_year,
        "to_report_year": to_year,
        "from_model_year": from_year + 1,
        "to_model_year": to_year + 1,
        "from_hunt_code": from_code,
        "to_hunt_code": to_code,
        "from_prefix": prefix_of(from_code) if from_code else "",
        "to_prefix": prefix_of(to_code) if to_code else "",
        "crosswalk_status": status,
        "crosswalk_confidence": confidence,
        "identity_score": score,
        "identity_match_status": identity_match_status,
        "from_hunt_name": left.get("hunt_name", ""),
        "to_hunt_name": right.get("hunt_name", ""),
        "from_species": left.get("species", ""),
        "to_species": right.get("species", ""),
        "from_unit": left.get("unit", ""),
        "to_unit": right.get("unit", ""),
        "from_weapon": left.get("weapon", ""),
        "to_weapon": right.get("weapon", ""),
        "from_source_report_family": left.get("source_report_family", ""),
        "to_source_report_family": right.get("source_report_family", ""),
        "from_identity_source": left.get("identity_source", ""),
        "to_identity_source": right.get("identity_source", ""),
        "from_source_files": hit_from.get("source_files", ""),
        "to_source_files": hit_to.get("source_files", ""),
        "from_source_pages": hit_from.get("source_pages", ""),
        "to_source_pages": hit_to.get("source_pages", ""),
        "notes": notes,
    }


def summarize(crosswalk_rows: list[dict[str, object]], candidate_rows: list[dict[str, object]], by_year: dict[int, set[str]]) -> dict[str, object]:
    status_counts = Counter(str(row["crosswalk_status"]) for row in crosswalk_rows)
    transition_counts: dict[str, dict[str, int]] = {}
    for row in crosswalk_rows:
        key = f"{row['from_report_year']}->{row['to_report_year']}"
        transition_counts.setdefault(key, Counter())
        transition_counts[key][str(row["crosswalk_status"])] += 1
    return {
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "scope": "Adjacent year-to-year hunt-code crosswalk for BIBLE HUNT CODES comprehensive 2020-2026 evidence.",
        "year_semantics": "report_year/draw_year = permit draw year; model_year = report_year + 1.",
        "input_presence_matrix": PRESENCE.relative_to(ROOT).as_posix(),
        "artifact_filter": ARTIFACT_FILTER.relative_to(ROOT).as_posix(),
        "artifact_codes_excluded_from_crosswalk": len(artifact_filter_codes()),
        "uses_database_for_2026_identity_only": DATABASE.relative_to(ROOT).as_posix(),
        "report_years": YEARS,
        "codes_by_report_year": {str(year): len(by_year[year]) for year in YEARS},
        "row_counts": {
            "crosswalk_rows": len(crosswalk_rows),
            "candidate_rows": len(candidate_rows),
            "reviewed_2020_to_2021_discontinuation_rows": sum(
                1
                for row in crosswalk_rows
                if row["crosswalk_status"] == "REVIEWED_DISCONTINUED_AFTER_2020_NO_SUCCESSOR"
            ),
            "reviewed_2020_to_2021_cougar_active_continuity_rows": sum(
                1
                for row in crosswalk_rows
                if row["crosswalk_status"] == "REVIEWED_2021_COUGAR_ACTIVE_CONTINUITY"
            ),
            "reviewed_2021_to_2022_successor_rows": sum(
                1
                for row in crosswalk_rows
                if row["crosswalk_status"] == "REVIEWED_SUCCESSOR_BY_2022_BEAR_GUIDE"
            ),
            "reviewed_2021_to_2022_antlerless_successor_rows": sum(
                1
                for row in crosswalk_rows
                if row["crosswalk_status"] == "REVIEWED_SUCCESSOR_BY_2022_ANTLERLESS_DRAW_RESULTS"
            ),
            "reviewed_2021_to_2022_antlerless_discontinued_rows": sum(
                1
                for row in crosswalk_rows
                if row["crosswalk_status"] == "REVIEWED_DISCONTINUED_AFTER_2021_NO_2022_ANTLERLESS_SUCCESSOR"
            ),
            "reviewed_2021_to_2022_cougar_active_continuity_rows": sum(
                1
                for row in crosswalk_rows
                if row["crosswalk_status"] == "REVIEWED_2022_COUGAR_ACTIVE_CONTINUITY"
            ),
            "reviewed_2021_to_2022_artifact_rows": sum(
                1
                for row in crosswalk_rows
                if row["crosswalk_status"] == "REVIEWED_SOURCE_YEAR_ARTIFACT_NOT_TRUE_DROP"
            ),
            "reviewed_2022_to_2023_sportsman_active_continuity_rows": sum(
                1
                for row in crosswalk_rows
                if row["crosswalk_status"] == "REVIEWED_SPORTSMAN_ACTIVE_CONTINUITY"
            ),
        },
        "crosswalk_status_counts": dict(status_counts),
        "transition_status_counts": {key: dict(value) for key, value in transition_counts.items()},
        "outputs": {
            "crosswalk_csv": OUT_CROSSWALK.relative_to(ROOT).as_posix(),
            "candidate_csv": OUT_CANDIDATES.relative_to(ROOT).as_posix(),
            "reviewed_decisions_csv": OUT_REVIEWED_DECISIONS.relative_to(ROOT).as_posix(),
            "reviewed_decisions_2021_2022_csv": OUT_REVIEWED_DECISIONS_2021_2022.relative_to(ROOT).as_posix(),
            "reviewed_decisions_2022_2023_csv": OUT_REVIEWED_DECISIONS_2022_2023.relative_to(ROOT).as_posix(),
            "summary_json": OUT_SUMMARY.relative_to(ROOT).as_posix(),
            "report_md": OUT_REPORT.relative_to(ROOT).as_posix(),
        },
        "notes": [
            "Exact retained rows are evidence of code continuity by exact hunt_code.",
            "Candidate successor rows are review evidence only and must not be treated as promoted crosswalk truth until reviewed.",
            "Historical reappearance gaps are already handled in the interpreted lifecycle layer; this file focuses on adjacent year links.",
            "2026 identity fields use current DATABASE rows only for codes already observed in 2026 comprehensive source hits.",
            "Known A-prefixed Sportsman/OCR artifacts are excluded from this crosswalk; normalized real hunt codes remain eligible.",
            "Reviewed 2020-to-2021 discontinuation decisions are recorded separately and are not successor mappings.",
            "Reviewed 2021-to-2022 antlerless decisions use the official 2021, 2022, and 2023 antlerless draw-results PDFs to separate true successors from discontinued rows.",
            "Reviewed 2022-to-2023 sportsman decisions are active sportsman permit-hunt continuity rows across the analyzed source years; they are not discontinuations or successor mappings.",
        ],
    }


def write_report(summary: dict[str, object]) -> None:
    lines = [
        "# Hunt Code Year-To-Year Crosswalk 2020-2026",
        "",
        "## Purpose",
        "",
        "This audit creates an adjacent year-to-year hunt-code crosswalk from the BIBLE HUNT CODES comprehensive evidence. It distinguishes exact code continuity from candidate successor links.",
        "",
        "## Year Semantics",
        "",
        "- `report_year` / `draw_year` is the year permits were drawn.",
        "- `model_year` is `report_year + 1`.",
        "",
        "## Key Counts",
        "",
        f"- Crosswalk rows: `{summary['row_counts']['crosswalk_rows']}`",
        f"- Candidate rows: `{summary['row_counts']['candidate_rows']}`",
        f"- Reviewed 2020->2021 discontinued/no-successor rows: `{summary['row_counts']['reviewed_2020_to_2021_discontinuation_rows']}`",
        f"- Reviewed 2020->2021 cougar active-continuity rows: `{summary['row_counts']['reviewed_2020_to_2021_cougar_active_continuity_rows']}`",
        f"- Reviewed 2021->2022 bear successor rows: `{summary['row_counts']['reviewed_2021_to_2022_successor_rows']}`",
        f"- Reviewed 2021->2022 antlerless successor rows: `{summary['row_counts']['reviewed_2021_to_2022_antlerless_successor_rows']}`",
        f"- Reviewed 2021->2022 antlerless discontinued/no-successor rows: `{summary['row_counts']['reviewed_2021_to_2022_antlerless_discontinued_rows']}`",
        f"- Reviewed 2021->2022 cougar active-continuity rows: `{summary['row_counts']['reviewed_2021_to_2022_cougar_active_continuity_rows']}`",
        f"- Reviewed 2021->2022 source-artifact rows: `{summary['row_counts']['reviewed_2021_to_2022_artifact_rows']}`",
        f"- Reviewed 2022->2023 sportsman active-continuity rows: `{summary['row_counts']['reviewed_2022_to_2023_sportsman_active_continuity_rows']}`",
        "- Candidate rows list up to five same-prefix successor candidates per dropped code; they are not promoted one-to-one links.",
        "",
        "## Codes By Report Year",
        "",
    ]
    for year, count in summary["codes_by_report_year"].items():
        lines.append(f"- `{year}`: `{count}`")
    lines.extend(["", "## Status Counts", ""])
    for key, value in sorted(summary["crosswalk_status_counts"].items()):
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Transition Counts", ""])
    for transition, counts in summary["transition_status_counts"].items():
        rendered = ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
        lines.append(f"- `{transition}`: {rendered}")
    lines.extend(["", "## Outputs", ""])
    for value in summary["outputs"].values():
        lines.append(f"- `{value}`")
    lines.extend(
        [
            "",
            "## Source Guardrails",
            "",
            f"- Artifact codes excluded from the crosswalk: `{summary['artifact_codes_excluded_from_crosswalk']}`",
            "- 2026 `DATABASE.csv` is used only as an identity reference for codes already observed in 2026 source hits; this audit does not promote or change permit values.",
            "",
            "## Caution",
            "",
            "Candidate successor rows are review evidence only. They are not promoted crosswalk truth until reviewed against official PDFs and family context.",
            "",
            "Reviewed discontinuation rows are closure decisions, not successor mappings.",
        ]
    )
    OUT_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    crosswalk_rows, candidate_rows, summary = build_crosswalk()
    decision_rows = reviewed_decision_rows(crosswalk_rows, 2020, 2021)
    decision_rows_2021_2022 = reviewed_decision_rows(crosswalk_rows, 2021, 2022)
    decision_rows_2022_2023 = reviewed_decision_rows(crosswalk_rows, 2022, 2023)
    fields = list(base_row(2020, 2021, "", "", "", "", "", "", {}, {}, {}, {}, "").keys())
    candidate_fields = [
        "from_report_year",
        "to_report_year",
        "from_hunt_code",
        "to_hunt_code",
        "identity_score",
        "match_quality",
        "from_hunt_name",
        "to_hunt_name",
        "from_unit",
        "to_unit",
        "from_weapon",
        "to_weapon",
        "notes",
    ]
    write_csv(OUT_CROSSWALK, crosswalk_rows, fields)
    write_csv(OUT_CANDIDATES, candidate_rows, candidate_fields)
    write_csv(
        OUT_REVIEWED_DECISIONS,
        decision_rows,
        [
            "from_report_year",
            "to_report_year",
            "from_model_year",
            "to_model_year",
            "hunt_code",
            "species",
            "unit",
            "weapon",
            "reviewed_status",
            "source_evidence",
            "source_pages",
            "target_source_evidence",
            "target_source_pages",
            "decision_basis",
        ],
    )
    write_csv(
        OUT_REVIEWED_DECISIONS_2021_2022,
        decision_rows_2021_2022,
        [
            "from_report_year",
            "to_report_year",
            "from_model_year",
            "to_model_year",
            "hunt_code",
            "species",
            "unit",
            "weapon",
            "reviewed_status",
            "source_evidence",
            "source_pages",
            "target_source_evidence",
            "target_source_pages",
            "decision_basis",
        ],
    )
    write_csv(
        OUT_REVIEWED_DECISIONS_2022_2023,
        decision_rows_2022_2023,
        [
            "from_report_year",
            "to_report_year",
            "from_model_year",
            "to_model_year",
            "hunt_code",
            "species",
            "unit",
            "weapon",
            "reviewed_status",
            "source_evidence",
            "source_pages",
            "target_source_evidence",
            "target_source_pages",
            "decision_basis",
        ],
    )
    OUT_SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_report(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
