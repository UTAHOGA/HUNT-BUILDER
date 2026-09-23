import pathlib
p = pathlib.Path('engine/utah_draw_predictive/bear.py').read_text(encoding='utf-8')
# 1) fix restricted pursuit UNKNOWN -> RESTRICTED
p = p.replace('if "restricted pursuit" in text:\n        return UNKNOWN_BEAR_SUBTYPE', 'if "restricted pursuit" in text:\n        return RESTRICTED_BEAR_PURSUIT')
# 2) fix unlimited pursuit to exclude official pursuit codes too
p = p.replace('if hunt_code not in official_draw_codes and (hunt_type == "pursuit"', 'if hunt_code not in official_draw_codes and hunt_code not in official_pursuit_codes and (hunt_type == "pursuit"')
pathlib.Path('engine/utah_draw_predictive/bear.py').write_text(p, encoding='utf-8')
print("fixed")
