import pathlib
p = pathlib.Path('engine/utah_draw_predictive/bear.py').read_text()
# fix retired set to 5 codes = 4 La Sal + BR7237
p = p.replace(
    'retired_2026 = set(BEAR_HISTORICAL_CODE_SUCCESSORS_2026.keys()) # BR7008, BR7108, BR7208, BR7307',
    'retired_2026 = set(BEAR_HISTORICAL_CODE_SUCCESSORS_2026.keys()) | {"BR7237"} # 5 retired for 2026 per validation doc: 4 La Sal + BR7237 Monroe fall'
)
pathlib.Path('engine/utah_draw_predictive/bear.py').write_text(p)
print("patched retired to 5")
