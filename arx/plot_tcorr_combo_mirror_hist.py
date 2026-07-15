#!/usr/bin/env python3
import argparse
import csv
import os
import re
from collections import defaultdict
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np


def _parse_float(v: str) -> float:
    try:
        x = float(str(v).strip())
    except Exception:
        return np.nan
    return x


def _read_tcorr_by_combo(csv_path: str) -> Dict[Tuple[str, str], np.ndarray]:
    """
    Read CSV with at least columns: stokes, components, tcorr.
    Returns dict: (stokes, components) -> np.array(valid_tcorr), excluding -1 and NaN.
    """
    with open(csv_path, "r", newline="") as f:
        rd = csv.DictReader(f)
        if not rd.fieldnames:
            raise ValueError("CSV has no header.")
        names = {k.strip().lower(): k for k in rd.fieldnames}
        for req in ("stokes", "components", "tcorr"):
            if req not in names:
                raise ValueError(f"Missing required column '{req}' in {csv_path}")

        grouped: Dict[Tuple[str, str], List[float]] = defaultdict(list)
        for r in rd:
            st = str(r[names["stokes"]]).strip()
            cp = str(r[names["components"]]).strip()
            tc = _parse_float(r[names["tcorr"]])
            if not np.isfinite(tc):
                continue
            if tc == -1.0:
                continue
            grouped[(st, cp)].append(tc)

    out: Dict[Tuple[str, str], np.ndarray] = {}
    for k, vals in grouped.items():
        if len(vals) == 0:
            continue
        out[k] = np.asarray(vals, dtype=float)
    return out


def _scan_from_filename(path: str) -> int:
    name = os.path.basename(path)
    m = re.search(r"scan[_-]?(\d+)", name, flags=re.IGNORECASE)
    return int(m.group(1)) if m else -1


def _discover_cross_tcorr_csvs(csv_dir: str) -> List[Tuple[int, str]]:
    patt = re.compile(r"^cross_tcorr_scan[_-]?(\d+)\.csv$", flags=re.IGNORECASE)
    out: List[Tuple[int, str]] = []
    for name in os.listdir(csv_dir):
        m = patt.match(name)
        if not m:
            continue
        out.append((int(m.group(1)), os.path.join(csv_dir, name)))
    out.sort(key=lambda x: (x[0], x[1]))
    return out


