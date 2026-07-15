#!/usr/bin/env python3
import argparse
import os
from typing import Dict, List, Optional, Sequence, Tuple

import matplotlib.pyplot as plt
import numpy as np

try:
    from casatools import table as casatable
except Exception as exc:
    raise RuntimeError("Could not import casatools.table. Run inside CASA/casa6.") from exc


def compute_structure_function(
    data1,
    data2=None,
    tmin=None,
    tmax=None,
    Nbin=32,
    bintype="log",
    NJack=1,
    output_file=None,
    S2Thr=0.9,
    output_plot_file=None,
    title=None,
):
    """
    Compute the order-2 structure function S2(tau) normalized to 2*sigma^2.

    If only one dataset is given, compute the self-structure function:
        S2(tau) = < [x(t+tau) - x(t)]^2 > / (2*sigma^2)
    If two datasets are given, compute the cross-structure function:
        S2_cross(tau) = < [x(t+tau) - y(t)]^2 > / (2*sigma^2)
    where sigma^2 is the variance of the series; for cross, we use the mean of the variances of x and y.

    Inputs:
    - data1: tuple (time1, values1)
    - data2: optional tuple (time2, values2). If None, self-structure function is computed.
    - tmin, tmax: lag range. Defaults: tmin = min time resolution in data; tmax = max time span / 10.
    - Nbin: number of lag bins (default 32)
    - bintype: 'log' or 'lin' (default 'log')
    - NJack: jackknife resampling count for error; if 1, no error is computed (default 1)
    - output_file: optional path to save columns (tau_center, S2, err, counts). If None, nothing is saved.
    - output_plot_file: optional path to save a plot of S2 vs tau; if None, no plot is saved.
    - title: optional custom title for the plot when output_plot_file is provided.

    Returns:
    - tau_centers (array), S2 (array), err (array or None), counts (array)
    """
    # Unpack inputs and ensure numpy arrays
    t1, x1 = data1
    t1 = np.asarray(t1, dtype=float)
    x1 = np.asarray(x1, dtype=float)

    if data2 is not None:
        t2, x2 = data2
        t2 = np.asarray(t2, dtype=float)
        x2 = np.asarray(x2, dtype=float)
    else:
        t2, x2 = t1, x1

    # Remove non-finite values
    mask1 = np.isfinite(t1) & np.isfinite(x1)
    t1 = t1[mask1]
    x1 = x1[mask1]
    mask2 = np.isfinite(t2) & np.isfinite(x2)
    t2 = t2[mask2]
    x2 = x2[mask2]

    if t1.size == 0 or t2.size == 0:
        raise ValueError("Input data arrays must contain finite values.")

    # Sort by time
    idx1 = np.argsort(t1)
    t1 = t1[idx1]
    x1 = x1[idx1]
    idx2 = np.argsort(t2)
    t2 = t2[idx2]
    x2 = x2[idx2]

    # Determine default tmin and tmax
    if tmin is None:
        # time resolution as min positive difference
        dt1 = np.diff(t1)
        dt1 = dt1[dt1 > 0]
        dt2 = np.diff(t2)
        dt2 = dt2[dt2 > 0]
        dt_candidates = []
        if dt1.size > 0:
            dt_candidates.append(np.min(dt1))
        if dt2.size > 0:
            dt_candidates.append(np.min(dt2))
        if len(dt_candidates) == 0:
            tmin = 0.0
        else:
            tmin = float(np.min(dt_candidates))
    if tmax is None:
        span1 = t1.max() - t1.min()
        span2 = t2.max() - t2.min()
        span = max(span1, span2)
        tmax = float(span / 10.0) if span > 0 else float(span)

    if tmax <= tmin:
        raise ValueError("tmax must be greater than tmin.")

    # Build lag bins
    if bintype.lower() == 'lin':
        edges = np.linspace(tmin, tmax, Nbin + 1)
    else:
        # log bins
        if tmin <= 0:
            raise ValueError("For log binning, tmin must be > 0.")
        edges = np.logspace(np.log10(tmin), np.log10(tmax), Nbin + 1)
    tau_centers = 0.5 * (edges[:-1] + edges[1:])

    # Precompute normalization 2*sigma^2
    var1 = np.nanvar(x1)
    var2 = np.nanvar(x2)
    if data2 is None:
        sigma2 = var1
    else:
        sigma2 = 0.5 * (var1 + var2)
    norm = 2.0 * sigma2 if sigma2 > 0 else 1.0

    # Efficient pairwise computation using two-pointer technique for irregular grids
    # For cross: consider pairs (i, j) with tau = t1[i] - t2[j] in [tmin, tmax]
    # For self: pairs within the same series; we'll treat as cross with same arrays but avoid pairing same index when times align.

    # Prepare accumulators
    s2_sum = np.zeros(Nbin, dtype=float)
    counts = np.zeros(Nbin, dtype=int)

    # Two-pointer over sorted times
    j_start = 0
    for i in range(t1.size):
        ti = t1[i]
        # Move j_start to the first t2 that could satisfy tau >= tmin
        while j_start < t2.size and (ti - t2[j_start]) > tmax:
            j_start += 1
        j = j_start
        # Advance j while tau decreases below -tmax (not used since we take positive tau = |t1 - t2|?).
        # We define tau as positive lag |t1 - t2|.
        # For each i, we'll scan j around where t2 ~ ti - tau.
        # Simpler approach: for each j from 0 to t2.size-1, compute tau = |ti - t2[j]| and bin if within [tmin, tmax].
        # This is O(N^2) worst-case; acceptable for moderate sizes. For large data, a more efficient method would be needed.
        # We'll implement a vectorized approach per i.
        tau = np.abs(ti - t2)
        # Mask within range
        m = (tau >= tmin) & (tau <= tmax)
        if not np.any(m):
            continue
        tau_sel = tau[m]
        # Differences
        diff = x1[i] - x2[m]
        val = diff * diff
        # Bin
        bin_idx = np.searchsorted(edges, tau_sel, side='right') - 1
        # Keep only valid bins
        valid = (bin_idx >= 0) & (bin_idx < Nbin)
        if np.any(valid):
            b = bin_idx[valid]
            # Accumulate sums per bin
            # Use np.add.at for repeated indices
            np.add.at(s2_sum, b, val[valid])
            np.add.at(counts, b, 1)

    # Compute S2 normalized
    with np.errstate(invalid='ignore', divide='ignore'):
        S2 = s2_sum / counts
        S2 = S2 / norm

    # Jackknife error if requested (NJack > 1)
    err = None
    if NJack is not None and NJack > 1:
        # Split t1 indices into NJack folds and recompute S2 leaving out each fold
        n = t1.size
        folds = np.array_split(np.arange(n), NJack)
        JK = []
        for fold in folds:
            # Use complement indices
            keep_mask = np.ones(n, dtype=bool)
            keep_mask[fold] = False
            t1_j = t1[keep_mask]
            x1_j = x1[keep_mask]
            # Recompute sums and counts
            s2_sum_j = np.zeros(Nbin, dtype=float)
            counts_j = np.zeros(Nbin, dtype=int)
            for i in range(t1_j.size):
                ti = t1_j[i]
                tau = np.abs(ti - t2)
                m = (tau >= tmin) & (tau <= tmax)
                if not np.any(m):
                    continue
                tau_sel = tau[m]
                diff = x1_j[i] - x2[m]
                val = diff * diff
                bin_idx = np.searchsorted(edges, tau_sel, side='right') - 1
                valid = (bin_idx >= 0) & (bin_idx < Nbin)
                if np.any(valid):
                    b = bin_idx[valid]
                    np.add.at(s2_sum_j, b, val[valid])
                    np.add.at(counts_j, b, 1)
            with np.errstate(invalid='ignore', divide='ignore'):
                S2_j = (s2_sum_j / counts_j) / norm
            JK.append(S2_j)
        JK = np.array(JK)
        # Jackknife standard error across folds, ignoring NaNs
        err = np.sqrt((NJack - 1) * np.nanvar(JK, axis=0, ddof=0))

    # Local helper function to interpolate NaNs in plot
    def _interp_nan(x, y):
        """Return a copy of y with NaNs linearly interpolated over x; leaves leading/trailing NaNs as-is."""
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        y_out = y.copy()
        m = np.isfinite(y)
        if np.count_nonzero(m) >= 2:
            y_out[~m] = np.interp(x[~m], x[m], y[m])
        return y_out

    # Save to file if requested
    if output_file is not None:
        # Columns: tau_center, S2, err (or nan), counts
        if err is None:
            err_out = np.full_like(S2, np.nan, dtype=float)
        else:
            err_out = err
        out = np.column_stack([tau_centers, S2, err_out, counts])
        header = "tau_center S2_norm err counts"
        np.savetxt(output_file, out, header=header)

    # Save plot if requested
    if output_plot_file is not None:
        fig, ax = plt.subplots(figsize=(5.0, 3.2))
        # Plot original points (with errors if available) without interpolation
        if err is not None:
            ax.errorbar(tau_centers, S2, yerr=err, fmt='o', ms=3, lw=1, capsize=2)
        else:
            ax.plot(tau_centers, S2, 'o', ms=3, lw=1)
        # Draw a smooth line using interpolated values across NaNs
        S2_line = _interp_nan(tau_centers, S2)
        ax.plot(tau_centers, S2_line, '-', lw=2, color='blue')
        ax.axhline(1., color='green', lw=2)
        ax.axhline(S2Thr, color='red', lw=2, linestyle='--')
        ax.set_xlabel(r'$\tau$ [sec]')
        ax.set_ylabel(r'$S_2 / (2\,\sigma^2)$')
        # X axis scale according to bintype; keep Y linear for readable tick formatting
        if bintype.lower() == 'log':
            ax.set_xscale('log')
        import matplotlib.ticker as mticker
        ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.2f'))
        if title is not None:
            if '\n' in title:
                parts = title.split('\n')
                title = '\n'.join(parts[:2])
            ax.set_title(title, fontsize=10)
        ax.grid(True, which='both', ls=':', alpha=0.4)
        fig.tight_layout()
        fig.savefig(output_plot_file, dpi=150)
        plt.close(fig)

    return tau_centers, S2, err, counts


