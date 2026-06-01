#!/usr/bin/env python3
import csv
import json
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

OUT_CSV = ROOT / "processed_data" / "audits" / "lfs_runtime_canonicalization_audit.csv"
OUT_MD = ROOT / "docs" / "lfs_runtime_canonicalization_report.md"
MANIFEST_PATH = ROOT / "public" / "data" / "runtime-manifest.json"
GITATTRIBUTES_PATH = ROOT / ".gitattributes"
HARD_COPY_DOCS_PATH = ROOT / "public" / "hard-copy" / "data" / "documents.json"

FRONTEND_FILES = [
    "index.html",
    "research.html",
    "verify.html",
    "hard-copy.html",
    "config.js",
    "app.js",
    "data.js",
    "hunt-research.js",
    "assets/js/research-outlook-dashboard.js",
]

GIT_LFS_POINTER_PREFIX = b"version https://git-lfs.github.com/spec/v1"

ALLOWED_CANONICAL = {"REPO_PUBLIC", "CLOUDFLARE_R2_PUBLIC", "LOCAL_REFERENCE_ONLY", "LEGACY_TO_REMOVE"}
ALLOWED_ACTIONS = {"KEEP_REPO_PUBLIC", "SERVE_FROM_R2", "REMOVE_FROM_RUNTIME", "KEEP_REFERENCE_ONLY", "REVIEW_REQUIRED"}


def run(cmd):
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{proc.stderr}")
    return proc.stdout


def read_text(path: Path):
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def is_lfs_pointer(path: Path):
    if not path.exists() or not path.is_file():
        return False
    with path.open("rb") as f:
        return f.read(256).startswith(GIT_LFS_POINTER_PREFIX)


def parse_lfs_files():
    output = run(["git", "lfs", "ls-files"])
    rows = []
    for line in output.splitlines():
        if not line.strip():
            continue
        # format: "<sha> <status> <path>"
        parts = line.split(maxsplit=2)
        if len(parts) < 3:
            continue
        sha, status, rel = parts
        rows.append(
            {
                "sha": sha.strip(),
                "status": status.strip(),
                "path": rel.strip().replace("\\", "/"),
            }
        )
    return rows


def parse_lfs_patterns():
    patterns = []
    for line in read_text(GITATTRIBUTES_PATH).splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if "filter=lfs" in text:
            patterns.append(text.split()[0].strip())
    return patterns


def load_manifest():
    if not MANIFEST_PATH.exists():
        return {}
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assets = payload.get("assets", []) if isinstance(payload, dict) else []
    by_path = {}
    for asset in assets:
        rel = str(asset.get("path") or "").strip().replace("\\", "/")
        if rel:
            by_path[rel] = asset
    return by_path


def load_hard_copy_public_paths():
    out = set()
    if not HARD_COPY_DOCS_PATH.exists():
        return out
    payload = json.loads(HARD_COPY_DOCS_PATH.read_text(encoding="utf-8"))
    for row in payload if isinstance(payload, list) else []:
        file_path = str(row.get("file") or row.get("path") or "").strip().replace("\\", "/")
        if file_path:
            out.add(file_path.lstrip("./"))
    return out


def classify_website_universe(path_rel, manifest_asset, live_runtime_used, public_download_used):
    path_lower = path_rel.lower()
    if live_runtime_used:
        if manifest_asset:
            canonical_url = str(manifest_asset.get("canonical_url") or "").strip()
            if canonical_url.startswith("http"):
                return "LIVE_RUNTIME_REQUIRED", "CLOUDFLARE_R2_PUBLIC", "SERVE_FROM_R2"
            if canonical_url.startswith("/"):
                return "LIVE_RUNTIME_REQUIRED", "REPO_PUBLIC", "KEEP_REPO_PUBLIC"
        # Runtime path without explicit manifest canonical URL.
        return "REVIEW_REQUIRED", "LOCAL_REFERENCE_ONLY", "REVIEW_REQUIRED"

    if public_download_used:
        return "PUBLIC_DOWNLOAD_REQUIRED", "REPO_PUBLIC", "KEEP_REPO_PUBLIC"

    if "/backups/" in path_lower or path_lower.startswith("processed_data/backups/"):
        return "OBSOLETE_OR_LEGACY", "LEGACY_TO_REMOVE", "KEEP_REFERENCE_ONLY"
    if path_lower.endswith(".sqlite"):
        return "INTERNAL_REFERENCE_ONLY", "LOCAL_REFERENCE_ONLY", "KEEP_REFERENCE_ONLY"
    if path_lower.startswith("data_truth/") or path_lower.startswith("data_model/"):
        return "GENERATED_REFERENCE_ONLY", "LOCAL_REFERENCE_ONLY", "KEEP_REFERENCE_ONLY"
    if "backup" in path_lower:
        return "OBSOLETE_OR_LEGACY", "LEGACY_TO_REMOVE", "KEEP_REFERENCE_ONLY"
    return "INTERNAL_REFERENCE_ONLY", "LOCAL_REFERENCE_ONLY", "KEEP_REFERENCE_ONLY"


