#!/usr/bin/env python3
"""Minify large runtime JSON files without changing their values."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TARGETS = [
    "processed_data/hunt_research_2026.json",
    "processed_data/hunt_research_2026_ladder.json",
    "processed_data/hunt_research_2026_ladder_preference.json",
    "processed_data/hunt_research_2026_ladder_bonus_max_random.json",
]


def main() -> None:
    for rel_path in TARGETS:
        path = ROOT / rel_path
        if not path.exists():
            print(f"skip missing {rel_path}")
            continue
        before = path.stat().st_size
        payload = json.loads(path.read_text(encoding="utf-8"))
        path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        after = path.stat().st_size
        print(f"{rel_path}: {before} -> {after} bytes")


if __name__ == "__main__":
    main()
