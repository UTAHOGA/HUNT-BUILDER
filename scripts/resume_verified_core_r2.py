"""Resume the same six-object transaction after an interrupted transfer.

Every current remote object must match either its verified rollback copy or
the reviewed candidate. Unknown changes stop the resume without replacement.
"""
import argparse
import json
from pathlib import Path

from publish_verified_certified_core_r2 import ALLOWED, ROOT, sha, wrangler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transaction-dir", type=Path, required=True)
    parser.add_argument("--release-manifest", type=Path, required=True)
    args = parser.parse_args()
    log = args.transaction_dir / "transaction.json"
    transaction = json.loads(log.read_text())
    manifest = json.loads(args.release_manifest.read_text())
    if sha(args.release_manifest) != transaction["release_manifest_sha256"]:
        raise ValueError("Reviewed manifest changed")
    records = transaction["objects"]
    candidates = {r["r2_key"]: r["local_release_candidate"] for r in manifest["objects"] if r["r2_key"] in ALLOWED}
    if set(candidates) != ALLOWED or {r["key"] for r in records} != ALLOWED or len(records) != 6:
        raise ValueError("Exact six-object scope required")
    for record in records:
        key = record["key"]
        if not record["rollback_verified"] or sha(args.transaction_dir / "before" / key) != record["before_sha256"]:
            raise ValueError(f"Rollback source invalid: {key}")
        if sha(ROOT / candidates[key]["path"]) != candidates[key]["sha256"]:
            raise ValueError(f"Candidate changed: {key}")
    # Read the entire transaction population before retrying any write.
    current_hashes = {}
    for record in records:
        key = record["key"]
        current = args.transaction_dir / "resume_preflight" / key
        current.parent.mkdir(parents=True, exist_ok=True)
        wrangler("get", key, current)
        current_hashes[key] = sha(current)
        if current_hashes[key] not in {record["before_sha256"], candidates[key]["sha256"]}:
            raise ValueError(f"Unexpected remote change: {key}")
    transaction["transfer_recovery"] = "REMOTE_BEFORE_OR_CANDIDATE_HASHES_REVERIFIED_AFTER_AUTHENTICATION_ERROR"
    for record in records:
        key = record["key"]
        expected = candidates[key]["sha256"]
        if current_hashes[key] != expected:
            wrangler("put", key, ROOT / candidates[key]["path"])
            record["replacement_uploaded"] = True
            log.write_text(json.dumps(transaction, indent=2) + "\n")
            after = args.transaction_dir / "after" / key
            after.parent.mkdir(parents=True, exist_ok=True)
            wrangler("get", key, after)
            actual = sha(after)
        else:
            actual = current_hashes[key]
        if actual != expected:
            transaction["status"] = "READBACK_FAILED_ROLLBACK_REQUIRED"
            log.write_text(json.dumps(transaction, indent=2) + "\n")
            raise ValueError(f"Readback mismatch: {key}")
        record.update(replacement_uploaded=True, replacement_verified=True, after_sha256=actual)
        log.write_text(json.dumps(transaction, indent=2) + "\n")
        print(f"RESUME_VERIFIED {key}", flush=True)
    transaction["status"] = "PASS_SIX_OBJECTS_PUBLISHED_AND_HASH_VERIFIED"
    log.write_text(json.dumps(transaction, indent=2) + "\n")
    print(transaction["status"], flush=True)


if __name__ == "__main__":
    main()
