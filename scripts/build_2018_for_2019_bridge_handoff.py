"""Build compact 2018_for_2019 bridge handoff.

This creates manifests/specs only. It does not export external comparables or
create joined truth-vs-prediction files.
"""

from __future__ import annotations

import csv
import hashlib
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Set


REPO_ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT_DIR = REPO_ROOT / "audits" / "year_to_year_key_correction20260721_021528" / "year_checkpoints" / "2018_for_2019"
PREDICTION_FILE = REPO_ROOT / "audits" / "progressive_prediction_audit" / "20260721_youth_turkey_program_start_fix" / "runs" / "2019" / "family_predictions.csv"
TRUTH_FILE = REPO_ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly" / "draw_results_2018_for_2019_canonical_yearly_draw_results.csv"
CWMU_DIR = REPO_ROOT / "audits" / "2018_prediction_repair_blind20260721_020854"
CWMU_KEYED = CWMU_DIR / "2018_CWMU_TRUTH_KEYED_DEDUPED.csv"
CWMU_LOCK = CWMU_DIR / "2018_CWMU_TRUTH_LOCK_MANIFEST.md"
LOCK_DIR = REPO_ROOT / "audits" / "year_to_year_key_correction20260721_021528"

FULL_YEAR_OFFICIAL_KEY_STATUS = "REVIEW_REQUIRED_CANONICAL_TRUTH_MISSING_OFFICIAL_SCORE_KEY_V2"
CWMU_STATUS = "PASS_CWMU_BRIDGED_BLIND"
BRIDGE_STATUS = "READY_FOR_CHATGPT_OR_USER_SIDE_BUILD"


def rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def count_csv(path: Path) -> int:
    if not path.exists() or path.stat().st_size == 0:
        return 0
    with path.open("rb") as f:
        return max(sum(chunk.count(b"\n") for chunk in iter(lambda: f.read(1024 * 1024), b"")) - 1, 0)


def prediction_health(path: Path) -> Dict[str, object]:
    rows = 0
    hunts: Set[str] = set()
    keys = Counter()
    blank_keys = 0
    family_counts = Counter()
    official_present = False
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        official_present = "official_score_key_v2" in (reader.fieldnames or [])
        for row in reader:
            rows += 1
            hunt_code = (row.get("hunt_code") or "").strip()
            if hunt_code:
                hunts.add(hunt_code)
            family = (row.get("family") or row.get("engine_family") or "").strip() or "UNKNOWN"
            family_counts[family] += 1
            key = (row.get("official_score_key_v2") or "").strip()
            if key:
                keys[key] += 1
            else:
                blank_keys += 1
    duplicate_key_groups = sum(1 for count in keys.values() if count > 1)
    duplicate_key_rows = sum(count for count in keys.values() if count > 1)
    return {
        "rows": rows,
        "unique_hunt_codes": len(hunts),
        "official_score_key_v2_present": official_present,
        "blank_keys": blank_keys,
        "duplicate_key_groups": duplicate_key_groups,
        "duplicate_key_rows": duplicate_key_rows,
        "unique_keys": len(keys),
        "family_counts": family_counts,
    }


def csv_key_health(path: Path, key_col: str) -> Dict[str, object]:
    rows = 0
    keys = Counter()
    blanks = 0
    present = False
    hunts: Set[str] = set()
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        present = key_col in (reader.fieldnames or [])
        for row in reader:
            rows += 1
            code = (row.get("hunt_code") or "").strip()
            if code:
                hunts.add(code)
            key = (row.get(key_col) or "").strip()
            if present and key:
                keys[key] += 1
            else:
                blanks += 1
    return {
        "rows": rows,
        "unique_hunt_codes": len(hunts),
        "key_present": present,
        "blank_keys": blanks,
        "unique_keys": len(keys),
        "duplicate_key_groups": sum(1 for count in keys.values() if count > 1),
        "duplicate_key_rows": sum(count for count in keys.values() if count > 1),
    }


def file_row(file_role: str, path: Path, required_for: str, review_status: str, notes: str = "") -> Dict[str, object]:
    row_count = count_csv(path) if path.suffix.lower() == ".csv" else ""
    return {
        "file_role": file_role,
        "path": rel(path),
        "file_name": path.name,
        "row_count_if_csv": row_count,
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "required_for": required_for,
        "review_status": review_status,
        "notes": notes,
    }


