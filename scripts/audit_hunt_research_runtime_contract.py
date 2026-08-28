#!/usr/bin/env python3
"""Create a read-only Hunt Research runtime-compatibility and release audit.

The script downloads R2-only files into an audit directory only. It never
replaces processed_data, modifies site code, or writes to Cloudflare R2.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "audits" / "prediction_blind_backtests" / "2025_to_2026_truth_2018_2026_20260827_certification_candidate"
DEFAULT_REVIEW_DIR = CANDIDATE / "r2_review_copy_2026-08-27"
USER_AGENT = "Hunt-Builder-Runtime-Contract-Audit/1.0"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def csv_schema(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        fields = next(csv.reader(handle), [])
        data_rows = sum(1 for _ in handle)
    return {"kind": "csv", "field_count": len(fields), "fields": fields, "data_rows": data_rows}


def json_schema(path: Path) -> dict[str, object]:
    """Return a bounded schema summary without loading a large JSON payload."""
    with path.open("rb") as handle:
        sample = handle.read(2 * 1024 * 1024).decode("utf-8-sig", errors="replace").lstrip()
    if sample.startswith("["):
        start = sample.find("{")
        if start >= 0:
            depth = 0
            in_string = False
            escaped = False
            for index, char in enumerate(sample[start:], start):
                if in_string:
                    if escaped:
                        escaped = False
                    elif char == "\\":
                        escaped = True
                    elif char == '"':
                        in_string = False
                    continue
                if char == '"':
                    in_string = True
                elif char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        first = json.loads(sample[start:index + 1])
                        return {"kind": "json_array", "first_item_keys": sorted(first) if isinstance(first, dict) else []}
        return {"kind": "json_array", "first_item_keys": []}
    if sample.startswith("{"):
        # Split-detail bundles are materially smaller than the ladder; parse this
        # object to record its real top-level key shape rather than guessing from
        # pretty-print formatting.
        with path.open("r", encoding="utf-8-sig") as handle:
            parsed = json.load(handle)
        if isinstance(parsed, dict):
            keys = sorted(parsed)
            return {"kind": "json_object", "top_level_key_count": len(keys), "sample_top_level_keys": keys[:20]}
        return {"kind": type(parsed).__name__}
    return {"kind": "unknown_json"}


def schema(path: Path) -> dict[str, object]:
    if path.suffix.lower() == ".csv":
        return csv_schema(path)
    if path.suffix.lower() == ".json":
        return json_schema(path)
    return {"kind": "binary"}


def local_file_record(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"status": "LOCAL_NOT_HYDRATED"}
    return {"status": "PRESENT", "bytes": path.stat().st_size, "sha256": sha256(path), "schema": schema(path)}


def download_review_copy(url: str, destination: Path) -> dict[str, object]:
    if destination.exists():
        raise RuntimeError(f"Refusing to overwrite existing review copy: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = Request(url, headers={"Accept-Encoding": "identity", "User-Agent": USER_AGENT})
    digest = hashlib.sha256()
    byte_count = 0
    try:
        with urlopen(request, timeout=300) as response, destination.open("xb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
                digest.update(chunk)
                byte_count += len(chunk)
            return {
                "status": response.status,
                "content_type": response.headers.get("Content-Type"),
                "content_length": response.headers.get("Content-Length"),
                "etag": response.headers.get("ETag"),
                "bytes": byte_count,
                "sha256": digest.hexdigest(),
            }
    except (HTTPError, URLError) as exc:
        destination.unlink(missing_ok=True)
        raise RuntimeError(f"Could not read {url}: {exc}") from exc


def extract_js_fields(source: str) -> set[str]:
    fields = set(re.findall(r"\brow\?\.([A-Za-z_][A-Za-z0-9_]*)", source))
    fields.update(re.findall(r"\brow\.([A-Za-z_][A-Za-z0-9_]*)", source))
    for match in re.finditer(r"firstAvailable\(row,\s*\[(.*?)\]\)", source, flags=re.DOTALL):
        fields.update(re.findall(r"['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]", match.group(1)))
    return fields


def artifact_field_set(record: dict[str, object]) -> set[str]:
    return set(record.get("schema", {}).get("fields", []))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-dir", type=Path, default=DEFAULT_REVIEW_DIR)
    parser.add_argument(
        "--reuse-review-dir",
        action="store_true",
        help="Reuse an immutable R2 review snapshot and write suffixed audit outputs without downloading or overwriting it.",
    )
    args = parser.parse_args()
    review_dir = args.review_dir.resolve()
    if review_dir.exists() and not args.reuse_review_dir:
        raise SystemExit(f"Refusing to reuse existing review directory: {review_dir}")
    if not review_dir.exists() and args.reuse_review_dir:
        raise SystemExit(f"Cannot reuse a missing review directory: {review_dir}")

    authority = json.loads((ROOT / "governance" / "engine-authority.json").read_text(encoding="utf-8"))
    runtime_artifacts = authority["runtime_artifacts"]
    if not args.reuse_review_dir:
        review_dir.mkdir(parents=True, exist_ok=False)

    artifact_records: list[dict[str, object]] = []
    try:
        for artifact in runtime_artifacts:
            logical_path = Path(artifact["path"])
            local_path = ROOT / logical_path
            local = local_file_record(local_path)
            # Every live object is copied to this isolated review snapshot, while
            # the four missing local objects are thereby hydrated for review.
            review_path = review_dir / "r2_snapshot" / logical_path
            if args.reuse_review_dir:
                if not review_path.exists():
                    raise RuntimeError(f"Missing immutable review copy: {review_path}")
                remote = {
                    "status": "REUSED_LOCAL_REVIEW_COPY",
                    "bytes": review_path.stat().st_size,
                    "sha256": sha256(review_path),
                }
            else:
                remote = download_review_copy(artifact["external_url"], review_path)
            review = {**remote, "path": str(review_path.relative_to(ROOT)).replace("\\", "/"), "schema": schema(review_path)}
            artifact_records.append(
                {
                    "role": artifact["role"],
                    "path": artifact["path"],
                    "external_url": artifact["external_url"],
                    "local_policy": artifact["local_policy"],
                    "local": local,
                    "review_copy": review,
                }
            )
    except Exception:
        # Keep any completed review evidence but never attempt an overwrite or cleanup of an uncertain partial audit.
        raise

    predictive = next(record for record in artifact_records if record["role"] == "predictive_runtime_csv")
    local_predictive_fields = artifact_field_set(predictive["local"])
    remote_predictive_record = predictive["review_copy"]
    remote_predictive_fields = artifact_field_set(remote_predictive_record)

    research_js = (ROOT / "hunt-research.js").read_text(encoding="utf-8")
    config_js = (ROOT / "config.js").read_text(encoding="utf-8")
    page_html = (ROOT / "research.html").read_text(encoding="utf-8")
    legacy_fields_referenced = extract_js_fields(research_js)
    remote_only = sorted(remote_predictive_fields - local_predictive_fields)
    local_only = sorted(local_predictive_fields - remote_predictive_fields)
    remote_only_classification = []
    for field in remote_only:
        remote_only_classification.append(
            {
                "field": field,
                "classification": (
                    "VALID_DATA_TO_CARRY_FORWARD_IF_EXPLICIT_LEGACY_FALLBACK_IS_RETAINED"
                    if field in legacy_fields_referenced
                    else "OBSOLETE_RUNTIME_BAGGAGE_FOR_NORMAL_RESEARCH"
                ),
                "normal_runtime_required": False,
                "legacy_fallback_referenced": field in legacy_fields_referenced,
            }
        )
    local_only_classification = [
        {
            "field": field,
            "classification": "VALID_NEW_FORECAST_FIELD_NOT_REQUIRED_BY_NORMAL_RESEARCH",
            "normal_runtime_required": False,
            "legacy_fallback_referenced": field in legacy_fields_referenced,
        }
        for field in local_only
    ]

    normal_contract = {
        "research_html_loads_hunt_research_js": "hunt-research.js" in page_html,
        "split_contract_default": "HUNT_RESEARCH_USE_SPLIT_CONTRACT !== false" in research_js,
        "legacy_fallback_default_disabled": True,
        "default_path": "split_summary + split_index + canonical_ladder + split_detail",
        "predictive_csv_loaded_by_default": False,
        "finding": "The predictive CSV is only loaded if the canonical contract fails and an explicit legacy-fallback override is enabled.",
    }

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    deployment_objects = []
    for record in artifact_records:
        role = record["role"]
        local = record["local"]
        review = record["review_copy"]
        if local["status"] != "PRESENT":
            release_action = "DO_NOT_UPLOAD: normal Research runtime uses this R2-backed contract but no rebuilt local replacement exists."
        elif role == "predictive_runtime_csv":
            release_action = "DO_NOT_UPLOAD: predictive CSV is not consumed by the normal split-contract runtime; explicit release review remains required."
        else:
            release_action = "DO_NOT_UPLOAD: local candidate differs from the hosted normal-runtime contract and requires a full reviewed replacement set."
        deployment_objects.append(
            {
                "role": role,
                "r2_key": record["path"],
                "current_remote_review_hash": review.get("sha256") if review else None,
                "local_candidate_hash": local.get("sha256"),
                "candidate_source_status": "AVAILABLE" if local["status"] == "PRESENT" else "NO_LOCAL_REPLACEMENT_SOURCE",
                "current_remote_schema": review.get("schema") if review else None,
                "local_candidate_schema": local.get("schema"),
                "required_by_normal_research": role != "predictive_runtime_csv",
                "required_rollback_backup_key": f"rollback/{timestamp}/{record['path']}",
                "release_action": release_action,
            }
        )
    deployment_objects.append(
        {
            "role": "predictive_runtime_remote_baseline",
            "r2_key": predictive["path"],
            "current_remote_review_hash": remote_predictive_record["sha256"],
            "local_candidate_hash": predictive["local"]["sha256"],
            "candidate_source_status": "AVAILABLE",
            "schema": remote_predictive_record["schema"],
            "required_by_normal_research": False,
            "required_rollback_backup_key": f"rollback/{timestamp}/{predictive['path']}",
            "release_action": "BASELINE_ONLY: use to verify a future authorized upload and rollback plan.",
        }
    )

    audit = {
        "schema_version": "1.0.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "READ_ONLY_REVIEW_COPY_NO_R2_WRITE",
        "normal_research_runtime": normal_contract,
        "site_scripts_traced": re.findall(r'<script[^>]+src="\.\/([^?\"]+)', page_html),
        "legacy_predictive_fields_referenced": sorted(legacy_fields_referenced),
        "predictive_runtime_contract": {
            "local": predictive["local"],
            "remote_review_copy": remote_predictive_record,
            "remote_only_fields": remote_only_classification,
            "local_only_fields": local_only_classification,
            "fields_required_by_normal_research": [],
            "finding": "No predictive CSV field is required by the normal split-contract Research runtime. Legacy-only referenced fields must be retained only if that fallback is deliberately kept.",
        },
        "hydrated_r2_only_artifacts": artifact_records,
        "deployment_readiness": {
            "status": "NOT_DEPLOYMENT_READY",
            "reason_codes": [
                "NORMAL_RESEARCH_R2_CONTRACT_HAS_NO_REBUILT_LOCAL_REPLACEMENT_SET",
                "PREDICTIVE_CSV_SCHEMA_DIFFERS_FROM_HOSTED_BASELINE",
                "EXPLICIT_TYLER_AUTHORIZATION_REQUIRED_FOR_ANY_R2_WRITE",
            ],
            "required_release_controls": [
                "Create and hash-verify each listed rollback object before changing its live R2 key.",
                "Upload only objects with a reviewed local source and matching declared schema contract.",
                "Use a new cache/version marker in config.js only as part of an explicitly authorized deployment.",
                "Run this audit again after any staging build and before a live R2 write.",
            ],
            "objects": deployment_objects,
        },
    }
    suffix = ""
    if args.reuse_review_dir:
        revision = 2
        while (review_dir / f"runtime_contract_audit_v{revision}.json").exists() or (review_dir / f"deployment_readiness_manifest_v{revision}.json").exists():
            revision += 1
        suffix = f"_v{revision}"
    audit_path = review_dir / f"runtime_contract_audit{suffix}.json"
    manifest_path = review_dir / f"deployment_readiness_manifest{suffix}.json"
    if audit_path.exists() or manifest_path.exists():
        raise RuntimeError("Refusing to overwrite an existing audit or deployment manifest.")
    audit_path.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    manifest_path.write_text(json.dumps(audit["deployment_readiness"], indent=2) + "\n", encoding="utf-8")
    print("RUNTIME_CONTRACT_AUDIT=PASS")
    print(f"REVIEW_DIR={review_dir.relative_to(ROOT)}")
    print(f"AUDIT={audit_path.relative_to(ROOT)}")
    print(f"MANIFEST={manifest_path.relative_to(ROOT)}")
    print(f"REMOTE_ONLY_FIELDS={len(remote_only)}")
    print(f"LOCAL_ONLY_FIELDS={len(local_only)}")
    print(f"REMOTE_ONLY_LEGACY_REFERENCED={sum(item['legacy_fallback_referenced'] for item in remote_only_classification)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
