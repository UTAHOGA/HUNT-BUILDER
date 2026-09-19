#!/usr/bin/env python3
"""Create a local-only Research-page harness pointing at the audit candidate."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "audits" / "prediction_blind_backtests" / "2025_to_2026_truth_2018_2026_20260827_certification_candidate" / "research_split_contract_candidate_2026-08-27"
OUT = CANDIDATE / "research_candidate_v2.html"
BASE = "/audits/prediction_blind_backtests/2025_to_2026_truth_2018_2026_20260827_certification_candidate/research_split_contract_candidate_2026-08-27/processed_data"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=CANDIDATE)
    parser.add_argument("--output-name", default="research_candidate_v2.html")
    args = parser.parse_args()
    candidate = args.candidate if args.candidate.is_absolute() else ROOT / args.candidate
    out = candidate / args.output_name
    base = "/" + str((candidate / "processed_data").relative_to(ROOT)).replace("\\", "/")
    if out.exists():
        raise SystemExit(f"Refusing to overwrite existing harness: {out}")
    source = (ROOT / "research.html").read_text(encoding="utf-8")
    # The harness is nested under audits; all production relative assets and
    # runtime-manifest requests must still resolve from the repository root.
    source = source.replace("<head>", '<head>\n  <base href="/">', 1)
    replacements = {
        'href="./style.css': 'href="/style.css',
        'src="./embed-mode.js': 'src="/embed-mode.js',
        'src="./sentry-browser-init.js': 'src="/sentry-browser-init.js',
        'src="./config.js': 'src="/config.js',
        'src="./ui.js': 'src="/ui.js',
        'src="./hunt-research.js': 'src="/hunt-research.js',
        'src="./assets/': 'src="/assets/',
        'href="./assets/': 'href="/assets/',
    }
    for before, after in replacements.items():
        source = source.replace(before, after)
    override = f'''
  <script>
    Object.assign(window.UOGA_CONFIG, {{
      HUNT_RESEARCH_USE_SPLIT_CONTRACT: true,
      HUNT_RESEARCH_ALLOW_LEGACY_FALLBACK: false,
      HUNT_RESEARCH_SUMMARY_SOURCES: ['{base}/hunt_research_2026_summary.json'],
      HUNT_RESEARCH_SPLIT_INDEX_SOURCES: ['{base}/hunt_research_2026_split/hunt_research_2026.index.json'],
      HUNT_RESEARCH_CANONICAL_LADDER_SOURCES: ['{base}/hunt_research_2026_ladder.json'],
      HUNT_RESEARCH_LADDER_SOURCES: ['{base}/point_ladder_view.csv'],
      HUNT_RESEARCH_SPLIT_DETAIL_BUNDLE_SOURCES: ['{base}/hunt_research_2026_split/hunt_research_2026.details.json'],
      HUNT_RESEARCH_SPLIT_DETAIL_BASES: ['{base}/hunt_research_2026_split'],
    }});
  </script>'''
    config_tag = r'(<script\s+src="/config\.js[^>]*></script>)'
    source, replacements = re.subn(config_tag, lambda match: match.group(1) + override, source, count=1)
    if replacements != 1:
        raise RuntimeError("Could not find the config script tag in research.html")
    out.write_text(source, encoding="utf-8")
    print(f"RESEARCH_CANDIDATE_HARNESS={out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
