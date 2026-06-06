#!/usr/bin/env python3
"""Diagnose why controlled prediction outputs are not production-equivalent.

Read-only except for compact reports under
audits/prediction_model_runs/production_eligibility/.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any


OUT_DIR = Path("audits/prediction_model_runs/production_eligibility")
CANDIDATE_RUNS = [
    Path("audits/prediction_model_runs/2026_from_2025_truth_pdf_draw_results"),
    Path("audits/prediction_model_runs/2027_from_2026_dwr_released_candidate"),
]
PRODUCTION_FILES = [
    Path("processed_data/ml_draw_predictions_v1.csv"),
    Path("processed_data/draw_reality_engine_predictive_v2.csv"),
    Path("processed_data/point_ladder_view.csv"),
    Path("processed_data/hunt_research_2026.json"),
    Path("processed_data/hunt_research_2026_ladder.json"),
    Path("data_model/runtime_drafts/predictive_bonus_engine_2026.materialized.csv"),
]

CSV_EQUIVALENTS = {
    "processed_data/ml_draw_predictions_v1.csv": "ml_draw_predictions_v1.csv",
    "processed_data/draw_reality_engine_predictive_v2.csv": "draw_reality_engine_predictive_v2.csv",
    "data_model/runtime_drafts/predictive_bonus_engine_2026.materialized.csv": "predictive_bonus_engine_2026.materialized.csv",
}

COLUMN_FIELDS = [
    "candidate_run",
    "production_file",
    "candidate_file",
    "production_column",
    "classification",
    "required_for_direct_promotion",
    "reason",
]

FAMILY_FIELDS = [
    "candidate_run",
    "production_file",
    "candidate_file",
    "family",
    "production_rows",
    "candidate_rows",
    "missing_rows",
    "classification",
    "reason",
]

MERGE_FIELDS = [
    "candidate_run",
    "production_file",
    "candidate_file",
    "candidate_exists",
    "production_rows",
    "candidate_rows",
    "production_columns",
    "candidate_columns",
    "missing_column_count",
    "missing_family_count",
    "missing_row_count",
    "primary_classification",
    "merge_requirement",
    "promotion_blocker",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root.")
    parser.add_argument("--out-dir", default=str(OUT_DIR), help="Output directory.")
    return parser.parse_args()


def norm(value: Any) -> str:
    return str(value or "").replace("\ufeff", "").strip()


def norm_code(value: Any) -> str:
    return norm(value).upper()


def rel(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def sha256(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
    os.replace(tmp, path)


def fieldnames_from_json_array(path: Path, sample_limit: int = 2000) -> tuple[list[str], int, set[str], Counter[str]]:
    # The Hunt Research JSON files are large. Avoid loading the entire payload by
    # using the decoder incrementally for the top-level array.
    text = path.read_text(encoding="utf-8-sig")
    decoder = json.JSONDecoder()
    index = 0
    while index < len(text) and text[index].isspace():
        index += 1
    if index >= len(text) or text[index] != "[":
        data = json.loads(text)
        rows = data if isinstance(data, list) else data.get("rows", []) if isinstance(data, dict) else []
        header = sorted({key for row in rows if isinstance(row, dict) for key in row.keys()})
        codes = {norm_code(row.get("hunt_code")) for row in rows if isinstance(row, dict) and norm_code(row.get("hunt_code"))}
        fams = Counter(first_family(row) for row in rows if isinstance(row, dict))
        return header, len(rows), codes, fams
    index += 1
    header: set[str] = set()
    codes: set[str] = set()
    fams: Counter[str] = Counter()
    rows = 0
    while index < len(text):
        while index < len(text) and text[index].isspace():
            index += 1
        if index < len(text) and text[index] == "]":
            break
        obj, index = decoder.raw_decode(text, index)
        rows += 1
        if isinstance(obj, dict):
            if rows <= sample_limit:
                header.update(str(key) for key in obj.keys())
            code = norm_code(obj.get("hunt_code"))
            if code:
                codes.add(code)
            fams[first_family(obj)] += 1
        while index < len(text) and text[index].isspace():
            index += 1
        if index < len(text) and text[index] == ",":
            index += 1
            continue
        if index < len(text) and text[index] == "]":
            break
    return sorted(header), rows, codes, fams


def first_family(row: dict[str, Any]) -> str:
    for field in (
        "draw_system_type",
        "draw_2026_system_type",
        "draw_type",
        "hunt_type",
        "draw_model_class",
        "probability_model",
    ):
        value = norm(row.get(field))
        if value:
            return value
    return "(blank)"


def profile_file(root: Path, path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "path": rel(root, path),
            "exists": False,
            "rows": 0,
            "columns": [],
            "column_count": 0,
            "families": Counter(),
            "hunt_codes": set(),
            "sha256": "",
        }
    if path.suffix.lower() == ".json":
        columns, rows, hunt_codes, families = fieldnames_from_json_array(path)
        return {
            "path": rel(root, path),
            "exists": True,
            "rows": rows,
            "columns": columns,
            "column_count": len(columns),
            "families": families,
            "hunt_codes": hunt_codes,
            "sha256": sha256(path),
        }
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = list(reader.fieldnames or [])
        rows = 0
        families: Counter[str] = Counter()
        hunt_codes: set[str] = set()
        for row in reader:
            rows += 1
            code = norm_code(row.get("hunt_code"))
            if code:
                hunt_codes.add(code)
            families[first_family(row)] += 1
    return {
        "path": rel(root, path),
        "exists": True,
        "rows": rows,
        "columns": columns,
        "column_count": len(columns),
        "families": families,
        "hunt_codes": hunt_codes,
        "sha256": sha256(path),
    }


def classify_family(family: str) -> tuple[str, str]:
    value = family.upper()
    if value.startswith("BONUS") or "LIMITED ENTRY" in value or "ONCE" in value or "CWMU" in value:
        return "BONUS_ENGINE_OUTPUT", "bonus/max-random lane expected from the bonus materializer"
    if "PREFERENCE" in value or "DEDICATED" in value or "GENERAL SEASON" in value or "ANTLERLESS" in value:
        return "PREFERENCE_ENGINE_OUTPUT", "preference-point lane requires preference engine/output merge"
    if "SPORTSMAN" in value:
        return "SPORTSMAN_RANDOM_ONLY", "Sportsman permits are random-only/special-case outputs"
    if "YOUTH" in value:
        return "YOUTH_REVIEW_REQUIRED", "youth family needs separate review/merge rules"
    if "PRIVATE_LANDS" in value or "PRIVATE LAND" in value or "ALLOCATION" in value or "MOUNTAIN_LION" in value or "COUGAR" in value:
        return "ALLOCATION_OR_REFERENCE_ONLY", "availability/allocation/reference lane, not bonus probability output"
    if value == "(BLANK)":
        return "PUBLIC_RUNTIME_DISPLAY_METADATA", "display/runtime row lacks a normalized draw family"
    return "TRUE_MISSING_MODEL_OUTPUT", "family not explained by current classifier rules"


def classify_column(column: str, production_file: Path) -> tuple[str, str, str]:
    name = column.lower()
    file_text = production_file.as_posix().lower()
    if "hunt_research_2026" in file_text:
        return "PUBLIC_RUNTIME_DISPLAY_METADATA", "yes", "Hunt Research JSON is a merged website/runtime surface, not a raw model output"
    if "point_ladder_view" in file_text:
        return "ALLOCATION_OR_REFERENCE_ONLY", "yes", "point ladder columns come from draw-result/reference ladder merge"
    if "predictive_bonus_engine_2026.materialized" in file_text:
        return "BONUS_ENGINE_OUTPUT", "yes", "materialized file is the bonus-engine input, not produced by the controlled output folder"
    if any(token in name for token in ("preference", "dedicated", "general_season")):
        return "PREFERENCE_ENGINE_OUTPUT", "yes", "column belongs to preference-point modeling lane"
    if "sportsman" in name:
        return "SPORTSMAN_RANDOM_ONLY", "yes", "column belongs to Sportsman/random-only lane"
    if "youth" in name:
        return "YOUTH_REVIEW_REQUIRED", "yes", "column belongs to youth-specific review/model lane"
    if any(token in name for token in ("boundary", "allotment", "quota", "permit", "allocation", "source_file", "source_sha", "source_status", "validation", "hunt_name_source", "species_source", "weapon_source")):
        return "ALLOCATION_OR_REFERENCE_ONLY", "yes", "column is source/reference/allocation merge metadata"
    if any(token in name for token in ("display", "badge", "label", "status", "reason", "outlook", "context", "harvest", "quality", "freshness", "runtime")):
        return "PUBLIC_RUNTIME_DISPLAY_METADATA", "yes", "column is website/display/runtime decoration"
    if any(token in name for token in ("draw_2025", "permits_2025_draw", "page", "lineage", "source", "model_version", "rule_version")):
        return "PRODUCTION_COLUMN_DECORATION", "yes", "column is production decoration/lineage carried by runtime merge"
    if any(token in name for token in ("p_draw", "p_bonus", "p_random", "probability", "odds")):
        return "TRUE_MISSING_MODEL_OUTPUT", "yes", "probability/model column missing from candidate output"
    return "PRODUCTION_COLUMN_DECORATION", "yes", "production column appears to be decoration or merge metadata"


def candidate_path_for(root: Path, run: Path, production_file: Path) -> Path:
    rel_production = production_file.as_posix()
    equivalent = CSV_EQUIVALENTS.get(rel_production)
    if not equivalent:
        return root / run / production_file.name
    return root / run / equivalent


def diagnose(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    production_profiles = {prod: profile_file(root, root / prod) for prod in PRODUCTION_FILES}
    column_rows: list[dict[str, Any]] = []
    family_rows: list[dict[str, Any]] = []
    merge_rows: list[dict[str, Any]] = []
    summary: dict[str, Any] = {
        "candidate_runs": [run.as_posix() for run in CANDIDATE_RUNS],
        "production_files": [path.as_posix() for path in PRODUCTION_FILES],
        "production_files_modified": False,
        "promotions_applied": 0,
        "overall_diagnosis": "CONTROLLED_OUTPUTS_ARE_NOT_PRODUCTION_EQUIVALENT",
        "reason": "controlled folders contain engine outputs, while production files include preference/youth/special lanes plus runtime display/reference merge decorations",
    }

    for run in CANDIDATE_RUNS:
        run_name = run.name
        for prod in PRODUCTION_FILES:
            prod_profile = production_profiles[prod]
            candidate_path = candidate_path_for(root, run, prod)
            candidate_profile = profile_file(root, candidate_path)
            prod_columns = set(prod_profile["columns"])
            candidate_columns = set(candidate_profile["columns"])
            missing_columns = sorted(prod_columns - candidate_columns)
            for column in missing_columns:
                classification, required, reason = classify_column(column, prod)
                column_rows.append(
                    {
                        "candidate_run": run_name,
                        "production_file": prod.as_posix(),
                        "candidate_file": rel(root, candidate_path),
                        "production_column": column,
                        "classification": classification,
                        "required_for_direct_promotion": required,
                        "reason": reason,
                    }
                )

            missing_family_count = 0
            missing_rows = 0
            for family, prod_count in sorted(prod_profile["families"].items()):
                candidate_count = candidate_profile["families"].get(family, 0)
                delta = max(prod_count - candidate_count, 0)
                if delta <= 0:
                    continue
                classification, reason = classify_family(family)
                missing_family_count += 1
                missing_rows += delta
                family_rows.append(
                    {
                        "candidate_run": run_name,
                        "production_file": prod.as_posix(),
                        "candidate_file": rel(root, candidate_path),
                        "family": family,
                        "production_rows": prod_count,
                        "candidate_rows": candidate_count,
                        "missing_rows": delta,
                        "classification": classification,
                        "reason": reason,
                    }
                )

            primary_classification = "PRODUCTION_COLUMN_DECORATION"
            merge_requirement = "runtime schema/decorator merge required"
            if not candidate_profile["exists"]:
                if prod.suffix.lower() == ".json":
                    primary_classification = "PUBLIC_RUNTIME_DISPLAY_METADATA"
                    merge_requirement = "website JSON build/merge required; controlled model does not emit Hunt Research JSON"
                elif prod.name == "point_ladder_view.csv":
                    primary_classification = "ALLOCATION_OR_REFERENCE_ONLY"
                    merge_requirement = "point ladder generation required from draw truth/reference ladder"
                elif "materialized" in prod.name:
                    primary_classification = "BONUS_ENGINE_OUTPUT"
                    merge_requirement = "runtime draft materialized input is an upstream feeder, not a candidate output"
                else:
                    primary_classification = "TRUE_MISSING_MODEL_OUTPUT"
                    merge_requirement = "candidate did not produce production-equivalent file"
            elif missing_family_count:
                classes = Counter(row["classification"] for row in family_rows if row["candidate_run"] == run_name and row["production_file"] == prod.as_posix())
                primary_classification = classes.most_common(1)[0][0]
                merge_requirement = "additional family/lane merge required"

            merge_rows.append(
                {
                    "candidate_run": run_name,
                    "production_file": prod.as_posix(),
                    "candidate_file": rel(root, candidate_path),
                    "candidate_exists": candidate_profile["exists"],
                    "production_rows": prod_profile["rows"],
                    "candidate_rows": candidate_profile["rows"],
                    "production_columns": prod_profile["column_count"],
                    "candidate_columns": candidate_profile["column_count"],
                    "missing_column_count": len(missing_columns),
                    "missing_family_count": missing_family_count,
                    "missing_row_count": missing_rows,
                    "primary_classification": primary_classification,
                    "merge_requirement": merge_requirement,
                    "promotion_blocker": "YES" if missing_columns or missing_family_count or not candidate_profile["exists"] else "NO",
                }
            )
    summary["missing_column_rows"] = len(column_rows)
    summary["missing_family_rows"] = len(family_rows)
    summary["runtime_merge_rows"] = len(merge_rows)
    summary["promotion_blocker_rows"] = sum(1 for row in merge_rows if row["promotion_blocker"] == "YES")
    summary["classification_counts_columns"] = dict(Counter(row["classification"] for row in column_rows))
    summary["classification_counts_families"] = dict(Counter(row["classification"] for row in family_rows))
    return column_rows, family_rows, merge_rows, summary


def write_markdown(path: Path, summary: dict[str, Any], merge_rows: list[dict[str, Any]], family_rows: list[dict[str, Any]]) -> None:
    class_counts = Counter(row["primary_classification"] for row in merge_rows)
    family_counts = Counter(row["classification"] for row in family_rows)
    blocked = [row for row in merge_rows if row["promotion_blocker"] == "YES"]
    lines = [
        "# Production Equivalence Diagnosis",
        "",
        "## Result",
        "- Production promotion attempted: `no`",
        "- Production files modified: `no`",
        "- Direct production equivalence: `FAIL`",
        "- Diagnosis: controlled outputs are useful engine artifacts, but they are not production-equivalent runtime feeds.",
        "",
        "## Main Cause",
        "The controlled folders are not only a pure bonus-engine run, but they are still mostly bonus-engine materializer outputs plus a few special-case appenders. Production files are wider runtime surfaces: they include preference lanes, Sportsman/random-only lanes, youth review lanes, allocation/reference rows, point ladder rows, Hunt Research JSON display fields, and source/lineage decorations.",
        "",
        "## Blocker Counts",
        f"- Missing production column rows classified: `{summary['missing_column_rows']}`",
        f"- Missing family rows classified: `{summary['missing_family_rows']}`",
        f"- Runtime merge checks: `{summary['runtime_merge_rows']}`",
        f"- Promotion-blocking checks: `{summary['promotion_blocker_rows']}`",
        "",
        "## Runtime Merge Classification Counts",
    ]
    for name, count in sorted(class_counts.items()):
        lines.append(f"- `{name}`: `{count}`")
    lines.extend(["", "## Missing Family Classification Counts"])
    for name, count in sorted(family_counts.items()):
        lines.append(f"- `{name}`: `{count}`")
    lines.extend(["", "## What Is Missing"])
    lines.extend(
        [
            "- `PREFERENCE_ENGINE_OUTPUT`: preference-point and dedicated-hunter rows require the preference engine/output merge path.",
            "- `SPORTSMAN_RANDOM_ONLY`: Sportsman rows are random-only and special-case, not produced by the basic bonus ladder.",
            "- `YOUTH_REVIEW_REQUIRED`: youth rows need separate youth routing/review before production replacement.",
            "- `ALLOCATION_OR_REFERENCE_ONLY`: point ladder, allocation, permit, boundary, and reference rows come from runtime/reference merge layers.",
            "- `PUBLIC_RUNTIME_DISPLAY_METADATA`: Hunt Research JSON files are website-ready merged display surfaces, not direct model outputs.",
            "- `PRODUCTION_COLUMN_DECORATION`: production CSVs carry lineage, source, page, and display decoration columns beyond the controlled model core.",
            "- `TRUE_MISSING_MODEL_OUTPUT`: any remaining probability/model gaps need model-output investigation before promotion.",
        ]
    )
    lines.extend(["", "## Promotion Blockers By File"])
    for row in blocked:
        lines.append(
            f"- `{row['candidate_run']}` vs `{row['production_file']}`: "
            f"`{row['primary_classification']}`, missing columns `{row['missing_column_count']}`, "
            f"missing families `{row['missing_family_count']}`, missing rows `{row['missing_row_count']}`."
        )
    lines.extend(
        [
            "",
            "## Required Reports",
            "- `audits/prediction_model_runs/production_eligibility/diagnose_missing_production_columns.csv`",
            "- `audits/prediction_model_runs/production_eligibility/diagnose_missing_families.csv`",
            "- `audits/prediction_model_runs/production_eligibility/diagnose_runtime_merge_requirements.csv`",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    out_dir = (root / args.out_dir).resolve()
    columns, families, merges, summary = diagnose(root)
    write_csv(out_dir / "diagnose_missing_production_columns.csv", COLUMN_FIELDS, columns)
    write_csv(out_dir / "diagnose_missing_families.csv", FAMILY_FIELDS, families)
    write_csv(out_dir / "diagnose_runtime_merge_requirements.csv", MERGE_FIELDS, merges)
    write_markdown(out_dir / "PRODUCTION_EQUIVALENCE_DIAGNOSIS.md", summary, merges, families)
    (out_dir / "production_equivalence_diagnosis_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
