import pathlib
p = pathlib.Path("check_bear.py")
p.write_text("""import engine.utah_draw_predictive.bear as bear
from collections import Counter
import pathlib, csv, json

# Official set - should be 99 total (90 LE + 9 pursuit)
official = bear.official_bear_draw_odds_hunt_codes()
official_le = [c for c in official if not c.startswith("BR10")]  # exclude pursuit BR1008-1017
# pursuit codes are BR1008-1017
pursuit = [c for c in official if c.startswith("BR10")]

print(f"Official total: {len(official)} (expected 99)")
print(f"Official LE: {len(official_le)} (expected 90)")
print(f"Official Pursuit: {len(pursuit)} (expected 9) -> {sorted(pursuit)}")

# Read rebuild output if exists
for path in [pathlib.Path("processed_data/bear_predictions_2026.csv"), pathlib.Path("pipeline/processed/bear_predictions_2026.csv")]:
    if path.exists():
        rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
        c = Counter(r.get("algorithm_status") for r in rows)
        print(f"\\nRebuild status: {dict(c)}")
        break

# Final V7 assertions
assert len(official) == 99, f"FAIL official total should be 99 got {len(official)}"
assert len(official_le) == 90, f"FAIL official LE should be 90 got {len(official_le)}"
assert len(pursuit) == 9, f"FAIL pursuit should be 9 got {len(pursuit)}"
print("\\nPASS - V7 canonical: 99 total, 90 LE, 9 Pursuit")
print("Note: MODELED_BONUS 54 + AVAIL 4 is expected - 179 pending is new units without history ladder")
""", encoding="utf-8")
print("Wrote new check_bear.py")
