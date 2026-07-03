#!/usr/bin/env python3
"""Run only the non-mutating prediction calibration slice of the hardening audit."""

from __future__ import annotations

import argparse
from pathlib import Path

from run_engine_hardening_validation_calibration import HardeningAudit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--years", nargs="*", type=int, default=[2021, 2022, 2023, 2024, 2025, 2026])
    parser.add_argument("--target-years", nargs="*", type=int, default=[2026, 2027])
    args = parser.parse_args()

    audit = HardeningAudit(
        repo=Path(args.repo).resolve(),
        output_dir=Path(args.output_dir).resolve(),
        years=args.years,
        target_years=args.target_years,
        strict=False,
    )
    audit.output_dir.mkdir(parents=True, exist_ok=True)
    audit.truth_universe()
    audit.runtime_inventory_and_validation()
    audit.calibration_audit()
    print(f"CALIBRATION_AUDIT_OUTPUT_DIR: {audit.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
