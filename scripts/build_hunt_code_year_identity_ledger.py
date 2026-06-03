import argparse
import csv
import difflib
import json
import re
import zipfile
from collections import Counter, defaultdict
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader


PREFIX_SPECIES = {
    "BI": "Bison",
    "BR": "Black Bear",
    "CG": "Cougar",
    "DA": "Antlerless Deer",
    "DB": "Buck Deer",
    "DS": "Desert Bighorn Sheep",
    "EA": "Antlerless Elk",
    "EB": "Bull Elk",
    "GO": "Mountain Goat",
    "MA": "Doe Pronghorn",
    "MB": "Bull Moose",
    "PB": "Buck Pronghorn",
    "PD": "Pronghorn",
    "RE": "Restricted",
    "RS": "Rocky Mountain Bighorn Sheep",
    "TK": "Turkey",
}

SPORTSMAN_2022_ROWS = [
    ("BI1000", "Sportsman Bison", 1, 0, 5964, 0, 5965, 1, 0, 1, "1 in 5,965.0", "N/A"),
    ("BR1000", "Sportsman Black Bear", 1, 0, 1584, 0, 1585, 1, 0, 1, "1 in 1,585.0", "N/A"),
    ("CG1000", "Sportsman Cougar", 1, 0, 1410, 0, 1411, 1, 0, 1, "1 in 1,411.0", "N/A"),
    ("DB0007", "Sportsman Deer", 1, 0, 10593, 0, 10594, 1, 0, 1, "1 in 10,594.0", "N/A"),
    ("DS1000", "Sportsman Desert Bighorn Sheep", 1, 0, 5085, 0, 5086, 1, 0, 1, "1 in 5,086.0", "N/A"),
    ("EB1000", "Sportsman Elk", 1, 0, 10846, 0, 10847, 1, 0, 1, "1 in 10,847.0", "N/A"),
    ("GO1000", "Sportsman Mountain Goat", 1, 0, 4112, 0, 4113, 1, 0, 1, "1 in 4,113.0", "N/A"),
    ("MB1000", "Sportsman Moose", 1, 0, 6584, 0, 6585, 1, 0, 1, "1 in 6,585.0", "N/A"),
    ("PB1000", "Sportsman Pronghorn", 1, 0, 4527, 0, 4528, 1, 0, 1, "1 in 4,528.0", "N/A"),
    ("RS0001", "Sportsman Rocky Mtn Bighorn Sheep", 1, 0, 5237, 0, 5238, 1, 0, 1, "1 in 5,238.0", "N/A"),
    ("TK0001", "Sportsman Bearded Turkey", 1, 0, 1246, 0, 1247, 1, 0, 1, "1 in 1,247.0", "N/A"),
]


def norm(value):
    return re.sub(r"\s+", " ", (value or "").replace("\xa0", " ")).strip()


def norm_name(value):
    return norm(re.sub(r"[^a-z0-9]+", " ", norm(value).lower()))


def prefix_of(code):
    match = re.match(r"^([A-Z]+)", code or "")
    return match.group(1) if match else ""


def read_csv(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path, rows, fieldnames=None):
    if fieldnames is None:
        fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def report_label(member):
    label = Path(member).name.rsplit(".", 1)[0]
    return label.split("__", 1)[1] if "__" in label else label


def report_family(label):
    upper = label.upper()
    if "ANTLERLESS" in upper:
        return "ANTLERLESS"
    if "BEAR" in upper:
        return "BEAR"
    if "COUGAR" in upper:
        return "COUGAR"
    if "G.S." in upper or "GS " in upper:
        return "GENERAL_SEASON_DEER"
    if "D.H." in upper:
        return "DEDICATED_HUNTER_DEER"
    if "LIFETIME" in upper:
        return "LIFETIME_GENERAL_DEER"
    if "SPORTSMAN" in upper:
        return "SPORTSMAN"
    if "TURKEY" in upper:
        return "TURKEY"
    if "O.I.L." in upper or "OIL" in upper:
        return "ONCE_IN_A_LIFETIME"
    if "L.E." in upper or "LE " in upper:
        return "LIMITED_ENTRY"
    return "REVIEW"


def infer_identity(code, title, label):
    title = re.sub(r"\s+Page\s+\d+\s*$", "", norm(title), flags=re.I).strip()
    parts = [part.strip() for part in re.split(r"\s+-\s+", title) if part.strip()]
    descriptor = unit = weapon = ""
    if len(parts) >= 3:
        descriptor = parts[0]
        unit = " - ".join(parts[1:-1])
        weapon = parts[-1]
    elif len(parts) == 2:
        descriptor = report_family(label).replace("_", " ").title()
        unit = parts[0]
        weapon = parts[1]
    elif len(parts) == 1:
        descriptor = report_family(label).replace("_", " ").title()
        unit = parts[0]
    return {
        "hunt_title_raw": title,
        "hunt_descriptor": descriptor,
        "species_inferred_from_prefix": PREFIX_SPECIES.get(prefix_of(code), ""),
        "unit_name_inferred": unit,
        "weapon_or_last_segment_inferred": weapon,
    }


