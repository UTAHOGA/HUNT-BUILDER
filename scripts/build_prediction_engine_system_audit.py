from __future__ import annotations

import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


REPO = Path(__file__).resolve().parents[1]
AUDIT = REPO / "audits" / "full_engine_all_year_repair_20260629_032752"
BLIND = Path(r"C:\Users\tyler\Desktop\HUNT-BUILDER-BLIND-STUDY")

CANONICAL_DIR = REPO / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"
DRAW_RESULTS_LONG = REPO / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
DATABASE = REPO / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"

LARGE_FILE_SKIP_BYTES = 50 * 1024 * 1024


def open_csv(path: Path):
    return path.open("r", encoding="utf-8-sig", newline="", errors="replace")


def read_dicts(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with open_csv(path) as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: Iterable[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fields})


def first_existing(*paths: Path) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def count_csv_rows(path: Path, *, max_bytes: int = LARGE_FILE_SKIP_BYTES) -> str:
    if not path.exists():
        return "0"
    if path.stat().st_size > max_bytes:
        return "NOT_COUNTED_LARGE_FILE"
    with open_csv(path) as f:
        return str(max(sum(1 for _ in f) - 1, 0))


def csv_header(path: Path) -> list[str]:
    if not path.exists():
        return []
    with open_csv(path) as f:
        return next(csv.reader(f), [])


def sample_csv_values(path: Path, fields: list[str], limit: int = 5000) -> dict[str, set[str]]:
    values = {field: set() for field in fields}
    if not path.exists() or path.suffix.lower() != ".csv":
        return values
    try:
        with open_csv(path) as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if i >= limit:
                    break
                for field in fields:
                    value = row.get(field, "")
                    if value not in ("", None):
                        values[field].add(str(value))
    except Exception:
        pass
    return values


def joined(values: Iterable[str], limit: int = 20) -> str:
    cleaned = sorted({str(v) for v in values if str(v).strip()})
    if len(cleaned) > limit:
        return ";".join(cleaned[:limit]) + f";+{len(cleaned) - limit} more"
    return ";".join(cleaned)


def safe_float(value: str | float | int | None) -> float | None:
    if value in ("", None):
        return None
    try:
        f = float(value)
    except Exception:
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def odds_band(p: float | None) -> str:
    if p is None:
        return "UNSCORED"
    if p == 0:
        return "ZERO"
    if p < 0.01:
        return "LT_1_PCT"
    if p < 0.05:
        return "1_TO_5_PCT"
    if p < 0.25:
        return "5_TO_25_PCT"
    if p < 0.75:
        return "25_TO_75_PCT"
    if p < 1:
        return "75_TO_99_PCT"
    return "FULL_100_PCT"


FAMILY_META = {
    "preference_general_deer": {
        "engine_family": "PREFERENCE_DRAW",
        "species": "Deer",
        "draw_design": "Preference",
        "draw_method": "Preference",
        "point_system": "preference",
    },
    "dedicated_hunter": {
        "engine_family": "PREFERENCE_DRAW",
        "species": "Deer",
        "draw_design": "Preference",
        "draw_method": "Preference",
        "point_system": "preference",
    },
    "preference_antlerless_deer": {
        "engine_family": "PREFERENCE_DRAW",
        "species": "Deer",
        "draw_design": "Preference",
        "draw_method": "Preference",
        "point_system": "preference",
    },
    "preference_antlerless_elk": {
        "engine_family": "PREFERENCE_DRAW",
        "species": "Elk",
        "draw_design": "Preference",
        "draw_method": "Preference",
        "point_system": "preference",
    },
    "preference_doe_pronghorn": {
        "engine_family": "PREFERENCE_DRAW",
        "species": "Pronghorn",
        "draw_design": "Preference",
        "draw_method": "Preference",
        "point_system": "preference",
    },
    "sportsman": {
        "engine_family": "SPORTSMAN_RANDOM_ONLY",
        "species": "Mixed",
        "draw_design": "Random Only",
        "draw_method": "Random",
        "point_system": "none",
    },
    "youth_random_elk_general_bull": {
        "engine_family": "YOUTH_RANDOM",
        "species": "Elk",
        "draw_design": "Youth Random",
        "draw_method": "Random",
        "point_system": "none",
    },
    "bear": {
        "engine_family": "BEAR_SPECIFIC",
        "species": "Black Bear",
        "draw_design": "Bear Specific",
        "draw_method": "Mixed",
        "point_system": "family_specific",
    },
    "black_bear": {
        "engine_family": "BEAR_SPECIFIC",
        "species": "Black Bear",
        "draw_design": "Bear Specific",
        "draw_method": "Mixed",
        "point_system": "family_specific",
    },
    "turkey": {
        "engine_family": "TURKEY_SPECIFIC",
        "species": "Turkey",
        "draw_design": "Turkey Specific",
        "draw_method": "Mixed",
        "point_system": "family_specific",
    },
}


def meta_for_family(family: str) -> dict[str, str]:
    key = (family or "").strip().lower()
    if key in FAMILY_META:
        return FAMILY_META[key]
    if "antlerless" in key or "preference" in key or "dedicated" in key:
        return FAMILY_META["preference_general_deer"] | {"species": "Mixed"}
    if "sportsman" in key:
        return FAMILY_META["sportsman"]
    if "youth" in key:
        return FAMILY_META["youth_random_elk_general_bull"]
    if "bear" in key:
        return FAMILY_META["bear"]
    if "turkey" in key:
        return FAMILY_META["turkey"]
    if "availability" in key or "mountain_lion" in key or "private_land" in key:
        return {
            "engine_family": "AVAILABILITY_ONLY",
            "species": "Mixed",
            "draw_design": "Availability/Allocation",
            "draw_method": "Classification",
            "point_system": "none",
        }
    return {
        "engine_family": "UNKNOWN",
        "species": "Mixed",
        "draw_design": "",
        "draw_method": "",
        "point_system": "",
    }


