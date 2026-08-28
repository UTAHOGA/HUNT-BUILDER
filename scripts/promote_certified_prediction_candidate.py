#!/usr/bin/env python3
"""Promote one frozen, certified prediction candidate into local processed_data.

This is deliberately a *local* promotion.  It neither contacts R2 nor deploys
the website.  Every overwritten local artifact is copied to a timestamped
audit backup first, and the promoted manifest records the frozen audit hash.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE = REPO / "audits" / "prediction_blind_backtests" / "2025_to_2026_truth_2018_2026_20260827_certification_candidate"
PROCESSED = REPO / "processed_data"
DATABASE = REPO / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def zero_row_count(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def promote(candidate: Path, apply: bool) -> dict[str, Any]:
    prediction_dir = candidate / "prediction_phase"
    comparison_dir = candidate / "comparison_phase"
    locked_path = candidate / "locked_prediction_manifest.json"
    source_manifest_path = prediction_dir / "utah_bonus_predictive_manifest.json"
    summary_path = comparison_dir / "comparison_summary.json"
    required = [prediction_dir, comparison_dir, locked_path, source_manifest_path, summary_path, DATABASE]
    missing = [str(path.relative_to(REPO)) if path.is_relative_to(REPO) else str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Promotion candidate is incomplete: {missing}")

    summary = read_json(summary_path)
    if summary.get("unexpected_unmatched_actual_keys") != 0:
        raise ValueError("Candidate has unexpected actual key gaps; local promotion is blocked.")
    if summary.get("duplicate_actual_key_groups") != 0 or summary.get("duplicate_prediction_key_groups") != 0:
        raise ValueError("Candidate has unresolved duplicate prediction or actual keys; local promotion is blocked.")

    locked = read_json(locked_path)
    frozen = locked.get("frozen_prediction") or {}
    frozen_path = REPO / str(frozen.get("path", ""))
    frozen_hash = str(frozen.get("sha256", ""))
    if not frozen_path.exists() or sha256(frozen_path) != frozen_hash:
        raise ValueError("Frozen prediction path/hash no longer matches the locked candidate manifest.")

    source_manifest = read_json(source_manifest_path)
    source_outputs = source_manifest.get("output_files") or {}
    copied: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    backup_root = candidate / "local_promotion_backups" / utc_stamp()

    # draw_reality_engine_v2.csv is the observed-truth input copy. It is not a
    # forecast artifact and the candidate intentionally removes its temporary
    # copy after scoring. Preserve the existing local observed runtime instead.
    for logical_name, source_value in source_outputs.items():
        source = REPO / str(source_value)
        if logical_name == "draw_reality_engine_v2.csv":
            skipped.append({"logical_name": logical_name, "reason": "candidate temporary observed-truth copy intentionally removed"})
            continue
        if not source.exists():
            raise FileNotFoundError(f"Candidate output is missing: {logical_name} at {source}")
        target = PROCESSED / logical_name
        record: dict[str, Any] = {
            "logical_name": logical_name,
            "source": str(source.relative_to(REPO)),
            "source_sha256": sha256(source),
            "target": str(target.relative_to(REPO)),
            "target_existed": target.exists(),
        }
        if target.exists():
            backup = backup_root / logical_name
            record["prior_target_sha256"] = sha256(target)
            record["backup"] = str(backup.relative_to(REPO))
            if apply:
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
        if apply:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            record["target_sha256"] = sha256(target)
            if record["target_sha256"] != record["source_sha256"]:
                raise RuntimeError(f"Hash mismatch after local promotion: {logical_name}")
        copied.append(record)

    promoted_manifest = dict(source_manifest)
    promoted_manifest["output_files"] = {
        name: str((PROCESSED / name).relative_to(REPO))
        for name in source_outputs
        if name != "draw_reality_engine_v2.csv"
    }
    promoted_manifest["output_row_counts"] = {
        name: value
        for name, value in (source_manifest.get("output_row_counts") or {}).items()
        if name != "draw_reality_engine_v2.csv"
    }
    promoted_manifest["local_promotion_provenance"] = {
        "status": "LOCAL_REBUILT_HOSTED_EQUIVALENCE_PENDING",
        "promoted_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_candidate": str(candidate.relative_to(REPO)),
        "source_candidate_manifest_sha256": sha256(source_manifest_path),
        "locked_prediction_manifest": str(locked_path.relative_to(REPO)),
        "frozen_prediction_sha256": frozen_hash,
        "blind_comparison_summary_sha256": sha256(summary_path),
        "database_sha256_at_promotion": sha256(DATABASE),
        "expected_unmatched_actual_key_groups": 0,
        "expected_duplicate_actual_key_groups": 0,
        "expected_duplicate_prediction_key_groups": 0,
        "hosted_action": "NONE",
        "observed_runtime_artifact": "processed_data/draw_reality_engine_v2.csv preserved; it is not a frozen forecast output.",
    }

    promotion_summary = {
        "status": "DRY_RUN" if not apply else "LOCAL_PROMOTED_HOSTED_EQUIVALENCE_PENDING",
        "candidate": str(candidate.relative_to(REPO)),
        "frozen_prediction_sha256": frozen_hash,
        "database_sha256": sha256(DATABASE),
        "comparison": {
            "joined_keys": summary.get("joined_keys"),
            "unexpected_unmatched_actual_keys": summary.get("unexpected_unmatched_actual_keys"),
            "duplicate_actual_key_groups": summary.get("duplicate_actual_key_groups"),
            "duplicate_prediction_key_groups": summary.get("duplicate_prediction_key_groups"),
        },
        "copied_artifacts": copied,
        "skipped_artifacts": skipped,
        "backup_root": str(backup_root.relative_to(REPO)),
        "hosted_action": "NONE",
    }
    if apply:
        manifest_target = PROCESSED / "utah_bonus_predictive_manifest.json"
        manifest_target.write_text(json.dumps(promoted_manifest, indent=2) + "\n", encoding="utf-8")
        promotion_summary["promoted_manifest_sha256"] = sha256(manifest_target)
        audit_path = candidate / "local_prediction_promotion_summary.json"
        audit_path.write_text(json.dumps(promotion_summary, indent=2) + "\n", encoding="utf-8")
        (PROCESSED / "local_prediction_promotion_2026.json").write_text(
            json.dumps(promotion_summary, indent=2) + "\n", encoding="utf-8"
        )
    return promotion_summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", default=str(DEFAULT_CANDIDATE))
    parser.add_argument("--apply", action="store_true", help="Perform the local artifact replacement after all certification checks pass.")
    args = parser.parse_args()
    candidate = Path(args.candidate)
    if not candidate.is_absolute():
        candidate = REPO / candidate
    print(json.dumps(promote(candidate, args.apply), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
