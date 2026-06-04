#!/usr/bin/env python3
"""Classify repo files by intended GitHub, Vercel, Cloudflare, or local storage home."""

from __future__ import annotations

import csv
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_CSV = ROOT / "processed_data" / "audits" / "repo_storage_placement_audit.csv"
OUT_JSON = ROOT / "processed_data" / "audits" / "repo_storage_placement_summary.json"
OUT_MD = ROOT / "docs" / "repo_storage_placement_decision_report.md"

SKIP_DIRS = {
    ".git",
    ".wrangler",
    ".pytest_cache",
    "__pycache__",
    "node_modules",
    "_exports",
    "_local_untracked_backup",
}

BIG_BYTES = 5 * 1024 * 1024
HUGE_BYTES = 50 * 1024 * 1024
LFS_POINTER_PREFIX = b"version https://git-lfs.github.com/spec/v1"

R2_RUNTIME_REL_PATHS = {
    "processed_data/display-boundary-index-2026.json",
    "processed_data/statewide_composite_boundaries_2026.geojson",
    "processed_data/composite_hunt_unit_mapping_2026.geojson",
    "processed_data/hunt_research_2026.json",
    "processed_data/hunt_research_2026_summary.json",
    "processed_data/hunt_research_2026_ladder.json",
    "processed_data/hunt_research_2026_ladder_preference.json",
    "processed_data/hunt_research_2026_ladder_bonus_max_random.json",
    "processed_data/hunt_research_2026_split/hunt_research_2026.index.json",
    "processed_data/draw_reality_engine.csv",
    "processed_data/draw_reality_engine_v2.csv",
    "processed_data/draw_reality_engine_predictive_v2.csv",
    "processed_data/draw_reality_view.csv",
    "processed_data/ml_draw_predictions_v1.csv",
    "processed_data/hunt_master_enriched.csv",
    "processed_data/hunt_unit_reference_linked.csv",
    "processed_data/point_ladder_view.csv",
    "processed_data/public_contracts/hunt_odds_history.json",
}

VERCEL_ROOT_FILES = {
    "index.html",
    "research.html",
    "verify.html",
    "hard-copy.html",
    "hunt-builder-google-earth.html",
    "builder.html",
    "style.css",
    "app.js",
    "config.js",
    "data.js",
    "hunt-research.js",
    "embed-mode.js",
    "google-basemap.js",
    "map-engine.js",
    "header-layout.js",
    "ui.js",
    "event-handlers.js",
    "boundary-resolver.js",
    "ownership-dock.js",
    "sentry-browser-init.js",
    "uoga-analytics.js",
    "favicon.ico",
    "CNAME",
    "vercel.json",
    "package.json",
    "package-lock.json",
}

ROOT_JUNK_OR_LEGACY_NAMES = {
    "point_ladder_view1.csv",
    ".tmp_r2_test.csv",
    "old_app_d5e8a419.js",
    "hunt-research.js.bak",
    "hunt-research.js.bak-lfs-pointer-fix",
    "verify.htmlm",
    "large-files.txt",
    "Git",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_git(args: list[str]) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, encoding="utf-8", errors="replace")


def git_set(args: list[str]) -> set[str]:
    out = run_git(args)
    return {line.strip().replace("\\", "/") for line in out.splitlines() if line.strip()}