def parse_totals(text):
    text = norm(text)
    indexes = [match.start() for match in re.finditer(r"\bTotals\b", text)]
    if len(indexes) < 2:
        return {"status": "TOTALS_NOT_FOUND"}
    first, second = indexes[-2], indexes[-1]

    def parse_segment(segment):
        segment = segment.replace("N / A", "N/A").replace("N /A", "N/A").replace("N/ A", "N/A")
        ratio = ""
        before_ratio = segment
        ratios = list(re.finditer(r"\b\d+\s+in\s+[\d.]+\b", segment))
        if ratios:
            match = ratios[-1]
            ratio = norm(match.group(0))
            before_ratio = segment[: match.start()]
        else:
            match = re.search(r"\bN/A\b", segment)
            if match:
                ratio = "N/A"
                before_ratio = segment[: match.start()]
        nums = [int(value) for value in re.findall(r"\b\d+\b", before_ratio)]
        if len(nums) >= 4:
            return {
                "status": "OK",
                "applicants": nums[0],
                "bonus_permits": nums[1],
                "regular_permits": nums[2],
                "total_permits": nums[3],
                "success_ratio": ratio,
            }
        if len(nums) == 3:
            return {
                "status": "INFERRED_TOTAL_FROM_BONUS_REGULAR",
                "applicants": nums[0],
                "bonus_permits": nums[1],
                "regular_permits": nums[2],
                "total_permits": nums[1] + nums[2],
                "success_ratio": ratio,
            }
        return {"status": "PARSE_FAILED"}

    resident = parse_segment(text[first + 6 : second].strip())
    nonresident = parse_segment(text[second + 6 :].strip())
    return {
        "status": "OK" if resident.get("status") == "OK" and nonresident.get("status") == "OK" else "REVIEW_TOTALS_PARSE",
        "resident_applicants": resident.get("applicants", ""),
        "resident_bonus_permits": resident.get("bonus_permits", ""),
        "resident_regular_permits": resident.get("regular_permits", ""),
        "resident_total_permits": resident.get("total_permits", ""),
        "resident_success_ratio": resident.get("success_ratio", ""),
        "nonresident_applicants": nonresident.get("applicants", ""),
        "nonresident_bonus_permits": nonresident.get("bonus_permits", ""),
        "nonresident_regular_permits": nonresident.get("regular_permits", ""),
        "nonresident_total_permits": nonresident.get("total_permits", ""),
        "nonresident_success_ratio": nonresident.get("success_ratio", ""),
        "resident_parse_status": resident.get("status", ""),
        "nonresident_parse_status": nonresident.get("status", ""),
    }


def source_model_label(member):
    match = re.search(r"PERMITS=(\d{4})_MODEL", Path(member).name, re.I)
    return match.group(1) if match else ""


def build_comparison_maps(repo):
    db_path = repo / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
    db = defaultdict(list)
    db_prefixes = set()
    with db_path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            code = norm(row.get("hunt_code", "")).upper()
            if code:
                db[code].append(row)
                db_prefixes.add(prefix_of(code))
    audits = repo / "processed_data" / "audits"
    lifecycle = {row["hunt_code"]: row for row in read_csv(audits / "hunt_code_interpreted_lifecycle_summary_comprehensive_2020_2026.csv")}
    reappear = {row["hunt_code"] for row in read_csv(audits / "hunt_code_historical_reappearance_gaps_comprehensive_2020_2026.csv")}
    terminal = {row["hunt_code"] for row in read_csv(audits / "hunt_code_terminal_dropoffs_comprehensive_2020_2026.csv")}
    return db, db_prefixes, lifecycle, reappear, terminal


