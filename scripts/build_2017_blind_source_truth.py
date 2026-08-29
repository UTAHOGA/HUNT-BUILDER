"""Reconstruct an audit-local 2017 draw-truth input from official DWR PDFs.

This intentionally produces only a source-side input for a 2017-to-2018
blind forecast.  It never opens the 2018 canonical, the normalized long file,
the runtime database, or prediction outputs.  Each emitted row retains its
official PDF, page, and residency lane.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pdfplumber

from extract_2020_draw_results_from_pdfs import HEADER, classify, sex_metadata_for, species_for
from extract_draw_reality import parse_pdf


REPO = Path(__file__).resolve().parents[1]
PDF_ROOT = REPO / "pipeline" / "RAW" / "hunt_unit_database" / "2017" / "pdf" / "draw_odds"
ALIAS_MANIFEST = REPO / "data_truth" / "draw_results_truth" / "source_file_aliases" / "2017_PERMITS=2018_MODEL_source_alias_manifest.csv"
SOURCE_CONFIG = (
    ("official_dwr_archive/big_game/17_big_game_odds_report.pdf", "BIG_GAME"),
    ("official_dwr_archive/big_game_antlerless/17_antlerless_points.pdf", "ANTLERLESS"),
    ("official_dwr_archive/big_game/17_general_deer.pdf", "GENERAL_SEASON_DEER"),
    ("official_dwr_archive/big_game/17_dedicated_hunter_deer.pdf", "DEDICATED_HUNTER"),
    ("official_dwr_archive/big_game/17_youth_any_bull_elk.pdf", "YOUTH_ANY_BULL_ELK"),
    ("official_dwr_archive/big_game/17_youth_general_deer.pdf", "YOUTH_GENERAL_SEASON_DEER"),
    ("official_dwr_archive/big_game_antlerless/17_antlerless_youth_points.pdf", "YOUTH_ANTLERLESS"),
    ("official_dwr_archive/black_bear/17_bonus_points.pdf", "BLACK_BEAR"),
    ("official_dwr_archive/turkey/2017_turkey_bonus_points_and_draw_results.pdf", "TURKEY"),
    ("official_dwr_archive/cougar/2017_cougar_odds_report.pdf", "COUGAR"),
)
EXCLUDED_SOURCE_SCOPES = {
    "official_dwr_archive/black_bear/17_drawing_odds.pdf": "NO_HUNT_CODE_IN_OFFICIAL_2017_NAME_ONLY_TABLE",
    "official_dwr_archive/big_game/17_lifetime_general_deer.pdf": "REFERENCE_LIFETIME_PERMIT_HOLDER_NOT_PREDICTIVE_DRAW",
}
HUNT_PAGE_CODE_RE = re.compile(r"(?im)^\s*Hunt:\s*([A-Z]{2}\d{4})\b")
SPORTSMAN_ROW_RE = re.compile(
    r"^(?P<raw_code>\S+)\s+(?P<successful>\d+)\s+N/A\s+"
    r"(?P<unsuccessful>\d+)\s+N/A\s+(?P<applicants>\d+)\s+"
    r"(?P<resident_quota>\d+)\s+N/A\s+(?P<total_quota>\d+)\s+"
    r"(?P<ratio>1\s+in\s+[\d.]+)\s+N/A$",
    re.I,
)

# The 2017 one-page official Sportsman report uses a font/extraction layout
# that interleaves the printed code characters (for example ``DDBB10-45``).
# These are not inferred from later application behavior: each mapping is the
# year-scoped published Sportsman identity already retained by the scoring
# contract. Deer must stay DB1045 in this 2017 source context; DB0007 is a
# later canonical Sportsman label and also collides with another real hunt.
SPORTSMAN_2017_CODE_CROSSWALK = {
    "TKT1K0-00": ("TK1000", "Sportsman Bearded Turkey"),
    "BI1B0I0-0": ("BI1000", "Sportsman Bison"),
    "BBRR10-00": ("BR1000", "Sportsman Black Bear"),
    "CCGG10-00": ("CG1000", "Sportsman Cougar"),
    "DDBB10-45": ("DB1045", "Sportsman Deer"),
    "DDSS10-00": ("DS1000", "Sportsman Desert Bighorn Sheep"),
    "EBE1B0-00": ("EB1000", "Sportsman Elk"),
    "MMBB10-00": ("MB1000", "Sportsman Moose"),
    "GGOO10-00": ("GO1000", "Sportsman Mountain Goat"),
    "PBP1B0-00": ("PB1000", "Sportsman Pronghorn"),
    "RRSS10-00": ("RS1000", "Sportsman Rocky Mtn Bighorn Sheep"),
}


def clean(value: object) -> str:
    return "" if value is None else " ".join(str(value).strip().split())


def as_int(value: object) -> int:
    try:
        return int(float(clean(value).replace(",", "")))
    except ValueError:
        return 0


CODE_PREFIX_SPECIES = {
    "BI": "Bison",
    "BR": "Black Bear",
    "CG": "Cougar",
    "DA": "Deer",
    "DB": "Deer",
    "DS": "Desert Bighorn Sheep",
    "EA": "Elk",
    "EB": "Elk",
    "GO": "Mountain Goat",
    "MA": "Moose",
    "MB": "Moose",
    "PB": "Pronghorn",
    "PD": "Pronghorn",
    "RS": "Rocky Mountain Bighorn Sheep",
    "TK": "Turkey",
}


def source_species_for(code: str, name: str) -> str:
    """Classify from the official hunt-code prefix before unit-name text.

    Unit names legitimately contain terms such as "Elk Ridge" and "Bear
    River". Those location terms cannot change a DB/DA deer or EB/EA elk
    record into another species.
    """

    return CODE_PREFIX_SPECIES.get(code[:2].upper(), species_for(code, name))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_2017_alias_manifest() -> dict[str, object]:
    """Verify that every retained official 2017 source has one hashed role."""
    if not ALIAS_MANIFEST.exists():
        raise FileNotFoundError(f"Required 2017 source alias manifest is missing: {ALIAS_MANIFEST}")
    with ALIAS_MANIFEST.open(encoding="utf-8-sig", newline="") as handle:
        entries = list(csv.DictReader(handle))
    required = {
        "source_year", "target_year", "standardized_raw_pdf_relative_path",
        "source_family", "source_role", "active_for_scoring", "sha256", "source_disposition",
    }
    if not entries or not required.issubset(entries[0]):
        raise ValueError("2017 source alias manifest is missing required columns")
    paths = [clean(row["standardized_raw_pdf_relative_path"]) for row in entries]
    if len(paths) != len(set(paths)):
        raise ValueError("2017 source alias manifest has duplicate source paths")
    for row in entries:
        if clean(row["source_year"]) != "2017" or clean(row["target_year"]) != "2018":
            raise ValueError(f"2017 source alias manifest has wrong year boundary: {row}")
        path = PDF_ROOT / clean(row["standardized_raw_pdf_relative_path"])
        if not path.exists():
            raise FileNotFoundError(f"2017 alias manifest source is missing: {path}")
        if sha256(path) != clean(row["sha256"]):
            raise ValueError(f"2017 alias manifest hash mismatch: {path}")
    configured = {source_file for source_file, _scope in SOURCE_CONFIG}
    configured.add("official_dwr_archive/big_game/2017_sportsman_odds.pdf")
    manifest_relative = {
        str(Path(path)).replace("\\", "/")
        for path in paths
    }
    missing_configured = configured - manifest_relative
    if missing_configured:
        raise ValueError(f"Configured 2017 source is absent from alias manifest: {sorted(missing_configured)}")
    active = [row for row in entries if clean(row["active_for_scoring"]).lower() == "true"]
    active_relative = {
        clean(row["standardized_raw_pdf_relative_path"]).replace("\\", "/")
        for row in active
    }
    unsupported_active = active_relative - configured
    if unsupported_active:
        raise ValueError(f"Active 2017 source has no configured extractor: {sorted(unsupported_active)}")
    return {
        "manifest_path": str(ALIAS_MANIFEST.relative_to(REPO)).replace("\\", "/"),
        "manifest_rows": len(entries),
        "hash_verified_sources": len(entries),
        "active_for_scoring_sources": len(active),
        "configured_truth_sources": len(configured),
        "non_scoring_retained_sources": len(entries) - len(active),
    }


def probability(numerator: int, denominator: int) -> tuple[str, str]:
    if denominator <= 0:
        return "0", "0"
    value = min(1.0, max(0.0, numerator / denominator))
    return f"{value:.10f}".rstrip("0").rstrip("."), f"{value * 100:.8f}".rstrip("0").rstrip(".")


def official_hunt_page_codes(path: Path) -> dict[str, str]:
    """Return only hunt-code pages explicitly named by the official PDF.

    The legacy line parser can carry a prior page's hunt identity into a
    species-summary page. A summary page may contain a valid points table but
    is not a hunt-level draw-result page and cannot inherit that prior code.
    The physical PDF page header is the source identity boundary.
    """
    codes: dict[str, str] = {}
    with pdfplumber.open(path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            match = HUNT_PAGE_CODE_RE.search(text)
            if match:
                codes[str(page_number)] = match.group(1)
    return codes


def extract_2017_sportsman_rows(path: Path) -> tuple[list[dict[str, object]], list[dict[str, str]]]:
    """Parse the official one-page Sportsman report with its recorded code map.

    Sportsman is a single random-only draw, not a point ladder. The output
    retains the raw published glyph token in a companion crosswalk audit so a
    later source reviewer can see exactly why the normalized code was used.
    """
    parsed: list[dict[str, object]] = []
    crosswalk: list[dict[str, str]] = []
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != 1:
            raise ValueError(f"Expected one Sportsman page in {path}, found {len(pdf.pages)}")
        for line in (pdf.pages[0].extract_text() or "").splitlines():
            match = SPORTSMAN_ROW_RE.match(clean(line))
            if not match:
                continue
            raw_code = match.group("raw_code").upper()
            if raw_code not in SPORTSMAN_2017_CODE_CROSSWALK:
                raise ValueError(f"Unmapped official 2017 Sportsman code token: {raw_code}")
            code, name = SPORTSMAN_2017_CODE_CROSSWALK[raw_code]
            applicants = int(match.group("applicants"))
            permits = int(match.group("total_quota"))
            parsed.append(
                {
                    "page_number": 1,
                    "hunt_code": code,
                    "hunt_name": name,
                    "residency": "Resident",
                    "points": 0,
                    "eligible_applicants": applicants,
                    "bonus_permits": 0,
                    "regular_permits": permits,
                    "total_permits": permits,
                    "success_ratio": match.group("ratio"),
                }
            )
            crosswalk.append(
                {
                    "source_file": str(path.relative_to(PDF_ROOT)).replace("\\", "/"),
                    "pdf_page": "1",
                    "raw_published_code_token": raw_code,
                    "normalized_hunt_code": code,
                    "hunt_name": name,
                    "code_resolution_basis": "2017_SPORTSMAN_YEAR_SCOPED_OFFICIAL_CODE_CROSSWALK",
                    "applicants": str(applicants),
                    "total_permits": str(permits),
                }
            )
    if len(parsed) != len(SPORTSMAN_2017_CODE_CROSSWALK):
        raise ValueError(
            "Official 2017 Sportsman report did not produce every expected published row: "
            f"got {len(parsed)}, expected {len(SPORTSMAN_2017_CODE_CROSSWALK)}"
        )
    return parsed, crosswalk


def classify_2017_source(scope: str, code: str, name: str) -> tuple[str, str, str, str]:
    """Keep historical Cougar source truth distinct from current availability."""
    if scope == "COUGAR":
        return (
            "HISTORICAL_LIMITED_ENTRY_COUGAR",
            "Cougar",
            "BONUS_HISTORICAL_COUGAR",
            "SOURCE_ONLY_HISTORICAL_DRAW",
        )
    return classify(scope, code, name)


def canonical_row(raw: dict[str, object], source_file: str, scope: str) -> dict[str, str]:
    code = clean(raw["hunt_code"]).upper()
    name = clean(raw["hunt_name"])
    residency = clean(raw["residency"])
    applicants = as_int(raw["eligible_applicants"])
    bonus = as_int(raw["bonus_permits"])
    regular = as_int(raw["regular_permits"])
    permits = as_int(raw["total_permits"])
    p_draw, p_draw_pct = probability(permits, applicants)
    hunt_class, hunt_type, draw_design, algorithm_status = classify_2017_source(scope, code, name)
    sex, sex_type = sex_metadata_for(code, name)
    row = {field: "" for field in HEADER}
    row.update(
        {
            "actual_draw_year": "2017",
            "model_target_year": "2018",
            "hunt_code": code,
            "hunt_name": name,
            "raw_hunt_name": name,
            "species": source_species_for(code, name),
            "sex": sex,
            "sex_type": sex_type,
            "hunt_type": hunt_type,
            "draw_design": draw_design,
            "hunt_draw_class": hunt_class,
            "hunt_class": hunt_class,
            "points": str(raw["points"]),
            "residency": residency,
            "row_type": "POINT_ROW",
            "record_type": "point_level_draw_result",
            "eligible_applicants": str(applicants),
            "bonus_permits": str(bonus),
            "regular_permits": str(regular),
            "total_permits": str(permits),
            "success_ratio": clean(raw["success_ratio"]),
            "p_draw": p_draw,
            "p_draw_percent": p_draw_pct,
            "successful_applicants": str(permits),
            "unsuccessful_applicants": str(max(0, applicants - permits)),
            "source_scope": scope,
            "source_namespace": "OFFICIAL_DWR_DRAW_RESULTS_2017",
            "draw_source_namespace": "OFFICIAL_DWR_DRAW_RESULTS_2017",
            "source_file": source_file,
            "draw_source_file": source_file,
            "source_path": str((PDF_ROOT / source_file).relative_to(REPO)).replace("\\", "/"),
            "source_pdf": Path(source_file).name,
            "pdf_page": str(raw["page_number"]),
            "official_page": str(raw["page_number"]),
            "page_kind": "HUNT_PAGE",
            "source_dataset": "DWR_2017_DRAW_RESULTS_PDF",
            "extraction_status": "OK",
            "parse_method": "PDFPLUMBER_LINE_LADDER",
            "qa_status": "SOURCE_TABLE_PARSED",
            "algorithm_status": algorithm_status,
            "source_residencies": residency.lower(),
            "source_row_count": "1",
            "collapse_conflict_count": "0",
            "candidate_promotion_status": "AUDIT_LOCAL_SOURCE_ONLY",
            "draw_system_type": draw_design,
            "draw_pool": hunt_class,
            "draw_system_type_source": "2017_OFFICIAL_PDF_SOURCE_SCOPE",
            "draw_system_type_confidence": "high",
            "metric_scope": residency.lower(),
        }
    )
    prefix = "resident" if residency.lower().startswith("res") else "nonresident"
    row[f"{prefix}_eligible_applicants"] = str(applicants)
    row[f"{prefix}_bonus_permits"] = str(bonus)
    row[f"{prefix}_regular_permits"] = str(regular)
    row[f"{prefix}_total_permits"] = str(permits)
    row[f"{prefix}_success_ratio"] = clean(raw["success_ratio"])
    row[f"{prefix}_p_draw"] = p_draw
    row[f"{prefix}_p_draw_percent"] = p_draw_pct
    return row


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADER, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def dwr_table_shape_rows(split_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Collapse audit-local residency lanes back to the official DWR table shape.

    This produces a review candidate only. The source-lane CSV remains the
    forensic input, while this table-shaped form is what a yearly canonical
    would require if and only if later promotion is approved.
    """
    key_fields = (
        "actual_draw_year", "model_target_year", "source_scope", "source_file",
        "pdf_page", "hunt_code", "hunt_name", "points", "record_type",
        "hunt_type", "draw_design",
    )
    grouped: dict[tuple[str, ...], list[dict[str, str]]] = {}
    for row in split_rows:
        grouped.setdefault(tuple(row[field] for field in key_fields), []).append(row)

    collapsed: list[dict[str, str]] = []
    for _, lanes in sorted(grouped.items()):
        by_residency = {row["residency"]: row for row in lanes}
        if len(by_residency) != len(lanes):
            raise ValueError(f"Duplicate residency lane in canonical candidate: {lanes[0]['source_file']} p{lanes[0]['pdf_page']} {lanes[0]['hunt_code']} {lanes[0]['points']}")
        template = dict(lanes[0])
        resident = by_residency.get("Resident", {})
        nonresident = by_residency.get("Nonresident", {})
        res_apps = as_int(resident.get("eligible_applicants", 0))
        nr_apps = as_int(nonresident.get("eligible_applicants", 0))
        res_bonus = as_int(resident.get("bonus_permits", 0))
        nr_bonus = as_int(nonresident.get("bonus_permits", 0))
        res_regular = as_int(resident.get("regular_permits", 0))
        nr_regular = as_int(nonresident.get("regular_permits", 0))
        res_permits = as_int(resident.get("total_permits", 0))
        nr_permits = as_int(nonresident.get("total_permits", 0))
        total_apps = res_apps + nr_apps
        total_permits = res_permits + nr_permits
        total_p_draw, total_p_draw_pct = probability(total_permits, total_apps)
        template.update(
            {
                "residency": "",
                "eligible_applicants": str(total_apps),
                "bonus_permits": str(res_bonus + nr_bonus),
                "regular_permits": str(res_regular + nr_regular),
                "total_permits": str(total_permits),
                "success_ratio": f"1 in {total_apps / total_permits:.1f}" if total_permits else "N/A",
                "p_draw": total_p_draw,
                "p_draw_percent": total_p_draw_pct,
                "successful_applicants": str(total_permits),
                "unsuccessful_applicants": str(max(0, total_apps - total_permits)),
                "total_eligible_applicants": str(total_apps),
                "total_bonus_permits": str(res_bonus + nr_bonus),
                "total_regular_permits": str(res_regular + nr_regular),
                "total_permits": str(total_permits),
                "total_p_draw": total_p_draw,
                "total_p_draw_percent": total_p_draw_pct,
                "source_residencies": "; ".join(sorted(by_residency)),
                "source_row_count": str(len(lanes)),
                "collapse_conflict_count": "0",
                "candidate_promotion_status": "SOURCE_ONLY_CANONICAL_CANDIDATE_NOT_PROMOTED",
                "metric_scope": "total",
            }
        )
        collapsed.append(template)
    return collapsed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    alias_manifest_validation = validate_2017_alias_manifest()
    rows: list[dict[str, str]] = []
    source_counts: dict[str, int] = {}
    source_hashes: dict[str, str] = {}
    page_identity_exclusions: list[dict[str, str]] = []
    sportsman_crosswalk: list[dict[str, str]] = []
    for source_file, scope in SOURCE_CONFIG:
        path = PDF_ROOT / source_file
        if not path.exists():
            raise FileNotFoundError(path)
        print(f"Extracting {source_file}", flush=True)
        extracted = parse_pdf(path, 2017)
        page_codes = official_hunt_page_codes(path)
        matched = []
        for raw in extracted:
            page_number = str(raw.get("page_number", ""))
            parsed_code = clean(raw.get("hunt_code")).upper()
            official_code = page_codes.get(page_number, "")
            if official_code == parsed_code:
                matched.append(raw)
                continue
            page_identity_exclusions.append(
                {
                    "source_file": source_file,
                    "source_scope": scope,
                    "pdf_page": page_number,
                    "parser_hunt_code": parsed_code,
                    "official_page_hunt_code": official_code,
                    "eligible_applicants": str(raw.get("eligible_applicants", "")),
                    "total_permits": str(raw.get("total_permits", "")),
                    "reason": (
                        "PAGE_HAS_NO_EXPLICIT_HUNT_CODE"
                        if not official_code
                        else "PARSER_HUNT_CODE_DIFFERS_FROM_OFFICIAL_PAGE_HEADER"
                    ),
                }
            )
        extracted = matched
        converted = [canonical_row(row, source_file, scope) for row in extracted]
        rows.extend(converted)
        source_counts[source_file] = len(converted)
        source_hashes[source_file] = sha256(path)
        print(f"  parsed rows: {len(converted)}", flush=True)

    sportsman_source = "official_dwr_archive/big_game/2017_sportsman_odds.pdf"
    sportsman_path = PDF_ROOT / sportsman_source
    print(f"Extracting {sportsman_source}", flush=True)
    sportsman_raw, sportsman_crosswalk = extract_2017_sportsman_rows(sportsman_path)
    sportsman_rows = [canonical_row(row, sportsman_source, "SPORTSMAN") for row in sportsman_raw]
    rows.extend(sportsman_rows)
    source_counts[sportsman_source] = len(sportsman_rows)
    source_hashes[sportsman_source] = sha256(sportsman_path)
    print(f"  parsed rows: {len(sportsman_rows)}", flush=True)

    rows.sort(key=lambda row: (row["source_file"], int(row["pdf_page"]), row["hunt_code"], row["residency"], -as_int(row["points"])))
    duplicate_keys = Counter((row["source_file"], row["pdf_page"], row["hunt_code"], row["residency"], row["points"]) for row in rows)
    duplicate_count = sum(count - 1 for count in duplicate_keys.values() if count > 1)
    if duplicate_count:
        raise ValueError(f"Source parser produced {duplicate_count} duplicate page/hunt/lane/point rows")

    out_csv = args.out_dir / "official_2017_pdf_reconstructed_source_truth.csv"
    canonical_candidate_csv = args.out_dir / "official_2017_pdf_reconstructed_canonical_yearly_candidate.csv"
    out_summary = args.out_dir / "official_2017_pdf_reconstructed_source_manifest.json"
    page_identity_audit = args.out_dir / "official_2017_pdf_page_identity_exclusions.csv"
    sportsman_crosswalk_audit = args.out_dir / "official_2017_sportsman_code_crosswalk.csv"
    write_csv(out_csv, rows)
    canonical_candidate_rows = dwr_table_shape_rows(rows)
    canonical_candidate_keys = Counter(
        (row["source_file"], row["pdf_page"], row["hunt_code"], row["points"], row["record_type"])
        for row in canonical_candidate_rows
    )
    candidate_duplicate_count = sum(count - 1 for count in canonical_candidate_keys.values() if count > 1)
    if candidate_duplicate_count:
        raise ValueError(f"Canonical candidate produced {candidate_duplicate_count} duplicate official table identities")
    write_csv(canonical_candidate_csv, canonical_candidate_rows)
    with page_identity_audit.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "source_file", "source_scope", "pdf_page", "parser_hunt_code",
                "official_page_hunt_code", "eligible_applicants", "total_permits", "reason",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(page_identity_exclusions)
    with sportsman_crosswalk_audit.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "source_file", "pdf_page", "raw_published_code_token", "normalized_hunt_code",
                "hunt_name", "code_resolution_basis", "applicants", "total_permits",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(sportsman_crosswalk)
    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "2017_source_only_input_for_2018_blind_forecast",
        "truth_boundary": {
            "opened_2018_actual_canonical": False,
            "opened_normalized_long_file": False,
            "opened_runtime_database": False,
            "opened_prediction_outputs": False,
        },
        "alias_manifest_validation": alias_manifest_validation,
        "source_pdf_sha256": source_hashes,
        "source_row_counts": source_counts,
        "rows": len(rows),
        "canonical_yearly_candidate": {
            "rows": len(canonical_candidate_rows),
            "path": canonical_candidate_csv.name,
            "output_sha256": sha256(canonical_candidate_csv),
            "duplicate_official_table_identity_rows": candidate_duplicate_count,
            "promotion_status": "SOURCE_ONLY_CANONICAL_CANDIDATE_NOT_PROMOTED",
        },
        "unique_hunt_codes": len({row["hunt_code"] for row in rows}),
        "residency_rows": dict(Counter(row["residency"] for row in rows)),
        "source_scopes": dict(Counter(row["source_scope"] for row in rows)),
        "page_identity_exclusions": {
            "rows": len(page_identity_exclusions),
            "path": page_identity_audit.name,
            "reasons": dict(Counter(row["reason"] for row in page_identity_exclusions)),
        },
        "sportsman_code_crosswalk": {
            "rows": len(sportsman_crosswalk),
            "path": sportsman_crosswalk_audit.name,
            "status": "PASS_ALL_OFFICIAL_2017_SPORTSMAN_ROWS_RESOLVED",
        },
        "excluded_official_source_scopes": EXCLUDED_SOURCE_SCOPES,
        "output_sha256": sha256(out_csv),
        "status": "PASS_SOURCE_ONLY_RECONSTRUCTION",
    }
    out_summary.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
