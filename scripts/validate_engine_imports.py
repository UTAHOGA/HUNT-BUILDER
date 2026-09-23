"""Code-only safety gate: compile owning modules and import their real entrypoints.

No prediction materialization, network access, or bytecode writes are performed.
This is not a statistical certification or a replacement for source/data tests.
"""
from __future__ import annotations

import importlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINTS = (
    "engine.utah_draw_predictive.classifier",
    "engine.utah_draw_predictive.run_all_families",
    "engine.utah_bonus_predictive.materialize",
    "engine.utah_predictive_mixed.materialize",
)


def main() -> int:
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(ROOT))
    files = sorted((ROOT / "engine").rglob("*.py"))
    for source in files:
        compile(source.read_bytes(), str(source.relative_to(ROOT)), "exec")
    for name in ENTRYPOINTS:
        importlib.import_module(name)
    print(f"PASS: {len(files)} engine modules compile; {len(ENTRYPOINTS)} real entrypoints import")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
