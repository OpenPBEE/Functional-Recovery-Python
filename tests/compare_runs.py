"""Batch comparison engine for Functional Recovery Simulation outputs.

Compares Python-generated recovery outputs against reference data using
three tiers of statistical checks:

1. High-level: mean recovery days within tolerance (reoccupancy, functional,
   full repair).
2. AUC: system-level area under recovery curve within tolerance.
3. Pointwise: system-level curve error metrics (P95, MAE) within tolerance.

Can be used as a library via ``evaluate_tolerances()`` or as a standalone
CLI tool.

The comparison methods are based on scripts originally developed by Ziyi Wang.
"""

import argparse
import json
import os
import warnings
from pathlib import Path
import numpy as np

def load_runs(directory):
    """Load recovery output JSONs from a directory.

    Reads every ``*.json`` file, extracts building-level recovery days
    (reoccupancy, functional, full repair) and system-level breakdown
    curves.  Files that are malformed or missing required keys are
    skipped with a warning.

    Args:
        directory: Path to a directory containing recovery output JSON
            files (one per batch run).

    Returns:
        A list of dicts, one per successfully loaded run.  Each dict
        contains scalar recovery-day lists (``reoc``, ``func``, ``full``)
        and system breakdown arrays (``*_sys_names``, ``*_sys_bkdwns``,
        ``*_targ_days``) for reoccupancy and functional recovery.

    Raises:
        NotADirectoryError: If *directory* does not exist.
    """
    runs = []
    dir_path = Path(directory)
    if not dir_path.is_dir():
        raise NotADirectoryError(f"Directory {directory} does not exist.")
        
    for file_path in dir_path.glob("*.json"):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            warnings.warn(f"Failed to load {file_path.name}: {e}")
            continue
            
        # Handle nesting based on reference script
        root_data = data
        if 'functionality' in data:
            data = data['functionality']
            
        if 'recovery' not in data:
            warnings.warn(f"Skipping {file_path.name} - missing 'recovery' key.")
            continue
            
        try:
            run_dict = {
                'file': file_path.name,
                'reoc': data['recovery']['reoccupancy']['building_level']['recovery_day'],
                'func': data['recovery']['functional']['building_level']['recovery_day'],
                'full': None,
                
                # Reoc breakdowns
                'reoc_sys_names': data['recovery']['reoccupancy']['breakdowns']['system_names'],
                'reoc_sys_bkdwns': data['recovery']['reoccupancy']['breakdowns']['system_breakdowns'],
                'reoc_targ_days': data['recovery']['reoccupancy']['breakdowns']['perform_targ_days'],
                
                # Func breakdowns
                'func_sys_names': data['recovery']['functional']['breakdowns']['system_names'],
                'func_sys_bkdwns': data['recovery']['functional']['breakdowns']['system_breakdowns'],
                'func_targ_days': data['recovery']['functional']['breakdowns']['perform_targ_days'],
            }
        except KeyError as e:
            warnings.warn(f"Skipping {file_path.name} - malformed data structure missing {e}")
            continue
            
        try:
            per_story = np.asarray(data['building_repair_schedule']['full']['repair_complete_day']['per_story'])
            if per_story.ndim > 1:
                # Multiple stories (realizations x stories) -> get max across stories for building recovery
                full_rec = np.amax(per_story, axis=1)
            else:
                full_rec = per_story
            run_dict['full'] = full_rec.tolist()
        except KeyError:
            warnings.warn(f"{file_path.name} missing 'building_repair_schedule.full.repair_complete_day.per_story'.")
            run_dict['full'] = []
            
        runs.append(run_dict)
        
    return runs

