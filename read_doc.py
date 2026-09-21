import pathlib
p = pathlib.Path("docs/bear_availability_validation_2026.md")
print(p.read_text(encoding='utf-8')[-2000:])
