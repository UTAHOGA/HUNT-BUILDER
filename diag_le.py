import sys
sys.path.insert(0, ".")
from engine.utah_draw_predictive.bear import official_bear_draw_odds_hunt_codes
draw = official_bear_draw_odds_hunt_codes()
le = [c for c in draw if not c.startswith('BR10')]
print(f"LE {len(le)}: {sorted(le)}")
