import pathlib
p = pathlib.Path('engine/utah_draw_predictive/bear.py').read_text(encoding='utf-8')
old = 'def official_bear_draw_odds_hunt_codes() -> set[str]:\n return set(_parse_official_bear_draw_odds_pdf().keys())'
new = '''def official_bear_draw_odds_hunt_codes() -> set[str]:
    base = set(_parse_official_bear_draw_odds_pdf().keys())
    retired_2026 = set(BEAR_HISTORICAL_CODE_SUCCESSORS_2026.keys()) | {"BR7237"}
    new_2026 = {"BR7021","BR7022","BR7126","BR7127","BR7238","BR7239","BR7326"}
    return (base - retired_2026) | new_2026'''
if old in p:
    p = p.replace(old, new)
    pathlib.Path('engine/utah_draw_predictive/bear.py').write_text(p, encoding='utf-8')
    print("patched V7 to 90 LE")
else:
    print("old not found, already patched?")