def make_ledger_row(year, model_year, code, title, member, page, label, family, totals, db, lifecycle, reappear, terminal, normalization):
    db_rows = db.get(code, [])
    db_first = db_rows[0] if db_rows else {}
    db_name = norm(db_first.get("hunt_name", ""))
    similarity = round(difflib.SequenceMatcher(None, norm_name(title), norm_name(db_name)).ratio(), 3) if db_name else ""
    if db_rows:
        db_status = "EXACT_CODE_IN_DATABASE"
        name_status = "MATCH_LIKELY" if isinstance(similarity, float) and similarity >= 0.72 else "REVIEW_NAME_DIFFERENCE"
    else:
        db_status = "NOT_IN_CURRENT_DATABASE"
        name_status = "NO_CURRENT_CODE_MATCH"
    life = lifecycle.get(code, {})
    lifecycle_class = (
        "HISTORICAL_REAPPEARANCE_GAP_CODE"
        if code in reappear
        else "TERMINAL_DROPOFF_CANDIDATE"
        if code in terminal
        else "ACTIVE_IN_2026"
        if life.get("active_in_2026") == "YES"
        else "REVIEW_LIFECYCLE"
    )
    identity = infer_identity(code, title, label)
    try:
        combined = int(totals.get("resident_total_permits", "")) + int(totals.get("nonresident_total_permits", ""))
    except Exception:
        combined = totals.get("combined_total_permits", "")
    return {
        "draw_results_year": year,
        "permit_draw_year": year,
        "report_year": year,
        "model_year": model_year,
        "source_model_year_label": source_model_label(member),
        "hunt_code": code,
        "hunt_code_normalization_note": normalization,
        "prefix": prefix_of(code),
        "source_report_label": label,
        "source_report_family": family,
        "source_file": member,
        "source_pdf_page_index": page,
        "source_report_page_printed": page,
        **identity,
        "resident_applicants": totals.get("resident_applicants", ""),
        "resident_bonus_permits": totals.get("resident_bonus_permits", ""),
        "resident_regular_permits": totals.get("resident_regular_permits", ""),
        "resident_total_permits": totals.get("resident_total_permits", ""),
        "resident_success_ratio": totals.get("resident_success_ratio", ""),
        "nonresident_applicants": totals.get("nonresident_applicants", ""),
        "nonresident_bonus_permits": totals.get("nonresident_bonus_permits", ""),
        "nonresident_regular_permits": totals.get("nonresident_regular_permits", ""),
        "nonresident_total_permits": totals.get("nonresident_total_permits", ""),
        "nonresident_success_ratio": totals.get("nonresident_success_ratio", ""),
        "combined_total_permits": combined,
        "totals_parse_status": totals.get("status", ""),
        "resident_parse_status": totals.get("resident_parse_status", ""),
        "nonresident_parse_status": totals.get("nonresident_parse_status", ""),
        "current_database_exact_code_rows": len(db_rows),
        "current_database_match_status": db_status,
        "current_database_hunt_name": db_name,
        "current_database_species": norm(db_first.get("species", "")),
        "current_database_weapon": norm(db_first.get("weapon", "")),
        "current_database_boundary_id": norm(db_first.get("boundary_id", "")),
        "current_database_permit_2026_total": norm(db_first.get("permit_allotment_2026_total", "")),
        "name_similarity_to_current_database": similarity,
        "name_match_status": name_status,
        "lifecycle_class": lifecycle_class,
        "lifecycle_observed_years": life.get("observed_years", ""),
        "lifecycle_gap_years_likely_continued": life.get("gap_years_likely_continued", ""),
        "lifecycle_terminal_absent_years_through_2026": life.get("terminal_absent_years_through_2026", ""),
        "identity_review_status": "REVIEW_TOTALS_PARSE"
        if totals.get("status") not in ("OK", "OK_SPORTSMAN_TABLE")
        else "REVIEW_NAME_DIFFERENCE"
        if name_status == "REVIEW_NAME_DIFFERENCE"
        else "OK",
    }


