"""Per-design statistical certification and publication gating.

Runtime materialization and statistical certification are deliberately
different concepts.  A family can be wired into the runtime while its
probability remains experimental.  This module applies the compact,
machine-readable certification registry to prediction rows and exposes a
separate public probability only when every ADR-0006 gate passed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping


CERTIFIED = "CERTIFIED"
EXPERIMENTAL = "EXPERIMENTAL_NOT_CERTIFIED"
INSUFFICIENT = "INSUFFICIENT_EVIDENCE"
NOT_EVALUATED = "NOT_EVALUATED"

PUBLIC_CERTIFIED = "CERTIFIED_PROBABILITY"
PUBLIC_WITHHELD_EXPERIMENTAL = "EXPERIMENTAL_PROBABILITY_WITHHELD"
PUBLIC_WITHHELD_INSUFFICIENT = "INSUFFICIENT_EVIDENCE_PROBABILITY_WITHHELD"
PUBLIC_WITHHELD_NOT_EVALUATED = "NOT_EVALUATED_PROBABILITY_WITHHELD"

BEAR_CERTIFICATION_DESIGNS = {
    "LIMITED_ENTRY_BEAR_HUNT": "BEAR_LIMITED_ENTRY_HUNT_BONUS",
    "RESTRICTED_BEAR_PURSUIT": "BEAR_RESTRICTED_PURSUIT_BONUS",
}


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def certification_design_for_row(row: Mapping[str, object]) -> str:
    """Resolve the certification population without collapsing Bear programs."""

    design = clean(row.get("draw_system_type") or row.get("draw_design")).upper()
    if design != "BEAR_DRAW":
        return design
    subtype = clean(row.get("bear_draw_subtype")).upper()
    return BEAR_CERTIFICATION_DESIGNS.get(subtype, "BEAR_DRAW_UNCLASSIFIED_SUBTYPE")


def load_registry(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "prediction-family-certification.v1":
        raise ValueError(f"Unsupported prediction certification registry schema: {payload.get('schema_version')!r}")
    families = payload.get("families")
    if not isinstance(families, dict):
        raise ValueError("Prediction certification registry has no family mapping.")
    for design, evidence in families.items():
        if not isinstance(evidence, dict):
            raise ValueError(f"Certification evidence for {design} is not an object.")
        status = clean(evidence.get("certification_status"))
        if status not in {CERTIFIED, EXPERIMENTAL, INSUFFICIENT}:
            raise ValueError(f"Unsupported certification status for {design}: {status!r}")
    return payload


def publication_status(certification_status: str) -> str:
    return {
        CERTIFIED: PUBLIC_CERTIFIED,
        EXPERIMENTAL: PUBLIC_WITHHELD_EXPERIMENTAL,
        INSUFFICIENT: PUBLIC_WITHHELD_INSUFFICIENT,
    }.get(certification_status, PUBLIC_WITHHELD_NOT_EVALUATED)


def _first_probability(row: Mapping[str, object], *fields: str) -> object:
    for field in fields:
        value = row.get(field)
        if clean(value) != "":
            return value
    return ""


def annotate_prediction_rows(
    rows: Iterable[dict[str, object]],
    registry: Mapping[str, Any],
) -> dict[str, object]:
    """Apply design certification to rows and return a compact coverage report.

    Raw modeling fields are preserved for blind scoring and development.  The
    ``certified_*`` fields are the only probability fields authorized for a
    certification-aware public contract.
    """

    families = registry.get("families")
    if not isinstance(families, Mapping):
        raise ValueError("Prediction certification registry has no family mapping.")
    evidence_path = clean(registry.get("evidence", {}).get("acceptance_by_draw_design"))
    registry_id = clean(registry.get("registry_id"))
    counts: dict[str, int] = {}
    designs: dict[str, int] = {}

    for row in rows:
        design = certification_design_for_row(row)
        evidence = families.get(design)
        if isinstance(evidence, Mapping):
            status = clean(evidence.get("certification_status"))
            failure_reasons = clean(evidence.get("failure_reasons"))
        else:
            status = NOT_EVALUATED
            failure_reasons = "NO_ADJACENT_YEAR_CERTIFICATION_EVIDENCE"

        public_status = publication_status(status)
        row["prediction_certification_design"] = design
        row["prediction_certification_status"] = status
        row["prediction_publication_status"] = public_status
        row["prediction_certification_registry_id"] = registry_id
        row["prediction_certification_evidence"] = evidence_path
        row["prediction_certification_failure_reasons"] = failure_reasons

        # These are projected structural lines, not guarantees that a future
        # applicant will draw.  Keep the legacy names for compatibility while
        # establishing accurate names for every new contract.
        row["projected_draw_line_2025"] = row.get("guaranteed_at_2025", "")
        row["projected_draw_line_2026"] = _first_probability(
            row,
            "guaranteed_at_2026",
            "projected_2026_max_cutoff_point",
        )

        if status == CERTIFIED:
            row["certified_p_draw"] = _first_probability(row, "p_draw", "p_draw_mean", "p_preference_draw")
            row["certified_p_draw_mean"] = _first_probability(row, "p_draw_mean", "p_draw", "p_preference_draw")
            row["certified_p_draw_pct"] = _first_probability(row, "p_draw_pct", "display_odds_pct")
        else:
            row["certified_p_draw"] = ""
            row["certified_p_draw_mean"] = ""
            row["certified_p_draw_pct"] = ""

        counts[status] = counts.get(status, 0) + 1
        designs[design] = designs.get(design, 0) + 1

    return {
        "registry_id": registry_id,
        "certification_status_counts": dict(sorted(counts.items())),
        "certification_design_row_counts": dict(sorted(designs.items())),
        "public_probability_field_contract": [
            "certified_p_draw",
            "certified_p_draw_mean",
            "certified_p_draw_pct",
        ],
        "raw_probability_policy": "RETAINED_FOR_DEVELOPMENT_AND_BLIND_SCORING_NOT_AUTHORIZED_AS_CERTIFIED_PUBLIC_ODDS",
    }
