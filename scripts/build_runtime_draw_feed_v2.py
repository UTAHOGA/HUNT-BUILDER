import csv
import hashlib
import json
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
INPUT_LONG = REPO / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
INPUT_2026_SCORABLE = REPO / "outputs" / "2026 scorable draw results.csv"
CURRENT_RUNTIME = REPO / "processed_data" / "draw_reality_engine.csv"
DATABASE_2026 = REPO / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
RAW_INVENTORY = REPO / "data_model" / "quality" / "raw_pdf_inventory.csv"
OUT_DIR = REPO / "data_model" / "runtime_drafts"

OUT_V2 = OUT_DIR / "draw_reality_engine_v2.csv"
OUT_MANIFEST = OUT_DIR / "draw_reality_engine_v2_manifest.json"
OUT_VALIDATION = OUT_DIR / "draw_reality_engine_v2_validation_report.json"
OUT_COMPARE = OUT_DIR / "draw_reality_engine_v2_vs_current_report.json"
OUT_ROWS_ADDED = OUT_DIR / "draw_reality_engine_v2_rows_added.csv"
OUT_SCHEMA_CHANGES = OUT_DIR / "draw_reality_engine_v2_schema_changes.csv"
OUT_COLLAPSED_DUPES = OUT_DIR / "draw_reality_engine_v2_collapsed_duplicate_scorable_rows.csv"


def configure_output_dir(out_dir: Path) -> None:
    global OUT_DIR, OUT_V2, OUT_MANIFEST, OUT_VALIDATION, OUT_COMPARE, OUT_ROWS_ADDED, OUT_SCHEMA_CHANGES, OUT_COLLAPSED_DUPES
    OUT_DIR = out_dir
    OUT_V2 = OUT_DIR / "draw_reality_engine_v2.csv"
    OUT_MANIFEST = OUT_DIR / "draw_reality_engine_v2_manifest.json"
    OUT_VALIDATION = OUT_DIR / "draw_reality_engine_v2_validation_report.json"
    OUT_COMPARE = OUT_DIR / "draw_reality_engine_v2_vs_current_report.json"
    OUT_ROWS_ADDED = OUT_DIR / "draw_reality_engine_v2_rows_added.csv"
    OUT_SCHEMA_CHANGES = OUT_DIR / "draw_reality_engine_v2_schema_changes.csv"
    OUT_COLLAPSED_DUPES = OUT_DIR / "draw_reality_engine_v2_collapsed_duplicate_scorable_rows.csv"

REQUIRED_COLUMNS = [
    "hunt_code",
    "boundary_id",
    "hunt_name",
    "species",
    "sex_type",
    "hunt_type",
    "weapon",
    "hunt_class",
    "draw_design",
    "season",
    "year",
    "draw_pool",
    "residency",
    "points",
    "eligible_applicants",
    "bonus_permits",
    "regular_permits",
    "total_permits",
    "success_ratio",
    "source_file",
    "source_pdf_page",
    "source_report_page",
    "source_sha256",
    "validation_status",
    "validation_notes",
]

SCORABLE_RECORD_TYPES = {
    "point_level_draw_result",
    "point_row",
    "point_level",
    "sportsman_total",
    "sportsman_total_draw_result",
    "sportsman_random_total",
}

NON_SCORABLE_RECORD_TYPES = {
    "hunt_planner_permit_quota",
    "quota",
    "quota_row",
    "permit_quota",
    "hunt_total_draw_result",
    "total",
    "total_row",
    "supplemental_permit_total_row",
    "availability_only",
    "conservation_auction_allocation",
    "allocation_only",
    "reference_only",
    "point_purchase_reference",
    "cwmu_contact_operator_reference_only",
}


def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, headers, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        w.writerows(rows)


def clean(value):
    return "" if value is None else str(value).strip()


def normalize_int(value):
    t = clean(value)
    if not t:
        return ""
    try:
        return str(int(float(t)))
    except Exception:
        return ""


def normalize_year(value):
    t = normalize_int(value)
    return t


def normalize_residency(value):
    t = clean(value).lower()
    if t in {"res", "resident", "r"}:
        return "Resident"
    if t in {"nr", "nonresident", "non-resident", "non resident", "n"}:
        return "Nonresident"
    return clean(value)


