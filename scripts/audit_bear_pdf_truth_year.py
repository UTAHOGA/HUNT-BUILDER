#!/usr/bin/env python3
"""Fresh, isolated, one-year Bear PDF verification; never writes production truth.

2020-2025 have individually reviewed layouts. This is a source audit, not a prediction
engine or a replacement truth authority. Add another year only after reviewing
its actual PDF layout. Canonicals are read only AFTER the PDF extract is frozen.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COUNTS = ("eligible_applicants", "bonus_permits", "regular_permits", "total_permits")
LANES = ("Resident", "Nonresident")
REVIEWED = {
    year: {"max_point": maximum, "url": f"https://wildlife.utah.gov/pdf/bear/{str(year)[2:]}_drawing_odds.pdf"}
    for year, maximum in ((2020, 19), (2021, 19), (2022, 20), (2023, 21), (2024, 21), (2025, 22))
}


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def write_rows(path, rows):
    if not rows:
        raise ValueError(f"Refusing empty truth output: {path}")
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def number(value):
    text = str(value if value is not None else "").strip()
    if not re.fullmatch(r"(?:\d+|\d{1,3}(?:,\d{3})+)", text):
        raise ValueError(f"Missing/malformed published integer: {value!r}")
    return int(text.replace(",", ""))


def parse_table(table, max_point):
    """Validate all cells, paired rungs, printed totals and rounded ratios.

    The known pdfplumber empty zero-label artifact is permitted only between
    the completed zero rung and the totals. It is NOT another applicant row.
    """
    rows, totals, artifacts = [], [], []
    expected_point = max_point
    saw_artifact = False
    for index, cells in enumerate(table):
        # 2022 has a spurious empty column under the resident '#' heading.
        if len(cells) == 13 and cells[1] in (None, ""):
            cells = cells[:1] + cells[2:]
        # 2023/24 split two resident permit cells into three extraction cells.
        # Exactly one contains the printed number; never add these cells.
        elif len(cells) == 16:
            bonus = [value for value in cells[2:5] if value not in (None, "")]
            regular = [value for value in cells[5:8] if value not in (None, "")]
            if len(bonus) != 1 or len(regular) != 1:
                raise ValueError("Ambiguous split permit cell")
            cells = cells[:2] + bonus + regular + cells[8:]
        if len(cells) != 12:
            raise ValueError(f"Unreviewed table shape: {len(cells)} columns")
        labels = [str(cells[pos] or "").strip() for pos in (0, 6)]
        if labels[0] == "0" and all(value is None for value in cells[1:]):
            if expected_point != -1 or totals or saw_artifact:
                raise ValueError("Unrecognized/inappropriately placed zero-label artifact")
            artifacts.append({"table_row": index, "reason": "EMPTY_ZERO_LABEL_EXTRACTION_ARTIFACT"})
            saw_artifact = True
            continue
        is_total = labels == ["Totals", "Totals"]
        if is_total:
            if expected_point != -1 or totals:
                raise ValueError("Missing rungs or duplicate totals")
        elif totals or labels != [str(expected_point)] * 2 or expected_point < 0:
            raise ValueError(f"Missing/duplicate/mismatched rung: {labels}, expected {expected_point}")
        for residency, offset in zip(LANES, (0, 6)):
            row = {"residency": residency, "points": "" if is_total else expected_point}
            row.update({field: number(cells[offset + i + 1]) for i, field in enumerate(COUNTS)})
            applicants, bonus, regular, awarded = (row[field] for field in COUNTS)
            if bonus + regular != awarded or awarded > applicants:
                raise ValueError(f"Published count inconsistency: {row}")
            ratio = str(cells[offset + 5] or "").strip()
            if awarded == 0:
                if ratio != "N/A":
                    raise ValueError(f"Unexpected zero-award ratio: {ratio}")
            else:
                match = re.fullmatch(r"1 in ([\d,]+\.\d)", ratio)
                if not match or abs(float(match[1].replace(",", "")) - applicants / awarded) > 0.0500001:
                    raise ValueError(f"Published success ratio does not reconcile: {row}, {ratio}")
            row["published_success_ratio"] = ratio
            # This is a retrospective fraction, NOT an individual/future probability.
            row["observed_success_fraction"] = awarded / applicants if applicants else ""
            (totals if is_total else rows).append(row)
        if not is_total:
            expected_point -= 1
    if len(totals) != 2 or expected_point != -1:
        raise ValueError("Incomplete point table")
    for total in totals:
        for field in COUNTS:
            observed = sum(row[field] for row in rows if row["residency"] == total["residency"])
            if observed != total[field]:
                raise ValueError(f"Printed total mismatch: {total['residency']} {field}: {observed} != {total[field]}")
    return rows, totals, artifacts


def extract(source, retained, year):
    import pdfplumber

    points, totals, pages, aggregates = [], [], [], []
    codes = set()
    source_hash = digest(source)
    with pdfplumber.open(source) as pdf:
        for page_number, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            if f"{year} Draw 1, Black Bear" not in text:
                raise ValueError(f"Unrecognized year/report header on page {page_number}")
            tables = page.extract_tables()
            page_record = {"pdf_page": page_number, "text": text, "raw_tables": tables}
            if "Bonus Point Purchase Results" in text:
                if "Hunt:" in text:
                    raise ValueError("Purchase page unexpectedly has hunt identity")
                page_record["classification"] = "STATEWIDE_POINT_PURCHASE_CONTEXT_NOT_HUNT_APPLICANTS"
                pages.append(page_record)
                continue
            if len(tables) != 1:
                raise ValueError(f"Expected one table on PDF page {page_number}")
            if "All Applicants" in text and "Hunt:" not in text:
                program = "RESTRICTED_BEAR_PURSUIT" if "Pursuit" in text else "LIMITED_ENTRY_BEAR_HUNT"
                aggregate_points, aggregate_totals, _ = parse_table(tables[0], REVIEWED[year]["max_point"])
                aggregates.extend({**row, "draw_pool": program, "pdf_page": page_number} for row in aggregate_points)
                pages.append({**page_record, "classification": "STATEWIDE_DRAW_AGGREGATE_NOT_ADDITIONAL_HUNT",
                              "draw_pool": program, "printed_totals": aggregate_totals})
                continue
            hunt = re.search(r"Hunt:\s*(BR\d{4})\s+(.+?)\nResident Applicants", text, re.S)
            printed_page = re.search(r"Draw Results Page (\d+)", text)
            if not hunt or not printed_page or "Non-Resident Applicants" not in text:
                raise ValueError(f"Missing hunt/page/residency headers on page {page_number}")
            code, name = hunt[1], " ".join(hunt[2].split())
            if code in codes:
                raise ValueError(f"Duplicate hunt page: {code}")
            codes.add(code)
            normalized_name = re.sub(r"\s", "", name).lower()
            if normalized_name.endswith("-pursuit"):
                program, classification = "RESTRICTED_BEAR_PURSUIT", "BEAR_PURSUIT_BONUS_DRAW"
            elif normalized_name.endswith("-anylegalweapon"):
                program, classification = "LIMITED_ENTRY_BEAR_HUNT", "TRUE_BEAR_BONUS_DRAW"
            else:
                raise ValueError(f"Unreviewed program label: {name}")
            try:
                point_rows, total_rows, artifacts = parse_table(tables[0], REVIEWED[year]["max_point"])
            except ValueError as exc:
                raise ValueError(f"{code} PDF page {page_number}: {exc}") from exc
            common = {
                "actual_draw_year": year, "hunt_code": code, "hunt_name": name,
                "species": "Black Bear", "draw_pool": program,
                "bear_source_classification": classification,
                "source_file": retained.relative_to(ROOT).as_posix(),
                "retained_snapshot": source.relative_to(ROOT).as_posix(),
                "source_url": REVIEWED[year]["url"], "source_sha256": source_hash,
                "pdf_page": page_number, "printed_report_page": int(printed_page[1]),
                "truth_status": "ISOLATED_PDF_REEXTRACTION_NOT_PROMOTED",
            }
            points.extend({**common, "record_type": "point_level_draw_result", **row} for row in point_rows)
            totals.extend({**common, "record_type": "hunt_total_draw_result", **row} for row in total_rows)
            pages.append({**page_record, "hunt_code": code, "classification": classification,
                          "empty_label_artifacts": artifacts, "printed_totals_checked": True})
    if not points:
        raise ValueError("No official point rows extracted")
    for aggregate in aggregates:
        selection = [row for row in points if row["draw_pool"] == aggregate["draw_pool"]
                     and row["residency"] == aggregate["residency"] and row["points"] == aggregate["points"]]
        for field in COUNTS:
            if sum(row[field] for row in selection) != aggregate[field]:
                raise ValueError(f"Hunt sums do not reconcile to aggregate page {aggregate['pdf_page']}: {aggregate}")
    return points, totals, pages


def compare_canonical(points, totals, canonical, year):
    """Compare numeric columns AND code/program/name/page; never boundary_id."""
    expected = defaultdict(dict)
    for row in points + totals:
        key = row["hunt_code"], str(row["points"]), row["record_type"]
        if row["residency"] in expected[key]:
            raise ValueError(f"Duplicate PDF lane: {key}, {row['residency']}")
        expected[key][row["residency"]] = row
    mismatches, seen, outside, format_differences = [], set(), [], []
    count_cells = 0

    def check(key, field, actual, wanted):
        if actual != wanted:
            mismatches.append({"key": list(key), "field": field, "canonical": actual, "pdf": wanted})

    with canonical.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if not row.get("hunt_code", "").startswith("BR"):
                continue
            key = row["hunt_code"], row["points"], row["record_type"]
            if key not in expected:
                separate_sportsman = (
                    row["hunt_code"] == "BR1000" and not row["points"]
                    and row["record_type"] == "sportsman_total_draw_result"
                    and row.get("draw_system_type") == "SPORTSMAN_RANDOM_ONLY"
                    and "sportsman" in row.get("source_file", "").lower()
                )
                outside.append({"key": key, "source_file": row.get("source_file"),
                                "reason": "SEPARATE_SPORTSMAN_REPORT_NOT_A_BONUS_LADDER" if separate_sportsman else "UNRESOLVED_OUTSIDE_REPORT_SCOPE"})
                continue
            if key in seen:
                check(key, "duplicate_key", True, False)
            seen.add(key)
            lanes = expected[key]
            source_row = lanes["Resident"]
            for field, wanted in (("actual_draw_year", str(year)),
                                  ("draw_pool", source_row["draw_pool"]), ("species", "Black Bear"),
                                  ("pdf_page", str(source_row["pdf_page"]))):
                check(key, field, row.get(field), wanted)
            actual_name, wanted_name = row.get("hunt_name", ""), source_row["hunt_name"]
            if actual_name != wanted_name:
                if re.sub(r"\s", "", actual_name).casefold() == re.sub(r"\s", "", wanted_name).casefold():
                    format_differences.append({"key": list(key), "canonical": actual_name, "pdf": wanted_name})
                else:
                    check(key, "hunt_name", actual_name, wanted_name)
            if not str(row.get("source_file", "")).replace("\\", "/").endswith("official_dwr_archive/black_bear/" + Path(source_row["source_file"]).name):
                check(key, "source_file", row.get("source_file"), source_row["source_file"])
            for field in COUNTS:
                for lane in LANES:
                    col = f"{lane.lower()}_{field}"
                    try:
                        value = number(row.get(col))
                    except ValueError:
                        value = row.get(col)
                    check(key, col, value, lanes[lane][field])
                    count_cells += 1
                combined = sum(lanes[lane][field] for lane in LANES)
                for col in {field, "total_" + field if field != "total_permits" else field}:
                    try:
                        value = number(row.get(col))
                    except ValueError:
                        value = row.get(col)
                    check(key, col, value, combined)
                    count_cells += 1
    missing = sorted(set(expected) - seen)
    # Other Bear programs remain visible and require their separate source;
    # they do not falsify exact parity for this report's point-ladder scope.
    unresolved_outside = [row for row in outside if row["reason"] == "UNRESOLVED_OUTSIDE_REPORT_SCOPE"]
    return {"status": "PASS" if not mismatches and not missing and not unresolved_outside else "REVIEW_REQUIRED",
            "matched_combined_point_rows": sum(key[2] == "point_level_draw_result" for key in seen),
            "matched_combined_total_rows": sum(key[2] == "hunt_total_draw_result" for key in seen),
            "numeric_cells_checked": count_cells, "mismatches": mismatches,
            "pdf_keys_missing_from_canonical": missing, "canonical_bear_rows_outside_report": outside,
            "whitespace_case_only_name_differences": format_differences,
            "point_ladder_scope_status": "PASS" if not mismatches and not missing else "FAIL"}


def protected_paths():
    paths = list((ROOT / "data_truth/draw_results_truth/normalized/canonical_yearly").glob("*.csv"))
    paths += [ROOT / path for path in (
        "data_truth/draw_results_truth/normalized/draw_results_long.csv",
        "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv",
        "processed_data/ml_draw_predictions_v1.csv", "processed_data/draw_reality_engine_predictive_v2.csv",
        "processed_data/bear_draw_predictions_v1.csv", "processed_data/bear_predictions_v1.csv",
        "processed_data/bear_report.json", "processed_data/draw_system_coverage_report.json",
        "processed_data/modeled_availability_review_report.json", "governance/prediction-family-certification.json",
        "engine/utah_draw_predictive/bear.py", "engine/utah_bonus_predictive/materialize.py",
    )]
    return {path.relative_to(ROOT).as_posix(): digest(path) for path in sorted(set(paths))}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, choices=sorted(REVIEWED), required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    out = args.out_dir.resolve()
    if not out.is_relative_to(ROOT / "audits") or out == ROOT / "audits":
        parser.error("Output must be a new directory below repository audits/")
    if out.exists():
        parser.error("Refusing to overwrite an existing evidence directory")
    year = args.year
    filename = REVIEWED[year]["url"].rsplit("/", 1)[-1]
    retained = ROOT / f"pipeline/RAW/hunt_unit_database/{year}/pdf/draw_odds/official_dwr_archive/black_bear/{filename}"
    canonical = ROOT / f"data_truth/draw_results_truth/normalized/canonical_yearly/draw_results_{year}_for_{year + 1}_canonical_yearly_draw_results.csv"
    before = protected_paths()
    before[retained.relative_to(ROOT).as_posix()] = digest(retained)
    out.mkdir(parents=True)
    dump(out / "protected_before.json", before)
    try:
        source = out / filename
        request = urllib.request.Request(REVIEWED[year]["url"], headers={"User-Agent": "UOGA-source-verification/1.0"})
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = response.read()
            if not payload.startswith(b"%PDF-"):
                raise ValueError("Official response is not a PDF")
            source.write_bytes(payload)
            provenance = {"url": REVIEWED[year]["url"], "final_url": response.url,
                          "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                          "last_modified": response.headers.get("Last-Modified"),
                          "etag": response.headers.get("ETag"), "bytes": len(payload),
                          "fresh_sha256": digest(source), "retained_sha256": digest(retained)}
        provenance["matches_retained_bytes"] = provenance["fresh_sha256"] == provenance["retained_sha256"]
        dump(out / "source_provenance.json", provenance)
        points, totals, pages = extract(source, retained, year)
        write_rows(out / f"bear_{year}_pdf_point_lanes.csv", points)
        write_rows(out / f"bear_{year}_pdf_printed_totals.csv", totals)
        dump(out / "page_audit.json", pages)
        # Freeze the independent PDF extraction before opening canonical contents.
        frozen = {path.name: digest(path) for path in out.glob("*.csv")}
        dump(out / "pdf_extract_freeze.json", frozen)
        parity = compare_canonical(points, totals, canonical, year)
        dump(out / "canonical_comparison.json", parity)
        grouped = {}
        for program in sorted({row["draw_pool"] for row in totals}):
            grouped[program] = {"hunt_codes": len({row["hunt_code"] for row in totals if row["draw_pool"] == program})}
            for lane in LANES:
                selected = [row for row in totals if row["draw_pool"] == program and row["residency"] == lane]
                grouped[program][lane] = {field: sum(row[field] for row in selected) for field in COUNTS}
        summary = {"year": year, "scope": "SINGLE_YEAR_OFFICIAL_BLACK_BEAR_REPORT_SOURCE_AUDIT_ONLY",
                   "status": parity["status"] if provenance["matches_retained_bytes"] else "OFFICIAL_SOURCE_CHANGED_REVIEW_REQUIRED",
                   "source": provenance, "pdf_pages": len(pages),
                   "context_only_pages": [page["pdf_page"] for page in pages if "hunt_code" not in page],
                   "point_purchase_pages": [page["pdf_page"] for page in pages if page["classification"] == "STATEWIDE_POINT_PURCHASE_CONTEXT_NOT_HUNT_APPLICANTS"],
                   "aggregate_pages": [page["pdf_page"] for page in pages if page["classification"] == "STATEWIDE_DRAW_AGGREGATE_NOT_ADDITIONAL_HUNT"],
                   "hunt_pages": len(totals) // 2, "explicit_residency_ladders": len(totals),
                   "point_rows": len(points), "point_range": [min(row["points"] for row in points), max(row["points"] for row in points)],
                   "printed_totals_checked": len(totals), "programs": grouped,
                   "canonical_comparison": parity, "canonical_sha256": digest(canonical),
                   "pdf_extract_frozen_before_canonical_comparison": True,
                   "frozen_extract_unchanged": all(digest(out / name) == value for name, value in frozen.items()),
                   "forecast_run": False, "production_rewritten": False, "certification_claim": False}
        dump(out / "summary.json", summary)
        print(json.dumps({key: value for key, value in summary.items() if key != "canonical_comparison"}, indent=2))
        return 0 if summary["status"] == "PASS" else 2
    finally:
        after = {path: digest(ROOT / path) for path in before}
        changed = [path for path in before if before[path] != after[path]]
        dump(out / "protected_after.json", {"files": after, "changed": changed, "unchanged": len(before) - len(changed)})
        if changed:
            raise RuntimeError(f"Protected files changed: {changed}")


if __name__ == "__main__":
    sys.exit(main())
