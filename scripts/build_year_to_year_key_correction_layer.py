"""Build repo-side year-to-year truth key correction audits.

This script intentionally does not read prediction outputs, external export
locations, or comparable files. It locks the repo truth/key layer from the
canonical yearly truth CSVs only.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_ROOT = REPO_ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"
AUDIT_ROOT = REPO_ROOT / "audits"
FILENAME_RE = re.compile(r"draw_results_(\d{4})_for_(\d{4})_canonical_yearly_draw_results\.csv$")

LANES = (
    ("resident_p_draw", "RESIDENT", "resident", "resident"),
    ("nonresident_p_draw", "NONRESIDENT", "nonresident", "nonresident"),
    ("total_p_draw", "TOTAL", "total", "total"),
)


@dataclass
class LaneRecord:
    key: str
    actual_draw_year: str
    model_target_year: str
    source_family: str
    draw_system_type: str
    draw_pool: str
    hunt_code: str
    species: str
    sex: str
    hunt_type: str
    score_scope: str
    residency: str
    points: str
    probability_metric: str
    probability_value: str
    source_pdf: str
    source_lineage: str


def norm(value: object, default: str = "") -> str:
    text = "" if value is None else str(value).strip()
    return text if text else default


def compact(value: object, default: str = "UNKNOWN") -> str:
    text = norm(value, default).upper()
    text = re.sub(r"[^A-Z0-9]+", "_", text).strip("_")
    return text or default


def parse_probability(value: object) -> str | None:
    text = norm(value)
    if not text or text.upper() in {"NA", "N/A", "NULL", "NONE"}:
        return None
    try:
        number = float(text.rstrip("%"))
    except ValueError:
        return None
    if text.endswith("%"):
        number = number / 100.0
    return f"{number:.12g}"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_files() -> List[Path]:
    files = []
    for path in CANONICAL_ROOT.glob("draw_results_*_for_*_canonical_yearly_draw_results.csv"):
        if FILENAME_RE.match(path.name):
            files.append(path)
    return sorted(files)


def extract_family(row: Dict[str, str]) -> str:
    for field in ("hunt_draw_class", "hunt_class", "source_dataset", "source_namespace"):
        value = norm(row.get(field))
        if value:
            return compact(value)
    notes = norm(row.get("qa_notes"))
    match = re.search(r"(?:family|rebuilt_bucket)=([^;]+)", notes, flags=re.I)
    if match:
        return compact(match.group(1))
    source = " ".join(
        norm(row.get(field))
        for field in ("source_file", "draw_source_file", "source_path", "source_pdf")
    ).lower()
    if "cwmu" in source:
        return "CWMU"
    if "sportsman" in source:
        return "SPORTSMAN"
    if "turkey" in source:
        return "TURKEY"
    if "antlerless" in source:
        return "ANTLERLESS"
    if "cougar" in source:
        return "COUGAR"
    if "bear" in source:
        return "BLACK_BEAR"
    if "dedicated" in source:
        return "DEDICATED_HUNTER"
    if "general" in source or "gs" in source:
        return "GENERAL_SEASON_DEER"
    if "limited" in source or "oil" in source:
        return "BIG_GAME_LIMITED_ENTRY"
    return "UNKNOWN"


def lineage_value(row: Dict[str, str]) -> str:
    parts = [
        norm(row.get("source_file")),
        norm(row.get("draw_source_file")),
        norm(row.get("source_path")),
        norm(row.get("source_pdf")),
        norm(row.get("pdf_page")),
        norm(row.get("official_page")),
    ]
    return "|".join(part for part in parts if part)


def source_pdf_value(row: Dict[str, str]) -> str:
    for field in ("source_pdf", "draw_source_file", "source_file"):
        value = norm(row.get(field))
        if value:
            return value
    return ""


def key_parts_for(row: Dict[str, str], metric: str, scope: str, residency: str) -> List[str]:
    actual_year = norm(row.get("actual_draw_year"))
    target_year = norm(row.get("model_target_year"))
    source_family = extract_family(row)
    draw_system_type = compact(row.get("draw_system_type") or row.get("draw_design"))
    draw_pool = compact(row.get("draw_pool") or row.get("draw_design"))
    hunt_code = compact(row.get("hunt_code"))
    species = compact(row.get("species"))
    sex = compact(row.get("sex") or row.get("sex_type"))
    hunt_type = compact(row.get("hunt_type"))
    points = compact(row.get("points"), "NO_POINTS")
    return [
        actual_year,
        target_year,
        source_family,
        draw_system_type,
        draw_pool,
        hunt_code,
        species,
        sex,
        hunt_type,
        compact(scope),
        compact(residency),
        points,
        compact(metric),
    ]


def lane_records(row: Dict[str, str]) -> Tuple[List[LaneRecord], Counter]:
    excluded = Counter()
    rows: List[LaneRecord] = []
    hunt_code = compact(row.get("hunt_code"), "")
    actual_year = norm(row.get("actual_draw_year"))
    target_year = norm(row.get("model_target_year"))
    if not actual_year or not target_year:
        excluded["missing_year"] += 1
    if not hunt_code:
        excluded["missing_hunt_code"] += 1

    for metric, scope, residency, lineage_scope in LANES:
        probability = parse_probability(row.get(metric))
        if probability is None:
            excluded[f"missing_or_nonnumeric_{metric}"] += 1
            continue
        parts = key_parts_for(row, metric, scope, residency)
        line = lineage_value(row)
        rows.append(
            LaneRecord(
                key="|".join(parts),
                actual_draw_year=actual_year,
                model_target_year=target_year,
                source_family=parts[2],
                draw_system_type=parts[3],
                draw_pool=parts[4],
                hunt_code=parts[5],
                species=parts[6],
                sex=parts[7],
                hunt_type=parts[8],
                score_scope=scope,
                residency=lineage_scope,
                points=parts[11],
                probability_metric=metric,
                probability_value=probability,
                source_pdf=source_pdf_value(row),
                source_lineage=line,
            )
        )

    if not rows:
        fallback_probability = parse_probability(row.get("p_draw"))
        if fallback_probability is None:
            excluded["missing_or_nonnumeric_p_draw_fallback"] += 1
        else:
            residency = norm(row.get("residency"), "total").lower()
            scope = "TOTAL" if residency in {"total", "all"} else residency.upper()
            parts = key_parts_for(row, "p_draw", scope, residency)
            line = lineage_value(row)
            rows.append(
                LaneRecord(
                    key="|".join(parts),
                    actual_draw_year=actual_year,
                    model_target_year=target_year,
                    source_family=parts[2],
                    draw_system_type=parts[3],
                    draw_pool=parts[4],
                    hunt_code=parts[5],
                    species=parts[6],
                    sex=parts[7],
                    hunt_type=parts[8],
                    score_scope=scope,
                    residency=residency,
                    points=parts[11],
                    probability_metric="p_draw",
                    probability_value=fallback_probability,
                    source_pdf=source_pdf_value(row),
                    source_lineage=line,
                )
            )
    return rows, excluded


def write_csv(path: Path, rows: Iterable[Dict[str, object]], fieldnames: List[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def main() -> int:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    lock_timestamp = datetime.now().isoformat(timespec="seconds")
    output_dir = AUDIT_ROOT / f"year_to_year_key_correction{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=False)

    files = canonical_files()
    if not files:
        raise SystemExit(f"No canonical yearly files found under {CANONICAL_ROOT}")

    summary_rows: List[Dict[str, object]] = []
    lineage_rows: List[Dict[str, object]] = []
    row_sanity_rows: List[Dict[str, object]] = []
    construction_counts: Counter[Tuple[str, str, str, str, str]] = Counter()
    key_records: Dict[str, List[LaneRecord]] = defaultdict(list)
    input_hashes: Dict[str, str] = {}
    source_pdfs = set()
    totals = Counter()

    for path in files:
        match = FILENAME_RE.match(path.name)
        actual_year, target_year = match.group(1), match.group(2)
        input_hashes[str(path.relative_to(REPO_ROOT))] = sha256_file(path)

        physical_rows = 0
        generated_lanes = 0
        excluded = Counter()
        missing_lineage_rows = 0
        missing_code_rows = 0
        unique_hunt_codes = set()
        unique_source_pdfs = set()
        year_key_counter = Counter()
        year_probabilities: Dict[str, set] = defaultdict(set)

        with path.open("r", newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                physical_rows += 1
                if not norm(row.get("hunt_code")):
                    missing_code_rows += 1
                else:
                    unique_hunt_codes.add(compact(row.get("hunt_code")))
                if not lineage_value(row):
                    missing_lineage_rows += 1
                source_pdf = source_pdf_value(row)
                if source_pdf:
                    source_pdfs.add(source_pdf)
                    unique_source_pdfs.add(source_pdf)

                lanes, lane_excluded = lane_records(row)
                excluded.update(lane_excluded)
                for lane in lanes:
                    generated_lanes += 1
                    key_records[lane.key].append(lane)
                    year_key_counter[lane.key] += 1
                    year_probabilities[lane.key].add(lane.probability_value)
                    construction_counts[
                        (
                            lane.actual_draw_year,
                            lane.source_family,
                            lane.draw_system_type,
                            lane.score_scope,
                            lane.probability_metric,
                        )
                    ] += 1

        duplicate_groups = sum(1 for count in year_key_counter.values() if count > 1)
        conflict_groups = sum(
            1
            for key, count in year_key_counter.items()
            if count > 1 and len(year_probabilities[key]) > 1
        )
        unique_keys = len(year_key_counter)
        lineage_covered_rows = physical_rows - missing_lineage_rows
        lineage_pct = (lineage_covered_rows / physical_rows * 100.0) if physical_rows else 0.0

        summary_rows.append(
            {
                "actual_draw_year": actual_year,
                "model_target_year": target_year,
                "canonical_truth_path": str(path.relative_to(REPO_ROOT)),
                "physical_truth_rows": physical_rows,
                "unique_hunt_codes": len(unique_hunt_codes),
                "generated_truth_key_lanes": generated_lanes,
                "unique_truth_keys": unique_keys,
                "duplicate_key_groups": duplicate_groups,
                "conflict_key_groups": conflict_groups,
                "excluded_missing_or_nonnumeric_probability_lanes": sum(excluded.values()),
                "missing_hunt_code_rows": missing_code_rows,
                "source_lineage_coverage_pct": f"{lineage_pct:.4f}",
                "sanity_status": "REVIEW" if conflict_groups or missing_code_rows or lineage_pct < 100.0 else "PASS",
            }
        )
        lineage_rows.append(
            {
                "actual_draw_year": actual_year,
                "model_target_year": target_year,
                "canonical_truth_path": str(path.relative_to(REPO_ROOT)),
                "physical_truth_rows": physical_rows,
                "rows_with_source_lineage": lineage_covered_rows,
                "rows_missing_source_lineage": missing_lineage_rows,
                "source_lineage_coverage_pct": f"{lineage_pct:.4f}",
                "unique_source_pdf_count": len(unique_source_pdfs),
                "unique_source_pdf_sample": "; ".join(sorted(unique_source_pdfs)[:20]),
            }
        )
        row_sanity_rows.append(
            {
                "actual_draw_year": actual_year,
                "model_target_year": target_year,
                "canonical_truth_path": str(path.relative_to(REPO_ROOT)),
                "physical_truth_rows": physical_rows,
                "generated_truth_key_lanes": generated_lanes,
                "unique_truth_keys": unique_keys,
                "duplicate_key_groups": duplicate_groups,
                "conflict_key_groups": conflict_groups,
                "missing_hunt_code_rows": missing_code_rows,
                "missing_year_lanes": excluded.get("missing_year", 0),
                "missing_or_nonnumeric_resident_p_draw": excluded.get("missing_or_nonnumeric_resident_p_draw", 0),
                "missing_or_nonnumeric_nonresident_p_draw": excluded.get("missing_or_nonnumeric_nonresident_p_draw", 0),
                "missing_or_nonnumeric_total_p_draw": excluded.get("missing_or_nonnumeric_total_p_draw", 0),
                "missing_or_nonnumeric_p_draw_fallback": excluded.get("missing_or_nonnumeric_p_draw_fallback", 0),
                "row_count_sanity_status": "REVIEW" if conflict_groups or missing_code_rows else "PASS",
            }
        )
        totals.update(
            {
                "physical_truth_rows": physical_rows,
                "generated_truth_key_lanes": generated_lanes,
                "unique_hunt_codes_year_sum": len(unique_hunt_codes),
                "duplicate_key_groups_year_sum": duplicate_groups,
                "conflict_key_groups_year_sum": conflict_groups,
                "missing_hunt_code_rows": missing_code_rows,
                "missing_source_lineage_rows": missing_lineage_rows,
            }
        )

    duplicate_rows: List[Dict[str, object]] = []
    conflict_rows: List[Dict[str, object]] = []
    for key, records in sorted(key_records.items()):
        if len(records) <= 1:
            continue
        probabilities = sorted({record.probability_value for record in records})
        source_values = sorted({record.source_pdf for record in records if record.source_pdf})
        first = records[0]
        row = {
            "truth_key": key,
            "duplicate_count": len(records),
            "actual_draw_year": first.actual_draw_year,
            "model_target_year": first.model_target_year,
            "source_family": first.source_family,
            "draw_system_type": first.draw_system_type,
            "draw_pool": first.draw_pool,
            "hunt_code": first.hunt_code,
            "species": first.species,
            "sex": first.sex,
            "hunt_type": first.hunt_type,
            "score_scope": first.score_scope,
            "residency": first.residency,
            "points": first.points,
            "probability_metric": first.probability_metric,
            "distinct_probability_count": len(probabilities),
            "probability_values": ";".join(probabilities[:20]),
            "source_pdf_count": len(source_values),
            "source_pdf_sample": "; ".join(source_values[:10]),
            "review_status": "CONFLICT_REVIEW_REQUIRED"
            if len(probabilities) > 1
            else "DUPLICATE_IDENTICAL_OR_LINEAGE_COLLAPSE_CANDIDATE",
        }
        duplicate_rows.append(row)
        if row["review_status"] == "CONFLICT_REVIEW_REQUIRED":
            conflict_rows.append(row)

    construction_rows = [
        {
            "actual_draw_year": year,
            "source_family": family,
            "draw_system_type": system_type,
            "score_scope": scope,
            "probability_metric": metric,
            "generated_truth_key_lanes": count,
        }
        for (year, family, system_type, scope, metric), count in sorted(construction_counts.items())
    ]

    duplicate_count = len(duplicate_rows)
    conflict_count = len(conflict_rows)
    lineage_blocked = any(float(row["source_lineage_coverage_pct"]) == 0.0 for row in lineage_rows)
    row_sanity_blocked = any(int(row["generated_truth_key_lanes"]) == 0 for row in row_sanity_rows)
    if lineage_blocked:
        status = "FAIL_BLOCKED_SOURCE_LINEAGE"
    elif row_sanity_blocked:
        status = "FAIL_BLOCKED_ROW_COUNT_SANITY"
    elif conflict_count:
        status = "PASS_WITH_REVIEW_REQUIRED"
    else:
        status = "PASS_KEY_MATCHED_THROUGH_CURRENT" if duplicate_count == 0 else "PASS_WITH_REVIEW_REQUIRED"

    outputs = {
        "summary": output_dir / "YEAR_TO_YEAR_KEY_CORRECTION_SUMMARY.csv",
        "duplicates": output_dir / "YEAR_TO_YEAR_DUPLICATE_KEY_AUDIT.csv",
        "lineage": output_dir / "YEAR_TO_YEAR_SOURCE_LINEAGE_AUDIT.csv",
        "row_sanity": output_dir / "YEAR_TO_YEAR_ROW_COUNT_SANITY_AUDIT.csv",
        "construction": output_dir / "YEAR_TO_YEAR_KEY_CONSTRUCTION_AUDIT.csv",
        "conflicts": output_dir / "YEAR_TO_YEAR_KEY_CONFLICT_REVIEW.csv",
        "report": output_dir / "YEAR_TO_YEAR_KEY_CORRECTION_REPORT.md",
        "manifest": output_dir / "YEAR_TO_YEAR_TRUTH_KEY_LOCK_MANIFEST.md",
    }

    write_csv(
        outputs["summary"],
        summary_rows,
        [
            "actual_draw_year",
            "model_target_year",
            "canonical_truth_path",
            "physical_truth_rows",
            "unique_hunt_codes",
            "generated_truth_key_lanes",
            "unique_truth_keys",
            "duplicate_key_groups",
            "conflict_key_groups",
            "excluded_missing_or_nonnumeric_probability_lanes",
            "missing_hunt_code_rows",
            "source_lineage_coverage_pct",
            "sanity_status",
        ],
    )
    write_csv(
        outputs["duplicates"],
        duplicate_rows,
        [
            "truth_key",
            "duplicate_count",
            "actual_draw_year",
            "model_target_year",
            "source_family",
            "draw_system_type",
            "draw_pool",
            "hunt_code",
            "species",
            "sex",
            "hunt_type",
            "score_scope",
            "residency",
            "points",
            "probability_metric",
            "distinct_probability_count",
            "probability_values",
            "source_pdf_count",
            "source_pdf_sample",
            "review_status",
        ],
    )
    write_csv(
        outputs["lineage"],
        lineage_rows,
        [
            "actual_draw_year",
            "model_target_year",
            "canonical_truth_path",
            "physical_truth_rows",
            "rows_with_source_lineage",
            "rows_missing_source_lineage",
            "source_lineage_coverage_pct",
            "unique_source_pdf_count",
            "unique_source_pdf_sample",
        ],
    )
    write_csv(
        outputs["row_sanity"],
        row_sanity_rows,
        [
            "actual_draw_year",
            "model_target_year",
            "canonical_truth_path",
            "physical_truth_rows",
            "generated_truth_key_lanes",
            "unique_truth_keys",
            "duplicate_key_groups",
            "conflict_key_groups",
            "missing_hunt_code_rows",
            "missing_year_lanes",
            "missing_or_nonnumeric_resident_p_draw",
            "missing_or_nonnumeric_nonresident_p_draw",
            "missing_or_nonnumeric_total_p_draw",
            "missing_or_nonnumeric_p_draw_fallback",
            "row_count_sanity_status",
        ],
    )
    write_csv(
        outputs["construction"],
        construction_rows,
        [
            "actual_draw_year",
            "source_family",
            "draw_system_type",
            "score_scope",
            "probability_metric",
            "generated_truth_key_lanes",
        ],
    )
    write_csv(
        outputs["conflicts"],
        conflict_rows,
        [
            "truth_key",
            "duplicate_count",
            "actual_draw_year",
            "model_target_year",
            "source_family",
            "draw_system_type",
            "draw_pool",
            "hunt_code",
            "species",
            "sex",
            "hunt_type",
            "score_scope",
            "residency",
            "points",
            "probability_metric",
            "distinct_probability_count",
            "probability_values",
            "source_pdf_count",
            "source_pdf_sample",
            "review_status",
        ],
    )

    source_pdf_manifest = output_dir / "YEAR_TO_YEAR_SOURCE_PDF_LIST.json"
    source_pdf_manifest.write_text(
        json.dumps(sorted(source_pdfs), indent=2) + "\n",
        encoding="utf-8",
    )

    output_hashes = {
        name: sha256_file(path)
        for name, path in outputs.items()
        if name not in {"report", "manifest"}
    }
    output_hashes["source_pdf_list"] = sha256_file(source_pdf_manifest)

    key_recipe = (
        "truth_key = actual_draw_year | model_target_year | source_family_truth | "
        "draw_system_type_truth | draw_pool_truth | hunt_code | species | sex | hunt_type | "
        "score_scope | residency | points | probability_metric. All fields are read or "
        "derived only from canonical truth/source columns."
    )
    report = [
        "# Year-to-Year Key Correction Report",
        "",
        f"timestamp: {lock_timestamp}",
        f"status: {status}",
        "",
        "## Boundary",
        "",
        "Repo-side key construction used canonical yearly truth files only.",
        "No prediction outputs were opened, read, or used.",
        "No external comparable export path was used or inferred.",
        "Large comparable exports were not created.",
        "",
        "## Key Recipe",
        "",
        key_recipe,
        "",
        "## Totals",
        "",
        f"canonical_yearly_files: {len(files)}",
        f"physical_truth_rows: {totals['physical_truth_rows']}",
        f"generated_truth_key_lanes: {totals['generated_truth_key_lanes']}",
        f"duplicate_key_groups: {duplicate_count}",
        f"conflict_key_groups: {conflict_count}",
        f"missing_hunt_code_rows: {totals['missing_hunt_code_rows']}",
        f"missing_source_lineage_rows: {totals['missing_source_lineage_rows']}",
        "",
        "## Required Outputs",
        "",
    ]
    for label, path in outputs.items():
        report.append(f"- {path.relative_to(REPO_ROOT)}")
    report.append(f"- {source_pdf_manifest.relative_to(REPO_ROOT)}")
    report.append("")
    report.append("## Export Status")
    report.append("")
    report.append("EXTERNAL_COMPARABLES_STATUS=WAITING_FOR_USER_APPROVED_EXTERNAL_PATH")
    report.append("NEXT_REQUIRED_USER_INPUT=Provide approved external output path for large truth-test comparable exports.")
    outputs["report"].write_text("\n".join(report) + "\n", encoding="utf-8")
    output_hashes["report"] = sha256_file(outputs["report"])

    manifest_lines = [
        "# Year-to-Year Truth Key Lock Manifest",
        "",
        f"truth_key_lock_timestamp: {lock_timestamp}",
        f"YEAR_TO_YEAR_KEY_STATUS: {status}",
        "TRUTH_KEY_LAYER_LOCKED_BEFORE_COMPARABLE_EXPORT = TRUE",
        "PREDICTION_OUTPUTS_ACCESSED_DURING_KEY_LAYER_BUILD = FALSE",
        "EXTERNAL_COMPARABLE_EXPORT_PATH_KNOWN_DURING_KEY_LAYER_BUILD = FALSE",
        "LARGE_COMPARABLE_OUTPUTS_WRITTEN_INSIDE_GITHUB = FALSE",
        "",
        "## Corrected Truth/Key File Paths",
        "",
        "The locked repo-side layer consists of the canonical yearly truth inputs, the deterministic key recipe, and the aggregate audit outputs listed below. Full comparable files are intentionally not materialized inside GitHub.",
        "",
        "## Key Recipe",
        "",
        key_recipe,
        "",
        "## Row Counts",
        "",
        f"canonical_yearly_files: {len(files)}",
        f"physical_truth_rows: {totals['physical_truth_rows']}",
        f"generated_truth_key_lanes: {totals['generated_truth_key_lanes']}",
        f"duplicate_key_groups: {duplicate_count}",
        f"conflict_key_groups: {conflict_count}",
        f"excluded_missing_or_nonnumeric_probability_lane_events: {sum(int(row['excluded_missing_or_nonnumeric_probability_lanes']) for row in summary_rows)}",
        f"missing_hunt_code_rows: {totals['missing_hunt_code_rows']}",
        f"missing_source_lineage_rows: {totals['missing_source_lineage_rows']}",
        "",
        "## Source Lineage Coverage",
        "",
    ]
    for row in lineage_rows:
        manifest_lines.append(
            f"- {row['actual_draw_year']}_for_{row['model_target_year']}: "
            f"{row['rows_with_source_lineage']}/{row['physical_truth_rows']} rows "
            f"({row['source_lineage_coverage_pct']}%), "
            f"{row['unique_source_pdf_count']} unique source PDFs"
        )
    manifest_lines.extend(["", "## Canonical Input SHA256", ""])
    for rel_path, digest in sorted(input_hashes.items()):
        manifest_lines.append(f"- {rel_path}: {digest}")
    manifest_lines.extend(["", "## Locked Output SHA256", ""])
    for name, digest in sorted(output_hashes.items()):
        path = source_pdf_manifest if name == "source_pdf_list" else outputs[name]
        manifest_lines.append(f"- {path.relative_to(REPO_ROOT)}: {digest}")
    manifest_lines.extend(["", "## Source PDF List", ""])
    for source_pdf in sorted(source_pdfs):
        manifest_lines.append(f"- {source_pdf}")
    outputs["manifest"].write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")

    final_output = (
        f"YEAR_TO_YEAR_KEY_CORRECTION_OUTPUT_DIR={output_dir}\n"
        f"YEAR_TO_YEAR_TRUTH_KEY_LOCK_MANIFEST={outputs['manifest']}\n"
        f"YEAR_TO_YEAR_KEY_STATUS={status}\n"
        "EXTERNAL_COMPARABLES_STATUS=WAITING_FOR_USER_APPROVED_EXTERNAL_PATH\n"
        "NEXT_REQUIRED_USER_INPUT=Provide approved external output path for large truth-test comparable exports.\n"
    )
    (output_dir / "FINAL_TERMINAL_OUTPUT.txt").write_text(final_output, encoding="utf-8")
    print(final_output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
