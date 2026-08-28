#!/usr/bin/env python3
"""Describe the exact, local-only split Research release candidate.

This produces a future deployment runbook from immutable R2 review copies and
the validated candidate artifacts.  It has no network calls and cannot write
to R2, site files, or processed_data.
"""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CERTIFICATION_ROOT = ROOT / "audits" / "prediction_blind_backtests" / "2025_to_2026_truth_2018_2026_20260827_certification_candidate"
CANDIDATE_ROOT = CERTIFICATION_ROOT / "research_split_contract_candidate_2026-08-27"
REVIEW_ROOT = CERTIFICATION_ROOT / "r2_review_copy_2026-08-27" / "r2_snapshot" / "processed_data"
FROZEN_PREDICTION = ROOT / "processed_data" / "draw_reality_engine_predictive_v2.csv"
OUTPUT = CANDIDATE_ROOT / "release_readiness_manifest.json"
FROZEN_SHA256 = "9e4c0f1a66678cd63df88512e45ba71d63746a6b21d7e4038fecb142f40e9d5e"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def first_json_object(path: Path) -> dict[str, object]:
    """Read only the first item of a large JSON array."""
    with path.open("rb") as handle:
        sample = handle.read(2 * 1024 * 1024).decode("utf-8-sig", errors="replace").lstrip()
    if not sample.startswith("["):
        raise ValueError(f"Expected JSON array: {path}")
    start = sample.find("{")
    if start < 0:
        return {}
    depth = 0
    string = False
    escaped = False
    for index, char in enumerate(sample[start:], start):
        if string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                string = False
        elif char == '"':
            string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                result = json.loads(sample[start:index + 1])
                return result if isinstance(result, dict) else {}
    raise ValueError(f"Could not parse first JSON item: {path}")


def schema(path: Path) -> dict[str, object]:
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            fields = next(reader, [])
            data_rows = sum(1 for _ in reader)
        return {"kind": "csv", "field_count": len(fields), "fields": fields, "data_rows": data_rows}
    with path.open("rb") as handle:
        leading = handle.read(4096).decode("utf-8-sig", errors="replace").lstrip()
    if leading.startswith("["):
        return {"kind": "json_array", "first_item_keys": sorted(first_json_object(path))}
    if leading.startswith("{"):
        with path.open("r", encoding="utf-8-sig") as handle:
            value = json.load(handle)
        if isinstance(value, dict):
            return {"kind": "json_object", "top_level_keys": sorted(value)}
    return {"kind": "unknown"}


def schema_compatibility(remote: dict[str, object], candidate: dict[str, object]) -> dict[str, object]:
    if remote["kind"] != candidate["kind"]:
        return {"compatible": False, "reason": "ARTIFACT_KIND_CHANGED"}
    if remote["kind"] == "csv":
        remote_fields = set(remote["fields"])
        candidate_fields = set(candidate["fields"])
        missing = sorted(remote_fields - candidate_fields)
        return {
            "compatible": not missing,
            "remote_fields_missing_from_candidate": missing,
            "candidate_extra_field_count": len(candidate_fields - remote_fields),
        }
    if remote["kind"] == "json_array":
        remote_keys = set(remote["first_item_keys"])
        candidate_keys = set(candidate["first_item_keys"])
        missing = sorted(remote_keys - candidate_keys)
        return {
            "compatible": not missing,
            "remote_first_item_keys_missing_from_candidate": missing,
            "candidate_extra_first_item_key_count": len(candidate_keys - remote_keys),
        }
    if remote["kind"] == "json_object":
        remote_keys = set(remote["top_level_keys"])
        candidate_keys = set(candidate["top_level_keys"])
        missing = sorted(remote_keys - candidate_keys)
        return {
            "compatible": not missing,
            "remote_top_level_keys_missing_from_candidate": missing,
            "candidate_extra_top_level_key_count": len(candidate_keys - remote_keys),
        }
    return {"compatible": False, "reason": "UNSUPPORTED_ARTIFACT_KIND"}


def record(path: Path) -> dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(path)
    return {
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "schema": schema(path),
    }


