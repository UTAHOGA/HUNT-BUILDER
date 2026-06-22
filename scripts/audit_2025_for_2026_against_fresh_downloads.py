import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRESH = ROOT / "audits" / "2025_canonical_finalization" / "fresh_live_pulls_20260621_192945"
AUDIT_DIR = ROOT / "audits" / "2025_canonical_finalization"
CANONICAL = (
    ROOT
    / "data_truth"
    / "draw_results_truth"
    / "normalized"
    / "canonical_yearly"
    / "draw_results_2025_for_2026_canonical_yearly_draw_results.csv"
)
WORKBOOK = ROOT / "outputs" / "2025 standardized long.xlsx"
MANIFEST = FRESH / "utahdraws_draw_odds_full_matrix_manifest.csv"

REAL_HUNT_CODE_RE = re.compile(r"^[A-Z]{2}\d{4}$")
POINT_PURCHASE_CATEGORIES = {"bonus point", "preference point"}
EXPECTED_HUNT_TYPES = {
    "Limited Entry",
    "General Season",
    "CWMU",
    "Once-in-a-lifetime",
    "Dedicated Hunter",
    "O.T.C.",
    "Premium Limited Entry",
    "Sportsman",
    "Conservation",
    "Private Lands Entry",
    "Tribal",
}
EXPECTED_DRAW_DESIGNS = {
    "Max/Weighted Split",
    "Preference",
    "Capped Permits",
    "Random",
    "Unlimited",
    "Organizations",
}


def clean(value):
    return " ".join(str(value or "").replace("\r", "\n").split())


def norm_int(value, blank_is_zero=False):
    text = clean(value)
    if text == "":
        return "0" if blank_is_zero else ""
    try:
        return str(int(float(text)))
    except ValueError:
        return text


def residency(value):
    text = clean(value)
    if text in {"1", "Resident"}:
        return "Resident"
    if text in {"2", "Nonresident", "Non-Resident"}:
        return "Nonresident"
    return text


def point_key(value):
    return norm_int(value)


def row_key(row):
    return (
        clean(row.get("hunt_code")).upper(),
        residency(row.get("residency")),
        point_key(row.get("points")),
    )


def source_point(odd):
    point = clean(odd.get("Point"))
    if point != "":
        return point_key(point)
    return point_key(odd.get("PreferencePoint"))


def source_key(hunt_code, odd):
    return (
        clean(hunt_code).upper(),
        residency(odd.get("ResidencyTypeID")),
        source_point(odd),
    )


def load_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fields):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def source_permit_values(source):
    quota_res = int(source.get("QUOTA_RES") or 0)
    quota_nr = int(source.get("QUOTA_NRES") or 0)
    quota = int(source.get("QUOTA") or 0)
    if quota_res + quota_nr > 0:
        return str(quota_res), str(quota_nr), str(quota_res + quota_nr)
    if quota > 0:
        return "", "", str(quota)
    return "", "", "0"


def load_canonical():
    rows = load_csv(CANONICAL)
    by_key = defaultdict(list)
    by_code = defaultdict(list)
    scorable_rows = []
    supplemental_rows = []
    for row in rows:
        code = clean(row.get("hunt_code")).upper()
        by_code[code].append(row)
        if clean(row.get("record_type")) == "point_level_draw_result":
            scorable_rows.append(row)
            by_key[row_key(row)].append(row)
        else:
            supplemental_rows.append(row)
    return rows, scorable_rows, supplemental_rows, by_key, by_code


def flatten_fresh_utahdraws():
    rows = []
    skipped = []
    manifest_rows = load_csv(MANIFEST)
    for manifest in manifest_rows:
        if clean(manifest.get("status")).lower() != "ok":
            continue
        filename = clean(manifest.get("file"))
        if not filename.startswith("utahdraws_"):
            continue
        path = FRESH / filename
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        for hunt in payload.get("Data", []):
            code = clean(hunt.get("HuntCode")).upper()
            category = clean(hunt.get("HuntCategoryName"))
            if category.lower() in POINT_PURCHASE_CATEGORIES or not REAL_HUNT_CODE_RE.match(code):
                skipped.append(
                    {
                        "hunt_code": code,
                        "hunt_name": clean(hunt.get("HuntName")),
                        "hunt_category_name": category,
                        "species_subtype_name": clean(hunt.get("SpeciesSubtypeName")),
                        "source_file": filename,
                        "reason": "point_purchase_or_family_code",
                    }
                )
                continue
            for odd in hunt.get("OddsList", []):
                rows.append(
                    {
                        "hunt_code": code,
                        "hunt_name": clean(hunt.get("HuntName")),
                        "hunt_category_name": category,
                        "species_subtype_name": clean(hunt.get("SpeciesSubtypeName")),
                        "residency": residency(odd.get("ResidencyTypeID")),
                        "points": source_point(odd),
                        "eligible_applicants": norm_int(odd.get("ParticipantCount")),
                        "bonus_permits": norm_int(odd.get("SuccessfulByMaxPointRoundCount"), blank_is_zero=True),
                        "regular_permits": norm_int(odd.get("SuccessfulByRegularRoundCount"), blank_is_zero=True),
                        "total_permits": norm_int(odd.get("SuccessfulCount"), blank_is_zero=True),
                        "source_file": filename,
                    }
                )
    return rows, skipped


