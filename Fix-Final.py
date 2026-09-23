import pathlib, re
p = pathlib.Path('engine/utah_draw_predictive/bear.py').read_text(encoding='utf-8')

# 1. Fix restricted pursuit -> should be RESTRICTED_BEAR_PURSUIT, not UNKNOWN
p = re.sub(
    r'if "restricted pursuit" in text:\s*\n\s*return UNKNOWN_BEAR_SUBTYPE',
    'if "restricted pursuit" in text:\n return RESTRICTED_BEAR_PURSUIT',
    p
)

# 2. Fix unlimited pursuit condition to also exclude official pursuit codes
p = p.replace(
    'if hunt_code not in official_draw_codes and (hunt_type == "pursuit"',
    'if hunt_code not in official_draw_codes and hunt_code not in official_pursuit_codes and (hunt_type == "pursuit"'
)

# 3. Ensure V7 LE 90 stays
if 'def official_bear_draw_odds_hunt_codes() -> set[str]:\n return set(_parse_official_bear_draw_odds_pdf().keys())' in p:
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
print("fixed pursuit classifier + V7")
