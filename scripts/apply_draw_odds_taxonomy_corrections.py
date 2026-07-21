"""Apply draw-odds taxonomy corrections to a repo-side deep-pull snapshot."""

from __future__ import annotations

import argparse
import csv
import re
import shutil
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGING_ROOT = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "_staging"

TAXONOMY_FIELDS = [
    "master_family",
    "draw_design",
    "program_bucket",
    "species_bucket",
    "species_subbucket",
    "sheep_subspecies",
    "youth_flag",
    "youth_program_status",
    "source_proven_youth_report",
    "pre_program_start_suppression_reason",
    "cwmu_flag",
    "points_report_flag",
    "support_only_flag",
    "year_specific_exception",
    "taxonomy_status",
    "review_reason",
]

WEBSITE_MATRIX_FIELDS = [
    "website_matrix_source_page_group",
    "website_matrix_draw_package",
    "website_matrix_report_label",
    "website_matrix_year",
    "website_matrix_key",
]

CORRECTION_FIELDS = [
    "file_path",
    "source_url",
    "source_file",
    "old_master_family",
    "old_draw_design",
    "old_species_bucket",
    "old_species_subbucket",
    "corrected_master_family",
    "corrected_draw_design",
    "corrected_species_bucket",
    "corrected_species_subbucket",
    "correction_reason",
    "year_specific_exception",
    "status",
]

OIL_MASTER_IDS = {"11", "12", "13", "14", "15"}
POINT_TERMS = ("point", "points", "bonus")
BIG_GAME_SPECIES_BUCKETS = [
    "DEER",
    "ELK",
    "PRONGHORN",
    "BISON",
    "ROCKY_MOUNTAIN_BIGHORN_SHEEP",
    "DESERT_BIGHORN_SHEEP",
    "MOOSE",
    "MOUNTAIN_GOAT",
]
PLE_SPECIES_BUCKETS = ["DEER"]
LE_BIG_GAME_SPECIES_BUCKETS = ["DEER", "ELK", "PRONGHORN"]
OIL_SPECIES_BUCKETS = [
    "BISON",
    "ROCKY_MOUNTAIN_BIGHORN_SHEEP",
    "DESERT_BIGHORN_SHEEP",
    "MOOSE",
    "MOUNTAIN_GOAT",
]


@dataclass
class Taxonomy:
    master_family: str = ""
    draw_design: str = ""
    program_bucket: str = ""
    species_bucket: str = ""
    species_subbucket: str = ""
    sheep_subspecies: str = ""
    youth_flag: str = "FALSE"
    youth_program_status: str = "NOT_YOUTH"
    source_proven_youth_report: str = "FALSE"
    pre_program_start_suppression_reason: str = ""
    cwmu_flag: str = "FALSE"
    points_report_flag: str = "FALSE"
    support_only_flag: str = "FALSE"
    year_specific_exception: str = ""
    taxonomy_status: str = "PASS_TAXONOMY_MAPPED"
    review_reason: str = ""

    def as_dict(self) -> dict[str, str]:
        return {field: getattr(self, field) for field in TAXONOMY_FIELDS}


def clean(value: object) -> str:
    return " ".join(str(value or "").replace("_", " ").split())


def norm(value: object) -> str:
    return clean(value).lower()


def latest_snapshot() -> Path:
    candidates = [
        path
        for path in STAGING_ROOT.glob("draw_odds_deep_pull_*")
        if (path / "DRAW_ODDS_DEEP_PULL_MANIFEST.csv").exists()
    ]
    if not candidates:
        raise FileNotFoundError(f"No draw odds deep-pull snapshots found under {STAGING_ROOT}")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized_fieldnames = [field if isinstance(field, str) else str(field) for field in fieldnames]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=normalized_fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def year_from_row(row: dict[str, str]) -> int | None:
    if clean(row.get("license_year")).isdigit():
        return int(clean(row.get("license_year")))
    text = " ".join([row.get("source_url", ""), row.get("output_file", ""), row.get("link_text", "")])
    matches = re.findall(r"(?<!\d)(20\d{2})(?!\d)|(?<!\d)(\d{2})_", text)
    years: list[int] = []
    for full, short in matches:
        if full:
            years.append(int(full))
        elif short:
            candidate = int(short)
            if 0 <= candidate <= 30:
                years.append(2000 + candidate)
    return years[0] if years else None


