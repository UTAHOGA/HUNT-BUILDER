#!/usr/bin/env python3
"""Create a Vercel preview by replacing only approved outfitter assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APPROVED_FILES = {
    "app.js",
    "config.js",
    "data/outfitters-public.json",
    "processed_data/public_contracts/outfitters-public.json",
    "processed_data/outfitter-federal-unit-coverage-review.json",
}
DEFAULT_AUDIT = (
    ROOT
    / "output"
    / "qa"
    / "outfitter_coverage_release_20260908"
    / "vercel_overlay_preview.json"
)


def cli() -> str:
    return shutil.which("npx.cmd" if os.name == "nt" else "npx") or "npx"


def vercel_api(endpoint: str, scope: str, *args: str) -> object:
    command = [cli(), "vercel", "api", endpoint, *args, "--scope", scope, "--raw"]
    result = subprocess.run(command, cwd=ROOT, check=True, capture_output=True)
    return json.loads(result.stdout.decode("utf-8"))


def flatten(node: dict[str, object], prefix: str = "") -> list[dict[str, str]]:
    name = str(node.get("name") or "")
    path = f"{prefix}/{name}".strip("/")
    if node.get("type") == "file":
        return [{"file": path, "sha": str(node["uid"])}]
    rows: list[dict[str, str]] = []
    for child in node.get("children") or []:
        rows.extend(flatten(child, path))
    return rows


def sha1(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def upload(path: Path, digest: str, scope: str) -> None:
    vercel_api(
        "/v2/files",
        scope,
        "-X",
        "POST",
        "--input",
        str(path),
        "-H",
        f"x-vercel-digest: {digest}",
        "-H",
        "Content-Type: application/octet-stream",
        "-H",
        f"Content-Length: {path.stat().st_size}",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-deployment", required=True)
    parser.add_argument("--scope", default="tyler-miller-s-projects")
    parser.add_argument("--project", default="hunt-builder")
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    args = parser.parse_args()

    missing_sources = [path for path in APPROVED_FILES if not (ROOT / path).is_file()]
    if missing_sources:
        raise RuntimeError(f"Approved source files are missing: {sorted(missing_sources)}")

    tree = vercel_api(f"/v6/deployments/{args.base_deployment}/files", args.scope)
    if not isinstance(tree, list) or len(tree) != 1 or tree[0].get("name") != "src":
        raise RuntimeError("Expected one Vercel source-root directory named src.")
    files = flatten(tree[0])
    for row in files:
        row["file"] = row["file"].removeprefix("src/")
    by_path = {row["file"]: row for row in files}
    missing_targets = APPROVED_FILES - set(by_path)
    if missing_targets:
        raise RuntimeError(f"Approved targets absent from base deployment: {sorted(missing_targets)}")

    replacements: dict[str, dict[str, object]] = {}
    for relative in sorted(APPROVED_FILES):
        source = ROOT / relative
        digest = sha1(source)
        upload(source, digest, args.scope)
        old_digest = by_path[relative]["sha"]
        by_path[relative] = {
            "file": relative,
            "sha": digest,
            "size": source.stat().st_size,
        }
        replacements[relative] = {
            "old_sha1": old_digest,
            "new_sha1": digest,
            "size": source.stat().st_size,
        }

    payload = {
        "name": args.project,
        "files": [by_path[key] for key in sorted(by_path)],
        "projectSettings": {"framework": None, "outputDirectory": "."},
        "meta": {
            "release": "outfitter-confirmed-usfs-coverage-20260908",
            "baseDeploymentId": args.base_deployment,
        },
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as handle:
        json.dump(payload, handle, separators=(",", ":"))
        payload_path = Path(handle.name)
    try:
        deployment = vercel_api(
            "/v13/deployments?forceNew=1",
            args.scope,
            "-X",
            "POST",
            "--input",
            str(payload_path),
            "-H",
            "Content-Type: application/json",
        )
    finally:
        payload_path.unlink(missing_ok=True)

    audit = {
        "base_deployment_id": args.base_deployment,
        "base_file_count": len(files),
        "preserved_file_count": len(files) - len(APPROVED_FILES),
        "replacements": replacements,
        "preview_deployment_id": deployment.get("id"),
        "preview_url": deployment.get("url"),
        "preview_ready_state": deployment.get("readyState"),
        "production_promoted": False,
    }
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    args.audit.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(audit, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
