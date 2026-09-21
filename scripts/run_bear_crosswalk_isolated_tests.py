"""Run the unchanged, write-producing crosswalk tests in a bounded mirror."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.audit_bear_controlled_candidates import new_directory
from scripts.audit_bear_pdf_truth_year import digest, dump


def run(out):
    out = new_directory(out)
    inputs = [
        "scripts/crosscompare-black-bear-draw-odds-2024-2025-2026.py",
        "tests/utah/test_black_bear_br_crosscompare_2024_2025_2026.py",
        "pipeline/RAW/hunt_unit_database/2024/pdf/draw_odds/official_dwr_archive/black_bear/24_drawing_odds.pdf",
        "pipeline/RAW/hunt_unit_database/2025/pdf/draw_odds/official_dwr_archive/black_bear/25_drawing_odds.pdf",
        "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv",
    ]
    original_outputs = [
        "data_truth/draw_results_truth/normalized/black_bear_2025_draw_odds_model_target_2026_permit_totals.csv",
        "data_truth/crosswalk_truth/normalized/black_bear_BR_2024_2025_2026_crosswalk.csv",
        "data_truth/crosswalk_truth/validation/black_bear_BR_2024_2025_2026_crosswalk_summary.json",
        "processed_data/black_bear_BR_2024_2025_2026_crosswalk.md",
    ]
    hashes = {p: digest(ROOT / p) for p in inputs + original_outputs}
    for relative in inputs:
        destination = out / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
        if digest(destination) != hashes[relative]:
            raise ValueError("Mirror input changed")
    (out / "processed_data").mkdir()
    result = subprocess.run([sys.executable, "-m", "pytest", inputs[1], "-q", "--tb=short",
                             f"--basetemp={out / 'pytest_tmp'}", f"--junitxml={out / 'crosswalk_tests.xml'}"], cwd=out)
    if any(digest(ROOT / p) != h for p, h in hashes.items()):
        raise ValueError("Original crosswalk source/output changed")
    dump(out / "isolation_verification.json", {"exit_code": result.returncode, "original_files_unchanged": hashes,
                                              "test_and_script_unmodified": True})
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    run(parser.parse_args().out_dir.resolve())
