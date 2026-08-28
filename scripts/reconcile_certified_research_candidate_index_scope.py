#!/usr/bin/env python3
"""Constrain the local Research candidate index to the current declared code universe."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "audits" / "prediction_blind_backtests" / "2025_to_2026_truth_2018_2026_20260827_certification_candidate" / "research_split_contract_candidate_2026-08-27"
INDEX = CANDIDATE / "processed_data" / "hunt_research_2026_split" / "hunt_research_2026.index.json"
CURRENT_INDEX = ROOT / "processed_data" / "hunt_research_2026_split" / "hunt_research_2026.index.json"
BACKUP = CANDIDATE / "pre_index_scope_reconciliation" / "hunt_research_2026.index.json"
AUDIT = CANDIDATE / "candidate_index_scope_reconciliation.json"


def code(row: dict[str, object]) -> str:
    return str(row.get("hunt_code") or "").strip().upper()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    if not INDEX.exists() or not CURRENT_INDEX.exists():
        raise SystemExit("Candidate or current split index is missing.")
    if BACKUP.exists() or AUDIT.exists():
        raise SystemExit("Refusing to overwrite an existing index-scope reconciliation record.")
    candidate_rows = json.loads(INDEX.read_text(encoding="utf-8"))
    current_rows = json.loads(CURRENT_INDEX.read_text(encoding="utf-8"))
    active_codes = {code(row) for row in current_rows if code(row)}
    candidate_by_code = {code(row): row for row in candidate_rows if code(row)}
    missing_active = sorted(active_codes - set(candidate_by_code))
    if missing_active:
        raise SystemExit(f"Candidate index is missing {len(missing_active)} current codes; not modifying it.")
    selected = [candidate_by_code[hunt_code] for hunt_code in sorted(active_codes)]
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(INDEX, BACKUP)
    prior_hash = sha256(BACKUP)
    with INDEX.open("w", encoding="utf-8") as handle:
        json.dump(selected, handle, ensure_ascii=False, separators=(",", ":"))
        handle.write("\n")
    audit = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "CURRENT_INDEX_SCOPE_RECONCILED",
        "current_declared_code_count": len(active_codes),
        "candidate_code_count_before": len(candidate_by_code),
        "candidate_code_count_after": len(selected),
        "removed_summary_only_code_count": len(candidate_by_code) - len(selected),
        "removed_summary_only_code_examples": sorted(set(candidate_by_code) - active_codes)[:50],
        "backup_path": str(BACKUP.relative_to(ROOT)).replace("\\", "/"),
        "backup_sha256": prior_hash,
        "reconciled_index_sha256": sha256(INDEX),
    }
    AUDIT.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print("CANDIDATE_INDEX_SCOPE_RECONCILIATION=PASS")
    print(json.dumps(audit, sort_keys=True))


if __name__ == "__main__":
    main()
