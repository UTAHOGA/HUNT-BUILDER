from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/rebuild-runtime-hunt-master-and-split.py"


def load_module():
    spec = importlib.util.spec_from_file_location("runtime_hunt_master", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bear_hunt_name_never_falls_back_to_boundary_id_or_odds_text():
    module = load_module()
    good = {"hunt_code": "BR7000", "hunt_name": "Beaver", "boundary_id": "410"}
    assert module.to_runtime_record(good, "2026-09-20T00:00:00Z")["hunt_name"] == "Beaver"

    for invalid in ("", "410", "BR7000", "N/A", "1 in 19.0"):
        row = {"hunt_code": "BR7000", "hunt_name": invalid, "boundary_id": "410"}
        with pytest.raises(ValueError, match="no valid official hunt_name"):
            module.to_runtime_record(row, "2026-09-20T00:00:00Z")
