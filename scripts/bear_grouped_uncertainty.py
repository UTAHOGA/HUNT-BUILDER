"""ADR-0009 diagnostics: resample complete groups, never independent rungs.

This module does not assign a production certification status. Group identities
must be frozen from pre-draw lineage before revised candidate scoring.
"""
from collections import defaultdict

import numpy as np

METRICS = ('mae', 'p90_absolute_error', 'tail_error_rate_over_25pp', 'bias')
ANALYSES = {
    'WHOLE_HUNT_YEAR_BLOCKS': ('target_year', 'hunt_identity', 'program_regime'),
    'WHOLE_HUNT_REGIME_HISTORIES': ('hunt_identity', 'program_regime'),
    'WHOLE_DRAW_YEARS': ('target_year',),
}


def group_indices(rows, fields):
    groups = defaultdict(list)
    for index, row in enumerate(rows):
        if any(str(row.get(field, '')).strip() == '' for field in fields):
            raise ValueError('Missing frozen group identity')
        groups[tuple(str(row[field]) for field in fields)].append(index)
    return [np.asarray(groups[key], dtype=int) for key in sorted(groups)]


def metric_values(errors):
    if len(errors) == 0:
        return None
    absolute = np.abs(errors)
    return dict(zip(METRICS, map(float, (absolute.mean(), np.quantile(absolute, .9, method='linear'),
                                       (absolute > .25).mean(), errors.mean()))))


def grouped_intervals(rows, fields, *, replicates=10000, seed=20260920):
    groups = group_indices(rows, fields)
    if not groups:
        return {'groups': 0, 'estimable': False, 'populations': {}}
    errors = np.asarray([float(r['predicted_probability']) - float(r['actual_probability']) for r in rows])
    lanes = np.asarray([r['residency'] for r in rows])
    populations = ('POOLED_DESIGN', 'Resident', 'Nonresident')
    draws = {p: [] for p in populations}
    undefined = dict.fromkeys(populations, 0)
    contributing = {p: sum(int(p == 'POOLED_DESIGN' or np.any(lanes[g] == p)) for g in groups) for p in populations}
    rng = np.random.Generator(np.random.PCG64(seed))
    for _ in range(replicates):
        selected = np.concatenate([groups[i] for i in rng.integers(0, len(groups), len(groups))])
        for population in populations:
            indices = selected if population == 'POOLED_DESIGN' else selected[lanes[selected] == population]
            values = metric_values(errors[indices])
            if values is None:
                undefined[population] += 1  # Never redraw or manufacture a value.
            else:
                draws[population].append([values[m] for m in METRICS])
    report = {}
    for population in populations:
        samples = np.asarray(draws[population])
        report[population] = {
            'contributing_groups': contributing[population],
            'undefined_replicates': undefined[population],
            'estimable': contributing[population] >= 2 and undefined[population] == 0,
            'intervals_95': {m: np.quantile(samples[:, i], [.025, .975], method='linear').tolist()
                             for i, m in enumerate(METRICS)} if len(samples) else {},
        }
    return {'groups': len(groups), 'replicates': replicates, 'seed': seed,
            'estimable': all(p['estimable'] for p in report.values()), 'populations': report}


def failures(values):
    if values is None:
        return ['NO_SCORED_ROWS']
    return [name for name, limit in [('mae', .1), ('p90_absolute_error', .3),
                                    ('tail_error_rate_over_25pp', .1)] if values[name] > limit]


def review_groups(rows, *, replicates=10000):
    errors = np.asarray([float(r['predicted_probability']) - float(r['actual_probability']) for r in rows])
    breakdowns, recurring = {}, defaultdict(set)
    for label, fields in {
        'residency': ('residency',), 'target_year': ('target_year',),
        'hunt_identity': ('hunt_identity', 'program_regime'),
        'year_residency': ('target_year', 'residency'),
        'hunt_year_residency': ('hunt_identity', 'program_regime', 'target_year', 'residency'),
    }.items():
        cells = []
        for indices in group_indices(rows, fields):
            identity = {f: rows[int(indices[0])][f] for f in fields}
            values = metric_values(errors[indices])
            failed = failures(values)
            cells.append({**identity, 'rows': len(indices), **values, 'failed_metrics': failed})
            if label == 'hunt_year_residency':
                for metric in failed:
                    recurring[(str(identity['hunt_identity']), str(identity['program_regime']), identity['residency'], metric)].add(identity['target_year'])
        breakdowns[label] = cells
    sensitivity = {}
    for label in ('WHOLE_HUNT_REGIME_HISTORIES', 'WHOLE_DRAW_YEARS'):
        sensitivity[label] = []
        for excluded in group_indices(rows, ANALYSES[label]):
            keep = np.setdiff1d(np.arange(len(rows)), excluded)
            for population in ('POOLED_DESIGN', 'Resident', 'Nonresident'):
                indices = keep if population == 'POOLED_DESIGN' else np.asarray([i for i in keep if rows[int(i)]['residency'] == population], dtype=int)
                values = metric_values(errors[indices])
                sensitivity[label].append({
                    'excluded': {f: rows[int(excluded[0])][f] for f in ANALYSES[label]},
                    'population': population, 'metrics': values, 'failed_metrics': failures(values)})
    return {
        'scope': 'DEPENDENCE_SENSITIVITY_NOT_CERTIFICATION',
        'point_rows_are_independent': False, 'rows': len(rows),
        'pooled_metrics': metric_values(errors), 'breakdowns': breakdowns,
        'recurring_failures': [{'hunt_identity': key[0], 'program_regime': key[1], 'residency': key[2],
                                'metric': key[3], 'years': sorted(years)}
                               for key, years in sorted(recurring.items()) if len(years) >= 2],
        'uncertainty': {name: grouped_intervals(rows, fields, replicates=replicates)
                        for name, fields in ANALYSES.items()},
        'leave_one_group_out': sensitivity,
    }