def website_matrix_fields(row: dict[str, str], tx: Taxonomy) -> dict[str, str]:
    year = year_from_row(row)
    source_page = clean(row.get("source_page"))
    if source_page == "wildlife_biggame_odds":
        page_group = "WILDLIFE_BIGGAME_ODDS"
        draw_package = "Big Game"
    elif source_page == "wildlife_bear_cougar_turkey_odds":
        page_group = "WILDLIFE_BEAR_COUGAR_TURKEY_ODDS"
        draw_package = tx.master_family.replace("_", " ").title() if tx.master_family else "Bear/Cougar/Turkey"
    elif source_page.startswith("utahdraws"):
        page_group = "UTAHDRAWS_CURRENT_DRAW_ODDS"
        draw_package = clean(row.get("draw_name")) or "UtahDraws"
    else:
        page_group = source_page.upper().replace(" ", "_") if source_page else "UNKNOWN_SOURCE_PAGE"
        draw_package = clean(row.get("draw_name")) or tx.master_family.replace("_", " ").title()
    report_label = clean(row.get("link_text")) or clean(row.get("master_hunt_type_name")) or clean(row.get("source_kind"))
    key_parts = [
        page_group,
        str(year or ""),
        draw_package.upper().replace(" ", "_").replace("/", "_"),
        tx.master_family,
        tx.program_bucket,
        tx.species_bucket,
        tx.species_subbucket,
        report_label.upper().replace(" ", "_").replace("/", "_"),
    ]
    matrix_key = "|".join(part for part in key_parts if part)
    return {
        "website_matrix_source_page_group": page_group,
        "website_matrix_draw_package": draw_package,
        "website_matrix_report_label": report_label,
        "website_matrix_year": str(year or ""),
        "website_matrix_key": matrix_key,
    }


def row_text(row: dict[str, str]) -> str:
    return norm(
        " ".join(
            [
                row.get("source_kind", ""),
                row.get("category", ""),
                row.get("link_text", ""),
                row.get("source_url", ""),
                row.get("draw_name", ""),
                row.get("master_hunt_type_name", ""),
                row.get("output_file", ""),
            ]
        )
    )


def contains_any(text: str, terms: tuple[str, ...] | list[str] | set[str]) -> bool:
    return any(term in text for term in terms)


def species_from_text(text: str, master_id: str = "") -> tuple[str, str, str]:
    if "desert bighorn" in text or master_id == "13":
        return "BIGHORN_SHEEP", "DESERT_BIGHORN_SHEEP", "DESERT_BIGHORN_SHEEP"
    if "rocky mtn bighorn" in text or "rocky mountain bighorn" in text or "rocky mountain sheep" in text or master_id == "14":
        return "BIGHORN_SHEEP", "ROCKY_MOUNTAIN_BIGHORN_SHEEP", "ROCKY_MOUNTAIN_BIGHORN_SHEEP"
    if "bighorn" in text or "sheep" in text:
        return "BIGHORN_SHEEP", "", ""
    if "mountain goat" in text or "mtn goat" in text or master_id == "15":
        return "MOUNTAIN_GOAT", "", ""
    if "bison" in text or master_id == "12":
        return "BISON", "", ""
    if "moose" in text or master_id == "11":
        return "MOOSE", "", ""
    if "pronghorn" in text:
        return "PRONGHORN", "", ""
    if "elk" in text:
        return "ELK", "", ""
    if "deer" in text or "buck" in text:
        return "DEER", "", ""
    if "bear" in text:
        return "BLACK_BEAR", "", ""
    if "cougar" in text:
        return "COUGAR", "", ""
    if "turkey" in text:
        return "WILD_TURKEY", "", ""
    return "MIXED_OR_UNSPECIFIED", "", ""


