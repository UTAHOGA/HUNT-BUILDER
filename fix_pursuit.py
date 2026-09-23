import pathlib
p = pathlib.Path('engine/utah_draw_predictive/bear.py').read_text(encoding='utf-8')
p = p.replace('if "restricted pursuit" in text:\n return UNKNOWN_BEAR_SUBTYPE', 'if "restricted pursuit" in text:\n return RESTRICTED_BEAR_PURSUIT')
pathlib.Path('engine/utah_draw_predictive/bear.py').write_text(p, encoding='utf-8')
print("fixed pursuit")
