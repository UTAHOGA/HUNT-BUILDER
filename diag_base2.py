import engine.utah_draw_predictive.bear as bear
base = bear._parse_official_bear_draw_odds_pdf()
base_keys = set(base.keys())
retired = set(bear.BEAR_HISTORICAL_CODE_SUCCESSORS_2026.keys()) | {"BR7237"}
new = {"BR7021","BR7022","BR7126","BR7127","BR7238","BR7239","BR7326"}
result = (base_keys - retired) | new
print(f"base {len(base_keys)} - retired {len(retired)} + new {len(new)} = {len(result)}")
le_in_base = [k for k,v in base.items() if v.get("source_classification")!="BEAR_PURSUIT_BONUS_DRAW"]
pur_in_base = [k for k,v in base.items() if v.get("source_classification")=="BEAR_PURSUIT_BONUS_DRAW"]
print(f"LE in base PDF: {len(le_in_base)}")
print(f"Pursuit in base PDF: {len(pur_in_base)} -> {sorted(pur_in_base)}")
print(f"LE after V7: {len([k for k in result if k not in pur_in_base and not k.startswith('BR10')]) + len([k for k in result if k in le_in_base]) }")
print(f"result sorted: {sorted(result)}")
