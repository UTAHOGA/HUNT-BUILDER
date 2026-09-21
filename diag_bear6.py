import pathlib, re
text = pathlib.Path('engine/utah_draw_predictive/bear.py').read_text()
m = re.search(r'def official_bear_draw_odds_hunt_codes.*?\n(?:.*\n){0,40}', text, re.MULTILINE)
print(m.group(0) if m else "not found")
# also dump where 7021 etc should be added
print("\n--- searching 7021 ---")
for i, line in enumerate(text.splitlines(),1):
    if "7021" in line or "BR7022" in line or "official_bear" in line.lower():
        print(i, line)
