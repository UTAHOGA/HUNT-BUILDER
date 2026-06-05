#!/usr/bin/env python3
"""Audit local feeder CSV parity against runtime manifest and R2.

This read-only audit classifies engine/runtime feeder files as local-authoritative,
R2-canonical, restore-needed local stubs, or retire/review candidates.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import asdict
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.engine_feeder_contract import ENGINE_FEEDERS


DEFAULT_OUT_DIR = "audits/hunt_research_engine"
MANIFESTS = ("public/data/runtime-manifest.json", "data/runtime-manifest.json")

IMPORTANT_FEEDERS = {
    "processed_data/draw_reality_engine.csv",
    "processed_data/draw_reality_engine_v2.csv",
    "processed_data/draw_reality_engine_predictive_v2.csv",
    "processed_data/draw_reality_view.csv",
    "processed_data/point_ladder_view.csv",
    "processed_data/hunt_master_enriched.csv",
    "processed_data/hunt_master_enriched_2026_draw_subset.csv",
    "processed_data/hunt_unit_reference_linked.csv",
    "processed_data/ml_draw_predictions_v1.csv",
    "processed_data/draw_system_coverage_report.csv",
    "data_model/runtime_drafts/predictive_bonus_engine_2026.predictions.csv",
    "data_model/runtime_drafts/predictive_bonus_engine_2026.materialized.csv",
    "data_model/runtime_drafts/predictive_bonus_engine_2026.audit.csv",
    "data_model/runtime_drafts/mixed_predictive_engine_2026.predictions.csv",
    "data_model/runtime_drafts/mixed_predictive_engine_2026.materialized.csv",
    "data_model/runtime_drafts/mixed_predictive_engine_2026.audit.csv",
    "data_model/harvest_quality/harvest_feature_model_by_hunt_code_2026.csv",
    "data_model/harvest_quality/harvest_quality_features_all_years_by_hunt_code.csv",
    "data_model/harvest_quality/harvest_results_all_years_long.csv",
    "data_truth/draw_results_truth/normalized/draw_results_long.csv",
    "data_truth/harvest_results_truth/normalized/harvest_results_all_years_long.csv",
    "data_truth/harvest_results_truth/normalized/harvest_quality_features_all_years_by_hunt_code.csv",
}

STUB_HINTS = (
    "Unknown Fixture Hunt",
    "fixture",
    "FIXTURE",
)


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def rel(path: str | Path) -> str:
    return Path(path).as_posix()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_manifest_assets(root: Path) -> dict[str, dict[str, Any]]:
    assets: dict[str, dict[str, Any]] = {}
    for manifest in MANIFESTS:
        payload = load_json(root / manifest)
        for item in payload.get("assets", []) if isinstance(payload, dict) else []:
            path = clean(item.get("path"))
            if not path:
                continue
            merged = dict(assets.get(path, {}))
            merged.update(item)
            manifest_paths = (set((merged.get("manifest_paths") or "").split("|")) | {manifest}) - {""}
            merged["manifest_paths"] = "|".join(sorted(manifest_paths))
            assets[path] = merged
    return assets


def csv_profile(path: Path) -> dict[str, Any]:
    if not path.exists() or path.suffix.lower() != ".csv":
        return {"row_count": "", "column_count": "", "hunt_codes": "", "header": "", "stub_hint": False}
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            sample = handle.read(65536)
            handle.seek(0)
            reader = csv.DictReader(handle)
            rows = list(reader)
    except UnicodeDecodeError:
        with path.open("r", encoding="latin-1", newline="") as handle:
            sample = handle.read(65536)
            handle.seek(0)
            reader = csv.DictReader(handle)
            rows = list(reader)
    fields = list(reader.fieldnames or [])
    codes = {clean(row.get("hunt_code")).upper() for row in rows if clean(row.get("hunt_code"))}
    return {
        "row_count": len(rows),
        "column_count": len(fields),
        "hunt_codes": len(codes),
        "header": "|".join(fields[:20]),
        "stub_hint": any(hint in sample for hint in STUB_HINTS),
    }


def head_url(url: str, timeout: int = 15) -> dict[str, Any]:
    if not url:
        return {"remote_status": "", "remote_size_bytes": "", "remote_etag": "", "remote_error": ""}
    if not url.lower().startswith(("http://", "https://")):
        return {"remote_status": "LOCAL_PATH", "remote_size_bytes": "", "remote_etag": "", "remote_error": ""}
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "HUNT-BUILDER-runtime-parity-audit/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return {
                "remote_status": response.status,
                "remote_size_bytes": response.headers.get("Content-Length", ""),
                "remote_etag": response.headers.get("ETag", ""),
                "remote_error": "",
            }
    except urllib.error.HTTPError as exc:
        return {
            "remote_status": exc.code,
            "remote_size_bytes": "",
            "remote_etag": "",
            "remote_error": str(exc),
        }
    except Exception as exc:  # noqa: BLE001 - audit should capture failures.
        return {
            "remote_status": "",
            "remote_size_bytes": "",
            "remote_etag": "",
            "remote_error": str(exc),
        }


def contract_index() -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for item in ENGINE_FEEDERS:
        out.setdefault(item.path, []).append(asdict(item))
    return out


def target_paths(manifest_assets: dict[str, dict[str, Any]], contracts: dict[str, list[dict[str, Any]]]) -> list[str]:
    paths = set(IMPORTANT_FEEDERS)
    paths.update(path for path in manifest_assets if path.endswith(".csv"))
    paths.update(path for path, items in contracts.items() if path.endswith(".csv") and any(item.get("generated") for item in items))
    return sorted(paths)


def classify(
    path: str,
    local_exists: bool,
    local_size: int,
    profile: dict[str, Any],
    manifest: dict[str, Any],
    contracts: list[dict[str, Any]],
    remote: dict[str, Any],
) -> tuple[str, str]:
    canonical_url = clean(manifest.get("canonical_url"))
    classification = clean(manifest.get("classification"))
    served_live = manifest.get("served_live") is True
    used_by_frontend = manifest.get("used_by_frontend") is True
    remote_ok = str(remote.get("remote_status")) == "200"
    manifest_size = clean(manifest.get("size_bytes"))
    remote_size = clean(remote.get("remote_size_bytes"))
    size_drift = bool(manifest_size and remote_size and manifest_size != remote_size)
    row_count = profile.get("row_count")
    row_count_int = row_count if isinstance(row_count, int) else None
    stub = bool(profile.get("stub_hint")) or (row_count_int is not None and row_count_int <= 2 and local_size < 5000)
    required_by_engine = bool(contracts)
    runtime_draft = path.startswith("data_model/runtime_drafts/")
    truth = path.startswith("data_truth/")
    harvest_model = path.startswith("data_model/harvest_quality/")

    if truth:
        return "LOCAL_TRUTH_AUTHORITATIVE", "Normalized truth table is local/repo authoritative and should not be replaced from R2."
    if canonical_url and classification == "R2_PUBLIC" and served_live and remote_ok and stub:
        if size_drift:
            return "RESTORE_LOCAL_STUB_FROM_R2_AND_UPDATE_MANIFEST", "R2 is live and local CSV is a tiny/stub copy; manifest size differs from R2. Restore local if local tools consume it and update runtime manifest sizes."
        return "RESTORE_LOCAL_STUB_FROM_R2_OR_DEMOTE_LOCAL", "R2 is live and local CSV is a tiny/stub copy. Restore local if local tools still consume it; otherwise keep R2 canonical and remove/demote local tracked copy."
    if canonical_url and classification == "R2_PUBLIC" and served_live and remote_ok and size_drift:
        return "R2_CANONICAL_MANIFEST_SIZE_DRIFT", "R2 is live, but manifest size differs from the served object. Update manifest sizes before publish closeout."
    if canonical_url and classification == "R2_PUBLIC" and served_live and remote_ok:
        return "R2_CANONICAL_LOCAL_CACHE_OK", "Manifest marks R2 as live canonical runtime source; local file is a cache/reference copy."
    if canonical_url and classification == "R2_PUBLIC" and not remote_ok:
        return "R2_DECLARED_BUT_REMOTE_NOT_VERIFIED", "Manifest declares R2 runtime source but HEAD did not return 200."
    if classification == "REVIEW_REQUIRED":
        return "REVIEW_OR_RETIRE_CANDIDATE", "Manifest says this file is review-required and not currently served live."
    if classification == "LFS_REFERENCE_ONLY":
        return "REFERENCE_ONLY_RETIRE_FROM_RUNTIME", "Reference/backup file only; should not feed runtime."
    if harvest_model:
        return "LOCAL_MODEL_FEEDER_AUTHORITATIVE", "Harvest model feeder is a local generated model input/output, not R2 runtime canonical."
    if runtime_draft:
        return "LOCAL_RUNTIME_DRAFT_AUTHORITATIVE", "Runtime draft output is local authoritative until promoted/published."
    if required_by_engine and stub:
        return "LOCAL_REQUIRED_FEEDER_STUB_RESTORE_NEEDED", "Engine contract references this feeder and local copy is stub-sized."
    if required_by_engine and local_exists:
        return "LOCAL_ENGINE_FEEDER_AUTHORITATIVE", "Engine contract references this generated local feeder."
    if local_exists:
        return "LOCAL_REFERENCE_UNCLASSIFIED", "Local file exists but is not clearly runtime-canonical from manifest or contract."
    return "MISSING_REVIEW", "File is referenced by manifest/contract/audit target list but not present locally."


def git_status(root: Path) -> list[str]:
    proc = subprocess.run(["git", "status", "--short"], cwd=root, text=True, capture_output=True, check=False)
    return [line for line in proc.stdout.splitlines() if line.strip()]


def build_audit(root: Path, check_remote: bool) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest_assets = load_manifest_assets(root)
    contracts = contract_index()
    rows: list[dict[str, Any]] = []
    for path in target_paths(manifest_assets, contracts):
        local = root / path
        profile = csv_profile(local)
        manifest = manifest_assets.get(path, {})
        remote = head_url(clean(manifest.get("canonical_url"))) if check_remote else {
            "remote_status": "SKIPPED",
            "remote_size_bytes": "",
            "remote_etag": "",
            "remote_error": "",
        }
        classification, recommendation = classify(
            path,
            local.exists(),
            local.stat().st_size if local.exists() else 0,
            profile,
            manifest,
            contracts.get(path, []),
            remote,
        )
        rows.append(
            {
                "path": path,
                "local_exists": local.exists(),
                "local_size_bytes": local.stat().st_size if local.exists() else 0,
                "row_count": profile["row_count"],
                "column_count": profile["column_count"],
                "hunt_codes": profile["hunt_codes"],
                "stub_hint": profile["stub_hint"],
                "manifest_key": clean(manifest.get("key")),
                "manifest_classification": clean(manifest.get("classification")),
                "manifest_used_by_frontend": manifest.get("used_by_frontend", ""),
                "manifest_served_live": manifest.get("served_live", ""),
                "manifest_size_bytes": manifest.get("size_bytes", ""),
                "canonical_url": clean(manifest.get("canonical_url")),
                "remote_status": remote["remote_status"],
                "remote_size_bytes": remote["remote_size_bytes"],
                "manifest_size_matches_remote": (
                    clean(manifest.get("size_bytes")) == clean(remote["remote_size_bytes"])
                    if clean(manifest.get("size_bytes")) and clean(remote["remote_size_bytes"])
                    else ""
                ),
                "remote_etag": remote["remote_etag"],
                "remote_error": remote["remote_error"],
                "engine_groups": "|".join(sorted({item.get("group", "") for item in contracts.get(path, [])})),
                "consumer_modules": "|".join(sorted({item.get("consumer_module", "") for item in contracts.get(path, [])})),
                "classification": classification,
                "recommendation": recommendation,
            }
        )
    dirty = git_status(root)
    counts = Counter(row["classification"] for row in rows)
    restore_needed = [row for row in rows if "RESTORE" in row["classification"] or row["classification"] == "LOCAL_REQUIRED_FEEDER_STUB_RESTORE_NEEDED"]
    r2_remote_failures = [row for row in rows if row["classification"] == "R2_DECLARED_BUT_REMOTE_NOT_VERIFIED"]
    manifest_size_drift = [row for row in rows if "MANIFEST_SIZE_DRIFT" in row["classification"] or "UPDATE_MANIFEST" in row["classification"]]
    summary = {
        "audit_name": "runtime_feeder_parity",
        "files_checked": len(rows),
        "classification_counts": dict(sorted(counts.items())),
        "restore_or_demote_count": len(restore_needed),
        "r2_remote_failure_count": len(r2_remote_failures),
        "manifest_size_drift_count": len(manifest_size_drift),
        "git_dirty": bool(dirty),
        "git_dirty_count": len(dirty),
        "git_dirty_sample": dirty[:50],
        "result": (
            "FAIL_R2_REMOTE_VERIFICATION"
            if r2_remote_failures
            else (
                "PASS_WITH_RESTORE_AND_MANIFEST_RECOMMENDATIONS"
                if restore_needed and manifest_size_drift
                else ("PASS_WITH_RESTORE_RECOMMENDATIONS" if restore_needed else ("PASS_WITH_MANIFEST_SIZE_DRIFT" if manifest_size_drift else "PASS"))
            )
        ),
        "recommendation": "Restore or explicitly demote local stub feeder CSVs before relying on local processed_data as complete. R2 live runtime files verified where manifest declares them.",
    }
    return summary, rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    columns = [
        "path",
        "local_exists",
        "local_size_bytes",
        "row_count",
        "column_count",
        "hunt_codes",
        "stub_hint",
        "manifest_key",
        "manifest_classification",
        "manifest_used_by_frontend",
        "manifest_served_live",
        "manifest_size_bytes",
        "canonical_url",
        "remote_status",
        "remote_size_bytes",
        "manifest_size_matches_remote",
        "remote_etag",
        "remote_error",
        "engine_groups",
        "consumer_modules",
        "classification",
        "recommendation",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_md(path: Path, summary: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    ordered = sorted(rows, key=lambda row: (row["classification"], row["path"]))
    lines = [
        "# Runtime Feeder Parity Audit",
        "",
        "Read-only classification of local feeder CSVs against runtime manifests and R2 URLs.",
        "",
        "## Summary",
        "",
        f"- Result: `{summary['result']}`.",
        f"- Files checked: `{summary['files_checked']}`.",
        f"- Restore/demote recommendations: `{summary['restore_or_demote_count']}`.",
        f"- R2 remote failures: `{summary['r2_remote_failure_count']}`.",
        f"- Manifest size drift files: `{summary['manifest_size_drift_count']}`.",
        f"- Worktree dirty during audit: `{summary['git_dirty']}` (`{summary['git_dirty_count']}` entries).",
        "",
        "## Classification Counts",
        "",
        "| Classification | Count |",
        "| --- | ---: |",
    ]
    for key, value in summary["classification_counts"].items():
        lines.append(f"| {key} | {value} |")
    lines.extend(
        [
            "",
            "## Files",
            "",
            "| Path | Local Rows | Local Size | R2 Status | Classification | Recommendation |",
            "| --- | ---: | ---: | --- | --- | --- |",
        ]
    )
    for row in ordered:
        lines.append(
            f"| `{row['path']}` | {row['row_count']} | {row['local_size_bytes']} | {row['remote_status']} | {row['classification']} | {row['recommendation']} |"
        )
    if summary["git_dirty_sample"]:
        lines.extend(["", "## Dirty Worktree Sample", ""])
        for item in summary["git_dirty_sample"]:
            lines.append(f"- `{item}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--skip-remote", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    out_dir = (root / args.out_dir).resolve()
    summary, rows = build_audit(root, check_remote=not args.skip_remote)
    base = out_dir / "runtime_feeder_parity_audit"
    write_csv(base.with_suffix(".csv"), rows)
    base.with_suffix(".json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_md(base.with_suffix(".md"), summary, rows)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
