#!/usr/bin/env python3
import argparse
import csv
import os
import re
from typing import Dict, List, Optional, Sequence, Tuple

import matplotlib.pyplot as plt
import numpy as np
try:
    from sklearn.gaussian_process import GaussianProcessRegressor
    from sklearn.gaussian_process.kernels import ConstantKernel, RBF, WhiteKernel
    _HAS_SKLEARN = True
except Exception:
    _HAS_SKLEARN = False


def _discover_npz_files(
    csv_dir: str,
    mode: str = "gain",
    bchan: Optional[int] = None,
    echan: Optional[int] = None,
) -> List[Tuple[int, str]]:
    if mode == "gain":
        patterns = [re.compile(r"^gain_s2_colormap_scan[_-]?(\d+)\.npz$", flags=re.IGNORECASE)]
    elif mode == "bandpass":
        if bchan is not None and echan is not None:
            patterns = [
                re.compile(
                    rf"^bpass_{int(bchan)}_{int(echan)}_s2_colormap_scan[_-]?(\d+)\.npz$",
                    flags=re.IGNORECASE,
                )
            ]
        else:
            patterns = [
                re.compile(r"^bpass_s2_colormap_scan[_-]?(\d+)\.npz$", flags=re.IGNORECASE),
                re.compile(r"^bpass_\d+_\d+_s2_colormap_scan[_-]?(\d+)\.npz$", flags=re.IGNORECASE),
            ]
    else:
        raise ValueError(f"Unsupported mode: {mode}")

    found: List[Tuple[int, str]] = []
    for name in os.listdir(csv_dir):
        for patt in patterns:
            m = patt.match(name)
            if m:
                found.append((int(m.group(1)), os.path.join(csv_dir, name)))
                break
    found.sort(key=lambda x: (x[0], x[1]))
    return found


def _mad_nan(x: np.ndarray, axis: int = 1) -> np.ndarray:
    med = np.nanmedian(x, axis=axis, keepdims=True)
    return np.nanmedian(np.abs(x - med), axis=axis)


