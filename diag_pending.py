import sys
from pathlib import Path
sys.path.insert(0, str(Path(".").resolve()))
import engine.utah_draw_predictive.bear as bear
import csv

db_path = Path("pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv")
# find truth rows same way Rebuild-Bear-Final does
truth_rows = []
# Rebuild-Bear-Final uses pipeline truth? Let's load data_truth if exists, else use processed
# We'll just inspect db_rows for 2026 bear codes
db_rows = list(csv.DictReader(db_path.open(encoding="utf-8-sig")))
bear_codes_in_db = [r for r in db_rows if r.get("hunt_code","").upper().startswith("BR") and bear.is_bear_row(r)]
print(f"DB bear rows: {len(bear_codes_in_db)}")
for r in bear_codes_in_db[:5]:
    print(r.get("hunt_code"), bear.classify_bear_subtype(r), r.get("hunt_name","")[:60])

# Check history coverage via internal function
from engine.utah_draw_predictive.bear import _build_truth_ladders, _history_years_or_bootstrap
# load truth csvs from data_truth/draw_results_truth ?
import glob
truth_files = glob.glob("data_truth/**/*.csv", recursive=True)
print(f"truth files found: {len(truth_files)}")

# Quick: check bear_report for pending reasons
import json
rep = json.loads(Path("processed_data/bear_report.json").read_text())
print(json.dumps({k:v for k,v in rep.items() if "pending" in k or "missing" in k or "excluded" in k or "new_unit" in k}, indent=2))
