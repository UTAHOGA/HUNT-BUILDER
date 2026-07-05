#!/usr/bin/env python3
"""Audit Hunt Research advertised data sources against published assets."""

from __future__ import annotations

import csv
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
PUBLIC_BASE = "https://json.uoga.workers.dev"


STATIC_RESEARCH_SOURCES = [
    {
        "claim": "Main legacy/full Hunt Research JSON",
        "key": "research_hunt_research_2026_json",
        "path": "processed_data/hunt_research_2026.json",
        "used_by_page": True,
        "required": False,
        "source": "config.js HUNT_RESEARCH_DATA_SOURCES / hunt-research.js fallback",
    },
    {
        "claim": "Compact Hunt Research summary contract",
        "key": "research_hunt_research_2026_summary_json",
        "path": "processed_data/hunt_research_2026_summary.json",
        "used_by_page": True,
        "required": True,
        "source": "config.js HUNT_RESEARCH_SUMMARY_SOURCES",
    },
    {
        "claim": "Split Hunt Research index",
        "key": "research_hunt_research_2026_split_index_json",
        "path": "processed_data/hunt_research_2026_split/hunt_research_2026.index.json",
        "used_by_page": True,
        "required": True,
        "source": "config.js HUNT_RESEARCH_SPLIT_INDEX_SOURCES",
    },
    {
        "claim": "Split Hunt Research details bundle",
        "key": "research_hunt_research_2026_split_details_json",
        "path": "processed_data/hunt_research_2026_split/hunt_research_2026.details.json",
        "used_by_page": True,
        "required": True,
        "source": "config.js HUNT_RESEARCH_SPLIT_DETAIL_BUNDLE_SOURCES",
    },
    {
        "claim": "Full Hunt Research ladder JSON",
        "key": "research_hunt_research_2026_ladder_json",
        "path": "processed_data/hunt_research_2026_ladder.json",
        "used_by_page": True,
        "required": False,
        "source": "config.js HUNT_RESEARCH_CANONICAL_LADDER_SOURCES",
    },
    {
        "claim": "Preference Hunt Research ladder JSON",
        "key": "research_hunt_research_2026_ladder_preference_json",
        "path": "processed_data/hunt_research_2026_ladder_preference.json",
        "used_by_page": False,
        "required": False,
        "source": "data/runtime-manifest.json",
    },
    {
        "claim": "Bonus/max-random Hunt Research ladder JSON",
        "key": "research_hunt_research_2026_ladder_bonus_max_random_json",
        "path": "processed_data/hunt_research_2026_ladder_bonus_max_random.json",
        "used_by_page": False,
        "required": False,
        "source": "data/runtime-manifest.json",
    },
    {
        "claim": "Observed draw engine feed",
        "key": "research_draw_reality_engine_csv",
        "path": "processed_data/draw_reality_engine.csv",
        "used_by_page": True,
        "required": True,
        "source": "config.js HUNT_RESEARCH_OBSERVED_ENGINE_SOURCES",
    },
    {
        "claim": "Observed draw engine v2 fallback feed",
        "key": "research_draw_reality_engine_v2_csv",
        "path": "processed_data/draw_reality_engine_v2.csv",
        "used_by_page": True,
        "required": False,
        "source": "config.js HUNT_RESEARCH_OBSERVED_ENGINE_SOURCES",
    },
    {
        "claim": "Predictive draw engine feed",
        "key": "research_draw_reality_engine_predictive_v2_csv",
        "path": "processed_data/draw_reality_engine_predictive_v2.csv",
        "used_by_page": True,
        "required": False,
        "source": "config.js HUNT_RESEARCH_PREDICTIVE_ENGINE_SOURCES",
    },
    {
        "claim": "Point ladder CSV",
        "key": "research_point_ladder_view_csv",
        "path": "processed_data/point_ladder_view.csv",
        "used_by_page": True,
        "required": True,
        "source": "config.js HUNT_RESEARCH_LADDER_SOURCES",
    },
    {
        "claim": "Hunt master enriched CSV",
        "key": "research_hunt_master_enriched_csv",
        "path": "processed_data/hunt_master_enriched.csv",
        "used_by_page": True,
        "required": True,
        "source": "config.js HUNT_RESEARCH_MASTER_SOURCES",
    },
    {
        "claim": "Hunt unit reference linked CSV",
        "key": "research_hunt_unit_reference_linked_csv",
        "path": "processed_data/hunt_unit_reference_linked.csv",
        "used_by_page": True,
        "required": True,
        "source": "config.js HUNT_RESEARCH_REFERENCE_SOURCES",
    },
    {
        "claim": "Hunt application outlook contract",
        "key": "public_contract_hunt_application_outlook_json",
        "path": "processed_data/public_contracts/hunt_application_outlook.json",
        "used_by_page": True,
        "required": False,
        "source": "assets/js/research-outlook-dashboard.js",
    },
    {
        "claim": "Management objective context",
        "key": "research_management_objective_context_json",
        "path": "processed_data/management_context/hunt_management_objective_context.json",
        "used_by_page": True,
        "required": False,
        "source": "assets/js/research-outlook-dashboard.js",
    },
]


