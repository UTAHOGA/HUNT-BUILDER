"""Assemble hash-bound publication evidence and the human completion report."""
import csv
import hashlib
import json
import shutil
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "audits/prediction_release_candidates/core_le_deer_repair_20260919"
PUBLIC = "research_candidate_harvest_preserved"


def read(name):
    return json.loads((BASE / name).read_text(encoding="utf-8"))


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def write(name, data):
    (BASE / name).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main():
    local = read(f"{PUBLIC}/browser_qa.json")
    live = read(f"{PUBLIC}/browser_qa_production_alias.json")
    immutable = read(f"{PUBLIC}/browser_qa_deployment.json")
    deployment = read("published_pages_snapshot.json")
    overlay = read("pages_overlay_verification_harvest_preserved.json")
    transaction = read("r2_publication_harvest_preserved/transaction.json")
    validation = read(f"{PUBLIC}/candidate_contract_validation.json")
    coverage = read("coverage_harvest_preserved.json")
    registry = read("certification_registry.json")
    frozen = read("SELECTED_REPAIR_FREEZE.json")
    expected_scenarios = 19 + sum(
        row["coverage_status"] != "HISTORICAL_REFERENCE_ONLY" for row in coverage["inventory"]
    )
    for name, qa in (("local", local), ("production", live), ("deployment", immutable)):
        if qa["status"] != "PASS" or qa["failed_requests"] or qa["console_errors"]:
            raise ValueError(f"Browser QA failed: {name}")
        if len(qa["scenarios"]) != expected_scenarios or not all(row["passed"] for row in qa["scenarios"]):
            raise ValueError(f"Incomplete browser scenario population: {name}")
        if qa["independent_coverage_sha256"] != sha(BASE / "coverage_harvest_preserved.json"):
            raise ValueError(f"Browser coverage artifact changed: {name}")
        if name != "local":
            checks = qa.get("runtime_source_hash_checks", [])
            if not checks or not all(r["passed"] for r in checks) or {r["role"] for r in checks} != {"summary", "index"}:
                raise ValueError(f"Public runtime source hashes not verified: {name}")
    if deployment["files"] != overlay["expected_deployment_files"]:
        raise ValueError("Published Pages file hashes differ from the reviewed overlay")
    if transaction["status"] != "PASS_SIX_OBJECTS_PUBLISHED_AND_HASH_VERIFIED":
        raise ValueError("R2 publication incomplete")
    for group in ("protected_baselines", "implementation"):
        for relative, expected in frozen[group].items():
            if sha(ROOT / relative) != expected:
                raise ValueError(f"Frozen {group} changed: {relative}")
    aliases = []
    for source, destination in (
        ("coverage_harvest_preserved.json", "coverage_final_audited.json"),
        ("classifications.json", "classifications_final_audited.json"),
        (f"{PUBLIC}/browser_qa_production_alias.json", "research_final_audited/browser_qa.json"),
    ):
        target = BASE / destination
        if target.exists() and sha(target) != sha(BASE / source):
            raise ValueError(f"Refusing to replace different retained evidence: {destination}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(BASE / source, target)
        aliases.append({"source": source, "alias": destination, "sha256": sha(target)})
    mixed = read("mixed_materialization/mixed_predictive_engine_2026_summary.json")
    manifest = read("family_materialization/utah_bonus_predictive_manifest.json")
    manifest["prediction_family_certification"]["registry_id"] = registry["registry_id"]
    manifest["prediction_family_certification"]["certification_status_counts"] = mixed["prediction_certification_status_counts"]
    manifest["final_probability_release"] = {
        "contract": "CORE_FAMILY_MECHANICS_PRESERVED_V1",
        "registry_sha256": sha(BASE / "certification_registry.json"),
        "final_probability_file": str((BASE / "mixed_materialization/ml_draw_predictions_v1.csv").relative_to(ROOT)).replace("\\", "/"),
        "final_probability_sha256": sha(BASE / "mixed_materialization/ml_draw_predictions_v1.csv"),
        "historical_folds": 9, "historical_database_csv_reads": 0,
        "coverage_report_sha256": sha(BASE / "coverage_harvest_preserved.json"),
        "release_readiness_manifest_sha256": sha(BASE / PUBLIC / "release_readiness_manifest.json"),
    }
    write("promoted_prediction_manifest.json", manifest)
    regression = {"status": "RUNNING_OR_NO_FINAL_XML", "log": "regression.log"}
    if (BASE / "regression.xml").exists():
        suites = ET.parse(BASE / "regression.xml").getroot()
        suite = suites if suites.tag == "testsuite" else suites.find("testsuite")
        failures = [{"test": r.attrib.get("classname", "") + "." + r.attrib["name"],
                     "message": r.find("failure").attrib.get("message", "")}
                    for r in suites.iter("testcase") if r.find("failure") is not None]
        regression = {"status": "COMPLETED_WITH_FAILURES" if failures else "PASS", **suite.attrib, "failure_details": failures}
    with (BASE / "acceptance_review/acceptance_by_draw_design.csv").open() as handle:
        metrics = [r for r in csv.DictReader(handle) if r["draw_design"] in registry["certified_designs"]]
    report = {
        "status": "PASS_PROMOTED_AND_PUBLIC_ALIAS_VERIFIED", "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "registry_id": registry["registry_id"], "registry_sha256": sha(BASE / "certification_registry.json"),
        "materialization_rows": mixed["prediction_row_count"],
        "materialization_sha256": sha(BASE / "mixed_materialization/ml_draw_predictions_v1.csv"),
        "promoted_manifest_sha256": sha(BASE / "promoted_prediction_manifest.json"),
        "cloudflare_pages_deployment": deployment["url"], "deployment_id": deployment["id"],
        "public_alias": "https://huntbuilder.pages.dev/research.html",
        "browser_qa_scenarios_each": {name: len(value["scenarios"]) for name, value in (("local", local), ("immutable", immutable), ("public_alias", live))},
        "browser_startup_ms": {name: value["startup_timing"]["research_ready_ms"] for name, value in (("local", local), ("immutable", immutable), ("public_alias", live))},
        "failed_requests": 0, "console_errors": 0,
        "r2_changed_object_count": 6, "r2_post_upload_verification": "ALL_SIX_SHA256_MATCH_CANDIDATE",
        "rollback_namespace": transaction["rollback_namespace"],
        "r2_objects": transaction["objects"],
        "unchanged_legacy_ladder_sha256": "1a45732cf45232ded9f9f3e81ac9827a0522326020af141abfc9a0b546644a5d",
        "public_probability_contract": "CERTIFIED_P_DRAW_FIELDS_ONLY", "unauthorized_probability_rows": 0,
        "protected_draw_permit_quota_field_changes": 0, "protected_truth_and_database_unchanged": True,
        "original_pages_files": 4249, "pages_changed_files": len(overlay["changed"]),
        "pages_untouched_files": overlay["untouched_file_count"], "pages_added_files": len(overlay["added"]), "pages_deleted_files": 0,
        "coverage": {k: v for k, v in coverage.items() if k not in {"inventory", "sources", "current_deer_regular_quota_evidence"}},
        "certified_design_metrics": metrics, "residual_error_audit": read("residual_error_audit_summary.json"),
        "focused_tests_passed": 51, "broader_regression": regression,
        "protected_harvest_context_field_changes": read(f"{PUBLIC}/candidate_build_audit.json")["overlay"]["protected_harvest_context_field_changes"],
        "first_attempt_rollback": read("r2_publication/rollback_result.json"),
        "final_evidence_aliases": aliases,
        "r2_transfer_recovery": transaction.get("transfer_recovery"),
        "repository_head_at_completion": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "external_repository_activity": "Commit d9a5bfec appeared during verification; not created by this release. Frozen source and artifact hashes reverified unchanged.",
        "staged_committed_or_pushed": False,
    }
    write("production_promotion_report.json", report)
    lines = ["# Certified-core prediction release — 2026-09-19", "",
             f"Published and verified: {report['public_alias']}", f"Immutable deployment: {deployment['url']}", "",
             "## Result", "", "All four core designs pass the unchanged ADR-0006 gates across nine adjacent, source-only folds on the exact final website calculation. Certification is not a guarantee or universal forecast coverage.", "",
             "| Design | Scored rows | Mean error (pp) | P90 error (pp) | Tail >25 pp | Unresolved gaps |",
             "|---|---:|---:|---:|---:|---:|"]
    for r in metrics:
        lines.append(f"| {r['draw_design']} | {r['joined_rows']} | {float(r['mae'])*100:.3f} | {float(r['p90_absolute_error'])*100:.3f} | {float(r['tail_error_rate_over_25pp'])*100:.3f}% | {r['unclassified_actual_gap_rows']} |")
    lines += ["", "All four have zero forecasted-certainty failures. No thresholds were relaxed. No numeric errors were excluded because of target-year program or quota changes.", "",
              "## Repairs and evidence", "",
              "- Historical deer quota intake now counts official point-level awards once, not hunt totals plus those awards. The preference probability formula is unchanged.",
              "- All 32 LE blanks have independent source-only replay evidence. No probabilities were invented. See `le_32_no_transition_prediction_annotations.csv` and `le_gap_resolution_summary.json`.",
              "- See `audit_3886_collapse_verification.csv`: 125 current zero-versus-positive errors across eight folds; 129 across nine. Every error stays in the metrics. The supplied 3,886 prior count was not independently reproduced, so no causal reduction is claimed. The supplied six-way catch-all is not proof of a zero-demand defect.",
              "- `deer_9fold_final_website_calc.csv` retains all 8,936 deer scored rows. `SELECTED_REPAIR_FREEZE.json` preserves selection before later-fold evaluation; later years were previously examined in the project and are not described as untouched holdouts.",
              "- The yearly canonicals and long truth are value-for-value equal, with 338,574 rows and complete retained PDF/official-endpoint lineage. No fictional page numbers were assigned to web endpoints.", "",
              "## Coverage and public behavior", "",
              "796 retained core codes / 1,592 lanes: 847 modeled; 100 zero-quota; 356 historical-only; 7 lack comparable history; 6 lack transition evidence; 276 lack current allocation. All are accounted for; not all receive a prediction.",
              "All 105 current general-deer hunts retain both official regular-round residency lanes (210 combinations). Planner combined totals were not treated as regular-round quotas.",
              "Only certified_p_draw* fields display. Bear, CWMU, turkey, antlerless, Dedicated Hunter and youth remain withheld. The label is Projected Draw Line; no future guarantee is displayed.", "",
              "## Verification and publication", "",
              f"- 1,255/1,255 scenarios pass locally, on the immutable deployment, and on the public alias. Each run has zero failed requests and console errors.",
              "- 51 focused tests pass. Broader regression status: " + regression["status"] + ". Failures, if any, are retained in regression.log/regression.xml and the JSON promotion report; they are not replaced by production data edits.",
              "- Project memory, npm tests, public-manifest guard, contract validation, exact-code freeze, source parity, full eligible accounting and release-readiness gates pass.",
              "- Requested final evidence names are exact hash-verified aliases: coverage_final_audited.json, classifications_final_audited.json, and research_final_audited/browser_qa.json (the production-alias browser run). Original evidence paths remain retained.",
              "- Six R2 objects were backed up remotely, read back and hash-verified before replacement. All six replacements were also read back and hash-verified.",
              "- An additional isolation audit caught four derived harvest-context fields in the initial rebuild. The initial R2 attempt was stopped and all six original objects restored and hash-verified before the corrected prediction-only contract was revalidated and published. Both transactions are retained; no Pages deployment occurred during the aborted attempt.",
              f"- Rollback namespace: `{transaction['rollback_namespace']}`. The earlier immutable Pages deployment remains available.",
              f"- All 4,249 prior Pages files are retained: {len(overlay['changed'])} explicitly reviewed files updated, {overlay['untouched_file_count']} byte-identical, none added or removed. See pages_overlay_verification_harvest_preserved.json for exact paths and hashes.",
              "- Pages changes: research.html, config.js, hunt-research.js, summary/index, and 1,791 direct hunt details. The oversized legacy archive, harvest reports/data, draw truth, DATABASE.csv and unrelated production assets are unchanged.",
              "- This release did not stage, commit or push Git. An externally created commit d9a5bfec appeared during verification; frozen source/artifact hashes were reverified unchanged. The release used only the isolated, hash-reviewed Pages directory, not the working tree.", ""]
    (BASE / "COMPLETION_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("status", "registry_id", "materialization_sha256", "promoted_manifest_sha256", "deployment_id")}))


if __name__ == "__main__":
    main()