def normalize_success_ratio(value):
    t = clean(value)
    if not t:
        return ""
    stripped = t.replace("%", "")
    try:
        return f"{float(stripped):.6f}".rstrip("0").rstrip(".")
    except Exception:
        return t


def success_ratio_from_counts(eligible_applicants, total_permits):
    eligible = normalize_int(eligible_applicants)
    permits = normalize_int(total_permits)
    if eligible == "" or permits == "":
        return ""
    eligible_n = int(eligible)
    permits_n = int(permits)
    if eligible_n <= 0 or permits_n <= 0:
        return "N/A"
    return f"{permits_n / eligible_n:.6f}".rstrip("0").rstrip(".")


def first_nonempty(row, *fields):
    for field in fields:
        value = clean(row.get(field))
        if value:
            return value
    return ""


def row_year(row):
    return normalize_year(first_nonempty(row, "actual_draw_year", "year", "source_year"))


def record_type(row):
    return clean(first_nonempty(row, "record_type", "row_type", "record_kind")).lower()


def derive_draw_design(row):
    existing = first_nonempty(row, "draw_design", "draw_pool")
    if existing:
        return existing

    text = " ".join(
        clean(row.get(field)).lower()
        for field in (
            "hunt_code",
            "hunt_name",
            "species",
            "sex_type",
            "hunt_type",
            "hunt_class",
            "weapon",
            "source_scope",
            "source_file",
        )
    )
    hunt_type = clean(row.get("hunt_type")).lower()
    code = clean(row.get("hunt_code")).upper()

    if "sportsman" in text:
        return "Random"
    if "cougar" in text or code.startswith("CG"):
        return "Unlimited"
    if "o.t.c" in text or "otc" in text or "over-the-counter" in text or "over the counter" in text:
        return "Capped Permits"
    if "private land" in text or "pursuit" in text or "spot and stalk" in text:
        return "Capped Permits"
    if "dedicated hunter" in text:
        return "Preference"
    if "management" in text:
        return "Max/Weighted Split"
    if "general season" in hunt_type or "general season" in text:
        return "Preference"
    if "antlerless" in text or "doe pronghorn" in text:
        return "Preference"
    if "limited entry" in hunt_type or "limited-entry" in text:
        return "Max/Weighted Split"
    if "once-in-a-lifetime" in hunt_type or "once in a lifetime" in text:
        return "Max/Weighted Split"
    if "cwmu" in text:
        return "Max/Weighted Split"
    if "conservation" in text:
        return "Organizations"
    if code.startswith(("DA", "EA", "PD")):
        return "Preference"
    if code.startswith(("DB", "EB", "PB", "MB", "BI", "DS", "RS", "GO", "BR", "TK")):
        return "Max/Weighted Split"
    return ""


def is_scorable_truth_row(row):
    status = clean(row.get("algorithm_status")).upper()
    qa_status = clean(row.get("qa_status")).lower()
    if status.startswith("NON_SCORABLE") or "quota_only" in qa_status:
        return False

    hunt_type = clean(row.get("hunt_type")).lower()
    draw_design = clean(first_nonempty(row, "draw_design", "draw_pool")).lower()
    source_scope = clean(row.get("source_scope")).lower()
    text = " ".join(
        clean(row.get(key)).lower()
        for key in ("record_type", "hunt_type", "draw_design", "draw_pool", "source_scope", "source_file", "notes")
    )
    if (
        hunt_type == "conservation"
        or draw_design in {"organizations", "organization"}
        or "conservation_auction_allocation" in text
        or "allocation/reference" in text
        or "allocation_only" in text
        or "conservation" in source_scope
    ):
        return False

    kind = record_type(row)
    if kind in NON_SCORABLE_RECORD_TYPES:
        return False
    if kind in SCORABLE_RECORD_TYPES:
        return True

    # Older truth surfaces sometimes omitted record_type but still had a real
    # point/residency/applicant ladder. Keep those, but never keep quota rows.
    return bool(
        clean(row.get("hunt_code"))
        and row_year(row)
        and clean(first_nonempty(row, "residency"))
        and clean(first_nonempty(row, "points")) != ""
        and clean(first_nonempty(row, "eligible_applicants", "applicants"))
    )


