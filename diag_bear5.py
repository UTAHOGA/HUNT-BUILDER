import sys
sys.path.insert(0, ".")
import engine.utah_draw_predictive.bear as b
draw = sorted(b.official_bear_draw_odds_hunt_codes())
purs = sorted(b.official_bear_pursuit_hunt_codes())
print(f"DRAW {len(draw)}: {draw}")
print(f"\nPURSUIT {len(purs)}: {purs}")
print(f"\nMODELED_SUBTYPES: {b.MODELED_BEAR_SUBTYPES}")
print(f"EXCLUDED_SUBTYPES: {b.EXCLUDED_BEAR_SUBTYPES}")

# check which of the 7 are in draw
splits = ["BR7021","BR7022","BR7126","BR7127","BR7238","BR7239","BR7326","BR7307","BR7008","BR7108","BR7208"]
for code in splits:
    in_draw = code in b.official_bear_draw_odds_hunt_codes()
    print(f"{code} in_draw={in_draw}")

# check materialize count logic
import pathlib, json
rep_path = pathlib.Path('processed_data/bear_report.json')
j=json.loads(rep_path.read_text())
print("\nReport:", j['bear_rows_by_algorithm_status'])
print("LE modeled hunt_code count:", j['limited_entry_hunt_modeled_hunt_code_count'])
