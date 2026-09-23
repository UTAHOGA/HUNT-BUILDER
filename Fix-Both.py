import pathlib
p = pathlib.Path('engine/utah_draw_predictive/bear.py').read_text(encoding='utf-8')
# fix 1: restricted pursuit indent
p = p.replace('    if "restricted pursuit" in text:\n return RESTRICTED_BEAR_PURSUIT', '    if "restricted pursuit" in text:\n        return RESTRICTED_BEAR_PURSUIT')
# fix 2: BR1001/BR1007/BR1018 block - add indent
p = p.replace(
    '                if _clean(row.get("hunt_code")).upper() in {"BR1001", "BR1007", "BR1018"}:\n                report_counts["availability"]',
    '                if _clean(row.get("hunt_code")).upper() in {"BR1001", "BR1007", "BR1018"}:\n                    report_counts["availability"]'
)
pathlib.Path('engine/utah_draw_predictive/bear.py').write_text(p, encoding='utf-8')
print("fixed both indents")
