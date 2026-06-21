import csv
import json
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
TARGET = (
    REPO
    / "data_truth"
    / "draw_results_truth"
    / "normalized"
    / "canonical_yearly"
    / "draw_results_2019_for_2020_canonical_yearly_draw_results.csv"
)
RAW_PDF_DIR = (
    REPO
    / "data_truth"
    / "draw_results_truth"
    / "raw_pdfs"
    / "2019_PERMITS=2020_MODEL"
)
BOUNDARY_SOURCES = [
    REPO / "data" / "hunt_boundaries.geojson",
    REPO / "data" / "hunt-boundaries-lite.geojson",
]
AUDIT = (
    REPO
    / "audits"
    / "truth_cross_year"
    / "final_yearly_canonical_audit"
    / "2019_for_2020"
    / "sex_boundary_fill"
)
BACKUPS = AUDIT / "backups"

PROTECTED_DRAW_FIELDS = {
    "eligible_applicants",
    "bonus_permits",
    "regular_permits",
    "total_permits",
    "success_ratio",
    "p_draw",
    "p_draw_percent",
    "successful_applicants",
    "unsuccessful_applicants",
}

SPECIES_SEX_DEFAULTS = {
    "cougar": ("Either Sex", "user_directed_species_default_cougar_either_sex"),
    "mountain goat": ("Either Sex", "user_directed_species_default_mountain_goat_either_sex"),
}

PROGRAM_PREFIXES = [
    r"Antlerless Rocky Mountain Bighorn Sheep",
    r"Rocky Mountain Bighorn Sheep",
    r"Limited Entry Archery Buck Pronghorn",
    r"Limited Entry Alw \(rifle\) Buck Pronghorn",
    r"Limited Entry Muzzleloader Buck Pronghorn",
    r"Limited Entry Buck Pronghorn",
    r"Limited Entry Archery Buck Deer",
    r"Limited Entry Alw \(rifle\) Buck Deer",
    r"Limited Entry Muzzleloader Buck Deer",
    r"Limited Entry Multi-season Buck Deer",
    r"Limited Entry Buck Deer",
    r"Limited Entry Archery Bull Elk",
    r"Limited Entry Alw \(rifle\) Bull Elk",
    r"Limited Entry Muzzleloader Bull Elk",
    r"Limited Entry Multi-season Bull Elk",
    r"Limited Entry Bull Elk",
    r"Cwmu Buck Deer",
    r"CWMU Buck Deer",
    r"Cwmu Bull Elk",
    r"CWMU Bull Elk",
    r"Cwmu Buck Pronghorn",
    r"CWMU Buck Pronghorn",
    r"Dedicated Hunter",
    r"General Season Buck Deer",
    r"Youth General Season Buck Deer",
    r"Youth Dedicated Hunter",
    r"Antlerless Pronghorn",
    r"Doe Pronghorn",
    r"Youth Doe Pronghorn",
    r"Youth Antlerless Pronghorn",
    r"Antlerless Moose",
    r"Cow Moose",
    r"Antlerless Deer",
    r"Youth Antlerless Deer",
    r"Antlerless Elk",
    r"Youth Antlerless Elk",
    r"Cow Elk",
    r"Bison",
    r"Buck Pronghorn",
    r"Buck Deer",
    r"Bull Elk",
    r"Bull Moose",
    r"Mountain Goat",
    r"Cougar",
    r"Black Bear",
]

WEAPON_SUFFIXES = [
    "Any Legal Weapon",
    "ALW",
    "Archery",
    "Muzzleloader",
    "Multi-season",
    "Mzl",
    "Muzzleloader Only",
    "Archery Only",
    "Hounds",
]


def clean(value):
    return "" if value is None else str(value).strip()


def norm_text(value):
    text = clean(value).lower()
    text = text.replace("&", "and")
    text = text.replace("'", "")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def norm_code(value):
    return re.sub(r"[^A-Z0-9]", "", clean(value).upper())


def blank_counts(rows, fields):
    counts = {field: 0 for field in fields}
    for row in rows:
        for field in fields:
            if not clean(row.get(field)):
                counts[field] += 1
    return counts


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def load_boundary_lookup():
    by_name = defaultdict(dict)
    source_rows = []
    for path in BOUNDARY_SOURCES:
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        for feature in payload.get("features", []):
            props = feature.get("properties") or {}
            boundary_id = clean(
                props.get("boundary_id")
                or props.get("BoundaryID")
                or props.get("BOUNDARY_ID")
                or props.get("id")
            )
            name = clean(
                props.get("boundary_name")
                or props.get("Boundary_Name")
                or props.get("name")
                or props.get("NAME")
            )
            if not boundary_id or not name:
                continue
            key = norm_text(name)
            by_name[key][boundary_id] = {
                "boundary_id": boundary_id,
                "boundary_name": name,
                "boundary_source": str(path.relative_to(REPO)),
            }
            source_rows.append(
                {
                    "boundary_id": boundary_id,
                    "boundary_name": name,
                    "boundary_name_norm": key,
                    "boundary_source": str(path.relative_to(REPO)),
                }
            )
    return by_name, source_rows