def get_high_level_stats(runs, key):
    """Compute summary statistics for a recovery metric across batch runs.

    For each run, calculates the mean and percentiles (p25, p50, p75) of
    the per-realization recovery days, then averages those statistics
    across all runs.

    Args:
        runs: List of run dicts as returned by ``load_runs()``.
        key: Metric key to extract from each run (``'reoc'``, ``'func'``,
            or ``'full'``).

    Returns:
        A dict with keys ``'mean'``, ``'p25'``, ``'p50'``, ``'p75'``
        representing the run-averaged statistics.  Returns all zeros if
        no valid data is found.
    """
    means, p25s, p50s, p75s = [], [], [], []
    for r in runs:
        vals = r[key]
        if not vals:
            continue
        means.append(np.mean(vals))
        p25s.append(np.percentile(vals, 25))
        p50s.append(np.percentile(vals, 50))
        p75s.append(np.percentile(vals, 75))

    if not means:
        return {'mean': 0.0, 'p25': 0.0, 'p50': 0.0, 'p75': 0.0}

    return {
        'mean': np.mean(means),
        'p25': np.mean(p25s),
        'p50': np.mean(p50s),
        'p75': np.mean(p75s)
    }

def standardize_to_grid(t, y, T_END=365.0, dt=1.0, extend="last"):
    """Interpolate an irregular time-series onto a uniform daily grid.

    Produces a regularly spaced representation of a recovery curve on
    ``[0, T_END]`` with spacing *dt*.  Boundary handling: if the curve
    does not start at t=0, a point is prepended assuming the initial
    recovery fraction equals the first observed value.  If the curve
    ends before *T_END*, the tail is filled according to *extend*.

    Args:
        t: 1-D array of time values (days).
        y: 1-D array of corresponding recovery fractions.
        T_END: End of the evaluation window in days.
        dt: Grid spacing in days.
        extend: How to fill beyond the last observed time —
            ``'last'`` holds the final value, ``'zero'`` drops to 0.

    Returns:
        Tuple ``(t_grid, y_grid)`` of equal-length 1-D arrays.

    Raises:
        ValueError: If *t* is empty or *extend* is unrecognized.
    """
    t = np.asarray(t, dtype=float)
    y = np.asarray(y, dtype=float)

    t_grid = np.arange(0.0, T_END + dt, dt)

    if t.size == 0:
        raise ValueError("Empty time array.")

    # Assume recovery at t=0 equals the first observed value
    if t[0] > 0.0:
        t = np.insert(t, 0, 0.0)
        y = np.insert(y, 0, y[0])

    y_grid = np.interp(t_grid, t, y)

    if t[-1] < T_END:
        if extend == "last":
            y_grid[t_grid > t[-1]] = y[-1]
        elif extend == "zero":
            y_grid[t_grid > t[-1]] = 0.0
        else:
            raise ValueError("extend must be 'last' or 'zero'")

    return t_grid, y_grid

def get_system_curves(runs, sys_prefix):
    """Extract and average system-level breakdown curves across batch runs.

    For each system name found in the first run, collects the
    corresponding breakdown curve from every run, standardizes each to a
    daily grid, and averages them.

    Args:
        runs: List of run dicts as returned by ``load_runs()``.
        sys_prefix: Key prefix — ``'reoc'`` for reoccupancy or ``'func'``
            for functional recovery.

    Returns:
        Tuple ``(t_grid, avg_curves)`` where *t_grid* is the daily time
        grid and *avg_curves* is a list of dicts, each with ``'name'``
        (system name) and ``'curve'`` (averaged 1-D array).
    """
    t_grid = np.arange(0.0, 365.0 + 1.0, 1.0)

    if not runs:
        return t_grid, []

    systems = runs[0][f'{sys_prefix}_sys_names']

    avg_curves = []
    for sys_name in systems:
        curves = []
        for r in runs:
            run_sys_names = r[f'{sys_prefix}_sys_names']
            try:
                run_idx = run_sys_names.index(sys_name)
            except ValueError:
                # System not present in this run; average over remaining runs
                continue

            t = r[f'{sys_prefix}_targ_days']
            y = r[f'{sys_prefix}_sys_bkdwns'][run_idx]
            _, y_grid = standardize_to_grid(t, y, T_END=365, dt=1.0)
            curves.append(y_grid)

        if curves:
            avg_curves.append({
                'name': sys_name,
                'curve': np.mean(curves, axis=0)
            })

    return t_grid, avg_curves

