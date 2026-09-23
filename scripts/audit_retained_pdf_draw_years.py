"""Read-only report-year audit; directory and filename years are not truth.

Inspect explicit draw-result titles on the first three pages of each distinct
retained draw-odds PDF. Join canonical references by basename only as a candidate
lineage check, never numeric proof. Preserve unknown/conflicting evidence.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
TITLE_YEAR = re.compile(r"\b(20\d{2})\s+Draw\s+\d+\s*[,:-]?", re.I)


def explicit_draw_years(text):
    return sorted({int(m) for m in TITLE_YEAR.findall(text)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out-dir', type=Path, required=True)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=False)
    refs = defaultdict(Counter)
    canonical_hashes = {}
    canonical_root = ROOT / 'data_truth/draw_results_truth/normalized/canonical_yearly'
    for path in sorted(canonical_root.glob('*.csv')):
        canonical_hashes[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
        with path.open(encoding='utf-8-sig', newline='') as f:
            for row in csv.DictReader(f):
                names = {Path(row.get(k, '').replace('\\', '/')).name.lower()
                         for k in ('source_file', 'draw_source_file', 'source_pdf', 'source_path')}
                for name in names - {''}:
                    refs[name][row.get('actual_draw_year', '')] += 1
    root = ROOT / 'pipeline/RAW/hunt_unit_database'
    cache, rows = {}, []
    for path in sorted(root.glob('20*/pdf/draw_odds/**/*.pdf')):
        relative = path.relative_to(root)
        folder_year = int(relative.parts[0])
        if not 2017 <= folder_year <= 2026:
            continue
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        if sha not in cache:
            try:
                with pymupdf.open(path) as doc:
                    evidence = []
                    for i in range(min(3, len(doc))):
                        text = doc[i].get_text()
                        years = explicit_draw_years(text)
                        if years:
                            evidence.append({'page': i + 1, 'years': years,
                                             'title_matches': [m.group(0) for m in TITLE_YEAR.finditer(text)]})
                    cache[sha] = {'pages': len(doc), 'evidence': evidence, 'error': ''}
            except Exception as exc:
                cache[sha] = {'pages': None, 'evidence': [], 'error': f'{type(exc).__name__}: {exc}'}
        info = cache[sha]
        years = sorted({y for p in info['evidence'] for y in p['years']})
        status = ('PDF_READ_ERROR' if info['error'] else
                  'TITLE_YEAR_UNRESOLVED' if not years else
                  'MULTIPLE_TITLE_YEARS' if len(years) != 1 else
                  'FOLDER_YEAR_DIFFERS' if years[0] != folder_year else 'FOLDER_YEAR_MATCHES')
        references = dict(refs[path.name.lower()])
        rows.append({'pdf_path': path.relative_to(ROOT).as_posix(), 'sha256': sha,
                     'folder_year': folder_year, 'title_years': years, 'status': status,
                     **info, 'canonical_basename_reference_year_counts': references,
                     'canonical_year_candidate_conflict': bool(len(years) == 1 and references
                         and any(y != str(years[0]) for y in references)),
                     'numeric_parity_proven': False})
    changed = [p for p, h in canonical_hashes.items()
               if hashlib.sha256((ROOT / p).read_bytes()).hexdigest() != h]
    result = {'scope': 'TITLE_YEAR_AND_CANDIDATE_LINEAGE_NOT_NUMERIC_PARITY',
              'pdf_paths': len(rows), 'distinct_hashes': len(cache),
              'statuses': dict(Counter(r['status'] for r in rows)),
              'canonical_year_candidate_conflicts': sum(r['canonical_year_candidate_conflict'] for r in rows),
              'canonical_input_hashes': canonical_hashes, 'changed_canonicals': changed,
              'files': rows}
    (args.out_dir / 'report.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('files', 'canonical_input_hashes')}, indent=2))
    return int(bool(changed or any(r['error'] for r in rows)))


if __name__ == '__main__':
    raise SystemExit(main())