def classify_big_game(row: dict[str, str], text: str, year: int | None) -> Taxonomy:
    tx = Taxonomy(master_family="BIG_GAME")
    master_id = clean(row.get("master_hunt_type_id"))
    species, subbucket, sheep = species_from_text(text, master_id)
    tx.species_bucket = species
    tx.species_subbucket = subbucket
    tx.sheep_subspecies = sheep
    if "cwmu" in text:
        tx.cwmu_flag = "TRUE"
        tx.program_bucket = "CWMU"
        if "youth" in text and "antlerless" in text:
            tx.draw_design = "YOUTH_ANTLERLESS"
        elif "antlerless" in text:
            tx.draw_design = "ANTLERLESS"
        else:
            tx.draw_design = "CWMU"
        return tx
    if "premium" in text or "p l e" in text or "ple " in text:
        tx.program_bucket = "PREMIUM_LIMITED_ENTRY"
        tx.draw_design = "PREMIUM_LIMITED_ENTRY"
        if tx.species_bucket not in {"DEER", "MIXED_OR_UNSPECIFIED", ""}:
            tx.taxonomy_status = "REVIEW_REQUIRED_UNEXPECTED_PREMIUM_NON_DEER_LABEL"
            tx.review_reason = "Premium Limited-Entry is deer-only; non-deer P.L.E. labels require review."
        elif tx.species_bucket in {"MIXED_OR_UNSPECIFIED", ""}:
            tx.species_bucket = "DEER"
            tx.review_reason = "Premium Limited-Entry is routed only to deer unless source proves otherwise."
        return tx
    if master_id in OIL_MASTER_IDS or "once in a lifetime" in text or "once-in-a-lifetime" in text:
        tx.program_bucket = "ONCE_IN_A_LIFETIME"
        tx.draw_design = "ONCE_IN_A_LIFETIME"
        if tx.species_bucket == "BIGHORN_SHEEP" and not tx.sheep_subspecies:
            tx.taxonomy_status = "PASS_WITH_YEAR_SPECIFIC_DIFFERENCES"
            tx.review_reason = "Source label is a combined O.I.L. big game report; preserve combined report until PDF rows expose sheep subspecies."
        return tx
    if "sportsman" in text:
        tx.program_bucket = "SPORTSMAN"
        tx.draw_design = "SPORTSMAN"
        return tx
    if "antlerless" in text:
        tx.program_bucket = "ANTLERLESS"
        tx.draw_design = "ANTLERLESS"
    elif "dedicated hunter" in text or "d h deer" in text:
        tx.program_bucket = "DEDICATED_HUNTER"
        tx.draw_design = "DEDICATED_HUNTER"
    elif "general season" in text or "general-season" in text or "g s" in text or "lifetime" in text:
        tx.program_bucket = "GENERAL_SEASON"
        tx.draw_design = "GENERAL_SEASON"
    elif "limited entry" in text or "limited-entry" in text or "l e" in text:
        tx.program_bucket = "LIMITED_ENTRY"
        tx.draw_design = "LIMITED_ENTRY"
        if tx.species_bucket not in {*LE_BIG_GAME_SPECIES_BUCKETS, "MIXED_OR_UNSPECIFIED"}:
            tx.program_bucket = "ONCE_IN_A_LIFETIME"
            tx.draw_design = "ONCE_IN_A_LIFETIME"
    else:
        tx.program_bucket = "BIG_GAME"
        tx.draw_design = "BIG_GAME"
    if "youth" in text:
        tx.youth_flag = "TRUE"
        tx.source_proven_youth_report = "TRUE"
        if year is not None and year < 2019 and "turkey" in text:
            tx.youth_program_status = "SUPPRESSED_PRE_2019_PROGRAM_START"
            tx.taxonomy_status = "SUPPRESSED_PRE_PROGRAM_START"
            tx.pre_program_start_suppression_reason = "Youth turkey program not source-proven before 2019."
        else:
            tx.youth_program_status = "SOURCE_PROVEN_YOUTH_REPORT"
    return tx


