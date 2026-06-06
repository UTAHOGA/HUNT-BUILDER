#!/usr/bin/env python3
"""Build a production prediction assembly plan from equivalence diagnosis reports.

This script does not modify production files and does not promote outputs. It
only writes compact planning reports under the production-eligibility audit
folder.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


DEFAULT_OUT_DIR = Path("audits/prediction_model_runs/production_eligibility")
DIAGNOSIS_MD = DEFAULT_OUT_DIR / "PRODUCTION_EQUIVALENCE_DIAGNOSIS.md"
MISSING_COLUMNS = DEFAULT_OUT_DIR / "diagnose_missing_production_columns.csv"
MISSING_FAMILIES = DEFAULT_OUT_DIR / "diagnose_missing_families.csv"
RUNTIME_MERGE = DEFAULT_OUT_DIR / "diagnose_runtime_merge_requirements.csv"

LANE_FIELDS = [
    "lane",
    "purpose",
    "current_provider_files",
    "current_production_outputs",
    "controlled_candidate_files",
    "current_production_status",
    "controlled_rebuild_status",
    "safe_promotion_candidate_later",
    "must_remain_audit_only",
    "runtime_merge_required",
    "evidence_summary",
    "notes",
]

INPUT_FIELDS = [
    "lane",
    "input_file",
    "role",
    "exists",
    "required_for_production",
    "mutation_allowed",
    "source_status",
    "notes",
]

BLOCKER_FIELDS = [
    "blocker_id",
    "lane",
    "blocker_type",
    "severity",
    "source_evidence_file",
    "affected_production_files",
    "blocker",
    "required_resolution",
    "stop_condition",
]

LANES = [
    "BONUS_ENGINE_OUTPUT",
    "PREFERENCE_ENGINE_OUTPUT",
    "SPORTSMAN_RANDOM_ONLY",
    "YOUTH_REVIEW_REQUIRED / YOUTH_CONFIRMED_LANE",
    "ALLOCATION_OR_REFERENCE_ONLY",
    "PUBLIC_RUNTIME_DISPLAY_METADATA",
    "POINT_LADDER_DISPLAY",
    "HUNT_RESEARCH_JSON_MERGE",
]

ACTIVE_BUILDERS = [
    {
        "script": "engine.utah_bonus_predictive.materialize",
        "sequence_role": "prediction math",
        "contributes": "model outputs",
        "primary_outputs": "ml_draw_predictions_v1.csv; draw_reality_engine_predictive_v2.csv; lane-specific prediction CSVs",
        "lane_ownership": "BONUS_ENGINE_OUTPUT plus wired special-case model appenders; does not by itself create the full website/runtime contract",
        "required_inputs": "validated historical draw truth; current hunt/permit/allotment reference; runtime draft materialized feeder inputs",
        "blocker_if_missing": "No production-equivalent model rows can be staged.",
    },
    {
        "script": "scripts/sync_online_runtime_from_predictive.py",
        "sequence_role": "runtime sync",
        "contributes": "runtime display fields; allocation/reference rows; Hunt Research JSON decoration inputs",
        "primary_outputs": "decorated runtime CSV surfaces consumed by downstream builders",
        "lane_ownership": "PUBLIC_RUNTIME_DISPLAY_METADATA and ALLOCATION_OR_REFERENCE_ONLY merge layer",
        "required_inputs": "model outputs plus reference, source-lineage, and current hunt metadata",
        "blocker_if_missing": "Model math remains too narrow for production display and website handoff.",
    },
    {
        "script": "scripts/build-unified-point-ladder-runtime.py",
        "sequence_role": "point ladder merge",
        "contributes": "POINT_LADDER_DISPLAY",
        "primary_outputs": "processed_data/point_ladder_view.csv",
        "lane_ownership": "compact public/runtime ladder; not the broader 91k Hunt Research surface",
        "required_inputs": "draw truth, point rows, residency/points grain, and runtime reference fields",
        "blocker_if_missing": "Hunt Research ladder display cannot prove compact grain/row parity.",
    },
    {
        "script": "scripts/build-hunt-research-2026-contract.py",
        "sequence_role": "Hunt Research JSON contract",
        "contributes": "HUNT_RESEARCH_JSON_MERGE; PUBLIC_RUNTIME_DISPLAY_METADATA; Hunt Research JSON decoration",
        "primary_outputs": "processed_data/hunt_research_2026.json; processed_data/hunt_research_2026_ladder.json",
        "lane_ownership": "website-facing research contract merge, including model outputs, ladder/reference rows, lineage, and display metadata",
        "required_inputs": "decorated model/runtime CSVs, compact ladder, reference overlays, and source-lineage fields",
        "blocker_if_missing": "Large Hunt Research JSON cannot be rebuilt from validated staged runtime inputs.",
    },
    {
        "script": "scripts/rebuild-runtime-hunt-master-and-split.py",
        "sequence_role": "final runtime master/split",
        "contributes": "final runtime master/split; R2-ready split/index packaging",
        "primary_outputs": "processed_data/hunt_research_2026_summary.json; processed_data/hunt_research_2026_split/",
        "lane_ownership": "final public/runtime packaging after contract validation; upload/publish remains a separate gated action",
        "required_inputs": "validated Hunt Research contract JSON and runtime master files",
        "blocker_if_missing": "Website/runtime split files cannot be regenerated or prepared for R2 validation.",
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="Output directory.")
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
    os.replace(tmp, path)


def exists(root: Path, relpath: str) -> str:
    return "yes" if (root / relpath).exists() else "no"


def count_by(rows: list[dict[str, str]], field: str) -> Counter[str]:
    return Counter((row.get(field) or "").strip() or "(blank)" for row in rows)


def rows_for_class(rows: list[dict[str, str]], classification: str) -> list[dict[str, str]]:
    return [row for row in rows if (row.get("classification") or row.get("primary_classification") or "").strip() == classification]


def affected_files(rows: list[dict[str, str]]) -> str:
    return "; ".join(sorted({row.get("production_file", "") for row in rows if row.get("production_file")}))


def sum_int(rows: list[dict[str, str]], field: str) -> int:
    total = 0
    for row in rows:
        try:
            total += int(float(str(row.get(field) or 0)))
        except ValueError:
            pass
    return total


def build_lane_rows(root: Path, column_rows: list[dict[str, str]], family_rows: list[dict[str, str]], merge_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    column_counts = count_by(column_rows, "classification")
    family_counts = count_by(family_rows, "classification")
    merge_counts = count_by(merge_rows, "primary_classification")
    lane_rows = [
        {
            "lane": "BONUS_ENGINE_OUTPUT",
            "purpose": "LE / OIL / PLE / CWMU / other bonus-based families with split random/max-pool probability logic.",
            "current_provider_files": "data_model/runtime_drafts/predictive_bonus_engine_2026.materialized.csv; engine/utah_bonus_predictive/materialize.py; engine/utah_draw_predictive/special_bonus.py; engine/utah_draw_predictive/turkey.py; engine/utah_draw_predictive/bear.py",
            "current_production_outputs": "processed_data/ml_draw_predictions_v1.csv; processed_data/draw_reality_engine_predictive_v2.csv",
            "controlled_candidate_files": "audits/prediction_model_runs/2026_from_2025_truth_pdf_draw_results/ml_draw_predictions_v1.csv; audits/prediction_model_runs/2026_from_2025_truth_pdf_draw_results/draw_reality_engine_predictive_v2.csv",
            "current_production_status": "present_in_current_production",
            "controlled_rebuild_status": "partial_not_production_equivalent",
            "safe_promotion_candidate_later": "only_after_schema_family_and_runtime_merge_parity",
            "must_remain_audit_only": "yes_until_full_assembly_passes",
            "runtime_merge_required": "yes",
            "evidence_summary": f"column_gaps={column_counts['BONUS_ENGINE_OUTPUT']}; family_gaps={family_counts['BONUS_ENGINE_OUTPUT']}; merge_gaps={merge_counts['BONUS_ENGINE_OUTPUT']}",
            "notes": "Controlled outputs include bonus lanes, but diagnosis still shows missing bonus-family rows versus production.",
        },
        {
            "lane": "PREFERENCE_ENGINE_OUTPUT",
            "purpose": "General-season deer, dedicated hunter, antlerless deer/elk, doe pronghorn, and preference-point ladder/rank logic with no bonus max-pool assumptions.",
            "current_provider_files": "engine/utah_draw_predictive/preference_general_deer.py; engine/utah_draw_predictive/preference_antlerless.py; engine/utah_draw_predictive/dedicated_hunter.py; processed_data/point_ladder_view.csv",
            "current_production_outputs": "processed_data/ml_draw_predictions_v1.csv; processed_data/draw_reality_engine_predictive_v2.csv; processed_data/point_ladder_view.csv",
            "controlled_candidate_files": "candidate ML/predictive CSVs contain only partial preference rows",
            "current_production_status": "present_in_current_production",
            "controlled_rebuild_status": "incomplete_missing_preference_lanes",
            "safe_promotion_candidate_later": "preference lane outputs only after row/family/schema parity",
            "must_remain_audit_only": "yes_until_preference_merge_is_verified",
            "runtime_merge_required": "yes",
            "evidence_summary": f"column_gaps={column_counts['PREFERENCE_ENGINE_OUTPUT']}; family_gaps={family_counts['PREFERENCE_ENGINE_OUTPUT']}; merge_gaps={merge_counts['PREFERENCE_ENGINE_OUTPUT']}",
            "notes": "Preference families are the largest clear missing model lane in the controlled outputs.",
        },
        {
            "lane": "SPORTSMAN_RANDOM_ONLY",
            "purpose": "Sportsman permits; random-only draw logic with no bonus ladder, no preference ladder, and no max-pool math.",
            "current_provider_files": "engine/utah_draw_predictive/sportsman.py; data/utah/sportsman/sportsman_odds_2025.csv",
            "current_production_outputs": "processed_data/ml_draw_predictions_v1.csv; processed_data/draw_reality_engine_predictive_v2.csv",
            "controlled_candidate_files": "audits/prediction_model_runs/*/sportsman_permit_predictions_v1.csv",
            "current_production_status": "present_small_special_case_lane",
            "controlled_rebuild_status": "special_case_present_but_not_standalone_production_surface",
            "safe_promotion_candidate_later": "only_sportsman_lane_rows_after_source_and_random_only_validation",
            "must_remain_audit_only": "yes_until_sportsman_source_parity_is_verified",
            "runtime_merge_required": "yes",
            "evidence_summary": f"family_gaps={family_counts['SPORTSMAN_RANDOM_ONLY']}",
            "notes": "Sportsman rows should stay separate from point-probability ladders.",
        },
        {
            "lane": "YOUTH_REVIEW_REQUIRED / YOUTH_CONFIRMED_LANE",
            "purpose": "Youth rows must be classified from official source mechanics; they may become youth preference, youth bonus, youth random-only, or allocation-only.",
            "current_provider_files": "engine/utah_draw_predictive/youth.py; engine/utah_draw_predictive/classifier.py",
            "current_production_outputs": "processed_data/ml_draw_predictions_v1.csv; processed_data/draw_reality_engine_predictive_v2.csv",
            "controlled_candidate_files": "audits/prediction_model_runs/*/youth_draw_predictions_v1.csv",
            "current_production_status": "review_required",
            "controlled_rebuild_status": "incomplete_do_not_guess",
            "safe_promotion_candidate_later": "only_after_official_source_classifies_each_youth_family",
            "must_remain_audit_only": "yes",
            "runtime_merge_required": "yes",
            "evidence_summary": f"family_gaps={family_counts['YOUTH_REVIEW_REQUIRED']}",
            "notes": "Do not force youth rows into bonus or preference math until source mechanics prove the lane.",
        },
        {
            "lane": "ALLOCATION_OR_REFERENCE_ONLY",
            "purpose": "Conservation, Expo, private-land, permit overlays, guidebook/reference rows, boundary/allotment metadata.",
            "current_provider_files": "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv; processed_data/hunt_unit_reference_linked.csv; scripts/promote-2026-draw-permit-subset.py; scripts/sync_online_runtime_from_predictive.py",
            "current_production_outputs": "processed_data/point_ladder_view.csv; processed_data/hunt_research_2026.json; processed_data/hunt_research_2026_ladder.json; processed_data/ml_draw_predictions_v1.csv",
            "controlled_candidate_files": "not emitted as standalone model output",
            "current_production_status": "present_as_runtime_reference_layer",
            "controlled_rebuild_status": "missing_from_controlled_model_outputs_by_design",
            "safe_promotion_candidate_later": "no_direct_model_promotion; reference merge only",
            "must_remain_audit_only": "controlled_candidate_rows_yes",
            "runtime_merge_required": "yes",
            "evidence_summary": f"column_gaps={column_counts['ALLOCATION_OR_REFERENCE_ONLY']}; merge_gaps={merge_counts['ALLOCATION_OR_REFERENCE_ONLY']}",
            "notes": "These rows are not point-probability rows unless an official source proves otherwise.",
        },
        {
            "lane": "PUBLIC_RUNTIME_DISPLAY_METADATA",
            "purpose": "Display fields, lane labels, source lineage, validation notes, Hunt Research JSON merge fields.",
            "current_provider_files": "scripts/sync_online_runtime_from_predictive.py; scripts/build-hunt-research-2026-contract.py; scripts/rebuild-runtime-hunt-master-and-split.py",
            "current_production_outputs": "processed_data/hunt_research_2026.json; processed_data/hunt_research_2026_ladder.json; processed_data/hunt_research_2026_split/",
            "controlled_candidate_files": "not emitted by model folders",
            "current_production_status": "present_in_website_runtime",
            "controlled_rebuild_status": "missing_from_model_outputs_by_design",
            "safe_promotion_candidate_later": "no_direct_model_promotion; generated runtime contract only",
            "must_remain_audit_only": "candidate_model_outputs_yes",
            "runtime_merge_required": "yes",
            "evidence_summary": f"column_gaps={column_counts['PUBLIC_RUNTIME_DISPLAY_METADATA']}; merge_gaps={merge_counts['PUBLIC_RUNTIME_DISPLAY_METADATA']}",
            "notes": "Hunt Research JSON is a merged website surface, not a model-lane CSV.",
        },
        {
            "lane": "POINT_LADDER_DISPLAY",
            "purpose": "Compact public/runtime point ladder used by the website.",
            "current_provider_files": "processed_data/point_ladder_view.csv; scripts/build-unified-point-ladder-runtime.py; data_model/runtime_drafts/point_ladder_view_v3.csv",
            "current_production_outputs": "processed_data/point_ladder_view.csv",
            "controlled_candidate_files": "none",
            "current_production_status": "present_compact_runtime_ladder",
            "controlled_rebuild_status": "not_generated_by_controlled_model_outputs",
            "safe_promotion_candidate_later": "only compact ladder after grain/row-count parity",
            "must_remain_audit_only": "broader_91k_surface_must_not_replace_compact_ladder_blindly",
            "runtime_merge_required": "yes",
            "evidence_summary": "diagnosis marks point_ladder_view as ALLOCATION_OR_REFERENCE_ONLY runtime requirement",
            "notes": "Do not blindly replace compact `point_ladder_view.csv` with the broader 91k Hunt Research surface.",
        },
        {
            "lane": "HUNT_RESEARCH_JSON_MERGE",
            "purpose": "Large website JSON merge surface for research/display metadata and ladder presentation.",
            "current_provider_files": "scripts/build-hunt-research-2026-contract.py; scripts/rebuild-runtime-hunt-master-and-split.py; processed_data/hunt_research_2026_summary.json",
            "current_production_outputs": "processed_data/hunt_research_2026.json; processed_data/hunt_research_2026_ladder.json",
            "controlled_candidate_files": "none",
            "current_production_status": "present_in_runtime_files",
            "controlled_rebuild_status": "not_generated_by_model_outputs",
            "safe_promotion_candidate_later": "only after full runtime contract validation and R2 readiness",
            "must_remain_audit_only": "model_candidate_outputs_yes",
            "runtime_merge_required": "yes",
            "evidence_summary": "diagnosis shows both Hunt Research JSON files missing entirely from candidate runs",
            "notes": "The broader 91k lane/allocation metadata may belong here as display/research metadata, not as a replacement for compact point ladder.",
        },
    ]
    return lane_rows


def build_input_rows(root: Path) -> list[dict[str, Any]]:
    rows = [
        ("BONUS_ENGINE_OUTPUT", "engine/utah_bonus_predictive/materialize.py", "active builder: prediction math", "yes", "no", "code_provider", "Primary active materializer command: python -m engine.utah_bonus_predictive.materialize. Produces model outputs but not full runtime/display contract."),
        ("BONUS_ENGINE_OUTPUT", "data_truth/draw_results_truth/normalized/draw_results_long.csv", "historical draw truth", "yes", "no", "validated_normalized_truth", "Provides applicant/drawn/permit ladder history for bonus and preference model lanes."),
        ("BONUS_ENGINE_OUTPUT", "data_model/runtime_drafts/predictive_bonus_engine_2026.materialized.csv", "bonus materialized feeder", "yes", "no", "current_runtime_draft_dirty_in_worktree", "Upstream feeder for bonus materializer; do not replace from candidate output."),
        ("BONUS_ENGINE_OUTPUT", "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv", "current hunt/permit/allotment truth", "yes", "no", "protected_truth_source", "Used for current permit/allocation overlay; no edits in this plan."),
        ("PREFERENCE_ENGINE_OUTPUT", "processed_data/point_ladder_view.csv", "compact public preference/point ladder", "yes", "no", "current_runtime_reference", "Source/reference surface for point-rank display and preference review."),
        ("PREFERENCE_ENGINE_OUTPUT", "engine/utah_draw_predictive/preference_general_deer.py", "preference model logic", "yes", "no", "code_provider", "General-season deer preference lane."),
        ("PREFERENCE_ENGINE_OUTPUT", "engine/utah_draw_predictive/preference_antlerless.py", "preference model logic", "yes", "no", "code_provider", "Antlerless deer/elk and doe pronghorn preference lane."),
        ("PREFERENCE_ENGINE_OUTPUT", "engine/utah_draw_predictive/dedicated_hunter.py", "preference model logic", "yes", "no", "code_provider", "Dedicated hunter preference lane."),
        ("SPORTSMAN_RANDOM_ONLY", "data/utah/sportsman/sportsman_odds_2025.csv", "Sportsman odds source", "yes", "no", "source_required_if_present", "Special random-only lane source."),
        ("SPORTSMAN_RANDOM_ONLY", "engine/utah_draw_predictive/sportsman.py", "Sportsman model logic", "yes", "no", "code_provider", "Keeps Sportsman separated from bonus/preference ladders."),
        ("YOUTH_REVIEW_REQUIRED / YOUTH_CONFIRMED_LANE", "engine/utah_draw_predictive/youth.py", "youth lane routing logic", "yes", "no", "review_required", "Classify from source evidence before promotion."),
        ("ALLOCATION_OR_REFERENCE_ONLY", "processed_data/hunt_unit_reference_linked.csv", "reference and permit overlay", "yes", "no", "runtime_reference", "Reference rows and boundary/allocation support."),
        ("PUBLIC_RUNTIME_DISPLAY_METADATA", "scripts/sync_online_runtime_from_predictive.py", "runtime decoration merge", "yes", "no", "code_provider", "Decorates model rows for website/runtime fields."),
        ("POINT_LADDER_DISPLAY", "scripts/build-unified-point-ladder-runtime.py", "compact ladder builder", "yes", "no", "code_provider", "Builds compact point ladder; preserve compact grain."),
        ("HUNT_RESEARCH_JSON_MERGE", "scripts/build-hunt-research-2026-contract.py", "Hunt Research JSON contract builder", "yes", "no", "code_provider", "Builds large Hunt Research JSON surfaces."),
        ("HUNT_RESEARCH_JSON_MERGE", "scripts/rebuild-runtime-hunt-master-and-split.py", "R2/runtime split builder", "yes", "no", "code_provider", "Builds split/index runtime surfaces after contract validation."),
    ]
    return [
        {
            "lane": lane,
            "input_file": path,
            "role": role,
            "exists": exists(root, path),
            "required_for_production": required,
            "mutation_allowed": mutation,
            "source_status": status,
            "notes": notes,
        }
        for lane, path, role, required, mutation, status, notes in rows
    ]


def build_blocker_rows(family_rows: list[dict[str, str]], merge_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    blocker_id = 1
    for lane in [
        "BONUS_ENGINE_OUTPUT",
        "PREFERENCE_ENGINE_OUTPUT",
        "SPORTSMAN_RANDOM_ONLY",
        "YOUTH_REVIEW_REQUIRED",
        "ALLOCATION_OR_REFERENCE_ONLY",
        "PUBLIC_RUNTIME_DISPLAY_METADATA",
        "TRUE_MISSING_MODEL_OUTPUT",
    ]:
        lane_family_rows = rows_for_class(family_rows, lane)
        if not lane_family_rows:
            continue
        blockers.append(
            {
                "blocker_id": f"B{blocker_id:03d}",
                "lane": lane,
                "blocker_type": "missing_family_or_rows",
                "severity": "HIGH" if lane in {"PREFERENCE_ENGINE_OUTPUT", "TRUE_MISSING_MODEL_OUTPUT", "YOUTH_REVIEW_REQUIRED"} else "MEDIUM",
                "source_evidence_file": "diagnose_missing_families.csv",
                "affected_production_files": affected_files(lane_family_rows),
                "blocker": f"{len(lane_family_rows)} missing-family rows; {sum_int(lane_family_rows, 'missing_rows')} missing production rows in diagnosis.",
                "required_resolution": "Build/merge lane-specific outputs and prove row/family/schema parity before promotion.",
                "stop_condition": "Do not promote controlled candidate while this blocker remains.",
            }
        )
        blocker_id += 1

    for row in merge_rows:
        if row.get("promotion_blocker") != "YES":
            continue
        blockers.append(
            {
                "blocker_id": f"B{blocker_id:03d}",
                "lane": row.get("primary_classification", ""),
                "blocker_type": "runtime_merge_requirement",
                "severity": "HIGH",
                "source_evidence_file": "diagnose_runtime_merge_requirements.csv",
                "affected_production_files": row.get("production_file", ""),
                "blocker": row.get("merge_requirement", ""),
                "required_resolution": "Run full assembly into staging, then compare against current production before any promotion.",
                "stop_condition": "No direct promotion from model-lane folder.",
            }
        )
        blocker_id += 1
    return blockers


def command_sequence() -> list[str]:
    return [
        "python -m engine.utah_bonus_predictive.materialize --output-dir <staging_dir> --forecast-year 2026 --history-years 2025",
        "python scripts/sync_online_runtime_from_predictive.py",
        "python scripts/build-unified-point-ladder-runtime.py",
        "python scripts/build-hunt-research-2026-contract.py",
        "python scripts/rebuild-runtime-hunt-master-and-split.py",
        "python tools/prediction_accuracy_backtest/validate_and_run_prediction_models.py --root .",
        "python tools/prediction_accuracy_backtest/diagnose_production_equivalence.py --root .",
        "python tools/prediction_accuracy_backtest/build_production_assembly_plan.py --root .",
        "git diff --check",
        "python tools/git_size_guard.py --warn-only",
    ]


def write_markdown(path: Path, lane_rows: list[dict[str, Any]], input_rows: list[dict[str, Any]], blocker_rows: list[dict[str, Any]]) -> None:
    complete_lanes = [row["lane"] for row in lane_rows if row["current_production_status"].startswith("present")]
    incomplete_lanes = [row["lane"] for row in lane_rows if "incomplete" in row["controlled_rebuild_status"] or "missing" in row["controlled_rebuild_status"] or "not_generated" in row["controlled_rebuild_status"]]
    lines = [
        "# Production Prediction Assembly Plan",
        "",
        "## Scope",
        "This is a no-promotion assembly plan. It explains how the current production prediction/runtime files are assembled from separate model lanes and runtime merge layers.",
        "",
        "## Production Files Not Modified",
        "- `processed_data/ml_draw_predictions_v1.csv`",
        "- `processed_data/draw_reality_engine_predictive_v2.csv`",
        "- `processed_data/point_ladder_view.csv`",
        "- `processed_data/hunt_research_2026.json`",
        "- `processed_data/hunt_research_2026_ladder.json`",
        "- `data_model/runtime_drafts/predictive_bonus_engine_2026.materialized.csv`",
        "- `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv`",
        "- `data_truth/draw_results_truth/normalized/draw_results_long.csv`",
        "",
        "## Main Finding",
        "Current production is not a single model output. It is an assembled runtime product: bonus engine rows plus preference rows, Sportsman/random-only rows, youth-reviewed rows, allocation/reference overlays, compact point-ladder display, and Hunt Research JSON display metadata.",
        "",
        "## Lanes Already Present In Current Production",
    ]
    for lane in complete_lanes:
        lines.append(f"- `{lane}`")
    lines.extend(["", "## Lanes Missing Or Incomplete In Controlled Rebuilds"])
    for lane in incomplete_lanes:
        lines.append(f"- `{lane}`")
    lines.extend(
        [
            "",
            "## Runtime Decoration / Merge Required",
            "The following production files require runtime decoration or merge after model math:",
            "- `processed_data/ml_draw_predictions_v1.csv`: model lanes plus lineage, display, source, and demand/quality decorations.",
            "- `processed_data/draw_reality_engine_predictive_v2.csv`: modeled predictive rows plus runtime/reference decoration.",
            "- `processed_data/point_ladder_view.csv`: compact point ladder generated from draw truth/reference grain; not a direct model output.",
            "- `processed_data/hunt_research_2026.json`: website/research merge output.",
            "- `processed_data/hunt_research_2026_ladder.json`: website ladder/research merge output.",
            "",
            "## Active Builder Contributions",
            "These are the active production assembly builders to understand before touching runtime files. This plan documents them only; it does not execute the rebuild sequence.",
        ]
    )
    for builder in ACTIVE_BUILDERS:
        lines.extend(
            [
                f"- `{builder['script']}`",
                f"  - Sequence role: {builder['sequence_role']}.",
                f"  - Contributes: {builder['contributes']}.",
                f"  - Primary outputs: {builder['primary_outputs']}.",
                f"  - Lane ownership: {builder['lane_ownership']}.",
                f"  - Required inputs: {builder['required_inputs']}.",
                f"  - Blocker if missing: {builder['blocker_if_missing']}",
            ]
        )
    lines.extend(
        [
            "",
            "## Safe Candidates For Later Promotion",
            "- No full controlled folder is safe for direct promotion today.",
            "- Individual lane outputs may become promotion candidates only after a staging assembly proves row, family, schema, and runtime-display parity.",
            "- The 2027-from-2026 released candidate remains audit-only for production odds because it lacks scorable probability/applicant/drawn fields.",
            "",
            "## Must Remain Audit-Only",
            "- `audits/prediction_model_runs/2026_from_2025_truth_pdf_draw_results/` until full assembly parity passes.",
            "- `audits/prediction_model_runs/2027_from_2026_dwr_released_candidate/` for production odds.",
            "- Any broader 91k Hunt Research surface as a replacement for compact `point_ladder_view.csv`; it may belong in Hunt Research display metadata, not compact ladder replacement.",
            "",
            "## Exact Rebuild Sequence If Blockers Are Cleared",
            "Do not execute this sequence until blockers are cleared, staging paths are explicit, and production/runtime files are protected by a reviewed promotion gate.",
        ]
    )
    for index, command in enumerate(command_sequence(), start=1):
        lines.append(f"{index}. `{command}`")
    lines.extend(
        [
            "",
            "## Stop Conditions",
            "- Stop if any lane remains unclassified.",
            "- Stop if youth source mechanics are not proven.",
            "- Stop if staging output is missing production columns, families, or row coverage.",
            "- Stop if compact `point_ladder_view.csv` would be replaced by a broader research surface without grain proof.",
            "- Stop if any production file, `DATABASE.csv`, `draw_results_long.csv`, website/R2/manifest file, or large row-level output would be modified during planning.",
            "",
            "## Output Files",
            "- `production_assembly_lane_plan.csv`",
            "- `production_assembly_required_inputs.csv`",
            "- `production_assembly_blockers.csv`",
            "- `PRODUCTION_ASSEMBLY_PLAN.md`",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    out_dir = (root / args.out_dir).resolve()
    column_rows = read_csv(root / MISSING_COLUMNS)
    family_rows = read_csv(root / MISSING_FAMILIES)
    merge_rows = read_csv(root / RUNTIME_MERGE)

    lane_rows = build_lane_rows(root, column_rows, family_rows, merge_rows)
    input_rows = build_input_rows(root)
    blocker_rows = build_blocker_rows(family_rows, merge_rows)

    write_csv(out_dir / "production_assembly_lane_plan.csv", LANE_FIELDS, lane_rows)
    write_csv(out_dir / "production_assembly_required_inputs.csv", INPUT_FIELDS, input_rows)
    write_csv(out_dir / "production_assembly_blockers.csv", BLOCKER_FIELDS, blocker_rows)
    write_markdown(out_dir / "PRODUCTION_ASSEMBLY_PLAN.md", lane_rows, input_rows, blocker_rows)

    summary = {
        "lanes": len(lane_rows),
        "required_inputs": len(input_rows),
        "blockers": len(blocker_rows),
        "production_files_modified": False,
        "promotions_applied": 0,
        "command_sequence": command_sequence(),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
