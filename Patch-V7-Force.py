import pathlib, re
p = pathlib.Path('engine/utah_draw_predictive/bear.py').read_text(encoding='utf-8')
# force replace regardless of spacing
p = re.sub(
    r'def official_bear_draw_odds_hunt_codes\(\) -> set\[str\]:\s*\n\s*return set\(_parse_official_bear_draw_odds_pdf\(\)\.keys\(\)\)',
    '''def official_bear_draw_odds_hunt_codes() -> set[str]:
    base = set(_parse_official_bear_draw_odds_pdf().keys())
    retired_2026 = set(BEAR_HISTORICAL_CODE_SUCCESSORS_2026.keys()) | {"BR7237"}
    new_2026 = {"BR7021","BR7022","BR7126","BR7127","BR7238","BR7239","BR7326"}
    return (base - retired_2026) | new_2026''',
    p
)
pathlib.Path('engine/utah_draw_predictive/bear.py').write_text(p, encoding='utf-8')
print("patched")
