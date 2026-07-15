#!/usr/bin/env python3
import argparse
import csv
import os
import re
from collections import defaultdict
from typing import Dict, List, Optional, Sequence, Tuple

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LogNorm


Combo = Tuple[str, str]  # (stokes_combo, comp_combo)
Pair = Tuple[int, int]   # (ant_low, ant_high)


def _parse_float(v: str) -> float:
    try:
        x = float(str(v).strip())
    except Exception:
        return np.nan
    return x


def _scan_from_filename(path: str) -> int:
    name = os.path.basename(path)
    m = re.search(r"scan[_-]?(\d+)", name, flags=re.IGNORECASE)
    return int(m.group(1)) if m else -1


def _discover_scan_csvs(csv_dir: str) -> List[Tuple[int, str]]:
    patt = re.compile(r"^cross_tcorr_scan[_-]?(\d+)\.csv$", flags=re.IGNORECASE)
    out: List[Tuple[int, str]] = []
    for name in os.listdir(csv_dir):
        m = patt.match(name)
        if not m:
            continue
        out.append((int(m.group(1)), os.path.join(csv_dir, name)))
    out.sort(key=lambda x: (x[0], x[1]))
    return out


def _read_tcorr_csv(path: str):
    """
    Returns:
      antennas: sorted list[int]
      combo_map: dict[(stokes,components)][(ant_low,ant_high)] = tcorr
      combos_by_stokes: dict[stokes] -> list[components]
    """
    with open(path, "r", newline="") as f:
        rd = csv.DictReader(f)
        if not rd.fieldnames:
            raise ValueError(f"No header in CSV: {path}")
        names = {c.strip().lower(): c for c in rd.fieldnames}
        for req in ("ant1", "ant2", "stokes", "components", "tcorr"):
            if req not in names:
                raise ValueError(f"Missing required column '{req}' in {path}")

        antennas_set = set()
        combo_map: Dict[Combo, Dict[Pair, float]] = defaultdict(dict)
        combos_by_stokes: Dict[str, set] = defaultdict(set)
        for r in rd:
            a1 = int(float(str(r[names["ant1"]]).strip()))
            a2 = int(float(str(r[names["ant2"]]).strip()))
            st = str(r[names["stokes"]]).strip()
            cp = str(r[names["components"]]).strip()
            tc = _parse_float(r[names["tcorr"]])
            if not np.isfinite(tc) or tc == -1.0:
                continue
            lo, hi = (a1, a2) if a1 <= a2 else (a2, a1)
            antennas_set.add(lo)
            antennas_set.add(hi)
            combo_map[(st, cp)][(lo, hi)] = float(tc)
            combos_by_stokes[st].add(cp)

    antennas = sorted(antennas_set)
    combos_by_stokes_final = {k: sorted(v) for k, v in combos_by_stokes.items()}
    return antennas, combo_map, combos_by_stokes_final


def _combo_mean(combo_map: Dict[Combo, Dict[Pair, float]], combo: Combo) -> float:
    vals = list(combo_map.get(combo, {}).values())
    if len(vals) == 0:
        return -np.inf
    return float(np.nanmean(vals))


def _choose_pair_order(combo_map: Dict[Combo, Dict[Pair, float]], c1: Combo, c2: Combo) -> Tuple[Combo, Combo]:
    """
    Decide which combo goes lower-left triangle and which goes upper-right.
    Higher-mean combo goes lower-left.
    """
    m1 = _combo_mean(combo_map, c1)
    m2 = _combo_mean(combo_map, c2)
    if m1 >= m2:
        return c1, c2
    return c2, c1