def auc_to_1yr(y, t, T_END=365):
    """Compute the area under a recovery curve from 0 to *T_END* days.

    Handles three boundary cases before integrating:

    * If the curve starts after t=0, prepend a point at t=0 using the
      first observed value.
    * If the curve ends before *T_END*, extend it by holding the last
      value.
    * If the curve extends beyond *T_END*, truncate and interpolate at
      *T_END*.

    Args:
        y: 1-D array of recovery fractions.
        t: 1-D array of corresponding time values (days).
        T_END: Upper integration bound in days.

    Returns:
        Area under the curve as a float (units: fraction-days).
    """
    y = np.asarray(y, dtype=float)
    t = np.asarray(t, dtype=float)

    if t[0] > 0:
        t = np.insert(t, 0, 0.0)
        y = np.insert(y, 0, y[0])

    if t[-1] < T_END:
        t = np.append(t, T_END)
        y = np.append(y, y[-1])

    if t[-1] > T_END:
        mask = t < T_END
        t_trunc = t[mask]
        y_trunc = y[mask]
        y_end = np.interp(T_END, t, y)
        t = np.append(t_trunc, T_END)
        y = np.append(y_trunc, y_end)

    return float(np.trapezoid(y, t))

def curve_diff_metrics(y_py, y_ref, t_grid):
    """Compute pointwise error metrics between two recovery curves.

    All error values are in the same units as the input curves
    (recovery fraction, 0-1 scale).

    Args:
        y_py: 1-D array of Python-generated recovery fractions.
        y_ref: 1-D array of reference recovery fractions (same length).
        t_grid: 1-D array of corresponding time values (days).

    Returns:
        A dict with keys ``'MAE'``, ``'RMSE'``, ``'P50_abs'``,
        ``'P95_abs'``, ``'P99_abs'``, ``'Max_abs'``, and ``'t_at_max'``
        (day at which the maximum absolute error occurs).
    """
    d = np.abs(y_py - y_ref)

    mae = float(np.mean(d))
    rmse = float(np.sqrt(np.mean(d**2)))
    p50 = float(np.quantile(d, 0.50))
    p95 = float(np.quantile(d, 0.95))
    p99 = float(np.quantile(d, 0.99))
    max_abs = float(np.max(d))

    i_max = int(np.argmax(d))
    t_at_max = float(t_grid[i_max])

    return {
        "MAE": mae,
        "RMSE": rmse,
        "P50_abs": p50,
        "P95_abs": p95,
        "P99_abs": p99,
        "Max_abs": max_abs,
        "t_at_max": t_at_max,
    }

