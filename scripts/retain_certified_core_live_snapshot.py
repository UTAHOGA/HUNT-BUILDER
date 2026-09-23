"""Retain byte-exact live R2 inputs before an isolated certified-core rebuild."""
import argparse
import hashlib
import json
import urllib.request
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--production-report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--remote-r2", action="store_true", help="Use the authenticated object API through Wrangler")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Refusing to overwrite retained live evidence")
    report = json.loads(args.production_report.read_text())
    if "r2_objects" in report:
        objects = [(r["key"], r["after_sha256"]) for r in report["r2_objects"]]
        legacy_hash = report["unchanged_legacy_ladder_sha256"]
    else:
        objects = [(r["key"], r["new_sha256"]) for r in report["r2"]["objects"]]
        legacy_hash = report["r2"]["unchanged_legacy_ladder_sha256"]
    objects.append(("processed_data/hunt_research_2026_ladder.json", legacy_hash))
    args.output.mkdir(parents=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    def fetch(item):
        key, expected = item
        path = args.output / key
        path.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://json.uoga.workers.dev/{key}?certified_release_readback={stamp}"
        digest = hashlib.sha256()
        if args.remote_r2:
            root = Path(__file__).resolve().parents[1]
            subprocess.run(["node", str(root / "node_modules/wrangler/bin/wrangler.js"), "r2", "object", "get",
                            f"uoga-data/{key}", "--file", str(path), "--remote", "--config", str(root / "wrangler.r2-runtime.jsonc")],
                           check=True, stdout=subprocess.DEVNULL)
            with path.open("rb") as handle:
                digest = hashlib.file_digest(handle, "sha256")
            url = f"r2://uoga-data/{key}"
        else:
            request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(request, timeout=60) as response, path.open("wb") as output:
                for chunk in iter(lambda: response.read(1024 * 1024), b""):
                    digest.update(chunk)
                    output.write(chunk)
        actual = digest.hexdigest()
        if actual != expected:
            raise RuntimeError(f"Live state changed for {key}: expected {expected}, got {actual}")
        print(f"VERIFIED {key} {actual}", flush=True)
        return {"key": key, "url": url, "sha256": actual, "bytes": path.stat().st_size}

    with ThreadPoolExecutor(max_workers=2) as pool:
        retained = list(pool.map(fetch, objects))
    (args.output / "snapshot_manifest.json").write_text(json.dumps({"status": "PASS", "retrieved_at": stamp, "objects": retained}, indent=2) + "\n")


if __name__ == "__main__":
    main()
