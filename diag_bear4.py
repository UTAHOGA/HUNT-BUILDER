import sys
sys.path.insert(0, ".")
import engine.utah_draw_predictive.bear as b
import pathlib
# Show how bear.py defines LE counts
text = pathlib.Path('engine/utah_draw_predictive/bear.py').read_text()[:8000]
print(text[2000:6000])

print("\n--- official lists ---")
print("draw_odds 97:", b.official_bear_draw_odds_hunt_codes()[:20])
print("pursuit 9:", b.official_bear_pursuit_hunt_codes())
# try classify with row dict
for code in ["BR7021","BR7022","BR7126","BR7127","BR7238","BR7239","BR7326","BR1007","BR1018"]:
    row={"hunt_code":code,"species":"Bear","subtype":""}
    try:
        print(code, b.classify_bear_subtype(row), b.is_modeled_bear_row(row), b.is_excluded_bear_row(row))
    except Exception as e:
        print(code, "ERR", e)
