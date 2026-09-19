"""Restore all six exact pre-publication objects after a scoped release abort."""
import argparse
import json
from pathlib import Path
from publish_verified_certified_core_r2 import ALLOWED, sha, wrangler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transaction-dir", type=Path, required=True)
    args = parser.parse_args()
    transaction = json.loads((args.transaction_dir / "transaction.json").read_text())
    records = transaction["objects"]
    if {r["key"] for r in records} != ALLOWED or not all(r["rollback_verified"] for r in records):
        raise ValueError("Complete verified rollback set required")
    for record in records:
        before = args.transaction_dir / "before" / record["key"]
        if sha(before) != record["before_sha256"]:
            raise ValueError(f"Rollback source changed: {record['key']}")
    result = {"status": "ROLLBACK_IN_PROGRESS", "reason": "Preserve unrelated harvest context in prediction-only release", "objects": []}
    log = args.transaction_dir / "rollback_result.json"
    for record in records:
        key = record["key"]
        before = args.transaction_dir / "before" / key
        wrangler("put", key, before)
        readback = args.transaction_dir / "restored_readback" / key
        readback.parent.mkdir(parents=True, exist_ok=True)
        wrangler("get", key, readback)
        if sha(readback) != record["before_sha256"]:
            raise ValueError(f"Rollback readback mismatch: {key}")
        result["objects"].append({"key": key, "restored_sha256": sha(readback)})
        log.write_text(json.dumps(result, indent=2) + "\n")
        print(f"RESTORED_VERIFIED {key}", flush=True)
    result["status"] = "PASS_ALL_SIX_ORIGINAL_OBJECTS_RESTORED"
    log.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