def build_identity_outputs(repo, zip_path, year):
    audits = repo / "processed_data" / "audits"
    docs = repo / "docs"
    model_year = year + 1
    db, db_prefixes, lifecycle, reappear, terminal = build_comparison_maps(repo)
    ledger = []
    errors = []
    model_label_counts = Counter()
    hunt_line_re = re.compile(r"\bHunt:\s*([A-Z]{2,3}\d{3,4})(?:\s+(.*?))?(?:\s+Page\s+\d+\s*)?$", re.I)
    code_re = re.compile(r"\b[A-Z]{2,3}\d{3,4}\b")
    with zipfile.ZipFile(zip_path) as archive:
        members = sorted([
            m for m in archive.namelist()
            if m.lower().endswith(".pdf")
            and (m.startswith(f"{year}/") or Path(m).name.startswith(f"{year}_"))
        ])
        for member in members:
            label = report_label(member)
            family = report_family(label)
            model_label_counts[source_model_label(member) or "MISSING"] += 1
            if family == "SPORTSMAN":
                continue
            try:
                reader = PdfReader(BytesIO(archive.read(member)))
            except Exception as exc:
                errors.append({"source_file": member, "source_pdf_page_index": "", "error": f"file_read: {exc}"})
                continue
            for page_number, page in enumerate(reader.pages, start=1):
                try:
                    text = page.extract_text() or ""
                except Exception as exc:
                    errors.append({"source_file": member, "source_pdf_page_index": page_number, "error": f"page_extract: {exc}"})
                    continue
                for line in [norm(x) for x in text.splitlines() if norm(x)]:
                    if "Hunt:" not in line:
                        continue
                    match = hunt_line_re.search(line)
                    if match:
                        code, title = match.group(1).upper(), match.group(2) or ""
                    else:
                        codes = code_re.findall(line.upper())
                        if not codes:
                            continue
                        code = codes[0]
                        title = line.split(code, 1)[1] if code in line else ""
                    if prefix_of(code) not in db_prefixes:
                        continue
                    ledger.append(make_ledger_row(year, model_year, code, title, member, page_number, label, family, parse_totals(text), db, lifecycle, reappear, terminal, "AS_EXTRACTED"))
    normalizations = []
    if year == 2022:
        member = f"{year}/{year}_PERMITS={model_year}_MODEL__SPORTSMAN DRAW RESULTS.pdf"
        for row in SPORTSMAN_2022_ROWS:
            code, title, succ_res, succ_nr, unsucc_res, unsucc_nr, total_apps, res_quota, nr_quota, total_quota, res_ratio, nr_ratio = row
            raw_artifact = f"A{code}"
            totals = {
                "status": "OK_SPORTSMAN_TABLE",
                "resident_applicants": total_apps,
                "resident_total_permits": res_quota,
                "resident_success_ratio": res_ratio,
                "nonresident_total_permits": nr_quota,
                "nonresident_success_ratio": nr_ratio,
                "combined_total_permits": total_quota,
                "resident_parse_status": "OK_SPORTSMAN_TABLE",
                "nonresident_parse_status": "OK_SPORTSMAN_TABLE",
            }
            ledger.append(make_ledger_row(year, model_year, code, title, member, 1, report_label(member), "SPORTSMAN", totals, db, lifecycle, reappear, terminal, f"NORMALIZED_FROM_TEXT_ARTIFACT_{raw_artifact}"))
            normalizations.append({"raw_extracted_code": raw_artifact, "normalized_hunt_code": code, "source_file": member, "source_page": 1, "normalization_note": "PDF text extraction joined N/A to the hunt code; user-provided copied text confirms normalized code."})
    ledger = sorted(ledger, key=lambda r: (r["source_file"], int(r["source_pdf_page_index"]), r["hunt_code"]))
    by_code = defaultdict(list)
    for row in ledger:
        by_code[row["hunt_code"]].append(row)
    crosscheck = []
    issues = []
    for code, rows in sorted(by_code.items()):
        names = sorted({r["hunt_title_raw"] for r in rows if r["hunt_title_raw"]})
        files = sorted({r["source_file"] for r in rows})
        totals = sorted({str(r["combined_total_permits"]) for r in rows if str(r["combined_total_permits"])})
        db_statuses = sorted({r["current_database_match_status"] for r in rows})
        name_statuses = sorted({r["name_match_status"] for r in rows})
        parse_statuses = sorted({r["totals_parse_status"] for r in rows})
        conflicting_names = len({norm_name(n) for n in names}) > 1
        conflicting_totals = len(totals) > 1
        if conflicting_names:
            status = "REVIEW_CONFLICTING_SOURCE_NAMES"
        elif conflicting_totals:
            status = "REVIEW_CONFLICTING_TOTAL_PERMITS"
        elif any(s not in ("OK", "OK_SPORTSMAN_TABLE") for s in parse_statuses):
            status = "REVIEW_TOTALS_PARSE"
        elif "EXACT_CODE_IN_DATABASE" not in db_statuses:
            status = "HISTORICAL_CODE_NOT_IN_CURRENT_DATABASE"
        elif "REVIEW_NAME_DIFFERENCE" in name_statuses:
            status = "REVIEW_CURRENT_DATABASE_NAME_DIFFERENCE"
        else:
            status = "OK"
        out = {
            "draw_results_year": year,
            "permit_draw_year": year,
            "report_year": year,
            "model_year": model_year,
            "hunt_code": code,
            "prefix": prefix_of(code),
            "source_appearance_count": len(rows),
            "source_file_count": len(files),
            "source_files": "|".join(files),
            "source_report_families": "|".join(sorted({r["source_report_family"] for r in rows})),
            "source_pages": "|".join(sorted({str(r["source_pdf_page_index"]) for r in rows})),
            "source_hunt_titles": "|".join(names),
            "combined_total_permits_values": "|".join(totals),
            "current_database_match_statuses": "|".join(db_statuses),
            "name_match_statuses": "|".join(name_statuses),
            "totals_parse_statuses": "|".join(parse_statuses),
            "lifecycle_classes": "|".join(sorted({r["lifecycle_class"] for r in rows})),
            "normalization_notes": "|".join(sorted({r["hunt_code_normalization_note"] for r in rows if r["hunt_code_normalization_note"] != "AS_EXTRACTED"})),
            "duplicate_source_files": "YES" if len(files) > 1 else "NO",
            "conflicting_source_names": "YES" if conflicting_names else "NO",
            "conflicting_total_permits": "YES" if conflicting_totals else "NO",
            "crosscheck_status": status,
        }
        crosscheck.append(out)
        if status != "OK":
            issues.append(out)
    outputs = {
        "ledger": audits / f"hunt_code_year_identity_ledger_{year}.csv",
        "crosscheck": audits / f"hunt_code_year_identity_crosscheck_{year}.csv",
        "issues": audits / f"hunt_code_year_identity_issues_{year}.csv",
        "scan_errors": audits / f"hunt_code_year_identity_scan_errors_{year}.csv",
        "normalization": audits / f"hunt_code_year_identity_sportsman_normalization_{year}.csv",
        "summary": audits / f"hunt_code_year_identity_{year}_summary.json",
        "report": docs / f"hunt_code_year_identity_alignment_{year}.md",
    }
    write_csv(outputs["ledger"], ledger)
    write_csv(outputs["crosscheck"], crosscheck)
    write_csv(outputs["issues"], issues)
    write_csv(outputs["scan_errors"], errors, ["source_file", "source_pdf_page_index", "error"])
    write_csv(outputs["normalization"], normalizations)
    return outputs, ledger, crosscheck, errors, normalizations, model_label_counts


