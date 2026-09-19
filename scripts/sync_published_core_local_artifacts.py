"""Hydrate only verified published artifacts; preserve exact local rollback copies."""
import argparse
import json
import shutil
from pathlib import Path
from publish_verified_certified_core_r2 import sha

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "audits/prediction_release_candidates/core_le_deer_repair_20260919"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    if not args.check_only:
        report = json.loads((BASE / "production_promotion_report.json").read_text())
        if report["status"] != "PASS_PROMOTED_AND_PUBLIC_ALIAS_VERIFIED":
            raise ValueError("Verified live publication required before local hydration")
    overlay = json.loads((BASE / "pages_overlay_verification_harvest_preserved.json").read_text())
    release = json.loads((BASE / "research_candidate_harvest_preserved/release_readiness_manifest.json").read_text())
    operations = {}
    for item in release["objects"]:
        if item["role"] == "research_ladder":
            continue
        source = ROOT / item["local_release_candidate"]["path"]
        dest = ROOT / item["r2_key"]
        operations[dest] = (source, item["review_copy_current_r2"]["sha256"])
    for item in overlay["changed"]:
        source = BASE / "pages-release-harvest-preserved" / item["path"]
        operations[ROOT / "pages-dist" / item["path"]] = (source, item["before_sha256"])
        if item["path"].startswith("processed_data/hunt_research_2026_split/hunts/"):
            operations[ROOT / item["path"]] = (source, item["before_sha256"])
    for source, name in ((BASE / "certification_registry.json", "governance/prediction-family-certification.json"),
                         (BASE / "promoted_prediction_manifest.json", "processed_data/utah_bonus_predictive_manifest.json")):
        dest = ROOT / name
        operations[dest] = (source, sha(dest))
    # All normal runtime destinations must still equal the original live copy;
    # an unrelated local edit is a blocker, never permission to overwrite it.
    for dest, (source, expected) in operations.items():
        if not dest.is_file() or sha(dest) != expected:
            raise ValueError(f"Unrelated or unexpected local artifact: {dest}")
        if not source.is_file() and not (args.check_only and source.name == "promoted_prediction_manifest.json"):
            raise FileNotFoundError(source)
    if args.check_only:
        print(f"Local hydration preflight passed for {len(operations)} destinations; no files changed")
        return
    backup = BASE / "local_promotion_backups"
    backup.mkdir(exist_ok=False)
    evidence = []
    for dest, (source, expected) in operations.items():
        before = backup / dest.relative_to(ROOT)
        before.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(dest, before)
        if sha(before) != expected:
            raise ValueError(f"Local rollback hash mismatch: {dest}")
        shutil.copy2(source, dest)
        if sha(dest) != sha(source):
            raise ValueError(f"Local hydration mismatch: {dest}")
        evidence.append({"path": dest.relative_to(ROOT).as_posix(), "before_sha256": expected, "after_sha256": sha(dest)})
    (BASE / "local_promotion_verification.json").write_text(json.dumps({
        "status": "PASS_PUBLISHED_ARTIFACTS_ONLY_LOCAL_SYNC", "objects": evidence,
        "raw_internal_predictions": "RETAINED_ONLY_IN_FROZEN_AUDIT_CANDIDATE",
        "legacy_archive": "UNCHANGED", "git_staged_committed_pushed": False}, indent=2) + "\n")
    print(f"Verified published artifacts hydrated: {len(evidence)}; rollback copies retained")


if __name__ == "__main__":
    main()