def main():
    generated_at = datetime.now().isoformat()
    lfs_rows = parse_lfs_files()
    lfs_patterns = parse_lfs_patterns()
    manifest_by_path = load_manifest()
    hard_copy_paths = load_hard_copy_public_paths()

    frontend_content = "\n".join(read_text(ROOT / rel) for rel in FRONTEND_FILES if (ROOT / rel).exists())
    frontend_content_lower = frontend_content.lower()
    alternate_domain_hits = "hunt-builder.uoga.org" in frontend_content_lower

    out_rows = []
    class_counts = Counter()
    canonical_counts = Counter()
    action_counts = Counter()

    for row in lfs_rows:
        rel = row["path"]
        full_path = ROOT / rel
        manifest_asset = manifest_by_path.get(rel)

        live_runtime_used = False
        if manifest_asset and bool(manifest_asset.get("used_by_frontend")):
            live_runtime_used = True
        if f"./{rel}".lower() in frontend_content_lower or rel.lower() in frontend_content_lower:
            live_runtime_used = True

        public_download_used = rel in hard_copy_paths

        universe_class, canonical_source, action = classify_website_universe(
            rel, manifest_asset, live_runtime_used, public_download_used
        )

        real_file_present = full_path.exists() and full_path.is_file() and not is_lfs_pointer(full_path)
        notes = []
        notes.append(f"lfs_status={row['status']}")
        if manifest_asset:
            notes.append(f"manifest_key={manifest_asset.get('key')}")
            notes.append(f"manifest_used_by_frontend={manifest_asset.get('used_by_frontend')}")
            notes.append(f"manifest_canonical_url={manifest_asset.get('canonical_url')}")
        if not full_path.exists():
            notes.append("missing_local_file")
        elif is_lfs_pointer(full_path):
            notes.append("local_lfs_pointer_payload")

        out = {
            "path": rel,
            "lfs_tracked": "YES",
            "local_real_file_present": "YES" if real_file_present else "NO",
            "live_runtime_used": "YES" if live_runtime_used else "NO",
            "public_download_used": "YES" if public_download_used else "NO",
            "canonical_source": canonical_source,
            "recommended_action": action,
            "notes": f"{universe_class}; " + "; ".join(notes),
        }

        if out["canonical_source"] not in ALLOWED_CANONICAL:
            raise RuntimeError(f"Invalid canonical_source for {rel}: {out['canonical_source']}")
        if out["recommended_action"] not in ALLOWED_ACTIONS:
            raise RuntimeError(f"Invalid recommended_action for {rel}: {out['recommended_action']}")

        out_rows.append(out)
        class_counts[universe_class] += 1
        canonical_counts[canonical_source] += 1
        action_counts[action] += 1

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "path",
                "lfs_tracked",
                "local_real_file_present",
                "live_runtime_used",
                "public_download_used",
                "canonical_source",
                "recommended_action",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerows(sorted(out_rows, key=lambda x: x["path"]))

    live_runtime_rows = [r for r in out_rows if r["live_runtime_used"] == "YES"]

    md = [
        "# LFS Runtime Canonicalization Report",
        "",
        f"Generated: {generated_at}",
        "",
        "## Scope",
        "- Audit of all currently LFS-tracked files in repo.",
        "- Classification of live website universe dependencies.",
        "- Canonical source assignment and runtime action recommendations.",
        "",
        "## LFS Pattern Inventory (.gitattributes)",
    ]
    for pattern in lfs_patterns:
        md.append(f"- `{pattern}`")
    md.extend(
        [
            "",
            "## Counts",
            f"- LFS-tracked files audited: **{len(out_rows)}**",
            f"- LIVE_RUNTIME_REQUIRED: **{class_counts['LIVE_RUNTIME_REQUIRED']}**",
            f"- PUBLIC_DOWNLOAD_REQUIRED: **{class_counts['PUBLIC_DOWNLOAD_REQUIRED']}**",
            f"- INTERNAL_REFERENCE_ONLY: **{class_counts['INTERNAL_REFERENCE_ONLY']}**",
            f"- GENERATED_REFERENCE_ONLY: **{class_counts['GENERATED_REFERENCE_ONLY']}**",
            f"- OBSOLETE_OR_LEGACY: **{class_counts['OBSOLETE_OR_LEGACY']}**",
            f"- REVIEW_REQUIRED: **{class_counts['REVIEW_REQUIRED']}**",
            "",
            "## Canonical Source Distribution",
        ]
    )
    for key in sorted(canonical_counts.keys()):
        md.append(f"- {key}: **{canonical_counts[key]}**")
    md.extend(["", "## Recommended Actions"])
    for key in sorted(action_counts.keys()):
        md.append(f"- {key}: **{action_counts[key]}**")

    md.extend(["", "## Live Runtime Universe (LFS-tracked only)"])
    if not live_runtime_rows:
        md.append("- No LFS-tracked files are active runtime dependencies.")
    else:
        for r in sorted(live_runtime_rows, key=lambda x: x["path"]):
            md.append(
                f"- `{r['path']}` -> `{r['canonical_source']}` / `{r['recommended_action']}`"
            )
    md.extend(
        [
            "",
            "## Domain Canonicalization Check (Active Runtime Files)",
            "- Canonical domain expected: `huntbuilder.uoga.org`",
            f"- Alternate domain reference found in active runtime files: {'YES' if alternate_domain_hits else 'NO'}",
        ]
    )

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(md) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "audited_files": len(out_rows),
                "live_runtime_required": class_counts["LIVE_RUNTIME_REQUIRED"],
                "report": str(OUT_MD),
                "csv": str(OUT_CSV),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