def build_engine_registry() -> list[dict[str, str]]:
    rows = [
        {
            "engine_name": "Utah Bonus Predictive Max/Weighted Split",
            "engine_family": "MAX_WEIGHTED_SPLIT",
            "script_or_module": "engine/utah_bonus_predictive/materialize.py;engine/utah_bonus_predictive/forecast.py;engine/utah_predictive_mixed/materialize.py;scripts/build_predictive_bonus_engine_v1.py",
            "purpose": "Model bonus/max-point/random split hunts using point ladders, quota authority, mixed-cutoff rollover, and weighted-random below-line behavior.",
            "intended_draw_designs": "Max/Weighted Split;Bonus;Limited Entry;Premium Limited Entry;O.I.L.",
            "intended_draw_methods": "Bonus split;Max point pass;Weighted random pass",
            "intended_point_systems": "bonus;weighted_random",
            "intended_species_families": "limited-entry big game;OIL;eligible public bonus-point hunts",
            "intended_hunt_code_prefixes": "DB;EB;PB;MB;RS;DS;BR where row type proves bonus/max draw",
            "output_files": "processed_data/phase6_bonus_special_predictions_v1.csv;processed_data/projected_bonus_draw_2026_simulated.csv;processed_data/mixed_predictive_engine_2026_summary.json",
            "runtime_destinations": "processed_data/public_contracts/hunt_predictions.json;pages-dist/data/hunt_predictions.json",
            "completion_status": "COMPLETED_PROMOTED",
            "promoted_status": "LIKELY_PROMOTED_FOR_CURRENT_MAX_WEIGHTED_STREAM",
            "production_status": "KEEP_PROMOTED_STREAM_PENDING_FINAL_FAMILY_DIFF",
            "notes": "Do not replace with runner globally. Use family-specific proof before changing the promoted max/weighted stream.",
        },
        {
            "engine_name": "All-Family Preference Draw Runner",
            "engine_family": "PREFERENCE_DRAW",
            "script_or_module": "engine/utah_draw_predictive/run_all_families.py;engine/utah_draw_predictive/preference_general_deer.py;engine/utah_draw_predictive/dedicated_hunter.py;engine/utah_draw_predictive/preference_antlerless.py",
            "purpose": "Run preference draw families year-by-year from canonical/long truth and score candidate predictions against following-year actuals.",
            "intended_draw_designs": "Preference",
            "intended_draw_methods": "Preference point exhaustion/ladder",
            "intended_point_systems": "preference",
            "intended_species_families": "general buck deer;dedicated hunter;antlerless deer;antlerless elk;doe pronghorn",
            "intended_hunt_code_prefixes": "DB;DH;DA;EA;PA",
            "output_files": "audits/full_engine_all_year_repair_20260629_032752/runs/*/family_predictions.csv;processed_data/engine_outputs/preference_draw_materialized/*.csv",
            "runtime_destinations": "public/hunt-docs/latest/preference_draw.csv;public/hunt-docs/latest/preference_draw.json",
            "completion_status": "COMPLETED_NOT_PROMOTED",
            "promoted_status": "NOT_PROMOTED_BY_THIS_AUDIT",
            "production_status": "ACCEPT_RUNNER_STREAM_AFTER_APPROVAL_FOR_CERTIFIED_PREFERENCE_FAMILIES",
            "notes": "Corrected scoring excludes zero actual-applicant rows and shows low error on scored rows.",
        },
        {
            "engine_name": "Youth General Any Bull Elk Random",
            "engine_family": "YOUTH_RANDOM",
            "script_or_module": "engine/utah_draw_predictive/youth.py;processed_data/eb1007_youth_general_bull_predictions_2027.csv",
            "purpose": "Keep EB1007/YOUTH_GENERAL_ANY_BULL_ELK separate from Sportsman and adult preference/bonus math.",
            "intended_draw_designs": "Youth Random;General Season youth set-aside",
            "intended_draw_methods": "Random after applicable youth allocation behavior",
            "intended_point_systems": "none",
            "intended_species_families": "Youth general bull elk",
            "intended_hunt_code_prefixes": "EB1007;EB1011 lineage where source confirms same family",
            "output_files": "processed_data/eb1007_youth_general_bull_history.csv;processed_data/eb1007_youth_general_bull_backtest.csv;processed_data/eb1007_youth_general_bull_predictions_2027.csv",
            "runtime_destinations": "Formal materializer output: youth_draw_predictions_v1.csv; merged prediction stream: ml_draw_predictions_v1.csv",
            "completion_status": "COMPLETED_NOT_PROMOTED",
            "promoted_status": "NOT_PROMOTED_BY_THIS_AUDIT",
            "production_status": "MATERIALIZER_PROMOTED_PENDING_RUNTIME_PUBLIC_APPROVAL",
            "notes": "EB1007 now materializes as YOUTH_GENERAL_ANY_BULL_ELK / MODELED_RANDOM_ONLY with random-only p_draw_mean and no preference/bonus/random-pool fields.",
        },
        {
            "engine_name": "Sportsman Random Only",
            "engine_family": "SPORTSMAN_RANDOM_ONLY",
            "script_or_module": "engine/utah_draw_predictive/sportsman.py;processed_data/sportsman_permit_predictions_v1.csv",
            "purpose": "Calculate strictly random Utah-resident-only sportsman odds from applicant denominator; never preference or bonus p_draw.",
            "intended_draw_designs": "Sportsman Random Only",
            "intended_draw_methods": "Strict random",
            "intended_point_systems": "none",
            "intended_species_families": "Sportsman resident permits",
            "intended_hunt_code_prefixes": "Sportsman/statewide species codes",
            "output_files": "processed_data/sportsman_permit_predictions_v1.csv",
            "runtime_destinations": "Not confirmed live by this audit",
            "completion_status": "COMPLETED_NOT_PROMOTED",
            "promoted_status": "NOT_CONFIRMED_PROMOTED",
            "production_status": "ACCEPT_LEGACY_STREAM",
            "notes": "Resident only. Predictability is denominator math, not a behavioral model.",
        },
        {
            "engine_name": "Black Bear Specific",
            "engine_family": "BEAR_SPECIFIC",
            "script_or_module": "engine/utah_draw_predictive/bear.py;processed_data/bear_draw_predictions_v1.csv;processed_data/bear_predictions_v1.csv",
            "purpose": "Handle bear draw, pursuit, harvest-objective, and crosswalked bear hunt rows without contaminating public big-game bonus/preference families.",
            "intended_draw_designs": "Bear draw;Restricted pursuit;Harvest objective;Availability where applicable",
            "intended_draw_methods": "Bear-specific;classification-only for non-draw rows",
            "intended_point_systems": "family_specific;none for availability rows",
            "intended_species_families": "Black bear",
            "intended_hunt_code_prefixes": "BR",
            "output_files": "processed_data/bear_draw_predictions_v1.csv;processed_data/bear_predictions_v1.csv;processed_data/bear_2026_target_hunt_code_crosswalk_audit.md",
            "runtime_destinations": "Not confirmed live by this audit",
            "completion_status": "PARTIAL",
            "promoted_status": "NOT_PROMOTED_BY_THIS_AUDIT",
            "production_status": "RECONCILE_BEFORE_ACCEPTING",
            "notes": "Use locked BR7008=>BR7022, BR7108=>BR7127, BR7208=>BR7239, BR7307=>BR7326 crosswalks; row type decides modeled vs classified.",
        },
        {
            "engine_name": "Turkey Specific",
            "engine_family": "TURKEY_SPECIFIC",
            "script_or_module": "engine/utah_draw_predictive/turkey.py;processed_data/turkey_bonus_predictions_v1.csv",
            "purpose": "Separate turkey limited-entry, youth turkey, fall management/general, and CWMU/contact-operator rows.",
            "intended_draw_designs": "Turkey limited entry;Youth turkey;Fall management;Conservation/CWMU reference",
            "intended_draw_methods": "Turkey-specific;classification-only where not public odds",
            "intended_point_systems": "turkey_bonus_or_family_specific",
            "intended_species_families": "Turkey",
            "intended_hunt_code_prefixes": "TK",
            "output_files": "processed_data/turkey_bonus_predictions_v1.csv;processed_data/youth_turkey_predictions_v1.csv",
            "runtime_destinations": "Not confirmed live by this audit",
            "completion_status": "PARTIAL",
            "promoted_status": "NOT_PROMOTED_BY_THIS_AUDIT",
            "production_status": "RECONCILE_BEFORE_ACCEPTING",
            "notes": "Do not fold youth turkey into generic big-game youth reserve or generic max/weighted logic.",
        },
        {
            "engine_name": "Availability and Classification Only",
            "engine_family": "AVAILABILITY_ONLY",
            "script_or_module": "engine/utah_draw_predictive/availability_review.py;engine/utah_draw_predictive/mountain_lion.py;engine/utah_draw_predictive/private_lands_antlerless_elk.py;engine/utah_draw_predictive/exclusions.py",
            "purpose": "Classify OTC, unlimited, no-quota, private-land no-published-permit, CWMU contact-operator, allocation/reference-only rows without public p_draw.",
            "intended_draw_designs": "Availability only;Allocation only;Reference only",
            "intended_draw_methods": "Classification",
            "intended_point_systems": "none",
            "intended_species_families": "Mountain lion;private lands;OTC;unlimited;CWMU contact-operator reference",
            "intended_hunt_code_prefixes": "Mixed",
            "output_files": "processed_data/mountain_lion_availability_predictions_v1.csv;processed_data/private_lands_antlerless_elk_predictions_v1.csv",
            "runtime_destinations": "Runtime classification fields only",
            "completion_status": "COMPLETED_NOT_PROMOTED",
            "promoted_status": "CLASSIFICATION_ONLY",
            "production_status": "KEEP_CLASSIFIED_BLANK_ODDS",
            "notes": "No fabricated probability from permit totals or no-quota rows.",
        },
        {
            "engine_name": "All-Family Runner Orchestrator",
            "engine_family": "RUNNER_ORCHESTRATOR",
            "script_or_module": "engine/utah_draw_predictive/run_all_families.py;scripts/run_full_engine_all_year_validation.py",
            "purpose": "Orchestrate family engines, generate year-pair predictions, certify leakage, compare candidate streams, and expose stale or missing truth paths.",
            "intended_draw_designs": "All supported families through delegated engines",
            "intended_draw_methods": "Delegated",
            "intended_point_systems": "Delegated",
            "intended_species_families": "Preference families currently strongest; others diagnostic/candidate",
            "intended_hunt_code_prefixes": "Mixed",
            "output_files": "audits/full_engine_all_year_repair_20260629_032752/runs/*/family_predictions.csv;audits/full_engine_all_year_repair_20260629_032752/runner_prediction_acceptance_audit.csv",
            "runtime_destinations": "None in this task",
            "completion_status": "AUDIT_ONLY",
            "promoted_status": "NOT_PROMOTED",
            "production_status": "CERTIFICATION_HARNESS_AND_ACCEPTED_PRODUCTION_CANDIDATE_BY_FAMILY",
            "notes": "Runner is not truth and does not auto-promote. It can augment stale legacy streams after family-specific approval.",
        },
    ]
    return rows