def plot_mirrored_combo_hist(
    input_csv: str,
    output_png: str,
    bins: int = 40,
    title: str = "",
    date_text: str = "",
    shade_alpha: float = 0.35,
) -> None:
    combo_vals = _read_tcorr_by_combo(input_csv)
    if not combo_vals:
        raise ValueError("No valid tcorr values found after discarding -1/NaN.")

    all_vals = np.concatenate(list(combo_vals.values()))
    tc_min = float(np.nanmin(all_vals))
    tc_max = float(np.nanmax(all_vals))
    if not np.isfinite(tc_min) or not np.isfinite(tc_max):
        raise ValueError("Could not determine tcorr range.")
    if tc_max <= tc_min:
        tc_max = tc_min + 1.0

    # Bin edges start from global min tcorr and end at 100 (requested x span on both sides).
    tc_edge_max = 100.0
    if tc_min >= tc_edge_max:
        tc_min = max(1e-3, tc_edge_max * 0.5)
    edges = np.linspace(tc_min, tc_edge_max, int(max(2, bins)) + 1)
    xcent_pos = 0.5 * (edges[:-1] + edges[1:])

    combos = sorted(combo_vals.keys(), key=lambda x: (x[0], x[1]))
    ncombo = len(combos)
    half = (ncombo + 1) // 2
    left_set = set(combos[half:])
    right_set = set(combos[:half])

    cmap = plt.get_cmap("tab20")
    colors = {c: cmap(i % 20) for i, c in enumerate(combos)}

    fig, ax = plt.subplots(figsize=(10, 8))
    max_count = 1

    for c in combos:
        vals = combo_vals[c]
        # Probability density histogram, ignore out-of-range values above 100.
        vv = vals[(vals >= tc_min) & (vals <= tc_edge_max)]
        hist, _ = np.histogram(vv, bins=edges, density=True)
        max_count = max(max_count, int(np.max(hist)) if hist.size > 0 else 1)
        y = hist.astype(float)
        x = xcent_pos.copy()
        if c in left_set:
            x = -x
        ax.step(x, y, where="mid", lw=2.0, color=colors[c])

    # Central vertical axis
    ax.axvline(0.0, color="black", lw=2.0)
    # Shade +/- (2 * t_corr_min) region about zero.
    band = 2.0 * tc_min
    ax.axvspan(-band, band, color="#d9d9d9", alpha=shade_alpha, zorder=0)
    ax.set_xlim(-100.0, 100.0)
    # Keep density strictly positive for log-y visibility if needed downstream.
    ymax = float(np.nanmax([0.0] + [np.nanmax(np.histogram(combo_vals[c][(combo_vals[c] >= tc_min) & (combo_vals[c] <= tc_edge_max)], bins=edges, density=True)[0]) for c in combos]))
    ax.set_ylim(1e-4, max(1e-3, 1.15 * ymax))
    ax.set_xscale("symlog", linthresh=max(1e-3, tc_min), base=10)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, pos: f"{abs(v):g}"))
    ax.set_xlabel(r"$\tau_{corr}$", fontsize=14)
    ax.set_ylabel("probability density", fontsize=14)
    ax.tick_params(axis="both", labelsize=14)
    ax.grid(axis="y", ls=":", alpha=0.35)

    if title.strip():
        final_title = title.strip()
    else:
        sc = _scan_from_filename(input_csv)
        final_title = rf"Cross $\tau_{{corr}}$ | scan {sc if sc >= 0 else '?'}"
    if date_text.strip():
        final_title = f"{final_title} | {date_text.strip()}"
    ax.set_title(final_title, fontsize=14)

    # Put colored labels as vertical columns inside plot, separately on each side.
    left_list = [c for c in combos if c in left_set]
    right_list = [c for c in combos if c in right_set]
    if left_list:
        for i, c in enumerate(left_list):
            y_pos = 0.95 - (0.9 * i / max(1, len(left_list) - 1 if len(left_list) > 1 else 1))
            ax.text(
                0.03,
                y_pos,
                f"{c[0]}|{c[1]}",
                color=colors[c],
                ha="left",
                va="center",
                transform=ax.transAxes,
                fontsize=14,
            )
    if right_list:
        for i, c in enumerate(right_list):
            y_pos = 0.95 - (0.9 * i / max(1, len(right_list) - 1 if len(right_list) > 1 else 1))
            ax.text(
                0.97,
                y_pos,
                f"{c[0]}|{c[1]}",
                color=colors[c],
                ha="right",
                va="center",
                transform=ax.transAxes,
                fontsize=14,
            )

    fig.tight_layout(rect=[0.04, 0.04, 0.96, 0.96])
    fig.savefig(output_png, dpi=150)
    plt.close(fig)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Plot mirrored tcorr histograms grouped by (stokes, components) from CSV. "
            "tcorr == -1 values are discarded."
        )
    )
    p.add_argument("--input-csv-file", default=None, help="Input CSV from cross_tcorr script")
    p.add_argument(
        "--input-csv-dir",
        default=None,
        help="Directory containing cross_tcorr_scan#.csv files for batch plotting",
    )
    p.add_argument("--output-plot-file", default=None, help="Output PNG path for single-file mode")
    p.add_argument(
        "--output-plot-dir",
        default=None,
        help="Output plot directory for batch mode (default: input csv dir)",
    )
    p.add_argument("--bins", type=int, default=40, help="Number of histogram bins")
    p.add_argument("--title", default="", help="Optional title")
    p.add_argument("--date", default="", help="Optional date string to append to title")
    p.add_argument("--shade-alpha", type=float, default=0.35, help="Alpha for central shaded region")
    return p


def main() -> None:
    args = build_parser().parse_args()
    # Batch mode from directory
    if args.input_csv_dir is not None:
        in_dir = args.input_csv_dir
        if not os.path.isdir(in_dir):
            raise NotADirectoryError(f"Not a directory: {in_dir}")
        files = _discover_cross_tcorr_csvs(in_dir)
        if not files:
            raise FileNotFoundError(f"No files matching cross_tcorr_scan#.csv in {in_dir}")
        out_dir = args.output_plot_dir if args.output_plot_dir else in_dir
        os.makedirs(out_dir, exist_ok=True)
        for sc, in_csv in files:
            out_png = os.path.join(out_dir, f"cross_tcorr_hist_scan{sc}.png")
            plot_mirrored_combo_hist(
                input_csv=in_csv,
                output_png=out_png,
                bins=args.bins,
                title=args.title,
                date_text=args.date,
                shade_alpha=args.shade_alpha,
            )
            print(f"Wrote plot: {out_png}")
        return

    # Single-file mode
    if args.input_csv_file is None:
        raise ValueError("Provide --input-csv-file for single mode, or --input-csv-dir for batch mode.")
    if args.output_plot_file is None:
        raise ValueError("Provide --output-plot-file in single-file mode.")
    out_dir = os.path.dirname(args.output_plot_file) or "."
    os.makedirs(out_dir, exist_ok=True)
    plot_mirrored_combo_hist(
        input_csv=args.input_csv_file,
        output_png=args.output_plot_file,
        bins=args.bins,
        title=args.title,
        date_text=args.date,
        shade_alpha=args.shade_alpha,
    )
    print(f"Wrote plot: {args.output_plot_file}")


if __name__ == "__main__":
    main()