def _panel_plan(combos_by_stokes: Dict[str, List[str]]) -> List[Tuple[Combo, Combo]]:
    """
    Build (lower_combo, upper_combo) list of panels.
    Rules:
      - For 1 stokes: 2 panels covering all 4 component combos by pairing
        (re-re, im-im) and (re-im, im-re).
      - For 2 stokes: 4 panels, one per stokes combo, each with (re-re, im-im).
      - Fallback: one panel per stokes combo with first two components available.
    """
    stokes_keys = sorted(combos_by_stokes.keys())
    nst = len(stokes_keys)

    def has(st: str, cp: str) -> bool:
        return cp in combos_by_stokes.get(st, [])

    panels: List[Tuple[Combo, Combo]] = []
    if nst == 1:
        st = stokes_keys[0]
        if has(st, "real-real") and has(st, "imag-imag"):
            panels.append(((st, "real-real"), (st, "imag-imag")))
        if has(st, "real-imag") and has(st, "imag-real"):
            panels.append(((st, "real-imag"), (st, "imag-real")))
        if not panels:
            comps = combos_by_stokes.get(st, [])
            if len(comps) >= 2:
                panels.append(((st, comps[0]), (st, comps[1])))
    elif nst == 4:
        for st in stokes_keys:
            if has(st, "real-real") and has(st, "imag-imag"):
                panels.append(((st, "real-real"), (st, "imag-imag")))
            else:
                comps = combos_by_stokes.get(st, [])
                if len(comps) >= 2:
                    panels.append(((st, comps[0]), (st, comps[1])))
    else:
        for st in stokes_keys:
            comps = combos_by_stokes.get(st, [])
            if len(comps) >= 2:
                panels.append(((st, comps[0]), (st, comps[1])))
    return panels


def _short_comp_label(comp: str) -> str:
    c = str(comp).strip().lower()
    c = c.replace("real", "re").replace("imag", "im")
    return c


def _compact_pair_label(combo: Combo) -> str:
    """
    Convert combo like:
      stokes='0-0', components='imag-imag'
    into:
      '0-im : 0-im'
    """
    st = str(combo[0]).split("-")
    cp = _short_comp_label(str(combo[1])).split("-")
    if len(st) == 2 and len(cp) == 2:
        return f"{st[0]}-{cp[0]} : {st[1]}-{cp[1]}"
    return f"{combo[0]} | {_short_comp_label(combo[1])}"


def _build_panel_matrix(
    antennas: Sequence[int],
    combo_map: Dict[Combo, Dict[Pair, float]],
    lower_combo: Combo,
    upper_combo: Combo,
) -> np.ndarray:
    nant = len(antennas)
    idx = {a: i for i, a in enumerate(antennas)}
    mat = np.full((nant, nant), np.nan, dtype=float)
    low_map = combo_map.get(lower_combo, {})
    up_map = combo_map.get(upper_combo, {})

    for i, ai in enumerate(antennas):
        for j, aj in enumerate(antennas):
            if i == j:
                # Keep self-correlations unplotted (white diagonal).
                continue
            lo, hi = (ai, aj) if ai <= aj else (aj, ai)
            if i >= j:
                if (lo, hi) in low_map:
                    mat[i, j] = low_map[(lo, hi)]
            else:
                if (lo, hi) in up_map:
                    mat[i, j] = up_map[(lo, hi)]
    return mat


def _antenna_score_order(
    antennas: Sequence[int],
    combo_map: Dict[Combo, Dict[Pair, float]],
    panels: Sequence[Tuple[Combo, Combo]],
) -> List[int]:
    """
    Order antennas by mean tcorr participation across all panel combos (high to low).
    """
    vals_by_ant: Dict[int, List[float]] = {a: [] for a in antennas}
    for c_low, c_up in panels:
        for cmap in (combo_map.get(c_low, {}), combo_map.get(c_up, {})):
            for (a1, a2), v in cmap.items():
                if np.isfinite(v):
                    vals_by_ant.setdefault(a1, []).append(v)
                    vals_by_ant.setdefault(a2, []).append(v)
    scores = []
    for a in antennas:
        vals = vals_by_ant.get(a, [])
        sc = float(np.nanmean(vals)) if len(vals) > 0 else -np.inf
        scores.append((sc, a))
    scores.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [a for _, a in scores]


