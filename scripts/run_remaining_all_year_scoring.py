"""Run remaining independent audit folds in separate folders; no engine changes."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.run_historical_adjacent_full_engine_scoring import canonical_actual


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--source-start', type=int, required=True)
    parser.add_argument('--source-end', type=int, default=2025)
    parser.add_argument('--workers', type=int, default=3)
    args = parser.parse_args()
    args.base.mkdir(parents=True, exist_ok=False)

    def fold(year):
        command = [sys.executable, 'scripts/run_historical_adjacent_full_engine_scoring.py',
                   '--source-start', str(year), '--source-end', str(year),
                   '--out-dir', str(args.base / f'source_{year}'),
                   '--final-probability-stage', '--all-family-final-stage', '--exact-codes-only',
                   '--bonus-central-estimate', 'deterministic', '--bonus-iterations', '1',
                   '--bear-central-estimate', 'simulation_mean', '--bear-iterations', '200']
        for prior in range(2017, year + 1):
            command.extend(['--truth-year-file', f'{prior}={canonical_actual(prior)}'])
        print(f'START {year} -> {year+1}', flush=True)
        with (args.base / f'fold_{year}.log').open('w', encoding='utf-8') as log:
            result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        print(f'FINISH {year} exit={result.returncode}', flush=True)
        return result.returncode

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = [pool.submit(fold, year) for year in range(args.source_start, args.source_end + 1)]
        return int(any(future.result() != 0 for future in as_completed(results)))


if __name__ == '__main__':
    raise SystemExit(main())