def main() -> int:
    if OUTPUT.exists():
        raise SystemExit(f"Refusing to overwrite existing manifest: {OUTPUT}")
    validation_path = CANDIDATE_ROOT / "candidate_contract_validation.json"
    scope_path = CANDIDATE_ROOT / "candidate_index_scope_reconciliation.json"
    build_audit_path = CANDIDATE_ROOT / "candidate_build_audit.json"
    for required in (validation_path, scope_path, build_audit_path, FROZEN_PREDICTION):
        if not required.exists():
            raise SystemExit(f"Required evidence is missing: {required}")
    if sha256(FROZEN_PREDICTION) != FROZEN_SHA256:
        raise SystemExit("Frozen local predictive CSV hash no longer matches certification.")

    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    scope = json.loads(scope_path.read_text(encoding="utf-8"))
    build_audit = json.loads(build_audit_path.read_text(encoding="utf-8"))
    if validation.get("status") != "PASS" or scope.get("status") != "CURRENT_INDEX_SCOPE_RECONCILED":
        raise SystemExit("Candidate validation and current-index scope reconciliation must both pass.")

    # The fixed timestamp is a release-plan namespace only.  Before a future
    # authorized upload, the operator must make new hash-verified backups under
    # this prefix and replace it with that run's actual timestamp.
    rollback_namespace = "rollback/REPLACE_WITH_AUTHORIZED_R2_WRITE_TIMESTAMP"
    objects = [
        ("research_summary", "processed_data/hunt_research_2026_summary.json", "hunt_research_2026_summary.json", True, "NORMAL_SPLIT_CONTRACT"),
        ("research_index", "processed_data/hunt_research_2026_split/hunt_research_2026.index.json", "hunt_research_2026_split/hunt_research_2026.index.json", True, "NORMAL_SPLIT_CONTRACT"),
        ("research_ladder", "processed_data/hunt_research_2026_ladder.json", "hunt_research_2026_ladder.json", True, "NORMAL_SPLIT_CONTRACT"),
        ("research_details", "processed_data/hunt_research_2026_split/hunt_research_2026.details.json", "hunt_research_2026_split/hunt_research_2026.details.json", True, "NORMAL_SPLIT_CONTRACT"),
        ("point_ladder_csv", "processed_data/point_ladder_view.csv", "point_ladder_view.csv", False, "RUNTIME_SUPPORTING_ARTIFACT"),
        ("predictive_runtime_csv", "processed_data/draw_reality_engine_predictive_v2.csv", None, False, "LEGACY_FALLBACK_ONLY"),
    ]
    manifest_objects = []
    for role, r2_key, candidate_relative, normal_required, consumption in objects:
        remote_path = REVIEW_ROOT / r2_key.removeprefix("processed_data/")
        candidate_path = FROZEN_PREDICTION if candidate_relative is None else CANDIDATE_ROOT / "processed_data" / candidate_relative
        remote = record(remote_path)
        candidate = record(candidate_path)
        compatibility = schema_compatibility(remote["schema"], candidate["schema"])
        manifest_objects.append(
            {
                "role": role,
                "r2_key": r2_key,
                "normal_research_consumption": consumption,
                "required_by_normal_research": normal_required,
                "review_copy_current_r2": remote,
                "local_release_candidate": candidate,
                "schema_compatibility": compatibility,
                "required_rollback_backup_key": f"{rollback_namespace}/{r2_key}",
                "upload_disposition": "HOLD_NO_R2_WRITE_AUTHORIZATION",
            }
        )

    incompatible = [item["role"] for item in manifest_objects if not item["schema_compatibility"]["compatible"]]
    payload = {
        "schema_version": "1.0.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "LOCAL_ONLY_NO_NETWORK_NO_R2_WRITE",
        "status": "LOCAL_RELEASE_CANDIDATE_VALIDATED_R2_WRITE_NOT_AUTHORIZED",
        "candidate_root": str(CANDIDATE_ROOT.relative_to(ROOT)).replace("\\", "/"),
        "certified_frozen_prediction": {
            "path": str(FROZEN_PREDICTION.relative_to(ROOT)).replace("\\", "/"),
            "sha256": FROZEN_SHA256,
            "row_count": 40642,
        },
        "candidate_validation": {
            "path": str(validation_path.relative_to(ROOT)).replace("\\", "/"),
            "status": validation["status"],
            "frozen_prediction_keys_missing_from_ladder": validation["frozen_prediction_keys_missing_from_ladder"],
            "frozen_prediction_keys_missing_from_point_ladder": validation["frozen_prediction_keys_missing_from_point_ladder"],
        },
        "current_index_scope": {
            "path": str(scope_path.relative_to(ROOT)).replace("\\", "/"),
            "status": scope["status"],
            "current_declared_code_count": scope["current_declared_code_count"],
            "candidate_code_count_after": scope["candidate_code_count_after"],
            "summary_only_historical_reference_code_count": scope["removed_summary_only_code_count"],
        },
        "candidate_build": {
            "path": str(build_audit_path.relative_to(ROOT)).replace("\\", "/"),
            "frozen_prediction_rows": build_audit["frozen_prediction"]["rows"],
            "summary_exact_overlays": build_audit["overlay"]["summary_exact_overlays"],
            "ladder_exact_overlays": build_audit["overlay"]["ladder_exact_overlays"],
            "new_forecast_rows_in_ladder": build_audit["overlay"]["ladder_new_rows"],
            "preserved_reference_rows": build_audit["overlay"]["preserved_reference_rows"],
        },
        "objects": manifest_objects,
        "schema_incompatibilities": incompatible,
        "release_preconditions": [
            "Tyler explicitly authorizes the specific R2 upload/deployment action.",
            "At authorized release time, copy and SHA-256-verify every current live key to its listed rollback key before any replacement.",
            "Re-read live R2 objects immediately before upload and confirm their hashes still equal this review snapshot, or regenerate this manifest from a new immutable review copy.",
            "Upload the reviewed normal split-contract set together: summary, index, ladder, and details. Do not mix candidate and old split-contract members.",
            "Run the local contract validator and actual Research-page smoke tests against the staged/released objects before calling the release complete.",
        ],
        "explicit_non_actions": [
            "No R2 object was uploaded, overwritten, deleted, or cache-purged.",
            "No production page, configuration, deployment, Git index, commit, or push was changed.",
            "The predictive CSV is documented for rollback parity but is not loaded by the normal split-contract Research runtime.",
        ],
    }
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print("CERTIFIED_RESEARCH_RELEASE_MANIFEST=PASS")
    print(f"MANIFEST={OUTPUT.relative_to(ROOT)}")
    print(f"OBJECTS={len(manifest_objects)}")
    print(f"SCHEMA_INCOMPATIBILITIES={len(incompatible)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
