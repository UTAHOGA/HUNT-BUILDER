from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / 'data_model' / 'harvest_quality'

AGE_2021 = MODEL_DIR / 'harvest_results_2021_for_2022_complete_database.csv'
AGE_2022 = MODEL_DIR / 'harvest_results_2022_for_2023_complete_database.csv'
AGE_2023 = MODEL_DIR / 'harvest_results_2023_for_2024_complete_database.csv'
AGE_2024_24BG = MODEL_DIR / 'harvest_results_2024_complete_database.csv'
AGE_2025 = MODEL_DIR / 'harvest_results_2025_for_2026_age_database.csv'
COUGAR_2021_FEATURES = MODEL_DIR / 'cougar_2021_for_2022_age_features_by_current_hunt_code.csv'

BACKFILL_2024_DIR = ROOT / 'pipeline' / 'RAW' / 'hunt_unit_database' / '2025' / 'pdf' / 'harvest_report' / 'harvest_2024_for_2025_backfill_package_revised'
BACKFILL_2024_COMBINED = BACKFILL_2024_DIR / 'combined_average_harvest_age_2024_for_2025_features_by_hunt_code.csv'
BACKFILL_GOAT_ALL = BACKFILL_2024_DIR / 'mountain_goat_average_age_2015_2024_all_available.csv'

OUT_GLOBAL = MODEL_DIR / 'harvest_average_age_global_merge_database.csv'
OUT_SUMMARY = MODEL_DIR / 'harvest_average_age_global_merge_database_summary.json'


def clean(value: object) -> str:
    return str(value or '').strip()


def norm_code(value: object) -> str:
    return ''.join(ch for ch in clean(value).upper() if ch.isalnum())


def parse_year(value: object) -> str:
    text = clean(value)
    if not text:
        return ''
    if text.isdigit():
        return text
    try:
        return str(int(float(text)))
    except ValueError:
        return ''


def parse_age(value: object) -> str:
    text = clean(value)
    if not text:
        return ''
    try:
        num = float(text)
    except ValueError:
        return ''
    if num <= 0 or num >= 30:
        return ''
    return f"{num:.2f}".rstrip('0').rstrip('.')


def confidence_rank(value: object) -> int:
    text = clean(value).lower()
    if text in {'high', 'unit_level_high', 'reviewed_high'}:
        return 3
    if text in {'medium', 'unit_level_medium', 'reviewed_medium'}:
        return 2
    if text in {'low', 'unit_level_low', 'reviewed_low'}:
        return 1
    if text in {'review', 'needs_review'}:
        return 0
    return 1


def species_norm(value: object) -> str:
    text = clean(value)
    if not text:
        return ''
    normalized = text.lower()
    if normalized in {'deer', 'mule deer'}:
        return 'Mule Deer'
    if normalized == 'black bear':
        return 'Black Bear'
    if normalized == 'mountain goat':
        return 'Mountain Goat'
    if normalized == 'elk':
        return 'Elk'
    if normalized == 'pronghorn':
        return 'Pronghorn'
    if normalized == 'moose':
        return 'Moose'
    if normalized == 'cougar':
        return 'Cougar'
    return text