def update_lifecycle(repo, year, model_year, normalizations, ledger):
    audits = repo / "processed_data" / "audits"
    source_hits_path = audits / "hunt_code_source_hits_comprehensive_2020_2026.csv"
    hits = read_csv(source_hits_path)
    existing = {(r["hunt_code"], r["report_year"], r["source_file"], r["source_page"]) for r in hits}
    existing_code_years = {(r["hunt_code"], r["report_year"]) for r in hits}
    added = []
    for row in normalizations:
        hit = {
            "hunt_code": row["normalized_hunt_code"],
            "report_year": str(year),
            "model_year": str(model_year),
            "source_kind": "COMPREHENSIVE_ZIP_PDF_NORMALIZED_SPORTSMAN",
            "source_file": row["source_file"],
            "source_page": str(row["source_page"]),
        }
        key = (hit["hunt_code"], hit["report_year"], hit["source_file"], hit["source_page"])
        if key not in existing:
            hits.append(hit)
            added.append(hit)
            existing.add(key)
            existing_code_years.add((hit["hunt_code"], hit["report_year"]))
    for row in ledger:
        code = row["hunt_code"]
        report_year = str(year)
        if (code, report_year) in existing_code_years:
            continue
        hit = {
            "hunt_code": code,
            "report_year": report_year,
            "model_year": str(model_year),
            "source_kind": "IDENTITY_LEDGER_BACKFILL",
            "source_file": row["source_file"],
            "source_page": str(row["source_pdf_page_index"]),
        }
        key = (hit["hunt_code"], hit["report_year"], hit["source_file"], hit["source_page"])
        if key not in existing:
            hits.append(hit)
            added.append(hit)
            existing.add(key)
            existing_code_years.add((hit["hunt_code"], hit["report_year"]))
    hits = sorted(hits, key=lambda r: (int(r["report_year"]), r["hunt_code"], r["source_file"], int(r["source_page"]) if str(r["source_page"]).isdigit() else 99999))
    write_csv(source_hits_path, hits, ["hunt_code", "report_year", "model_year", "source_kind", "source_file", "source_page"])
    return added