def _fit_gpr_logx(
    tau: np.ndarray,
    y: np.ndarray,
    yerr: np.ndarray,
    ngrid: int = 400,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    valid = (~np.isnan(y)) & (~np.isnan(yerr)) & (tau > 0)
    x = tau[valid]
    yy = y[valid]
    ee = yerr[valid]
    if x.size < 3:
        return np.array([]), np.array([]), np.array([])
    lx = np.log10(x)
    lx_grid = np.linspace(np.min(lx), np.max(lx), ngrid)

    if _HAS_SKLEARN:
        lx2 = lx.reshape(-1, 1)
        alpha = np.maximum(ee, 1e-4) ** 2
        kernel = ConstantKernel(0.5, (1e-3, 10.0)) * RBF(length_scale=1.0, length_scale_bounds=(1e-3, 10.0)) + WhiteKernel(
            noise_level=1e-3, noise_level_bounds=(1e-8, 1e0)
        )
        gpr = GaussianProcessRegressor(
            kernel=kernel, alpha=alpha, normalize_y=True, n_restarts_optimizer=2, random_state=0
        )
        gpr.fit(lx2, yy)
        y_pred, y_std = gpr.predict(lx_grid.reshape(-1, 1), return_std=True)
    else:
        # Fallback: weighted RBF kernel regression in log10(tau) space.
        # This keeps script usable without scikit-learn.
        w_data = 1.0 / np.maximum(ee, 1e-4) ** 2
        span = max(np.max(lx) - np.min(lx), 1e-6)
        h = max(0.08 * span, 1e-3)
        y_pred = np.full_like(lx_grid, np.nan, dtype=float)
        y_std = np.full_like(lx_grid, np.nan, dtype=float)
        for i, xg in enumerate(lx_grid):
            k = np.exp(-0.5 * ((lx - xg) / h) ** 2)
            w = k * w_data
            ws = np.sum(w)
            if ws <= 0:
                continue
            mu = np.sum(w * yy) / ws
            var = np.sum(w * (yy - mu) ** 2) / ws
            y_pred[i] = mu
            y_std[i] = np.sqrt(max(var, 0.0))

    tau_grid = 10 ** lx_grid
    return tau_grid, y_pred, y_std


def _estimate_tcorr_from_curve(tau_grid: np.ndarray, y_grid: np.ndarray, thr: float) -> float:
    if tau_grid.size == 0:
        return np.nan
    y = y_grid - thr
    if np.all(np.isnan(y)):
        return np.nan
    valid = ~np.isnan(y)
    tau = tau_grid[valid]
    yv = y[valid]
    if tau.size < 2:
        return np.nan
    above = yv >= 0
    idx = np.where(above)[0]
    if idx.size == 0:
        return np.nan
    i = idx[0]
    if i == 0:
        return float(tau[0])
    x0, x1 = tau[i - 1], tau[i]
    y0, y1 = yv[i - 1], yv[i]
    if y1 == y0:
        return float(x1)
    return float(x0 + (x1 - x0) * ((0.0 - y0) / (y1 - y0)))


def _load_s2_npz(npz_path: str):
    z = np.load(npz_path, allow_pickle=True)
    if "s2_data" not in z or "params" not in z:
        raise ValueError(f"{npz_path} missing required keys 's2_data' or 'params'")
    s2_data = z["s2_data"]  # (Nbin+1, n_ant, n_stokes, 2)
    params = z["params"].item() if hasattr(z["params"], "item") else z["params"]
    tau = np.asarray(params.get("tau_common"))
    antenna_list = list(np.asarray(params.get("antenna_list")).tolist())
    stokes_list = list(np.asarray(params.get("stokes_list")).tolist())
    scan = int(params.get("scan")) if params.get("scan") is not None else None
    if s2_data.ndim != 4:
        raise ValueError(f"Unexpected s2_data ndim={s2_data.ndim}, expected 4")
    if tau.size != (s2_data.shape[0] - 1):
        raise ValueError(
            f"tau_common length {tau.size} does not match s2_data bins {s2_data.shape[0]-1}"
        )
    return s2_data, tau, antenna_list, stokes_list, scan


def _format_row_for_csv(row: Dict[str, object]) -> Dict[str, object]:
    out: Dict[str, object] = {}
    for k, v in row.items():
        if isinstance(v, (float, np.floating)):
            if np.isnan(v):
                out[k] = "nan"
            else:
                out[k] = f"{float(v):.2f}"
        else:
            out[k] = v
    return out


def plot_s2_all_antennas_with_median(
    npz_path: str,
    output_plot_path: str,
    output_median_csv_path: str,
    alpha_lines: float = 0.8,
    threshold: float = 0.7,
    date_text: Optional[str] = None,
    mode: str = "gain",
) -> None:
    s2_data, tau, antenna_list, stokes_list, scan = _load_s2_npz(npz_path)
    s2 = s2_data[1:, :, :, :]  # (Nbin, n_ant, n_stokes, 2)
    nbin, n_ant, n_stokes, _ = s2.shape
    if n_stokes == 0:
        raise ValueError("No stokes found in input file.")

    fig, axes = plt.subplots(
        nrows=n_stokes,
        ncols=2,
        figsize=(12, max(3.0, 2.7 * n_stokes)),
        sharex=True,
        sharey=False,
        constrained_layout=True,
    )
    if n_stokes == 1:
        axes = np.array([axes])

    comp_names = ["real", "imag"]
    csv_rows: List[Dict[str, object]] = []

    for s_idx, stokes_val in enumerate(stokes_list):
        for c_idx, comp_name in enumerate(comp_names):
            ax = axes[s_idx, c_idx]
            mat = s2[:, :, s_idx, c_idx]  # (Nbin, n_ant)

            # Plot all antennas as low-alpha lines.
            for a_idx, ant in enumerate(antenna_list):
                y = mat[:, a_idx]
                valid = (~np.isnan(y)) & (tau > 0)
                if np.count_nonzero(valid) == 0:
                    continue
                gray = 0.02 + 0.28 * (a_idx / max(1, n_ant - 1))
                ax.plot(tau[valid], y[valid], color=str(gray), alpha=alpha_lines, lw=3.0)

            # Median and MAD across antennas per tau.
            med = np.nanmedian(mat, axis=1)
            mad = _mad_nan(mat, axis=1)
            n_valid = np.sum(~np.isnan(mat), axis=1).astype(int)
            valid_med = (~np.isnan(med)) & (tau > 0)
            if np.any(valid_med):
                # Black median dashed line.
                ax.plot(tau[valid_med], med[valid_med], color="black", lw=3.0, ls="--")
                # Error bars as MAD (black, lw=2).
                ax.errorbar(
                    tau[valid_med],
                    med[valid_med],
                    yerr=mad[valid_med],
                    fmt="none",
                    ecolor="black",
                    elinewidth=2.0,
                    capsize=4,
                    capthick=2.0,
                )
            tau_gpr, y_gpr, ystd_gpr = _fit_gpr_logx(tau=tau, y=med, yerr=mad, ngrid=500)
            tcorr = _estimate_tcorr_from_curve(tau_gpr, y_gpr, threshold) if tau_gpr.size > 0 else np.nan
            if tau_gpr.size > 0:
                ax.plot(tau_gpr, y_gpr, color="blue", lw=3.0, ls="-")
                ax.fill_between(
                    tau_gpr,
                    y_gpr - ystd_gpr,
                    y_gpr + ystd_gpr,
                    color="#1E90FF",
                    alpha=0.8,
                    linewidth=0,
                )
            ax.axhline(threshold, color="red", ls="--", lw=3.0)
            if np.isfinite(tcorr) and tcorr > 0:
                ax.axvline(tcorr, color="red", ls="-.", lw=3.0)
                # Keep tcorr label horizontal and offset from the vertical line.
                # If the line is near the right side, place text ending just left of the line.
                if tcorr < 120.0:
                    tx = min(tcorr * 1.08, 198.0)
                    ha = "left"
                else:
                    tx = max(tcorr / 1.08, 2.6)
                    ha = "right"
                ax.text(
                    tx,
                    0.215,
                    (
                        rf"$Chan_{{corr}}$={tcorr:.3g}"
                        if mode == "bandpass"
                        else rf"$\tau_{{corr}}$={tcorr:.3g} [sec]"
                    ),
                    color="red",
                    rotation=0,
                    va="bottom",
                    ha=ha,
                    fontsize=14,
                    bbox=dict(facecolor="white", edgecolor="red", alpha=0.8, boxstyle="round,pad=0.2"),
                    clip_on=True,
                )

            # Evaluate GPR at native tau bins for CSV export.
            gpr_mean_at_tau = np.full(nbin, np.nan, dtype=float)
            gpr_std_at_tau = np.full(nbin, np.nan, dtype=float)
            if tau_gpr.size > 0:
                mvalid = tau > 0
                gpr_mean_at_tau[mvalid] = np.interp(tau[mvalid], tau_gpr, y_gpr, left=np.nan, right=np.nan)
                gpr_std_at_tau[mvalid] = np.interp(tau[mvalid], tau_gpr, ystd_gpr, left=np.nan, right=np.nan)

            for i in range(nbin):
                csv_rows.append(
                    {
                        "scan": scan if scan is not None else "",
                        "stokes": stokes_val,
                        "component": comp_name,
                        "tau": float(tau[i]),
                        "median_s2": float(med[i]) if not np.isnan(med[i]) else np.nan,
                        "mad_s2": float(mad[i]) if not np.isnan(mad[i]) else np.nan,
                        "gpr_mean": float(gpr_mean_at_tau[i]) if not np.isnan(gpr_mean_at_tau[i]) else np.nan,
                        "gpr_std": float(gpr_std_at_tau[i]) if not np.isnan(gpr_std_at_tau[i]) else np.nan,
                        "threshold": float(threshold),
                        "tcorr_gpr": float(tcorr) if np.isfinite(tcorr) else np.nan,
                        "n_ant_valid": int(n_valid[i]),
                    }
                )

            ax.set_title(f"Stokes {stokes_val} | {comp_name}", fontsize=12)
            ax.grid(True, ls=":", alpha=0.35)
            ax.axhline(1.0, color="black", ls="--", lw=2.0, zorder=0)
            if mode == "bandpass":
                tau_max = float(np.nanmax(tau)) if np.any(np.isfinite(tau)) else 2.0
                maxchan = max(2.0, 2.0 * tau_max)
                ax.set_xscale("log")
                ax.set_xlim(1.0, maxchan / 2.0)
            else:
                ax.set_xscale("log")
                ax.set_xlim(2.5, 200.0)
            ax.set_ylim(0.2, 1.2)
            if c_idx == 0:
                ax.set_ylabel(r"$s_2(\tau)$", fontsize=14)
            if s_idx == n_stokes - 1:
                ax.set_xlabel("channel" if mode == "bandpass" else r"$\tau$ [sec]", fontsize=14)

    main_title = f"S2 Across Antennas"
    if scan is not None:
        main_title += f" | Scan {scan}"
    if date_text is not None and str(date_text).strip() != "":
        main_title += f" | {str(date_text).strip()}"
    fig.suptitle(main_title, fontsize=13)
    fig.savefig(output_plot_path, dpi=150)
    plt.close(fig)

    # Save median structure function with MAD.
    with open(output_median_csv_path, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "scan",
                "stokes",
                "component",
                "tau",
                "median_s2",
                "mad_s2",
                "gpr_mean",
                "gpr_std",
                "threshold",
                "tcorr_gpr",
                "n_ant_valid",
            ],
        )
        writer.writeheader()
        writer.writerows([_format_row_for_csv(r) for r in csv_rows])


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Read gain/bandpass s2_colormap_scan#.npz, plot all-antenna S2 curves by "
            "stokes/component, overlay median+MAD, and write mode-prefixed s2_mean_scan#.csv."
        )
    )
    p.add_argument("--mode", choices=["gain", "bandpass"], default="gain", help="Input/output mode prefix")
    p.add_argument("--bchan", type=int, default=None, help="Bandpass mode: bchan used in filename pattern")
    p.add_argument("--echan", type=int, default=None, help="Bandpass mode: echan used in filename pattern")
    p.add_argument(
        "--in-csv-dir",
        required=True,
        help="Input directory containing mode-prefixed *_s2_colormap_scan#.npz files",
    )
    p.add_argument("--scan", type=int, default=None, help="If set, process only this scan; else process all scans")
    p.add_argument("--alpha", type=float, default=0.2, help="Alpha for per-antenna lines")
    p.add_argument("--threshold", type=float, default=0.7, help="S2 threshold for tcorr extraction from GPR fit")
    p.add_argument("--date", default=None, help="Optional date string to append in plot title.")
    p.add_argument(
        "--plot-dir",
        default=None,
        help="Output plot directory (default: same as csv_dir)",
    )
    p.add_argument(
        "--out-csv-dir",
        default=None,
        help="Output median CSV directory (default: same as csv_dir)",
    )
    return p