def to_record(
    *,
    reported_hunt_year: object,
    hunt_code: object,
    species: object,
    average_harvest_age: object,
    average_harvest_age_3yr: object = '',
    age_source_file: object = '',
    age_source_url: object = '',
    age_source_sha256: object = '',
    age_source_page: object = '',
    age_source_table_title: object = '',
    crosswalk_source_page: object = '',
    crosswalk_source_hunt_name: object = '',
    crosswalk_source_weapon: object = '',
    crosswalk_confidence: object = '',
    age_mapping_status: object = '',
    source_package: str,
    source_priority: int,
    notes: object = '',
) -> dict[str, str] | None:
    year = parse_year(reported_hunt_year)
    code = norm_code(hunt_code)
    age = parse_age(average_harvest_age)
    age_3yr = parse_age(average_harvest_age_3yr)
    if not year or not code or (not age and not age_3yr):
        return None
    model_target_year = str(int(year) + 1)
    return {
        'reported_hunt_year': year,
        'model_target_year': model_target_year,
        'hunt_code': code,
        'species': species_norm(species),
        'average_harvest_age': age,
        'average_harvest_age_3yr': age_3yr,
        'age_data_available': 'true',
        'age_source_file': clean(age_source_file),
        'age_source_url': clean(age_source_url),
        'age_source_sha256': clean(age_source_sha256),
        'age_source_page': clean(age_source_page),
        'age_source_table_title': clean(age_source_table_title),
        'crosswalk_source_page': clean(crosswalk_source_page),
        'crosswalk_source_hunt_name': clean(crosswalk_source_hunt_name),
        'crosswalk_source_weapon': clean(crosswalk_source_weapon),
        'crosswalk_confidence': clean(crosswalk_confidence),
        'age_mapping_status': clean(age_mapping_status),
        'source_package': source_package,
        'source_priority': str(source_priority),
        'notes': clean(notes),
    }


def load_2021_records() -> list[dict[str, str]]:
    df = pd.read_csv(AGE_2021, dtype=str, low_memory=False).fillna('')
    out: list[dict[str, str]] = []
    for _, row in df.iterrows():
        rec = to_record(
            reported_hunt_year=row.get('reported_hunt_year', ''),
            hunt_code=row.get('hunt_code', ''),
            species=row.get('species', ''),
            average_harvest_age=row.get('average_harvest_age_2021', ''),
            age_source_file=row.get('source_files', ''),
            age_source_page=row.get('source_pages', ''),
            crosswalk_confidence=row.get('age_match_confidence_2021', ''),
            age_mapping_status=row.get('age_mapping_status_2021', ''),
            source_package='harvest_results_2021_for_2022_complete_database',
            source_priority=70,
            notes='2021 complete database lane',
        )
        if rec:
            out.append(rec)
    return out


def load_2022_records() -> list[dict[str, str]]:
    df = pd.read_csv(AGE_2022, dtype=str, low_memory=False).fillna('')
    out: list[dict[str, str]] = []
    for _, row in df.iterrows():
        rec = to_record(
            reported_hunt_year=row.get('reported_hunt_year', ''),
            hunt_code=row.get('hunt_code', ''),
            species=row.get('species', ''),
            average_harvest_age=row.get('average_harvest_age_2022', ''),
            average_harvest_age_3yr=row.get('average_harvest_age_3yr_2022', ''),
            age_source_file=row.get('source_file', ''),
            age_source_page=row.get('source_page', ''),
            crosswalk_confidence=row.get('age_match_confidence_2022', ''),
            age_mapping_status=row.get('age_mapping_status_2022', ''),
            source_package='harvest_results_2022_for_2023_complete_database',
            source_priority=72,
            notes='2022 complete database lane',
        )
        if rec:
            out.append(rec)
    return out


def load_2023_records() -> list[dict[str, str]]:
    df = pd.read_csv(AGE_2023, dtype=str, low_memory=False).fillna('')
    out: list[dict[str, str]] = []
    for _, row in df.iterrows():
        rec = to_record(
            reported_hunt_year=row.get('reported_hunt_year', ''),
            hunt_code=row.get('hunt_code', ''),
            species=row.get('species', ''),
            average_harvest_age=row.get('average_harvest_age_2023', ''),
            average_harvest_age_3yr=row.get('average_harvest_age_3yr_2023', ''),
            age_source_file=row.get('source_file', ''),
            age_source_page=row.get('source_page', ''),
            crosswalk_confidence=row.get('age_match_confidence_2023', ''),
            age_mapping_status=row.get('age_mapping_status_2023', ''),
            source_package='harvest_results_2023_for_2024_complete_database',
            source_priority=74,
            notes='2023 complete database lane',
        )
        if rec:
            out.append(rec)
    return out


