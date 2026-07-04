"""Time-in-Healthy-Range over a DataFrame of readings.

Unlike analytics.py (which works off the database, one metric at a time), this
computes a "simultaneous" TIHR as well: the share of timestamps where every
metric is in range at once. Handy for the dashboard, where we already have the
whole history in a frame.
"""

import numpy as np
import pandas as pd

# clinical defaults, mg/dL etc; callers can override per-patient
DEFAULT_RANGES = {
    "systolic_bp_mmhg": (90, 120),
    "heart_rate_bpm": (60, 100),
    "glucose_mg_dl": (70, 140),
}


def calculate_tihr(
    df: pd.DataFrame,
    ranges: dict[str, tuple[float, float]] | None = None,
    start: str | None = None,
    end: str | None = None,
    timestamp_col: str = "timestamp",
) -> dict:
    """
    Calculate Time-in-Healthy-Range over a given period.

    Args:
        df: DataFrame with a timestamp column and metric columns.
        ranges: Override thresholds, e.g. {"heart_rate_bpm": (55, 110)}.
                Missing keys fall back to DEFAULT_RANGES.
        start: ISO timestamp string for window start (inclusive). None = use all data.
        end: ISO timestamp string for window end (inclusive). None = use all data.
        timestamp_col: Name of the datetime column.

    Returns:
        Dict with per-metric TIHR, simultaneous TIHR, and a breakdown DataFrame.
    """
    thresholds = {**DEFAULT_RANGES, **(ranges or {})}

    data = df.copy()
    data[timestamp_col] = pd.to_datetime(data[timestamp_col])

    # narrow to the requested window if one was given
    if start:
        data = data[data[timestamp_col] >= pd.to_datetime(start)]
    if end:
        data = data[data[timestamp_col] <= pd.to_datetime(end)]

    data = data.sort_values(timestamp_col).reset_index(drop=True)
    total = len(data)

    if total == 0:
        return {
            "total_readings": 0,
            "period_start": start,
            "period_end": end,
            "per_metric": {},
            "simultaneous_tihr_pct": 0.0,
            "simultaneous_in_range": 0,
        }

    # per-metric in-range flags
    in_range_flags = {}
    per_metric_results = {}

    for metric, (lo, hi) in thresholds.items():
        if metric not in data.columns:
            continue

        flag = (data[metric] >= lo) & (data[metric] <= hi)
        in_range_flags[metric] = flag

        count = int(flag.sum())
        pct = round(count / total * 100, 2)

        per_metric_results[metric] = {
            "healthy_range": f"{lo}-{hi}",
            "in_range_count": count,
            "out_of_range_count": total - count,
            "tihr_pct": pct,
        }

    # simultaneous: a reading only counts if ALL metrics are in range
    if in_range_flags:
        all_in_range = pd.concat(in_range_flags, axis=1).all(axis=1)
    else:
        all_in_range = pd.Series([False] * total)

    sim_count = int(all_in_range.sum())
    sim_pct = round(sim_count / total * 100, 2)

    # keep a per-row breakdown so callers can drill in if they want
    breakdown = data[[timestamp_col]].copy()
    for metric, flag in in_range_flags.items():
        breakdown[f"{metric}_in_range"] = flag
    breakdown["all_in_range"] = all_in_range

    return {
        "total_readings": total,
        "period_start": str(data[timestamp_col].min()),
        "period_end": str(data[timestamp_col].max()),
        "per_metric": per_metric_results,
        "simultaneous_tihr_pct": sim_pct,
        "simultaneous_in_range": sim_count,
        "breakdown": breakdown,
    }


def print_tihr_report(result: dict) -> None:
    """Dump a TIHR result to stdout (handy when running this module by hand)."""
    print(f"\nTIHR  {result['period_start']} -> {result['period_end']}"
          f"  ({result['total_readings']} readings)\n")

    for metric, info in result["per_metric"].items():
        label = metric.replace("_", " ").title()
        print(f"  {label:<22} {info['healthy_range']:<10} "
              f"{info['tihr_pct']:>6.1f}%  ({info['in_range_count']} in range)")

    print(f"\n  all metrics healthy at once: "
          f"{result['simultaneous_tihr_pct']:.1f}% "
          f"({result['simultaneous_in_range']}/{result['total_readings']})")