def main() -> None:
    args = build_parser().parse_args()
    csv_dir = args.in_csv_dir
    if not os.path.isdir(csv_dir):
        raise NotADirectoryError(f"Not a directory: {csv_dir}")

    if args.mode == "gain":
        out_prefix = "gain"
    else:
        if args.bchan is not None and args.echan is not None:
            out_prefix = f"bpass_{int(args.bchan)}_{int(args.echan)}"
        else:
            out_prefix = "bpass"
    npz_files = _discover_npz_files(csv_dir, mode=args.mode, bchan=args.bchan, echan=args.echan)
    if args.scan is not None:
        npz_files = [(sc, p) for sc, p in npz_files if sc == args.scan]

    if not npz_files:
        if args.scan is None:
            raise FileNotFoundError(f"No mode-matching s2_colormap_scan#.npz found in {csv_dir}")
        raise FileNotFoundError(f"No mode-matching s2_colormap_scan{args.scan}.npz found in {csv_dir}")

    plot_dir = args.plot_dir if args.plot_dir is not None else csv_dir
    out_csv_dir = args.out_csv_dir if args.out_csv_dir is not None else csv_dir
    os.makedirs(plot_dir, exist_ok=True)
    os.makedirs(out_csv_dir, exist_ok=True)

    for scan, npz_path in npz_files:
        out_plot = os.path.join(plot_dir, f"{out_prefix}_s2_mean_scan{scan}.png")
        out_csv = os.path.join(out_csv_dir, f"{out_prefix}_s2_mean_scan{scan}.csv")
        print(f"Processing scan {scan}: {npz_path}")
        plot_s2_all_antennas_with_median(
            npz_path=npz_path,
            output_plot_path=out_plot,
            output_median_csv_path=out_csv,
            alpha_lines=args.alpha,
            threshold=args.threshold,
            date_text=args.date,
            mode=args.mode,
        )
        print(f"  Wrote plot: {out_plot}")
        print(f"  Wrote CSV:  {out_csv}")


if __name__ == "__main__":
    main()