def load_2024_revised_records() -> list[dict[str, str]]:
    df = pd.read_csv(BACKFILL_2024_COMBINED, dtype=str, low_memory=False).fillna('')
    out: list[dict[str, str]] = []
    for _, row in df.iterrows():
        rec = to_record(
            reported_hunt_year=row.get('reported_hunt_year', ''),
            hunt_code=row.get('hunt_code', ''),
            species=row.get('species', ''),
            average_harvest_age=row.get('average_harvest_age', ''),
            average_harvest_age_3yr=row.get('average_harvest_age_3yr', ''),
            age_source_file=row.get('age_source_file', ''),
            age_source_page=row.get('age_source_page', ''),
            age_source_table_title=row.get('age_source_table_title', ''),
            crosswalk_confidence=row.get('crosswalk_confidence', ''),
            age_mapping_status=row.get('crosswalk_method', '') or 'mapped_revised_2024_backfill',
            source_package='harvest_2024_for_2025_backfill_package_revised_combined',
            source_priority=95,
            notes=row.get('notes', ''),
        )
        if rec:
            out.append(rec)
    return out


def load_2024_24bg_fallback_records() -> list[dict[str, str]]:
    df = pd.read_csv(AGE_2024_24BG, dtype=str, low_memory=False).fillna('')
    allowed_species = {'Mule Deer', 'Pronghorn', 'Moose'}
    out: list[dict[str, str]] = []
    for _, row in df.iterrows():
        if species_norm(row.get('species', '')) not in allowed_species:
            continue
        rec = to_record(
            reported_hunt_year=row.get('reported_hunt_year', ''),
            hunt_code=row.get('hunt_code', ''),
            species=row.get('species', ''),
            average_harvest_age=row.get('average_age_2024_from_24_bg', ''),
            average_harvest_age_3yr=row.get('average_age_3yr_from_24_bg', ''),
            age_source_file=row.get('source_file', ''),
            age_source_page=row.get('source_page', ''),
            age_source_table_title=row.get('age_source_table_24_bg', ''),
            crosswalk_confidence='medium',
            age_mapping_status=row.get('age_mapping_status_24_bg', ''),
            source_package='harvest_results_2024_complete_database_24_bg_fallback',
            source_priority=80,
            notes='24_bg fallback for species not covered in revised package',
        )
        if rec:
            out.append(rec)
    return out


def load_goat_historical_records() -> list[dict[str, str]]:
    df = pd.read_csv(BACKFILL_GOAT_ALL, dtype=str, low_memory=False).fillna('')
    out: list[dict[str, str]] = []
    for _, row in df.iterrows():
        rec = to_record(
            reported_hunt_year=row.get('reported_hunt_year', ''),
            hunt_code=row.get('hunt_code', ''),
            species=row.get('species', ''),
            average_harvest_age=row.get('average_harvest_age', ''),
            average_harvest_age_3yr=row.get('average_harvest_age_3yr', ''),
            age_source_file=row.get('source_file', ''),
            age_source_page=row.get('source_page', ''),
            age_source_table_title=row.get('source_table_title', ''),
            crosswalk_confidence=row.get('crosswalk_confidence', ''),
            age_mapping_status='goat_historical_crosswalked_scope',
            source_package='harvest_2024_for_2025_backfill_package_revised_goat_all_years',
            source_priority=90,
            notes=row.get('notes', ''),
        )
        if rec:
            out.append(rec)
    return out


def load_cougar_2021_records() -> list[dict[str, str]]:
    df = pd.read_csv(COUGAR_2021_FEATURES, dtype=str, low_memory=False).fillna('')
    out: list[dict[str, str]] = []
    for _, row in df.iterrows():
        rec = to_record(
            reported_hunt_year=row.get('reported_hunt_year', ''),
            hunt_code=row.get('current_hunt_code', ''),
            species=row.get('species', ''),
            average_harvest_age=row.get('average_harvest_age', ''),
            age_source_file=row.get('age_source_file', ''),
            age_source_page=row.get('source_page', ''),
            age_source_table_title=row.get('age_source_table_title', ''),
            crosswalk_confidence=row.get('crosswalk_confidence', ''),
            age_mapping_status=row.get('age_match_scope', '') or 'cougar_unit_to_hunt_code_crosswalk',
            source_package='cougar_2021_for_2022_crosswalk_package',
            source_priority=85,
            notes=row.get('notes', ''),
        )
        if rec:
            out.append(rec)
    return out