def _get_table_metadata(table_path: str) -> Dict[str, List[int]]:
    tb = casatable()
    tb.open(table_path)
    try:
        cols = tb.colnames()
        out = {"scans": [], "antennas": [], "stokes": []}
        if "SCAN_NUMBER" in cols:
            out["scans"] = np.unique(tb.getcol("SCAN_NUMBER")).astype(int).tolist()
        if "ANTENNA1" in cols:
            out["antennas"] = np.unique(tb.getcol("ANTENNA1")).astype(int).tolist()
        if tb.nrows() > 0:
            gain_col = "GAIN" if "GAIN" in cols else "CPARAM"
            if gain_col in cols:
                out["stokes"] = list(range(int(tb.getcell(gain_col, 0).shape[0])))
        return out
    finally:
        tb.close()


def _read_gain_table(table_path: str, ants: Sequence[int], scan: int, use_flags: bool) -> Dict:
    tb = casatable()
    ant_query = ",".join(str(a) for a in ants)
    taql = f"SCAN_NUMBER == {int(scan)} AND ANTENNA1 IN [{ant_query}]"
    tb.open(table_path)
    sub = tb.query(taql)
    try:
        t = sub.getcol("TIME")
        ant = sub.getcol("ANTENNA1")
        flg = sub.getcol("FLAG")
        cols = sub.colnames()
        gain_col = "CPARAM"
        g = sub.getcol(gain_col)

        out = {"time": np.unique(t)}
        for a in ants:
            m = ant == a
            out[str(a)] = {}
            if not np.any(m):
                continue
            gd = g[:, :, m]
            fd = flg[:, :, m]
            npol = gd.shape[0]
            for p in range(npol):
                arr = gd[p, :, :]
                if use_flags:
                    arr = np.where(fd[p, :, :], np.nan + 1j * np.nan, arr)
                out[str(a)][p] = arr
        return out
    finally:
        sub.close()
        tb.close()


