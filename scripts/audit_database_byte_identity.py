"""Prove a DATABASE byte delta is exclusively LF/CRLF; refresh feeder evidence."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import audit_database_current_identity_quota_2026 as feeder


def audit(out, expected_lf):
    if out.exists():
        raise ValueError('Use a new evidence directory')
    out.mkdir(parents=True)
    data = feeder.DATABASE.read_bytes()
    digest = lambda b: hashlib.sha256(b).hexdigest()
    normalized = data.replace(b'\r\n', b'\n')
    byte_only = digest(normalized) == expected_lf
    feeder.OUTPUT_DIR = out
    feeder.OUTPUT_CSV = out / 'feeder_audit.csv'
    feeder.OUTPUT_JSON = out / 'feeder_summary.json'
    sys.argv = [sys.argv[0]]  # no repair flag may pass into the feeder
    result = feeder.main()
    # Older feeder versions append literal backslash-n; keep this audit's
    # machine-readable review valid without rewriting any older evidence.
    text = feeder.OUTPUT_JSON.read_text(encoding='utf-8')
    payload = json.loads(text[:-2] if text.endswith('\\n') else text)
    feeder.OUTPUT_JSON.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
    if feeder.DATABASE.read_bytes() != data:
        raise ValueError('DATABASE changed during read-only audit')
    evidence = dict(status='PASS' if byte_only and result == 0 else 'FAIL',
                    current_raw_sha256=digest(data), lf_normalized_sha256=digest(normalized),
                    expected_previously_verified_sha256=expected_lf,
                    exclusively_line_ending_delta=byte_only, crlf_count=data.count(b'\r\n'),
                    database_modified=False, feeder_exit_code=result)
    (out / 'byte_identity.json').write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(evidence, indent=2))
    return 0 if evidence['status'] == 'PASS' else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--expected-lf-sha256', required=True)
    args = parser.parse_args()
    raise SystemExit(audit(args.output_dir.resolve(), args.expected_lf_sha256))