def is_lfs_pointer(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            return fh.read(120).startswith(LFS_POINTER_PREFIX)
    except OSError:
        return False


def iter_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(ROOT).parts
        if any(part in SKIP_DIRS for part in rel_parts):
            continue
        files.append(path)
    return files


def file_family(rel: str, suffix: str) -> str:
    if rel in VERCEL_ROOT_FILES or rel.startswith("assets/") or rel.startswith("public/"):
        return "frontend_or_public_static"
    if rel.startswith("data/"):
        return "runtime_small_data"
    if rel.startswith("processed_data/"):
        return "processed_or_runtime_data"
    if rel.startswith("pipeline/RAW/"):
        return "raw_source_pipeline"
    if rel.startswith("data_truth/"):
        return "truth_or_validation_data"
    if rel.startswith("data_model/"):
        return "model_working_data"
    if rel.startswith("scripts/") or rel.startswith("tests/") or rel.startswith("engine/") or rel.startswith("lib/"):
        return "source_code_or_tests"
    if rel.startswith("docs/") or suffix == ".md":
        return "documentation"
    if suffix in {".pdf", ".xlsx", ".xls", ".zip", ".sqlite", ".db"}:
        return "large_binary_or_archive"
    return "miscellaneous"


def classify(rel: str, size: int, suffix: str, tracked: bool, ignored: bool, lfs: bool) -> tuple[str, str, str]:
    rel_lower = rel.lower()
    name = Path(rel).name
    if rel in ROOT_JUNK_OR_LEGACY_NAMES or rel_lower.endswith((".bak", ".patch", ".log")):
        return "LOCAL_ONLY_IGNORE", "NONE", "Legacy/temp/root junk; do not deploy or publish."
    if rel.startswith("HUNT-BUILDER/"):
        return "LOCAL_ONLY_IGNORE", "NONE", "Nested repo/archive copy; do not track, deploy, or publish from this duplicate path."
    if rel in R2_RUNTIME_REL_PATHS:
        return "CLOUDFLARE_R2_PUBLIC", "R2_PUBLIC_URL", "Large or canonical runtime/public asset; serve from R2 and reference via runtime manifest."
    if rel.startswith("processed_data/backups/") or "/backups/" in rel:
        return "LOCAL_ONLY_IGNORE", "NONE", "Backup/archive artifact; keep out of GitHub and Vercel."
    if rel.startswith("node_modules/") or rel.startswith(".wrangler/"):
        return "LOCAL_ONLY_IGNORE", "NONE", "Tool/vendor/cache directory."
    if rel.startswith("pipeline/RAW/"):
        if rel.endswith("pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv") or rel == "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv":
            return "GITHUB_TRUTH_SOURCE", "NO_DIRECT_VERCEL_ROUTE", "Current DATABASE truth anchor; track in GitHub, not as visitor runtime."
        if suffix in {".pdf", ".xlsx", ".xls", ".zip"} or size >= BIG_BYTES:
            return "LOCAL_OR_R2_REFERENCE", "NONE_UNLESS_PUBLIC_LIBRARY", "Raw source/reference artifact; keep local or publish curated copy to R2 only if visitor-facing."
        return "GITHUB_REFERENCE_IF_PROMOTED", "NO_DIRECT_VERCEL_ROUTE", "Small promoted raw/source evidence may be tracked if lineage requires it."
    if rel.startswith("data_truth/"):
        if size >= BIG_BYTES or lfs:
            return "GIT_LFS_OR_LOCAL_REFERENCE", "NONE", "Truth/reference artifact too large for normal GitHub; keep LFS/local, not Vercel runtime."
        return "GITHUB_TRUTH_SOURCE", "NONE", "Small truth/validation source should be tracked in GitHub."
    if rel.startswith("data_model/"):
        if size >= BIG_BYTES:
            return "LOCAL_ONLY_IGNORE", "NONE", "Model working output; regenerate or publish reviewed runtime derivative, not raw artifact."
        return "GITHUB_REFERENCE_IF_PROMOTED", "NONE", "Small model config/reference can be tracked if still active."
    if rel.startswith("processed_data/"):
        if rel.startswith("processed_data/audits/"):
            if size >= BIG_BYTES:
                return "LOCAL_OR_R2_REFERENCE", "NONE_UNLESS_PUBLIC_LIBRARY", "Large audit/reference output; keep local unless intentionally curated for public download."
            return "GITHUB_SMALL_PROCESSED", "NONE", "Small audit output can be tracked when it documents a completed validation step."
        if suffix == ".sqlite" or suffix == ".db":
            return "LOCAL_ONLY_IGNORE", "NONE", "Internal database artifact; do not publish directly."
        if size >= BIG_BYTES or lfs:
            return "CLOUDFLARE_R2_PUBLIC" if ("public_contracts/" in rel or "hunt_research" in rel or "reality_engine" in rel or "ladder" in rel or "master_enriched" in rel or suffix == ".geojson") else "LOCAL_OR_R2_REFERENCE", "R2_PUBLIC_URL_IF_VISITOR_FACING", "Large processed artifact; use R2 only if active/public, otherwise local/reference."
        return "GITHUB_SMALL_PROCESSED", "VERCEL_IF_REFERENCED", "Small processed artifact can stay in GitHub; Vercel only if active frontend fetches it."
    if rel.startswith("public/"):
        if size >= BIG_BYTES:
            return "CLOUDFLARE_R2_PUBLIC", "R2_PUBLIC_URL", "Public file is large; move/serve from R2 and keep only manifest/link in repo."
        return "GITHUB_AND_VERCEL_PUBLIC", "VERCEL_STATIC", "Small visitor-facing public asset belongs in GitHub and deploys through Vercel."
    if rel.startswith("data/"):
        if size >= BIG_BYTES:
            return "CLOUDFLARE_R2_PUBLIC", "R2_PUBLIC_URL", "Runtime data is large; serve from R2 and leave manifest/small fallback in repo."
        return "GITHUB_AND_VERCEL_RUNTIME", "VERCEL_STATIC", "Small runtime JSON/config used by frontend belongs in GitHub and Vercel."
    if rel.startswith("assets/"):
        if size >= BIG_BYTES:
            return "CLOUDFLARE_R2_PUBLIC", "R2_PUBLIC_URL", "Large media asset; R2 is safer than Vercel bundle."
        return "GITHUB_AND_VERCEL_PUBLIC", "VERCEL_STATIC", "Frontend asset belongs in GitHub and Vercel."
    if rel.startswith("docs/") or suffix == ".md":
        return "GITHUB_DOCS", "NONE", "Documentation belongs in GitHub; not Vercel runtime unless intentionally public."
    if rel.startswith("scripts/") or rel.startswith("tests/") or rel.startswith("engine/") or rel.startswith("lib/"):
        return "GITHUB_CODE", "NONE", "Build/audit/test source belongs in GitHub, not Vercel public runtime."
    if rel in VERCEL_ROOT_FILES or suffix in {".html", ".js", ".css", ".ico"}:
        if size >= BIG_BYTES:
            return "REVIEW_REQUIRED", "VERCEL_STATIC_OR_SPLIT", "Large frontend/root file needs review before deploy."
        return "GITHUB_AND_VERCEL_APP", "VERCEL_STATIC", "Active frontend app file belongs in GitHub and Vercel."
    if suffix in {".pdf", ".xlsx", ".xls", ".zip", ".sqlite", ".db"} or size >= HUGE_BYTES:
        return "LOCAL_OR_R2_REFERENCE", "NONE_UNLESS_PUBLIC_LIBRARY", "Large binary/archive; do not store normal GitHub or Vercel unless curated."
    if ignored and not tracked:
        return "LOCAL_ONLY_IGNORE", "NONE", "Ignored untracked local artifact."
    return "GITHUB_REVIEW", "NONE", "Small miscellaneous file; review before tracking/deploying."


def write_csv(rows: list[dict[str, object]]) -> None:
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "path",
        "size_bytes",
        "size_mb",
        "tracked",
        "ignored",
        "lfs_tracked",
        "lfs_pointer_payload",
        "family",
        "recommended_home",
        "deploy_target",
        "notes",
    ]
    with OUT_CSV.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_md(rows: list[dict[str, object]], summary: dict[str, object]) -> None:
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    counts = summary["recommended_home_counts"]
    large = [r for r in rows if int(r["size_bytes"]) >= BIG_BYTES]
    large_sorted = sorted(large, key=lambda r: int(r["size_bytes"]), reverse=True)[:40]
    active_r2 = [r for r in rows if r["path"] in R2_RUNTIME_REL_PATHS]
    review = [r for r in rows if "REVIEW" in str(r["recommended_home"])][:40]
    lines = [
        "# Repo Storage Placement Decision Report",
        "",
        f"Generated: {summary['generated_at']}",
        "",
        "## Decision Rule",
        "",
        "- GitHub: source code, small docs/manifests/config, small truth anchors, and reproducible scripts.",
        "- Vercel: the frontend app and small static/runtime files required for first load.",
        "- Cloudflare R2: large public/runtime files and public downloads.",
        "- Local/LFS reference: raw source PDFs/XLSX, backups, SQLite, model working files, and internal truth exports not read by visitors.",
        "",
        "## Counts",
        "",
    ]
    for key, count in sorted(counts.items()):
        lines.append(f"- `{key}`: `{count}`")
    lines.extend(
        [
            "",
            "## Must Stay In GitHub And Vercel",
            "",
            "- Root app files: `index.html`, `research.html`, `verify.html`, `hard-copy.html`, `app.js`, `config.js`, `data.js`, `hunt-research.js`, CSS, map modules, and small supporting JS.",
            "- Small runtime data under `data/`, especially Builder first-load hunt-master JSON files.",
            "- Small public assets under `public/` and `assets/`.",
            "- `public/data/runtime-manifest.json` and `data/runtime-manifest.json` as small manifests pointing to R2.",
            "",
            "## Must Stay In GitHub But Not Vercel Runtime",
            "",
            "- `scripts/`, `tests/`, `docs/`, `schemas/`, and small validation/audit outputs.",
            "- `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv` as the current truth anchor.",
            "- Small `data_truth/` validation/source-control files.",
            "",
            "## Must Live In Cloudflare R2 For Public Runtime",
            "",
        ]
    )
    for row in sorted(active_r2, key=lambda r: r["path"]):
        lines.append(f"- `{row['path']}` ({row['size_mb']} MB)")
    lines.extend(
        [
            "",
            "## Should Stay Local Or LFS Reference Only",
            "",
            "- Raw `pipeline/RAW/` PDFs/XLSX/ZIPs unless curated for public library downloads.",
            "- `processed_data/*.sqlite`, backup folders, and model draft CSVs.",
            "- Large truth/reference files such as `data_truth/draw_results_truth/normalized/draw_results_long.csv` unless a reviewed public contract is produced.",
            "- Root backup/junk files such as `.tmp_r2_test.csv`, `point_ladder_view1.csv`, old `.bak` files, and stale one-off exports.",
            "",
            "## Immediate Cleanup Recommendations",
            "",
            "- Remove broad `.gitignore` rule `*.md`; it accidentally hides project docs from GitHub.",
            "- Keep `DATABASE.csv` explicitly tracked even though `pipeline/RAW/` is generally ignored.",
            "- Keep large runtime outputs ignored locally and published through `public/data/runtime-manifest.json` to R2.",
            "- Delete or move root junk/legacy files to a local archive before any commit sweep.",
            "- Do not put R2-public files back into normal GitHub blobs; GitHub should carry manifests and source scripts, not 50-300 MB runtime payloads.",
            "",
            "## Largest Files Reviewed",
            "",
            "| Path | MB | Recommended home |",
            "| --- | ---: | --- |",
        ]
    )
    for row in large_sorted:
        lines.append(f"| `{row['path']}` | {row['size_mb']} | `{row['recommended_home']}` |")
    lines.extend(["", "## Review Required Examples", ""])
    if review:
        for row in review:
            lines.append(f"- `{row['path']}` -> `{row['recommended_home']}`: {row['notes']}")
    else:
        lines.append("- No high-priority review examples found in the first pass.")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    tracked = git_set(["ls-files"])
    ignored = git_set(["ls-files", "--others", "--ignored", "--exclude-standard"])
    try:
        lfs_files = git_set(["lfs", "ls-files", "-n"])
    except (subprocess.CalledProcessError, FileNotFoundError):
        lfs_files = set()
    files = iter_files()
    rows: list[dict[str, object]] = []
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        size = path.stat().st_size
        suffix = path.suffix.lower()
        tracked_flag = rel in tracked
        ignored_flag = rel in ignored
        lfs_flag = rel in lfs_files
        pointer = is_lfs_pointer(path)
        family = file_family(rel, suffix)
        home, deploy_target, notes = classify(rel, size, suffix, tracked_flag, ignored_flag, lfs_flag)
        rows.append(
            {
                "path": rel,
                "size_bytes": size,
                "size_mb": round(size / 1024 / 1024, 3),
                "tracked": "yes" if tracked_flag else "no",
                "ignored": "yes" if ignored_flag else "no",
                "lfs_tracked": "yes" if lfs_flag else "no",
                "lfs_pointer_payload": "yes" if pointer else "no",
                "family": family,
                "recommended_home": home,
                "deploy_target": deploy_target,
                "notes": notes,
            }
        )
    rows.sort(key=lambda r: (str(r["recommended_home"]), str(r["path"])))
    summary = {
        "generated_at": utc_now(),
        "total_files_reviewed": len(rows),
        "total_size_bytes": sum(int(r["size_bytes"]) for r in rows),
        "tracked_files_reviewed": sum(1 for r in rows if r["tracked"] == "yes"),
        "ignored_files_reviewed": sum(1 for r in rows if r["ignored"] == "yes"),
        "lfs_tracked_files_reviewed": sum(1 for r in rows if r["lfs_tracked"] == "yes"),
        "lfs_pointer_payloads_found": sum(1 for r in rows if r["lfs_pointer_payload"] == "yes"),
        "large_files_over_5mb": sum(1 for r in rows if int(r["size_bytes"]) >= BIG_BYTES),
        "recommended_home_counts": dict(Counter(str(r["recommended_home"]) for r in rows)),
        "deploy_target_counts": dict(Counter(str(r["deploy_target"]) for r in rows)),
        "outputs": {
            "csv": OUT_CSV.relative_to(ROOT).as_posix(),
            "markdown": OUT_MD.relative_to(ROOT).as_posix(),
        },
    }
    write_csv(rows)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    write_md(rows, summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
