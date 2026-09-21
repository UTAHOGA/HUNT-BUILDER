import pathlib
p = pathlib.Path('engine/utah_draw_predictive/bear.py').read_text()

# Patch official_bear_draw_odds_hunt_codes to return 2026 set
old_func = '''def official_bear_draw_odds_hunt_codes() -> set[str]:
    return set(_parse_official_bear_draw_odds_pdf().keys())'''

new_func = '''def official_bear_draw_odds_hunt_codes() -> set[str]:
    base = set(_parse_official_bear_draw_odds_pdf().keys())
    # 2026 DWR successor logic: old public codes retired, new codes added
    retired_2026 = set(BEAR_HISTORICAL_CODE_SUCCESSORS_2026.keys()) # BR7008, BR7108, BR7208, BR7307
    new_2026 = {"BR7021","BR7022","BR7126","BR7127","BR7238","BR7239","BR7326"}
    return (base - retired_2026) | new_2026'''

if old_func in p:
    p = p.replace(old_func, new_func)
    pathlib.Path('engine/utah_draw_predictive/bear.py').write_text(p)
    print("Patched official_bear_draw_odds_hunt_codes to 2026 = 100 total")
else:
    print("FAILED to find func to patch - paste lines 294-296")
