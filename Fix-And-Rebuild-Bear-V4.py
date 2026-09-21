# Fix-And-Rebuild-Bear-V4.py
import pathlib, sys, importlib.util, types

REPO = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))
print(f"REPO: {REPO}")

for pkg in ["engine", "engine.utah_draw_predictive", "engine.utah_bonus_predictive"]:
    if pkg not in sys.modules:
        mod = types.ModuleType(pkg)
        mod.__path__ = [str(REPO / pkg.replace(".", "/"))]
        mod.__package__ = pkg
        sys.modules[pkg] = mod
        print(f"Inserted {pkg} as package -> {mod.__path__}")

bear_path = REPO / "engine" / "utah_draw_predictive" / "bear.py"
spec = importlib.util.spec_from_file_location("engine.utah_draw_predictive.bear", str(bear_path))
bear_mod = importlib.util.module_from_spec(spec)
bear_mod.__package__ = "engine.utah_draw_predictive"
sys.modules[spec.name] = bear_mod
print(f"Loading {spec.name} from {bear_path}")
spec.loader.exec_module(bear_mod)
print("Bear module loaded OK")

if hasattr(bear_mod, "main"):
    bear_mod.main()
    print("Ran main()")
