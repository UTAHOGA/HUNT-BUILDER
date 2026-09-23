import pathlib, subprocess, sys
repo = pathlib.Path(".")
bear_path = repo / "engine/utah_draw_predictive/bear.py"

# Apply V7 patch via file edit (idempotent)
text = bear_path.read_text(encoding="utf-8")
# Ensure V7 function exists
v7_func = """def official_bear_draw_odds_hunt_codes() -> set[str]:
    base = set(_parse_official_bear_draw_odds_pdf().keys())
    retired_2026 = set(BEAR_HISTORICAL_CODE_SUCCESSORS_2026.keys()) | {"BR7237"}
    new_2026 = {"BR7021","BR7022","BR7126","BR7127","BR7238","BR7239","BR7326"}
    return (base - retired_2026) | new_2026"""

# replace any def official_bear_draw_odds_hunt_codes block
import re
text = re.sub(r'def official_bear_draw_odds_hunt_codes\(\)[^:]*:\s*\n(?:.*\n)*?return \(base.*?\n', v7_func + "\n\n\n", text, flags=re.MULTILINE)
# Simpler: if not correct, overwrite file from template using git show + patch
if "BR7021" not in text:
    print("V7 patch missing, re-applying via Patch-V7-Force.py")
    subprocess.run([sys.executable, "Patch-V7-Force.py"], check=False)
    text = bear_path.read_text(encoding="utf-8")

# Fix restricted pursuit
text = text.replace('if "restricted pursuit" in text:\n return UNKNOWN_BEAR_SUBTYPE', 'if "restricted pursuit" in text:\n return RESTRICTED_BEAR_PURSUIT')
bear_path.write_text(text, encoding="utf-8")
print("fixed bear V7 + pursuit")

# Also restore deer to known-good so Codex doesn't fight you
subprocess.run(["git", "checkout", "f7331fa0", "--", "engine/utah_draw_predictive/deer.py"], check=False)
print("restored deer to f7331fa0 - let Codex re-apply deer fixes on clean base")
