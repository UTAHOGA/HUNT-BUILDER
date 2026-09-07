from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SUMMARY = (
    ROOT
    / "data_truth"
    / "harvest_results_truth"
    / "validation"
    / "current_2025_reconciliation"
    / "summary.json"
)


def test_current_harvest_reconciliation_is_idempotent_and_protected() -> None:
    subprocess.run(
        [sys.executable, "scripts/reconcile-current-harvest-to-canonical.py", "--audit-only"],
        cwd=ROOT,
        check=True,
    )
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))

    assert summary["source_rows"] == 1141
    assert summary["boundary_id_used"] is False
    assert summary["database"]["changed_cells"] == 0
    assert summary["reference"]["changed_cells"] == 0
    assert summary["database"]["status_counts"] == {
        "HUNT_CODE_NAME_OR_SPECIES_MISMATCH": 15,
        "MATCHED_CODE_NAME_SPECIES": 1117,
        "MISSING_HUNT_CODE": 9,
    }
    protected = summary["protected_field_fingerprints"]
    assert protected["database_unchanged"] is True
    assert protected["reference_unchanged"] is True