def compare_values(source, canonical_candidates):
    fields = ["eligible_applicants", "bonus_permits", "regular_permits", "total_permits"]
    exact_payload_matches = []
    mismatches = []
    for candidate in canonical_candidates:
        if all(norm_int(candidate.get(field)) == source[field] for field in fields):
            exact_payload_matches.append(candidate)
    if exact_payload_matches:
        return "matched", []
    for candidate in canonical_candidates[:5]:
        for field in fields:
            can_value = norm_int(candidate.get(field))
            src_value = source[field]
            if can_value != src_value:
                mismatches.append(
                    {
                        "hunt_code": source["hunt_code"],
                        "residency": source["residency"],
                        "points": source["points"],
                        "field": field,
                        "fresh_download_value": src_value,
                        "canonical_value": can_value,
                        "fresh_hunt_name": source["hunt_name"],
                        "canonical_hunt_name": clean(candidate.get("hunt_name")),
                        "source_file": source["source_file"],
                    }
                )
        break
    return "value_mismatch", mismatches


def audit_schema(rows, supplemental_rows):
    flags = []
    for row in rows:
        code = clean(row.get("hunt_code")).upper()
        hunt_type = clean(row.get("hunt_type"))
        draw_design = clean(row.get("draw_design"))
        if hunt_type == "":
            flags.append({"hunt_code": code, "issue": "blank_hunt_type", "value": "", "sample_hunt_name": clean(row.get("hunt_name"))})
        elif hunt_type not in EXPECTED_HUNT_TYPES:
            flags.append({"hunt_code": code, "issue": "nonstandard_hunt_type", "value": hunt_type, "sample_hunt_name": clean(row.get("hunt_name"))})
        if draw_design == "":
            flags.append({"hunt_code": code, "issue": "blank_draw_design", "value": "", "sample_hunt_name": clean(row.get("hunt_name"))})
        elif draw_design not in EXPECTED_DRAW_DESIGNS:
            flags.append({"hunt_code": code, "issue": "nonstandard_draw_design", "value": draw_design, "sample_hunt_name": clean(row.get("hunt_name"))})
        if clean(row.get("boundary_id")) == "":
            flags.append({"hunt_code": code, "issue": "blank_boundary_id", "value": "", "sample_hunt_name": clean(row.get("hunt_name"))})
    for row in supplemental_rows:
        if any(clean(row.get(field)) for field in ["residency", "points", "eligible_applicants", "bonus_permits", "regular_permits", "successful_applicants", "unsuccessful_applicants"]):
            flags.append(
                {
                    "hunt_code": clean(row.get("hunt_code")).upper(),
                    "issue": "supplemental_row_has_draw_success_fields",
                    "value": clean(row.get("record_type")),
                    "sample_hunt_name": clean(row.get("hunt_name")),
                }
            )
    return flags