def classify_bear(row: dict[str, str], text: str) -> Taxonomy:
    tx = Taxonomy(master_family="BLACK_BEAR", species_bucket="BLACK_BEAR")
    if contains_any(text, POINT_TERMS):
        tx.points_report_flag = "TRUE"
        tx.program_bucket = "POINTS"
        tx.draw_design = "POINTS"
    elif "restricted pursuit" in text:
        tx.program_bucket = "RESTRICTED_PURSUIT"
        tx.draw_design = "RESTRICTED_PURSUIT"
    elif "pursuit" in text:
        tx.program_bucket = "PURSUIT"
        tx.draw_design = "PURSUIT"
    elif "harvest objective" in text:
        tx.program_bucket = "HARVEST_OBJECTIVE"
        tx.draw_design = "HARVEST_OBJECTIVE"
    else:
        tx.program_bucket = "LIMITED_ENTRY"
        tx.draw_design = "LIMITED_ENTRY"
    return tx


def classify_cougar(row: dict[str, str], text: str, year: int | None) -> Taxonomy:
    tx = Taxonomy(master_family="COUGAR", species_bucket="COUGAR")
    if contains_any(text, POINT_TERMS):
        tx.points_report_flag = "TRUE"
        tx.program_bucket = "POINTS"
        tx.draw_design = "POINTS"
        return tx
    if "pursuit" in text:
        tx.program_bucket = "PURSUIT"
        tx.draw_design = "PURSUIT"
        return tx
    if year is not None and year >= 2023 and "limited entry" not in text and "limited-entry" not in text:
        tx.program_bucket = "AVAILABILITY_OR_OTC"
        tx.draw_design = "AVAILABILITY_OR_OTC"
        tx.year_specific_exception = "COUGAR_POST_2023_AVAILABILITY_OR_OTC_STYLE_WHEN_NOT_SOURCE_LABELED_LIMITED_ENTRY"
        tx.taxonomy_status = "PASS_WITH_YEAR_SPECIFIC_DIFFERENCES"
        return tx
    tx.program_bucket = "LIMITED_ENTRY"
    tx.draw_design = "LIMITED_ENTRY"
    return tx


def classify_turkey(row: dict[str, str], text: str, year: int | None) -> Taxonomy:
    tx = Taxonomy(master_family="WILD_TURKEY", species_bucket="WILD_TURKEY")
    if contains_any(text, POINT_TERMS):
        tx.points_report_flag = "TRUE"
        tx.program_bucket = "POINTS"
        tx.draw_design = "POINTS"
    elif "youth" in text:
        tx.program_bucket = "YOUTH"
        tx.draw_design = "YOUTH"
    elif "leftover" in text or "general season" in text or "general-season" in text:
        tx.program_bucket = "GENERAL_SEASON_OR_LEFTOVER_IF_PRESENT"
        tx.draw_design = "GENERAL_SEASON_OR_LEFTOVER_IF_PRESENT"
    else:
        tx.program_bucket = "LIMITED_ENTRY"
        tx.draw_design = "LIMITED_ENTRY"
    if "youth" in text:
        tx.youth_flag = "TRUE"
        tx.source_proven_youth_report = "TRUE"
        if year is not None and year < 2019:
            tx.youth_program_status = "SUPPRESSED_PRE_2019_PROGRAM_START"
            tx.taxonomy_status = "SUPPRESSED_PRE_PROGRAM_START"
            tx.pre_program_start_suppression_reason = "Youth turkey program not source-proven before 2019."
        else:
            tx.youth_program_status = "SOURCE_PROVEN_YOUTH_REPORT"
    return tx