def write_csv(path: Path, rows: Iterable[Dict[str, object]], fieldnames: List[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def main() -> int:
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().isoformat(timespec="seconds")

    pred = prediction_health(PREDICTION_FILE)
    truth = csv_key_health(TRUTH_FILE, "official_score_key_v2")
    cwmu = csv_key_health(CWMU_KEYED, "official_score_key_v2")

    manifest_path = CHECKPOINT_DIR / "2018_FOR_2019_BRIDGE_HANDOFF_MANIFEST.md"
    required_path = CHECKPOINT_DIR / "2018_FOR_2019_BRIDGE_REQUIRED_FILES.csv"
    spec_path = CHECKPOINT_DIR / "2018_FOR_2019_BRIDGE_BUILD_SPEC.md"

    required_rows = [
        file_row("canonical_truth_file", TRUTH_FILE, "full-year bridge truth source", "REVIEW_REQUIRED", "canonical truth lacks official_score_key_v2"),
        file_row("prediction_package", PREDICTION_FILE, "prediction side exact-key bridge input", "PASS", "official_score_key_v2 present; bulky file listed only"),
        file_row("blind_cwmu_keyed_truth", CWMU_KEYED, "CWMU bridged truth input", CWMU_STATUS, "clean blind keyed CWMU truth"),
        file_row("cwmu_truth_lock_manifest", CWMU_LOCK, "CWMU blindness certification", CWMU_STATUS, "TRUTH_LOCKED_BEFORE_PREDICTION_ACCESS = TRUE"),
        file_row("checkpoint_report", CHECKPOINT_DIR / "2018_FOR_2019_CHECKPOINT_REPORT.md", "checkpoint review", "PASS_WITH_REVIEW_REQUIRED"),
        file_row("checkpoint_counts", CHECKPOINT_DIR / "2018_FOR_2019_CHECKPOINT_COUNTS.csv", "checkpoint row/key counts", "PASS_WITH_REVIEW_REQUIRED"),
        file_row("checkpoint_key_audit", CHECKPOINT_DIR / "2018_FOR_2019_KEY_AUDIT.csv", "checkpoint key health", "PASS_WITH_REVIEW_REQUIRED"),
        file_row("unmatched_truth_summary", CHECKPOINT_DIR / "2018_FOR_2019_UNMATCHED_TRUTH_SUMMARY.csv", "bridge review diagnostics", "REVIEW_REQUIRED"),
        file_row("unmatched_prediction_summary", CHECKPOINT_DIR / "2018_FOR_2019_UNMATCHED_PREDICTION_SUMMARY.csv", "bridge review diagnostics", "REVIEW_REQUIRED"),
        file_row("cwmu_blindness_audit", CHECKPOINT_DIR / "2018_FOR_2019_CWMU_BLINDNESS_AUDIT.md", "CWMU blindness review", CWMU_STATUS),
        file_row("key_correction_summary", LOCK_DIR / "YEAR_TO_YEAR_KEY_CORRECTION_SUMMARY.csv", "locked year-to-year key counts", "PASS_WITH_REVIEW_REQUIRED"),
        file_row("source_lineage_audit", LOCK_DIR / "YEAR_TO_YEAR_SOURCE_LINEAGE_AUDIT.csv", "source lineage review", "LOCKED"),
        file_row("duplicate_key_audit", LOCK_DIR / "YEAR_TO_YEAR_DUPLICATE_KEY_AUDIT.csv", "duplicate key review", "REVIEW_REQUIRED"),
        file_row("key_conflict_review", LOCK_DIR / "YEAR_TO_YEAR_KEY_CONFLICT_REVIEW.csv", "key conflict review", "REVIEW_REQUIRED"),
        file_row("cwmu_score_summary", CWMU_DIR / "2018_TO_2019_BRIDGED_CONTRACT_SCORE_SUMMARY.csv", "CWMU post-lock scoring evidence", CWMU_STATUS),
        file_row("cwmu_repair_certification", CWMU_DIR / "2018_PREDICTION_ENGINE_REPAIR_CERTIFICATION.md", "CWMU blind repair certification", CWMU_STATUS),
    ]
    write_csv(
        required_path,
        required_rows,
        ["file_role", "path", "file_name", "row_count_if_csv", "size_bytes", "sha256", "required_for", "review_status", "notes"],
    )

    family_lines = [
        f"- {family}: {count}"
        for family, count in sorted(pred["family_counts"].items())  # type: ignore[union-attr]
    ]
    manifest_lines = [
        "# 2018 For 2019 Bridge Handoff Manifest",
        "",
        f"handoff_timestamp: {timestamp}",
        "YEAR_CHECKPOINT=2018_FOR_2019",
        f"FULL_YEAR_OFFICIAL_KEY_STATUS={FULL_YEAR_OFFICIAL_KEY_STATUS}",
        f"2018_FOR_2019_CWMU_STATUS={CWMU_STATUS}",
        "YEAR_CHECKPOINT_STATUS=PASS_WITH_REVIEW_REQUIRED",
        f"BRIDGE_BUILD_STATUS={BRIDGE_STATUS}",
        "CODEX_DID_NOT_BUILD_EXTERNAL_BRIDGE = TRUE",
        "CHATGPT_OR_USER_BUILDS_TEST_AGAINST_BRIDGE_AFTER_HANDOFF = TRUE",
        "EXTERNAL_OUTPUT_PATH_UNKNOWN_TO_CODEX = TRUE",
        "",
        "## Required Paths",
        "",
        f"canonical truth file path: `{rel(TRUTH_FILE)}`",
        f"prediction package path: `{rel(PREDICTION_FILE)}`",
        f"blind CWMU keyed truth path: `{rel(CWMU_KEYED)}`",
        f"CWMU lock manifest path: `{rel(CWMU_LOCK)}`",
        f"checkpoint report path: `{rel(CHECKPOINT_DIR / '2018_FOR_2019_CHECKPOINT_REPORT.md')}`",
        "",
        "## Prediction-Side Key Health",
        "",
        f"row count: `{pred['rows']}`",
        f"unique hunt-code count: `{pred['unique_hunt_codes']}`",
        f"official_score_key_v2 present: `{pred['official_score_key_v2_present']}`",
        f"blank official_score_key_v2 count: `{pred['blank_keys']}`",
        f"duplicate official_score_key_v2 count: `{pred['duplicate_key_groups']}`",
        f"duplicate official_score_key_v2 rows: `{pred['duplicate_key_rows']}`",
        f"unique official_score_key_v2 count: `{pred['unique_keys']}`",
        "",
        "## Prediction Family Counts",
        "",
        *family_lines,
        "",
        "## Truth-Side Bridge Inputs",
        "",
        f"canonical 2018 truth CSV exists: `{TRUTH_FILE.exists()}`",
        f"canonical 2018 truth rows: `{truth['rows']}`",
        f"canonical 2018 truth unique hunt codes: `{truth['unique_hunt_codes']}`",
        f"canonical 2018 truth official_score_key_v2 present: `{truth['key_present']}`",
        f"blind CWMU keyed truth exists: `{CWMU_KEYED.exists()}`",
        f"blind CWMU keyed rows: `{cwmu['rows']}`",
        f"blind CWMU unique CWMU hunt codes: `{cwmu['unique_hunt_codes']}`",
        f"blind CWMU duplicate keys: `{cwmu['duplicate_key_groups']}`",
        f"CWMU truth lock manifest exists: `{CWMU_LOCK.exists()}`",
        "",
        "## File Hashes",
        "",
    ]
    for row in required_rows:
        manifest_lines.append(f"- {row['path']}: {row['sha256']}")
    manifest_lines.extend(
        [
            "",
            "## Review Notes",
            "",
            "Full-year official-key bridge construction remains review-required because the canonical 2018 truth CSV does not carry official_score_key_v2.",
            "CWMU has a clean blind keyed/scored repair run and can be used as bridge evidence after handoff.",
            "No bulky joined bridge or external comparable was created by Codex.",
            "Do not proceed to 2019_for_2020 from this handoff.",
        ]
    )
    manifest_path.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")

    spec_lines = [
        "# 2018 For 2019 Bridge Build Spec",
        "",
        "This is a handoff specification only.",
        "",
        "## Inputs",
        "",
        f"- Prediction package: `{rel(PREDICTION_FILE)}`",
        f"- Canonical truth source: `{rel(TRUTH_FILE)}`",
        f"- Blind CWMU keyed truth: `{rel(CWMU_KEYED)}`",
        f"- CWMU lock manifest: `{rel(CWMU_LOCK)}`",
        f"- Required files manifest: `{rel(required_path)}`",
        "",
        "## Later User-Side Bridge Rules",
        "",
        "- Build the full-year bridge after this handoff, not inside this checkpoint.",
        "- Preserve the locked truth/key boundary.",
        "- Do not patch canonical truth in place while building the bridge.",
        "- Use the blind CWMU keyed truth as CWMU bridge evidence.",
        "- Keep bulky joined truth-vs-prediction outputs outside this Codex checkpoint.",
        "- If a full-year truth-key bridge is generated later, record hashes and row counts in a new reviewed handoff/result manifest.",
    ]
    spec_path.write_text("\n".join(spec_lines) + "\n", encoding="utf-8")

    print(
        "YEAR_CHECKPOINT=2018_FOR_2019\n"
        f"PREDICTION_PACKAGE={rel(PREDICTION_FILE)}\n"
        f"PREDICTION_ROWS={pred['rows']}\n"
        f"PREDICTION_BLANK_KEYS={pred['blank_keys']}\n"
        f"PREDICTION_DUPLICATE_KEYS={pred['duplicate_key_groups']}\n"
        f"BRIDGE_HANDOFF_MANIFEST={rel(manifest_path)}\n"
        f"BRIDGE_REQUIRED_FILES={rel(required_path)}\n"
        f"BRIDGE_BUILD_SPEC={rel(spec_path)}\n"
        f"FULL_YEAR_OFFICIAL_KEY_STATUS={FULL_YEAR_OFFICIAL_KEY_STATUS}\n"
        f"2018_FOR_2019_CWMU_STATUS={CWMU_STATUS}\n"
        f"BRIDGE_BUILD_STATUS={BRIDGE_STATUS}\n"
        "NEXT_ACTION=STOP_BEFORE_2019_FOR_2020\n",
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