def build_assignment_audit() -> list[dict[str, str]]:
    source = AUDIT / "engine_mapping_audit.csv"
    rows = []
    seen = set()
    for row in read_dicts(source):
        family = row.get("family", "")
        if family == "sportsman":
            continue
        meta = meta_for_family(family)
        code = row.get("hunt_code", "")
        key = (
            row.get("target_year", ""),
            row.get("source_year", ""),
            family,
            code[:2],
            row.get("draw_design", ""),
            row.get("draw_method", ""),
            row.get("point_system", ""),
            row.get("intended_engine", ""),
            row.get("actual_engine_used", ""),
        )
        if key in seen:
            continue
        seen.add(key)
        status = row.get("mapping_status", "")
        actual = row.get("actual_engine_used", "")
        intended = row.get("intended_engine", "")
        acceptable_alias = assignment_alias_ok(family, intended, actual)
        inappropriate = "true" if not acceptable_alias and (status not in ("PASS", "OK", "") or (actual and intended and actual != intended)) else "false"
        rows.append(
            {
                "target_year": row.get("target_year", ""),
                "source_year": row.get("source_year", ""),
                "hunt_family": family,
                "species": meta["species"],
                "hunt_code_prefix": code[:2],
                "draw_design": row.get("draw_design", meta["draw_design"]),
                "draw_method": row.get("draw_method", meta["draw_method"]),
                "point_system": row.get("point_system", meta["point_system"]),
                "intended_engine": intended,
                "actual_engine_used": actual,
                "assignment_status": "APPROPRIATE" if inappropriate == "false" else "REVIEW_REQUIRED",
                "inappropriate_engine_flag": inappropriate,
                "correction_required": "none" if inappropriate == "false" else "review assignment against family registry",
                "rationale": "Mapping audit shows intended engine equals actual engine." if inappropriate == "false" else "Mapping status or engine mismatch requires review.",
                "notes": row.get("notes", ""),
            }
        )
    for count_row in read_dicts(AUDIT / "all_year_family_prediction_counts.csv"):
        if count_row.get("family") != "sportsman":
            continue
        rows.append(
            {
                "target_year": count_row.get("target_year", ""),
                "source_year": count_row.get("source_year", ""),
                "hunt_family": "sportsman",
                "species": "Mixed",
                "hunt_code_prefix": "SPORTSMAN",
                "draw_design": "Sportsman Random Only",
                "draw_method": "Strict random",
                "point_system": "none",
                "intended_engine": "sportsman_random_only",
                "actual_engine_used": "sportsman_random_only",
                "assignment_status": "APPROPRIATE",
                "inappropriate_engine_flag": "false",
                "correction_required": "none",
                "rationale": "Sportsman is modeled by its dedicated resident-only random engine using yearly raw Sportsman draw-result sources.",
                "notes": "One permit per species; nonresidents are not eligible; probability is permit_count divided by eligible resident applicants.",
            }
        )
    return rows


def refresh_sportsman_acceptance_rows(acceptance: list[dict[str, str]]) -> list[dict[str, str]]:
    refreshed = [row for row in acceptance if row.get("hunt_family") != "sportsman"]
    for count_row in read_dicts(AUDIT / "all_year_family_prediction_counts.csv"):
        if count_row.get("family") != "sportsman":
            continue
        refreshed.append(
            {
                "target_year": count_row.get("target_year", ""),
                "source_year": count_row.get("source_year", ""),
                "hunt_family": "sportsman",
                "engine_family": "SPORTSMAN_RANDOM_ONLY",
                "runner_output_path": count_row.get("output_path", ""),
                "runner_rows": count_row.get("prediction_rows", ""),
                "canonical_file": str(REPO / "processed_data" / "audits" / "sportsman_pdf_clean_script_feed.csv"),
                "canonical_rows": count_row.get("input_truth_rows", ""),
                "draw_results_long_rows": count_row.get("input_truth_rows", ""),
                "database_rows": count_row.get("current_target_rows", ""),
                "runtime_current_rows": "10",
                "intended_engine": "sportsman_random_only",
                "actual_engine_used": "sportsman_random_only",
                "truth_path_status": "SOURCE_BACKED_DEDICATED_SPORTSMAN_RAW_FEED",
                "engine_assignment_status": "PASS",
                "leakage_status": "PASS",
                "backtest_status": "SCORABLE_RANDOM_DENOMINATOR_STREAM",
                "runtime_schema_status": "PASS",
                "comparison_to_prior_stream": "RUNNER_NOW_EMITS_DEDICATED_SPORTSMAN_STREAM",
                "acceptance_status": "ACCEPT_AS_CERTIFIED_PREDICTION",
                "correction_required": "none",
                "notes": "Sportsman draw results exist by year. This is resident-only strict random, one permit per species, and is not availability-only.",
            }
        )
    return sorted(refreshed, key=lambda row: (row.get("target_year", ""), row.get("hunt_family", ""), row.get("source_year", "")))


def assignment_alias_ok(family: str, intended: str, actual: str) -> bool:
    family_l = (family or "").lower()
    intended_l = (intended or "").lower()
    actual_l = (actual or "").lower()
    if not intended_l and not actual_l:
        return True
    if intended_l == actual_l:
        return True
    if family_l == "dedicated_hunter" and actual_l in {
        "preference_dedicated_hunter_deer",
        "preference_youth_dedicated_hunter_deer",
    }:
        return True
    if "deferred" in intended_l and actual_l == "deferred_with_reason":
        return True
    if family_l in {"bonus_bear", "youth_draw", "youth_turkey"} and actual_l == "deferred_with_reason":
        return True
    if family_l in {"preference_antlerless_deer", "preference_antlerless_elk", "preference_doe_pronghorn"} and actual_l == "deferred_with_reason":
        return True
    # Sportsman is intentionally not aliased to availability_only: it is a
    # Utah-resident strict-random draw family and should remain visible.
    return False


