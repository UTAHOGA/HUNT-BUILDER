import pathlib, re, sys, csv, json, importlib.util, types

repo = pathlib.Path(".").resolve()
bear_path = repo / "engine" / "utah_draw_predictive" / "bear.py"

print(f"Patching {bear_path}...")
txt = bear_path.read_text(encoding="utf-8")

# Idempotent patches - only if not already fixed
if '    if "restricted pursuit" in text or hunt_type == "pursuit"' in txt:
    txt = txt.replace(
        '    if "restricted pursuit" in text or hunt_type == "pursuit" or hunt_type.startswith("pursuit") or weapon == "pursuit only":\n        return UNLIMITED_PURSUIT_PERMIT',
        '    if "restricted pursuit" in text:\n        return RESTRICTED_BEAR_PURSUIT\n    if hunt_type == "pursuit" or hunt_type.startswith("pursuit") or weapon == "pursuit only":\n        return UNLIMITED_PURSUIT_PERMIT'
    )
    print("  Applied Fix 1: before_source_correction split")

if 'if "restricted pursuit" in text:\n        return UNKNOWN_BEAR_SUBTYPE' in txt:
    txt = txt.replace(
        'if "restricted pursuit" in text:\n        return UNKNOWN_BEAR_SUBTYPE',
        'if "restricted pursuit" in text:\n        return RESTRICTED_BEAR_PURSUIT'
    )
    print("  Applied Fix 2: UNKNOWN -> RESTRICTED")

if '    if hunt_code not in official_draw_codes and (hunt_type == "pursuit"' in txt:
    txt = txt.replace(
        '    if hunt_code not in official_draw_codes and (hunt_type == "pursuit" or hunt_type.startswith("pursuit") or weapon == "pursuit only"):',
        '    if hunt_code not in official_draw_codes and hunt_code not in official_pursuit_codes and (hunt_type == "pursuit" or hunt_type.startswith("pursuit") or weapon == "pursuit only"):'
    )
    print("  Applied Fix 3: added official_pursuit_codes guard")

bear_path.write_text(txt, encoding="utf-8")
print("Patched bear.py written")

# Ensure inits exist
for p in [repo/"engine"/"__init__.py", repo/"engine"/"utah_draw_predictive"/"__init__.py", repo/"engine"/"utah_bonus_predictive"/"__init__.py"]:
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# init\n")
        print(f"Created {p}")

sys.path.insert(0, str(repo))

# Create parent packages in sys.modules to prevent dataclass __module__ None bug
for mod_name in ["engine", "engine.utah_draw_predictive", "engine.utah_bonus_predictive"]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = types.ModuleType(mod_name)
        print(f"Inserted {mod_name} into sys.modules")

# Load bear via file with SIMPLE name to avoid dataclass issue
# Using SourceFileLoader with module name 'bear' works
from importlib.machinery import SourceFileLoader
loader = SourceFileLoader("bear", str(bear_path))
bear_mod = types.ModuleType("bear")
bear_mod.__file__ = str(bear_path)
sys.modules["bear"] = bear_mod
loader.exec_module(bear_mod)
bear = bear_mod
print("Loaded bear module via SourceFileLoader")
print("Pursuit codes from PDF:", bear.official_bear_pursuit_hunt_codes())

# Load db_rows
db_csv = repo / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
if not db_csv.exists():
    cands = list((repo / "pipeline" / "RAW").rglob("DATABASE.csv"))
    if cands:
        db_csv = cands[0]
        print(f"Using alternate DATABASE.csv: {db_csv}")

db_rows = list(csv.DictReader(db_csv.open(encoding="utf-8-sig")))
print(f"Loaded {len(db_rows)} db_rows")

# Load truth rows
truth_dir = repo / "data_truth"
truth_rows = []
if truth_dir.exists():
    for cf in truth_dir.rglob("*.csv"):
        if "black_bear" in cf.name.lower() or "bear" in cf.name.lower():
            try:
                truth_rows.extend(list(csv.DictReader(cf.open(encoding="utf-8-sig"))))
            except:
                pass
    jf = repo / "data_truth" / "draw_results_truth" / "validation" / "black_bear_2025_BR7307_crosswalk_ladder_rows.json"
    if jf.exists():
        try:
            truth_rows.extend(json.loads(jf.read_text(encoding="utf-8")))
        except:
            pass
print(f"Loaded {len(truth_rows)} truth_rows")

point_purchase_rows = []
if truth_dir.exists():
    for cf in truth_dir.rglob("*point_purchase*.csv"):
        try:
            point_purchase_rows.extend(list(csv.DictReader(cf.open(encoding="utf-8-sig"))))
        except:
            pass

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

out_dir = repo / "processed_data"
out_dir.mkdir(exist_ok=True)
(out_dir / "bear_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(f"\nWrote bear_report.json")
print(report['bear_rows_by_algorithm_status'])
print('LE', report['limited_entry_hunt_modeled_hunt_code_count'], 'Pursuit', report['restricted_pursuit_modeled_hunt_code_count'])

if rows:
    fieldnames = sorted({k for r in rows for k in r.keys()})
    with (out_dir / "bear_draw_odds.csv").open("w", encoding="utf-8", newline="") as f:
        import csv as csvmod
        w = csvmod.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote bear_draw_odds.csv with {len(rows)} rows")

print("\nDone. Should be LE 91 Pursuit 9")