def extract_hunt_lines():
    try:
        import pdfplumber
    except Exception as exc:  # pragma: no cover - environment guard
        raise RuntimeError("pdfplumber is required for source PDF hunt-line extraction") from exc

    by_code = {}
    proof_rows = []
    for pdf_path in sorted(RAW_PDF_DIR.glob("*.pdf")):
        upper_name = pdf_path.name.upper()
        if "SUMMARY" in upper_name or "PURCHASE" in upper_name:
            continue
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page_index, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                for line in text.splitlines():
                    line = clean(line)
                    if "Hunt:" not in line:
                        continue
                    match = re.search(r"Hunt:\s*([A-Z]{1,3}\d{3,4})\s+(.+)$", line)
                    if not match:
                        continue
                    code = norm_code(match.group(1))
                    title = clean(match.group(2))
                    unit = extract_unit_name(title)
                    if not code or not unit:
                        continue
                    # Keep the first parsed source line; duplicates normally repeat the same title.
                    by_code.setdefault(
                        code,
                        {
                            "hunt_code": code,
                            "hunt_line": line,
                            "parsed_unit": unit,
                            "parsed_unit_norm": norm_text(unit),
                            "source_pdf": str(pdf_path.relative_to(REPO)),
                            "pdf_page": page_index,
                        },
                    )
                    proof_rows.append(
                        {
                            "hunt_code": code,
                            "hunt_line": line,
                            "parsed_unit": unit,
                            "parsed_unit_norm": norm_text(unit),
                            "source_pdf": str(pdf_path.relative_to(REPO)),
                            "pdf_page": page_index,
                        }
                    )
    return by_code, proof_rows


def extract_unit_name(title):
    text = clean(title)
    text = re.sub(r"\s+Page\s+\d+\s*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+\d{1,2}/\d{1,2}/\d{4}\s*$", "", text)
    for prefix in PROGRAM_PREFIXES:
        text = re.sub(rf"^{prefix}\s*-\s*", "", text, flags=re.IGNORECASE)
    parts = [clean(part) for part in text.split(" - ") if clean(part)]
    if len(parts) >= 2 and norm_text(parts[-1]) in {norm_text(w) for w in WEAPON_SUFFIXES}:
        parts = parts[:-1]
    unit = " - ".join(parts) if parts else text
    unit = re.sub(r"\s+", " ", unit).strip(" -")
    return unit


def duplicate_strict_key_count(rows):
    keys = Counter()
    for row in rows:
        key = (
            clean(row.get("source_year") or row.get("year") or row.get("actual_draw_year")),
            clean(row.get("model_year") or row.get("model_target_year") or row.get("permits_year")),
            clean(row.get("source_scope") or row.get("source_namespace") or row.get("draw_source_namespace")),
            norm_code(row.get("hunt_code")),
            clean(row.get("residency")),
            clean(row.get("points")),
            clean(row.get("row_type") or row.get("record_type")),
        )
        keys[key] += 1
    return sum(1 for count in keys.values() if count > 1)