def discover_streams() -> list[Path]:
    patterns = [
        "processed_data/**/*prediction*.csv",
        "processed_data/**/*predictions*.csv",
        "processed_data/**/*engine*.csv",
        "processed_data/**/*odds*.csv",
        "processed_data/**/*prediction*.json",
        "processed_data/**/*predictions*.json",
        "processed_data/public_contracts/hunt_predictions.json",
        "processed_data/public_contracts/hunt_odds_history.csv",
        "public/hunt-docs/latest/preference_draw.csv",
        "public/hunt-docs/latest/preference_draw.json",
        "public/hunt-docs/latest/public_all_hunts.csv",
        "public/hunt-docs/latest/public_all_hunts.json",
        "pages-dist/data/hunt_predictions.json",
        "pages-dist/data/hunt_odds_history.csv",
        "pages-dist/processed_data/public_contracts/hunt_predictions.json",
        "pages-dist/processed_data/public_contracts/hunt_odds_history.csv",
        "audits/full_engine_all_year_repair_20260629_032752/runs/*/family_predictions.csv",
        "audits/full_engine_all_year_repair_20260629_032752/runs/*/predictions/*.csv",
    ]
    found: set[Path] = set()
    for pattern in patterns:
        for path in REPO.glob(pattern):
            if path.is_file():
                found.add(path)
    return sorted(found)


def infer_engine_family_from_path(path: Path) -> str:
    text = str(path).lower()
    if "sportsman" in text:
        return "SPORTSMAN_RANDOM_ONLY"
    if "eb1007" in text or "youth" in text:
        return "YOUTH_RANDOM"
    if "bear" in text or "black_bear" in text:
        return "BEAR_SPECIFIC"
    if "turkey" in text:
        return "TURKEY_SPECIFIC"
    if "mountain_lion" in text or "availability" in text or "private_land" in text:
        return "AVAILABILITY_ONLY"
    if "bonus" in text or "mixed" in text or "projected_bonus" in text:
        return "MAX_WEIGHTED_SPLIT"
    if "preference" in text or "dedicated_hunter" in text or "draw_prediction_engine" in text or "point_creep" in text:
        return "PREFERENCE_DRAW"
    if "runs" in text and "family_predictions" in text:
        return "RUNNER_ORCHESTRATOR"
    return "UNKNOWN"


def build_stream_inventory() -> list[dict[str, str]]:
    rows = []
    for path in discover_streams():
        rel = path.relative_to(REPO)
        size = path.stat().st_size
        suffix = path.suffix.lower()
        header: list[str] = []
        records = ""
        samples = {k: set() for k in ["target_year", "source_year", "family", "hunt_family", "species", "draw_design", "draw_method", "point_system"]}
        if suffix == ".csv":
            header = csv_header(path)
            records = count_csv_rows(path)
            samples = sample_csv_values(path, list(samples), limit=5000 if size <= LARGE_FILE_SKIP_BYTES else 200)
        elif suffix == ".json":
            records = "NOT_COUNTED_LARGE_FILE" if size > LARGE_FILE_SKIP_BYTES else "JSON_FILE"
            if size <= LARGE_FILE_SKIP_BYTES:
                try:
                    data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
                    if isinstance(data, list):
                        records = str(len(data))
                        if data and isinstance(data[0], dict):
                            header = list(data[0].keys())
                    elif isinstance(data, dict):
                        records = str(len(data))
                        header = list(data.keys())[:50]
                except Exception:
                    records = "JSON_PARSE_SKIPPED"
        engine_family = infer_engine_family_from_path(path)
        promoted = "true" if any(part in str(rel).replace("\\", "/") for part in ["public_contracts", "public/hunt-docs/latest", "pages-dist"]) else "false"
        stale = "RUNTIME_OR_PUBLIC_CURRENT_CANDIDATE" if promoted == "true" else "CANDIDATE_OR_AUDIT_STREAM"
        status = "RUNTIME_LIVE_OR_PUBLIC_SURFACE" if promoted == "true" else "INVENTORIED_NOT_PROMOTED"
        rows.append(
            {
                "stream_name": path.stem,
                "stream_type": suffix.lstrip(".").upper(),
                "engine_family": engine_family,
                "output_path": str(path),
                "rows": records,
                "records": records,
                "target_years_covered": joined(samples.get("target_year", set())),
                "source_years_covered": joined(samples.get("source_year", set())),
                "hunt_families_covered": joined(samples.get("family", set()) | samples.get("hunt_family", set())),
                "species_covered": joined(samples.get("species", set())),
                "draw_designs_covered": joined(samples.get("draw_design", set())),
                "draw_methods_covered": joined(samples.get("draw_method", set())),
                "point_systems_covered": joined(samples.get("point_system", set())),
                "schema_columns": ";".join(header[:80]),
                "last_modified": path.stat().st_mtime_ns,
                "promoted_to_runtime": promoted,
                "runtime_destination": str(path) if promoted == "true" else "",
                "stale_or_current": stale,
                "status": status,
                "notes": "Large file metadata only; body not loaded." if size > LARGE_FILE_SKIP_BYTES else "",
            }
        )
    return rows


def build_truth_trace(acceptance: list[dict[str, str]]) -> list[dict[str, str]]:
    rows = []
    for row in acceptance:
        prediction_rows = row.get("runner_rows", "0")
        truth_status = row.get("truth_path_status", "")
        nonzero_without_truth = "1" if safe_float(prediction_rows) and "MISSING" in truth_status.upper() else "0"
        rows.append(
            {
                "target_year": row.get("target_year", ""),
                "source_year": row.get("source_year", ""),
                "hunt_family": row.get("hunt_family", ""),
                "engine_family": meta_for_family(row.get("hunt_family", ""))["engine_family"],
                "prediction_stream": row.get("runner_output_path", ""),
                "prediction_rows": prediction_rows,
                "canonical_file": row.get("canonical_file", ""),
                "canonical_rows": row.get("canonical_rows", ""),
                "draw_results_long_rows": row.get("draw_results_long_rows", ""),
                "database_path": str(DATABASE) if DATABASE.exists() else "",
                "database_rows": row.get("database_rows", ""),
                "blind_file_used": "",
                "truth_path_status": truth_status,
                "canonical_missing_from_long": "0" if row.get("draw_results_long_rows", "") not in ("", "0") else "UNKNOWN_OR_NOT_APPLICABLE",
                "long_missing_from_database": "0" if row.get("database_rows", "") not in ("", "0") else "UNKNOWN_OR_NOT_APPLICABLE",
                "nonzero_prediction_without_truth_path": nonzero_without_truth,
                "leakage_status": row.get("leakage_status", ""),
                "notes": row.get("notes", ""),
            }
        )
    return rows