def plot_tcorr_colormap_one_scan(
    input_csv: str,
    output_plot_file: str,
    output_matrix_csv: Optional[str] = None,
    cmap_name: str = "viridis",
    date_text: str = "",
) -> None:
    antennas, combo_map, combos_by_stokes = _read_tcorr_csv(input_csv)
    if len(antennas) == 0:
        raise ValueError(f"No valid tcorr rows (excluding -1/NaN) in {input_csv}")

    panels_raw = _panel_plan(combos_by_stokes)
    if len(panels_raw) == 0:
        raise ValueError(f"Could not infer panel combinations from {input_csv}")

    # Choose lower/upper order by higher mean value.
    panels = [_choose_pair_order(combo_map, a, b) for a, b in panels_raw]
    ants_ord = sorted(antennas)

    mats = []
    for low, up in panels:
        m = _build_panel_matrix(ants_ord, combo_map, low, up)
        mats.append((low, up, m))

    # Shared color scale across all panels
    all_vals = np.concatenate([m[np.isfinite(m)] for _, _, m in mats if np.any(np.isfinite(m))])
    if all_vals.size == 0:
        raise ValueError(f"No finite tcorr values to plot in {input_csv}")
    pos_vals = all_vals[all_vals > 0]
    use_lognorm = pos_vals.size > 0
    if use_lognorm:
        vmin, vmax = float(np.nanmin(pos_vals)), float(np.nanmax(pos_vals))
        if vmin == vmax:
            vmax = vmin * (1.0 + 1e-6)
        norm = LogNorm(vmin=vmin, vmax=vmax)
    else:
        vmin, vmax = float(np.nanmin(all_vals)), float(np.nanmax(all_vals))
        if vmin == vmax:
            vmax = vmin + 1e-6
        norm = None

    npanel = len(mats)
    ncols = 2 if npanel > 1 else 1
    nrows = int(np.ceil(npanel / ncols))
    fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(5.8 * ncols + 1.2, 5.0 * nrows))
    if not isinstance(axes, np.ndarray):
        axes = np.array([axes])
    axes = axes.ravel()
    cmap = plt.get_cmap(cmap_name).copy()
    cmap.set_bad("white")

    for i, (low, up, mat) in enumerate(mats):
        ax = axes[i]
        mplot = np.where(mat > 0, mat, np.nan) if use_lognorm else mat
        im = ax.imshow(
            mplot,
            origin="lower",
            cmap=cmap,
            norm=norm,
            vmin=None if norm is not None else vmin,
            vmax=None if norm is not None else vmax,
            interpolation="nearest",
            aspect="equal",
            alpha=0.65,
        )
        ticks = np.arange(len(ants_ord))
        labels = [str(a) for a in ants_ord]
        ax.set_xticks(ticks)
        ax.set_yticks(ticks)
        ax.set_xticklabels(labels, rotation=90, fontsize=14)
        ax.set_yticklabels(labels, fontsize=14)
        ax.tick_params(
            axis="both",
            labelsize=14,
            top=True,
            bottom=True,
            left=True,
            right=True,
            labeltop=True,
            labelbottom=True,
            labelleft=True,
            labelright=True,
        )
        # Dashed guide grid at every antenna boundary.
        every = np.arange(0, len(ants_ord), 1)
        ax.set_xticks(every - 0.5, minor=True)
        ax.set_yticks(every - 0.5, minor=True)
        ax.grid(which="minor", linestyle="--", linewidth=1.5, color="black", alpha=0.35)
        # In-panel compact labels:
        # With origin='lower', matrix i>=j appears in the top-left triangle,
        # and i<j appears in the bottom-right triangle.
        ax.text(
            0.02,
            0.98,
            _compact_pair_label(low),
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=14,
            color="black",
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.65, pad=1.5),
        )
        ax.text(
            0.98,
            0.02,
            _compact_pair_label(up),
            transform=ax.transAxes,
            ha="right",
            va="bottom",
            fontsize=14,
            color="black",
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.65, pad=1.5),
        )

    for j in range(npanel, len(axes)):
        axes[j].axis("off")

    sc = _scan_from_filename(input_csv)
    full_title = f"Cross tcorr Colormap | scan {sc if sc >= 0 else '?'}"
    if str(date_text).strip():
        full_title += f" | {str(date_text).strip()}"
    fig.suptitle(full_title, fontsize=14)
    fig.supylabel("Antenna", fontsize=16, fontweight="bold")
    fig.supxlabel("Antenna", fontsize=16, fontweight="bold")
    fig.subplots_adjust(wspace=0.0, hspace=0.08)
    fig.tight_layout(pad=0.2, rect=[0.02, 0.02, 0.98, 0.95])
    fig.savefig(output_plot_file, dpi=150, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)

    # Optional CSV export.
    if output_matrix_csv is not None:
        with open(output_matrix_csv, "w", newline="") as f:
            wr = csv.writer(f)
            wr.writerow(["scan", "panel", "triangle", "stokes", "components", "ant_row", "ant_col", "tcorr"])
            for pidx, (low, up, mat) in enumerate(mats):
                for i, ai in enumerate(ants_ord):
                    for j, aj in enumerate(ants_ord):
                        v = mat[i, j]
                        if not np.isfinite(v):
                            continue
                        if i >= j:
                            tri = "LL"
                            st, cp = low
                        else:
                            tri = "UR"
                            st, cp = up
                        wr.writerow([
                            sc if sc >= 0 else "",
                            pidx,
                            tri,
                            st,
                            cp,
                            ai,
                            aj,
                            f"{float(v):.6g}",
                        ])


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Plot tcorr colormap panels from cross_tcorr_scan#.csv. "
            "Rows with tcorr=-1 are ignored."
        )
    )
    p.add_argument("--input-csv-file", default=None, help="Single input CSV file")
    p.add_argument("--input-csv-dir", default=None, help="Directory with cross_tcorr_scan#.csv files")
    p.add_argument("--output-plot-file", default=None, help="Single output plot file (.png)")
    p.add_argument("--output-plot-dir", default=None, help="Output plot directory for batch mode")
    p.add_argument("--output-csv-dir", default=None, help="Output matrix CSV directory for batch mode")
    p.add_argument("--write-csv", action="store_true", default=False, help="Enable writing matrix CSV outputs")
    p.add_argument("--date", default="", help="Optional date string to append in title")
    p.add_argument("--cmap", default="viridis", help="Matplotlib colormap")
    return p