def load_retained_pre_2025_baseline_records() -> list[dict[str, str]]:
    """Retain the tracked canonical history when retired source packages are absent.

    The repository's tracked global database is the durable selected result for
    the 2015-2024 lanes. Filtering it before reading the new 2025 lane keeps
    incremental rebuilds deterministic and prevents prior promoted history from
    depending on source-package directories that are no longer in this checkout.
    """

    df = pd.read_csv(OUT_GLOBAL, dtype=str, low_memory=False).fillna('')
    out: list[dict[str, str]] = []
    for _, row in df.iterrows():
        if int(parse_year(row.get('reported_hunt_year', '')) or '0') >= 2025:
            continue
        rec = to_record(
            reported_hunt_year=row.get('reported_hunt_year', ''),
            hunt_code=row.get('hunt_code', ''),
            species=row.get('species', ''),
            average_harvest_age=row.get('average_harvest_age', ''),
            average_harvest_age_3yr=row.get('average_harvest_age_3yr', ''),
            age_source_file=row.get('age_source_file', ''),
            age_source_url=row.get('age_source_url', ''),
            age_source_sha256=row.get('age_source_sha256', ''),
            age_source_page=row.get('age_source_page', ''),
            age_source_table_title=row.get('age_source_table_title', ''),
            crosswalk_source_page=row.get('crosswalk_source_page', ''),
            crosswalk_source_hunt_name=row.get('crosswalk_source_hunt_name', ''),
            crosswalk_source_weapon=row.get('crosswalk_source_weapon', ''),
            crosswalk_confidence=row.get('crosswalk_confidence', ''),
            age_mapping_status=row.get('age_mapping_status', ''),
            source_package=clean(row.get('source_package', '')) or 'retained_pre_2025_canonical_baseline',
            source_priority=int(clean(row.get('source_priority', '0')) or '0'),
            notes=row.get('notes', ''),
        )
        if rec:
            out.append(rec)
    return out


def load_2025_records() -> list[dict[str, str]]:
    df = pd.read_csv(AGE_2025, dtype=str, low_memory=False).fillna('')
    out: list[dict[str, str]] = []
    for _, row in df.iterrows():
        rec = to_record(
            reported_hunt_year=row.get('reported_hunt_year', ''),
            hunt_code=row.get('hunt_code', ''),
            species=row.get('species', ''),
            average_harvest_age=row.get('average_harvest_age', ''),
            average_harvest_age_3yr=row.get('average_harvest_age_3yr', ''),
            age_source_file=row.get('age_source_file', ''),
            age_source_url=row.get('age_source_url', ''),
            age_source_sha256=row.get('age_source_sha256', ''),
            age_source_page=row.get('age_source_page', ''),
            age_source_table_title=row.get('age_source_table_title', ''),
            crosswalk_source_page=row.get('crosswalk_source_page', ''),
            crosswalk_source_hunt_name=row.get('crosswalk_source_hunt_name', ''),
            crosswalk_source_weapon=row.get('crosswalk_source_weapon', ''),
            crosswalk_confidence=row.get('crosswalk_confidence', ''),
            age_mapping_status=row.get('age_mapping_status', ''),
            source_package='official_2026_dwr_age_and_permit_tables',
            source_priority=100,
            notes=row.get('notes', ''),
        )
        if rec:
            out.append(rec)
    return out


