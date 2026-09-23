import sys
from pathlib import Path
sys.path.insert(0, ".")
import engine.utah_draw_predictive.bear as bear, csv, json
db_path = Path("pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv")
db_rows = list(csv.DictReader(db_path.open(encoding="utf-8-sig")))
official_le = bear.official_bear_draw_odds_hunt_codes()
print(f"official LE 90 set: {len(official_le)}")
db_bear = [r for r in db_rows if bear.is_bear_row(r)]
db_le_in_official = [r for r in db_bear if r.get("hunt_code","").upper() in official_le]
print(f"DB rows matching official LE 90: {len(db_le_in_official)}")
print(sorted(set(r.get("hunt_code") for r in db_le_in_official))[:20])

# Check report for which codes actually modeled
rep = json.loads(Path("processed_data/bear_report.json").read_text())
print("modeled hunt codes:", rep.get("modeled_bear_hunt_code_count"), rep.get("limited_entry_hunt_modeled_hunt_code_count"))
# Load processed predictions to see which codes survived
pred_path = Path("processed_data/bear_predictions_2026.csv")
if pred_path.exists():
    rows = list(csv.DictReader(pred_path.open(encoding="utf-8-sig")))
    modeled = [r for r in rows if r.get("algorithm_status")=="MODELED_BONUS"]
    print(f"predicted modeled rows: {len(modeled)}")
    print("distinct modeled codes:", sorted(set(r.get("hunt_code") for r in modeled)))
    pending = [r for r in rows if r.get("algorithm_status")!="MODELED_BONUS"]
    # show first few pending reasons
    for r in pending[:10]:
        print(r.get("hunt_code"), r.get("bear_draw_subtype"), r.get("algorithm_status"), r.get("data_quality_flags")[:80])