def recompute_lifecycle(repo):
    audits = repo / "processed_data" / "audits"
    db_path = repo / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
    db_prefixes = set()
    with db_path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            code = norm(row.get("hunt_code", "")).upper()
            if code:
                db_prefixes.add(prefix_of(code))
    years = list(range(2020, 2027))
    hits = read_csv(audits / "hunt_code_source_hits_comprehensive_2020_2026.csv")
    by_code_year = defaultdict(lambda: {"files": set(), "pages": set(), "source_kinds": set(), "model_years": set()})
    by_year = defaultdict(set)
    for row in hits:
        code = row["hunt_code"]
        if prefix_of(code) not in db_prefixes:
            continue
        report_year = int(row["report_year"])
        rec = by_code_year[(code, report_year)]
        rec["files"].add(row["source_file"])
        rec["pages"].add(str(row["source_page"]))
        rec["source_kinds"].add(row["source_kind"])
        rec["model_years"].add(str(row["model_year"]))
        by_year[report_year].add(code)
    all_codes = sorted({code for code, _year in by_code_year})
    lifecycle = []
    presence = []
    for code in all_codes:
        present = [year for year in years if (code, year) in by_code_year]
        first = min(present)
        last = max(present)
        gaps = [str(year) for year in range(first, last + 1) if (code, year) not in by_code_year]
        present_2026 = (code, 2026) in by_code_year
        if present_2026 and first == 2026:
            status = "NEW_IN_2026"
        elif present_2026 and gaps:
            status = "ACTIVE_2026_WITH_HISTORICAL_GAPS"
        elif present_2026:
            status = "ACTIVE_2026"
        else:
            status = "DROPPED_BEFORE_2026"
        source_files = {}
        source_pages = {}
        source_kinds = {}
        model_years = {}
        for year in present:
            rec = by_code_year[(code, year)]
            source_files[str(year)] = sorted(rec["files"])
            source_pages[str(year)] = sorted(rec["pages"], key=lambda value: int(value) if value.isdigit() else 99999)
            source_kinds[str(year)] = sorted(rec["source_kinds"])
            model_years[str(year)] = sorted(rec["model_years"])
        lifecycle.append({
            "hunt_code": code,
            "prefix": prefix_of(code),
            "first_seen_report_year": first,
            "last_seen_report_year": last,
            "years_seen": "|".join(map(str, present)),
            "observed_year_count": len(present),
            "missing_years_between_first_last": "|".join(gaps),
            "drop_off_after_report_year": "" if present_2026 else last,
            "absent_in_2026": "NO" if present_2026 else "YES",
            "status": status,
            "model_years_by_report_year": json.dumps(model_years, ensure_ascii=False),
            "source_kinds_by_year": json.dumps(source_kinds, ensure_ascii=False),
            "source_files_by_year": json.dumps(source_files, ensure_ascii=False),
            "source_pages_by_year": json.dumps(source_pages, ensure_ascii=False),
        })
        prow = {"hunt_code": code, "prefix": prefix_of(code)}
        for year in years:
            prow[f"present_report_year_{year}"] = "YES" if (code, year) in by_code_year else "NO"
            prow[f"source_count_report_year_{year}"] = len(by_code_year[(code, year)]["files"]) if (code, year) in by_code_year else 0
        presence.append(prow)
    transitions = []
    dropoffs = []
    additions = []
    for previous, current in zip(years[:-1], years[1:]):
        previous_codes = by_year[previous]
        current_codes = by_year[current]
        retained = sorted(previous_codes & current_codes)
        dropped = sorted(previous_codes - current_codes)
        added = sorted(current_codes - previous_codes)
        transitions.append({
            "from_report_year": previous,
            "to_report_year": current,
            "from_model_year": previous + 1,
            "to_model_year": current + 1,
            "from_year_code_count": len(previous_codes),
            "to_year_code_count": len(current_codes),
            "retained_count": len(retained),
            "dropped_count": len(dropped),
            "added_count": len(added),
            "retained_codes": "|".join(retained),
            "dropped_codes": "|".join(dropped),
            "added_codes": "|".join(added),
        })
        for code in dropped:
            reappears = any(code in by_year[year] for year in years if year > current)
            dropoffs.append({
                "hunt_code": code,
                "prefix": prefix_of(code),
                "present_report_year": previous,
                "first_missing_report_year": current,
                "present_model_year": previous + 1,
                "first_missing_model_year": current + 1,
                "reappears_later": "YES" if reappears else "NO",
                "permanent_through_2026": "NO" if reappears else "YES",
                "source_files_present_year": "|".join(sorted(by_code_year[(code, previous)]["files"])),
                "source_pages_present_year": "|".join(sorted(by_code_year[(code, previous)]["pages"], key=lambda value: int(value) if value.isdigit() else 99999)),
            })
        for code in added:
            additions.append({
                "hunt_code": code,
                "prefix": prefix_of(code),
                "first_present_report_year_in_transition": current,
                "previous_report_year_absent": previous,
                "first_present_model_year_in_transition": current + 1,
                "previous_model_year_absent": previous + 1,
                "seen_before_previous_year": "YES" if any(code in by_year[year] for year in years if year < previous) else "NO",
                "source_files_first_present_year": "|".join(sorted(by_code_year[(code, current)]["files"])),
                "source_pages_first_present_year": "|".join(sorted(by_code_year[(code, current)]["pages"], key=lambda value: int(value) if value.isdigit() else 99999)),
            })
    interpreted = []
    reappearance_gaps = []
    terminal_dropoffs = []
    interpreted_summary = []
    for row in presence:
        code = row["hunt_code"]
        observed = [year for year in years if row.get(f"present_report_year_{year}") == "YES"]
        first = min(observed)
        last = max(observed)
        gaps = []
        terminal_years = []
        for year in years:
            is_observed = year in observed
            if is_observed:
                status = "OBSERVED_IN_SOURCE"
                continuity = "CONFIRMED_PRESENT"
                notes = "Source PDF contains the hunt code in this report year."
            elif year < first:
                status = "NOT_YET_OBSERVED"
                continuity = "BEFORE_FIRST_OBSERVED_YEAR"
                notes = "No source evidence before first observed year in this audit window."
            elif first < year < last:
                status = "LIKELY_CONTINUED_NOT_OBSERVED"
                continuity = "TEMPORARY_SOURCE_GAP_BEFORE_REAPPEARANCE"
                notes = "The code is absent this year but reappears later, so do not treat this as termination."
                gaps.append(year)
            else:
                status = "TERMINAL_ABSENT_AFTER_LAST_OBSERVED"
                continuity = "NO_LATER_REAPPEARANCE_IN_AUDIT_WINDOW"
                notes = "The code has not reappeared in later scanned source years through 2026."
                terminal_years.append(year)
            interpreted.append({
                "hunt_code": code,
                "prefix": prefix_of(code),
                "report_year": year,
                "model_year": year + 1,
                "raw_observed_in_source": "YES" if is_observed else "NO",
                "interpreted_status": status,
                "continuity_status": continuity,
                "first_seen_report_year": first,
                "last_seen_report_year": last,
                "notes": notes,
            })
        if gaps:
            reappearance_gaps.append({
                "hunt_code": code,
                "prefix": prefix_of(code),
                "first_seen_report_year": first,
                "last_seen_report_year": last,
                "observed_years": "|".join(map(str, observed)),
                "gap_years_likely_continued": "|".join(map(str, gaps)),
                "gap_count": len(gaps),
                "interpretation": "HISTORICAL_REAPPEARANCE_GAP_LIKELY_CONTINUED",
                "notes": "Absent year(s) occur between observed years; treat as not observed in source, not terminated.",
            })
        if last < 2026:
            terminal_dropoffs.append({
                "hunt_code": code,
                "prefix": prefix_of(code),
                "first_seen_report_year": first,
                "last_seen_report_year": last,
                "terminal_dropoff_after_report_year": last,
                "terminal_absent_years_through_2026": "|".join(map(str, terminal_years)),
                "observed_years": "|".join(map(str, observed)),
                "had_prior_reappearance_gap": "YES" if gaps else "NO",
                "interpretation": "TERMINAL_ABSENT_NO_REAPPEARANCE_THROUGH_2026",
                "notes": "Last observed year has no later reappearance in the scanned years; this is the true terminal drop-off candidate.",
            })
        interpretation = "ACTIVE_2026_WITH_REAPPEARANCE_GAPS_LIKELY_CONTINUED" if gaps and last == 2026 else "ACTIVE_2026" if last == 2026 else "TERMINAL_DROPOFF_AFTER_LAST_OBSERVED_WITH_PRIOR_REAPPEARANCE_GAPS" if gaps else "TERMINAL_DROPOFF_AFTER_LAST_OBSERVED"
        interpreted_summary.append({
            "hunt_code": code,
            "prefix": prefix_of(code),
            "first_seen_report_year": first,
            "last_seen_report_year": last,
            "observed_years": "|".join(map(str, observed)),
            "gap_years_likely_continued": "|".join(map(str, gaps)),
            "terminal_absent_years_through_2026": "|".join(map(str, terminal_years)),
            "gap_count": len(gaps),
            "terminal_absent_year_count": len(terminal_years),
            "active_in_2026": "YES" if last == 2026 else "NO",
            "lifecycle_interpretation": interpretation,
        })
    prefix_summary = []
    for code_prefix in sorted({row["prefix"] for row in lifecycle}):
        rows = [row for row in lifecycle if row["prefix"] == code_prefix]
        prefix_summary.append({
            "prefix": code_prefix,
            "total_codes_observed": len(rows),
            "active_2026_codes": sum(1 for row in rows if row["absent_in_2026"] == "NO"),
            "dropped_before_2026_codes": sum(1 for row in rows if row["absent_in_2026"] == "YES"),
            "new_in_2026_codes": sum(1 for row in rows if row["status"] == "NEW_IN_2026"),
            "earliest_first_seen_report_year": min(row["first_seen_report_year"] for row in rows),
            "latest_last_seen_report_year": max(row["last_seen_report_year"] for row in rows),
        })
    write_csv(audits / "hunt_code_lifecycle_comprehensive_2020_2026.csv", lifecycle)
    write_csv(audits / "hunt_code_presence_matrix_comprehensive_2020_2026.csv", presence)
    write_csv(audits / "hunt_code_year_to_year_transitions_comprehensive_2020_2026.csv", transitions)
    write_csv(audits / "hunt_code_dropoffs_comprehensive_2020_2026.csv", dropoffs)
    write_csv(audits / "hunt_code_dropped_2025_to_2026_comprehensive.csv", [row for row in dropoffs if row["present_report_year"] == 2025 and row["first_missing_report_year"] == 2026])
    write_csv(audits / "hunt_code_additions_comprehensive_2020_2026.csv", additions)
    write_csv(audits / "hunt_code_prefix_summary_comprehensive_2020_2026.csv", prefix_summary)
    write_csv(audits / "hunt_code_interpreted_presence_comprehensive_2020_2026.csv", interpreted)
    write_csv(audits / "hunt_code_historical_reappearance_gaps_comprehensive_2020_2026.csv", reappearance_gaps)
    write_csv(audits / "hunt_code_terminal_dropoffs_comprehensive_2020_2026.csv", terminal_dropoffs)
    write_csv(audits / "hunt_code_interpreted_lifecycle_summary_comprehensive_2020_2026.csv", interpreted_summary)
    lifecycle_summary = {
        "scope": "Year-to-year hunt code lifecycle using COMPREHENSIVE 2020-2025.zip plus generated 2026 UtahDraws display PDFs. Strict prefix version with reviewed identity-ledger backfills.",
        "year_semantics": "For BIBLE HUNT CODES packages, report_year means draw_results_year and permit_draw_year. Model year is the predictive modeling year and equals draw_results_year + 1 unless reviewed source evidence proves otherwise.",
        "report_years": years,
        "unique_hunt_codes_observed": len(all_codes),
        "codes_by_report_year": {str(year): len(by_year[year]) for year in years},
        "active_2026_codes": len(by_year[2026]),
        "codes_observed_2020_2025_absent_in_2026": sum(1 for row in lifecycle if row["absent_in_2026"] == "YES"),
        "new_in_2026_codes": sum(1 for row in lifecycle if row["status"] == "NEW_IN_2026"),
        "dropped_2025_to_2026_count": sum(1 for row in dropoffs if row["present_report_year"] == 2025 and row["first_missing_report_year"] == 2026),
        "notes": [
            "2022 Sportsman source rows were normalized from A-prefixed extraction artifacts to real Sportsman hunt codes.",
            "Year-specific identity-ledger passes may add reviewed source-hit backfills when a provided truth-source ZIP proves code/year presence missed by the comprehensive source-hit scan.",
        ],
    }
    (audits / "hunt_code_lifecycle_comprehensive_2020_2026_summary.json").write_text(json.dumps(lifecycle_summary, indent=2), encoding="utf-8")
    interpreted_json = {
        "scope": "Interpreted lifecycle layer for strict-prefix comprehensive 2020-2026 hunt-code audit with reviewed identity-ledger backfills.",
        "purpose": "Historical reappearances are mapped as likely continued through non-observed years instead of terminated.",
        "year_semantics": lifecycle_summary["year_semantics"],
        "unique_hunt_codes_observed": len(interpreted_summary),
        "likely_continued_not_observed_cells": Counter(row["interpreted_status"] for row in interpreted).get("LIKELY_CONTINUED_NOT_OBSERVED", 0),
        "codes_with_historical_reappearance_gaps": len(reappearance_gaps),
        "terminal_dropoff_candidate_codes": len(terminal_dropoffs),
        "active_2026_codes": sum(1 for row in interpreted_summary if row["active_in_2026"] == "YES"),
    }
    (audits / "hunt_code_interpreted_lifecycle_comprehensive_2020_2026_summary.json").write_text(json.dumps(interpreted_json, indent=2), encoding="utf-8")
    return {"codes_by_report_year": lifecycle_summary["codes_by_report_year"], "unique_hunt_codes_observed": len(all_codes)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=r"C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER")
    parser.add_argument("--zip", required=True)
    parser.add_argument("--year", type=int, required=True)
    args = parser.parse_args()
    repo = Path(args.repo)
    outputs, ledger, crosscheck, errors, normalizations, model_labels = build_identity_outputs(repo, Path(args.zip), args.year)
    added_hits = update_lifecycle(repo, args.year, args.year + 1, normalizations, ledger)
    lifecycle_result = recompute_lifecycle(repo)
    presence_rows = read_csv(repo / "processed_data" / "audits" / "hunt_code_presence_matrix_comprehensive_2020_2026.csv")
    source_hits = read_csv(repo / "processed_data" / "audits" / "hunt_code_source_hits_comprehensive_2020_2026.csv")
    year_backfills = [
        row for row in source_hits
        if row.get("report_year") == str(args.year)
        and row.get("source_kind") == "IDENTITY_LEDGER_BACKFILL"
    ]
    expected = {r["hunt_code"] for r in presence_rows if r.get(f"present_report_year_{args.year}") == "YES"} | {r["normalized_hunt_code"] for r in normalizations}
    actual = {r["hunt_code"] for r in ledger}
    notes = [
        "Year semantics: draw_results_year = permit_draw_year for BIBLE HUNT CODES source packages.",
        "Model year is the predictive modeling year and equals draw_results_year + 1.",
        "This audit does not modify DATABASE.csv.",
    ]
    if normalizations:
        notes.append("Sportsman rows were normalized from PDF text-extraction artifacts when source evidence confirmed the real hunt code.")
    else:
        notes.append("No Sportsman code normalization rows were required for this year.")
    if added_hits:
        notes.append("Lifecycle source-hit backfills were added only for real identity-ledger code/year rows not already present in the comprehensive lifecycle source-hit table.")
    summary = {
        "scope": f"{args.year} hunt-code/year identity alignment from provided truth-source ZIP package.",
        "source_zip": str(Path(args.zip)),
        "draw_results_year": args.year,
        "permit_draw_year": args.year,
        "report_year": args.year,
        "model_year": args.year + 1,
        "ledger_rows": len(ledger),
        "unique_hunt_codes": len(crosscheck),
        "sportsman_rows_added": len(normalizations),
        "sportsman_code_normalizations": len(normalizations),
        "lifecycle_source_hits_added": len(added_hits),
        "lifecycle_source_hit_backfills_present_for_year": len(year_backfills),
        "lifecycle_source_hit_backfill_codes_for_year": sorted({row["hunt_code"] for row in year_backfills}),
        "scan_error_count": len(errors),
        "expected_code_count_after_correction": len(expected),
        "missing_from_identity_ledger": sorted(expected - actual),
        "extra_in_identity_ledger": sorted(actual - expected),
        "source_model_year_label_counts": dict(model_labels),
        "corrected_lifecycle_codes_by_report_year": lifecycle_result["codes_by_report_year"],
        "corrected_lifecycle_unique_hunt_codes": lifecycle_result["unique_hunt_codes_observed"],
        "crosscheck_status_counts": dict(Counter(r["crosscheck_status"] for r in crosscheck)),
        "totals_parse_status_counts": dict(Counter(r["totals_parse_status"] for r in ledger)),
        "current_database_match_status_counts": dict(Counter(r["current_database_match_status"] for r in ledger)),
        "outputs": {key: str(path) for key, path in outputs.items()},
        "notes": notes,
    }
    outputs["summary"].write_text(json.dumps(summary, indent=2), encoding="utf-8")
    report_lines = [
        f"# {args.year} Hunt-Code Year Identity Alignment Audit",
        "",
        "## Year Semantics",
        f"- `draw_results_year = {args.year}`.",
        f"- `permit_draw_year = {args.year}`.",
        f"- `model_year = {args.year + 1}`.",
        "- Source filename model labels are preserved as source evidence only.",
        "",
        "## Key Counts",
        f"- Ledger rows: `{len(ledger)}`",
        f"- Unique hunt codes: `{len(crosscheck)}`",
        f"- Sportsman rows added: `{len(normalizations)}`",
        f"- Lifecycle source-hit rows added: `{len(added_hits)}`",
        f"- Lifecycle source-hit backfills present for year: `{len(year_backfills)}`",
        f"- Scan errors: `{len(errors)}`",
        f"- Missing from identity ledger after correction: `{len(expected - actual)}`",
        f"- Extra in identity ledger after correction: `{len(actual - expected)}`",
        "",
        "## Sportsman Normalization",
        "No Sportsman normalization rows were required for this year." if not normalizations else "Sportsman source rows were normalized from PDF text-extraction artifacts where reviewed source evidence confirmed the real hunt code.",
        "",
        "## Lifecycle Backfills",
        "No lifecycle source-hit backfills are present for this year." if not year_backfills else f"`{len(year_backfills)}` lifecycle source-hit backfill row(s) are present for this year from identity-ledger evidence.",
        "" if not year_backfills else f"- Backfilled codes: `{', '.join(sorted({row['hunt_code'] for row in year_backfills}))}`",
        "",
        "## Outputs",
    ]
    for path in outputs.values():
        report_lines.append(f"- `{path}`")
    outputs["report"].write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
