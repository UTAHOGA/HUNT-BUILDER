"""Resolve the ten retained pending identities against yearly canonical truth."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PENDING_CODES = {"DA1006", "DA1008", "DA1014", "DA1015", "EA1057", "EA1083", "EA1123", "EA1133", "EA1169", "EA1188"}


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def audit(truth, predictions):
    dispositions, failures = [], []
    for code in sorted(PENDING_CODES):
        sources = [r for r in truth if r.get("hunt_code") == code]
        rows = [r for r in predictions if r.get("hunt_code") == code]
        designs = sorted({r.get("draw_system_type") for r in sources})
        years = sorted({r.get("actual_draw_year") for r in sources})
        leaks = [r for r in rows if any(str(r.get(f, "")).strip() for f in ("p_draw", "p_draw_mean", "certified_p_draw"))]
        unresolved = [r for r in rows if r.get("algorithm_status") != "EXCLUDED_NOT_PREDICTIVE_DRAW" or r.get("draw_system_type") not in designs]
        if not sources or not rows or leaks or unresolved or years != ["2017"]:
            failures.append(code)
        dispositions.append({
            "hunt_code": code, "canonical_designs": designs, "canonical_years": years,
            "canonical_rows": len(sources), "candidate_rows": len(rows),
            "status": "HISTORICAL_REFERENCE_ONLY" if code not in failures else "UNRESOLVED",
            "source_evidence": sorted({f"{r.get('source_file', '')}#page={r.get('pdf_page', '')}" for r in sources}),
            "probability_rows": len(leaks), "misclassified_rows": len(unresolved),
        })
    return {"status": "FAIL" if failures else "PASS", "records": dispositions, "failures": failures}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--truth", type=Path, default=ROOT / "data_truth/draw_results_truth/normalized/draw_results_long.csv")
    parser.add_argument("--prediction", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(read(args.truth), read(args.prediction))
    result["inputs"] = {name: {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for name, path in (("truth", args.truth), ("prediction", args.prediction))}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "resolved": 10 - len(result["failures"]), "failures": result["failures"]}))
    return int(bool(result["failures"]))


if __name__ == "__main__":
    raise SystemExit(main())
