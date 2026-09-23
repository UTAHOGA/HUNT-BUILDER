import pathlib
path = pathlib.Path('engine/utah_draw_predictive/bear.py')
txt = path.read_text(encoding='utf-8')
txt = txt.replace(
    '    if "restricted pursuit" in text:\n return RESTRICTED_BEAR_PURSUIT',
    '    if "restricted pursuit" in text:\n        return RESTRICTED_BEAR_PURSUIT'
)
path.write_text(txt, encoding='utf-8')
print("fixed indent")
