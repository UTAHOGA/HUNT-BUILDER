"""Compare fresh official JSON responses with retained ones; no truth writes."""
import argparse
import csv
import hashlib
import json
from pathlib import Path


def compare(old, fresh):
    manifest = fresh / 'manifest.csv'
    output = fresh / 'retained_snapshot_comparison.json'
    if output.exists():
        raise ValueError('Refusing to overwrite earlier comparison')
    entries = []
    with manifest.open(encoding='utf-8-sig', newline='') as handle:
        for row in csv.DictReader(handle):
            if row['license_year'] != '2026' or row['download_status'] != 'OK':
                raise ValueError('Unexpected year or failed download in fresh manifest')
            name = Path(row['output_file']).name
            new_bytes = (fresh / name).read_bytes()
            digest = hashlib.sha256(new_bytes).hexdigest()
            if digest != row['sha256']:
                raise ValueError(f'Fresh file hash mismatch: {name}')
            entry = dict(file=name, source_url=row['source_url'], fresh_sha256=digest,
                         status='NO_RETAINED_COUNTERPART', retained_sha256=None)
            if (old / name).is_file():
                before = (old / name).read_bytes()
                entry['retained_sha256'] = hashlib.sha256(before).hexdigest()
                entry['status'] = 'IDENTICAL_PARSED_RESPONSE' if json.loads(before) == json.loads(new_bytes) else 'RESPONSE_CHANGED'
            entries.append(entry)
    result = dict(license_year=2026, fresh_groups=len(entries),
                  identical_parsed_responses=sum(r['status'] == 'IDENTICAL_PARSED_RESPONSE' for r in entries),
                  changed_responses=sum(r['status'] == 'RESPONSE_CHANGED' for r in entries),
                  additional_groups=sum(r['status'] == 'NO_RETAINED_COUNTERPART' for r in entries),
                  interpretation='Structural JSON equality includes all values and list order; file bytes may differ only in JSON serialization. Extra groups are not automatically canonical/scoring scope.',
                  entries=entries)
    with output.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, indent=2)
    print(json.dumps({k:v for k,v in result.items() if k != 'entries'}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--retained-json', type=Path, required=True)
    parser.add_argument('--fresh-json', type=Path, required=True)
    args = parser.parse_args()
    compare(args.retained_json, args.fresh_json)