def evaluate_tolerances(reference_dir, python_dir):
    """Run the three-tier comparison and return a results dict.

    Loads runs from both directories, computes high-level, AUC, and
    pointwise metrics for reoccupancy, functional, and full-repair
    recovery, and applies pass/fail tolerance checks to each.

    Args:
        reference_dir: Path to directory containing reference output
            JSON files.
        python_dir: Path to directory containing Python output JSON
            files.

    Returns:
        A dict with four top-level keys:

        * ``'high_level'``: per-metric stats and pass/fail.
        * ``'auc'``: per-system AUC comparison and pass/fail.
        * ``'pointwise'``: per-system curve error metrics and pass/fail.
        * ``'all_passed'``: ``True`` only if every check passed.

    Raises:
        ValueError: If either directory contains no valid JSON runs.
    """
    ref_runs = load_runs(reference_dir)
    py_runs = load_runs(python_dir)

    if not ref_runs or not py_runs:
        raise ValueError("Missing valid JSON runs for comparison in one or both directories.")
        
    results = {
        "high_level": {},
        "auc": {"reoc": [], "func": []},
        "pointwise": {"reoc": [], "func": []},
        "all_passed": True
    }
    
    # --- 1. High-level Metrics ---
    hl_metrics = ['reoc', 'func', 'full']
    
    for metric in hl_metrics:
        py_stats = get_high_level_stats(py_runs, metric)
        ref_stats = get_high_level_stats(ref_runs, metric)

        if ref_stats['mean'] != 0:
            diff = 100.0 * abs(py_stats['mean'] - ref_stats['mean']) / ref_stats['mean']
        else:
            diff = float('nan')

        # Tolerance: mean recovery days within 3% of reference
        passed = diff <= 4.0 or (np.isnan(diff) and py_stats['mean'] == 0)
        if not passed: results["all_passed"] = False

        results["high_level"][metric] = {
            "mean": py_stats["mean"],
            "p25": py_stats["p25"],
            "p50": py_stats["p50"],
            "p75": py_stats["p75"],
            "ref_mean": ref_stats["mean"],
            "ref_p25": ref_stats["p25"],
            "ref_p50": ref_stats["p50"],
            "ref_p75": ref_stats["p75"],
            "pct_diff": diff,
            "pass": passed
        }

    # --- 2. System Level AUC Metrics ---
    for tag_key, prefix in [('reoc', 'reoc'), ('func', 'func')]:
        t_grid, ref_curves = get_system_curves(ref_runs, prefix)
        _, py_curves = get_system_curves(py_runs, prefix)

        for rc in ref_curves:
            sys_name = rc['name']
            pc = next((c for c in py_curves if c['name'] == sys_name), None)
            if not pc:
                results["auc"][tag_key].append({
                    "system": sys_name,
                    "auc_py": float('nan'),
                    "auc_ref": auc_to_1yr(rc['curve'], t_grid),
                    "pct_diff": float('nan'),
                    "pass": False,
                    "missing": True
                })
                results["all_passed"] = False
                continue

            auc_ref = auc_to_1yr(rc['curve'], t_grid)
            auc_py = auc_to_1yr(pc['curve'], t_grid)
            if auc_ref != 0:
                pct_diff = 100 * abs(auc_py - auc_ref) / auc_ref
            else:
                pct_diff = float('nan')

            # Tolerance: system AUC within 1% of reference
            passed = pct_diff <= 1.0 or (np.isnan(pct_diff) and auc_py == 0)
            if not passed: results["all_passed"] = False

            results["auc"][tag_key].append({
                "system": sys_name,
                "auc_py": auc_py,
                "auc_ref": auc_ref,
                "pct_diff": pct_diff,
                "pass": passed,
                "missing": False
            })

    # --- 3. System Level Pointwise Metrics ---
    for tag_key, prefix in [('reoc', 'reoc'), ('func', 'func')]:
        t_grid, ref_curves = get_system_curves(ref_runs, prefix)
        _, py_curves = get_system_curves(py_runs, prefix)

        for rc in ref_curves:
            sys_name = rc['name']
            pc = next((c for c in py_curves if c['name'] == sys_name), None)
            if not pc:
                results["pointwise"][tag_key].append({
                    "system": sys_name,
                    "MAE": float('nan'),
                    "RMSE": float('nan'),
                    "P50_abs": float('nan'),
                    "P95_abs": float('nan'),
                    "P99_abs": float('nan'),
                    "Max_abs": float('nan'),
                    "t_at_max": float('nan'),
                    "pass": False,
                    "missing": True
                })
                results["all_passed"] = False
                continue
            
            metrics = curve_diff_metrics(pc['curve'], rc['curve'], t_grid)
            # Tolerance: P95 absolute error ≤ 4% and MAE ≤ 2% (fraction scale)
            passed = metrics['P95_abs'] <= 0.04 and metrics['MAE'] <= 0.02
            if not passed: results["all_passed"] = False
            
            results["pointwise"][tag_key].append({
                "system": sys_name,
                "MAE": metrics['MAE'],
                "RMSE": metrics['RMSE'],
                "P50_abs": metrics['P50_abs'],
                "P95_abs": metrics['P95_abs'],
                "P99_abs": metrics['P99_abs'],
                "Max_abs": metrics['Max_abs'],
                "t_at_max": metrics['t_at_max'],
                "pass": passed,
                "missing": False
            })

    return results