UI_CLAIM_PATTERNS = [
    ("Research table header", r">([^<]*(?:2025 Draw Results|2026 Max Point Draw|2026 Random Draw)[^<]*)<"),
    ("Source modal/panel label", r">([^<]*(?:Hunt Data Snapshot|Official DWR|U\.O\.G\.A\. Modeled Output|Data Updated 2026|2026 permits|Official DWR Field Evidence)[^<]*)<"),
    ("JavaScript source/data claim", r"['\"]([^'\"]*(?:Official DWR|U\.O\.G\.A\. Modeled Output|Data Updated 2026|2026 permits|source fields|modeled row|runtime rows)[^'\"]*)['\"]"),
]


def rel(path: Path) -> str:
    return path.relative_to(REPO).as_posix()


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return {}


def manifest_assets() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for manifest_path in [REPO / "data/runtime-manifest.json", REPO / "public/data/runtime-manifest.json"]:
        payload = read_json(manifest_path)
        for asset in payload.get("assets", []) if isinstance(payload.get("assets"), list) else []:
            key = str(asset.get("key") or "").strip()
            path = str(asset.get("path") or "").strip().replace("\\", "/")
            if key:
                out[key] = asset
            if path:
                out.setdefault(f"path::{path}", asset)
    return out


def head_url(url: str, timeout: int = 30) -> tuple[int | None, int | None, str]:
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "hunt-builder-audit/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            length = response.headers.get("Content-Length")
            return response.status, int(length) if length and length.isdigit() else None, ""
    except Exception as exc:  # noqa: BLE001 - audit should record failures.
        return None, None, str(exc)


def local_status(path: str) -> dict[str, object]:
    candidates = {
        "repo_source": REPO / path,
        "public": REPO / "public" / path,
        "pages_dist": REPO / "pages-dist" / path,
    }
    out: dict[str, object] = {}
    for name, candidate in candidates.items():
        out[f"{name}_exists"] = candidate.exists()
        out[f"{name}_bytes"] = candidate.stat().st_size if candidate.exists() and candidate.is_file() else ""
    return out


def classify(row: dict[str, object]) -> str:
    required = bool(row["required"])
    used = bool(row["used_by_page"])
    repo_exists = bool(row["repo_source_exists"])
    pages_exists = bool(row["pages_dist_exists"])
    remote_ok = row["remote_status"] == 200
    manifest_mode = str(row.get("manifest_storage_mode") or "").upper()

    if used and required and not remote_ok:
        return "BLOCKER_REQUIRED_RESEARCH_SOURCE_NOT_PUBLISHED"
    if used and not repo_exists and not remote_ok:
        return "PATH_MISMATCH_USED_BY_PAGE_SOURCE_MISSING"
    if used and not pages_exists and not remote_ok and manifest_mode != "R2_OBJECT":
        return "BUILD_COPY_OR_R2_MISSING"
    if used and remote_ok:
        if not pages_exists:
            return "OK_R2_PUBLISHED_PAGES_DIST_SKIPPED_OR_LOCAL_MISSING"
        return "OK_PUBLISHED"
    if not used and repo_exists and remote_ok:
        return "PUBLISHED_BUT_NOT_USED_BY_RESEARCH_PAGE"
    if not used and not repo_exists:
        return "MANIFEST_OR_LEGACY_REFERENCE_ONLY_MISSING"
    return "REVIEW"