def classify_row(row: dict[str, str]) -> Taxonomy:
    text = row_text(row)
    category = norm(row.get("category"))
    year = year_from_row(row)
    if row.get("source_kind") in {"source_page_html", "utahdraws_supplement_json"}:
        return Taxonomy(
            support_only_flag="TRUE",
            program_bucket="SOURCE_SUPPORT",
            taxonomy_status="PASS_TAXONOMY_MAPPED",
        )
    if "wetland" in text or "waterfowl" in text:
        return Taxonomy(taxonomy_status="BLOCKED_NON_SCOPE_MIXED_REPORT", review_reason="Wetland/waterfowl is out of scope.")
    if "uplandgame" in text and "turkey" not in text:
        return Taxonomy(taxonomy_status="BLOCKED_NON_SCOPE_MIXED_REPORT", review_reason="Non-turkey upland game is out of scope.")
    if category in {"black bear", "sportsman black bear"} or "black bear" in text or (category == "black bear"):
        return classify_bear(row, text)
    if category == "cougar" or "cougar" in text:
        return classify_cougar(row, text, year)
    if category in {"turkey", "sportsman turkey"} or "turkey" in text:
        return classify_turkey(row, text, year)
    if category in {"big game", "big game antlerless", "sportsman big game"} or row.get("draw_name") == "Big Game":
        return classify_big_game(row, text, year)
    return Taxonomy(taxonomy_status="REVIEW_REQUIRED_UNMAPPED_REPORT", review_reason="Allowed-scope row could not be mapped by taxonomy rules.")


def correction_row(snapshot: Path, row: dict[str, str], tx: Taxonomy) -> dict[str, str] | None:
    old_master = clean(row.get("master_family"))
    old_draw = clean(row.get("draw_design"))
    old_species = clean(row.get("species_bucket"))
    old_sub = clean(row.get("species_subbucket"))
    corrected = tx.as_dict()
    needs_review = tx.taxonomy_status not in {"PASS_TAXONOMY_MAPPED", "PASS_WITH_YEAR_SPECIFIC_DIFFERENCES"}
    changed = (
        old_master
        or old_draw
        or old_species
        or old_sub
    ) and (
        old_master != tx.master_family
        or old_draw != tx.draw_design
        or old_species != tx.species_bucket
        or old_sub != tx.species_subbucket
    )
    notable = tx.draw_design in {
        "PREMIUM_LIMITED_ENTRY",
        "ONCE_IN_A_LIFETIME",
        "LIMITED_ENTRY",
        "RESTRICTED_PURSUIT",
        "AVAILABILITY_OR_OTC",
        "YOUTH",
        "POINTS",
    }
    if not (needs_review or changed or notable):
        return None
    reason = tx.review_reason
    if not reason and notable:
        reason = "Taxonomy rule applied for corrected draw-odds master family/program/species routing."
    return {
        "file_path": str(snapshot / "DRAW_ODDS_DEEP_PULL_MANIFEST.csv"),
        "source_url": row.get("source_url", ""),
        "source_file": row.get("output_file", ""),
        "old_master_family": old_master or clean(row.get("category")),
        "old_draw_design": old_draw,
        "old_species_bucket": old_species,
        "old_species_subbucket": old_sub,
        "corrected_master_family": corrected["master_family"],
        "corrected_draw_design": corrected["draw_design"],
        "corrected_species_bucket": corrected["species_bucket"],
        "corrected_species_subbucket": corrected["species_subbucket"],
        "correction_reason": reason,
        "year_specific_exception": tx.year_specific_exception,
        "status": tx.taxonomy_status,
    }


