#!/usr/bin/env python3
"""Read-only local-versus-R2 runtime comparison for Hunt Builder.

The script never writes to R2.  It only writes the requested local audit JSON.
Objects that are intentionally R2-backed and absent locally are reported as
``LOCAL_NOT_HYDRATED``; they are not falsely reported as equal or unequal.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT
    / "audits"
    / "prediction_blind_backtests"
    / "2025_to_2026_truth_2018_2026_20260827_certification_candidate"
    / "r2_runtime_equivalence_2026-08-27.json"
)


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def csv_schema_from_bytes(data: bytes) -> dict[str, object]:
    first_line = data.splitlines()[0].decode("utf-8-sig") if data else ""
    fields = next(csv.reader([first_line])) if first_line else []
    rows = max(0, len(data.splitlines()) - 1)
    return {"kind": "csv", "field_count": len(fields), "fields": fields, "data_rows": rows}


def json_schema_from_bytes(data: bytes) -> dict[str, object]:
    parsed = json.loads(data.decode("utf-8-sig"))
    if isinstance(parsed, dict):
        return {"kind": "json_object", "top_level_keys": sorted(parsed.keys())}
    if isinstance(parsed, list):
        first = parsed[0] if parsed else None
        return {
            "kind": "json_array",
            "item_count": len(parsed),
            "first_item_keys": sorted(first.keys()) if isinstance(first, dict) else [],
        }
    return {"kind": type(parsed).__name__}


def schema_from_bytes(path: Path, data: bytes) -> dict[str, object]:
    if path.suffix.lower() == ".csv":
        return csv_schema_from_bytes(data)
    if path.suffix.lower() == ".json":
        return json_schema_from_bytes(data)
    return {"kind": "binary"}


def local_record(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"status": "LOCAL_NOT_HYDRATED"}
    data = path.read_bytes()
    return {
        "status": "PRESENT",
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "schema": schema_from_bytes(path, data),
    }


def request_headers(url: str) -> dict[str, object]:
    headers = {"Accept-Encoding": "identity", "User-Agent": "Hunt-Builder-Runtime-Audit/1.0"}
    request = Request(url, method="HEAD", headers=headers)
    try:
        with urlopen(request, timeout=60) as response:
            return {
                "status": response.status,
                "content_length": response.headers.get("Content-Length"),
                "content_type": response.headers.get("Content-Type"),
                "etag": response.headers.get("ETag"),
                "last_modified": response.headers.get("Last-Modified"),
            }
    except HTTPError as exc:
        return {"status": exc.code, "error": str(exc)}
    except URLError as exc:
        return {"status": "NETWORK_ERROR", "error": str(exc.reason)}


def remote_record(path: Path, url: str, fetch_body: bool) -> dict[str, object]:
    record = request_headers(url)
    if not fetch_body or record.get("status") != 200:
        record["body_status"] = "NOT_FETCHED" if not fetch_body else "UNAVAILABLE"
        return record
    request = Request(
        url,
        headers={"Accept-Encoding": "identity", "User-Agent": "Hunt-Builder-Runtime-Audit/1.0"},
    )
    try:
        with urlopen(request, timeout=180) as response:
            data = response.read()
    except (HTTPError, URLError) as exc:
        record["body_status"] = "FETCH_FAILED"
        record["body_error"] = str(exc)
        return record
    record.update(
        {
            "body_status": "FETCHED_READ_ONLY",
            "bytes_read": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "schema": schema_from_bytes(path, data),
        }
    )
    return record


def comparison(local: dict[str, object], remote: dict[str, object]) -> str:
    if local["status"] != "PRESENT":
        return "NOT_COMPARABLE_LOCAL_NOT_HYDRATED"
    if remote.get("body_status") != "FETCHED_READ_ONLY":
        return "NOT_COMPARABLE_REMOTE_UNAVAILABLE"
    same_hash = local["sha256"] == remote["sha256"]
    same_schema = local["schema"] == remote["schema"]
    if same_hash and same_schema:
        return "EXACT_MATCH"
    if same_schema:
        return "CONTENT_MISMATCH_SCHEMA_MATCH"
    return "CONTENT_AND_SCHEMA_MISMATCH"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    authority = json.loads((ROOT / "governance" / "engine-authority.json").read_text(encoding="utf-8"))
    records: list[dict[str, object]] = []
    for artifact in authority["runtime_artifacts"]:
        path = ROOT / artifact["path"]
        local = local_record(path)
        remote = remote_record(path, artifact["external_url"], fetch_body=local["status"] == "PRESENT")
        records.append(
            {
                "role": artifact["role"],
                "path": artifact["path"],
                "external_url": artifact["external_url"],
                "local_policy": artifact["local_policy"],
                "local": local,
                "remote": remote,
                "comparison": comparison(local, remote),
            }
        )

    comparisons = [record["comparison"] for record in records]
    status = "HOSTED_EXACT_MATCH" if comparisons and set(comparisons) == {"EXACT_MATCH"} else "HOSTED_EQUIVALENCE_PENDING_OR_MISMATCH"
    audit = {
        "schema_version": "1.0.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "READ_ONLY_NO_R2_WRITE",
        "overall_status": status,
        "comparison_counts": {key: comparisons.count(key) for key in sorted(set(comparisons))},
        "artifacts": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(f"R2_RUNTIME_COMPARISON_STATUS={status}")
    print(f"AUDIT={args.output.relative_to(ROOT)}")
    for record in records:
        print(f"{record['role']}={record['comparison']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
