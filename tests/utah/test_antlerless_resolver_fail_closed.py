from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def resolver(monkeypatch, tmp_path):
    path = Path(__file__).resolve().parents[2] / "scripts/resolve-antlerless-hunt-codes-2026.py"
    spec = importlib.util.spec_from_file_location("antlerless_resolver_under_test", path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    for name in (
        "SOURCE_PDF", "AUDIT_JSON", "AUDIT_MD", "TEXT_LINES_CSV", "DRAW_ROWS_CSV",
        "DATABASE", "PREDICTIVE", "PROMOTION_DETAIL_CSV", "PROMOTION_JSON",
        "CODE_RECONCILIATION_CSV", "RECONCILIATION_JSON", "RECONCILIATION_MD",
    ):
        monkeypatch.setattr(module, name, tmp_path / Path(getattr(module, name)).name)
    return module


@pytest.mark.parametrize("source_state", ["missing", "unreadable", "empty_extraction"])
def test_bad_source_records_measured_failure_and_preserves_outputs(resolver, monkeypatch, source_state):
    retained = (resolver.TEXT_LINES_CSV, resolver.DRAW_ROWS_CSV, resolver.PREDICTIVE)
    for path in retained:
        path.write_bytes(b"retained output must not change\n")
    if source_state != "missing":
        resolver.SOURCE_PDF.write_bytes(b"invalid PDF used only by this failure-path test")
    if source_state == "empty_extraction":
        monkeypatch.setattr(
            resolver.pdfplumber, "open",
            lambda _path: nullcontext(SimpleNamespace(pages=[object()] * 203)),
        )
        monkeypatch.setattr(resolver, "extract_pdf_text_lines", lambda _sha: [])
        monkeypatch.setattr(resolver, "parse_draw_results", lambda _sha: [])

    assert resolver.main() == 1
    audit = json.loads(resolver.AUDIT_JSON.read_text(encoding="utf-8"))
    assert audit["blockers"] > 0
    assert audit["blockers"] == len(audit["blocker_reasons"])
    assert audit["text_lines"] == 0
    assert audit["draw_result_rows"] == 0
    assert audit["unique_draw_result_hunt_codes"] == 0
    assert audit["draw_result_prefix_counts"] == {}
    if source_state == "missing":
        assert audit["source_sha256"] is None
        assert audit["source_size_bytes"] is None
        assert audit["pdf_pages"] is None
        assert "source_pdf_missing" in audit["blocker_reasons"]
    else:
        assert audit["source_sha256"] == hashlib.sha256(resolver.SOURCE_PDF.read_bytes()).hexdigest()
        assert audit["source_size_bytes"] == resolver.SOURCE_PDF.stat().st_size
        assert audit["source_sha256"] != audit["expected_sha256"]
        assert audit["pdf_pages"] == (203 if source_state == "empty_extraction" else None)
    assert not resolver.PROMOTION_JSON.exists()
    assert all(path.read_bytes() == b"retained output must not change\n" for path in retained)


def test_reference_gap_is_dynamic_and_preserves_nonreference_rows(resolver):
    catalog = [{"hunt_code": f"EA{1000 + index}", "hunt_name": f"Test hunt {index}"} for index in range(66)]
    resolver.write_rows(resolver.DATABASE, ["hunt_code", "hunt_name"], catalog)
    fields = ["hunt_code", "hunt_name", "model_version", "p_draw", "certified_p_draw"]
    modeled = {"hunt_code": "EA1000", "hunt_name": "existing engine row", "model_version": "existing", "p_draw": "0.25", "certified_p_draw": ""}
    retired_reference = {"hunt_code": "EA1999", "model_version": resolver.REFERENCE_MODEL_VERSION}
    resolver.write_rows(resolver.PREDICTIVE, fields, [modeled, retired_reference])

    summary = resolver.promote_missing_reference_rows([])
    rows = resolver.read_rows(resolver.PREDICTIVE)
    references = [row for row in rows if row["model_version"] == resolver.REFERENCE_MODEL_VERSION]
    assert summary["promoted_reference_hunt_code_count"] == 65
    assert summary["still_missing_predictive_hunt_code_count"] == 0
    assert summary["duplicate_reference_key_count"] == 0
    assert {row["hunt_code"] for row in rows} == {row["hunt_code"] for row in catalog}
    assert {key: rows[0][key] for key in fields} == modeled
    assert len(references) == 65
    assert {row["display_odds_text"] for row in references} == {"Antlerless reference only; odds not modeled"}
    assert all(row["modeled_by_engine"] == "False" and row["probability_model"] == "NONE" for row in references)
    assert all(row["p_draw"] == row["certified_p_draw"] == "" for row in references)

    first_bytes = resolver.PREDICTIVE.read_bytes()
    second = resolver.promote_missing_reference_rows([])
    assert second["promoted_reference_hunt_code_count"] == 65
    assert resolver.PREDICTIVE.read_bytes() == first_bytes


def test_missing_source_process_exits_one_and_records_blocker(resolver):
    # Override paths in the child process, never rename or remove the real PDF.
    code = (
        "import runpy; from pathlib import Path; "
        f"m = runpy.run_path({str(Path(resolver.__file__))!r}); "
        "g = m['main'].__globals__; "
        f"g['SOURCE_PDF'] = Path({str(resolver.SOURCE_PDF)!r}); "
        f"g['AUDIT_JSON'] = Path({str(resolver.AUDIT_JSON)!r}); "
        f"g['AUDIT_MD'] = Path({str(resolver.AUDIT_MD)!r}); "
        "raise SystemExit(m['main']())"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 1, result.stderr
    audit = json.loads(resolver.AUDIT_JSON.read_text(encoding="utf-8"))
    assert "source_pdf_missing" in audit["blocker_reasons"]
    assert audit["source_sha256"] is None


def test_table_replacement_failure_restores_all_prior_bytes(resolver, monkeypatch):
    paths = [resolver.TEXT_LINES_CSV, resolver.DRAW_ROWS_CSV, resolver.PREDICTIVE]
    for path in paths:
        path.write_bytes(b"original verified artifact\n")
    original_replace = resolver.os.replace

    def fail_second_replace(source, destination):
        if destination == resolver.DRAW_ROWS_CSV:
            raise PermissionError("simulated locked output")
        original_replace(source, destination)

    monkeypatch.setattr(resolver.os, "replace", fail_second_replace)
    with pytest.raises(PermissionError, match="locked output"):
        resolver.publish_tables([(path, ["value"], [{"value": "new"}]) for path in paths])
    assert all(path.read_bytes() == b"original verified artifact\n" for path in paths)
    assert not list(paths[0].parent.glob(".*.csv.*"))

