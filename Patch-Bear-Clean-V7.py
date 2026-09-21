raise SystemExit("DISABLED_UNREVIEWED_REPAIR: regex patch can corrupt Bear source indentation. See docs/CORRECTIVE_RELEASE_20260921.md.")

import pathlib
p = pathlib.Path('engine/utah_draw_predictive/bear.py').read_text(encoding='utf-8')

# --- keep the 3 availability fixes from fix_and_rebuild_bear.py (they were correct) ---
p = p.replace(
    ' if "restricted pursuit" in text or hunt_type == "pursuit" or hunt_type.startswith("pursuit") or weapon == "pursuit only":\n return UNLIMITED_PURSUIT_PERMIT',
    ' if "restricted pursuit" in text:\n return RESTRICTED_BEAR_PURSUIT\n if hunt_type == "pursuit" or hunt_type.startswith("pursuit") or weapon == "pursuit only":\n return UNLIMITED_PURSUIT_PERMIT'
)
import re
p = re.sub(
    r'if "restricted pursuit" in text:\s*\n\s*return UNKNOWN_BEAR_SUBTYPE',
    'if "restricted pursuit" in text:\n return RESTRICTED_BEAR_PURSUIT',
    p
)
p = p.replace(
    ' if hunt_code not in official_draw_codes and (hunt_type == "pursuit" or hunt_type.startswith("pursuit") or weapon == "pursuit only"):',
    ' if hunt_code not in official_draw_codes and hunt_code not in official_pursuit_codes and (hunt_type == "pursuit" or hunt_type.startswith("pursuit") or weapon == "pursuit only"):'
)

# --- V7: 2026 official = 90 hunting + 9 restricted = 99 total ---
# retired = 4 La Sal + BR7237 per docs/bear_availability_validation_2026.md
old_func = '''def official_bear_draw_odds_hunt_codes() -> set[str]:
    return set(_parse_official_bear_draw_odds_pdf().keys())'''
new_func = '''def official_bear_draw_odds_hunt_codes() -> set[str]:
    base = set(_parse_official_bear_draw_odds_pdf().keys())
    # 2026 DWR: 5 codes absent from 2026 tables (4 La Sal + BR7237 Monroe fall)
    retired_2026 = set(BEAR_HISTORICAL_CODE_SUCCESSORS_2026.keys()) | {"BR7237"}
    new_2026 = {"BR7021","BR7022","BR7126","BR7127","BR7238","BR7239","BR7326"}
    return (base - retired_2026) | new_2026'''

if old_func in p:
    p = p.replace(old_func, new_func)
    print("Patched official_bear_draw_odds_hunt_codes")
else:
    print("WARNING: old_func not found")

pathlib.Path('engine/utah_draw_predictive/bear.py').write_text(p, encoding='utf-8')
print("wrote bear.py")