def audit_dwr_huntboundary(canonical_by_code):
    rows = []
    for path in sorted(FRESH.glob("dwr_huntboundary_*.json")):
        if path.name in {"dwr_huntboundary_hasetup.json"}:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, list):
            continue
        for source in payload:
            code = clean(source.get("HUNT_NBR")).upper()
            if not REAL_HUNT_CODE_RE.match(code):
                continue
            source_res, source_nr, source_total = source_permit_values(source)
            canonical_rows = canonical_by_code.get(code, [])
            canonical_permit_sets = {
                (
                    norm_int(row.get("permits_2025_res")),
                    norm_int(row.get("permits_2025_nr")),
                    norm_int(row.get("permits_2025_total")),
                )
                for row in canonical_rows
            }
            canonical_total_sets = {item[2] for item in canonical_permit_sets}
            if not canonical_rows:
                status = "missing_from_canonical"
            elif (source_res, source_nr, source_total) in canonical_permit_sets:
                status = "matched_permit_split"
            elif source_total in canonical_total_sets:
                status = "matched_total_only_or_split_diff"
            else:
                status = "permit_mismatch"
            rows.append(
                {
                    "hunt_code": code,
                    "source_hunt_name": clean(source.get("HUNT_NAME")),
                    "source_species": clean(source.get("SPECIES")),
                    "source_sex_type": clean(source.get("GENDER")),
                    "source_hunt_type": clean(source.get("HUNT_TYPE")),
                    "source_weapon": clean(source.get("WEAPON")),
                    "source_season": clean(source.get("SEASON_DATE_TEXT")),
                    "source_permits_res": source_res,
                    "source_permits_nr": source_nr,
                    "source_permits_total": source_total,
                    "canonical_match_count": len(canonical_rows),
                    "canonical_permit_sets": "; ".join(sorted("|".join(item) for item in canonical_permit_sets))[:1000],
                    "status": status,
                    "source_file": path.name,
                }
            )
    return rows