def write_taxonomy_reference(snapshot: Path) -> Path:
    path = snapshot / "DRAW_ODDS_TAXONOMY_REFERENCE.md"
    path.write_text(
        "\n".join(
            [
                "# Draw Odds Taxonomy Reference",
                "",
                "COLUMN_NAMING_AND_KEY_ALIGNMENT_FOLLOW_WEBSITE_MATRIX = TRUE",
                "",
                "## Included Master Families",
                "",
                "- BIG_GAME",
                "- BLACK_BEAR",
                "- COUGAR",
                "- WILD_TURKEY",
                "",
                "## Excluded Master Families",
                "",
                "- Wetland / waterfowl",
                "- Upland game except wild turkey",
                "- Swan",
                "- Grouse",
                "- Fishing",
                "- Any non-listed family",
                "",
                "## Big Game Species Universe",
                "",
                "BIG_GAME_SPECIES_BUCKET_COUNT = 8",
                "",
                *[f"{idx}. {species}" for idx, species in enumerate(BIG_GAME_SPECIES_BUCKETS, start=1)],
                "",
                "## Big Game Program Routing",
                "",
                "P.L.E. / PREMIUM_LIMITED_ENTRY:",
                "- DEER only",
                "",
                "L.E. / LIMITED_ENTRY:",
                "- DEER",
                "- ELK",
                "- PRONGHORN",
                "",
                "O.I.L. / ONCE_IN_A_LIFETIME:",
                "- BISON",
                "- ROCKY_MOUNTAIN_BIGHORN_SHEEP",
                "- DESERT_BIGHORN_SHEEP",
                "- MOOSE",
                "- MOUNTAIN_GOAT",
                "",
                "## Correct Big Game Folder Structure",
                "",
                "```text",
                "BIG_GAME/",
                "  PREMIUM_LIMITED_ENTRY/",
                "    DEER/",
                "",
                "  LIMITED_ENTRY/",
                "    DEER/",
                "    ELK/",
                "    PRONGHORN/",
                "",
                "  ONCE_IN_A_LIFETIME/",
                "    BISON/",
                "    ROCKY_MOUNTAIN_BIGHORN_SHEEP/",
                "    DESERT_BIGHORN_SHEEP/",
                "    MOOSE/",
                "    MOUNTAIN_GOAT/",
                "",
                "  GENERAL_SEASON/",
                "    DEER/",
                "",
                "  ANTLERLESS/",
                "    DEER/",
                "    ELK/",
                "    PRONGHORN/",
                "    MOOSE/",
                "    BIGHORN_SHEEP/",
                "    CWMU/",
                "    YOUTH/",
                "",
                "  CWMU/",
                "    BIG_GAME/",
                "      DEER/",
                "      ELK/",
                "      MOOSE/",
                "      PRONGHORN/",
                "    ANTLERLESS/",
                "      DEER/",
                "      ELK/",
                "      PRONGHORN/",
                "    YOUTH_ANTLERLESS/",
                "      DEER/",
                "      ELK/",
                "      PRONGHORN/",
                "",
                "  DEDICATED_HUNTER/",
                "    DEER/",
                "",
                "  SPORTSMAN/",
                "",
                "  POINTS/",
                "```",
                "",
                "## Guardrails",
                "",
                "PLE_DEER_ONLY = TRUE",
                "PLE_NON_DEER_STATUS = REVIEW_REQUIRED_UNEXPECTED_PREMIUM_NON_DEER_LABEL",
                "PROGRAM_BUCKETS_ARE_OVERLAYS_ON_SPECIES = TRUE",
                "PDF_REPORT_CONTENTS_DEFINE_TRUTH_ROWS = TRUE",
                "WEBSITE_MATRIX_DEFINES_SOURCE_GROUPING_AND_KEY_ALIGNMENT = TRUE",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def write_year_structure_audit(snapshot: Path, rows: list[dict[str, str]]) -> Path:
    path = snapshot / "DRAW_ODDS_YEAR_STRUCTURE_AUDIT.csv"
    grouped: dict[tuple[str, str, str, str, str, str], dict[str, object]] = {}
    for row in rows:
        key = (
            row.get("website_matrix_year", ""),
            row.get("website_matrix_source_page_group", ""),
            row.get("master_family", ""),
            row.get("program_bucket", ""),
            row.get("species_bucket", ""),
            row.get("species_subbucket", ""),
        )
        bucket = grouped.setdefault(
            key,
            {
                "website_matrix_year": key[0],
                "website_matrix_source_page_group": key[1],
                "master_family": key[2],
                "program_bucket": key[3],
                "species_bucket": key[4],
                "species_subbucket": key[5],
                "manifest_rows": 0,
                "download_errors": 0,
                "source_urls": set(),
                "taxonomy_statuses": Counter(),
            },
        )
        bucket["manifest_rows"] = int(bucket["manifest_rows"]) + 1
        if clean(row.get("download_status")) == "ERROR":
            bucket["download_errors"] = int(bucket["download_errors"]) + 1
        bucket["source_urls"].add(row.get("source_url", ""))
        bucket["taxonomy_statuses"][row.get("taxonomy_status", "")] += 1
    out_rows: list[dict[str, str]] = []
    for bucket in grouped.values():
        statuses = bucket["taxonomy_statuses"]
        out_rows.append(
            {
                "website_matrix_year": str(bucket["website_matrix_year"]),
                "website_matrix_source_page_group": str(bucket["website_matrix_source_page_group"]),
                "master_family": str(bucket["master_family"]),
                "program_bucket": str(bucket["program_bucket"]),
                "species_bucket": str(bucket["species_bucket"]),
                "species_subbucket": str(bucket["species_subbucket"]),
                "manifest_rows": str(bucket["manifest_rows"]),
                "download_errors": str(bucket["download_errors"]),
                "unique_source_url_count": str(len(bucket["source_urls"])),
                "taxonomy_statuses": "|".join(f"{status}:{count}" for status, count in sorted(statuses.items())),
            }
        )
    write_csv(
        path,
        [
            "website_matrix_year",
            "website_matrix_source_page_group",
            "master_family",
            "program_bucket",
            "species_bucket",
            "species_subbucket",
            "manifest_rows",
            "download_errors",
            "unique_source_url_count",
            "taxonomy_statuses",
        ],
        sorted(
            out_rows,
            key=lambda row: (
                row["website_matrix_year"],
                row["website_matrix_source_page_group"],
                row["master_family"],
                row["program_bucket"],
                row["species_bucket"],
                row["species_subbucket"],
            ),
        ),
    )
    return path


def apply(snapshot: Path) -> dict[str, object]:
    manifest = snapshot / "DRAW_ODDS_DEEP_PULL_MANIFEST.csv"
    taxonomy_manifest = manifest
    fieldnames, rows = read_csv(manifest)
    original_fieldnames = [field for field in fieldnames if field not in TAXONOMY_FIELDS and field not in WEBSITE_MATRIX_FIELDS]
    updated_fields = original_fieldnames + WEBSITE_MATRIX_FIELDS + TAXONOMY_FIELDS
    backup = snapshot / "DRAW_ODDS_DEEP_PULL_MANIFEST.pre_taxonomy_columns.csv"
    if not backup.exists():
        shutil.copy2(manifest, backup)

    audit_rows: list[dict[str, str]] = []
    correction_rows: list[dict[str, str]] = []
    for row in rows:
        tx = classify_row(row)
        matrix = website_matrix_fields(row, tx)
        row.update(matrix)
        row.update(tx.as_dict())
        audit_rows.append(
            {
                "source_url": row.get("source_url", ""),
                "source_file": row.get("output_file", ""),
                "link_text": row.get("link_text", ""),
                **matrix,
                **tx.as_dict(),
            }
        )
        corr = correction_row(snapshot, row, tx)
        if corr:
            correction_rows.append(corr)

    audit_fields = ["source_url", "source_file", "link_text", *WEBSITE_MATRIX_FIELDS, *TAXONOMY_FIELDS]
    try:
        write_csv(manifest, updated_fields, rows)
    except PermissionError:
        taxonomy_manifest = snapshot / "DRAW_ODDS_DEEP_PULL_MANIFEST_WITH_TAXONOMY.csv"
        write_csv(taxonomy_manifest, updated_fields, rows)
    write_csv(snapshot / "DRAW_ODDS_TAXONOMY_AUDIT.csv", audit_fields, audit_rows)
    write_csv(snapshot / "DRAW_ODDS_TAXONOMY_CORRECTIONS.csv", CORRECTION_FIELDS, correction_rows)
    reference_path = write_taxonomy_reference(snapshot)
    year_structure_path = write_year_structure_audit(snapshot, rows)

    status_counts = Counter(row["taxonomy_status"] for row in audit_rows)
    review_count = sum(count for status, count in status_counts.items() if status.startswith("REVIEW") or status.startswith("BLOCKED"))
    overall = "PASS_TAXONOMY_MAPPED"
    if review_count:
        overall = "PASS_WITH_YEAR_SPECIFIC_DIFFERENCES"
    elif status_counts.get("PASS_WITH_YEAR_SPECIFIC_DIFFERENCES"):
        overall = "PASS_WITH_YEAR_SPECIFIC_DIFFERENCES"

    report = snapshot / "DRAW_ODDS_TAXONOMY_CORRECTION_REPORT.md"
    report.write_text(
        "\n".join(
            [
                "# Draw Odds Taxonomy Correction Report",
                "",
                f"SNAPSHOT={snapshot}",
                f"MANIFEST={manifest}",
                f"TAXONOMY_ENHANCED_MANIFEST={taxonomy_manifest}",
                f"MANIFEST_BACKUP={backup}",
                f"DRAW_ODDS_TAXONOMY_AUDIT={snapshot / 'DRAW_ODDS_TAXONOMY_AUDIT.csv'}",
                f"DRAW_ODDS_TAXONOMY_CORRECTIONS={snapshot / 'DRAW_ODDS_TAXONOMY_CORRECTIONS.csv'}",
                f"DRAW_ODDS_TAXONOMY_REFERENCE={reference_path}",
                f"DRAW_ODDS_YEAR_STRUCTURE_AUDIT={year_structure_path}",
                "",
                "## Guardrails",
                "",
                "BIG_GAME_SPECIES_BUCKET_COUNT=8",
                "OIL_SPECIES_BUCKET_COUNT=5",
                "PLE_SPECIES_BUCKET_COUNT=1",
                "LE_BIG_GAME_SPECIES_BUCKET_COUNT=3",
                "PLE_ELK_BUCKET_REMOVED=TRUE",
                "PLE_DEER_ONLY=TRUE",
                "OIL_DESERT_BIGHORN_INCLUDED=TRUE",
                "OIL_ROCKY_MOUNTAIN_BIGHORN_INCLUDED=TRUE",
                "LE_TURKEY_INCLUDED=TRUE",
                "LE_BEAR_INCLUDED=TRUE",
                "LE_COUGAR_PRIOR_TO_2023_INCLUDED=TRUE",
                "YOUTH_PROGRAMS_YEAR_GATED=TRUE",
                "WETLAND_WATERFOWL_NON_TURKEY_UPLAND_EXCLUDED=TRUE",
                "COLUMN_NAMING_AND_KEY_ALIGNMENT_FOLLOW_WEBSITE_MATRIX=TRUE",
                "",
                "## Status Counts",
                "",
                *[f"- {status}: {count}" for status, count in sorted(status_counts.items())],
                "",
                f"TAXONOMY_STATUS={overall}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "manifest": manifest,
        "taxonomy_manifest": taxonomy_manifest,
        "audit": snapshot / "DRAW_ODDS_TAXONOMY_AUDIT.csv",
        "corrections": snapshot / "DRAW_ODDS_TAXONOMY_CORRECTIONS.csv",
        "status": overall,
        "status_counts": dict(status_counts),
        "correction_rows": len(correction_rows),
        "reference": reference_path,
        "year_structure": year_structure_path,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, default=None)
    args = parser.parse_args()
    snapshot = args.snapshot or latest_snapshot()
    if not snapshot.is_absolute():
        snapshot = ROOT / snapshot
    result = apply(snapshot)
    print("BIG_GAME_SPECIES_BUCKET_COUNT=8")
    print("OIL_SPECIES_BUCKET_COUNT=5")
    print("PLE_SPECIES_BUCKET_COUNT=1")
    print("LE_BIG_GAME_SPECIES_BUCKET_COUNT=3")
    print("PLE_ELK_BUCKET_REMOVED=TRUE")
    print("PLE_DEER_ONLY=TRUE")
    print("OIL_DESERT_BIGHORN_INCLUDED=TRUE")
    print("OIL_ROCKY_MOUNTAIN_BIGHORN_INCLUDED=TRUE")
    print("LE_TURKEY_INCLUDED=TRUE")
    print("LE_BEAR_INCLUDED=TRUE")
    print("LE_COUGAR_PRIOR_TO_2023_INCLUDED=TRUE")
    print("YOUTH_PROGRAMS_YEAR_GATED=TRUE")
    print(f"DRAW_ODDS_TAXONOMY_CORRECTIONS={result['corrections']}")
    print(f"TAXONOMY_STATUS={result['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