def main() -> None:
    args = build_parser().parse_args()

    if args.input_csv_dir is not None:
        in_dir = args.input_csv_dir
        if not os.path.isdir(in_dir):
            raise NotADirectoryError(f"Not a directory: {in_dir}")
        files = _discover_scan_csvs(in_dir)
        if not files:
            raise FileNotFoundError(f"No cross_tcorr_scan#.csv files in {in_dir}")

        out_plot_dir = args.output_plot_dir if args.output_plot_dir else in_dir
        os.makedirs(out_plot_dir, exist_ok=True)
        out_csv_dir = args.output_csv_dir if args.output_csv_dir else out_plot_dir
        if args.write_csv:
            os.makedirs(out_csv_dir, exist_ok=True)

        for sc, in_csv in files:
            out_plot = os.path.join(out_plot_dir, f"cross_tcorr_colormap_scan{sc}.png")
            out_csv = os.path.join(out_csv_dir, f"cross_tcorr_colormap_scan{sc}.csv") if args.write_csv else None
            print(f"Processing scan {sc}: {in_csv}")
            plot_tcorr_colormap_one_scan(
                input_csv=in_csv,
                output_plot_file=out_plot,
                output_matrix_csv=out_csv,
                cmap_name=args.cmap,
                date_text=args.date,
            )
            print(f"Wrote plot: {out_plot}")
            if out_csv is not None:
                print(f"Wrote csv:  {out_csv}")
        return

    # Single-file mode
    if args.input_csv_file is None:
        raise ValueError("Provide --input-csv-file (single mode) or --input-csv-dir (batch mode).")
    if args.output_plot_file is None:
        raise ValueError("Provide --output-plot-file in single-file mode.")
    in_csv = args.input_csv_file
    out_plot = args.output_plot_file
    out_csv_dir = args.output_csv_dir if args.output_csv_dir else (os.path.dirname(out_plot) or ".")
    os.makedirs(os.path.dirname(out_plot) or ".", exist_ok=True)
    if args.write_csv:
        os.makedirs(out_csv_dir, exist_ok=True)
    sc = _scan_from_filename(in_csv)
    out_csv = os.path.join(out_csv_dir, f"cross_tcorr_colormap_scan{sc if sc >= 0 else 0}.csv") if args.write_csv else None
    plot_tcorr_colormap_one_scan(
        input_csv=in_csv,
        output_plot_file=out_plot,
        output_matrix_csv=out_csv,
        cmap_name=args.cmap,
        date_text=args.date,
    )
    print(f"Wrote plot: {out_plot}")
    if out_csv is not None:
        print(f"Wrote csv:  {out_csv}")


if __name__ == "__main__":
    main()