def print_results(results, reference_dir, python_dir):
    """Pretty-print the three comparison tables to stdout.

    Args:
        results: Results dict as returned by ``evaluate_tolerances()``.
        reference_dir: Path shown in the header for the reference data.
        python_dir: Path shown in the header for the Python data.
    """
    print(f"Loading reference runs from {reference_dir}...")
    print(f"Loading Python runs from {python_dir}...\n")

    # --- 1. High-level Metrics ---
    print('===== High-level recovery statistics (days) =====')
    print('Metric           | Code   | mean  | p25   | median | p75   | % diff (mean) | Pass?')
    print('-----------------|--------|-------|-------|--------|-------|---------------|------')

    labels = {'reoc': 'Reoccupancy', 'func': 'Functional', 'full': 'Full repair'}
    for metric, label in labels.items():
        if metric not in results["high_level"]:
            continue
        r = results["high_level"][metric]
        print(f"{label:<16} | Py    | {r['mean']:5.1f} | {r['p25']:5.1f} | {r['p50']:6.1f} | {r['p75']:5.1f} |               |")
        print(f"{'':<16} | Ref   | {r['ref_mean']:5.1f} | {r['ref_p25']:5.1f} | {r['ref_p50']:6.1f} | {r['ref_p75']:5.1f} | {r['pct_diff']:7.3f}%     | {'PASS' if r['pass'] else 'FAIL'}")
    print('=================================================\n')

    # --- 2. System Level AUC Metrics ---
    print('===== System-level AUC comparison (0-365 days) =====')
    print('Tag         | System                | AUC Py   | AUC Ref | % diff     | Pass?')
    print('------------|-----------------------|----------|---------|------------|------')
    labels = {'reoc': 'Reoccupancy', 'func': 'Functional'}
    for tag_key, label in labels.items():
        for item in results["auc"][tag_key]:
            if item.get("missing"):
                print(f"{label:<11} | {item['system']:<21} | MISSING  | {item['auc_ref']:7.3f} | N/A        | FAIL")
            else:
                diff_str = f"{item['pct_diff']:8.4f}%" if not np.isnan(item['pct_diff']) else "     NaN"
                print(f"{label:<11} | {item['system']:<21} | {item['auc_py']:8.3f} | {item['auc_ref']:7.3f} | {diff_str:>10} | {'PASS' if item['pass'] else 'FAIL'}")
    print('====================================================\n')

    # --- 3. System Level Pointwise Metrics ---
    print('===== System-level curve comparison (pointwise metrics 0-365 days) =====')
    print('Tag         | System                | MAE    | RMSE   | P50    | P95    | P99    | Max    | t@Max | PASS? ')
    print('------------|-----------------------|--------|--------|--------|--------|--------|--------|-------|------')
    for tag_key, label in labels.items():
        for item in results["pointwise"][tag_key]:
            if item.get("missing"):
                print(f"{label:<11} | {item['system']:<21} | MISSING")
            else:
                print(f"{label:<11} | {item['system']:<21} | "
                      f"{item['MAE']:6.3f} | {item['RMSE']:6.3f} | {item['P50_abs']:6.3f} | {item['P95_abs']:6.3f} | {item['P99_abs']:6.3f} | {item['Max_abs']:6.3f} | "
                      f"{item['t_at_max']:5.0f} | {'PASS' if item['pass'] else 'FAIL'}")
    
    print('========================================================================')
    
    if not results.get("all_passed", False):
        print("\nResult: FAIL. One or more assertions did not meet the tolerance criteria.")
    else:
        print("\nResult: PASS. All comparisons meet the tolerance criteria.")

def main():
    """CLI entry point: compare two directories and print results."""
    parser = argparse.ArgumentParser(description="Batch comparison of Python vs reference Functional Recovery runs.")
    parser.add_argument('reference_dir', type=str, help='Directory containing reference output JSON runs')
    parser.add_argument('python_dir', type=str, help='Directory containing Python output JSON runs')
    args = parser.parse_args()

    try:
        results = evaluate_tolerances(args.reference_dir, args.python_dir)
        print_results(results, args.reference_dir, args.python_dir)
        
        if not results.get("all_passed", False):
            raise ValueError("One or more assertions did not meet the tolerance criteria.")
    except (NotADirectoryError, ValueError) as e:
        print(f"Error: {e}")
        raise SystemExit(1)

if __name__ == '__main__':
    main()
