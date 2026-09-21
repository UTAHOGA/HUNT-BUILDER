"""
Direct rebuild of bear_report.json without needing python -m package discovery.
Run from repo root: python rebuild_bear_direct.py
"""
import pathlib, sys, csv, json, os
repo = pathlib.Path(".").resolve()
sys.path.insert(0, str(repo))

# Ensure all __init__.py exist for package imports
for p in [
    repo/"engine"/"__init__.py",
    repo/"engine"/"utah_draw_predictive"/"__init__.py",
    repo/"engine"/"utah_bonus_predictive"/"__init__.py",
]:
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# init\n")
        print(f"Created {p}")

# Now try package import first
try:
    from engine.utah_draw_predictive import bear
    print("Imported bear via package")
except Exception as e:
    print(f"Package import failed: {e}, trying file import")
    import importlib.util
    bear_path = repo / "engine" / "utah_draw_predictive" / "bear.py"
    spec = importlib.util.spec_from_file_location("engine.utah_draw_predictive.bear", str(bear_path))
    bear = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bear)
    print("Loaded bear via file")

# Load db_rows
db_csv = repo / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
if not db_csv.exists():
    # try alternate
    candidates = list((repo / "pipeline" / "RAW").rglob("DATABASE.csv"))
    print(f"DATABASE.csv not found at {db_csv}, candidates: {candidates[:3]}")
    if candidates:
        db_csv = candidates[0]
        
db_rows = []
with db_csv.open(encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f)
    for row in reader:
        db_rows.append(row)
print(f"Loaded {len(db_rows)} db_rows from {db_csv}")

# Load truth rows - search data_truth
truth_dir = repo / "data_truth"
truth_rows = []
if truth_dir.exists():
    for csv_file in truth_dir.rglob("*.csv"):
        if "black_bear" in csv_file.name.lower() or "bear" in csv_file.name.lower():
            try:
                with csv_file.open(encoding="utf-8-sig", newline="") as f:
                    reader = csv.DictReader(f)
                    for r in reader:
                        truth_rows.append(r)
            except Exception:
                pass
    # also try json validation file
    json_file = repo / "data_truth" / "draw_results_truth" / "validation" / "black_bear_2025_BR7307_crosswalk_ladder_rows.json"
    if json_file.exists():
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            truth_rows.extend(data)
        except Exception:
            pass

print(f"Loaded {len(truth_rows)} truth_rows")

# Load point purchase rows if exists
point_purchase_rows = []
pp_dir = repo / "data_truth"
for csv_file in pp_dir.rglob("*point_purchase*.csv"):
    try:
        with csv_file.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for r in reader:
                point_purchase_rows.append(r)
    except Exception:
        pass

# Build predictions - use same args as original module
forecast_year = 2026
history_years = [2018,2019,2020,2021,2022,2023,2024,2025]

try:
    rows, report = bear.build_bear_bonus_predictions(
        truth_rows=truth_rows,
        db_rows=db_rows,
        forecast_year=forecast_year,
        history_years=history_years,
        central_estimate_mode="deterministic",
        iterations=1,
        seed=20260701,
        returning_cohort_mode="off",
        point_purchase_rows=point_purchase_rows,
    )
    print(f"Built {len(rows)} rows, report: {report['bear_rows_by_algorithm_status']}")
    print(f"LE {report['limited_entry_hunt_modeled_hunt_code_count']} Pursuit {report['restricted_pursuit_modeled_hunt_code_count']}")
    
    # Write outputs
    out_dir = repo / "processed_data"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "bear_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {out_dir / 'bear_report.json'}")
    
    # Write csv if possible
    if rows:
        import csv as csvmod
        csv_path = out_dir / "bear_draw_odds.csv"
        fieldnames = sorted({k for r in rows for k in r.keys()})
        with csv_path.open("w", encoding="utf-8", newline="") as f:
            writer = csvmod.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Wrote {csv_path}")
        
except Exception as e:
    import traceback
    traceback.print_exc()
    print("Build failed")
