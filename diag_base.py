import engine.utah_draw_predictive.bear as bear
base = bear._parse_official_bear_draw_odds_pdf()
print(f"base total: {len(base)}")
print("all keys sample:", sorted(base.keys())[:15])
from engine.utah_draw_predictive.bear import BEAR_HISTORICAL_CODE_SUCCESSORS_2026
retired = set(BEAR_HISTORICAL_CODE_SUCCESSORS_2026.keys()) | {"BR7237"}
print(f"retired {retired}: {len(retired)}")
new = {"BR7021","BR7022","BR7126","BR7127","BR7238","BR7239","BR7326"}
print(f"new {new}: {len(new)}")
print(f"(base - retired) | new = {(len(base - retired) + len(new - (base - retired)))}")
# Count LE vs pursuit in base
le_in_base = [k for k,v in base.items() if v.get("source_classification")!="BEAR_PURSUIT_BONUS_DRAW"]
pur_in_base = [k for k,v in base.items() if v.get("source_classification")=="BEAR_PURSUIT_BONUS_DRAW"]
print(f"LE in base: {len(le_in_base)}, Pursuit in base: {len(pur_in_base)} -> {sorted(pur_in_base)}")
