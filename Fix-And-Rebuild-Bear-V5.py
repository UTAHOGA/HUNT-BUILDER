import pathlib, sys, importlib.util
REPO = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

# Load REAL packages from disk - not fake ModuleType
import engine
import engine.utah_draw_predictive
import engine.utah_bonus_predictive
import engine.utah_bonus_predictive.monte_carlo

print(f"Real packages loaded from {REPO / 'engine'}")
print(f"Has ALGORITHM_STATUS_MODELED_BONUS: {hasattr(engine.utah_draw_predictive, 'ALGORITHM_STATUS_MODELED_BONUS')}")

bear_path = REPO / "engine" / "utah_draw_predictive" / "bear.py"
spec = importlib.util.spec_from_file_location("engine.utah_draw_predictive.bear", str(bear_path))
bear_mod = importlib.util.module_from_spec(spec)
bear_mod.__package__ = "engine.utah_draw_predictive"
sys.modules[spec.name] = bear_mod
print(f"Loading {spec.name}")
spec.loader.exec_module(bear_mod)
print("Bear module loaded OK")

if hasattr(bear_mod, "main"):
    bear_mod.main()
    print("Ran main()")