def _read_bandpass_table(
    table_path: str,
    ants: Sequence[int],
    scan: int,
    use_flags: bool,
    bchan: Optional[int],
    echan: Optional[int],
) -> Dict:
    tb = casatable()
    ant_query = ",".join(str(a) for a in ants)
    taql = f"SCAN_NUMBER == {int(scan)} AND ANTENNA1 IN [{ant_query}]"
    tb.open(table_path)
    sub = tb.query(taql)
    try:
        ant = sub.getcol("ANTENNA1")
        flg = sub.getcol("FLAG")
        cols = sub.colnames()
        gain_col = "CPARAM"
        g = sub.getcol(gain_col)
        nchan = int(g.shape[1])

        start = 0 if bchan is None else max(0, int(bchan))
        end_inclusive = (nchan - 1) if echan is None else min(nchan - 1, int(echan))
        if end_inclusive < start:
            start, end_inclusive = end_inclusive, start
        stop = end_inclusive + 1
        chans = np.arange(start, stop)

        out = {"chan": chans}
        for a in ants:
            m = ant == a
            out[str(a)] = {}
            if not np.any(m):
                continue
            gd = g[:, start:stop, m]
            fd = flg[:, start:stop, m]
            npol = gd.shape[0]
            for p in range(npol):
                arr = gd[p, :, :]
                if use_flags:
                    arr = np.where(fd[p, :, :], np.nan + 1j * np.nan, arr)
                out[str(a)][p] = arr
        return out
    finally:
        sub.close()
        tb.close()


