"""Read-only checks for the corrective release, not prediction acceptance."""
import ast
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DISABLED = (
    "Fix-Antlerless-Direct.py",
    "fix_antlerless_direct.py",
    "fix_live_feed_antlerless.py",
    "fix_cwmu_direct.py",
    "Patch-Scorer.py",
    "Patch-Bear-Clean-V7.py",
    "Fix-And-Rebuild-Bear-V2.py",
    "fix_and_rebuild_bear.py",
)


def test_all_owning_entrypoints_import_without_generating_predictions():
    result = subprocess.run(
        [sys.executable, "-B", str(ROOT / "scripts/validate_engine_imports.py")],
        cwd=ROOT, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_unreviewed_artifact_patchers_stop_before_any_import_or_write():
    # Do not execute these scripts: prove the first non-docstring statement
    # is an unconditional SystemExit before any old code could run.
    for name in DISABLED:
        body = ast.parse((ROOT / name).read_text(encoding="utf-8-sig")).body
        if isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            body = body[1:]
        first = body[0]
        assert isinstance(first, ast.Raise), name
        assert isinstance(first.exc, ast.Call), name
        assert isinstance(first.exc.func, ast.Name) and first.exc.func.id == "SystemExit", name
        assert first.exc.args[0].value.startswith("DISABLED_UNREVIEWED_REPAIR:"), name


def test_website_build_does_not_regenerate_prediction_data_from_fixtures():
    scripts = json.loads((ROOT / "package.json").read_text())["scripts"]
    assert "build:public-contracts" not in scripts["build:pages"]
    assert "build:library-page" not in scripts["build:pages"]
    assert "restore-reviewed-release-assets.js" in scripts["build:pages"]
    assert "hydrate:research-details" in scripts["build:pages"]
