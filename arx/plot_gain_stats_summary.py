#!/usr/bin/env python3
import argparse
import csv
import math
import os
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np


METRIC_SPECS = [
    ("std_mean", "std_std", "STD", "#1f77b4", "o", -0.24),
    ("skew_mean", "skew_std", "SKEW", "#2ca02c", "s", 0.00),
    ("kurt_mean", "kurt_std", "KURT", "#d62728", "o", 0.24),
]
FS = 14


def _parse_float(x: str) -> float:
    if x is None:
        return np.nan
    t = str(x).strip()
    if t == "":
        return np.nan
    try:
        v = float(t)
    except ValueError:
        return np.nan
    if math.isnan(v):
        return np.nan
    return v


def _scan_sort_key(scan: str):
    t = str(scan).strip()
    try:
        return (0, float(t))
    except ValueError:
        return (1, t)


def read_summary_csv(path: str):
    with open(path, "r", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("Input CSV has no header.")

        fieldnames = {c.strip().lower(): c for c in reader.fieldnames}
        required = ["scan", "stokes", "component"]
        for mean_col, err_col, _, _, _, _ in METRIC_SPECS:
            required.extend([mean_col, err_col])
        missing = [c for c in required if c not in fieldnames]
        if missing:
            raise ValueError(f"Missing required columns: {', '.join(missing)}")

        rows = []
        for r in reader:
            row = {
                "scan": str(r[fieldnames["scan"]]).strip(),
                "stokes": str(r[fieldnames["stokes"]]).strip(),
                "component": str(r[fieldnames["component"]]).strip(),
            }
            for mean_col, err_col, _, _, _, _ in METRIC_SPECS:
                row[mean_col] = _parse_float(r[fieldnames[mean_col]])
                row[err_col] = _parse_float(r[fieldnames[err_col]])
            rows.append(row)

    if not rows:
        raise ValueError("Input CSV has no data rows.")
    return rows


def _component_label(comp: str) -> str:
    c = str(comp).strip().lower()
    if c in {"0", "real"}:
        return "real"
    if c in {"1", "imag", "imaginary"}:
        return "imag"
    return str(comp)


def _non_outlier_mask(values: np.ndarray) -> np.ndarray:
    """IQR-based outlier mask; keeps all values if spread is degenerate."""
    if values.size == 0:
        return np.zeros(0, dtype=bool)
    q1 = np.nanpercentile(values, 25.0)
    q3 = np.nanpercentile(values, 75.0)
    iqr = q3 - q1
    if not np.isfinite(iqr) or iqr <= 0:
        return np.isfinite(values)
    low = q1 - 1.5 * iqr
    high = q3 + 1.5 * iqr
    return np.isfinite(values) & (values >= low) & (values <= high)


def plot_summary(
    rows: List[Dict[str, object]],
    output_png: str,
    title: str = "",
    date_text: str = "",
) -> None:
    scans = sorted({str(r["scan"]) for r in rows}, key=_scan_sort_key)
    scan_to_x = {s: i for i, s in enumerate(scans)}

    combos = sorted(
        {(str(r["stokes"]), str(r["component"])) for r in rows},
        key=lambda x: (_scan_sort_key(x[0]), _scan_sort_key(x[1])),
    )
    if not combos:
        raise ValueError("No (stokes, component) combinations found.")

    nrows = len(combos)
    fig_h = max(2.4 * nrows, 3.0)
    fig, axes = plt.subplots(nrows=nrows, ncols=1, figsize=(12, fig_h), sharex=True)
    if nrows == 1:
        axes = [axes]

    row_map: Dict[Tuple[str, str], Dict[str, Dict[str, float]]] = {}
    for stokes, comp in combos:
        row_map[(stokes, comp)] = {s: {} for s in scans}

    for r in rows:
        key = (str(r["stokes"]), str(r["component"]))
        scan = str(r["scan"])
        if key not in row_map or scan not in row_map[key]:
            continue
        for mean_col, err_col, _, _, _, _ in METRIC_SPECS:
            row_map[key][scan][mean_col] = float(r[mean_col]) if not np.isnan(r[mean_col]) else np.nan
            row_map[key][scan][err_col] = float(r[err_col]) if not np.isnan(r[err_col]) else np.nan

    # Build one shared y-range from all series, removing outliers before range estimate.
    y_center_all: List[float] = []
    y_low_all: List[float] = []
    y_high_all: List[float] = []
    for combo in combos:
        for mean_col, err_col, _, _, _, _ in METRIC_SPECS:
            yvals = []
            evals = []
            for s in scans:
                d = row_map[combo][s]
                yvals.append(d.get(mean_col, np.nan))
                evals.append(d.get(err_col, np.nan))
            yarr = np.asarray(yvals, dtype=float)
            earr = np.asarray(evals, dtype=float)
            valid = ~np.isnan(yarr)
            if not np.any(valid):
                continue
            yv = yarr[valid]
            ev = earr[valid]
            ev[~np.isfinite(ev)] = 0.0
            ev = np.abs(ev)
            keep = _non_outlier_mask(yv)
            if not np.any(keep):
                continue
            yk = yv[keep]
            ek = ev[keep]
            y_center_all.extend(yk.tolist())
            y_low_all.extend((yk - ek).tolist())
            y_high_all.extend((yk + ek).tolist())

    shared_ylim = None
    if y_low_all and y_high_all:
        y_min = float(np.min(np.asarray(y_low_all)))
        y_max = float(np.max(np.asarray(y_high_all)))
        if np.isfinite(y_min) and np.isfinite(y_max):
            if y_max <= y_min:
                pad = 1.0
            else:
                pad = 0.05 * (y_max - y_min)
            shared_ylim = (y_min - pad, y_max + pad)

    for i, (ax, combo) in enumerate(zip(axes, combos)):
        stokes, comp = combo

        for xi in range(len(scans)):
            shade = "#e6e6e6" if xi % 2 == 0 else "#f7f7f7"
            ax.axvspan(xi - 0.5, xi + 0.5, color=shade, zorder=0)
            ax.axvline(
                xi - 0.5,
                color="black",
                linestyle="--",
                linewidth=3.0,
                alpha=0.8,
                zorder=2,
            )
        ax.axvline(
            len(scans) - 0.5,
            color="black",
            linestyle="--",
            linewidth=3.0,
            alpha=0.8,
            zorder=2,
        )

        for mean_col, err_col, label, color, marker, offset in METRIC_SPECS:
            xvals = []
            yvals = []
            evals = []
            for s in scans:
                d = row_map[combo][s]
                y = d.get(mean_col, np.nan)
                e = d.get(err_col, np.nan)
                xvals.append(scan_to_x[s] + offset)
                yvals.append(y)
                evals.append(e if not np.isnan(e) else 0.0)

            xarr = np.asarray(xvals, dtype=float)
            yarr = np.asarray(yvals, dtype=float)
            earr = np.asarray(evals, dtype=float)
            valid = ~np.isnan(yarr)
            if not np.any(valid):
                continue

            mfc = "none" if label == "KURT" else color
            ax.errorbar(
                xarr[valid],
                yarr[valid],
                yerr=earr[valid],
                fmt=marker,
                color=color,
                ecolor=color,
                linewidth=2.0,
                elinewidth=2.0,
                capsize=3,
                markersize=10,
                markerfacecolor=mfc,
                markeredgewidth=2.0,
                linestyle="none",
                label=label,
                zorder=3,
            )

        comp_label = _component_label(comp)
        ax.set_ylabel(f"S{stokes}, {comp_label}", fontsize=FS)
        ax.grid(axis="y", linestyle=":", alpha=0.35, zorder=1)
        if shared_ylim is not None:
            ax.set_ylim(shared_ylim)
        for spine in ax.spines.values():
            spine.set_linewidth(3.0)
        ax.tick_params(axis="both", labelsize=FS, width=3.0)
        ax.tick_params(axis="y", right=True, labelright=True)
        if i == 0:
            leg = ax.legend(loc="best", fontsize=FS, frameon=True)
            leg.get_frame().set_linewidth(3.0)

    axes[-1].set_xticks(np.arange(len(scans)))
    axes[-1].set_xticklabels(scans, rotation=0, fontsize=FS)
    axes[-1].set_xlabel("Scan", fontsize=FS)
    # Mirror scan tick labels on the top margin.
    secax = axes[0].secondary_xaxis("top")
    secax.set_xticks(np.arange(len(scans)))
    secax.set_xticklabels(scans, fontsize=FS)
    secax.set_xlabel("Scan", fontsize=FS)
    secax.tick_params(axis="x", labelsize=FS, width=3.0)
    for spine in secax.spines.values():
        spine.set_linewidth(3.0)

    base_title = title.strip() if title.strip() else "Gain Stats Summary vs Scan"
    if date_text.strip():
        full_title = f"{base_title} | {date_text.strip()}"
    else:
        full_title = base_title
    fig.suptitle(full_title, fontsize=FS)

    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(output_png, dpi=150)
    plt.close(fig)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Plot summary CSV with one row per (stokes, component), shared scan axis, "
            "alternate scan shading, and error bars for STD/SKEW/KURT."
        )
    )
    p.add_argument("input_csv", help="Input summary CSV (e.g., gain_stats_summary.csv)")
    p.add_argument(
        "--output",
        default=None,
        help="Output PNG path (default: <input_basename>_plot.png)",
    )
    p.add_argument(
        "--title",
        default="",
        help="Optional plot title",
    )
    p.add_argument(
        "--date",
        default="",
        help="Optional date string to append to the title.",
    )
    return p


def main() -> None:
    args = build_parser().parse_args()
    input_csv = args.input_csv
    if args.output:
        output_png = args.output
    else:
        stem, _ = os.path.splitext(input_csv)
        output_png = f"{stem}_plot.png"

    rows = read_summary_csv(input_csv)
    plot_summary(rows, output_png=output_png, title=args.title, date_text=args.date)
    print(f"Wrote plot: {output_png}")


if __name__ == "__main__":
    main()