def _estimate_min_dt(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 2:
        return 1.0
    d = np.diff(np.sort(x))
    d = d[d > 0]
    return float(np.min(d)) if d.size > 0 else 1.0


def _tau_at_threshold(tau: np.ndarray, s2: np.ndarray, thr: float, min_dt: float) -> float:
    m = np.isfinite(tau) & np.isfinite(s2)
    if np.count_nonzero(m) < 2:
        return np.nan
    tau = np.asarray(tau[m], dtype=float)
    s2 = np.asarray(s2[m], dtype=float)
    o = np.argsort(tau)
    tau, s2 = tau[o], s2[o]

    min_tau = float(np.nanmin(tau))
    max_tau = float(np.nanmax(tau))

    above_mask = s2 > thr
    n_above = int(np.count_nonzero(above_mask))
    n_total = int(s2.size)

    # Same rules as Seasor_5.py
    if n_above <= 1:
        tc = max_tau
    elif n_above >= n_total - 1:
        tc = min_tau
    else:
        diff = s2 - thr
        sign = np.sign(diff)
        cross = sign[:-1] * sign[1:] <= 0
        idxs = np.where(cross)[0]
        if idxs.size == 0:
            frac_above = n_above / max(n_total, 1)
            tc = min_tau if frac_above > 0.5 else max_tau
        else:
            i = int(idxs[0])
            x0, x1 = tau[i], tau[i + 1]
            y0, y1 = s2[i], s2[i + 1]
            if not (np.isfinite(x0) and np.isfinite(x1) and np.isfinite(y0) and np.isfinite(y1)):
                return np.nan
            if x1 == x0 or y1 == y0:
                above_idx = np.where(s2 > thr)[0]
                tc = tau[int(above_idx[0])] if above_idx.size > 0 else max_tau
            else:
                w = (thr - y0) / (y1 - y0)
                tc = x0 + w * (x1 - x0)

    # Keep requested clipping rule from current tool contract.
    if tc < min_tau:
        tc = min_dt
    elif tc > max_tau:
        tc = max_tau
    return float(tc)


def compute_tcorr_matrices_and_plot(
    input_table,
    target_scan=None,
    requested_ants=None,
    S2Thr=0.75,
    Nbin=32,
    bintype="log",
    use_flag=True,
    UseFlags=True,
    output_plot_file=None,
    output_fits_file=None,
    mode="bandpass",
    bchan=0,
    echan=None,
):
    """
    Standalone tcorr computation for gain/bandpass tables.
    Matrix definitions follow Seasor_5.py style:
      - M00: stokes0 re/re (lower), stokes0 im/im (upper)
      - M11: stokes1 re/re (lower), stokes1 im/im (upper)
      - M01_same: 0re/1re (lower), 0im/1im (upper)
      - M01_cross: 0im/1re (lower), 0re/1im (upper)
    """
    apply_flags = bool(use_flag) and bool(UseFlags)
    mode = str(mode).lower()
    if mode not in {"gain", "bandpass"}:
        raise ValueError("mode must be 'gain' or 'bandpass'")
    if bintype.lower() not in {"log", "lin"}:
        raise ValueError("bintype must be 'log' or 'lin'")

    meta = _get_table_metadata(input_table)
    stokes_avail = meta.get("stokes", [])
    if 0 not in stokes_avail or 1 not in stokes_avail:
        raise ValueError("Stokes 0 and 1 must be available in the input table.")

    if requested_ants is None or len(requested_ants) == 0:
        ants = sorted(meta["antennas"])
    else:
        ants = sorted(set(int(a) for a in requested_ants))
    if len(ants) == 0:
        raise ValueError("No antennas available/selected.")

    def _load_for_scan(scan_value: int):
        if mode == "bandpass":
            d = _read_bandpass_table(input_table, ants, scan_value, apply_flags, bchan, echan)
            ax = np.asarray(d["chan"], dtype=float)
        else:
            d = _read_gain_table(input_table, ants, scan_value, apply_flags)
            ax = np.asarray(d["time"], dtype=float)
        return d, ax

    scans = sorted(meta["scans"])
    if len(scans) == 0:
        raise ValueError("No scans found in table.")

    if target_scan is None:
        data = None
        axis = None
        chosen = None
        for sc in scans:
            d_try, a_try = _load_for_scan(int(sc))
            print(d_try, a_try)
            if a_try.size >= 2:
                data, axis, chosen = d_try, a_try, int(sc)
                break
        if chosen is None:
            chosen = int(scans[0])
            data, axis = _load_for_scan(chosen)
            print(
                f"Warning: no scan has >=2 samples on analysis axis; using first scan {chosen}. "
                "Output tcorr values may be NaN."
            )
        target_scan = chosen
    else:
        target_scan = int(target_scan)
        data, axis = _load_for_scan(target_scan)
        if axis.size < 2:
            print(
                f"Warning: scan {target_scan} has fewer than 2 samples on analysis axis. "
                "Output tcorr values may be NaN."
            )

    min_dt = _estimate_min_dt(axis)
    vmax_cap = 20.0 * min_dt

    nant = len(ants)
    npts = axis.size
    s0r = np.full((nant, npts), np.nan, dtype=float)
    s0i = np.full((nant, npts), np.nan, dtype=float)
    s1r = np.full((nant, npts), np.nan, dtype=float)
    s1i = np.full((nant, npts), np.nan, dtype=float)

    for i, a in enumerate(ants):
        ad = data.get(str(a), {})
        if 0 in ad:
            arr = ad[0]
            if mode == "bandpass":
                s0r[i, :] = np.nanmean((np.real(arr) - 1.0) * 100.0, axis=1)
                s0i[i, :] = np.nanmean(np.imag(arr) * 100.0, axis=1)
            else:
                s0r[i, :] = np.nanmean((np.real(arr) - 1.0) * 100.0, axis=0)
                s0i[i, :] = np.nanmean(np.imag(arr) * 100.0, axis=0)
        if 1 in ad:
            arr = ad[1]
            if mode == "bandpass":
                s1r[i, :] = np.nanmean((np.real(arr) - 1.0) * 100.0, axis=1)
                s1i[i, :] = np.nanmean(np.imag(arr) * 100.0, axis=1)
            else:
                s1r[i, :] = np.nanmean((np.real(arr) - 1.0) * 100.0, axis=0)
                s1i[i, :] = np.nanmean(np.imag(arr) * 100.0, axis=0)

    # If an antenna has NaNs in any derived series, skip all correlations with it.
    # This leaves full white row/column bars in the plot for that antenna.
    bad_ant = np.zeros(nant, dtype=bool)
    for i in range(nant):
        if (
            np.any(np.isnan(s0r[i, :]))
            or np.any(np.isnan(s0i[i, :]))
            or np.any(np.isnan(s1r[i, :]))
            or np.any(np.isnan(s1i[i, :]))
        ):
            bad_ant[i] = True

    if np.any(bad_ant):
        bad_names = [str(ants[i]) for i in np.where(bad_ant)[0]]
        print(f"Skipping antennas with NaNs (white bars): {', '.join(bad_names)}")

    def tcorr(a: np.ndarray, b: np.ndarray) -> float:
        m = np.isfinite(a) & np.isfinite(b) & np.isfinite(axis)
        if np.count_nonzero(m) < 2:
            return np.nan
        t = axis[m]
        xa = a[m]
        xb = b[m]
        tau, s2, _, _ = compute_structure_function(
            (t, xa),
            data2=(t, xb),
            tmin=None,
            tmax=None,
            Nbin=int(Nbin),
            bintype=bintype,
            NJack=32,
            S2Thr=float(S2Thr),
            output_file=None,
            output_plot_file=None,
        )
        return _tau_at_threshold(tau, s2, float(S2Thr), min_dt)

    M00 = np.full((nant, nant), np.nan, dtype=float)
    M11 = np.full((nant, nant), np.nan, dtype=float)
    M01_same = np.full((nant, nant), np.nan, dtype=float)
    M01_cross = np.full((nant, nant), np.nan, dtype=float)

    # Matrix construction aligned with old/170226/develop_72.py logic,
    # with explicit full i,j coverage and NaN-antenna skipping.
    for i in range(nant):
        for j in range(nant):
            if bad_ant[i] or bad_ant[j]:
                continue
            if i == j:
                M00[i, j] = tcorr(s0r[i], s0r[j])
                M11[i, j] = tcorr(s1r[i], s1r[j])
                continue

            if i > j:
                M00[i, j] = tcorr(s0r[i], s0r[j])
                M11[i, j] = tcorr(s1r[i], s1r[j])
                M01_same[i, j] = tcorr(s0r[i], s1r[j])
                M01_cross[i, j] = tcorr(s0i[i], s1r[j])
            else:
                M00[i, j] = tcorr(s0i[i], s0i[j])
                M11[i, j] = tcorr(s1i[i], s1i[j])
                M01_same[i, j] = tcorr(s0i[i], s1i[j])
                M01_cross[i, j] = tcorr(s0r[i], s1i[j])

    vals = np.concatenate(
        [
            M00[np.isfinite(M00)],
            M11[np.isfinite(M11)],
            M01_same[np.isfinite(M01_same)],
            M01_cross[np.isfinite(M01_cross)],
        ]
    )
    if vals.size > 0:
        vmin, vmax = float(np.nanmin(vals)), float(np.nanmax(vals))
    else:
        vmin, vmax = 0.0, 1.0
    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmin == vmax:
        vmin, vmax = 0.0, 1.0
    vmax = min(vmax, vmax_cap)
    if vmin > vmax:
        vmin = vmax / 2.0 if vmax > 0 else 0.0

    if output_plot_file is None:
        tag = "bp" if mode == "bandpass" else "gain"
        output_plot_file = f"tcorr_matrices_{tag}_scan{int(target_scan)}.png"

    fig, axs = plt.subplots(2, 2, figsize=(10, 9), constrained_layout=True)
    cmap = plt.get_cmap("viridis").copy()
    cmap.set_bad("white")
    ticks = np.arange(nant) + 0.5
    labels = [str(a) for a in ants]
    labels_sparse = [lab if (i % 2 == 0) else "" for i, lab in enumerate(labels)]
    X, Y = np.meshgrid(np.arange(nant + 1), np.arange(nant + 1))

    def draw(ax, M, title, show_x=False, show_y=False):
        MM = np.ma.array(M, mask=np.isnan(M))
        im = ax.pcolormesh(X, Y, MM, cmap=cmap, vmin=vmin, vmax=vmax, shading="auto")
        ax.set_title(title, fontsize=10)
        ax.set_xlim(0, nant)
        ax.set_ylim(0, nant)
        ax.set_xticks(ticks)
        ax.set_yticks(ticks)
        ax.set_xticklabels(labels_sparse if show_x else [], rotation=90, fontsize=8)
        ax.set_yticklabels(labels_sparse if show_y else [], fontsize=8)
        return im

    im00 = draw(axs[0, 0], M00, "Stokes0: re/re (lower), im/im (upper)", show_y=True)
    im11 = draw(axs[0, 1], M11, "Stokes1: re/re (lower), im/im (upper)")
    im01s = draw(axs[1, 0], M01_same, "Cross: 0re/1re (lower), 0im/1im (upper)", show_x=True, show_y=True)
    im01c = draw(axs[1, 1], M01_cross, "Cross: 0im/1re (lower), 0re/1im (upper)", show_x=True)

    axs[0, 0].set_ylabel("Antenna")
    axs[1, 0].set_ylabel("Antenna")
    axs[1, 0].set_xlabel("Antenna")
    axs[1, 1].set_xlabel("Antenna")

    fig.colorbar(im00, ax=axs[0, 0], fraction=0.046, pad=0.04)
    fig.colorbar(im11, ax=axs[0, 1], fraction=0.046, pad=0.04)
    fig.colorbar(im01s, ax=axs[1, 0], fraction=0.046, pad=0.04)
    fig.colorbar(im01c, ax=axs[1, 1], fraction=0.046, pad=0.04)
    fig.suptitle(
        f"TCorr Matrices | {os.path.basename(input_table)} | scan={int(target_scan)} | thr={S2Thr}",
        fontsize=13,
    )
    fig.savefig(output_plot_file, dpi=150)
    plt.close(fig)

    if output_fits_file is not None:
        try:
            from astropy.io import fits

            cube = np.stack(
                [
                    np.asarray(M00, dtype=np.float32),
                    np.asarray(M11, dtype=np.float32),
                    np.asarray(M01_same, dtype=np.float32),
                    np.asarray(M01_cross, dtype=np.float32),
                ],
                axis=0,
            )
            hdu = fits.PrimaryHDU(cube)
            hdu.header["EXTNAME"] = "TCORR"
            hdu.header["SCAN"] = int(target_scan)
            hdu.header["S2THR"] = float(S2Thr)
            hdu.header["MODE"] = mode
            hdu.header["CHAN0"] = "M00"
            hdu.header["CHAN1"] = "M11"
            hdu.header["CHAN2"] = "M01_same"
            hdu.header["CHAN3"] = "M01_cross"
            fits.HDUList([hdu]).writeto(output_fits_file, overwrite=True)
        except Exception as exc:
            print(f"Warning: could not write FITS: {exc}")

    return output_plot_file, M00, M11, M01_same, M01_cross


def _parse_ant_list(s: Optional[str]) -> Optional[List[int]]:
    if s is None or str(s).strip() == "":
        return None
    return [int(x.strip()) for x in str(s).split(",") if x.strip() != ""]


def main():
    p = argparse.ArgumentParser(description="Compute tcorr matrices from gain/bandpass table.")
    p.add_argument("input_table", type=str, help="Input gain/bandpass table path")
    p.add_argument("--scan", type=int, default=None, help="Target scan number; default is first scan in table")
    p.add_argument("--requested-ants", type=str, default=None, help="Comma-separated antennas, e.g. 0,1,2")
    p.add_argument("--S2Thr", type=float, default=0.75)
    p.add_argument("--Nbin", type=int, default=32)
    p.add_argument("--bintype", choices=["log", "lin"], default="log")
    p.add_argument("--use-flag", action="store_true", default=True)
    p.add_argument("--no-use-flag", dest="use_flag", action="store_false")
    p.add_argument("--UseFlags", action="store_true", default=True)
    p.add_argument("--no-UseFlags", dest="UseFlags", action="store_false")
    p.add_argument("--output-plot-file", type=str, default=None)
    p.add_argument("--output-fits-file", type=str, default=None)
    p.add_argument("--mode", choices=["bandpass", "gain"], default="bandpass")
    p.add_argument("--bchan", type=int, default=0)
    p.add_argument("--echan", type=int, default=None, help="Inclusive channel end; default is Nchan-1")
    args = p.parse_args()

    ants = _parse_ant_list(args.requested_ants)
    out = compute_tcorr_matrices_and_plot(
        input_table=args.input_table,
        target_scan=args.scan,
        requested_ants=ants,
        S2Thr=args.S2Thr,
        Nbin=args.Nbin,
        bintype=args.bintype,
        use_flag=args.use_flag,
        UseFlags=args.UseFlags,
        output_plot_file=args.output_plot_file,
        output_fits_file=args.output_fits_file,
        mode=args.mode,
        bchan=args.bchan,
        echan=args.echan,
    )
    print(f"Wrote plot: {out[0]}")


if __name__ == "__main__":
    main()