def main():
    AUDIT.mkdir(parents=True, exist_ok=True)
    BACKUPS.mkdir(parents=True, exist_ok=True)

    fields, rows = read_csv(TARGET)
    before_counts = blank_counts(
        rows,
        [
            "sex",
            "sex_type",
            "boundary_id",
            "weapon",
            "draw_design",
            "permits_year_res",
            "permits_year_nr",
            "permits_year_total",
        ],
    )

    boundary_lookup, boundary_source_rows = load_boundary_lookup()
    hunt_lines_by_code, hunt_line_proof_rows = extract_hunt_lines()

    exact_boundary_by_code = {}
    ambiguous_boundary_rows = []
    unmatched_boundary_rows = []
    for code in sorted({norm_code(row.get("hunt_code")) for row in rows if not clean(row.get("boundary_id"))}):
        proof = hunt_lines_by_code.get(code)
        if not proof:
            unmatched_boundary_rows.append(
                {
                    "hunt_code": code,
                    "reason": "NO_HUNT_LINE_FOUND_IN_2019_RAW_PDFS",
                    "parsed_unit": "",
                    "source_pdf": "",
                    "candidate_boundary_ids": "",
                    "candidate_boundary_names": "",
                }
            )
            continue
        candidates = list(boundary_lookup.get(proof["parsed_unit_norm"], {}).values())
        if len(candidates) == 1:
            exact_boundary_by_code[code] = {
                **proof,
                **candidates[0],
                "boundary_match_status": "EXACT_NORMALIZED_UNIT_NAME_MATCH",
            }
        elif len(candidates) > 1:
            ambiguous_boundary_rows.append(
                {
                    "hunt_code": code,
                    "reason": "AMBIGUOUS_EXACT_NORMALIZED_UNIT_NAME_MATCH",
                    "parsed_unit": proof["parsed_unit"],
                    "parsed_unit_norm": proof["parsed_unit_norm"],
                    "source_pdf": proof["source_pdf"],
                    "pdf_page": proof["pdf_page"],
                    "candidate_boundary_ids": "|".join(c["boundary_id"] for c in candidates),
                    "candidate_boundary_names": "|".join(c["boundary_name"] for c in candidates),
                    "candidate_boundary_sources": "|".join(c["boundary_source"] for c in candidates),
                }
            )
        else:
            unmatched_boundary_rows.append(
                {
                    "hunt_code": code,
                    "reason": "NO_EXACT_NORMALIZED_UNIT_NAME_MATCH",
                    "parsed_unit": proof["parsed_unit"],
                    "parsed_unit_norm": proof["parsed_unit_norm"],
                    "source_pdf": proof["source_pdf"],
                    "pdf_page": proof["pdf_page"],
                    "candidate_boundary_ids": "",
                    "candidate_boundary_names": "",
                }
            )

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = BACKUPS / f"{TARGET.stem}.backup_before_sex_boundary_fill_{timestamp}.csv"
    shutil.copy2(TARGET, backup_path)

    mutations = []
    protected_before = {field: Counter(clean(row.get(field)) for row in rows) for field in PROTECTED_DRAW_FIELDS}
    for idx, row in enumerate(rows, start=2):
        code = norm_code(row.get("hunt_code"))
        species_norm = norm_text(row.get("species"))

        if species_norm in SPECIES_SEX_DEFAULTS:
            sex_value, reason = SPECIES_SEX_DEFAULTS[species_norm]
            for col in ("sex", "sex_type"):
                if col in fields and not clean(row.get(col)):
                    old = row.get(col, "")
                    row[col] = sex_value
                    mutations.append(
                        {
                            "row_number": idx,
                            "hunt_code": code,
                            "column": col,
                            "old_value": old,
                            "new_value": sex_value,
                            "source_type": "USER_APPROVED_SPECIES_DEFAULT",
                            "source_detail": reason,
                        }
                    )

        if "boundary_id" in fields and not clean(row.get("boundary_id")) and code in exact_boundary_by_code:
            match = exact_boundary_by_code[code]
            old = row.get("boundary_id", "")
            row["boundary_id"] = match["boundary_id"]
            mutations.append(
                {
                    "row_number": idx,
                    "hunt_code": code,
                    "column": "boundary_id",
                    "old_value": old,
                    "new_value": match["boundary_id"],
                    "source_type": "OFFICIAL_BOUNDARY_GEOJSON_EXACT_NAME_MATCH",
                    "source_detail": (
                        f"{match['boundary_name']} | {match['boundary_source']} | "
                        f"{match['source_pdf']} page {match['pdf_page']}"
                    ),
                }
            )

    protected_after = {field: Counter(clean(row.get(field)) for row in rows) for field in PROTECTED_DRAW_FIELDS}
    protected_changed = [
        field for field in sorted(PROTECTED_DRAW_FIELDS) if protected_before[field] != protected_after[field]
    ]

    after_counts = blank_counts(rows, before_counts.keys())
    duplicate_groups = duplicate_strict_key_count(rows)

    tmp_path = TARGET.with_suffix(".tmp")
    write_csv(tmp_path, rows, fields)
    shutil.move(str(tmp_path), str(TARGET))

    column_counts = Counter(m["column"] for m in mutations)
    write_csv(
        AUDIT / "2019_sex_boundary_fill_mutation_samples.csv",
        mutations[:500],
        ["row_number", "hunt_code", "column", "old_value", "new_value", "source_type", "source_detail"],
    )
    write_csv(
        AUDIT / "2019_sex_boundary_fill_column_counts.csv",
        [{"column": col, "mutation_count": count} for col, count in sorted(column_counts.items())],
        ["column", "mutation_count"],
    )
    write_csv(
        AUDIT / "2019_boundary_fill_exact_matches.csv",
        list(exact_boundary_by_code.values()),
        [
            "hunt_code",
            "parsed_unit",
            "parsed_unit_norm",
            "boundary_id",
            "boundary_name",
            "boundary_source",
            "boundary_match_status",
            "source_pdf",
            "pdf_page",
            "hunt_line",
        ],
    )
    write_csv(
        AUDIT / "2019_boundary_fill_ambiguous_review.csv",
        ambiguous_boundary_rows,
        [
            "hunt_code",
            "reason",
            "parsed_unit",
            "parsed_unit_norm",
            "source_pdf",
            "pdf_page",
            "candidate_boundary_ids",
            "candidate_boundary_names",
            "candidate_boundary_sources",
        ],
    )
    write_csv(
        AUDIT / "2019_boundary_fill_unmatched_review.csv",
        unmatched_boundary_rows,
        [
            "hunt_code",
            "reason",
            "parsed_unit",
            "parsed_unit_norm",
            "source_pdf",
            "pdf_page",
            "candidate_boundary_ids",
            "candidate_boundary_names",
        ],
    )
    write_csv(
        AUDIT / "2019_boundary_source_manifest.csv",
        boundary_source_rows,
        ["boundary_id", "boundary_name", "boundary_name_norm", "boundary_source"],
    )
    write_csv(
        AUDIT / "2019_raw_pdf_hunt_line_proof.csv",
        hunt_line_proof_rows,
        ["hunt_code", "hunt_line", "parsed_unit", "parsed_unit_norm", "source_pdf", "pdf_page"],
    )

    status = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "target": str(TARGET),
        "backup_path": str(backup_path),
        "row_count": len(rows),
        "column_count": len(fields),
        "before_blank_counts": before_counts,
        "after_blank_counts": after_counts,
        "mutation_counts": dict(sorted(column_counts.items())),
        "exact_boundary_code_matches": len(exact_boundary_by_code),
        "ambiguous_boundary_code_matches": len(ambiguous_boundary_rows),
        "unmatched_boundary_code_matches": len(unmatched_boundary_rows),
        "duplicate_strict_key_groups": duplicate_groups,
        "protected_draw_fields_changed": protected_changed,
        "status": "PASS" if not protected_changed and duplicate_groups == 0 else "REVIEW_REQUIRED",
        "audit_outputs": [
            str(AUDIT / "2019_sex_boundary_fill_mutation_samples.csv"),
            str(AUDIT / "2019_sex_boundary_fill_column_counts.csv"),
            str(AUDIT / "2019_boundary_fill_exact_matches.csv"),
            str(AUDIT / "2019_boundary_fill_ambiguous_review.csv"),
            str(AUDIT / "2019_boundary_fill_unmatched_review.csv"),
            str(AUDIT / "2019_boundary_source_manifest.csv"),
            str(AUDIT / "2019_raw_pdf_hunt_line_proof.csv"),
        ],
    }
    (AUDIT / "2019_SEX_BOUNDARY_FILL_STATUS.json").write_text(
        json.dumps(status, indent=2), encoding="utf-8"
    )
    report = [
        "# 2019 Sex / Boundary Fill",
        "",
        f"Generated UTC: {status['generated_utc']}",
        f"Target: `{TARGET}`",
        f"Backup: `{backup_path}`",
        "",
        "## Result",
        "",
        f"Status: `{status['status']}`",
        f"Rows: {len(rows)}",
        f"Duplicate strict-key groups: {duplicate_groups}",
        f"Protected draw-result fields changed: {', '.join(protected_changed) if protected_changed else 'none'}",
        "",
        "## Mutation Counts",
        "",
    ]
    for col, count in sorted(column_counts.items()):
        report.append(f"- `{col}`: {count}")
    report.extend(
        [
            "",
            "## Boundary Matching",
            "",
            f"Exact boundary code matches applied: {len(exact_boundary_by_code)}",
            f"Ambiguous boundary code matches held for review: {len(ambiguous_boundary_rows)}",
            f"Unmatched boundary code matches held for review: {len(unmatched_boundary_rows)}",
            "",
            "Only exact normalized unit-name matches to official boundary GeoJSON were applied. "
            "Ambiguous and unmatched rows were not guessed.",
        ]
    )
    (AUDIT / "2019_SEX_BOUNDARY_FILL_REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