def collect_claims() -> list[dict[str, str]]:
    files = [
        REPO / "research.html",
        REPO / "hunt-research.html",
        REPO / "hunt-research.js",
        REPO / "assets/js/research-outlook-dashboard.js",
    ]
    claims: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for path in files:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for claim_type, pattern in UI_CLAIM_PATTERNS:
            for match in re.finditer(pattern, text):
                value = " ".join(match.group(1).split())
                if not value:
                    continue
                key = (claim_type, rel(path), value)
                if key in seen:
                    continue
                seen.add(key)
                claims.append({"claim_type": claim_type, "file": rel(path), "claim_text": value})
    return claims


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_dir = REPO / "audits/research_page_published_data_reconciliation" / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)

    assets = manifest_assets()
    rows: list[dict[str, object]] = []
    for source in STATIC_RESEARCH_SOURCES:
        path = source["path"]
        manifest = assets.get(str(source["key"])) or assets.get(f"path::{path}") or {}
        canonical_url = str(manifest.get("canonical_url") or f"{PUBLIC_BASE}/{path}")
        status, remote_len, error = head_url(canonical_url)
        row: dict[str, object] = {
            **source,
            "canonical_url": canonical_url,
            "manifest_public_use": manifest.get("public_use", ""),
            "manifest_used_by_frontend": manifest.get("used_by_frontend", ""),
            "manifest_served_live": manifest.get("served_live", ""),
            "manifest_storage_mode": manifest.get("current_storage_mode", ""),
            "manifest_notes": manifest.get("notes", ""),
            **local_status(str(path)),
            "remote_status": status or "",
            "remote_content_length": remote_len if remote_len is not None else "",
            "remote_error": error,
        }
        row["classification"] = classify(row)
        rows.append(row)

    claims = collect_claims()
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_sources_checked": len(rows),
        "ui_claims_collected": len(claims),
        "classification_counts": {},
    }
    for row in rows:
        summary["classification_counts"][str(row["classification"])] = summary["classification_counts"].get(str(row["classification"]), 0) + 1

    write_csv(out_dir / "research_page_published_data_sources.csv", rows)
    write_csv(out_dir / "research_page_ui_availability_claims.csv", claims)
    (out_dir / "research_page_published_data_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    blockers = [row for row in rows if str(row["classification"]).startswith("BLOCKER")]
    mismatches = [
        row for row in rows
        if row["classification"] in {
            "PATH_MISMATCH_USED_BY_PAGE_SOURCE_MISSING",
            "BUILD_COPY_OR_R2_MISSING",
            "PUBLISHED_BUT_NOT_USED_BY_RESEARCH_PAGE",
            "MANIFEST_OR_LEGACY_REFERENCE_ONLY_MISSING",
        }
    ]
    md_lines = [
        "# Research Page Published Data Reconciliation",
        "",
        f"Generated: {summary['generated_at']}",
        "",
        "## Classification Counts",
        "",
    ]
    for key, count in sorted(summary["classification_counts"].items()):
        md_lines.append(f"- {key}: {count}")
    md_lines.extend(["", "## Reconciliation Findings", ""])
    if not blockers and not mismatches:
        md_lines.append("No blocker or mismatch rows were found.")
    else:
        for row in blockers + mismatches:
            md_lines.append(
                f"- {row['classification']}: {row['claim']} -> `{row['path']}` "
                f"(repo={row['repo_source_exists']}, pages-dist={row['pages_dist_exists']}, "
                f"remote={row['remote_status']}, used_by_page={row['used_by_page']})"
            )
    md_lines.extend([
        "",
        "## Primary UI Claims Captured",
        "",
    ])
    for claim in claims[:50]:
        md_lines.append(f"- {claim['claim_type']}: `{claim['claim_text']}` ({claim['file']})")
    md_lines.extend([
        "",
        "## Output Files",
        "",
        "- research_page_published_data_sources.csv",
        "- research_page_ui_availability_claims.csv",
        "- research_page_published_data_summary.json",
    ])
    (out_dir / "RESEARCH_PAGE_PUBLISHED_DATA_RECONCILIATION.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(f"AUDIT_DIR={out_dir}")
    print(json.dumps(summary, indent=2))
    return 1 if blockers else 0


if __name__ == "__main__":
    sys.exit(main())
