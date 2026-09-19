"""Publish only the six hash-gated core objects, after complete rollback backup.

Requires a passing release-readiness manifest and explicit --apply. Does not
deploy Pages, stage Git files, publish the oversized archive, or touch truth.
"""
import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = {
    "processed_data/hunt_research_2026_summary.json",
    "processed_data/hunt_research_2026_split/hunt_research_2026.index.json",
    "processed_data/hunt_research_2026_split/hunt_research_2026.details.json",
    "processed_data/point_ladder_view.csv",
    "processed_data/draw_reality_engine_predictive_v2.csv",
    "processed_data/ml_draw_predictions_v1.csv",
}


def sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def wrangler(action, key, path):
    command = ["node", str(ROOT / "node_modules/wrangler/bin/wrangler.js"), "r2", "object", action,
               f"uoga-data/{key}", "--file", str(path), "--remote", "--config", str(ROOT / "wrangler.r2-runtime.jsonc")]
    if action == "put":
        command += ["--content-type", "application/json" if key.endswith(".json") else "text/csv; charset=utf-8",
                    "--cache-control", "public, max-age=300"]
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    manifest = json.loads(args.release_manifest.read_text())
    if manifest["status"] != "LOCAL_RELEASE_CANDIDATE_VALIDATED_AUTHORIZED_PROMOTION_PENDING_EXECUTION":
        raise SystemExit("Release-readiness gate has not passed")
    if args.output.exists():
        raise SystemExit("Refusing to overwrite a publication transaction")
    objects = [r for r in manifest["objects"] if r["r2_key"] in ALLOWED]
    if {r["r2_key"] for r in objects} != ALLOWED or len(objects) != 6:
        raise SystemExit("Release manifest must contain exactly the six authorized runtime objects")
    for row in objects:
        candidate = ROOT / row["local_release_candidate"]["path"]
        if sha(candidate) != row["local_release_candidate"]["sha256"]:
            raise SystemExit(f"Candidate changed after validation: {row['r2_key']}")
    if not args.apply:
        print("DRY_RUN: six authorized hash-verified objects; no external write")
        return
    args.output.mkdir(parents=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    transaction = {"status": "PREWRITE_VERIFICATION", "authorization": "Tyler 2026-09-19: keep working until fixed and published online",
                   "release_manifest_sha256": sha(args.release_manifest), "rollback_namespace": f"rollback/{stamp}/", "objects": []}
    log = args.output / "transaction.json"
    def save():
        log.write_text(json.dumps(transaction, indent=2) + "\n", encoding="utf-8")
    save()
    # No replacement begins until every current object is re-read, backed up,
    # and the remote rollback copy itself has been downloaded and verified.
    for row in objects:
        key = row["r2_key"]
        before = args.output / "before" / key
        before.parent.mkdir(parents=True, exist_ok=True)
        wrangler("get", key, before)
        if sha(before) != row["review_copy_current_r2"]["sha256"]:
            raise SystemExit(f"Live object changed since review; no replacement performed: {key}")
        backup_key = f"rollback/{stamp}/{key}"
        wrangler("put", backup_key, before)
        verify = args.output / "rollback_readback" / key
        verify.parent.mkdir(parents=True, exist_ok=True)
        wrangler("get", backup_key, verify)
        if sha(verify) != sha(before):
            raise SystemExit(f"Remote rollback hash mismatch: {key}")
        transaction["objects"].append({"key": key, "before_sha256": sha(before), "rollback_key": backup_key,
                                      "rollback_verified": True, "replacement_uploaded": False})
        save()
    transaction["status"] = "BACKUPS_VERIFIED_REPLACING_SIX_OBJECTS"
    save()
    for row, record in zip(objects, transaction["objects"]):
        key = row["r2_key"]
        candidate = ROOT / row["local_release_candidate"]["path"]
        if sha(candidate) != row["local_release_candidate"]["sha256"]:
            raise SystemExit(f"Candidate changed immediately before upload: {key}")
        wrangler("put", key, candidate)
        record["replacement_uploaded"] = True
        save()
        after = args.output / "after" / key
        after.parent.mkdir(parents=True, exist_ok=True)
        wrangler("get", key, after)
        record["after_sha256"] = sha(after)
        if sha(after) != sha(candidate):
            transaction["status"] = "READBACK_FAILED_ROLLBACK_REQUIRED"
            save()
            raise SystemExit(f"Post-upload hash mismatch: {key}")
        record["replacement_verified"] = True
        save()
        print(f"PUBLISHED_VERIFIED {key}", flush=True)
    transaction["status"] = "PASS_SIX_OBJECTS_PUBLISHED_AND_HASH_VERIFIED"
    save()
    print(json.dumps({"status": transaction["status"], "rollback_namespace": transaction["rollback_namespace"]}))


if __name__ == "__main__":
    main()
