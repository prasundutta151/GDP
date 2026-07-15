#!/usr/bin/env python3
import argparse
import concurrent.futures
import csv
import multiprocessing as mp
import os
import platform
import sys
import time
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

try:
    from casatools import table as casatable
except Exception as exc:
    raise RuntimeError("Could not import casatools.table. Run inside CASA/casa6.") from exc

try:
    from sklearn.gaussian_process import GaussianProcessRegressor
    from sklearn.gaussian_process.kernels import ConstantKernel, RBF, WhiteKernel
    _HAS_SKLEARN = True
except Exception:
    _HAS_SKLEARN = False


def compute_structure_function(
    data1: Tuple[np.ndarray, np.ndarray],
    data2: Optional[Tuple[np.ndarray, np.ndarray]] = None,
    tmin: Optional[float] = None,
    tmax: Optional[float] = None,
    nbin: int = 32,
    bintype: str = "log",
    njack: int = 32,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Normalized cross-structure function:
      S2 = <(x(t+tau)-y(t))^2> / (2*sigma^2), sigma^2 = 0.5*(var(x)+var(y)).
    Returns tau_centers, s2, jackknife_err.
    """
    t1, x1 = data1
    t1 = np.asarray(t1, dtype=float)
    x1 = np.asarray(x1, dtype=float)
    if data2 is None:
        t2, x2 = t1, x1
    else:
        t2, x2 = data2
        t2 = np.asarray(t2, dtype=float)
        x2 = np.asarray(x2, dtype=float)

    m1 = np.isfinite(t1) & np.isfinite(x1)
    m2 = np.isfinite(t2) & np.isfinite(x2)
    t1, x1 = t1[m1], x1[m1]
    t2, x2 = t2[m2], x2[m2]
    if t1.size < 2 or t2.size < 2:
        return np.array([]), np.array([]), np.array([])

    o1 = np.argsort(t1)
    o2 = np.argsort(t2)
    t1, x1 = t1[o1], x1[o1]
    t2, x2 = t2[o2], x2[o2]

    if tmin is None:
        d1 = np.diff(t1)
        d2 = np.diff(t2)
        d = np.concatenate([d1[d1 > 0], d2[d2 > 0]])
        tmin = float(np.min(d)) if d.size > 0 else 1.0
    if tmax is None:
        span = max(float(np.max(t1) - np.min(t1)), float(np.max(t2) - np.min(t2)))
        tmax = float(span / 10.0) if span > 0 else float(max(tmin * 2.0, 2.0))
    if tmax <= tmin:
        tmax = float(tmin * 2.0)

    if bintype == "lin":
        edges = np.linspace(tmin, tmax, nbin + 1)
    else:
        tmin = max(float(tmin), 1e-6)
        edges = np.logspace(np.log10(tmin), np.log10(tmax), nbin + 1)
    tau = 0.5 * (edges[:-1] + edges[1:])

    var1 = np.nanvar(x1)
    var2 = np.nanvar(x2)
    sigma2 = 0.5 * (var1 + var2)
    norm = 2.0 * sigma2 if sigma2 > 0 else 1.0

    def _accumulate(tx: np.ndarray, xx: np.ndarray):
        s2_sum = np.zeros(nbin, dtype=float)
        cnt = np.zeros(nbin, dtype=int)
        for i in range(tx.size):
            dt = np.abs(tx[i] - t2)
            mm = (dt >= tmin) & (dt <= tmax)
            if not np.any(mm):
                continue
            dij = (xx[i] - x2[mm]) ** 2
            bid = np.searchsorted(edges, dt[mm], side="right") - 1
            ok = (bid >= 0) & (bid < nbin)
            if np.any(ok):
                np.add.at(s2_sum, bid[ok], dij[ok])
                np.add.at(cnt, bid[ok], 1)
        with np.errstate(invalid="ignore", divide="ignore"):
            s2 = (s2_sum / cnt) / norm
        return s2, cnt

    s2, _ = _accumulate(t1, x1)

    # Jackknife error over t1 folds
    if njack is None or njack < 2:
        err = np.full_like(s2, np.nan, dtype=float)
    else:
        folds = np.array_split(np.arange(t1.size), njack)
        jk = []
        for fold in folds:
            keep = np.ones(t1.size, dtype=bool)
            keep[fold] = False
            if np.count_nonzero(keep) < 2:
                continue
            s2_j, _ = _accumulate(t1[keep], x1[keep])
            jk.append(s2_j)
        if len(jk) < 2:
            err = np.full_like(s2, np.nan, dtype=float)
        else:
            jk = np.asarray(jk, dtype=float)
            err = np.sqrt((jk.shape[0] - 1) * np.nanvar(jk, axis=0, ddof=0))

    return tau, s2, err


def _fit_gpr_or_fallback(tau: np.ndarray, y: np.ndarray, yerr: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    valid = (tau > 0) & np.isfinite(tau) & np.isfinite(y)
    if np.count_nonzero(valid) < 3:
        return np.array([]), np.array([]), np.array([])
    x = tau[valid]
    yy = y[valid]
    ee = np.where(np.isfinite(yerr[valid]), yerr[valid], np.nanmedian(np.abs(yy - np.nanmedian(yy))))
    ee = np.maximum(ee, 1e-4)
    lx = np.log10(x)
    lxg = np.linspace(np.min(lx), np.max(lx), 400)

    if _HAS_SKLEARN:
        kernel = ConstantKernel(0.5, (1e-3, 10.0)) * RBF(1.0, (1e-3, 10.0)) + WhiteKernel(1e-3, (1e-8, 1e0))
        gpr = GaussianProcessRegressor(kernel=kernel, alpha=ee ** 2, normalize_y=True, n_restarts_optimizer=2, random_state=0)
        gpr.fit(lx.reshape(-1, 1), yy)
        ym, ys = gpr.predict(lxg.reshape(-1, 1), return_std=True)
    else:
        # Weighted RBF smoother fallback
        w = 1.0 / (ee ** 2)
        span = max(np.max(lx) - np.min(lx), 1e-6)
        h = max(0.08 * span, 1e-3)
        ym = np.full_like(lxg, np.nan)
        ys = np.full_like(lxg, np.nan)
        for i, xg in enumerate(lxg):
            k = np.exp(-0.5 * ((lx - xg) / h) ** 2)
            ww = k * w
            sw = np.sum(ww)
            if sw <= 0:
                continue
            mu = np.sum(ww * yy) / sw
            var = np.sum(ww * (yy - mu) ** 2) / sw
            ym[i] = mu
            ys[i] = np.sqrt(max(var, 0.0))
    return 10 ** lxg, ym, ys


def _tcorr_from_model(tau: np.ndarray, s2: np.ndarray, thr: float) -> float:
    m = np.isfinite(tau) & np.isfinite(s2)
    if np.count_nonzero(m) < 2:
        return np.nan
    t = tau[m]
    y = s2[m]
    o = np.argsort(t)
    t, y = t[o], y[o]
    tmin = float(np.min(t))
    tmax = float(np.max(t))

    # Rule 1: above threshold from start
    if y[0] >= thr:
        return tmin
    # Rule 2: if S2 is < 1 for any value
    if np.any(y < 1.0):
        return tmax
    # Rule 3: first passage to threshold
    for i in range(y.size - 1):
        y0, y1 = y[i], y[i + 1]
        if (y0 < thr <= y1) or (y0 > thr >= y1):
            x0, x1 = t[i], t[i + 1]
            if y1 == y0:
                return float(x0)
            w = (thr - y0) / (y1 - y0)
            return float(x0 + w * (x1 - x0))
    return tmax


def _get_table_info(input_table: str) -> Tuple[List[int], List[int], str]:
    tb = casatable()
    tb.open(input_table)
    try:
        cols = tb.colnames()
        scans = np.unique(tb.getcol("SCAN_NUMBER")).astype(int).tolist() if "SCAN_NUMBER" in cols else [0]
        ants = np.unique(tb.getcol("ANTENNA1")).astype(int).tolist() if "ANTENNA1" in cols else []
        if "GAIN" in cols:
            dcol = "GAIN"
        elif "CPARAM" in cols:
            dcol = "CPARAM"
        elif "FPARAM" in cols:
            dcol = "FPARAM"
        else:
            raise RuntimeError("No suitable data column among GAIN/CPARAM/FPARAM.")
        return scans, ants, dcol
    finally:
        tb.close()


def _read_scan_series(
    input_table: str,
    scan: int,
    antennas: Sequence[int],
    data_col: str,
    mode: str,
    use_flag: bool,
    bchan: Optional[int] = None,
    echan: Optional[int] = None,
) -> Tuple[
    Dict[int, Dict[int, Dict[str, Tuple[np.ndarray, np.ndarray]]]],
    Dict[int, Dict[int, bool]],
]:
    """
    Return nested dict:
      out[ant][stokes]["real"/"imag"] = (axis, series)
    and all-flag map:
      all_flagged[ant][stokes] = True if all samples are flagged/invalid.
    """
    tb = casatable()
    ant_query = ",".join(str(a) for a in antennas)
    taql = f"SCAN_NUMBER == {int(scan)} AND ANTENNA1 IN [{ant_query}]"
    tb.open(input_table)
    sub = tb.query(taql)
    try:
        ant = sub.getcol("ANTENNA1")
        flg = sub.getcol("FLAG")
        dat = sub.getcol(data_col)
        if dat.ndim != 3:
            raise RuntimeError(f"Expected data shape (npol,nchan,nrow), got {dat.shape}")
        if flg.ndim != 3:
            raise RuntimeError(f"Expected FLAG shape (npol,nchan,nrow), got {flg.shape}")
        if dat.shape != flg.shape:
            if dat.shape[0] != flg.shape[0] or dat.shape[2] != flg.shape[2]:
                raise RuntimeError(f"Data/FLAG incompatible shapes: {dat.shape} vs {flg.shape}")
            nchan_common = min(int(dat.shape[1]), int(flg.shape[1]))
            if nchan_common <= 0:
                raise RuntimeError(f"No common channels between data and FLAG: {dat.shape} vs {flg.shape}")
            print(
                f"Warning: channel mismatch data={dat.shape[1]} vs flag={flg.shape[1]}; "
                f"using first {nchan_common} channels."
            )
            dat = dat[:, :nchan_common, :]
            flg = flg[:, :nchan_common, :]
        npol, nchan, _ = dat.shape
        if mode == "bandpass":
            c0 = 0 if bchan is None else max(0, int(bchan))
            c1 = nchan if echan is None else min(nchan, int(echan))
            if c1 < c0:
                c0, c1 = c1, c0
            if c1 <= c0:
                raise ValueError(
                    f"Invalid bandpass channel range after clipping: bchan={bchan}, echan={echan}, nchan={nchan}"
                )
            dat = dat[:, c0:c1, :]
            flg = flg[:, c0:c1, :]
            nchan = dat.shape[1]
        axis_time = sub.getcol("TIME") if "TIME" in sub.colnames() else np.arange(sub.nrows(), dtype=float)
        out: Dict[int, Dict[int, Dict[str, Tuple[np.ndarray, np.ndarray]]]] = {}
        all_flagged: Dict[int, Dict[int, bool]] = {}
        for a in antennas:
            m = (ant == a)
            if not np.any(m):
                continue
            out[a] = {}
            all_flagged[a] = {}
            d = dat[:, :, m]
            f = flg[:, :, m]
            if use_flag:
                d = np.where(f, np.nan + 1j * np.nan, d)
            for p in range(npol):
                arr = d[p, :, :]  # (nchan, nrow_for_ant)
                all_flagged[a][p] = bool(np.all(~np.isfinite(arr.real) & ~np.isfinite(arr.imag)))
                if mode == "bandpass":
                    # Axis is channel, average over rows/time
                    axis = np.arange(nchan, dtype=float)
                    rr = np.nanmean(arr.real, axis=1)
                    ii = np.nanmean(arr.imag, axis=1)
                else:
                    # Axis is time, average over channels
                    axis = np.asarray(axis_time[m], dtype=float)
                    rr = np.nanmean(arr.real, axis=0)
                    ii = np.nanmean(arr.imag, axis=0)
                out[a][p] = {
                    "real": (axis, rr),
                    "imag": (axis, ii),
                }
        return out, all_flagged
    finally:
        sub.close()
        tb.close()


def _process_one_scan(
    sc: int,
    input_table: str,
    ants: Sequence[int],
    data_col: str,
    mode: str,
    use_flag: bool,
    nbin: int,
    bintype: str,
    njack: int,
    threshold: float,
    bchan: Optional[int],
    echan: Optional[int],
    out_dir: str,
    stem: str,
    ext: str,
) -> Tuple[int, int, float, str]:
    print(f"Processing scan {sc} (no cross-scan correlation) ...")
    scan_t0 = time.perf_counter()
    series, all_flagged = _read_scan_series(
        input_table=input_table,
        scan=int(sc),
        antennas=ants,
        data_col=data_col,
        mode=mode,
        use_flag=use_flag,
        bchan=bchan,
        echan=echan,
    )
    out_scan_csv = os.path.join(out_dir, f"{stem}_scan{int(sc)}{ext}")
    if len(series) == 0:
        with open(out_scan_csv, "w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["scan", "ant1", "ant2", "stokes", "components", "threshold", "tcorr"],
            )
            writer.writeheader()
        return int(sc), 0, time.perf_counter() - scan_t0, out_scan_csv

    scan_rows: List[Dict[str, object]] = []
    stokes_all = sorted(set(k for a in series.values() for k in a.keys()))
    comps = ["real", "imag"]

    for i1, a1 in enumerate(ants):
        if a1 not in series:
            continue
        ant1_t0 = time.perf_counter()
        for a2 in ants[i1:]:
            if a2 not in series:
                continue
            for s1 in stokes_all:
                for s2 in stokes_all:
                    a1_all_flag = bool(all_flagged.get(a1, {}).get(s1, True))
                    a2_all_flag = bool(all_flagged.get(a2, {}).get(s2, True))
                    for c1 in comps:
                        for c2 in comps:
                            t0 = time.perf_counter()
                            if a1_all_flag or a2_all_flag or (s1 not in series[a1]) or (s2 not in series[a2]):
                                tc = -1.0
                            else:
                                x_axis, x_val = series[a1][s1][c1]
                                y_axis, y_val = series[a2][s2][c2]
                                tau, s2v, err = compute_structure_function(
                                    (x_axis, x_val),
                                    data2=(y_axis, y_val),
                                    tmin=None,
                                    tmax=None,
                                    nbin=nbin,
                                    bintype=bintype,
                                    njack=njack,
                                )
                                if tau.size == 0:
                                    tc = np.nan
                                else:
                                    tg, yg, _ = _fit_gpr_or_fallback(tau, s2v, err)
                                    if tg.size == 0:
                                        tc = np.nan
                                    else:
                                        tc = _tcorr_from_model(tg, yg, threshold)
                            dt = time.perf_counter() - t0
                            c1s = "re" if c1 == "real" else "im"
                            c2s = "re" if c2 == "real" else "im"
                            print(
                                f"scan::ant:stokes:comp:  {sc}: [{a1}, {s1}, {c1s}]: "
                                f"[{a2}, {s2}, {c2s}] [{dt:.2f} sec]"
                            )
                            scan_rows.append(
                                {
                                    "scan": int(sc),
                                    "ant1": int(a1),
                                    "ant2": int(a2),
                                    "stokes": f"{int(s1)}-{int(s2)}",
                                    "components": f"{c1}-{c2}",
                                    "threshold": float(threshold),
                                    "tcorr": float(tc) if np.isfinite(tc) else np.nan,
                                }
                            )
        ant1_dt = time.perf_counter() - ant1_t0
        print(f"scan:ant1:done:  [{sc}, {a1}] [{ant1_dt:.2f} sec]")

    with open(out_scan_csv, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["scan", "ant1", "ant2", "stokes", "components", "threshold", "tcorr"],
        )
        writer.writeheader()
        for r in scan_rows:
            out = dict(r)
            if isinstance(out["tcorr"], float):
                out["tcorr"] = "nan" if np.isnan(out["tcorr"]) else f"{out['tcorr']:.6g}"
            out["threshold"] = f"{float(out['threshold']):.6g}"
            writer.writerow(out)

    scan_dt = time.perf_counter() - scan_t0
    return int(sc), len(scan_rows), scan_dt, out_scan_csv


def compute_all_cross_tcorr(
    input_table: str,
    output_csv: str,
    mode: str = "gain",
    scan: Optional[int] = None,
    use_flag: bool = True,
    threshold: float = 0.7,
    nbin: int = 32,
    bintype: str = "log",
    njack: int = 32,
    jobs: int = 1,
    bchan: Optional[int] = None,
    echan: Optional[int] = None,
) -> None:
    all_t0 = time.perf_counter()
    scans, ants, data_col = _get_table_info(input_table)
    if mode not in {"gain", "bandpass"}:
        raise ValueError("mode must be gain or bandpass")
    if scan is None:
        scan_list = scans
    else:
        if int(scan) not in scans:
            raise ValueError(f"Scan {scan} not found. Available scans: {scans}")
        scan_list = [int(scan)]
    if len(ants) == 0:
        raise ValueError("No antennas found in table.")

    os.makedirs(os.path.dirname(output_csv) or ".", exist_ok=True)
    out_dir = os.path.dirname(output_csv) or "."
    out_base = os.path.basename(output_csv)
    stem, ext = os.path.splitext(out_base)
    if ext == "":
        ext = ".csv"
    total_rows = 0

    if jobs > 1 and len(scan_list) > 1:
        # Prefer fork context in CASA/IPython-like runtimes to avoid '__spec__' spawn issues.
        use_process_pool = True
        ex = None
        try:
            if platform.system() in {"Darwin", "Linux"}:
                ctx = mp.get_context("fork")
                ex = concurrent.futures.ProcessPoolExecutor(max_workers=jobs, mp_context=ctx)
            else:
                ex = concurrent.futures.ProcessPoolExecutor(max_workers=jobs)
        except Exception as exc:
            use_process_pool = False
            print(
                f"Warning: process pool unavailable ({exc}). "
                "Falling back to thread pool for scan-level parallelism."
            )

        if use_process_pool and ex is not None:
            with ex:
                futs = [
                    ex.submit(
                        _process_one_scan,
                        int(sc),
                        input_table,
                        ants,
                        data_col,
                        mode,
                        use_flag,
                        nbin,
                        bintype,
                        njack,
                        threshold,
                        bchan,
                        echan,
                        out_dir,
                        stem,
                        ext,
                    )
                    for sc in scan_list
                ]
                for fut in concurrent.futures.as_completed(futs):
                    sc, nrows, scan_dt, out_scan_csv = fut.result()
                    total_rows += int(nrows)
                    print(f"scan:csv:done:  [{sc}] [{out_scan_csv}] [rows={nrows}]")
                    print(f"scan:done:  [{sc}] [{scan_dt:.2f} sec]")
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as ex_t:
                futs = [
                    ex_t.submit(
                        _process_one_scan,
                        int(sc),
                        input_table,
                        ants,
                        data_col,
                        mode,
                        use_flag,
                        nbin,
                        bintype,
                        njack,
                        threshold,
                        bchan,
                        echan,
                        out_dir,
                        stem,
                        ext,
                    )
                    for sc in scan_list
                ]
                for fut in concurrent.futures.as_completed(futs):
                    sc, nrows, scan_dt, out_scan_csv = fut.result()
                    total_rows += int(nrows)
                    print(f"scan:csv:done:  [{sc}] [{out_scan_csv}] [rows={nrows}]")
                    print(f"scan:done:  [{sc}] [{scan_dt:.2f} sec]")
    else:
        for sc in scan_list:
            sc2, nrows, scan_dt, out_scan_csv = _process_one_scan(
                int(sc),
                input_table,
                ants,
                data_col,
                mode,
                use_flag,
                nbin,
                bintype,
                njack,
                threshold,
                bchan,
                echan,
                out_dir,
                stem,
                ext,
            )
            total_rows += int(nrows)
            print(f"scan:csv:done:  [{sc2}] [{out_scan_csv}] [rows={nrows}]")
            print(f"scan:done:  [{sc2}] [{scan_dt:.2f} sec]")
    print(f"Wrote per-scan CSV files using template: {output_csv}")
    print(f"Total rows across scans: {total_rows}")
    all_dt = time.perf_counter() - all_t0
    print(f"all:done:  [{all_dt:.2f} sec]")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Compute all cross normalized structure-function tcorr values between "
            "(antenna, stokes, real/imag) pairs and write CSV."
        )
    )
    p.add_argument("--input-gain-table", required=True, help="Input gain or bandpass table")
    p.add_argument("--output-csv-file", required=True, help="Output CSV path")
    p.add_argument("--mode", choices=["gain", "bandpass"], default="gain")
    p.add_argument("--scan", type=int, default=None, help="Scan number; if omitted, process all scans")
    p.add_argument(
        "--use-flag",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Apply FLAG mask (default true; pass --no-use-flag to disable)",
    )
    p.add_argument("--threshold", type=float, default=0.7, help="Threshold for tcorr extraction from model")
    p.add_argument("--nbin", type=int, default=32, help="Number of lag bins for S2")
    p.add_argument("--bintype", choices=["log", "lin"], default="log", help="Lag binning")
    p.add_argument("--njack", type=int, default=32, help="Jackknife folds")
    p.add_argument("--jobs", type=int, default=1, help="Number of CPU processes for per-scan parallelism")
    p.add_argument("--bchan", type=int, default=None, help="Bandpass mode: starting channel (inclusive)")
    p.add_argument("--echan", type=int, default=None, help="Bandpass mode: ending channel (exclusive)")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    compute_all_cross_tcorr(
        input_table=args.input_gain_table,
        output_csv=args.output_csv_file,
        mode=args.mode,
        scan=args.scan,
        use_flag=args.use_flag,
        threshold=args.threshold,
        nbin=args.nbin,
        bintype=args.bintype,
        njack=args.njack,
        jobs=max(1, int(args.jobs)),
        bchan=args.bchan,
        echan=args.echan,
    )


if __name__ == "__main__":
    main()