def expanded_engine_rows(row):
    if clean(row.get("residency")):
        return [row]

    expanded = []
    for residency, prefix in (("Resident", "resident"), ("Nonresident", "nonresident")):
        has_data = any(
            clean(row.get(f"{prefix}_{field}"))
            for field in (
                "eligible_applicants",
                "bonus_permits",
                "regular_permits",
                "total_permits",
                "success_ratio",
                "p_draw",
                "p_draw_percent",
            )
        )
        if not has_data:
            continue
        out = dict(row)
        out["residency"] = residency
        out["eligible_applicants"] = clean(row.get(f"{prefix}_eligible_applicants"))
        out["bonus_permits"] = clean(row.get(f"{prefix}_bonus_permits"))
        out["regular_permits"] = clean(row.get(f"{prefix}_regular_permits"))
        out["total_permits"] = clean(row.get(f"{prefix}_total_permits"))
        out["success_ratio"] = clean(row.get(f"{prefix}_success_ratio"))
        out["p_draw"] = clean(row.get(f"{prefix}_p_draw"))
        out["p_draw_percent"] = clean(row.get(f"{prefix}_p_draw_percent"))
        expanded.append(out)
    return expanded or [row]


def load_truth_rows():
    long_rows = read_csv(INPUT_LONG)
    expanded_long_rows = [expanded for row in long_rows for expanded in expanded_engine_rows(row)]
    scorable_rows = [row for row in expanded_long_rows if is_scorable_truth_row(row)]
    replaced_2026_rows = 0
    source_note = str(INPUT_LONG.relative_to(REPO)).replace("\\", "/")

    if INPUT_2026_SCORABLE.exists():
        expanded_2026_rows = [expanded for row in read_csv(INPUT_2026_SCORABLE) for expanded in expanded_engine_rows(row)]
        scorable_2026_rows = [row for row in expanded_2026_rows if is_scorable_truth_row(row)]
        replaced_2026_rows = len([row for row in scorable_rows if row_year(row) == "2026"])
        scorable_rows = [row for row in scorable_rows if row_year(row) != "2026"] + scorable_2026_rows
        source_note = (
            f"{str(INPUT_LONG.relative_to(REPO)).replace('\\', '/')} "
            f"with 2026 slice replaced by {str(INPUT_2026_SCORABLE.relative_to(REPO)).replace('\\', '/')}"
        )

    return scorable_rows, {
        "source_note": source_note,
        "long_input_rows": len(long_rows),
        "long_expanded_rows": len(expanded_long_rows),
        "long_scorable_rows_after_filter": len([row for row in expanded_long_rows if is_scorable_truth_row(row)]),
        "replaced_2026_scorable_rows": replaced_2026_rows,
        "input_2026_scorable_path": str(INPUT_2026_SCORABLE.relative_to(REPO)).replace("\\", "/")
        if INPUT_2026_SCORABLE.exists()
        else "",
        "input_2026_scorable_rows": len(scorable_2026_rows) if INPUT_2026_SCORABLE.exists() else 0,
        "final_scorable_rows": len(scorable_rows),
    }


