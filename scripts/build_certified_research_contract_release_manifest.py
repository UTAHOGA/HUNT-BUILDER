#!/usr/bin/env python3
"""Describe the exact, local-only split Research release candidate.

This produces a future deployment runbook from immutable R2 review copies and
the validated candidate artifacts.  It has no network calls and cannot write
to R2, site files, or processed_data.
"""

from __future__ import annotations

import argparse
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
            return {"kind": "json_object", "top_level_keys": sorted(value),
                    "empty_top_level_keys": sorted(k for k, v in value.items() if v in ("", None))}
    return {"kind": "unknown"}


def schema_compatibility(
    remote: dict[str, object],
    candidate: dict[str, object],
    allowed_removed_fields: set[str] | None = None,
) -> dict[str, object]:
    allowed_removed_fields = allowed_removed_fields or set()
    if remote["kind"] != candidate["kind"]:
        return {"compatible": False, "reason": "ARTIFACT_KIND_CHANGED"}
    if remote["kind"] == "csv":
        remote_fields = set(remote["fields"])
        candidate_fields = set(candidate["fields"])
        removed = remote_fields - candidate_fields
        missing = sorted(removed - allowed_removed_fields)
        return {
            "compatible": not missing,
            "remote_fields_missing_from_candidate": missing,
            "intentionally_removed_prediction_fields": sorted(removed & allowed_removed_fields),
            "candidate_extra_field_count": len(candidate_fields - remote_fields),
        }
    if remote["kind"] == "json_array":
        remote_keys = set(remote["first_item_keys"])
        candidate_keys = set(candidate["first_item_keys"])
        removed = remote_keys - candidate_keys
        missing = sorted(removed - allowed_removed_fields)
        return {
            "compatible": not missing,
            "remote_first_item_keys_missing_from_candidate": missing,
            "intentionally_removed_prediction_fields": sorted(removed & allowed_removed_fields),
            "candidate_extra_first_item_key_count": len(candidate_keys - remote_keys),
        }
    if remote["kind"] == "json_object":
        remote_keys = set(remote["top_level_keys"])
        candidate_keys = set(candidate["top_level_keys"])
        # The old details container accidentally carried three blank row-level
        # probability placeholders. They are not hunt records or container
        # metadata. Permit removing ONLY these proven-empty placeholders;
        # a nonempty probability, hunt key, or any other field remains blocking.
        empty_probability_placeholders = set(remote.get("empty_top_level_keys", [])) & {
            "certified_p_draw", "certified_p_draw_mean", "certified_p_draw_pct"
        }
        removed = remote_keys - candidate_keys
        missing = sorted(removed - empty_probability_placeholders)
        return {
            "compatible": not missing,
            "remote_top_level_keys_missing_from_candidate": missing,
            "removed_empty_container_probability_placeholders": sorted(removed & empty_probability_placeholders),
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


CORE_RELEASE_DESIGNS = {
    "BONUS_LE_BIG_GAME", "BONUS_OIL_BIG_GAME", "BONUS_PLE_BIG_GAME",
    "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
}


def certification_alignment_failures(predictions, registry):
    """Reject stale annotations even if the artifact's coverage/browser checks pass."""
    failures = []
    for design in sorted(CORE_RELEASE_DESIGNS):
        if registry.get("families", {}).get(design, {}).get("certification_status") != "CERTIFIED":
            failures.append(f"CORE_DESIGN_NOT_CERTIFIED:{design}")
    for row in predictions:
        design = row.get("prediction_certification_design") or row.get("draw_system_type")
        evidence = registry.get("families", {}).get(design, {})
        if str(row.get("certified_p_draw", "")).strip():
            if evidence.get("certification_status") != "CERTIFIED":
                failures.append(f"UNCERTIFIED_PUBLIC_PROBABILITY:{row.get('hunt_code')}:{row.get('residency')}:{row.get('points')}")
            if row.get("prediction_certification_registry_id") != registry.get("registry_id"):
                failures.append(f"STALE_CERTIFICATION_REGISTRY:{row.get('hunt_code')}:{row.get('residency')}:{row.get('points')}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=CANDIDATE_ROOT)
    parser.add_argument("--review-root", type=Path, default=REVIEW_ROOT)
    parser.add_argument("--prediction", type=Path, default=FROZEN_PREDICTION)
    parser.add_argument("--expected-prediction-sha256", default=FROZEN_SHA256)
    parser.add_argument("--coverage-report", type=Path, required=True)
    parser.add_argument("--certification-registry", type=Path, required=True)
    parser.add_argument("--classification-report", type=Path, required=True)
    args = parser.parse_args()
    resolve = lambda path: path if path.is_absolute() else ROOT / path
    candidate_root = resolve(args.candidate)
    review_root = resolve(args.review_root)
    frozen_prediction = resolve(args.prediction)
    coverage_path = resolve(args.coverage_report)
    registry_path = resolve(args.certification_registry)
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    with frozen_prediction.open(encoding="utf-8-sig", newline="") as handle:
        alignment_failures = certification_alignment_failures(csv.DictReader(handle), registry)
    if alignment_failures:
        raise SystemExit("Four-core release certification blockers: " + "; ".join(alignment_failures[:12]))
    classification = json.loads(resolve(args.classification_report).read_text(encoding="utf-8"))
    if classification.get("status") != "PASS":
        raise SystemExit("Pending source classifications have not all been resolved.")
    if classification.get("inputs", {}).get("prediction", {}).get("sha256") != sha256(frozen_prediction):
        raise SystemExit("Classification audit does not describe the release prediction file.")
    final_gate = registry.get("evidence", {}).get("final_probability_gate", {})
    if final_gate.get("status") != "PASS" or not final_gate.get("folds"):
        raise SystemExit("Exact final public probability has not passed historical scoring.")
    implementation_hash = sha256(ROOT / "engine/utah_predictive_mixed/materialize.py")
    if any(fold.get("implementation_sha256") != implementation_hash for fold in final_gate["folds"]):
        raise SystemExit("Final probability implementation changed after historical scoring.")
    if coverage.get("status") != "PASS" or coverage.get("failures") or not coverage.get("complete_eligible_accounting"):
        raise SystemExit("Independent eligible-hunt/residency coverage audit has blockers.")
    if coverage.get("sources", {}).get("prediction", {}).get("sha256") != sha256(frozen_prediction):
        raise SystemExit("Coverage audit does not describe the frozen release prediction file.")
    if not coverage.get("public_details_verified"):
        raise SystemExit("Coverage must verify every eligible lane in the actual public hunt details.")
    output = candidate_root / "release_readiness_manifest.json"
    if output.exists():
        raise SystemExit(f"Refusing to overwrite existing manifest: {output}")
    validation_path = candidate_root / "candidate_contract_validation.json"
    build_audit_path = candidate_root / "candidate_build_audit.json"
    browser_qa_path = candidate_root / "browser_qa.json"
    for required in (validation_path, build_audit_path, browser_qa_path, frozen_prediction):
        if not required.exists():
            raise SystemExit(f"Required evidence is missing: {required}")
    prediction_sha256 = sha256(frozen_prediction)
    if args.expected_prediction_sha256 and prediction_sha256 != args.expected_prediction_sha256:
        raise SystemExit("Frozen local predictive CSV hash no longer matches certification.")

    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    build_audit = json.loads(build_audit_path.read_text(encoding="utf-8"))
    browser_qa = json.loads(browser_qa_path.read_text(encoding="utf-8"))
    if build_audit.get("overlay", {}).get("protected_harvest_context_field_changes") != 0:
        raise SystemExit("Prediction-only release lacks proof that retained harvest context is unchanged.")
    if validation.get("status") != "PASS" or browser_qa.get("status") != "PASS":
        raise SystemExit("Candidate contract validation and browser QA must both pass.")
    if (browser_qa.get("independent_coverage_sha256") != sha256(coverage_path)
            or browser_qa.get("audited_prediction_sha256") != prediction_sha256):
        raise SystemExit("Browser QA is not bound to this exact coverage/prediction evidence.")
    expected_browser_lanes = sum(bool(row.get("forecast_points")) for row in coverage["inventory"])
    if browser_qa.get("eligible_forecast_lanes_tested") != expected_browser_lanes:
        raise SystemExit("Browser QA did not exercise every independently inventoried forecast lane.")
    accounted_lanes = sum(row["coverage_status"] != "HISTORICAL_REFERENCE_ONLY" for row in coverage["inventory"])
    if browser_qa.get("eligible_lanes_accounted_tested") != accounted_lanes:
        raise SystemExit("Browser QA did not verify withheld and zero-quota current lanes.")
    if not validation.get("summary_only_reference_scope_reconciled"):
        raise SystemExit("Candidate current-index scope is not reconciled.")

    # The fixed timestamp is a release-plan namespace only.  Before a future
    # authorized upload, the operator must make new hash-verified backups under
    # this prefix and replace it with that run's actual timestamp.
    rollback_namespace = "rollback/REPLACE_WITH_AUTHORIZED_R2_WRITE_TIMESTAMP"
    objects = [
        ("research_summary", "processed_data/hunt_research_2026_summary.json", "hunt_research_2026_summary.json", True, "NORMAL_SPLIT_CONTRACT"),
        ("research_index", "processed_data/hunt_research_2026_split/hunt_research_2026.index.json", "hunt_research_2026_split/hunt_research_2026.index.json", True, "NORMAL_SPLIT_CONTRACT"),
        ("research_ladder", "processed_data/hunt_research_2026_ladder.json", "hunt_research_2026_ladder.json", False, "SANITIZED_CANONICAL_ARCHIVE"),
        ("research_details", "processed_data/hunt_research_2026_split/hunt_research_2026.details.json", "hunt_research_2026_split/hunt_research_2026.details.json", True, "NORMAL_SPLIT_CONTRACT"),
        ("point_ladder_csv", "processed_data/point_ladder_view.csv", "point_ladder_view.csv", True, "NORMAL_SPLIT_CONTRACT"),
        ("predictive_runtime_csv", "processed_data/draw_reality_engine_predictive_v2.csv", "draw_reality_engine_predictive_v2.csv", False, "SANITIZED_LEGACY_FALLBACK"),
        ("ml_predictions_runtime_csv", "processed_data/ml_draw_predictions_v1.csv", "ml_draw_predictions_v1.csv", False, "SANITIZED_PUBLIC_DOWNLOAD"),
    ]
    allowed_removed_fields = set(build_audit["overlay"]["removed_raw_future_probability_fields"])
    allowed_removed_fields.update(build_audit["overlay"]["removed_legacy_guarantee_fields"])
    manifest_objects = []
    for role, r2_key, candidate_relative, normal_required, consumption in objects:
        remote_path = review_root / r2_key.removeprefix("processed_data/")
        candidate_path = candidate_root / "processed_data" / candidate_relative
        remote = record(remote_path)
        candidate = record(candidate_path)
        compatibility = schema_compatibility(remote["schema"], candidate["schema"], allowed_removed_fields)
        upload_disposition = (
            "UNCHANGED_OVERSIZED_NON_RUNTIME_ARCHIVE"
            if role == "research_ladder"
            else "AUTHORIZED_AFTER_LIVE_HASH_RECHECK_AND_ROLLBACK_BACKUP"
        )
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
                "upload_disposition": upload_disposition,
            }
        )

    incompatible = [item["role"] for item in manifest_objects if not item["schema_compatibility"]["compatible"]]
    if incompatible:
        raise SystemExit(f"Release artifact schemas are incompatible: {incompatible}")
    payload = {
        "schema_version": "1.0.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "AUTHORIZED_PROMOTION_PLAN_NO_WRITE_PERFORMED_BY_THIS_SCRIPT",
        "status": "LOCAL_RELEASE_CANDIDATE_VALIDATED_AUTHORIZED_PROMOTION_PENDING_EXECUTION",
        "candidate_root": str(candidate_root.relative_to(ROOT)).replace("\\", "/"),
        "certified_frozen_prediction": {
            "path": str(frozen_prediction.relative_to(ROOT)).replace("\\", "/"),
            "sha256": prediction_sha256,
            "row_count": validation["frozen_prediction_rows"],
        },
        "candidate_validation": {
            "path": str(validation_path.relative_to(ROOT)).replace("\\", "/"),
            "status": validation["status"],
            "frozen_prediction_keys_missing_from_ladder": validation["frozen_prediction_keys_missing_from_ladder"],
            "frozen_prediction_keys_missing_from_point_ladder": validation["frozen_prediction_keys_missing_from_point_ladder"],
        },
        "browser_qa": {
            "path": str(browser_qa_path.relative_to(ROOT)).replace("\\", "/"),
            "status": browser_qa["status"],
            "scenario_count": len(browser_qa["scenarios"]),
            "eligible_forecast_lanes_tested": expected_browser_lanes,
        },
        "independent_eligible_coverage": {
            "path": str(coverage_path.relative_to(ROOT)).replace("\\", "/"),
            "sha256": sha256(coverage_path),
            "status": coverage["status"],
            "coverage_status_counts": coverage["coverage_status_counts"],
            "complete_forecast_coverage": coverage["complete_forecast_coverage"],
            "complete_eligible_accounting": coverage["complete_eligible_accounting"],
        },
        "exact_final_probability_evidence": {
            "registry": str(registry_path.relative_to(ROOT)).replace("\\", "/"),
            "registry_sha256": sha256(registry_path),
            "implementation_sha256": implementation_hash,
            "fold_count": final_gate.get("fold_count"),
            "status": final_gate["status"],
        },
        "current_index_scope": {
            "status": "CURRENT_INDEX_SCOPE_RECONCILED",
            "current_declared_code_count": validation["declared_current_index_hunt_codes"],
            "candidate_code_count_after": validation["index_hunt_codes"],
            "summary_only_historical_reference_code_count": validation["summary_only_reference_hunt_codes"],
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
            "Record Tyler's current explicit authorization for this exact core-only promotion; an older release authorization is not sufficient.",
            "At authorized release time, copy and SHA-256-verify every current live key to its listed rollback key before any replacement.",
            "Re-read live R2 objects immediately before upload and confirm their hashes still equal this review snapshot, or regenerate this manifest from a new immutable review copy.",
            "Upload the six reviewed runtime/public artifacts together. Leave the oversized non-runtime ladder archive unchanged.",
            "Run the local contract validator and actual Research-page smoke tests against the staged/released objects before calling the release complete.",
        ],
        "explicit_non_actions": [
            "No R2 object was uploaded, overwritten, deleted, or cache-purged.",
            "No production page, configuration, deployment, Git index, commit, or push was changed.",
            "The predictive CSV is documented for rollback parity but is not loaded by the normal split-contract Research runtime.",
        ],
    }
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print("CERTIFIED_RESEARCH_RELEASE_MANIFEST=PASS")
    print(f"MANIFEST={output.relative_to(ROOT)}")
    print(f"OBJECTS={len(manifest_objects)}")
    print(f"SCHEMA_INCOMPATIBILITIES={len(incompatible)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