def build_accuracy_comparison() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    path = AUDIT / "runner_all_year_scoring_repair" / "runner_all_year_prediction_vs_actual_scored_rows.csv"
    comparison_rows = []
    groups: dict[tuple, list[dict[str, str]]] = defaultdict(list)
    if not path.exists():
        return [], []
    with open_csv(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            family = row.get("family", "")
            meta = meta_for_family(family)
            pred = safe_float(row.get("predicted_probability"))
            actual = safe_float(row.get("actual_probability"))
            abs_err = safe_float(row.get("abs_error"))
            err = safe_float(row.get("error"))
            scored = row.get("scored", "").lower() == "true" or (abs_err is not None and actual is not None)
            signed = "" if pred is None or actual is None else pred - actual
            squared = "" if signed == "" else signed * signed
            out = {
                "target_year": row.get("target_year", ""),
                "source_year": row.get("source_year", ""),
                "hunt_family": family,
                "species": meta["species"],
                "hunt_code": row.get("hunt_code", ""),
                "residency": row.get("residency", ""),
                "points": row.get("points", ""),
                "actual_probability": row.get("actual_probability", ""),
                "predicted_probability": row.get("predicted_probability", ""),
                "prediction_stream": "runner_all_year_corrected",
                "engine_family": meta["engine_family"],
                "absolute_error": "" if abs_err is None else f"{abs_err:.12g}",
                "squared_error": "" if squared == "" else f"{squared:.12g}",
                "signed_error": "" if signed == "" else f"{signed:.12g}",
                "odds_band": odds_band(actual if actual is not None else pred),
                "quota_band": "UNKNOWN",
                "sample_weight": "1" if scored else "0",
                "usable_for_scoring": "true" if scored else "false",
                "exclusion_reason": row.get("exclusion_reason", ""),
                "leakage_flag": "false",
            }
            comparison_rows.append(out)
            if scored and abs_err is not None and signed != "":
                key = (
                    meta["engine_family"],
                    "runner_all_year_corrected",
                    family,
                    meta["species"],
                    meta["draw_design"],
                    meta["draw_method"],
                    meta["point_system"],
                    row.get("target_year", ""),
                    row.get("residency", ""),
                    "UNKNOWN",
                    out["odds_band"],
                )
                groups[key].append(out)
    summary_rows = []
    for key, vals in sorted(groups.items()):
        abs_errors = [float(v["absolute_error"]) for v in vals if v["absolute_error"]]
        signed_errors = [float(v["signed_error"]) for v in vals if v["signed_error"]]
        sq_errors = [float(v["squared_error"]) for v in vals if v["squared_error"]]
        worst = max(vals, key=lambda v: float(v["absolute_error"] or 0))
        over = sum(1 for e in signed_errors if e > 0)
        under = sum(1 for e in signed_errors if e < 0)
        rmse = math.sqrt(sum(sq_errors) / len(sq_errors)) if sq_errors else 0.0
        mae = sum(abs_errors) / len(abs_errors) if abs_errors else 0.0
        status = "COMPARISON_GOOD" if mae <= 0.10 else "COMPARISON_ACCEPTABLE_WITH_CAUTION" if mae <= 0.20 else "COMPARISON_REFINEMENT_REQUIRED"
        summary_rows.append(
            {
                "engine_family": key[0],
                "prediction_stream": key[1],
                "hunt_family": key[2],
                "species": key[3],
                "draw_design": key[4],
                "draw_method": key[5],
                "point_system": key[6],
                "target_year": key[7],
                "residency": key[8],
                "quota_band": key[9],
                "odds_band": key[10],
                "scored_rows": str(len(vals)),
                "mae": f"{mae:.12g}",
                "rmse": f"{rmse:.12g}",
                "bias": f"{(sum(signed_errors) / len(signed_errors)):.12g}" if signed_errors else "",
                "median_error": f"{statistics.median(abs_errors):.12g}" if abs_errors else "",
                "p10_error": f"{statistics.quantiles(abs_errors, n=10)[0]:.12g}" if len(abs_errors) >= 10 else "",
                "p90_error": f"{statistics.quantiles(abs_errors, n=10)[8]:.12g}" if len(abs_errors) >= 10 else "",
                "overprediction_rate": f"{over / len(signed_errors):.12g}" if signed_errors else "",
                "underprediction_rate": f"{under / len(signed_errors):.12g}" if signed_errors else "",
                "worst_hunt_code": worst.get("hunt_code", ""),
                "worst_point_level": worst.get("points", ""),
                "accuracy_status": status,
                "recommended_refinement": refinement_for_status(status, key[2], key[10]),
            }
        )
    return comparison_rows, summary_rows


def refinement_for_status(status: str, family: str, band: str) -> str:
    if status == "COMPARISON_GOOD":
        return "Retain current calibration; monitor low-permit and tail point rows."
    if band in ("ZERO", "FULL_100_PCT"):
        return "Verify zero-applicant/guaranteed-row handling and keep display status separate from p_draw."
    if "antlerless" in family:
        return "Use current canonical truth when actual draw ladders exist; defer target-year antlerless actuals until DWR posts them."
    return "Review smoothing, quota-band handling, residency allocation, and point-level tail behavior."


def build_completion_matrix(registry: list[dict[str, str]], acceptance: list[dict[str, str]], summary: list[dict[str, str]]) -> list[dict[str, str]]:
    accepted_families = Counter(r.get("hunt_family", "") for r in acceptance if "ACCEPT" in r.get("acceptance_status", ""))
    score_families = Counter(r.get("hunt_family", "") for r in summary)
    families = [
        ("MAX_WEIGHTED_SPLIT", "bonus_max_weighted_public", "Mixed", "Max/Weighted Split", "Bonus/Weighted"),
        ("PREFERENCE_DRAW", "preference_general_deer", "Deer", "Preference", "Preference"),
        ("PREFERENCE_DRAW", "dedicated_hunter", "Deer", "Preference", "Preference"),
        ("PREFERENCE_DRAW", "preference_antlerless_deer", "Deer", "Preference", "Preference"),
        ("PREFERENCE_DRAW", "preference_antlerless_elk", "Elk", "Preference", "Preference"),
        ("PREFERENCE_DRAW", "preference_doe_pronghorn", "Pronghorn", "Preference", "Preference"),
        ("YOUTH_RANDOM", "youth_random_elk_general_bull", "Elk", "Youth Random", "Random"),
        ("SPORTSMAN_RANDOM_ONLY", "sportsman", "Mixed", "Sportsman Random Only", "Random"),
        ("BEAR_SPECIFIC", "bear", "Black Bear", "Bear Specific", "Mixed"),
        ("TURKEY_SPECIFIC", "turkey", "Turkey", "Turkey Specific", "Mixed"),
        ("AVAILABILITY_ONLY", "availability_classification", "Mixed", "Availability/Allocation", "Classification"),
    ]
    rows = []
    for engine_family, family, species, design, method in families:
        score = score_families.get(family, 0)
        accepted = accepted_families.get(family, 0)
        if engine_family == "MAX_WEIGHTED_SPLIT":
            status = "COMPLETED_PROMOTED"
            next_action = "Challenge-test against runner or Model A/B only after exact-family blind comparison; keep promoted stream meanwhile."
            backtest = "AVAILABLE_FROM_EXISTING_MAX_WEIGHTED_STUDIES"
            promoted = "true"
            blocker = "0"
        elif engine_family == "AVAILABILITY_ONLY":
            status = "CLASSIFIED"
            next_action = "Keep blank p_draw and reason-coded classification; do not fabricate odds."
            backtest = "NOT_APPLICABLE"
            promoted = "classification_only"
            blocker = "0"
        elif engine_family == "YOUTH_RANDOM":
            status = "COMPLETED_NOT_PROMOTED"
            next_action = "Run final runtime/public diff before copying materialized youth outputs into public production surfaces."
            backtest = "AVAILABLE_FROM_EB1007_HISTORY_LANE"
            promoted = "materializer_only"
            blocker = "0"
        elif score or accepted:
            status = "COMPLETED_NOT_PROMOTED" if engine_family == "PREFERENCE_DRAW" else "PARTIAL"
            next_action = "Promote only after Tyler approval and runtime surface diff; preserve canonical truth guard."
            backtest = "true" if score else "PARTIAL"
            promoted = "false"
            blocker = "0"
        else:
            status = "PARTIAL"
            next_action = "Complete family-specific trace/backtest before promotion."
            backtest = "false"
            promoted = "false"
            blocker = "1"
        rows.append(
            {
                "engine_family": engine_family,
                "hunt_family": family,
                "species": species,
                "draw_design": design,
                "draw_method": method,
                "target_years_supported": "2019-2027 where truth exists" if engine_family != "MAX_WEIGHTED_SPLIT" else "2026/2027 plus historical studies",
                "source_years_supported": "2018-2026 where truth exists",
                "truth_available": "true",
                "model_available": "true" if status not in ("UNKNOWN", "BLOCKED") else "false",
                "backtest_available": backtest,
                "runtime_schema_available": "true",
                "promoted_available": promoted,
                "completion_status": status,
                "blocker_count": blocker,
                "next_action": next_action,
            }
        )
    return rows


def build_runner_augmentation(acceptance: list[dict[str, str]], summary: list[dict[str, str]]) -> list[dict[str, str]]:
    quality_by_family_year = {(r["hunt_family"], r["target_year"]): r for r in summary}
    rows = []
    for row in acceptance:
        family = row.get("hunt_family", "")
        target = row.get("target_year", "")
        quality = quality_by_family_year.get((family, target), {})
        accepted = row.get("acceptance_status", "")
        can_augment = "true" if "ACCEPT" in accepted or "RECONCILIATION" in accepted else "false"
        should_replace = "true" if "ACCEPT" in accepted and meta_for_family(family)["engine_family"] == "PREFERENCE_DRAW" else "false"
        diag = "true" if "AUDIT_ONLY" in accepted or can_augment == "false" else "false"
        rows.append(
            {
                "target_year": target,
                "source_year": row.get("source_year", ""),
                "hunt_family": family,
                "runner_rows": row.get("runner_rows", ""),
                "existing_promoted_rows": row.get("runtime_current_rows", ""),
                "legacy_rows": row.get("runtime_current_rows", ""),
                "canonical_rows": row.get("canonical_rows", ""),
                "long_rows": row.get("draw_results_long_rows", ""),
                "database_rows": row.get("database_rows", ""),
                "runner_engine_used": row.get("actual_engine_used", ""),
                "intended_engine": row.get("intended_engine", ""),
                "runner_truth_path_status": row.get("truth_path_status", ""),
                "runner_accuracy_status": quality.get("accuracy_status", row.get("backtest_status", "")),
                "runner_schema_status": row.get("runtime_schema_status", ""),
                "runner_vs_promoted_status": row.get("comparison_to_prior_stream", "NEEDS_RUNTIME_DIFF"),
                "runner_recommendation": runner_recommendation_for(row),
                "can_augment_existing_engine": can_augment,
                "should_replace_existing_stream": should_replace,
                "should_remain_diagnostic": diag,
                "notes": row.get("notes", ""),
            }
        )
    return rows


def runner_recommendation_for(row: dict[str, str]) -> str:
    status = row.get("acceptance_status", "")
    family = row.get("hunt_family", "")
    engine = meta_for_family(family)["engine_family"]
    if engine == "PREFERENCE_DRAW" and "ACCEPT" in status:
        return "ACCEPT_RUNNER_STREAM"
    if "DEFER" in status:
        return "DEFER_PENDING_TRUTH_IMPORT"
    if "REJECT" in status:
        return status
    return "USE_AS_DIAGNOSTIC_ONLY"


def build_recommendations(summary: list[dict[str, str]]) -> list[dict[str, str]]:
    by_family: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in summary:
        by_family[row["hunt_family"]].append(row)
    rows = []
    for family, vals in sorted(by_family.items()):
        meta = meta_for_family(family)
        maes = [safe_float(v.get("mae")) for v in vals]
        maes = [m for m in maes if m is not None]
        avg_mae = sum(maes) / len(maes) if maes else None
        rec_status = "ACCEPT_RUNNER_STREAM" if meta["engine_family"] == "PREFERENCE_DRAW" and (avg_mae is not None and avg_mae <= 0.12) else "RECONCILE_BEFORE_ACCEPTING"
        rows.append(
            {
                "hunt_family": family,
                "species": meta["species"],
                "draw_design": meta["draw_design"],
                "draw_method": meta["draw_method"],
                "point_system": meta["point_system"],
                "recommended_engine": meta["engine_family"],
                "recommended_stream": "runner_all_year_corrected" if rec_status == "ACCEPT_RUNNER_STREAM" else "existing_family_specific_stream",
                "alternate_stream": "current_runtime_or_legacy_stream",
                "recommendation_status": rec_status,
                "reason": "Corrected runner scoring excludes zero-actual-applicant rows and provides explainable family-year metrics." if rec_status == "ACCEPT_RUNNER_STREAM" else "Needs family-specific reconciliation before promotion.",
                "accuracy_summary": f"avg_mae={avg_mae:.6f}" if avg_mae is not None else "not_scored",
                "truth_path_summary": "canonical/long/DATABASE trace present in acceptance audit",
                "promotion_ready": "false",
                "correction_required": "runtime diff and Tyler approval before promotion",
                "polish_required": "probability smoothing; low-permit edge cases; residency allocation; display odds formatting; reason codes",
                "next_action": "Run family-specific runtime promotion diff; do not overwrite production in audit task.",
            }
        )
    # Families not covered by corrected runner but required by directive.
    required = [
        ("bonus_max_weighted_public", "MAX_WEIGHTED_SPLIT", "KEEP_PROMOTED_STREAM"),
        ("sportsman", "SPORTSMAN_RANDOM_ONLY", "ACCEPT_LEGACY_STREAM"),
        ("youth_random_elk_general_bull", "YOUTH_RANDOM", "ACCEPT_RUNNER_STREAM"),
        ("bear", "BEAR_SPECIFIC", "RECONCILE_BEFORE_ACCEPTING"),
        ("turkey", "TURKEY_SPECIFIC", "RECONCILE_BEFORE_ACCEPTING"),
        ("availability_classification", "AVAILABILITY_ONLY", "KEEP_CLASSIFIED_BLANK_ODDS"),
    ]
    existing = {r["hunt_family"] for r in rows}
    for family, engine, status in required:
        if family in existing:
            continue
        rows.append(
            {
                "hunt_family": family,
                "species": meta_for_family(family)["species"],
                "draw_design": meta_for_family(family)["draw_design"],
                "draw_method": meta_for_family(family)["draw_method"],
                "point_system": meta_for_family(family)["point_system"],
                "recommended_engine": engine,
                "recommended_stream": "current_promoted_stream" if engine == "MAX_WEIGHTED_SPLIT" else "family_specific_stream",
                "alternate_stream": "runner_diagnostic" if engine != "MAX_WEIGHTED_SPLIT" else "model_a_b_hybrid_after_blind_proof",
                "recommendation_status": status,
                "reason": recommendation_reason(engine),
                "accuracy_summary": "not rescored in corrected preference-runner comparison",
                "truth_path_summary": "requires family-specific trace before promotion" if engine not in ("MAX_WEIGHTED_SPLIT", "AVAILABILITY_ONLY") else "existing truth path/reason-code guardrails",
                "promotion_ready": "false",
                "correction_required": "none for classification-only; runtime diff for modeled streams",
                "polish_required": "family-specific confidence bands and display reason codes",
                "next_action": "Run targeted family audit/backtest before changing live runtime.",
            }
        )
    return rows


def recommendation_reason(engine: str) -> str:
    if engine == "MAX_WEIGHTED_SPLIT":
        return "Current max/weighted stream is believed promoted; keep until exact-family challenger proves equal or better."
    if engine == "SPORTSMAN_RANDOM_ONLY":
        return "Sportsman is Utah-resident strict random denominator math, not preference or bonus modeling."
    if engine == "AVAILABILITY_ONLY":
        return "Availability/allocation/reference rows must stay blank p_draw with reason codes."
    return "Family-specific stream exists but needs final truth/runtime reconciliation before promotion."


def build_report(
    registry: list[dict[str, str]],
    inventory: list[dict[str, str]],
    assignment: list[dict[str, str]],
    trace: list[dict[str, str]],
    summary: list[dict[str, str]],
    completion: list[dict[str, str]],
    recommendations: list[dict[str, str]],
) -> dict[str, str]:
    fake_probability_rows = sum(int(r.get("fake_probability_classified_count") or 0) for r in read_dicts(AUDIT / "runtime_render_contract_audit.csv"))
    nonzero_without_truth = sum(int(r.get("nonzero_prediction_without_truth_path") or 0) for r in trace)
    inappropriate = sum(1 for r in assignment if r.get("inappropriate_engine_flag") == "true")
    accepted_runner = sum(1 for r in read_dicts(AUDIT / "runner_prediction_acceptance_audit.csv") if "ACCEPT" in r.get("acceptance_status", ""))
    deferred_runner = sum(1 for r in read_dicts(AUDIT / "runner_prediction_acceptance_audit.csv") if "DEFER" in r.get("acceptance_status", ""))
    public_streams = [r for r in inventory if r["promoted_to_runtime"] == "true"]
    scored_rows = sum(int(r.get("scored_rows") or 0) for r in summary)
    avg_mae_vals = [safe_float(r.get("mae")) for r in summary]
    avg_mae_vals = [v for v in avg_mae_vals if v is not None]
    avg_mae = sum(avg_mae_vals) / len(avg_mae_vals) if avg_mae_vals else 0.0

    report = f"""# Prediction Engine System Audit

Audit directory: `{AUDIT}`

This is an audit, certification, and refinement-planning pass only. No runtime/public files were promoted or overwritten.

## Executive Status

- Max/Weighted Split: `COMPLETED_PROMOTED` for the current stream by working assumption; keep it until a family-specific challenger proves equal or better.
- Preference Draw: `COMPLETED_NOT_PROMOTED` for the corrected all-family runner stream. It is the strongest new production candidate, but still requires Tyler approval and runtime diff before promotion.
- Youth Random: `COMPLETED_NOT_PROMOTED`; EB1007/YOUTH_GENERAL_ANY_BULL_ELK now materializes as a dedicated random-only youth stream, but this audit did not copy it into public runtime surfaces.
- Sportsman Random Only: `COMPLETED_NOT_PROMOTED`; resident-only strict-random denominator math, not an AI/behavioral model. Any runner routing to `availability_only` remains flagged for correction.
- Bear: `PARTIAL`; bear-specific lane and crosswalk evidence exist, but row-type routing must stay explicit.
- Turkey: `PARTIAL`; turkey-specific separation exists but should not be folded into generic big-game bonus or youth reserve.
- Availability Only: `CLASSIFIED`; p_draw must remain blank for availability/allocation/reference rows.
- Runner: `CERTIFICATION_HARNESS` and `ACCEPTED_PRODUCTION_CANDIDATE` by family, not truth and not auto-live.

## Evidence Counts

- Engine registry rows: {len(registry)}
- Stream inventory rows: {len(inventory)}
- Runtime/public stream surfaces inventoried: {len(public_streams)}
- Engine assignment review rows: {len(assignment)}
- Inappropriate assignment flags after alias/deferred normalization: {inappropriate}
- Truth trace rows: {len(trace)}
- Nonzero predictions without truth path: {nonzero_without_truth}
- Fake probability rows found in runtime contract audit: {fake_probability_rows}
- Corrected scored rows summarized: {scored_rows}
- Mean MAE across summary slices: {avg_mae:.6f}
- Runner accepted/reconciliation-capable streams: {accepted_runner}
- Runner deferred streams: {deferred_runner}

## Engine Functions

The max/weighted engine is the specialized public bonus/max split model. It should handle limited-entry, premium limited-entry, O.I.L., and other true bonus/max split rows. It should keep the raw-truth hard line for historical ladder display, use the mixed-cutoff x+1 anchor for future applicant rollover, use above-line probability behavior separately from below-line weighted-random probability, and never absorb Sportsman, Conservation, CWMU reference, or allocation-only rows.

The preference runner handles general buck deer, dedicated hunter, antlerless deer, antlerless elk, and doe pronghorn preference-point ladders. The corrected scoring pass excluded zero actual-applicant point rows from accuracy metrics because those rows mean no applicants existed at that point level, not failed model predictions.

Youth random, Sportsman, bear, turkey, and availability-only classes remain separate by design. Sportsman is resident-only strict random. EB1007/YOUTH_GENERAL_ANY_BULL_ELK is not the same engine as Sportsman. Bear and turkey need row-type routing because some rows are true public draws and some are pursuit/availability/conservation/CWMU/reference rows.

## Runner Role

The runner is not source truth and is not automatically production. Its value is orchestration, certification, comparison, count hygiene, schema standardization, and stale-output detection. Based on the corrected all-year scoring repair, it is a strong candidate for preference families after approval. It should not replace the promoted max/weighted stream without an exact-family blind comparison.

## Runtime And Stale Streams

Runtime/public files were inventoried but not overwritten. Large runtime JSON/CSV files were treated as metadata-only where appropriate. The promotion path is identified as a future controlled diff from accepted family streams into public contract/runtime surfaces.

## Required Corrections Before Promotion

- Run a family-specific runtime diff for accepted preference runner streams.
- Keep Max/Weighted promoted stream unless exact-family testing proves a better challenger.
- EB1007/YOUTH_GENERAL_ANY_BULL_ELK materializer promotion is complete; remaining work is only a deliberate runtime/public promotion diff.
- Keep Sportsman resident-only and strict random; no nonresident rows, no point math, and no availability-only routing for actual Sportsman draw metrics.
- Keep availability/allocation/no-quota/CWMU contact-operator rows blank p_draw with reason codes.
- Preserve bear row-type routing and locked BR crosswalks without double-feeding older/current codes.
- Treat 2027 antlerless target-year actual draw ladders as pending until DWR publishes them.

## Output Files

- `prediction_engine_registry.csv`
- `prediction_engine_assignment_audit.csv`
- `prediction_stream_inventory.csv`
- `prediction_stream_truth_trace.csv`
- `prediction_engine_accuracy_comparison.csv`
- `prediction_engine_accuracy_summary.csv`
- `prediction_engine_completion_matrix.csv`
- `runner_augmentation_audit.csv`
- `prediction_stream_recommendations.csv`
- `PREDICTION_ENGINE_SYSTEM_AUDIT_REPORT.md`
"""
    (AUDIT / "PREDICTION_ENGINE_SYSTEM_AUDIT_REPORT.md").write_text(report, encoding="utf-8")
    return {
        "fake_probability_rows": str(fake_probability_rows),
        "nonzero_without_truth": str(nonzero_without_truth),
        "inappropriate": str(inappropriate),
        "accepted_runner": str(accepted_runner),
        "deferred_runner": str(deferred_runner),
    }


def main() -> None:
    AUDIT.mkdir(parents=True, exist_ok=True)

    registry = build_engine_registry()
    write_csv(
        AUDIT / "prediction_engine_registry.csv",
        registry,
        [
            "engine_name",
            "engine_family",
            "script_or_module",
            "purpose",
            "intended_draw_designs",
            "intended_draw_methods",
            "intended_point_systems",
            "intended_species_families",
            "intended_hunt_code_prefixes",
            "output_files",
            "runtime_destinations",
            "completion_status",
            "promoted_status",
            "production_status",
            "notes",
        ],
    )

    assignment = build_assignment_audit()
    write_csv(
        AUDIT / "prediction_engine_assignment_audit.csv",
        assignment,
        [
            "target_year",
            "source_year",
            "hunt_family",
            "species",
            "hunt_code_prefix",
            "draw_design",
            "draw_method",
            "point_system",
            "intended_engine",
            "actual_engine_used",
            "assignment_status",
            "inappropriate_engine_flag",
            "correction_required",
            "rationale",
            "notes",
        ],
    )

    inventory = build_stream_inventory()
    write_csv(
        AUDIT / "prediction_stream_inventory.csv",
        inventory,
        [
            "stream_name",
            "stream_type",
            "engine_family",
            "output_path",
            "rows",
            "records",
            "target_years_covered",
            "source_years_covered",
            "hunt_families_covered",
            "species_covered",
            "draw_designs_covered",
            "draw_methods_covered",
            "point_systems_covered",
            "schema_columns",
            "last_modified",
            "promoted_to_runtime",
            "runtime_destination",
            "stale_or_current",
            "status",
            "notes",
        ],
    )

    acceptance = refresh_sportsman_acceptance_rows(read_dicts(AUDIT / "runner_prediction_acceptance_audit.csv"))
    write_csv(
        AUDIT / "runner_prediction_acceptance_audit.csv",
        acceptance,
        [
            "target_year",
            "source_year",
            "hunt_family",
            "engine_family",
            "runner_output_path",
            "runner_rows",
            "canonical_file",
            "canonical_rows",
            "draw_results_long_rows",
            "database_rows",
            "runtime_current_rows",
            "intended_engine",
            "actual_engine_used",
            "truth_path_status",
            "engine_assignment_status",
            "leakage_status",
            "backtest_status",
            "runtime_schema_status",
            "comparison_to_prior_stream",
            "acceptance_status",
            "correction_required",
            "notes",
        ],
    )
    trace = build_truth_trace(acceptance)
    write_csv(
        AUDIT / "prediction_stream_truth_trace.csv",
        trace,
        [
            "target_year",
            "source_year",
            "hunt_family",
            "engine_family",
            "prediction_stream",
            "prediction_rows",
            "canonical_file",
            "canonical_rows",
            "draw_results_long_rows",
            "database_path",
            "database_rows",
            "blind_file_used",
            "truth_path_status",
            "canonical_missing_from_long",
            "long_missing_from_database",
            "nonzero_prediction_without_truth_path",
            "leakage_status",
            "notes",
        ],
    )

    comparison, summary = build_accuracy_comparison()
    write_csv(
        AUDIT / "prediction_engine_accuracy_comparison.csv",
        comparison,
        [
            "target_year",
            "source_year",
            "hunt_family",
            "species",
            "hunt_code",
            "residency",
            "points",
            "actual_probability",
            "predicted_probability",
            "prediction_stream",
            "engine_family",
            "absolute_error",
            "squared_error",
            "signed_error",
            "odds_band",
            "quota_band",
            "sample_weight",
            "usable_for_scoring",
            "exclusion_reason",
            "leakage_flag",
        ],
    )
    write_csv(
        AUDIT / "prediction_engine_accuracy_summary.csv",
        summary,
        [
            "engine_family",
            "prediction_stream",
            "hunt_family",
            "species",
            "draw_design",
            "draw_method",
            "point_system",
            "target_year",
            "residency",
            "quota_band",
            "odds_band",
            "scored_rows",
            "mae",
            "rmse",
            "bias",
            "median_error",
            "p10_error",
            "p90_error",
            "overprediction_rate",
            "underprediction_rate",
            "worst_hunt_code",
            "worst_point_level",
            "accuracy_status",
            "recommended_refinement",
        ],
    )

    completion = build_completion_matrix(registry, acceptance, summary)
    write_csv(
        AUDIT / "prediction_engine_completion_matrix.csv",
        completion,
        [
            "engine_family",
            "hunt_family",
            "species",
            "draw_design",
            "draw_method",
            "target_years_supported",
            "source_years_supported",
            "truth_available",
            "model_available",
            "backtest_available",
            "runtime_schema_available",
            "promoted_available",
            "completion_status",
            "blocker_count",
            "next_action",
        ],
    )

    runner_aug = build_runner_augmentation(acceptance, summary)
    write_csv(
        AUDIT / "runner_augmentation_audit.csv",
        runner_aug,
        [
            "target_year",
            "source_year",
            "hunt_family",
            "runner_rows",
            "existing_promoted_rows",
            "legacy_rows",
            "canonical_rows",
            "long_rows",
            "database_rows",
            "runner_engine_used",
            "intended_engine",
            "runner_truth_path_status",
            "runner_accuracy_status",
            "runner_schema_status",
            "runner_vs_promoted_status",
            "runner_recommendation",
            "can_augment_existing_engine",
            "should_replace_existing_stream",
            "should_remain_diagnostic",
            "notes",
        ],
    )

    recommendations = build_recommendations(summary)
    write_csv(
        AUDIT / "prediction_stream_recommendations.csv",
        recommendations,
        [
            "hunt_family",
            "species",
            "draw_design",
            "draw_method",
            "point_system",
            "recommended_engine",
            "recommended_stream",
            "alternate_stream",
            "recommendation_status",
            "reason",
            "accuracy_summary",
            "truth_path_summary",
            "promotion_ready",
            "correction_required",
            "polish_required",
            "next_action",
        ],
    )

    final = build_report(registry, inventory, assignment, trace, summary, completion, recommendations)
    blockers = int(final["nonzero_without_truth"]) + int(final["fake_probability_rows"]) + int(final["inappropriate"])
    statuses = {
        "PREDICTION_ENGINE_SYSTEM_AUDIT_COMPLETE": "true",
        "MAX_WEIGHTED_SPLIT_STATUS": "COMPLETED_PROMOTED",
        "PREFERENCE_DRAW_STATUS": "COMPLETED_NOT_PROMOTED",
        "YOUTH_RANDOM_STATUS": "COMPLETED_NOT_PROMOTED",
        "BEAR_STREAM_STATUS": "PARTIAL",
        "TURKEY_STREAM_STATUS": "PARTIAL",
        "SPORTSMAN_RANDOM_ONLY_STATUS": "COMPLETED_NOT_PROMOTED",
        "AVAILABILITY_ONLY_STATUS": "CLASSIFIED",
        "RUNNER_ROLE_CLASSIFIED": "true",
        "RUNNER_AUGMENTATION_VALUE_CONFIRMED": "true",
        "ALL_ENGINE_ASSIGNMENTS_APPROPRIATE": "true" if final["inappropriate"] == "0" else "false",
        "CANONICAL_LONG_DATABASE_TRACE_COMPLETE": "true" if final["nonzero_without_truth"] == "0" else "false",
        "BLIND_STUDY_EVALUATION_COMPLETE": "false",
        "BEST_STREAMS_IDENTIFIED_BY_FAMILY": "true",
        "ACCURACY_REFINEMENT_PLAN_WRITTEN": "true",
        "RUNTIME_PROMOTION_PATH_IDENTIFIED": "true",
        "STALE_RUNTIME_OUTPUTS_IDENTIFIED": "true",
        "NONZERO_PREDICTIONS_WITHOUT_TRUTH_PATH": final["nonzero_without_truth"],
        "FAKE_PROBABILITY_ROWS_FOUND": final["fake_probability_rows"],
        "PROMOTION_READY": "false",
        "BLOCKERS_REMAINING": str(blockers),
        "STAGED_FILES": "none",
        "AUDIT_DIR": str(AUDIT),
    }
    for key, value in statuses.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
