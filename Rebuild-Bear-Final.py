import pathlib, sys, csv, json
repo = pathlib.Path(".").resolve()
sys.path.insert(0, str(repo))
# ensure inits
for p in [repo/"engine"/"__init__.py", repo/"engine"/"utah_draw_predictive"/"__init__.py"]:
    if not p.exists():
        p.write_text("# init\n")

# package import (avoids dataclass error)
import importlib
bear = importlib.import_module("engine.utah_draw_predictive.bear")
print("Imported bear via package:", bear.official_bear_draw_odds_hunt_codes().__len__(), "codes")

# Load DATABASE.csv
db_csv = repo / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
if not db_csv.exists():
    db_csv = next(repo.glob("**/DATABASE.csv"))
db_rows = list(csv.DictReader(db_csv.open(encoding="utf-8-sig")))
print(f"DB rows {len(db_rows)} from {db_csv}")

# Load truth
truth_rows = []
for cf in (repo/"data_truth").rglob("*.csv"):
    if "bear" in cf.name.lower():
        try:
            truth_rows.extend(list(csv.DictReader(cf.open(encoding="utf-8-sig"))))
        except: pass
print(f"truth_rows {len(truth_rows)}")

point_purchase_rows = []
for cf in (repo/"data_truth").rglob("*point_purchase*.csv"):
    try:
        point_purchase_rows.extend(list(csv.DictReader(cf.open(encoding="utf-8-sig"))))
    except: pass

rows, report = bear.build_bear_bonus_predictions(
    truth_rows=truth_rows,
    db_rows=db_rows,
    forecast_year=2026,
    history_years=[2018,2019,2020,2021,2022,2023,2024,2025],
    central_estimate_mode="deterministic",
    iterations=1,
    seed=20260701,
    returning_cohort_mode="off",
    point_purchase_rows=point_purchase_rows,
)
out = repo/"processed_data"
out.mkdir(exist_ok=True)
(out/"bear_report.json").write_text(json.dumps(report, indent=2))
print(report['bear_rows_by_algorithm_status'])
print(f"LE {report['limited_entry_hunt_modeled_hunt_code_count']} Pursuit {report['restricted_pursuit_modeled_hunt_code_count']}")