def collapse_duplicate_scorable_rows(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[key_full(row)].append(row)

    collapsed = []
    collapse_audit = []
    for key, group in grouped.items():
        if len(group) == 1:
            collapsed.append(group[0])
            continue

        base = dict(group[0])
        for field in ("eligible_applicants", "bonus_permits", "regular_permits", "total_permits"):
            base[field] = str(sum(int(normalize_int(row.get(field)) or 0) for row in group))
        base["success_ratio"] = success_ratio_from_counts(base["eligible_applicants"], base["total_permits"])

        source_files = []
        for row in group:
            source_file = clean(row.get("source_file"))
            if source_file and source_file not in source_files:
                source_files.append(source_file)
        if source_files:
            base["source_file"] = "; ".join(source_files[:5])

        notes = clean(base.get("validation_notes"))
        suffix = f"COLLAPSED_DUPLICATE_SCORABLE_ROWS={len(group)}"
        base["validation_notes"] = f"{notes};{suffix}" if notes else suffix
        collapsed.append(base)
        collapse_audit.append(
            {
                "key": key,
                "collapsed_row_count": len(group),
                "hunt_code": base.get("hunt_code", ""),
                "year": base.get("year", ""),
                "draw_pool": base.get("draw_pool", ""),
                "residency": base.get("residency", ""),
                "points": base.get("points", ""),
                "eligible_applicants_sum": base.get("eligible_applicants", ""),
                "total_permits_sum": base.get("total_permits", ""),
                "source_files": base.get("source_file", ""),
            }
        )

    return collapsed, collapse_audit


DRAW_POOL_VALUES = {
    "standard",
    "youth",
    "lifetime",
    "dedicated_hunter",
    "youth_dedicated_hunter",
    "youth_turkey",
    "youth_mature_bull",
    "sportsman",
    "hunt_expo",
}


def _join_nonempty(parts):
    return " ".join([p for p in parts if clean(p)]).strip()


def synthesize_hunt_class(species, sex_type, hunt_type, weapon):
    sp = clean(species)
    sx = clean(sex_type)
    ht = clean(hunt_type)
    wp = clean(weapon)
    ht_l = ht.lower()
    wp_l = wp.lower()
    wp_specific = "" if wp_l in {"", "any legal weapon"} else wp

    if "cwmu" in ht_l:
        return _join_nonempty(["CWMU", sx, sp])
    if "once-in-a-lifetime" in ht_l or "once in a lifetime" in ht_l or ht_l == "oial":
        return _join_nonempty(["Once-in-a-lifetime", sx, sp])
    if "premium limited entry" in ht_l:
        return _join_nonempty(["Premium Limited-entry", wp_specific, sx, sp])
    if "limited entry" in ht_l:
        return _join_nonempty(["Limited-entry", wp_specific, sx, sp])
    if "antlerless" in ht_l:
        return _join_nonempty(["Antlerless", sp])
    if "general season" in ht_l:
        return _join_nonempty(["General-season", wp_specific, sx, sp])
    if "dedicated hunter" in ht_l:
        return _join_nonempty(["Dedicated Hunter", sp])
    if "lifetime" in ht_l:
        return _join_nonempty(["Lifetime", sx, sp])
    if "sportsman" in ht_l:
        return _join_nonempty(["Sportsman", sx, sp])
    if "expo" in ht_l:
        return _join_nonempty(["Hunt Expo", sx, sp])
    if ht:
        return _join_nonempty([ht, wp_specific, sx, sp])
    return _join_nonempty([wp_specific, sx, sp])


def normalize_hunt_class(raw_hunt_class, species, sex_type, hunt_type, weapon):
    hc = clean(raw_hunt_class)
    hc_l = hc.lower()
    ht = clean(hunt_type)
    ht_l = ht.lower()
    if hc and hc_l not in DRAW_POOL_VALUES and hc_l != ht_l:
        return hc
    return synthesize_hunt_class(species, sex_type, hunt_type, weapon)


def sha256_file(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def key_full(row):
    return "|".join(
        [
            clean(row.get("hunt_code")).upper(),
            clean(row.get("year")),
            clean(row.get("draw_pool")).lower(),
            clean(row.get("residency")),
            clean(row.get("points")),
        ]
    )


def key_no_pool(row):
    return "|".join(
        [
            clean(row.get("hunt_code")).upper(),
            clean(row.get("year")),
            clean(row.get("residency")),
            clean(row.get("points")),
        ]
    )


def build_source_sha_index():
    if not RAW_INVENTORY.exists():
        return {}
    rows = read_csv(RAW_INVENTORY)
    index = defaultdict(list)
    for row in rows:
        fn = clean(row.get("filename")).lower()
        if not fn:
            continue
        index[fn].append(
            {
                "sha256": clean(row.get("sha256")),
                "inferred_year": clean(row.get("inferred_year")),
                "path": clean(row.get("path")),
            }
        )
    return index


def choose_source_sha(source_sha_index, source_file, year):
    fn = clean(source_file).lower()
    if not fn:
        return ""
    options = source_sha_index.get(fn, [])
    if not options:
        return ""
    uniq_sha = sorted({x["sha256"] for x in options if x["sha256"]})
    if len(uniq_sha) == 1:
        return uniq_sha[0]
    year = clean(year)
    year_match = [x for x in options if clean(x.get("inferred_year")) == year and x.get("sha256")]
    if year_match:
        return year_match[0]["sha256"]
    draw_candidates = [x for x in options if "/draw_odds/" in x.get("path", "").replace("\\", "/").lower() and x.get("sha256")]
    if draw_candidates:
        return draw_candidates[0]["sha256"]
    return options[0].get("sha256", "")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default=None, help="Directory for generated runtime feed artifacts.")
    args = parser.parse_args()
    if args.out_dir:
        configure_output_dir((REPO / args.out_dir).resolve() if not Path(args.out_dir).is_absolute() else Path(args.out_dir))

    if not INPUT_LONG.exists():
        raise FileNotFoundError(f"Missing draw truth input: {INPUT_LONG}")
    if not DATABASE_2026.exists():
        raise FileNotFoundError(f"Missing DATABASE source: {DATABASE_2026}")
    if not CURRENT_RUNTIME.exists():
        raise FileNotFoundError(f"Missing current runtime feed: {CURRENT_RUNTIME}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    v3_rows, truth_input_report = load_truth_rows()
    current_rows = read_csv(CURRENT_RUNTIME)
    db_rows = read_csv(DATABASE_2026)

    db_code_to_boundary = {}
    db_codes = set()
    for row in db_rows:
        code = clean(row.get("hunt_code")).upper()
        if not code:
            continue
        db_codes.add(code)
        bid = clean(row.get("boundary_id"))
        if bid:
            db_code_to_boundary[code] = bid

    source_sha_index = build_source_sha_index()

    out_rows = []
    validation_counter = Counter()

    for row in v3_rows:
        hunt_code = clean(row.get("hunt_code")).upper()
        year = row_year(row)
        draw_design = derive_draw_design(row)
        draw_pool = clean(first_nonempty(row, "draw_pool") or draw_design).lower()
        residency = normalize_residency(first_nonempty(row, "residency"))
        points = normalize_int(first_nonempty(row, "points"))
        if points == "" and record_type(row) in {"sportsman_total", "sportsman_total_draw_result", "sportsman_random_total"}:
            points = "0"
        boundary_id = clean(row.get("boundary_id"))

        code_in_db = hunt_code in db_codes if hunt_code else False
        if code_in_db and not boundary_id:
            boundary_id = db_code_to_boundary.get(hunt_code, "")

        notes = []
        status = "VALID"

        if code_in_db:
            if not boundary_id:
                status = "INVALID"
                notes.append("DATABASE_MATCH_BOUNDARY_ID_MISSING")
            else:
                notes.append("DATABASE_MATCHED")
        else:
            notes.append("HUNT_CODE_NOT_IN_2026_DATABASE")
            validation_counter["rows_hunt_code_not_in_2026_database"] += 1

        if not hunt_code:
            status = "INVALID"
            notes.append("HUNT_CODE_BLANK")
        if not year:
            status = "INVALID"
            notes.append("YEAR_BLANK")
        if not draw_pool:
            status = "INVALID"
            notes.append("DRAW_POOL_BLANK")
        if not residency:
            status = "INVALID"
            notes.append("RESIDENCY_BLANK")
        if points == "":
            status = "INVALID"
            notes.append("POINTS_BLANK")

        source_file = clean(row.get("source_file"))
        source_pdf_page = normalize_int(first_nonempty(row, "source_pdf_page", "pdf_page"))
        source_report_page = normalize_int(first_nonempty(row, "source_report_page", "page_number", "pdf_page"))
        source_sha256 = choose_source_sha(source_sha_index, source_file, year)

        out_row = {
            "hunt_code": hunt_code,
            "boundary_id": boundary_id,
            "hunt_name": clean(row.get("hunt_name")),
            "species": clean(row.get("species")),
            "sex_type": clean(row.get("sex_type")),
            "hunt_type": clean(row.get("hunt_type")),
            "weapon": clean(row.get("weapon")),
            "hunt_class": normalize_hunt_class(
                first_nonempty(row, "hunt_class", "draw_design"),
                row.get("species"),
                row.get("sex_type"),
                row.get("hunt_type"),
                row.get("weapon"),
            ),
            "draw_design": clean(draw_design),
            "season": clean(row.get("season")),
            "year": year,
            "draw_pool": draw_pool,
            "residency": residency,
            "points": points,
            "eligible_applicants": normalize_int(row.get("eligible_applicants")),
            "bonus_permits": normalize_int(row.get("bonus_permits")),
            "regular_permits": normalize_int(row.get("regular_permits")),
            "total_permits": normalize_int(row.get("total_permits")),
            "success_ratio": normalize_success_ratio(row.get("success_ratio")),
            "source_file": source_file,
            "source_pdf_page": source_pdf_page,
            "source_report_page": source_report_page,
            "source_sha256": source_sha256,
            "validation_status": status,
            "validation_notes": ";".join(notes),
        }
        out_rows.append(out_row)

    out_rows, collapsed_duplicate_rows = collapse_duplicate_scorable_rows(out_rows)
    write_csv(
        OUT_COLLAPSED_DUPES,
        [
            "key",
            "collapsed_row_count",
            "hunt_code",
            "year",
            "draw_pool",
            "residency",
            "points",
            "eligible_applicants_sum",
            "total_permits_sum",
            "source_files",
        ],
        collapsed_duplicate_rows,
    )

    write_csv(OUT_V2, REQUIRED_COLUMNS, out_rows)

    # Validation
    row_count_v3 = len(v3_rows)
    row_count_v2 = len(out_rows)
    full_keys = [key_full(r) for r in out_rows]
    full_key_counts = Counter(full_keys)
    duplicate_keys = sum(1 for _, c in full_key_counts.items() if c > 1)

    blank_counts = {
        "hunt_code_blank_count": sum(1 for r in out_rows if not clean(r["hunt_code"])),
        "year_blank_count": sum(1 for r in out_rows if not clean(r["year"])),
        "draw_pool_blank_count": sum(1 for r in out_rows if not clean(r["draw_pool"])),
        "residency_blank_count": sum(1 for r in out_rows if not clean(r["residency"])),
        "points_blank_count": sum(1 for r in out_rows if clean(r["points"]) == ""),
        "draw_design_blank_count": sum(1 for r in out_rows if not clean(r["draw_design"])),
    }

    non_scorable_leaks = [
        row
        for row in out_rows
        if clean(row.get("validation_notes")).upper().startswith("NON_SCORABLE")
        or clean(row.get("draw_pool")) in {"hunt_planner_permit_quota", "quota"}
    ]

    db_matched_rows = [r for r in out_rows if "DATABASE_MATCHED" in clean(r["validation_notes"])]
    db_matched_missing_boundary = sum(1 for r in db_matched_rows if not clean(r["boundary_id"]))
    not_in_db_rows = [r for r in out_rows if "HUNT_CODE_NOT_IN_2026_DATABASE" in clean(r["validation_notes"])]
    not_in_db_codes = sorted({clean(r["hunt_code"]) for r in not_in_db_rows if clean(r["hunt_code"])})

    # Compare vs current runtime
    current_cols = list(current_rows[0].keys()) if current_rows else []
    current_has_draw_pool = "draw_pool" in current_cols
    current_no_pool_index = {}
    current_no_pool_dup = set()
    for r in current_rows:
        k = key_no_pool(r)
        if k in current_no_pool_index:
            current_no_pool_dup.add(k)
        else:
            current_no_pool_index[k] = r

    v2_no_pool_index = {}
    v2_no_pool_dup = set()
    for r in out_rows:
        k = key_no_pool(r)
        if k in v2_no_pool_index:
            v2_no_pool_dup.add(k)
        else:
            v2_no_pool_index[k] = r

    common_keys = sorted(set(current_no_pool_index.keys()) & set(v2_no_pool_index.keys()))
    comparable_common_keys = [k for k in common_keys if k not in current_no_pool_dup and k not in v2_no_pool_dup]

    # Core value integrity check vs current runtime: draw math fields only.
    core_shared_fields = [
        "eligible_applicants",
        "bonus_permits",
        "regular_permits",
        "total_permits",
    ]
    core_value_mismatches = []

    # Supplemental metadata drift check (expected to differ as schema matures).
    metadata_fields = ["hunt_name", "status", "source_file", "boundary_id"]
    metadata_value_mismatches = []
    for k in comparable_common_keys:
        c = current_no_pool_index[k]
        v = v2_no_pool_index[k]
        for f in core_shared_fields:
            cv = clean(c.get(f))
            vv = clean(v.get(f))
            cv = normalize_int(cv)
            vv = normalize_int(vv)
            if cv != vv:
                core_value_mismatches.append(
                    {"key_no_pool": k, "field": f, "current_value": cv, "v2_value": vv}
                )
        for f in metadata_fields:
            cv = clean(c.get(f))
            vv = clean(v.get(f))
            if cv != vv:
                metadata_value_mismatches.append(
                    {"key_no_pool": k, "field": f, "current_value": cv, "v2_value": vv}
                )

    # rows added vs current runtime
    current_row_count = len(current_rows)
    rows_added_vs_current = row_count_v2 - current_row_count

    # rows added file (by no-pool key presence)
    current_no_pool_keys = set(current_no_pool_index.keys())
    rows_added = [r for r in out_rows if key_no_pool(r) not in current_no_pool_keys]
    write_csv(OUT_ROWS_ADDED, REQUIRED_COLUMNS, rows_added)

    # schema change file
    v2_cols = REQUIRED_COLUMNS
    current_set = set(current_cols)
    v2_set = set(v2_cols)
    schema_rows = []
    for col in sorted(v2_set - current_set):
        schema_rows.append(
            {
                "column": col,
                "change_type": "ADDED_IN_V2_DRAFT",
                "current_runtime_has_column": "NO",
                "v2_runtime_has_column": "YES",
                "notes": "Required by V3 draw truth draft schema",
            }
        )
    for col in sorted(current_set - v2_set):
        schema_rows.append(
            {
                "column": col,
                "change_type": "ONLY_IN_CURRENT_RUNTIME",
                "current_runtime_has_column": "YES",
                "v2_runtime_has_column": "NO",
                "notes": "Current runtime field not required in this draft feed",
            }
        )
    write_csv(
        OUT_SCHEMA_CHANGES,
        ["column", "change_type", "current_runtime_has_column", "v2_runtime_has_column", "notes"],
        schema_rows,
    )

    validation_ok = (
        row_count_v2 > 0
        and row_count_v2 <= row_count_v3
        and duplicate_keys == 0
        and all(v == 0 for v in blank_counts.values())
        and db_matched_missing_boundary == 0
        and len(non_scorable_leaks) == 0
    )

    promotion_blockers = [
        "production processed_data not updated in this task",
        "website not updated in this task",
        "downstream code may need schema update for draw_pool",
    ]

    validation_report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_truth_path": truth_input_report["source_note"],
        "input_long_path": str(INPUT_LONG.relative_to(REPO)).replace("\\", "/"),
        "input_long_sha256": sha256_file(INPUT_LONG),
        "input_2026_scorable_sha256": sha256_file(INPUT_2026_SCORABLE) if INPUT_2026_SCORABLE.exists() else "",
        "truth_input_report": truth_input_report,
        "output_v2_path": str(OUT_V2.relative_to(REPO)).replace("\\", "/"),
        "row_count_v3": row_count_v3,
        "row_count_v2": row_count_v2,
        "row_count_equal": row_count_v3 == row_count_v2,
        "row_count_difference_reason": (
            "runtime feed collapses duplicate scorable keys by summing applicant/permit fields"
            if row_count_v3 != row_count_v2
            else ""
        ),
        "corrected_key_duplicate_count": duplicate_keys,
        "collapsed_duplicate_scorable_key_count": len(collapsed_duplicate_rows),
        "blank_counts": blank_counts,
        "db_matched_rows_count": len(db_matched_rows),
        "db_matched_rows_missing_boundary_id_count": db_matched_missing_boundary,
        "hunt_code_not_in_2026_database_rows_count": len(not_in_db_rows),
        "hunt_code_not_in_2026_database_hunt_code_count": len(not_in_db_codes),
        "hunt_code_not_in_2026_database_hunt_codes_sample": not_in_db_codes[:500],
        "validation_ok": validation_ok,
        "non_scorable_leak_count": len(non_scorable_leaks),
        "promotion_blockers": promotion_blockers,
    }

    compare_report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "current_runtime_path": str(CURRENT_RUNTIME.relative_to(REPO)).replace("\\", "/"),
        "current_runtime_row_count": current_row_count,
        "current_runtime_has_draw_pool": current_has_draw_pool,
        "v2_runtime_row_count": row_count_v2,
        "rows_added_vs_current_feed": rows_added_vs_current,
        "v2_rows_not_in_current_by_no_pool_key_count": len(rows_added),
        "common_no_pool_key_count": len(common_keys),
        "comparable_common_no_pool_key_count": len(comparable_common_keys),
        "current_no_pool_duplicate_key_count": len(current_no_pool_dup),
        "v2_no_pool_duplicate_key_count": len(v2_no_pool_dup),
        "core_draw_value_mismatch_count": len(core_value_mismatches),
        "core_draw_value_mismatch_samples": core_value_mismatches[:200],
        "metadata_value_mismatch_count": len(metadata_value_mismatches),
        "metadata_value_mismatch_samples": metadata_value_mismatches[:200],
        "expected_prior_audit_reference": {
            "v3_rows": 112056,
            "current_rows_approx": 36862,
            "expected_added_approx": 75194,
            "current_feed_lacks_draw_pool": True,
        },
        "promotion_blockers": promotion_blockers,
    }

    manifest = {
        "id": "draw_reality_engine_v2_draft",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "truth_source": truth_input_report["source_note"],
        "truth_source_sha256": sha256_file(INPUT_LONG),
        "truth_input_report": truth_input_report,
        "output_feed": str(OUT_V2.relative_to(REPO)).replace("\\", "/"),
        "required_key": "hunt_code + year + draw_pool + residency + points",
        "required_columns": REQUIRED_COLUMNS,
        "validation_report": str(OUT_VALIDATION.relative_to(REPO)).replace("\\", "/"),
        "comparison_report": str(OUT_COMPARE.relative_to(REPO)).replace("\\", "/"),
        "rows_added_file": str(OUT_ROWS_ADDED.relative_to(REPO)).replace("\\", "/"),
        "schema_changes_file": str(OUT_SCHEMA_CHANGES.relative_to(REPO)).replace("\\", "/"),
        "collapsed_duplicate_rows_file": str(OUT_COLLAPSED_DUPES.relative_to(REPO)).replace("\\", "/"),
        "notes": [
            "V3 is used as draw-result truth source",
            "Only scorable record types are admitted; quota/allotment/reference rows are excluded",
            "Duplicate scorable keys are collapsed by summing applicant/permit counts for runtime use",
            "2026 scorable slice is loaded from outputs/2026 scorable draw results.csv when present",
            "No production processed_data runtime feeds were overwritten in this task",
            "Historical hunt codes not in 2026 DATABASE are preserved and flagged",
        ],
    }

    OUT_VALIDATION.write_text(json.dumps(validation_report, indent=2), encoding="utf-8")
    OUT_COMPARE.write_text(json.dumps(compare_report, indent=2), encoding="utf-8")
    OUT_MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(json.dumps(
        {
            "row_count_v3": row_count_v3,
            "row_count_v2": row_count_v2,
            "corrected_key_duplicate_count": duplicate_keys,
            "collapsed_duplicate_scorable_key_count": len(collapsed_duplicate_rows),
            "non_scorable_leak_count": len(non_scorable_leaks),
            "rows_added_vs_current_feed": rows_added_vs_current,
            "current_runtime_has_draw_pool": current_has_draw_pool,
            "validation_ok": validation_ok,
        },
        indent=2,
    ))


if __name__ == "__main__":
    main()