def main():
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    canonical_rows, scorable_rows, supplemental_rows, canonical_by_key, canonical_by_code = load_canonical()
    fresh_rows, skipped = flatten_fresh_utahdraws()

    fresh_by_key = defaultdict(list)
    for row in fresh_rows:
        fresh_by_key[(row["hunt_code"], row["residency"], row["points"])].append(row)

    matched = 0
    source_only = []
    mismatches = []
    source_duplicate_keys = []
    for key, sources in fresh_by_key.items():
        if len(sources) > 1:
            source_duplicate_keys.append(
                {
                    "hunt_code": key[0],
                    "residency": key[1],
                    "points": key[2],
                    "download_rows": len(sources),
                    "source_files": "; ".join(sorted({s["source_file"] for s in sources})),
                }
            )
        candidates = canonical_by_key.get(key, [])
        if not candidates:
            for source in sources:
                source_only.append(source)
            continue
        status, row_mismatches = compare_values(sources[0], candidates)
        if status == "matched":
            matched += 1
        else:
            mismatches.extend(row_mismatches)

    canonical_only = []
    for key, candidates in canonical_by_key.items():
        if key not in fresh_by_key:
            sample = candidates[0]
            canonical_only.append(
                {
                    "hunt_code": key[0],
                    "residency": key[1],
                    "points": key[2],
                    "canonical_rows": len(candidates),
                    "hunt_name": clean(sample.get("hunt_name")),
                    "species": clean(sample.get("species")),
                    "record_type": clean(sample.get("record_type")),
                    "eligible_applicants": norm_int(sample.get("eligible_applicants")),
                    "total_permits": norm_int(sample.get("total_permits")),
                    "source_file": clean(sample.get("source_file")),
                }
            )

    schema_flags = audit_schema(canonical_rows, supplemental_rows)
    dwr_huntboundary_rows = audit_dwr_huntboundary(canonical_by_code)
    duplicate_canonical_keys = [
        {
            "hunt_code": key[0],
            "residency": key[1],
            "points": key[2],
            "canonical_rows": len(rows),
            "hunt_names": "; ".join(sorted({clean(r.get("hunt_name")) for r in rows})[:5]),
        }
        for key, rows in canonical_by_key.items()
        if len(rows) > 1
    ]

    source_code_set = {row["hunt_code"] for row in fresh_rows}
    canonical_code_set = {clean(row.get("hunt_code")).upper() for row in canonical_rows}
    source_code_missing_from_canonical = sorted(source_code_set - canonical_code_set)
    canonical_code_missing_from_source = sorted(canonical_code_set - source_code_set)

    summary = {
        "canonical_file": str(CANONICAL),
        "workbook_file": str(WORKBOOK),
        "fresh_download_folder": str(FRESH),
        "canonical_rows": len(canonical_rows),
        "canonical_scorable_point_rows": len(scorable_rows),
        "canonical_supplemental_rows": len(supplemental_rows),
        "canonical_unique_hunt_codes": len(canonical_code_set),
        "canonical_unique_scorable_keys": len(canonical_by_key),
        "fresh_download_real_hunt_point_rows": len(fresh_rows),
        "fresh_download_real_hunt_unique_keys": len(fresh_by_key),
        "fresh_download_skipped_point_purchase_or_family_hunts": len(skipped),
        "matched_unique_keys": matched,
        "fresh_only_unique_keys": len({(r["hunt_code"], r["residency"], r["points"]) for r in source_only}),
        "canonical_only_unique_keys": len(canonical_only),
        "value_mismatch_rows": len(mismatches),
        "source_duplicate_keys": len(source_duplicate_keys),
        "canonical_duplicate_scorable_keys": len(duplicate_canonical_keys),
        "source_code_missing_from_canonical_count": len(source_code_missing_from_canonical),
        "source_code_missing_from_canonical": source_code_missing_from_canonical[:200],
        "canonical_code_missing_from_fresh_download_count": len(canonical_code_missing_from_source),
        "canonical_code_missing_from_fresh_download_sample": canonical_code_missing_from_source[:200],
        "canonical_record_type_counts": dict(sorted(Counter(clean(r.get("record_type")) for r in canonical_rows).items())),
        "canonical_hunt_type_counts": dict(sorted(Counter(clean(r.get("hunt_type")) for r in canonical_rows).items())),
        "canonical_draw_design_counts": dict(sorted(Counter(clean(r.get("draw_design")) for r in canonical_rows).items())),
        "schema_flag_counts": dict(sorted(Counter(row["issue"] for row in schema_flags).items())),
        "dwr_huntboundary_rows": len(dwr_huntboundary_rows),
        "dwr_huntboundary_unique_codes": len({row["hunt_code"] for row in dwr_huntboundary_rows}),
        "dwr_huntboundary_status_counts": dict(sorted(Counter(row["status"] for row in dwr_huntboundary_rows).items())),
        "interpretation": (
            "Fresh UtahDraws endpoint rows are sparse official point rows; canonical PDF rows are denser and include "
            "zero-applicant/zero-success ladder rows plus supplemental permit-total rows. Large canonical-only key counts "
            "are expected and are not automatically errors."
        ),
    }

    (AUDIT_DIR / "2025_for_2026_vs_fresh_downloads_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    write_csv(
        AUDIT_DIR / "2025_for_2026_vs_fresh_downloads_fresh_only_keys.csv",
        source_only,
        [
            "hunt_code",
            "hunt_name",
            "hunt_category_name",
            "species_subtype_name",
            "residency",
            "points",
            "eligible_applicants",
            "bonus_permits",
            "regular_permits",
            "total_permits",
            "source_file",
        ],
    )
    write_csv(
        AUDIT_DIR / "2025_for_2026_vs_fresh_downloads_canonical_only_keys.csv",
        canonical_only,
        ["hunt_code", "residency", "points", "canonical_rows", "hunt_name", "species", "record_type", "eligible_applicants", "total_permits", "source_file"],
    )
    write_csv(
        AUDIT_DIR / "2025_for_2026_vs_fresh_downloads_value_mismatches.csv",
        mismatches,
        ["hunt_code", "residency", "points", "field", "fresh_download_value", "canonical_value", "fresh_hunt_name", "canonical_hunt_name", "source_file"],
    )
    write_csv(
        AUDIT_DIR / "2025_for_2026_vs_fresh_downloads_skipped_point_purchase_or_family_hunts.csv",
        skipped,
        ["hunt_code", "hunt_name", "hunt_category_name", "species_subtype_name", "source_file", "reason"],
    )
    write_csv(
        AUDIT_DIR / "2025_for_2026_vs_fresh_downloads_schema_flags.csv",
        schema_flags,
        ["hunt_code", "issue", "value", "sample_hunt_name"],
    )
    write_csv(
        AUDIT_DIR / "2025_for_2026_vs_fresh_downloads_duplicate_keys.csv",
        duplicate_canonical_keys + source_duplicate_keys,
        ["hunt_code", "residency", "points", "canonical_rows", "download_rows", "hunt_names", "source_files"],
    )
    write_csv(
        AUDIT_DIR / "2025_for_2026_vs_fresh_downloads_dwr_huntboundary.csv",
        dwr_huntboundary_rows,
        [
            "hunt_code",
            "source_hunt_name",
            "source_species",
            "source_sex_type",
            "source_hunt_type",
            "source_weapon",
            "source_season",
            "source_permits_res",
            "source_permits_nr",
            "source_permits_total",
            "canonical_match_count",
            "canonical_permit_sets",
            "status",
            "source_file",
        ],
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
