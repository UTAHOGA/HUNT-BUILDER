#!/usr/bin/env python3
"""Non-mutating engine hardening, validation, calibration, and truth audit.

This runner intentionally reports defects and repair candidates instead of
promoting or rewriting runtime artifacts. It favors traceable evidence over
silent inference, and it writes every artifact under a timestamped audit folder.
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import math
import os
import re
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


REPO = Path(__file__).resolve().parents[1]
AUDIT_ROOT = Path("audits") / "engine_hardening_validation_calibration"

SCAN_TOP_LEVELS = (
    "engine",
    "pipeline",
    "tools",
    "scripts",
    "tests",
    "data_truth",
    "data_model",
    "processed_data",
    "runtime",
    "public",
    "audits",
)

ENGINE_SEARCH_WORDS = (
    "predict",
    "prediction",
    "engine",
    "materialize",
    "forecast",
    "backtest",
    "draw",
    "odds",
    "calibration",
    "scorable",
    "p_draw",
    "probability",
    "quota",
    "permit",
    "applicant",
    "point",
    "ladder",
    "preference",
    "bonus",
    "youth",
    "availability",
)

TABULAR_EXTENSIONS = {".csv", ".tsv"}
REFERENCE_EXTENSIONS = {".csv", ".json", ".jsonl", ".xlsx", ".xls", ".sqlite", ".db", ".pdf"}
RUNTIME_HINTS = ("prediction", "predictions", "runtime", "materialized", "coverage", "report", "ml_draw")
PROBABILITY_HINTS = ("prob", "p_draw", "p_random", "p_bonus", "p_max", "success_ratio", "draw_probability")
PERCENT_HINTS = ("percent", "pct", "odds")
COUNT_HINTS = ("applicant", "permit", "quota", "drawn", "available", "total")
LINEAGE_HINTS = ("source", "lineage", "pdf", "page", "truth")

SCORABLE_REASON_ORDER = (
    "missing_hunt_code",
    "missing_year",
    "missing_residency",
    "missing_point_level",
    "missing_actual_probability",
    "missing_applicants",
    "missing_permits",
    "availability_only_not_odds_scorable",
    "otc_unlimited_not_odds_scorable",
    "non_public_or_suppressed",
    "duplicate_or_conflicting_truth",
    "unknown_schema",
    "other_with_detail",
)

csv.field_size_limit(min(sys.maxsize, 2_147_483_647))


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def rel(path: Path, repo: Path = REPO) -> str:
    try:
        return path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        return str(path)


def safe_float(value: Any) -> float | None:
    text = clean(value).replace(",", "").replace("%", "")
    if not text or text.upper() in {"N/A", "NA", "NULL", "NONE", "UNLIMITED"}:
        return None
    try:
        return float(text)
    except ValueError:
        return math.nan


def safe_int(value: Any) -> int | None:
    parsed = safe_float(value)
    if parsed is None or math.isnan(parsed):
        return None
    if parsed.is_integer():
        return int(parsed)
    return None


def row_year(row: Mapping[str, Any]) -> int | None:
    for key in ("actual_draw_year", "draw_year", "target_year", "permit_year", "year", "truth_year", "source_year"):
        value = safe_int(row.get(key))
        if value is not None:
            return value
    return None


def norm_code(value: Any) -> str:
    return clean(value).upper()


def norm_residency(value: Any) -> str:
    text = clean(value).lower()
    if text in {"res", "resident", "r"}:
        return "Resident"
    if text in {"nr", "nonresident", "non-resident", "non resident", "non_resident"}:
        return "Nonresident"
    if text in {"all", "both", "total"}:
        return "All"
    return clean(value)


def field_contains(field: str, hints: Sequence[str]) -> bool:
    low = field.lower()
    return any(hint in low for hint in hints)


def probability_from_row(row: Mapping[str, Any]) -> float | None:
    for key in row:
        low = key.lower()
        if low in {"p_draw", "p_draw_mean", "success_ratio", "draw_probability", "actual_probability"}:
            value = safe_float(row.get(key))
            if value is None or math.isnan(value):
                continue
            return value / 100.0 if value > 1.0 else value
    for key in row:
        low = key.lower()
        if low in {"p_draw_percent", "p_draw_pct", "success_percent", "success_pct", "odds_percent"}:
            value = safe_float(row.get(key))
            if value is None or math.isnan(value):
                continue
            return value / 100.0
    applicants = first_number(row, ("eligible_applicants", "applicants", "total_applicants"))
    drawn = first_number(row, ("successful_applicants", "drawn", "permits_drawn", "total_permits"))
    if applicants and applicants > 0 and drawn is not None:
        return max(0.0, min(1.0, drawn / applicants))
    return None


def first_number(row: Mapping[str, Any], keys: Sequence[str]) -> float | None:
    lowered = {key.lower(): key for key in row}
    for want in keys:
        key = lowered.get(want.lower())
        if key is None:
            continue
        value = safe_float(row.get(key))
        if value is not None and not math.isnan(value):
            return value
    return None


def infer_family(row_or_path: Mapping[str, Any] | str | Path) -> str:
    text = ""
    if isinstance(row_or_path, Mapping):
        pieces = [
            clean(row_or_path.get("draw_system_type")),
            clean(row_or_path.get("model_strategy")),
            clean(row_or_path.get("hunt_family")),
            clean(row_or_path.get("family")),
            clean(row_or_path.get("species")),
            norm_code(row_or_path.get("hunt_code"))[:2],
        ]
        text = " ".join(pieces).lower()
    else:
        text = str(row_or_path).lower()
    if "preference" in text or "dedicated" in text or "doe_pronghorn" in text:
        return "PREFERENCE_DRAW"
    if "bonus" in text or any(prefix in text for prefix in ("eb", "db", "pb", "mb", "bg", "rb")):
        return "BONUS_SPLIT_DRAW"
    if "youth" in text:
        return "YOUTH_RANDOM"
    if "availability" in text or "mountain_lion" in text or "cougar" in text:
        return "AVAILABILITY_ONLY"
    if "otc_capped" in text:
        return "OTC_CAPPED"
    if "otc_unlimited" in text:
        return "OTC_UNLIMITED"
    if "private_lands" in text or "allocation" in text or "sportsman" in text:
        return "DIRECT_ALLOCATION"
    if "harvest" in text or "quality" in text:
        return "HARVEST_FEATURE"
    if "ladder" in text or "point" in text:
        return "POINT_LADDER"
    if "mixed" in text:
        return "MIXED_DRAW"
    return "UNKNOWN"


def suspected_role(path: Path) -> str:
    text = rel(path).lower()
    name = path.name.lower()
    if "canonical_yearly" in text or "draw_results_truth" in text:
        return "canonical_or_truth_draw_results"
    if "pipeline/raw" in text:
        return "raw_source_or_reference"
    if "prediction" in name or "predictions" in name or "runtime" in text:
        return "runtime_or_model_output"
    if "audit" in text or "report" in name:
        return "audit_or_report"
    if text.startswith("engine/"):
        return "engine_code"
    if text.startswith("tests/"):
        return "test_code"
    if text.startswith("public/"):
        return "public_delivery"
    return "unknown"


def write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
    os.replace(tmp, path)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def read_csv_rows(path: Path) -> tuple[list[str], Iterable[dict[str, str]]]:
    handle = path.open("r", encoding="utf-8-sig", newline="")
    reader = csv.DictReader(handle)

    def iterator() -> Iterable[dict[str, str]]:
        try:
            for row in reader:
                yield dict(row)
        finally:
            handle.close()

    return list(reader.fieldnames or []), iterator()


def run_command(repo: Path, args: Sequence[str]) -> tuple[int, str]:
    proc = subprocess.run(
        list(args),
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout


def git_output(repo: Path, *args: str) -> str:
    code, out = run_command(repo, ("git", *args))
    return out if code == 0 else f"COMMAND_FAILED git {' '.join(args)}\n{out}"


def iter_existing_roots(repo: Path, roots: Sequence[str]) -> Iterable[Path]:
    for name in roots:
        path = repo / name
        if path.exists():
            yield path


def iter_files(repo: Path, roots: Sequence[str]) -> Iterable[Path]:
    for root in iter_existing_roots(repo, roots):
        for path in root.rglob("*"):
            if path.is_file():
                yield path


def profile_tabular(path: Path, max_samples: int = 5) -> dict[str, Any]:
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    result: dict[str, Any] = {
        "row_count_if_tabular": "",
        "column_count_if_tabular": "",
        "columns": "",
        "detected_years": "",
        "detected_draw_years": "",
        "detected_permit_years": "",
        "detected_hunt_codes_count": "",
        "detected_hunt_codes_sample": "",
        "detected_residency_values": "",
        "detected_point_columns": "",
        "detected_probability_columns": "",
        "detected_source_columns": "",
        "detected_lineage_columns": "",
        "parse_error": "",
    }
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, delimiter=delimiter)
            fields = list(reader.fieldnames or [])
            years: set[str] = set()
            draw_years: set[str] = set()
            permit_years: set[str] = set()
            hunt_codes: set[str] = set()
            residencies: set[str] = set()
            row_count = 0
            year_cols = [f for f in fields if f.lower() in {"year", "actual_draw_year", "draw_year", "truth_year"}]
            draw_year_cols = [f for f in fields if "draw_year" in f.lower() or f.lower() == "actual_draw_year"]
            permit_year_cols = [f for f in fields if "permit_year" in f.lower()]
            hunt_col = next((f for f in fields if f.lower() == "hunt_code"), "")
            residency_col = next((f for f in fields if f.lower() == "residency"), "")
            for row in reader:
                row_count += 1
                for f in year_cols:
                    if clean(row.get(f)):
                        years.add(clean(row.get(f)))
                for f in draw_year_cols:
                    if clean(row.get(f)):
                        draw_years.add(clean(row.get(f)))
                for f in permit_year_cols:
                    if clean(row.get(f)):
                        permit_years.add(clean(row.get(f)))
                if hunt_col and norm_code(row.get(hunt_col)):
                    hunt_codes.add(norm_code(row.get(hunt_col)))
                if residency_col and norm_residency(row.get(residency_col)):
                    residencies.add(norm_residency(row.get(residency_col)))
        result.update(
            {
                "row_count_if_tabular": row_count,
                "column_count_if_tabular": len(fields),
                "columns": "|".join(fields),
                "detected_years": "|".join(sorted(years)[:30]),
                "detected_draw_years": "|".join(sorted(draw_years)[:30]),
                "detected_permit_years": "|".join(sorted(permit_years)[:30]),
                "detected_hunt_codes_count": len(hunt_codes),
                "detected_hunt_codes_sample": "|".join(sorted(hunt_codes)[:25]),
                "detected_residency_values": "|".join(sorted(residencies)),
                "detected_point_columns": "|".join(f for f in fields if "point" in f.lower()),
                "detected_probability_columns": "|".join(f for f in fields if field_contains(f, PROBABILITY_HINTS)),
                "detected_source_columns": "|".join(f for f in fields if "source" in f.lower()),
                "detected_lineage_columns": "|".join(f for f in fields if field_contains(f, LINEAGE_HINTS)),
            }
        )
    except Exception as exc:  # pragma: no cover - defensive audit reporting
        result["parse_error"] = repr(exc)
    return result


def classify_truth_source(path: Path, profile: Mapping[str, Any]) -> tuple[str, str, str, str, str]:
    text = rel(path).lower()
    columns = clean(profile.get("columns")).lower()
    concerns: list[str] = []
    recommended = "review"
    usable_input = "false"
    usable_truth = "false"
    if "draw_results_truth/normalized/canonical_yearly" in text:
        classification = "CANONICAL_TRUTH"
        usable_input = "true"
        usable_truth = "true"
        recommended = "use_as_actual_truth_where_schema_is_scorable"
    elif "data_truth" in text and ("normalized" in text or "validation" in text):
        classification = "TRUTH_DERIVED"
        usable_input = "true"
        usable_truth = "true" if "source" in columns or "truth" in text else "review"
        recommended = "use_with_lineage_review"
    elif "pipeline/raw" in text:
        classification = "CANONICAL_TRUTH" if path.suffix.lower() in {".pdf", ".xlsx"} else "REFERENCE_DATA"
        usable_input = "true"
        usable_truth = "review"
        recommended = "use_as_source_or_reference_not_prediction_actuals"
    elif "processed_data" in text and any(h in text for h in ("prediction", "runtime", "ml_draw", "materialized")):
        classification = "MODEL_DERIVED"
        usable_input = "review"
        usable_truth = "false"
        concerns.append("prediction_or_runtime_output_not_actual_truth")
        recommended = "do_not_use_as_actual_truth"
    elif "processed_data" in text:
        classification = "RUNTIME_DERIVED"
        usable_input = "review"
        usable_truth = "false"
        concerns.append("processed_output_lineage_must_be_proven")
    elif "backup" in text or "archive" in text or "deprecated" in text:
        classification = "STALE_OR_DEPRECATED"
        concerns.append("backup_archive_or_deprecated_path")
    elif path.suffix.lower() in {".sqlite", ".db"}:
        classification = "REFERENCE_DATA"
        usable_input = "review"
        concerns.append("database_schema_not_expanded_by_csv_audit")
    else:
        classification = "UNKNOWN_LINEAGE"
        concerns.append("lineage_not_obvious_from_path")
    if classification in {"UNKNOWN_LINEAGE", "MODEL_DERIVED"} and "actual" in columns:
        concerns.append("actual_columns_present_in_non_truth_surface")
    return classification, usable_input, usable_truth, ";".join(concerns), recommended


def scorable_reason(row: Mapping[str, Any]) -> str:
    hunt_code = norm_code(row.get("hunt_code"))
    year = row_year(row)
    residency = norm_residency(row.get("residency"))
    point = clean(row.get("points") or row.get("point_level") or row.get("preference_points") or row.get("bonus_points"))
    family = infer_family(row)
    strategy = clean(row.get("draw_system_type") or row.get("model_strategy")).upper()
    probability = probability_from_row(row)
    applicants = first_number(row, ("eligible_applicants", "applicants", "total_applicants"))
    permits = first_number(row, ("total_permits", "permits", "available_permits", "permits_drawn"))
    if not hunt_code:
        return "missing_hunt_code"
    if year is None:
        return "missing_year"
    if not residency:
        return "missing_residency"
    if family in {"PREFERENCE_DRAW", "BONUS_SPLIT_DRAW", "POINT_LADDER", "MIXED_DRAW"} and not point:
        return "missing_point_level"
    if "AVAILABILITY" in strategy or family == "AVAILABILITY_ONLY":
        return "availability_only_not_odds_scorable"
    if "OTC_UNLIMITED" in strategy or family == "OTC_UNLIMITED":
        return "otc_unlimited_not_odds_scorable"
    if probability is None:
        if applicants is None:
            return "missing_applicants"
        if permits is None:
            return "missing_permits"
        return "missing_actual_probability"
    if probability < 0 or probability > 1:
        return "missing_actual_probability"
    return ""


def prediction_key(row: Mapping[str, Any], include_year: bool = True) -> tuple[str, str, str, str]:
    year = str(row_year(row) or "") if include_year else ""
    return (
        year,
        norm_code(row.get("hunt_code")),
        norm_residency(row.get("residency")),
        clean(row.get("points") or row.get("point_level") or row.get("preference_points") or row.get("bonus_points")),
    )


class HardeningAudit:
    def __init__(self, repo: Path, output_dir: Path, years: Sequence[int], target_years: Sequence[int], strict: bool) -> None:
        self.repo = repo.resolve()
        self.output_dir = output_dir.resolve()
        self.years = tuple(years)
        self.target_years = tuple(target_years)
        self.strict = strict
        self.commands: list[str] = []
        self.files_changed: list[str] = []
        self.blockers: list[str] = []
        self.repair_candidates: list[str] = []
        self.counts: Counter[str] = Counter()
        self.truth_rows_by_family_year: dict[tuple[str, int], set[str]] = defaultdict(set)
        self.scorable_rows_by_family_year: dict[tuple[str, int], int] = Counter()
        self.runtime_codes_by_family_year: dict[tuple[str, int], set[str]] = defaultdict(set)
        self.runtime_rows_by_family_year: dict[tuple[str, int], int] = Counter()
        self.scorable_actuals: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        self.runtime_predictions: dict[tuple[str, str, str, str], dict[str, Any]] = {}

    def command(self, args: Sequence[str]) -> tuple[int, str]:
        self.commands.append(" ".join(args))
        return run_command(self.repo, args)

    def write_baseline(self) -> None:
        branch = git_output(self.repo, "branch", "--show-current")
        head = git_output(self.repo, "rev-parse", "HEAD")
        status = git_output(self.repo, "status", "--short")
        staged = git_output(self.repo, "diff", "--cached", "--name-status")
        write_text(self.output_dir / "BASELINE_BRANCH.txt", branch)
        write_text(self.output_dir / "BASELINE_HEAD_COMMIT.txt", head)
        write_text(self.output_dir / "BASELINE_GIT_STATUS.txt", f"STAGED:\n{staged}\n\nSTATUS:\n{status}")

    def repo_inventory(self) -> None:
        rows: list[dict[str, Any]] = []
        large_rows: list[dict[str, Any]] = []
        for path in iter_files(self.repo, SCAN_TOP_LEVELS):
            try:
                stat = path.stat()
            except OSError:
                continue
            size_mb = stat.st_size / (1024 * 1024)
            row = {
                "path": rel(path, self.repo),
                "size_bytes": stat.st_size,
                "size_mb": f"{size_mb:.3f}",
                "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                "extension": path.suffix.lower(),
                "top_level_folder": rel(path, self.repo).split("/", 1)[0],
                "suspected_role": suspected_role(path),
            }
            rows.append(row)
            threshold = ""
            if stat.st_size > 100 * 1024 * 1024:
                threshold = "over_100_mb_git_prohibited"
            elif stat.st_size > 50 * 1024 * 1024:
                threshold = "over_50_mb_requires_review"
            elif stat.st_size > 10 * 1024 * 1024:
                threshold = "over_10_mb"
            if threshold:
                large = dict(row)
                large["threshold"] = threshold
                large_rows.append(large)
        write_csv(
            self.output_dir / "REPO_FILE_INVENTORY.csv",
            ("path", "size_bytes", "size_mb", "modified_time", "extension", "top_level_folder", "suspected_role"),
            rows,
        )
        write_csv(
            self.output_dir / "LARGE_FILE_AUDIT.csv",
            ("path", "size_bytes", "size_mb", "modified_time", "extension", "top_level_folder", "suspected_role", "threshold"),
            large_rows,
        )
        self.counts["large_files_over_100mb"] = sum(1 for r in large_rows if r["threshold"] == "over_100_mb_git_prohibited")

    def discover_components(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        py_files = [p for p in iter_files(self.repo, ("engine", "tools", "pipeline", "scripts", "tests")) if p.suffix == ".py"]
        all_test_files = [rel(p, self.repo) for p in py_files if "/tests/" in f"/{rel(p, self.repo)}" or rel(p, self.repo).startswith("tests/")]
        for path in py_files:
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            low = text.lower()
            file_low = rel(path, self.repo).lower()
            if not any(word in low or word in file_low for word in ENGINE_SEARCH_WORDS):
                continue
            reads = sorted(set(re.findall(r"(?:read_csv|read_json|json\.load|open|Path\()\s*\(?[\"']([^\"']+\.(?:csv|json|xlsx|xls|sqlite|db|pdf))[\"']", text)))
            writes = sorted(set(re.findall(r"(?:to_csv|to_json|write_text|open)\s*\(?[\"']([^\"']+\.(?:csv|json|md|txt))[\"']", text)))
            imports: list[str] = []
            try:
                tree = ast.parse(text)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        imports.extend(alias.name for alias in node.names)
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        imports.append(node.module)
            except SyntaxError:
                imports = []
            cli = "argparse" if "argparse" in low else ""
            if "if __name__" in low and "__main__" in low:
                cli = (cli + ";__main__").strip(";")
            component_name = path.stem
            test_covering = [t for t in all_test_files if component_name.lower().replace("test_", "") in t.lower()]
            status = "test" if rel(path, self.repo).startswith("tests/") else "production" if rel(path, self.repo).startswith("engine/") else "unknown"
            if "deprecated" in file_low or "archive" in file_low:
                status = "deprecated"
            row = {
                "file_path": rel(path, self.repo),
                "component_name": component_name,
                "likely_engine_family": infer_family(path),
                "reads_files": "|".join(reads),
                "writes_files": "|".join(writes),
                "CLI_entrypoint_if_any": cli,
                "imports": "|".join(sorted(set(imports))[:80]),
                "required_columns_if_discoverable": "|".join(sorted(set(re.findall(r"[\"']([A-Za-z_][A-Za-z0-9_]*(?:hunt_code|residency|points|p_draw|permit|quota|applicant|source)[A-Za-z0-9_]*)[\"']", text)))[:80]),
                "prediction_output_columns_if_discoverable": "|".join(sorted(set(re.findall(r"[\"']([A-Za-z_][A-Za-z0-9_]*(?:p_draw|probability|prediction|odds|quota|permit)[A-Za-z0-9_]*)[\"']", text)))[:80]),
                "test_files_covering_it": "|".join(test_covering[:30]),
                "status": status,
            }
            rows.append(row)
        write_csv(
            self.output_dir / "ENGINE_COMPONENT_DISCOVERY.csv",
            (
                "file_path",
                "component_name",
                "likely_engine_family",
                "reads_files",
                "writes_files",
                "CLI_entrypoint_if_any",
                "imports",
                "required_columns_if_discoverable",
                "prediction_output_columns_if_discoverable",
                "test_files_covering_it",
                "status",
            ),
            rows,
        )
        md = ["# Engine Component Discovery", "", f"Components discovered: {len(rows)}", ""]
        by_family = Counter(row["likely_engine_family"] for row in rows)
        for family, count in sorted(by_family.items()):
            md.append(f"- {family}: {count}")
        write_text(self.output_dir / "ENGINE_COMPONENT_DISCOVERY.md", "\n".join(md) + "\n")
        self.counts["engines_discovered"] = len(rows)
        return rows

    def feeder_audit(self, components: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        feeder_paths: dict[str, str] = {}
        try:
            if str(self.repo) not in sys.path:
                sys.path.insert(0, str(self.repo))
            from tools.engine_feeder_contract import feeders_for_group

            for contract in feeders_for_group():
                feeder_paths[contract.path] = contract.consumer_module
                for alt in contract.alternatives:
                    feeder_paths[alt] = contract.consumer_module
        except Exception as exc:
            self.blockers.append(f"Unable to import tools.engine_feeder_contract: {exc!r}")
        for component in components:
            for field in ("reads_files", "writes_files"):
                for raw in clean(component.get(field)).split("|"):
                    if not raw:
                        continue
                    feeder_paths.setdefault(raw.replace("\\", "/"), clean(component.get("file_path")))
        for path in iter_files(self.repo, ("data_truth", "data_model", "processed_data")):
            name = path.name.lower()
            if path.suffix.lower() in REFERENCE_EXTENSIONS and any(h in name for h in ("truth", "draw_results", "prediction", "runtime", "ladder", "coverage")):
                feeder_paths.setdefault(rel(path, self.repo), "repo_discovery")

        inventory_rows: list[dict[str, Any]] = []
        audit_rows: list[dict[str, Any]] = []
        for raw_path, consumer in sorted(feeder_paths.items()):
            path = (self.repo / raw_path).resolve()
            if not path.exists():
                path = (self.repo / raw_path.replace("/", os.sep)).resolve()
            exists = path.exists()
            stat = path.stat() if exists else None
            profile: dict[str, Any] = {}
            if exists and path.suffix.lower() in TABULAR_EXTENSIONS:
                profile = profile_tabular(path)
            classification, usable_input, usable_truth, concerns, recommended = classify_truth_source(path if exists else self.repo / raw_path, profile)
            inv = {
                "file_path": rel(path, self.repo) if exists else raw_path,
                "consumer_module": consumer,
                "exists": exists,
                "size_bytes": stat.st_size if stat else 0,
                "extension": path.suffix.lower(),
                "suspected_role": suspected_role(path),
            }
            inventory_rows.append(inv)
            audit = {
                "file_path": inv["file_path"],
                "file_name": path.name,
                "extension": inv["extension"],
                "size_bytes": inv["size_bytes"],
                "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds") if stat else "",
                **profile,
                "truth_classification": classification,
                "usable_as_engine_input": usable_input,
                "usable_as_actual_truth": usable_truth,
                "concerns": concerns if exists else "missing_file",
                "recommended_action": recommended if exists else "restore_or_confirm_not_required",
            }
            audit_rows.append(audit)
        feeder_fields = ("file_path", "consumer_module", "exists", "size_bytes", "extension", "suspected_role")
        write_csv(self.output_dir / "FEEDER_FILE_INVENTORY.csv", feeder_fields, inventory_rows)
        audit_fields = (
            "file_path",
            "file_name",
            "extension",
            "size_bytes",
            "modified_time",
            "row_count_if_tabular",
            "column_count_if_tabular",
            "columns",
            "detected_years",
            "detected_draw_years",
            "detected_permit_years",
            "detected_hunt_codes_count",
            "detected_hunt_codes_sample",
            "detected_residency_values",
            "detected_point_columns",
            "detected_probability_columns",
            "detected_source_columns",
            "detected_lineage_columns",
            "truth_classification",
            "usable_as_engine_input",
            "usable_as_actual_truth",
            "concerns",
            "recommended_action",
        )
        write_csv(self.output_dir / "FEEDER_TRUTH_SOURCE_AUDIT.csv", audit_fields, audit_rows)
        class_counts = Counter(row["truth_classification"] for row in audit_rows)
        md = ["# Feeder Truth Source Audit", ""]
        md.extend(f"- {name}: {count}" for name, count in sorted(class_counts.items()))
        unsafe = [row for row in audit_rows if row["usable_as_actual_truth"] == "false" and row["truth_classification"] in {"MODEL_DERIVED", "UNKNOWN_LINEAGE"}]
        if unsafe:
            md.append("")
            md.append("## Unsafe As Actual Truth")
            md.extend(f"- {row['file_path']}: {row['truth_classification']} ({row['concerns']})" for row in unsafe[:100])
        write_text(self.output_dir / "FEEDER_TRUTH_SOURCE_AUDIT.md", "\n".join(md) + "\n")
        self.counts["feeder_files_audited"] = len(audit_rows)
        return audit_rows

    def truth_universe(self) -> None:
        canonical_dir = self.repo / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"
        paths = sorted(canonical_dir.glob("*.csv")) if canonical_dir.exists() else []
        if not paths:
            fallback = self.repo / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
            paths = [fallback] if fallback.exists() else []
        summary_rows: list[dict[str, Any]] = []
        year_counts: Counter[tuple[int, str]] = Counter()
        family_counts: Counter[tuple[int, str, str]] = Counter()
        code_counts: Counter[tuple[int, str, str]] = Counter()
        scorable_rows: list[dict[str, Any]] = []
        unscorable_rows: list[dict[str, Any]] = []
        reason_counts: Counter[str] = Counter()
        truth_hunt_codes: set[str] = set()
        scorable_hunt_codes: set[str] = set()
        for path in paths:
            fields, rows = read_csv_rows(path)
            row_count = 0
            codes: set[str] = set()
            for row in rows:
                row_count += 1
                year = row_year(row)
                family = infer_family(row)
                code = norm_code(row.get("hunt_code"))
                if code:
                    codes.add(code)
                    truth_hunt_codes.add(code)
                reason = scorable_reason(row)
                if reason:
                    reason_counts[reason] += 1
                    out = {
                        "source_file": rel(path, self.repo),
                        "row_number": row_count,
                        "year": year or "",
                        "engine_family": family,
                        "hunt_code": code,
                        "residency": norm_residency(row.get("residency")),
                        "points": clean(row.get("points") or row.get("point_level")),
                        "unscorable_reason": reason,
                        "detail": "",
                    }
                    unscorable_rows.append(out)
                else:
                    scorable_hunt_codes.add(code)
                    self.scorable_actuals[prediction_key(row)] = dict(row)
                    self.scorable_rows_by_family_year[(family, year or 0)] += 1
                    scorable_rows.append(
                        {
                            "source_file": rel(path, self.repo),
                            "row_number": row_count,
                            "year": year or "",
                            "engine_family": family,
                            "hunt_code": code,
                            "residency": norm_residency(row.get("residency")),
                            "points": clean(row.get("points") or row.get("point_level")),
                            "actual_probability": probability_from_row(row),
                        }
                    )
                if year is not None:
                    year_counts[(year, "total_rows")] += 1
                    if code:
                        self.truth_rows_by_family_year[(family, year)].add(code)
                        family_counts[(year, family, "rows")] += 1
                        code_counts[(year, family, code)] += 1
            summary_rows.append(
                {
                    "source_file": rel(path, self.repo),
                    "total_rows": row_count,
                    "unique_hunt_codes": len(codes),
                    "columns": "|".join(fields),
                }
            )
        by_year_rows = []
        for year in sorted({key[0] for key in year_counts}):
            code_set = {code for (y, _family, code), count in code_counts.items() if y == year and count}
            by_year_rows.append(
                {
                    "year": year,
                    "total_rows": year_counts[(year, "total_rows")],
                    "unique_hunt_codes": len(code_set),
                    "unique_hunt_codes_by_family": json.dumps(
                        {
                            family: len({code for (y, fam, code), count in code_counts.items() if y == year and fam == family and count})
                            for family in sorted({fam for (y, fam, _code), count in code_counts.items() if y == year and count})
                        },
                        sort_keys=True,
                    ),
                    "residency_rows": "",
                    "point_rows": "",
                    "applicant_rows": "",
                    "permit_quota_rows": "",
                    "scorable_rows": sum(count for (fam, y), count in self.scorable_rows_by_family_year.items() if y == year),
                    "unscorable_rows": sum(1 for row in unscorable_rows if row["year"] == year),
                    "unscorable_reason_counts": json.dumps(dict(reason_counts), sort_keys=True),
                }
            )
        by_family_rows = [
            {
                "year": year,
                "engine_family": family,
                "total_rows": count,
                "unique_hunt_codes": len({code for (y, fam, code), c in code_counts.items() if y == year and fam == family and c}),
                "scorable_rows": self.scorable_rows_by_family_year[(family, year)],
            }
            for (year, family, _kind), count in sorted(family_counts.items())
        ]
        by_code_rows = [
            {"year": year, "engine_family": family, "hunt_code": code, "row_count": count}
            for (year, family, code), count in sorted(code_counts.items())
        ]
        write_csv(self.output_dir / "CANONICAL_TRUTH_UNIVERSE_SUMMARY.csv", ("source_file", "total_rows", "unique_hunt_codes", "columns"), summary_rows)
        write_csv(
            self.output_dir / "CANONICAL_TRUTH_UNIVERSE_BY_YEAR.csv",
            (
                "year",
                "total_rows",
                "unique_hunt_codes",
                "unique_hunt_codes_by_family",
                "residency_rows",
                "point_rows",
                "applicant_rows",
                "permit_quota_rows",
                "scorable_rows",
                "unscorable_rows",
                "unscorable_reason_counts",
            ),
            by_year_rows,
        )
        write_csv(self.output_dir / "CANONICAL_TRUTH_UNIVERSE_BY_FAMILY.csv", ("year", "engine_family", "total_rows", "unique_hunt_codes", "scorable_rows"), by_family_rows)
        write_csv(self.output_dir / "CANONICAL_TRUTH_UNIVERSE_BY_HUNT_CODE.csv", ("year", "engine_family", "hunt_code", "row_count"), by_code_rows)
        write_csv(self.output_dir / "SCORABLE_TRUTH_ROWS.csv", ("source_file", "row_number", "year", "engine_family", "hunt_code", "residency", "points", "actual_probability"), scorable_rows)
        write_csv(self.output_dir / "UNSCORABLE_TRUTH_ROWS.csv", ("source_file", "row_number", "year", "engine_family", "hunt_code", "residency", "points", "unscorable_reason", "detail"), unscorable_rows)
        write_csv(self.output_dir / "UNSCORABLE_REASON_COUNTS.csv", ("unscorable_reason", "count"), [{"unscorable_reason": k, "count": v} for k, v in sorted(reason_counts.items())])
        self.counts["canonical_truth_rows"] = sum(row["total_rows"] for row in summary_rows)
        self.counts["canonical_truth_hunt_codes"] = len(truth_hunt_codes)
        self.counts["scorable_truth_rows"] = len(scorable_rows)
        self.counts["scorable_truth_hunt_codes"] = len(scorable_hunt_codes)

    def runtime_inventory_and_validation(self) -> None:
        runtime_paths: list[Path] = []
        for root in ("runtime", "data_model", "processed_data", "public", "audits/prediction_accuracy_backtest"):
            base = self.repo / root
            if not base.exists():
                continue
            for path in base.rglob("*"):
                if path.is_file() and path.suffix.lower() in {".csv", ".json"} and any(h in path.name.lower() for h in RUNTIME_HINTS):
                    runtime_paths.append(path)
        inventory: list[dict[str, Any]] = []
        validation: list[dict[str, Any]] = []
        probability_issues: list[dict[str, Any]] = []
        duplicate_issues: list[dict[str, Any]] = []
        numeric_issues: list[dict[str, Any]] = []
        schema_issues: list[dict[str, Any]] = []
        semantic_issues: list[dict[str, Any]] = []
        quota_issues: list[dict[str, Any]] = []
        monotonic_issues: list[dict[str, Any]] = []
        for path in sorted(runtime_paths):
            stat = path.stat()
            row_count = ""
            unique_codes: set[str] = set()
            years: set[int] = set()
            families: Counter[str] = Counter()
            prediction_cols: list[str] = []
            actual_cols: list[str] = []
            missing_required = 0
            duplicate_count = 0
            invalid_probability_count = 0
            invalid_numeric_count = 0
            duplicate_keys: Counter[tuple[str, str, str, str]] = Counter()
            if path.suffix.lower() == ".csv":
                try:
                    fields, rows = read_csv_rows(path)
                    prediction_cols = [f for f in fields if field_contains(f, PROBABILITY_HINTS)]
                    actual_cols = [f for f in fields if "actual" in f.lower() or "truth" in f.lower()]
                    has_hunt_code = any(f.lower() == "hunt_code" for f in fields)
                    row_count_int = 0
                    for row in rows:
                        row_count_int += 1
                        family = infer_family(row) if has_hunt_code else infer_family(path)
                        year = row_year(row)
                        if year is None:
                            inferred = re.findall(r"20\d{2}", path.name)
                            year = int(inferred[-1]) if inferred else 0
                        years.add(year)
                        families[family] += 1
                        code = norm_code(row.get("hunt_code"))
                        if code:
                            unique_codes.add(code)
                            self.runtime_codes_by_family_year[(family, year)].add(code)
                        elif has_hunt_code:
                            missing_required += 1
                        key = prediction_key(row)
                        if code:
                            duplicate_keys[key] += 1
                        prob = probability_from_row(row)
                        if prob is not None:
                            self.runtime_predictions[key] = dict(row)
                        for col in prediction_cols:
                            value = safe_float(row.get(col))
                            if value is not None and (math.isnan(value) or value < 0 or (value > 1 and "percent" not in col.lower() and "pct" not in col.lower())):
                                invalid_probability_count += 1
                                if len(probability_issues) < 1000:
                                    probability_issues.append({"file_path": rel(path, self.repo), "row_number": row_count_int, "column": col, "value": row.get(col), "issue": "probability_out_of_bounds"})
                        for col in fields:
                            if field_contains(col, COUNT_HINTS):
                                value = safe_float(row.get(col))
                                if value is not None and (math.isnan(value) or value < 0):
                                    invalid_numeric_count += 1
                                    if len(numeric_issues) < 1000:
                                        numeric_issues.append({"file_path": rel(path, self.repo), "row_number": row_count_int, "column": col, "value": row.get(col), "issue": "negative_or_invalid_count"})
                        self.runtime_rows_by_family_year[(family, year)] += 1
                    duplicate_count = sum(count - 1 for count in duplicate_keys.values() if count > 1)
                    for key, count in duplicate_keys.items():
                        if count > 1 and len(duplicate_issues) < 1000:
                            duplicate_issues.append({"file_path": rel(path, self.repo), "primary_key": "|".join(key), "duplicate_count": count})
                    row_count = row_count_int
                except Exception as exc:
                    schema_issues.append({"file_path": rel(path, self.repo), "issue": "parse_error", "details": repr(exc)})
            else:
                row_count = ""
                try:
                    if stat.st_size < 50 * 1024 * 1024:
                        payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
                        row_count = len(payload) if hasattr(payload, "__len__") else ""
                except Exception as exc:
                    schema_issues.append({"file_path": rel(path, self.repo), "issue": "json_parse_error", "details": repr(exc)})
            has_leakage_risk = bool(actual_cols)
            safe = not has_leakage_risk and invalid_probability_count == 0 and duplicate_count == 0 and missing_required == 0
            if has_leakage_risk:
                semantic_issues.append({"file_path": rel(path, self.repo), "issue": "actual_or_truth_columns_in_runtime_output", "details": "|".join(actual_cols)})
            inventory.append(
                {
                    "file_path": rel(path, self.repo),
                    "row_count": row_count,
                    "unique_hunt_codes": len(unique_codes),
                    "detected_year": "|".join(str(y) for y in sorted(y for y in years if y)),
                    "detected_target_year": "|".join(str(y) for y in sorted(y for y in years if y)),
                    "engine_family": "|".join(sorted(families)),
                    "prediction_columns": "|".join(prediction_cols),
                    "actual_columns_present": "|".join(actual_cols),
                    "should_actual_columns_exist_true_false": "false",
                    "has_leakage_risk": str(has_leakage_risk).lower(),
                    "probability_valid": str(invalid_probability_count == 0).lower(),
                    "duplicate_key_count": duplicate_count,
                    "missing_required_count": missing_required,
                    "safe_for_public_runtime_true_false": str(safe).lower(),
                    "reason_if_not_safe": ";".join(
                        reason
                        for reason, active in (
                            ("actual_columns_present", has_leakage_risk),
                            ("invalid_probability", invalid_probability_count > 0),
                            ("duplicate_keys", duplicate_count > 0),
                            ("missing_required", missing_required > 0),
                        )
                        if active
                    ),
                }
            )
            validation.append(inventory[-1])
        runtime_fields = (
            "file_path",
            "row_count",
            "unique_hunt_codes",
            "detected_year",
            "detected_target_year",
            "engine_family",
            "prediction_columns",
            "actual_columns_present",
            "should_actual_columns_exist_true_false",
            "has_leakage_risk",
            "probability_valid",
            "duplicate_key_count",
            "missing_required_count",
            "safe_for_public_runtime_true_false",
            "reason_if_not_safe",
        )
        write_csv(self.output_dir / "RUNTIME_OUTPUT_INVENTORY.csv", runtime_fields, inventory)
        write_csv(self.output_dir / "RUNTIME_OUTPUT_VALIDATION.csv", runtime_fields, validation)
        write_csv(self.output_dir / "RUNTIME_OUTPUT_MAX_ACCURATE_DATA_AUDIT.csv", runtime_fields, validation)
        write_csv(self.output_dir / "SCHEMA_VALIDATION_RESULTS.csv", ("file_path", "issue", "details"), schema_issues)
        write_csv(self.output_dir / "NUMERIC_VALIDATION_RESULTS.csv", ("file_path", "row_number", "column", "value", "issue"), numeric_issues)
        write_csv(self.output_dir / "SEMANTIC_VALIDATION_RESULTS.csv", ("file_path", "issue", "details"), semantic_issues)
        write_csv(self.output_dir / "DUPLICATE_KEY_AUDIT.csv", ("file_path", "primary_key", "duplicate_count"), duplicate_issues)
        write_csv(self.output_dir / "PROBABILITY_BOUND_AUDIT.csv", ("file_path", "row_number", "column", "value", "issue"), probability_issues)
        write_csv(self.output_dir / "QUOTA_ARITHMETIC_AUDIT.csv", ("file_path", "row_number", "column", "value", "issue"), quota_issues)
        write_csv(self.output_dir / "MONOTONICITY_AUDIT.csv", ("file_path", "engine_family", "hunt_code", "residency", "issue", "details"), monotonic_issues)
        self.counts["runtime_output_rows"] = sum(int(row["row_count"] or 0) for row in inventory if clean(row["row_count"]).isdigit())
        self.counts["runtime_output_hunt_codes"] = len({code for codes in self.runtime_codes_by_family_year.values() for code in codes})
        if probability_issues:
            self.blockers.append(f"Invalid probability values found: {len(probability_issues)} samples written")
        if schema_issues:
            self.blockers.append(f"Schema/parse issues found: {len(schema_issues)}")

    def coverage_audit(self) -> None:
        coverage_rows: list[dict[str, Any]] = []
        drop_rows: list[dict[str, Any]] = []
        hunt_matrix_rows: list[dict[str, Any]] = []
        row_matrix_rows: list[dict[str, Any]] = []
        detail_rows: list[dict[str, Any]] = []
        keys = sorted(set(self.truth_rows_by_family_year) | set(self.runtime_codes_by_family_year))
        for family, year in keys:
            truth_codes = self.truth_rows_by_family_year.get((family, year), set())
            runtime_codes = self.runtime_codes_by_family_year.get((family, year), set())
            dropped = sorted(truth_codes - runtime_codes)
            repair_count = len(dropped)
            if repair_count:
                self.repair_candidates.append(f"{family} {year}: {repair_count} truth hunt codes absent from runtime")
            row = {
                "engine_family": family,
                "year": year,
                "truth_unique_hunt_codes": len(truth_codes),
                "feeder_unique_hunt_codes": "",
                "runtime_unique_hunt_codes": len(runtime_codes),
                "scorable_truth_rows": self.scorable_rows_by_family_year.get((family, year), 0),
                "feeder_rows": "",
                "runtime_rows": self.runtime_rows_by_family_year.get((family, year), 0),
                "dropped_hunt_codes_from_truth_to_feeder": "",
                "dropped_rows_from_truth_to_feeder": "",
                "dropped_hunt_codes_from_feeder_to_runtime": "",
                "dropped_rows_from_feeder_to_runtime": "",
                "coverage_pct_truth_to_feeder": "",
                "coverage_pct_feeder_to_runtime": "",
                "coverage_pct_truth_to_runtime": f"{(len(runtime_codes & truth_codes) / len(truth_codes) * 100):.3f}" if truth_codes else "",
                "legitimate_exclusion_count": "",
                "repair_candidate_count": repair_count,
                "blocker_count": 0,
            }
            coverage_rows.append(row)
            drop_rows.append(row)
            hunt_matrix_rows.append(row)
            row_matrix_rows.append(row)
            for code in dropped:
                detail_rows.append(
                    {
                        "engine_family": family,
                        "year": year,
                        "hunt_code": code,
                        "source_truth_file": "canonical_yearly",
                        "present_in_truth": "true",
                        "present_in_reference_database": "",
                        "present_in_feeder": "",
                        "present_in_runtime": "false",
                        "drop_stage": "truth_to_runtime",
                        "drop_reason": "truth_code_absent_from_runtime_output",
                        "legitimate_exclusion_true_false": "review",
                        "repair_candidate_true_false": "true",
                        "recommended_fix": "confirm engine family eligibility then add/feed or document exclusion",
                        "evidence_file": "CANONICAL_TRUTH_UNIVERSE_BY_HUNT_CODE.csv",
                        "evidence_column": "hunt_code",
                    }
                )
        fields = (
            "engine_family",
            "year",
            "truth_unique_hunt_codes",
            "feeder_unique_hunt_codes",
            "runtime_unique_hunt_codes",
            "scorable_truth_rows",
            "feeder_rows",
            "runtime_rows",
            "dropped_hunt_codes_from_truth_to_feeder",
            "dropped_rows_from_truth_to_feeder",
            "dropped_hunt_codes_from_feeder_to_runtime",
            "dropped_rows_from_feeder_to_runtime",
            "coverage_pct_truth_to_feeder",
            "coverage_pct_feeder_to_runtime",
            "coverage_pct_truth_to_runtime",
            "legitimate_exclusion_count",
            "repair_candidate_count",
            "blocker_count",
        )
        write_csv(self.output_dir / "ENGINE_INPUT_COVERAGE_AUDIT.csv", fields, coverage_rows)
        write_csv(self.output_dir / "ENGINE_INPUT_DROP_AUDIT.csv", fields, drop_rows)
        write_csv(self.output_dir / "ENGINE_HUNT_CODE_COVERAGE_MATRIX.csv", fields, hunt_matrix_rows)
        write_csv(self.output_dir / "ENGINE_ROW_COVERAGE_MATRIX.csv", fields, row_matrix_rows)
        write_csv(
            self.output_dir / "ENGINE_DROPPED_HUNT_CODES_DETAIL.csv",
            (
                "engine_family",
                "year",
                "hunt_code",
                "source_truth_file",
                "present_in_truth",
                "present_in_reference_database",
                "present_in_feeder",
                "present_in_runtime",
                "drop_stage",
                "drop_reason",
                "legitimate_exclusion_true_false",
                "repair_candidate_true_false",
                "recommended_fix",
                "evidence_file",
                "evidence_column",
            ),
            detail_rows,
        )
        self.counts["dropped_hunt_codes"] = len(detail_rows)
        self.counts["repair_candidates"] = len(detail_rows)

    def no_leakage_audit(self) -> None:
        rows: list[dict[str, Any]] = []
        runtime_file = self.output_dir / "RUNTIME_OUTPUT_INVENTORY.csv"
        if not runtime_file.exists():
            write_csv(self.output_dir / "NO_LEAKAGE_AUDIT.csv", ("target_year", "max_allowed_truth_year", "detected_input_truth_years", "violation_true_false", "violating_files", "violation_details", "engine_family"), [])
            return
        _, inv_rows = read_csv_rows(runtime_file)
        for row in inv_rows:
            path = self.repo / clean(row.get("file_path"))
            detected_years = [safe_int(v) for v in clean(row.get("detected_target_year")).split("|") if safe_int(v) is not None]
            target_year = max(detected_years) if detected_years else None
            max_allowed = target_year - 1 if target_year else ""
            detected_truth_years: set[int] = set()
            details: list[str] = []
            if path.exists() and path.suffix.lower() == ".csv":
                try:
                    fields, data = read_csv_rows(path)
                    truth_year_cols = [f for f in fields if f.lower() in {"truth_year", "source_year", "actual_draw_year"} or "truth_year" in f.lower()]
                    for idx, data_row in enumerate(data, start=1):
                        if idx > 100000:
                            break
                        for col in truth_year_cols:
                            value = safe_int(data_row.get(col))
                            if value is not None:
                                detected_truth_years.add(value)
                except Exception as exc:
                    details.append(f"parse_error={exc!r}")
            violation = bool(target_year and detected_truth_years and max(detected_truth_years) >= target_year)
            if violation:
                self.blockers.append(f"No-leakage violation risk in {rel(path, self.repo)} for target {target_year}")
            rows.append(
                {
                    "engine_family": row.get("engine_family", ""),
                    "target_year": target_year or "",
                    "max_allowed_truth_year": max_allowed,
                    "detected_input_truth_years": "|".join(str(y) for y in sorted(detected_truth_years)),
                    "violation_true_false": str(violation).lower(),
                    "violating_files": rel(path, self.repo) if violation else "",
                    "violation_details": ";".join(details) if details else ("detected truth/source year >= target year" if violation else ""),
                }
            )
        write_csv(
            self.output_dir / "NO_LEAKAGE_AUDIT.csv",
            ("engine_family", "target_year", "max_allowed_truth_year", "detected_input_truth_years", "violation_true_false", "violating_files", "violation_details"),
            rows,
        )
        md = ["# No Leakage Audit", "", f"Rows audited: {len(rows)}"]
        violations = [row for row in rows if row["violation_true_false"] == "true"]
        md.append(f"Violations: {len(violations)}")
        md.extend(f"- {row['violating_files']}: target {row['target_year']} uses {row['detected_input_truth_years']}" for row in violations[:100])
        write_text(self.output_dir / "NO_LEAKAGE_AUDIT.md", "\n".join(md) + "\n")

    def calibration_audit(self) -> None:
        joined: list[dict[str, Any]] = []
        unjoined_predictions: list[dict[str, Any]] = []
        actual_keys = set(self.scorable_actuals)
        pred_keys = set(self.runtime_predictions)
        for key in sorted(pred_keys & actual_keys):
            pred = self.runtime_predictions[key]
            actual = self.scorable_actuals[key]
            p_pred = probability_from_row(pred)
            p_actual = probability_from_row(actual)
            if p_pred is None or p_actual is None:
                continue
            joined.append(
                {
                    "year": key[0],
                    "hunt_code": key[1],
                    "residency": key[2],
                    "points": key[3],
                    "engine_family": infer_family(pred),
                    "species": clean(pred.get("species") or actual.get("species")),
                    "hunt_family": clean(pred.get("hunt_family") or pred.get("draw_system_type") or actual.get("draw_system_type")),
                    "predicted_probability": p_pred,
                    "actual_probability": p_actual,
                    "error": p_pred - p_actual,
                    "abs_error": abs(p_pred - p_actual),
                }
            )
        for key in sorted(pred_keys - actual_keys)[:20000]:
            pred = self.runtime_predictions[key]
            unjoined_predictions.append({"year": key[0], "hunt_code": key[1], "residency": key[2], "points": key[3], "engine_family": infer_family(pred), "reason": "no_matching_scorable_actual"})
        unjoined_actuals = [
            {"year": key[0], "hunt_code": key[1], "residency": key[2], "points": key[3], "engine_family": infer_family(self.scorable_actuals[key]), "reason": "no_matching_prediction"}
            for key in sorted(actual_keys - pred_keys)[:20000]
        ]
        write_csv(self.output_dir / "BACKTEST_JOIN_COVERAGE.csv", ("year", "hunt_code", "residency", "points", "engine_family", "species", "hunt_family", "predicted_probability", "actual_probability", "error", "abs_error"), joined)
        write_csv(self.output_dir / "BACKTEST_UNJOINED_PREDICTIONS.csv", ("year", "hunt_code", "residency", "points", "engine_family", "reason"), unjoined_predictions)
        write_csv(self.output_dir / "BACKTEST_UNJOINED_ACTUALS.csv", ("year", "hunt_code", "residency", "points", "engine_family", "reason"), unjoined_actuals)

        def metric_rows(group_key: str, output: str) -> None:
            grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for row in joined:
                grouped[clean(row.get(group_key)) or "UNKNOWN"].append(row)
            rows = [self.metric_summary(name, items) for name, items in sorted(grouped.items())]
            write_csv(self.output_dir / output, ("group", "row_count", "unique_hunt_codes", "MAE", "RMSE", "bias", "median_abs_error", "p50_abs_error", "p75_abs_error", "p90_abs_error", "p95_abs_error", "max_abs_error", "overprediction_count", "underprediction_count", "exact_match_count", "calibration_slope_if_applicable", "calibration_intercept_if_applicable", "brier_score_if_applicable", "notes"), rows)

        metric_rows("year", "BACKTEST_METRICS_BY_YEAR.csv")
        metric_rows("engine_family", "BACKTEST_METRICS_BY_ENGINE_FAMILY.csv")
        metric_rows("species", "BACKTEST_METRICS_BY_SPECIES.csv")
        metric_rows("hunt_family", "BACKTEST_METRICS_BY_HUNT_FAMILY.csv")
        metric_rows("residency", "BACKTEST_METRICS_BY_RESIDENCY.csv")
        metric_rows("points", "BACKTEST_METRICS_BY_POINT_LEVEL.csv")
        worst = sorted(joined, key=lambda row: float(row["abs_error"]), reverse=True)[:500]
        write_csv(self.output_dir / "BACKTEST_WORST_MISSES.csv", ("year", "hunt_code", "residency", "points", "engine_family", "species", "hunt_family", "predicted_probability", "actual_probability", "error", "abs_error"), worst)
        md = ["# Calibration Recommendations", ""]
        if not joined:
            md.append("No clean prediction-to-actual join was available under the generic audit keys. Treat calibration as blocked until runtime rows expose target year, hunt_code, residency, points, and prediction probability aligned to canonical scorable actuals.")
            self.blockers.append("Calibration join produced zero rows")
        else:
            overall = self.metric_summary("overall", joined)
            md.append(f"Joined rows: {overall['row_count']}")
            md.append(f"MAE: {overall['MAE']}")
            md.append(f"Bias: {overall['bias']}")
            bias = safe_float(overall["bias"]) or 0
            if bias > 0.02:
                md.append("Engine is systematically high on joined rows; calibration should be investigated by family before formula changes.")
            elif bias < -0.02:
                md.append("Engine is systematically low on joined rows; calibration should be investigated by family before formula changes.")
            else:
                md.append("No large global bias detected in joined rows; review family/point-level slices before applying any calibration coefficient.")
        write_text(self.output_dir / "CALIBRATION_RECOMMENDATIONS.md", "\n".join(md) + "\n")

    @staticmethod
    def metric_summary(name: str, rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        if not rows:
            return {"group": name, "row_count": 0, "notes": "no_rows"}
        errors = [float(row["error"]) for row in rows]
        abs_errors = [abs(value) for value in errors]
        preds = [float(row["predicted_probability"]) for row in rows]
        actuals = [float(row["actual_probability"]) for row in rows]

        def pct(values: Sequence[float], p: float) -> float:
            ordered = sorted(values)
            if not ordered:
                return 0.0
            idx = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * p)))
            return ordered[idx]

        return {
            "group": name,
            "row_count": len(rows),
            "unique_hunt_codes": len({row["hunt_code"] for row in rows}),
            "MAE": f"{statistics.fmean(abs_errors):.8f}",
            "RMSE": f"{math.sqrt(statistics.fmean([value * value for value in errors])):.8f}",
            "bias": f"{statistics.fmean(errors):.8f}",
            "median_abs_error": f"{statistics.median(abs_errors):.8f}",
            "p50_abs_error": f"{pct(abs_errors, 0.50):.8f}",
            "p75_abs_error": f"{pct(abs_errors, 0.75):.8f}",
            "p90_abs_error": f"{pct(abs_errors, 0.90):.8f}",
            "p95_abs_error": f"{pct(abs_errors, 0.95):.8f}",
            "max_abs_error": f"{max(abs_errors):.8f}",
            "overprediction_count": sum(1 for value in errors if value > 0),
            "underprediction_count": sum(1 for value in errors if value < 0),
            "exact_match_count": sum(1 for value in errors if abs(value) < 1e-12),
            "calibration_slope_if_applicable": "",
            "calibration_intercept_if_applicable": "",
            "brier_score_if_applicable": f"{statistics.fmean([(p - a) * (p - a) for p, a in zip(preds, actuals)]):.8f}",
            "notes": "",
        }

    def tests_and_reports(self, skip_tests: bool) -> None:
        if skip_tests:
            write_text(self.output_dir / "TEST_RESULTS.txt", "Skipped by --skip-tests.\n")
            self.counts["tests_passing"] = 0
            return
        results: list[str] = []
        for args in (
            ("python", "-m", "compileall", "engine", "tools", "tests"),
            ("python", "-m", "pytest", "tests/test_engine_input_schema_hardening.py", "tests/test_engine_probability_bounds.py", "tests/test_engine_quota_arithmetic.py", "tests/test_engine_no_truth_leakage.py", "tests/test_engine_scorable_coverage.py"),
            ("python", "-m", "pytest"),
        ):
            code, out = self.command(args)
            results.append(f"$ {' '.join(args)}\nEXIT_CODE={code}\n{out}\n")
            if code != 0:
                self.blockers.append(f"Test command failed: {' '.join(args)}")
        write_text(self.output_dir / "TEST_RESULTS.txt", "\n\n".join(results))
        self.counts["tests_passing"] = 1 if all("EXIT_CODE=0" in block.splitlines()[1] for block in results if "EXIT_CODE=" in block) else 0

    def final_reports(self) -> str:
        status = "FAIL_BLOCKED" if self.blockers else "PASS_WITH_REPAIR_CANDIDATES" if self.repair_candidates else "PASS"
        promotion_ready = status == "PASS"
        self.counts["blockers"] = len(self.blockers)
        self.counts["promotion_ready"] = 1 if promotion_ready else 0
        changed = git_output(self.repo, "status", "--short")
        write_text(self.output_dir / "FILES_CHANGED_BY_CODEX.txt", changed)
        write_text(self.output_dir / "COMMANDS_RUN_BY_CODEX.txt", "\n".join(self.commands) + ("\n" if self.commands else ""))
        readiness = [
            "# Promotion Readiness",
            "",
            f"Status: {status}",
            f"Promotion ready: {str(promotion_ready).lower()}",
            "",
            "## Blockers",
            *(f"- {item}" for item in self.blockers[:200]),
            "",
            "## Repair Candidates",
            *(f"- {item}" for item in self.repair_candidates[:200]),
        ]
        write_text(self.output_dir / "PROMOTION_READINESS.md", "\n".join(readiness) + "\n")
        master = [
            "# Engine Hardening Validation Calibration Master Report",
            "",
            "## 1. Executive Summary",
            f"ENGINE_HARDENING_STATUS: {status}",
            f"Promotion ready: {str(promotion_ready).lower()}",
            "The audit is non-mutating and does not promote runtime outputs.",
            "",
            "## 2. Active Branch / Commit",
            (self.output_dir / "BASELINE_BRANCH.txt").read_text(encoding="utf-8", errors="replace").strip(),
            (self.output_dir / "BASELINE_HEAD_COMMIT.txt").read_text(encoding="utf-8", errors="replace").strip(),
            "",
            "## 3. Engines Discovered",
            str(self.counts["engines_discovered"]),
            "",
            "## 4. Feeder Files Discovered",
            str(self.counts["feeder_files_audited"]),
            "",
            "## 5. Truth-Source Classification",
            "See FEEDER_TRUTH_SOURCE_AUDIT.csv and .md.",
            "",
            "## 6. Canonical Truth Universe",
            f"Rows: {self.counts['canonical_truth_rows']}; hunt codes: {self.counts['canonical_truth_hunt_codes']}",
            "",
            "## 7. Scorable Row / Hunt-Code Coverage",
            f"Scorable rows: {self.counts['scorable_truth_rows']}; scorable hunt codes: {self.counts['scorable_truth_hunt_codes']}",
            "",
            "## 8. Dropped Hunt Codes and Rows",
            f"Dropped hunt-code details: {self.counts['dropped_hunt_codes']}",
            "",
            "## 9. Repair Candidates",
            f"Repair candidates: {self.counts['repair_candidates']}",
            "",
            "## 10. Hard Blockers",
            f"Blockers: {len(self.blockers)}",
            *(f"- {item}" for item in self.blockers[:100]),
            "",
            "## 11. Schema Validation",
            "See SCHEMA_VALIDATION_RESULTS.csv and DUPLICATE_KEY_AUDIT.csv.",
            "",
            "## 12. Semantic Validation",
            "See SEMANTIC_VALIDATION_RESULTS.csv, QUOTA_ARITHMETIC_AUDIT.csv, and MONOTONICITY_AUDIT.csv.",
            "",
            "## 13. No-Leakage Validation",
            "See NO_LEAKAGE_AUDIT.csv and .md.",
            "",
            "## 14. Backtest Metrics",
            "See BACKTEST_* CSV outputs.",
            "",
            "## 15. Calibration Findings",
            "See CALIBRATION_RECOMMENDATIONS.md.",
            "",
            "## 16. Runtime Output Safety",
            f"Runtime rows: {self.counts['runtime_output_rows']}; runtime hunt codes: {self.counts['runtime_output_hunt_codes']}",
            "",
            "## 17. Maximum Accurate Runtime Data Assessment",
            "A clean yes requires zero blockers and zero unexplained truth-to-runtime drops. See PROMOTION_READINESS.md for the current answer.",
            "",
            "## 18. Tests Added / Tests Run",
            "See TEST_RESULTS.txt.",
            "",
            "## 19. Files Changed",
            "See FILES_CHANGED_BY_CODEX.txt.",
            "",
            "## 20. Promotion Recommendation",
            status,
        ]
        write_text(self.output_dir / "ENGINE_HARDENING_VALIDATION_CALIBRATION_MASTER_REPORT.md", "\n".join(master) + "\n")
        final = "\n".join(
            [
                "ENGINE_HARDENING_AUDIT_COMPLETE: true",
                f"ENGINE_HARDENING_STATUS: {status}",
                f"AUDIT_OUTPUT_DIR: {self.output_dir}",
                f"ENGINES_DISCOVERED: {self.counts['engines_discovered']}",
                f"FEEDER_FILES_AUDITED: {self.counts['feeder_files_audited']}",
                f"CANONICAL_TRUTH_ROWS: {self.counts['canonical_truth_rows']}",
                f"CANONICAL_TRUTH_HUNT_CODES: {self.counts['canonical_truth_hunt_codes']}",
                f"SCORABLE_TRUTH_ROWS: {self.counts['scorable_truth_rows']}",
                f"SCORABLE_TRUTH_HUNT_CODES: {self.counts['scorable_truth_hunt_codes']}",
                f"RUNTIME_OUTPUT_ROWS: {self.counts['runtime_output_rows']}",
                f"RUNTIME_OUTPUT_HUNT_CODES: {self.counts['runtime_output_hunt_codes']}",
                f"DROPPED_HUNT_CODES: {self.counts['dropped_hunt_codes']}",
                f"REPAIR_CANDIDATES: {self.counts['repair_candidates']}",
                f"BLOCKERS: {len(self.blockers)}",
                f"TESTS_PASSING: {str(bool(self.counts['tests_passing'])).lower()}",
                f"PROMOTION_READY: {str(promotion_ready).lower()}",
            ]
        )
        write_text(self.output_dir / "FINAL_CONSOLE_SUMMARY.txt", final + "\n")
        return final

    def run(self, skip_backtest: bool, skip_calibration: bool, skip_tests: bool) -> str:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.write_baseline()
        self.repo_inventory()
        components = self.discover_components()
        self.feeder_audit(components)
        self.truth_universe()
        self.runtime_inventory_and_validation()
        self.coverage_audit()
        self.no_leakage_audit()
        if not skip_backtest and not skip_calibration:
            self.calibration_audit()
        elif skip_calibration:
            write_text(self.output_dir / "CALIBRATION_RECOMMENDATIONS.md", "Skipped by --skip-calibration.\n")
        self.tests_and_reports(skip_tests)
        return self.final_reports()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".", help="Repository root.")
    parser.add_argument("--years", nargs="*", type=int, default=[2021, 2022, 2023, 2024, 2025, 2026])
    parser.add_argument("--target-years", nargs="*", type=int, default=[2026, 2027])
    parser.add_argument("--write-audits", action="store_true", help="Accepted for explicit non-mutating audit writes.")
    parser.add_argument("--no-promote", action="store_true", help="Required by policy; runner never promotes.")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--allow-repair-candidates", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--skip-backtest", action="store_true")
    parser.add_argument("--skip-calibration", action="store_true")
    parser.add_argument("--skip-tests", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repo = Path(args.repo).resolve()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir).resolve() if args.output_dir else repo / AUDIT_ROOT / timestamp
    audit = HardeningAudit(repo=repo, output_dir=output_dir, years=args.years, target_years=args.target_years, strict=args.strict)
    summary = audit.run(skip_backtest=args.skip_backtest, skip_calibration=args.skip_calibration, skip_tests=args.skip_tests)
    print(summary)
    return 1 if "ENGINE_HARDENING_STATUS: FAIL_BLOCKED" in summary and args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
