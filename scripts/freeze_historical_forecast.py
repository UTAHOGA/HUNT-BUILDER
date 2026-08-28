"""Write a reproducibility manifest for a historical blind-forecast output."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prediction-file", type=Path, required=True)
    parser.add_argument("--source-input", type=Path, required=True)
    parser.add_argument("--frozen-actual-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-year", type=int, required=True)
    parser.add_argument("--target-year", type=int, required=True)
    parser.add_argument(
        "--score-target-year",
        type=int,
        help="Canonical model-target key year when it differs from the forecast draw year.",
    )
    args = parser.parse_args()
    for path in (args.prediction_file, args.source_input, args.frozen_actual_manifest):
        if not path.exists():
            raise FileNotFoundError(path)
    with args.prediction_file.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_year": args.source_year,
        "forecast_draw_year": args.target_year,
        "score_target_year": args.score_target_year or args.target_year,
        "prediction_file": str(args.prediction_file).replace("\\", "/"),
        "prediction_sha256": sha256(args.prediction_file),
        "prediction_bytes": args.prediction_file.stat().st_size,
        "prediction_rows": len(rows),
        "prediction_unique_hunt_codes": len({str(row.get("hunt_code", "")).strip() for row in rows if str(row.get("hunt_code", "")).strip()}),
        "prediction_family_rows": dict(Counter(str(row.get("family", "")).strip() for row in rows)),
        "source_input": str(args.source_input).replace("\\", "/"),
        "source_input_sha256": sha256(args.source_input),
        "frozen_actual_manifest": str(args.frozen_actual_manifest).replace("\\", "/"),
        "truth_opened_before_forecast_freeze": False,
        "status": "FROZEN_HISTORICAL_BLIND_FORECAST",
    }
    if args.output.exists():
        existing = json.loads(args.output.read_text(encoding="utf-8"))
        if existing != manifest:
            raise FileExistsError(f"Refusing to overwrite differing forecast freeze manifest: {args.output}")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
