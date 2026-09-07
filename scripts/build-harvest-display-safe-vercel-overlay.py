#!/usr/bin/env python3
"""Build three frontend files against the current production/HEAD baseline only."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "processed_data" / "audits" / "harvest_display_release_20260906" / "vercel_overlay"


def head_text(path: str) -> str:
    return subprocess.check_output(["git", "show", f"HEAD:{path}"], cwd=ROOT).decode("utf-8").replace("\r\n", "\n")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"Expected one {label} block in production baseline, found {text.count(old)}")
    return text.replace(old, new, 1)


def build_hunt_research() -> str:
    text = head_text("hunt-research.js")
    text = replace_once(
        text,
        """  function hasMeaningfulValue(value) {
    const text = String(value ?? '').trim();
    return !!text && text.toUpperCase() !== 'N/A' && text.toUpperCase() !== 'NOT AVAILABLE';
  }
""",
        """  function hasMeaningfulValue(value) {
    const text = String(value ?? '').trim();
    return !!text && text.toUpperCase() !== 'N/A' && text.toUpperCase() !== 'NOT AVAILABLE';
  }

  function firstMeaningfulValue(...values) {
    return values.find(hasMeaningfulValue) ?? '';
  }
""",
        "meaningful-value helper",
    )
    text = replace_once(
        text,
        """      [`${RESEARCH_RESULT_YEAR} Harvest Success`, hasMeaningfulValue(referenceRow?.harvest_success_percent_2025)
        ? `${referenceRow.harvest_success_percent_2025}%`
        : (hasMeaningfulValue(meta?.success_percent) ? `${meta.success_percent}%` : 'Not available')],
      ['Harvest / Hunters', hasMeaningfulValue(referenceRow?.harvest_2025) || hasMeaningfulValue(referenceRow?.harvest_hunters_2025)
        ? `${referenceRow?.harvest_2025 || '0'} / ${referenceRow?.harvest_hunters_2025 || '0'}`
""",
        """      [`${RESEARCH_RESULT_YEAR} Harvest Success`, hasMeaningfulValue(firstMeaningfulValue(referenceRow?.harvest_success_percent_2025, referenceRow?.harvest_success_pct, referenceRow?.percent_success))
        ? `${firstMeaningfulValue(referenceRow?.harvest_success_percent_2025, referenceRow?.harvest_success_pct, referenceRow?.percent_success)}%`
        : (hasMeaningfulValue(meta?.success_percent) ? `${meta.success_percent}%` : 'Not available')],
      ['Harvest / Hunters', hasMeaningfulValue(firstMeaningfulValue(referenceRow?.harvest_2025, referenceRow?.harvest, referenceRow?.harvest_total)) || hasMeaningfulValue(firstMeaningfulValue(referenceRow?.harvest_hunters_2025, referenceRow?.hunters, referenceRow?.hunters_afield))
        ? `${firstMeaningfulValue(referenceRow?.harvest_2025, referenceRow?.harvest, referenceRow?.harvest_total) || '0'} / ${firstMeaningfulValue(referenceRow?.harvest_hunters_2025, referenceRow?.hunters, referenceRow?.hunters_afield) || '0'}`
""",
        "source-box harvest aliases",
    )
    old_snapshot = """  function getHarvestSnapshot(meta, referenceRow) {
    const success = hasMeaningfulValue(referenceRow?.harvest_success_percent_2025)
      ? `${referenceRow.harvest_success_percent_2025}% success`
      : (hasMeaningfulValue(meta?.success_percent) ? `${meta.success_percent}% success` : '');
    const harvestCount = hasMeaningfulValue(referenceRow?.harvest_2025) || hasMeaningfulValue(referenceRow?.harvest_hunters_2025)
      ? `${referenceRow?.harvest_2025 || '0'} harvest / ${referenceRow?.harvest_hunters_2025 || '0'} hunters`
      : (hasMeaningfulValue(meta?.success_harvest) || hasMeaningfulValue(meta?.success_hunters)
        ? `${meta?.success_harvest || '0'} harvest / ${meta?.success_hunters || '0'} hunters`
        : '');
    const days = hasMeaningfulValue(referenceRow?.harvest_average_days_2025)
      ? `${referenceRow.harvest_average_days_2025} avg days`
      : '';
    const satisfaction = hasMeaningfulValue(referenceRow?.harvest_satisfaction_2025)
      ? `${referenceRow.harvest_satisfaction_2025} satisfaction`
      : '';
    const parts = [success, harvestCount, days, satisfaction].filter(Boolean);
    return parts.length ? parts.join(' | ') : 'Harvest data is not mapped to this hunt row yet.';
  }
"""
    new_snapshot = """  function getHarvestSnapshot(meta, referenceRow) {
    const successValue = firstMeaningfulValue(
      referenceRow?.harvest_success_percent_2025,
      referenceRow?.harvest_success_pct,
      referenceRow?.percent_success,
      meta?.success_percent,
    );
    const harvestValue = firstMeaningfulValue(referenceRow?.harvest_2025, referenceRow?.harvest, referenceRow?.harvest_total, meta?.success_harvest);
    const huntersValue = firstMeaningfulValue(referenceRow?.harvest_hunters_2025, referenceRow?.hunters, referenceRow?.hunters_afield, meta?.success_hunters);
    const daysValue = firstMeaningfulValue(referenceRow?.harvest_average_days_2025, referenceRow?.average_days_hunted, referenceRow?.avg_days);
    const satisfactionValue = firstMeaningfulValue(referenceRow?.harvest_satisfaction_2025, referenceRow?.hunter_satisfaction, referenceRow?.satisfaction);
    const success = hasMeaningfulValue(successValue)
      ? `${successValue}% success`
      : (hasMeaningfulValue(meta?.success_percent) ? `${meta.success_percent}% success` : '');
    const harvestCount = hasMeaningfulValue(harvestValue) || hasMeaningfulValue(huntersValue)
      ? `${harvestValue || '0'} harvest / ${huntersValue || '0'} hunters`
      : (hasMeaningfulValue(meta?.success_harvest) || hasMeaningfulValue(meta?.success_hunters)
        ? `${meta?.success_harvest || '0'} harvest / ${meta?.success_hunters || '0'} hunters`
        : '');
    const days = hasMeaningfulValue(daysValue)
      ? `${daysValue} avg days`
      : '';
    const satisfaction = hasMeaningfulValue(satisfactionValue)
      ? `${satisfactionValue} satisfaction`
      : '';
    const parts = [success, harvestCount, days, satisfaction].filter(Boolean);
    return parts.length ? parts.join(' | ') : 'Harvest data is not mapped to this hunt row yet.';
  }
"""
    return replace_once(text, old_snapshot, new_snapshot, "harvest snapshot")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "assets" / "js").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "research.html", OUT / "research.html")
    shutil.copy2(ROOT / "assets" / "js" / "research-outlook-dashboard.js", OUT / "assets" / "js" / "research-outlook-dashboard.js")
    (OUT / "hunt-research.js").write_text(build_hunt_research(), encoding="utf-8", newline="\n")
    print(OUT.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