def select_best(records: list[dict[str, str]]) -> tuple[list[dict[str, str]], dict[str, int]]:
    by_key: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for rec in records:
        by_key[(rec['reported_hunt_year'], rec['hunt_code'], species_norm(rec['species']))].append(rec)

    selected: list[dict[str, str]] = []
    tie_count = 0
    for key, items in by_key.items():
        items_sorted = sorted(
            items,
            key=lambda r: (
                int(clean(r.get('source_priority', '0')) or '0'),
                confidence_rank(r.get('crosswalk_confidence', '')),
                1 if clean(r.get('average_harvest_age_3yr', '')) else 0,
            ),
            reverse=True,
        )
        top = items_sorted[0]
        if len(items_sorted) > 1:
            runner = items_sorted[1]
            if (
                clean(top.get('source_priority', '')) == clean(runner.get('source_priority', ''))
                and clean(top.get('average_harvest_age', '')) != clean(runner.get('average_harvest_age', ''))
            ):
                tie_count += 1
                top = dict(top)
                top['notes'] = (top.get('notes', '') + ' | tie_resolved_by_confidence_or_3yr_presence').strip(' |')
        selected.append(top)

    selected_sorted = sorted(selected, key=lambda r: (int(r['reported_hunt_year']), r['hunt_code']))
    return selected_sorted, {'conflicting_same_priority_age_value_keys': tie_count}


def main() -> None:
    legacy_required = [
        AGE_2021,
        AGE_2022,
        AGE_2023,
        AGE_2024_24BG,
        BACKFILL_2024_COMBINED,
        BACKFILL_GOAT_ALL,
        COUGAR_2021_FEATURES,
    ]
    required = [AGE_2025]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise FileNotFoundError('Missing required source files: ' + '; '.join(missing))

    all_records: list[dict[str, str]] = []
    source_counts: dict[str, int] = {}

    if all(path.exists() for path in legacy_required):
        lanes = [
            ('2021_complete', load_2021_records),
            ('2022_complete', load_2022_records),
            ('2023_complete', load_2023_records),
            ('2024_revised_combined', load_2024_revised_records),
            ('2024_24bg_fallback', load_2024_24bg_fallback_records),
            ('goat_historical_all_years', load_goat_historical_records),
            ('cougar_2021_crosswalked', load_cougar_2021_records),
        ]
    elif OUT_GLOBAL.exists():
        lanes = [('retained_pre_2025_canonical_baseline', load_retained_pre_2025_baseline_records)]
    else:
        missing_legacy = [str(path) for path in legacy_required if not path.exists()]
        raise FileNotFoundError(
            'Missing legacy age inputs and no tracked global baseline is available: ' + '; '.join(missing_legacy)
        )
    lanes.append(('2025_official_dwr_tables', load_2025_records))

    for lane_name, loader in lanes:
        lane_rows = loader()
        source_counts[lane_name] = len(lane_rows)
        all_records.extend(lane_rows)

    selected, selection_stats = select_best(all_records)
    out_df = pd.DataFrame(selected).fillna('')

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(OUT_GLOBAL, index=False, encoding='utf-8-sig')

    year_counts = out_df['reported_hunt_year'].value_counts().sort_index().to_dict() if not out_df.empty else {}
    species_counts = out_df['species'].value_counts().to_dict() if not out_df.empty else {}

    summary = {
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'global_age_database': str(OUT_GLOBAL.relative_to(ROOT)).replace('\\', '/'),
        'input_lane_row_counts': source_counts,
        'input_rows_total': len(all_records),
        'selected_rows_total': len(out_df),
        'selected_unique_year_hunt_code_keys': int(out_df[['reported_hunt_year', 'hunt_code']].drop_duplicates().shape[0]) if not out_df.empty else 0,
        'selected_unique_year_hunt_code_species_keys': int(out_df[['reported_hunt_year', 'hunt_code', 'species']].drop_duplicates().shape[0]) if not out_df.empty else 0,
        'reported_hunt_year_counts': year_counts,
        'species_counts': species_counts,
        'selection_stats': selection_stats,
        'outputs': {
            'global_age_csv': str(OUT_GLOBAL.relative_to(ROOT)).replace('\\', '/'),
            'global_age_summary': str(OUT_SUMMARY.relative_to(ROOT)).replace('\\', '/'),
        },
    }
    OUT_SUMMARY.write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
