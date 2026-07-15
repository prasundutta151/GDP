import numpy as np
import matplotlib.pyplot as plt
import os
from scipy.stats import skew, kurtosis, kstest, norm
import argparse # Import argparse
import logging
import warnings
from pathlib import Path
import time
from functools import wraps
import shutil
from casatools import table

# Default paths with testing gain and bandpass tables:
defgainpath = "/Users/prasun/Documents/DiagVis/gains/test/gain_int.g"
defbandpath = "/Users/prasun/Documents/DiagVis/gains/test/bandpass_phase.b"


# In CASA, the 'tb' tool is usually globally available.
# For modular CASA or robust scripts, we import it.
try:
    from casatools import table
    tb = table()
except ImportError:
    # If running inside monolithic CASA, 'tb' is already there
    pass


def timer(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        end = time.perf_counter()
        print(f"{[func.__name__]}: {end - start:.2f} seconds")
        return result
    return wrapper

def invert_cal_flags(cal_table, out_table=None):
    """
    Perform logical NOT on FLAG column of a CASA calibration table
    (bandpass, gain, or flag cal table).

    Parameters
    ----------
    cal_table : str
        Input CASA calibration table.
    out_table : str or None
        If provided, creates a copy and writes inverted flags there.
        If None, modifies table in-place.

    Returns
    -------
    str : path to modified table
    """

    # CASA tool
    try:
        from casatools import table as casatable
    except Exception:
        raise RuntimeError("Run inside CASA (casapy or casa6).")

    if not os.path.isdir(cal_table):
        raise FileNotFoundError(f"Table not found: {cal_table}")

    # If output table requested → copy first
    if out_table is not None:
        if os.path.exists(out_table):
            raise FileExistsError(f"Output table already exists: {out_table}")
        shutil.copytree(cal_table, out_table)
        target = out_table
    else:
        target = cal_table

    tb = casatable()
    tb.open(target, nomodify=False)

    if "FLAG" not in tb.colnames():
        tb.close()
        raise RuntimeError("No FLAG column found in this table.")

    flags = tb.getcol("FLAG")

    if flags.dtype != np.bool_:
        tb.close()
        raise RuntimeError("FLAG column is not boolean.")

    # Logical NOT
    inverted_flags = np.logical_not(flags)

    tb.putcol("FLAG", inverted_flags)
    tb.close()
    copy_all_directories(cal_table, target)
    return target

def copy_all_directories(src_path, dst_path):
    """
    Copy all directories inside src_path into dst_path.
    Copies full directory trees.
    """

    if not os.path.isdir(src_path):
        raise ValueError(f"Source path does not exist: {src_path}")

    os.makedirs(dst_path, exist_ok=True)

    for item in os.listdir(src_path):
        src_item = os.path.join(src_path, item)
        dst_item = os.path.join(dst_path, item)

        if os.path.isdir(src_item):
            print(f"Copying directory: {item}")
            shutil.copytree(src_item, dst_item, dirs_exist_ok=True)

    print("Done.")
    
def combine_bandpass_tables(bp_tables, out_table, freq_tol_hz=1.0):
    """
    Combine multiple CASA bandpass calibration tables into one, assuming only channels differ.

    Parameters
    ----------
    bp_tables : list[str]
        List of input bandpass cal tables (paths). Order doesn't matter.
    out_table : str
        Output calibration table path.
    freq_tol_hz : float
        Frequency matching tolerance in Hz. (Used for floating-point safety.)

    Notes
    -----
    - Assumes all tables have identical main-table rows (same TIME/ANTENNA1/SPW/SCAN etc.)
      and only differ in channel axis.
    - Merges CPARAM, FLAG, WEIGHT. If overlaps exist, later tables overwrite earlier ones.
    - If row ordering differs across tables, this function will raise an error.
    """

    # CASA tool import (works in CASA6; CASA5 also usually works)
    try:
        from casatools import table as casatable
    except Exception as e:
        raise RuntimeError("Could not import casatools.table. Run inside CASA (casa/casa6).") from e

    if not bp_tables or len(bp_tables) < 2:
        raise ValueError("Provide at least two bandpass tables in bp_tables.")

    for t in bp_tables:
        if not os.path.isdir(t):
            raise FileNotFoundError(f"Bandpass table not found or not a directory: {t}")

    # Prepare output: copy the first table as template
    template = bp_tables[0]
    if os.path.exists(out_table):
        raise FileExistsError(f"Output table already exists: {out_table}")

    shutil.copytree(template, out_table)

    tb = casatable()

    def _read_main_keys(tabpath):
        """Read minimal columns that define row identity."""
        tb.open(tabpath)
        cols = tb.colnames()
        need = []
        for c in ["TIME", "ANTENNA1", "SPECTRAL_WINDOW_ID", "SCAN_NUMBER", "FIELD_ID", "OBSERVATION_ID"]:
            if c in cols:
                need.append(c)
        keys = {c: tb.getcol(c) for c in need}
        tb.close()
        return keys

    def _assert_same_rows(keys_ref, keys_new, tabname):
        """Ensure row identity and ordering are identical."""
        for k, vref in keys_ref.items():
            vnew = keys_new.get(k, None)
            if vnew is None:
                raise RuntimeError(f"{tabname} missing key column {k} present in template.")
            if vref.shape != vnew.shape:
                raise RuntimeError(f"Row-key shape mismatch for {k}: {vref.shape} vs {vnew.shape} in {tabname}")
            # TIME can be float; compare with tolerance; others exact
            if k == "TIME":
                if not np.allclose(vref, vnew, rtol=0, atol=1e-6):
                    raise RuntimeError(f"Row mismatch in TIME between template and {tabname}.")
            else:
                if not np.array_equal(vref, vnew):
                    raise RuntimeError(f"Row mismatch in {k} between template and {tabname}.")

    # Check rows are identical across all inputs
    keys_ref = _read_main_keys(template)
    for t in bp_tables[1:]:
        _assert_same_rows(keys_ref, _read_main_keys(t), t)

    # Read template main table shapes to size output arrays later
    tb.open(template)
    cols = tb.colnames()
    for required in ["CPARAM", "FLAG"]:
        if required not in cols:
            tb.close()
            raise RuntimeError(f"Template table missing required column: {required}")
    cparam_shape = tb.getcol("CPARAM").shape  # (npol, nchan, nrow)
    npol, _, nrow = cparam_shape
    tb.close()

    # --- Helper: get per-SPW frequency grid from SPECTRAL_WINDOW ---
    def _read_spw_chanfreq(tabpath):
        tb.open(os.path.join(tabpath, "SPECTRAL_WINDOW"))
        chan_freq = tb.getcol("CHAN_FREQ")  # shape (nchan, nspw) OR (1,nchan,nspw) depending CASA version
        num_chan = tb.getcol("NUM_CHAN")
        tb.close()

        # Normalize shapes: prefer (nchan, nspw)
        cf = np.array(chan_freq)
        if cf.ndim == 3:
            # CASA sometimes stores CHAN_FREQ as (1,nchan,nspw)
            cf = cf[0, :, :]
        if cf.ndim == 1:
            # Single spw case stored as (nchan,)
            cf = cf.reshape(-1, 1)

        return cf, np.array(num_chan).astype(int)

    # Build union frequency grids per SPW across all tables
    cf0, num0 = _read_spw_chanfreq(template)
    nspw = cf0.shape[1]

    # collect freqs per spw
    all_freqs = [ [] for _ in range(nspw) ]
    for t in bp_tables:
        cf, _ = _read_spw_chanfreq(t)
        if cf.shape[1] != nspw:
            raise RuntimeError(f"SPW count mismatch: {t} has {cf.shape[1]} spw, template has {nspw}")
        for s in range(nspw):
            all_freqs[s].append(cf[:, s].ravel())

    # union with tolerance: sort and merge close values
    def _union_with_tol(freq_lists, tol):
        x = np.concatenate(freq_lists)
        x = np.sort(x)
        if x.size == 0:
            return x
        merged = [x[0]]
        for f in x[1:]:
            if abs(f - merged[-1]) > tol:
                merged.append(f)
        return np.array(merged)

    full_freq = []
    full_nchan = []
    for s in range(nspw):
        uf = _union_with_tol(all_freqs[s], freq_tol_hz)
        full_freq.append(uf)
        full_nchan.append(len(uf))

    # Rewrite SPECTRAL_WINDOW in output
    # Need CHAN_FREQ as (nchan_max, nspw) with padding if variable nchan across spw
    nchan_max = max(full_nchan) if full_nchan else 0
    chan_freq_out = np.zeros((nchan_max, nspw), dtype=float)

    for s in range(nspw):
        uf = full_freq[s]
        chan_freq_out[:len(uf), s] = uf
        if len(uf) < nchan_max:
            # pad with last value (harmless if NUM_CHAN is set correctly)
            chan_freq_out[len(uf):, s] = uf[-1] if len(uf) else 0.0

    tb.open(os.path.join(out_table, "SPECTRAL_WINDOW"), nomodify=False)
    # Some CASA versions expect (1,nchan,nspw)
    existing = tb.getcol("CHAN_FREQ")
    if np.array(existing).ndim == 3:
        tb.putcol("CHAN_FREQ", chan_freq_out.reshape(1, nchan_max, nspw))
    else:
        tb.putcol("CHAN_FREQ", chan_freq_out)
    tb.putcol("NUM_CHAN", np.array(full_nchan, dtype=int))
    tb.close()

    # Prepare output main columns with full channel axis.
    # We assume one channel axis applies per SPW; in cal tables, CPARAM channel axis corresponds to that SPW row.
    # For safety, we will map per row using SPECTRAL_WINDOW_ID.
    tb.open(template)
    spw_id = tb.getcol("SPECTRAL_WINDOW_ID") if "SPECTRAL_WINDOW_ID" in tb.colnames() else None
    tb.close()
    if spw_id is None:
        raise RuntimeError("Main table missing SPECTRAL_WINDOW_ID; cannot map per-SPW channel grids.")

    # Output arrays sized to maximum union nchan among SPWs (per row we use its SPW's nchan)
    # CASA stores CPARAM with a single nchan axis for the table; for multi-SPW tables it usually equals max NUM_CHAN.
    nchan_out = nchan_max
    c_out = np.zeros((npol, nchan_out, nrow), dtype=np.complex128)
    f_out = np.ones((npol, nchan_out, nrow), dtype=bool)     # start fully flagged
    w_out = None

    # If WEIGHT exists, merge it too
    tb.open(template)
    has_weight = "WEIGHT" in tb.colnames()
    if has_weight:
        w_shape = tb.getcol("WEIGHT").shape
        # Usually (npol, nchan, nrow) or (npol, nrow) depending table
        # We'll normalize to (npol, nchan_out, nrow) if possible
        w_out = np.zeros((npol, nchan_out, nrow), dtype=np.float64)
    tb.close()

    # Fill output by iterating tables; later tables overwrite overlaps
    for t in bp_tables:
        # Read per-spw freqs for this table
        cf, num = _read_spw_chanfreq(t)

        tb.open(t)
        c = tb.getcol("CPARAM")  # (npol, nchan_in, nrow)
        fl = tb.getcol("FLAG")   # same shape
        w = tb.getcol("WEIGHT") if (has_weight and "WEIGHT" in tb.colnames()) else None
        spw = tb.getcol("SPECTRAL_WINDOW_ID")
        tb.close()

        _, nchan_in, nrow_in = c.shape
        if nrow_in != nrow:
            raise RuntimeError(f"Row count mismatch in {t}: {nrow_in} vs template {nrow}")

        # For each spw, build mapping from this table's channel freqs to union freqs
        # Use tolerance match; assumes monotonic freqs
        for s in range(nspw):
            uf = full_freq[s]
            f_in = cf[:num[s], s]  # actual channels for this spw in this table

            # Build index map: for each input channel, find union index
            # Using searchsorted for speed, then check tol
            inds = np.searchsorted(uf, f_in)
            # clamp
            inds = np.clip(inds, 0, len(uf) - 1)

            # If searchsorted lands on neighbor, choose closer within tol
            # Try left neighbor too
            left = np.clip(inds - 1, 0, len(uf) - 1)
            choose_left = np.abs(uf[left] - f_in) < np.abs(uf[inds] - f_in)
            inds = np.where(choose_left, left, inds)

            # Verify within tolerance
            if np.any(np.abs(uf[inds] - f_in) > freq_tol_hz):
                bad = np.max(np.abs(uf[inds] - f_in))
                raise RuntimeError(
                    f"Frequency grid mismatch beyond tolerance in {t}, spw {s}. "
                    f"Max |Δf|={bad} Hz. Consider increasing freq_tol_hz."
                )

            # Apply only rows belonging to this spw
            row_mask = (spw == s)
            if not np.any(row_mask):
                continue
            rows = np.where(row_mask)[0]

            # Map channels into output arrays (note: union channels padded to nchan_out)
            # Only write within that spw's union length
            for j_in, j_out in enumerate(inds):
                # j_out < len(uf) <= nchan_out
                c_out[:, j_out, rows] = c[:, j_in, rows]
                f_out[:, j_out, rows] = fl[:, j_in, rows]
                if w_out is not None and w is not None:
                    # WEIGHT might be (npol,nchan,nrow) or (npol,nrow)
                    if w.ndim == 3:
                        w_out[:, j_out, rows] = w[:, j_in, rows]
                    elif w.ndim == 2:
                        w_out[:, j_out, rows] = w[:, rows]
                    else:
                        # unexpected, ignore
                        pass

    # Write to output main table
    tb.open(out_table, nomodify=False)
    tb.putcol("CPARAM", c_out)
    tb.putcol("FLAG", f_out)
    if w_out is not None and "WEIGHT" in tb.colnames():
        tb.putcol("WEIGHT", w_out)
    tb.close()

    return out_table

def _format_compact(val: float) -> str:
    v = abs(val)
    if v < 10:
        return f"{val:.2f}"
    elif v < 100:
        return f"{val:.1f}"
    else:
        return f"{val:.0f}"

# Create log file
logging.basicConfig(
    filename='warnings.log',
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Redirect warnings to logging
logging.captureWarnings(True)


def combine_bandpass_tables(bp_tables, out_table, freq_tol_hz=1.0):
    """
    Combine multiple CASA bandpass calibration tables into one, assuming only channels differ.

    Parameters
    ----------
    bp_tables : list[str]
        List of input bandpass cal tables (paths). Order doesn't matter.
    out_table : str
        Output calibration table path.
    freq_tol_hz : float
        Frequency matching tolerance in Hz. (Used for floating-point safety.)

    Notes
    -----
    - Assumes all tables have identical main-table rows (same TIME/ANTENNA1/SPW/SCAN etc.)
      and only differ in channel axis.
    - Merges CPARAM, FLAG, WEIGHT. If overlaps exist, later tables overwrite earlier ones.
    - If row ordering differs across tables, this function will raise an error.
    """

    # CASA tool import (works in CASA6; CASA5 also usually works)
    try:
        from casatools import table as casatable
    except Exception as e:
        raise RuntimeError("Could not import casatools.table. Run inside CASA (casa/casa6).") from e

    if not bp_tables or len(bp_tables) < 2:
        raise ValueError("Provide at least two bandpass tables in bp_tables.")

    for t in bp_tables:
        if not os.path.isdir(t):
            raise FileNotFoundError(f"Bandpass table not found or not a directory: {t}")

    # Prepare output: copy the first table as template
    template = bp_tables[0]
    if os.path.exists(out_table):
        raise FileExistsError(f"Output table already exists: {out_table}")

    shutil.copytree(template, out_table)

    tb = casatable()

    def _read_main_keys(tabpath):
        """Read minimal columns that define row identity."""
        tb.open(tabpath)
        cols = tb.colnames()
        need = []
        for c in ["TIME", "ANTENNA1", "SPECTRAL_WINDOW_ID", "SCAN_NUMBER", "FIELD_ID", "OBSERVATION_ID"]:
            if c in cols:
                need.append(c)
        keys = {c: tb.getcol(c) for c in need}
        tb.close()
        return keys

    def _assert_same_rows(keys_ref, keys_new, tabname):
        """Ensure row identity and ordering are identical."""
        for k, vref in keys_ref.items():
            vnew = keys_new.get(k, None)
            if vnew is None:
                raise RuntimeError(f"{tabname} missing key column {k} present in template.")
            if vref.shape != vnew.shape:
                raise RuntimeError(f"Row-key shape mismatch for {k}: {vref.shape} vs {vnew.shape} in {tabname}")
            # TIME can be float; compare with tolerance; others exact
            if k == "TIME":
                if not np.allclose(vref, vnew, rtol=0, atol=1e-6):
                    raise RuntimeError(f"Row mismatch in TIME between template and {tabname}.")
            else:
                if not np.array_equal(vref, vnew):
                    raise RuntimeError(f"Row mismatch in {k} between template and {tabname}.")

    # Check rows are identical across all inputs
    keys_ref = _read_main_keys(template)
    for t in bp_tables[1:]:
        _assert_same_rows(keys_ref, _read_main_keys(t), t)

    # Read template main table shapes to size output arrays later
    tb.open(template)
    cols = tb.colnames()
    for required in ["CPARAM", "FLAG"]:
        if required not in cols:
            tb.close()
            raise RuntimeError(f"Template table missing required column: {required}")
    cparam_shape = tb.getcol("CPARAM").shape  # (npol, nchan, nrow)
    npol, _, nrow = cparam_shape
    tb.close()

    # --- Helper: get per-SPW frequency grid from SPECTRAL_WINDOW ---
    def _read_spw_chanfreq(tabpath):
        tb.open(os.path.join(tabpath, "SPECTRAL_WINDOW"))
        chan_freq = tb.getcol("CHAN_FREQ")  # shape (nchan, nspw) OR (1,nchan,nspw) depending CASA version
        num_chan = tb.getcol("NUM_CHAN")
        tb.close()

        # Normalize shapes: prefer (nchan, nspw)
        cf = np.array(chan_freq)
        if cf.ndim == 3:
            # CASA sometimes stores CHAN_FREQ as (1,nchan,nspw)
            cf = cf[0, :, :]
        if cf.ndim == 1:
            # Single spw case stored as (nchan,)
            cf = cf.reshape(-1, 1)

        return cf, np.array(num_chan).astype(int)

    # Build union frequency grids per SPW across all tables
    cf0, num0 = _read_spw_chanfreq(template)
    nspw = cf0.shape[1]

    # collect freqs per spw
    all_freqs = [ [] for _ in range(nspw) ]
    for t in bp_tables:
        cf, _ = _read_spw_chanfreq(t)
        if cf.shape[1] != nspw:
            raise RuntimeError(f"SPW count mismatch: {t} has {cf.shape[1]} spw, template has {nspw}")
        for s in range(nspw):
            all_freqs[s].append(cf[:, s].ravel())

    # union with tolerance: sort and merge close values
    def _union_with_tol(freq_lists, tol):
        x = np.concatenate(freq_lists)
        x = np.sort(x)
        if x.size == 0:
            return x
        merged = [x[0]]
        for f in x[1:]:
            if abs(f - merged[-1]) > tol:
                merged.append(f)
        return np.array(merged)

    full_freq = []
    full_nchan = []
    for s in range(nspw):
        uf = _union_with_tol(all_freqs[s], freq_tol_hz)
        full_freq.append(uf)
        full_nchan.append(len(uf))

    # Rewrite SPECTRAL_WINDOW in output
    # Need CHAN_FREQ as (nchan_max, nspw) with padding if variable nchan across spw
    nchan_max = max(full_nchan) if full_nchan else 0
    chan_freq_out = np.zeros((nchan_max, nspw), dtype=float)

    for s in range(nspw):
        uf = full_freq[s]
        chan_freq_out[:len(uf), s] = uf
        if len(uf) < nchan_max:
            # pad with last value (harmless if NUM_CHAN is set correctly)
            chan_freq_out[len(uf):, s] = uf[-1] if len(uf) else 0.0

    tb.open(os.path.join(out_table, "SPECTRAL_WINDOW"), nomodify=False)
    # Some CASA versions expect (1,nchan,nspw)
    existing = tb.getcol("CHAN_FREQ")
    if np.array(existing).ndim == 3:
        tb.putcol("CHAN_FREQ", chan_freq_out.reshape(1, nchan_max, nspw))
    else:
        tb.putcol("CHAN_FREQ", chan_freq_out)
    tb.putcol("NUM_CHAN", np.array(full_nchan, dtype=int))
    tb.close()

    # Prepare output main columns with full channel axis.
    # We assume one channel axis applies per SPW; in cal tables, CPARAM channel axis corresponds to that SPW row.
    # For safety, we will map per row using SPECTRAL_WINDOW_ID.
    tb.open(template)
    spw_id = tb.getcol("SPECTRAL_WINDOW_ID") if "SPECTRAL_WINDOW_ID" in tb.colnames() else None
    tb.close()
    if spw_id is None:
        raise RuntimeError("Main table missing SPECTRAL_WINDOW_ID; cannot map per-SPW channel grids.")

    # Output arrays sized to maximum union nchan among SPWs (per row we use its SPW's nchan)
    # CASA stores CPARAM with a single nchan axis for the table; for multi-SPW tables it usually equals max NUM_CHAN.
    nchan_out = nchan_max
    c_out = np.zeros((npol, nchan_out, nrow), dtype=np.complex128)
    f_out = np.ones((npol, nchan_out, nrow), dtype=bool)     # start fully flagged
    w_out = None

    # If WEIGHT exists, merge it too
    tb.open(template)
    has_weight = "WEIGHT" in tb.colnames()
    if has_weight:
        w_shape = tb.getcol("WEIGHT").shape
        # Usually (npol, nchan, nrow) or (npol, nrow) depending table
        # We'll normalize to (npol, nchan_out, nrow) if possible
        w_out = np.zeros((npol, nchan_out, nrow), dtype=np.float64)
    tb.close()

    # Fill output by iterating tables; later tables overwrite overlaps
    for t in bp_tables:
        # Read per-spw freqs for this table
        cf, num = _read_spw_chanfreq(t)

        tb.open(t)
        c = tb.getcol("CPARAM")  # (npol, nchan_in, nrow)
        fl = tb.getcol("FLAG")   # same shape
        w = tb.getcol("WEIGHT") if (has_weight and "WEIGHT" in tb.colnames()) else None
        spw = tb.getcol("SPECTRAL_WINDOW_ID")
        tb.close()

        _, nchan_in, nrow_in = c.shape
        if nrow_in != nrow:
            raise RuntimeError(f"Row count mismatch in {t}: {nrow_in} vs template {nrow}")

        # For each spw, build mapping from this table's channel freqs to union freqs
        # Use tolerance match; assumes monotonic freqs
        for s in range(nspw):
            uf = full_freq[s]
            f_in = cf[:num[s], s]  # actual channels for this spw in this table

            # Build index map: for each input channel, find union index
            # Using searchsorted for speed, then check tol
            inds = np.searchsorted(uf, f_in)
            # clamp
            inds = np.clip(inds, 0, len(uf) - 1)

            # If searchsorted lands on neighbor, choose closer within tol
            # Try left neighbor too
            left = np.clip(inds - 1, 0, len(uf) - 1)
            choose_left = np.abs(uf[left] - f_in) < np.abs(uf[inds] - f_in)
            inds = np.where(choose_left, left, inds)

            # Verify within tolerance
            if np.any(np.abs(uf[inds] - f_in) > freq_tol_hz):
                bad = np.max(np.abs(uf[inds] - f_in))
                raise RuntimeError(
                    f"Frequency grid mismatch beyond tolerance in {t}, spw {s}. "
                    f"Max |Δf|={bad} Hz. Consider increasing freq_tol_hz."
                )

            # Apply only rows belonging to this spw
            row_mask = (spw == s)
            if not np.any(row_mask):
                continue
            rows = np.where(row_mask)[0]

            # Map channels into output arrays (note: union channels padded to nchan_out)
            # Only write within that spw's union length
            for j_in, j_out in enumerate(inds):
                # j_out < len(uf) <= nchan_out
                c_out[:, j_out, rows] = c[:, j_in, rows]
                f_out[:, j_out, rows] = fl[:, j_in, rows]
                if w_out is not None and w is not None:
                    # WEIGHT might be (npol,nchan,nrow) or (npol,nrow)
                    if w.ndim == 3:
                        w_out[:, j_out, rows] = w[:, j_in, rows]
                    elif w.ndim == 2:
                        w_out[:, j_out, rows] = w[:, rows]
                    else:
                        # unexpected, ignore
                        pass

    # Write to output main table
    tb.open(out_table, nomodify=False)
    tb.putcol("CPARAM", c_out)
    tb.putcol("FLAG", f_out)
    if w_out is not None and "WEIGHT" in tb.colnames():
        tb.putcol("WEIGHT", w_out)
    tb.close()

    return out_table
    
def select_stokes_from_gaintable(
    in_caltable: str,
    out_caltable: str,
    pol_sel=(0,),          # e.g. (0,) for 1st stokes/corr, (1,) for 2nd, (0,1) for both
    overwrite: bool = True,
):
    """
    Create a new CASA gain table containing only selected polarization(s) from CPARAM/FLAG.

    Works for typical G/Jones gaincal tables with:
      - CPARAM: complex array column shaped (npol, nchan) per row  (stored as (npol, nchan, nrow) in getcol)
      - FLAG:   bool array column shaped (npol, nchan) per row (sometimes (npol, nrow); handled)

    Parameters
    ----------
    in_caltable : str
        Input CASA caltable directory.
    out_caltable : str
        Output CASA caltable directory.
    pol_sel : tuple[int] or list[int]
        Indices of polarization axis to keep. Examples:
          (0,)    -> keep 1st stokes/corr only
          (1,)    -> keep 2nd stokes/corr only
          (0, 1)  -> keep first two
    overwrite : bool
        If True, remove out_caltable if it exists.

    Notes
    -----
    - This creates a *new* table with CPARAM/FLAG column shapes adjusted to the selected npol.
    - It copies all other columns and table/column keywords.
    - If your caltable uses FPARAM instead of CPARAM, extend similarly (rare for gaincal).
    """
    import os
    import shutil
    import numpy as np
    from casatools import table

    pol_sel = tuple(int(p) for p in pol_sel)
    if len(pol_sel) == 0:
        raise ValueError("pol_sel must contain at least one polarization index.")

    if overwrite and os.path.exists(out_caltable):
        shutil.rmtree(out_caltable)

    tb_in = table()
    tb_out = table()

    # ---- open input ----
    tb_in.open(in_caltable, nomodify=True)
    try:
        colnames = tb_in.colnames()
        nrows = tb_in.nrows()

        if "CPARAM" not in colnames:
            raise RuntimeError(f"{in_caltable} does not contain CPARAM. Columns: {colnames}")
        if "FLAG" not in colnames:
            raise RuntimeError(f"{in_caltable} does not contain FLAG. Columns: {colnames}")

        # Inspect shapes
        c0 = tb_in.getcell("CPARAM", 0)  # shape (npol, nchan)
        if c0.ndim != 2:
            raise RuntimeError(f"Unexpected CPARAM cell ndim={c0.ndim}; expected 2.")
        npol_in, nchan = c0.shape

        if max(pol_sel) >= npol_in or min(pol_sel) < 0:
            raise ValueError(f"pol_sel={pol_sel} out of range for npol={npol_in}")

        npol_out = len(pol_sel)

        # ---- build output table description (copy all coldsc; adjust CPARAM/FLAG shapes) ----
        desc_out = {}
        for cn in colnames:
            d = tb_in.getcoldesc(cn)

            # Many CASA tables store fixed-shape array columns with a 'shape' entry.
            # If not present, we leave it variable-shape (still works in many cases).
            if cn == "CPARAM":
                # Ensure array column
                d["valueType"] = "complex"
                d["ndim"] = 2
                # Set fixed shape if present in descriptor
                if "shape" in d:
                    d["shape"] = [npol_out, nchan]
            elif cn == "FLAG":
                d["valueType"] = "boolean"
                d["ndim"] = 2
                if "shape" in d:
                    d["shape"] = [npol_out, nchan]

            desc_out[cn] = d

        # ---- create output table ----
        tb_out.create(out_caltable, desc_out, nrow=nrows)

        # Copy table keywords (safe for your downstream use; keeps metadata)
        try:
            tb_out.putkeywords(tb_in.getkeywords())
        except Exception:
            pass

        # Copy column keywords (where possible)
        for cn in colnames:
            try:
                tb_out.putcolkeywords(cn, tb_in.getcolkeywords(cn))
            except Exception:
                pass

        # ---- copy columns ----
        # First copy all "simple" columns via putcol, except CPARAM/FLAG which need slicing
        simple_cols = [cn for cn in colnames if cn not in ("CPARAM", "FLAG", "WEIGHT")]
        for cn in simple_cols:
            arr = tb_in.getcol(cn)
            tb_out.putcol(cn, arr)

        # Now CPARAM/FLAG with pol slicing over all rows at once
        c = tb_in.getcol("CPARAM")  # (npol_in, nchan, nrows)
        if c.ndim != 3:
            raise RuntimeError(f"Unexpected CPARAM getcol ndim={c.ndim}; expected 3.")
        c_sel = c[np.array(pol_sel), :, :].astype(np.complex64, copy=False)
        tb_out.putcol("CPARAM", c_sel)

        f = tb_in.getcol("FLAG")
        # FLAG sometimes comes as (npol, nrow) — broadcast to (npol, nchan, nrow)
        if f.ndim == 2:
            # (npol, nrows) -> (npol, nchan, nrows)
            f = np.broadcast_to(f[:, None, :], (f.shape[0], nchan, f.shape[1]))
        elif f.ndim != 3:
            raise RuntimeError(f"Unexpected FLAG getcol ndim={f.ndim}; expected 2 or 3.")
        f_sel = f[np.array(pol_sel), :, :].astype(bool, copy=False)
        tb_out.putcol("FLAG", f_sel)

    finally:
        tb_in.close()
        try:
            tb_out.close()
        except Exception:
            pass

    copy_all_directories(in_caltable, out_caltable)
    print(f"✅ Wrote {out_caltable} with pol_sel={pol_sel} (npol {npol_in} → {len(pol_sel)})")

def select_stokes_from_bandpasstable(
    in_caltable: str,
    out_caltable: str,
    pol_sel=(0,),          # e.g. (0,) for 1st stokes/corr, (1,) for 2nd, (0,1) for both
    overwrite: bool = True,
):
    """
    Create a new CASA bandpass table containing only selected polarization(s) from CPARAM/FLAG.

    This function mirrors `select_stokes_from_gaintable` but is intended for bandpass calibration
    tables produced by `bandpass`.

    Parameters
    ----------
    in_caltable : str
        Input CASA bandpass caltable directory.
    out_caltable : str
        Output CASA bandpass caltable directory.
    pol_sel : tuple[int] or list[int]
        Indices of polarization axis to keep. Examples:
          (0,)    -> keep 1st stokes/corr only
          (1,)    -> keep 2nd stokes/corr only
          (0, 1)  -> keep first two
    overwrite : bool
        If True, remove out_caltable if it exists.
    """
    import os
    import shutil
    import numpy as np
    from casatools import table

    pol_sel = tuple(int(p) for p in pol_sel)
    if len(pol_sel) == 0:
        raise ValueError("pol_sel must contain at least one polarization index.")

    if overwrite and os.path.exists(out_caltable):
        shutil.rmtree(out_caltable)

    tb_in = table()
    tb_out = table()

    # ---- open input ----
    tb_in.open(in_caltable, nomodify=True)
    try:
        colnames = tb_in.colnames()
        nrows = tb_in.nrows()

        if "CPARAM" not in colnames:
            raise RuntimeError(f"{in_caltable} does not contain CPARAM. Columns: {colnames}")
        if "FLAG" not in colnames:
            raise RuntimeError(f"{in_caltable} does not contain FLAG. Columns: {colnames}")

        # Inspect shapes
        c0 = tb_in.getcell("CPARAM", 0)  # shape (npol, nchan)
        if c0.ndim != 2:
            raise RuntimeError(f"Unexpected CPARAM cell ndim={c0.ndim}; expected 2.")
        npol_in, nchan = c0.shape

        if max(pol_sel) >= npol_in or min(pol_sel) < 0:
            raise ValueError(f"pol_sel={pol_sel} out of range for npol={npol_in}")

        npol_out = len(pol_sel)

        # ---- build output table description (copy all coldsc; adjust CPARAM/FLAG shapes) ----
        desc_out = {}
        for cn in colnames:
            d = tb_in.getcoldesc(cn)

            if cn == "CPARAM":
                d["valueType"] = "complex"
                d["ndim"] = 2
                if "shape" in d:
                    d["shape"] = [npol_out, nchan]
            elif cn == "FLAG":
                d["valueType"] = "boolean"
                d["ndim"] = 2
                if "shape" in d:
                    d["shape"] = [npol_out, nchan]

            desc_out[cn] = d

        # ---- create output table ----
        tb_out.create(out_caltable, desc_out, nrow=nrows)

        # Copy table keywords (safe for your downstream use; keeps metadata)
        try:
            tb_out.putkeywords(tb_in.getkeywords())
        except Exception:
            pass

        # Copy column keywords (where possible)
        for cn in colnames:
            try:
                tb_out.putcolkeywords(cn, tb_in.getcolkeywords(cn))
            except Exception:
                pass

        # ---- copy columns ----
        # First copy all "simple" columns via putcol, except CPARAM/FLAG which need slicing
        simple_cols = [cn for cn in colnames if cn not in ("CPARAM", "FLAG", "WEIGHT")]
        for cn in simple_cols:
            arr = tb_in.getcol(cn)
            tb_out.putcol(cn, arr)

        # Now CPARAM/FLAG with pol slicing over all rows at once
        c = tb_in.getcol("CPARAM")  # (npol_in, nchan, nrows)
        if c.ndim != 3:
            raise RuntimeError(f"Unexpected CPARAM getcol ndim={c.ndim}; expected 3.")
        c_sel = c[np.array(pol_sel), :, :].astype(np.complex64, copy=False)
        tb_out.putcol("CPARAM", c_sel)

        f = tb_in.getcol("FLAG")
        if f.ndim == 2:
            f = np.broadcast_to(f[:, None, :], (f.shape[0], nchan, f.shape[1]))
        elif f.ndim != 3:
            raise RuntimeError(f"Unexpected FLAG getcol ndim={f.ndim}; expected 2 or 3.")
        f_sel = f[np.array(pol_sel), :, :].astype(bool, copy=False)
        tb_out.putcol("FLAG", f_sel)

    finally:
        tb_in.close()
        try:
            tb_out.close()
        except Exception:
            pass
    copy_all_directories(in_caltable, out_caltable)
    print(f"✅ Wrote {out_caltable} with pol_sel={pol_sel} (npol {npol_in} → {len(pol_sel)})")

def get_bandpass_table_metadata(bandpass_table_path):
    """
    Reads metadata from a CASA bandpass calibration table.

    Returns:
        dict: {
            'scans': list of unique scan numbers (if present),
            'antennas': list of unique antenna indices,
            'spws': list of spectral window IDs,
            'stokes': list of polarization indices,
            'nchan': number of channels per solution,
        }
    """

    metadata = {
        'scans': [],
        'antennas': [],
        'spws': [],
        'stokes': [],
        'nchan': None,
        'dcMHz': None,
        'timeS': None,
        'times': None,
    }

    tb = table()
    stb = table()
    tb.open(bandpass_table_path)
    stb.open(bandpass_table_path + "/SPECTRAL_WINDOW")
    metadata['dcMHz'] = np.mean(np.abs(stb.getcol('CHAN_WIDTH')))*1.e-6
    try:
        colnames = tb.colnames()
        nrows = tb.nrows()

        # ---- Scan numbers (optional) ----
        if "SCAN_NUMBER" in colnames:
            metadata['scans'] = np.unique(tb.getcol("SCAN_NUMBER")).tolist()

        # ---- Antennas ----
        if "ANTENNA1" in colnames:
            metadata['antennas'] = np.unique(tb.getcol("ANTENNA1")).T.tolist()

             # ---- Spectral windows ----
        if "SPECTRAL_WINDOW_ID" in colnames:
            metadata['spws'] = np.unique(tb.getcol("SPECTRAL_WINDOW_ID")).tolist()
        # ---- Times ----
        if "TIME" in colnames:
            tt = np.unique(tb.getcol("TIME"))
            metadata['timeS'] = tt[0]
            metadata['times'] = (tt - tt[0]).tolist()
        # ---- Infer polarization and channel structure ----
        # Bandpass uses CPARAM (complex bandpass per channel)
        band_col = None
        if "CPARAM" in colnames:
            band_col = "CPARAM"
        elif "FPARAM" in colnames:
            band_col = "FPARAM"

        if band_col and nrows > 0:
            cell_data = tb.getcell(band_col, 0)  # shape: (npol, nchan)

            if cell_data.ndim == 2:
                npol, nchan = cell_data.shape
                metadata['stokes'] = list(range(npol))
                metadata['nchan'] = int(nchan)

        # ---- Optional: channel frequency info ----
        if "CHAN_FREQ" in colnames:
            chan_freq = tb.getcol("CHAN_FREQ")
            metadata['chan_freq_shape'] = chan_freq.shape

    finally:
        tb.close()
        stb.close()

    return metadata

def get_gain_table_metadata(gain_table_path):
    """
    Reads the table header/columns to return available scans, antennas, and stokes.
    Applies to both gain and bandpass tables.
    
    Returns:
        dict: {
            'scans': list of unique scan numbers,
            'antennas': list of unique antenna indices,
            'stokes': list of unique stokes parameters (if column exists)
        }
    """
    metadata = {
        'scans': [],
        'antennas': [],
        'stokes': []
    }
    
    tb.open(gain_table_path)
    try:
        colnames = tb.colnames()
        nrows = tb.nrows()
        
        if "SCAN_NUMBER" in colnames:
            metadata['scans'] = np.unique(tb.getcol("SCAN_NUMBER")).tolist()
            
        if "ANTENNA1" in colnames:
            metadata['antennas'] = np.unique(tb.getcol("ANTENNA1")).tolist()
            
        if "STOKES" in colnames:
            metadata['stokes'] = np.unique(tb.getcol("STOKES")).tolist()
        elif nrows > 0:
            # Often Stokes info is implied by the shape of the gain array.
            # We check the shape of the first cell (row 0) if the STOKES column is missing.
            gain_col = "GAIN" if "GAIN" in colnames else "CPARAM"
            if gain_col in colnames:
                # getcell returns the array for a single row: [pols, chans]
                cell_data = tb.getcell(gain_col, 0)
                num_pols = cell_data.shape[0]
                metadata['stokes'] = list(range(num_pols))
                
    finally:
        tb.close()
        
    return metadata

def read_casa_gain_table(gain_table_path, antenna_list, scan, UseFlags=True):
    """
    Reads a CASA gain table and extracts complex gains per antenna and Stokes parameter.
    This function no longer subtracts the mean; it should be done by a separate function.
    
    Returns:
        dict: {
            'time': unique time stamps,
            'ant_index': {
                stokes_index: complex_gain_array (shape: [channels, time])
            }
        }
    """
    ant_query = ",".join(map(str, antenna_list))
    taql_string = f"SCAN_NUMBER == {scan} AND ANTENNA1 IN [{ant_query}]"
    
    tb.open(gain_table_path)
    sub_tb = tb.query(taql_string)
    
    try:
        time = sub_tb.getcol("TIME")
        antenna = sub_tb.getcol("ANTENNA1")
        flag = sub_tb.getcol("FLAG")
        
        col_names = sub_tb.colnames()
        gain_col = "GAIN" if "GAIN" in col_names else "CPARAM"
        gain = sub_tb.getcol(gain_col)
        if flag.ndim == 2:
            # Handle rare single-channel FLAG layout (npol, nrow).
            flag = flag[:, np.newaxis, :]
        if gain.ndim != 3 or flag.ndim != 3:
            raise ValueError(
                f"Unexpected GAIN/FLAG shapes: gain={gain.shape}, flag={flag.shape}. "
                "Expected (npol,nchan,nrow)."
            )
        if gain.shape != flag.shape:
            if gain.shape[0] != flag.shape[0] or gain.shape[2] != flag.shape[2]:
                raise ValueError(f"GAIN/FLAG incompatible shapes: gain={gain.shape}, flag={flag.shape}")
            nchan_common = min(int(gain.shape[1]), int(flag.shape[1]))
            if nchan_common <= 0:
                raise ValueError(f"No common channels in gain/flag arrays: gain={gain.shape}, flag={flag.shape}")
            print(
                f"Warning: gain/flag channel mismatch: gain={gain.shape[1]}, flag={flag.shape[1]}; "
                f"using first {nchan_common} channels."
            )
            gain = gain[:, :nchan_common, :]
            flag = flag[:, :nchan_common, :]
        
        stokes_available = "STOKES" in col_names
        stokes = sub_tb.getcol("STOKES") if stokes_available else None

        gains_dict = {'time': np.unique(time)}

        for ant in antenna_list:
            ant_key = str(ant)
            gains_dict[ant_key] = {}
            ant_mask = (antenna == ant)
            
            if not np.any(ant_mask):
                continue
            
            # gain shape is [pol, chan, row]
            ant_gain = gain[:, :, ant_mask]
            ant_flag = flag[:, :, ant_mask]
            
            num_pols = ant_gain.shape[0]
            
            for p in range(num_pols):
                pol_gain = ant_gain[p, :, :]
                pol_flag = ant_flag[p, :, :]
                
                if UseFlags:
                    # Apply flags: set flagged complex gains to NaN
                    pol_gain = np.where(pol_flag, np.nan + 1j*np.nan, pol_gain)

                stokes_label = stokes[p] if stokes_available else p
                gains_dict[ant_key][stokes_label] = pol_gain

    finally:
        sub_tb.close()
        tb.close()
        
    return gains_dict

def read_casa_bandpass_table(bandpass_table_path, antenna_list, scan=1, UseFlags=True, bchan=None, echan=None):
    """
    Reads a CASA bandpass table and extracts complex bandpass per antenna and Stokes parameter.
    Returns a dict like read_casa_gain_table but with emphasis on channels as the primary axis.
    Structure: {'chan': np.ndarray of channel indices (0..N-1), 'ant_key': {stokes: complex_array [channels, time]}}
    """
    ant_query = ",".join(map(str, antenna_list))
    taql_string = f"SCAN_NUMBER == {scan} AND ANTENNA1 IN [{ant_query}]"
    tb.open(bandpass_table_path)
    sub_tb = tb.query(taql_string)
    try:
        antenna = sub_tb.getcol("ANTENNA1")
        flag = sub_tb.getcol("FLAG")
        col_names = sub_tb.colnames()
        if "CPARAM" in col_names:
            gain_col = "CPARAM"
        elif "FPARAM" in col_names:
            gain_col = "FPARAM"
        elif "GAIN" in col_names:
            gain_col = "GAIN"
        else:
            raise ValueError("No CPARAM/FPARAM/GAIN column found in bandpass table.")
        bp = sub_tb.getcol(gain_col)
        stokes_available = "STOKES" in col_names
        stokes = sub_tb.getcol("STOKES") if stokes_available else None
        # Normalize FLAG to (npol, nchan, nrow) if needed.
        if flag.ndim == 2:
            # Some tables can expose FLAG as (npol, nrow) for effectively single-channel content.
            flag = flag[:, np.newaxis, :]
        if bp.ndim != 3 or flag.ndim != 3:
            raise ValueError(
                f"Unexpected BP/FLAG shapes: bp={bp.shape}, flag={flag.shape}. "
                "Expected 3D arrays (npol,nchan,nrow)."
            )

        # Use common channel count if data/flag channel dimensions differ.
        nchan = min(int(bp.shape[1]), int(flag.shape[1]))
        if nchan <= 0:
            raise ValueError(f"No valid channels found in table. bp={bp.shape}, flag={flag.shape}")
        if int(bp.shape[1]) != int(flag.shape[1]):
            print(
                f"Warning: channel mismatch in bandpass table: data={bp.shape[1]}, flag={flag.shape[1]}; "
                f"using first {nchan} channels."
            )
        bp = bp[:, :nchan, :]
        flag = flag[:, :nchan, :]
        chans = np.arange(nchan)

        # Determine channel slice
        start = 0 if bchan is None else max(0, int(bchan))
        stop = nchan if echan is None else min(nchan, int(echan))
        if stop < start:
            start, stop = stop, start
        if stop <= start:
            raise ValueError(
                f"Invalid bandpass channel range after clipping: bchan={bchan}, echan={echan}, nchan={nchan}"
            )
        chans = chans[start:stop]

        out = {'chan': chans}
        for ant in antenna_list:
            ant_key = str(ant)
            out[ant_key] = {}
            ant_mask = (antenna == ant)
            if not np.any(ant_mask):
                continue
            ant_bp = bp[:, start:stop, ant_mask]
            ant_flag = flag[:, start:stop, ant_mask]
            num_pols = ant_bp.shape[0]
            for p in range(num_pols):
                pol_bp = ant_bp[p, :, :]
                pol_flag = ant_flag[p, :, :]
                if UseFlags:
                    pol_bp = np.where(pol_flag, np.nan + 1j*np.nan, pol_bp)
                stokes_label = stokes[p] if stokes_available else p
                out[ant_key][stokes_label] = pol_bp
    finally:
        sub_tb.close(); tb.close()
    return out

def subtract_mean_from_gains_dict(gains_dict):
    """
    Modifies the gain_dict in place by subtracting the mean (real and imaginary parts separately)
    for each antenna and Stokes parameter.

    Args:
        gains_dict (dict): The dictionary containing gain data, as returned by read_casa_gain_table.
                           Structure: {'time': ..., 'ant_index': {stokes_index: complex_gain_array}}
    """
    if not isinstance(gains_dict, dict) or 'time' not in gains_dict:
        print("Warning: Invalid gains_dict format provided to subtract_mean_from_gains_dict. Skipping mean subtraction.")
        return gains_dict

    for ant_key in list(gains_dict.keys()):
        if ant_key == 'time' or ant_key == 'chan':
            continue
        
        ant_data = gains_dict.get(ant_key)
        if not isinstance(ant_data, dict):
            continue

        for stokes_key in list(ant_data.keys()):
            complex_gain_array = ant_data[stokes_key] # shape [channels, time]

            if complex_gain_array.size == 0:
                continue

            # Calculate mean of real and imaginary parts separately, ignoring NaNs
            mean_real_part = np.nanmean(np.real(complex_gain_array))
            mean_imag_part = np.nanmean(np.imag(complex_gain_array))

            # Subtract the corresponding means from real and imaginary parts
            real_part_corrected = np.real(complex_gain_array)
            imag_part_corrected = np.imag(complex_gain_array)

            if np.isfinite(mean_real_part):
                real_part_corrected = real_part_corrected - mean_real_part
            if np.isfinite(mean_imag_part):
                imag_part_corrected = imag_part_corrected - mean_imag_part
            
            # Reconstruct the complex array and update the dictionary
            ant_data[stokes_key] = real_part_corrected + 1j * imag_part_corrected
            
    return gains_dict

@timer
def plot_gain_colormap(gain_table_path, antenna_list=None, stokes_list=None, scan=None, output_plot_file=None, UseFlags=True, save_csv_file=None, bandpass=True, bchan=None, echan=None):
    """
    Plot gain amplitudes (as percentage) for antennas vs time or channels using pcolor (pcolormesh), per Stokes.

    Left column: real(gain) - 1 in percent. Right column: imag(gain) in percent.
    Flagged data shown as white. No smoothing.

    Args:
        gain_table_path (str): Path to CASA gain or bandpass table.
        antenna_list (list[int] | None): Antennas to include. If None, use all from table.
        stokes_list (list | None): Stokes indices/labels to include. If None, use all available.
        scan (int | None): Scan number to plot. If None, defaults to first available scan.
        output_plot_file (str | None): Output image file. If None, defaults to f"gains_colormap_scan{scan}.png".
        UseFlags (bool): Apply FLAG column to mask data.
        save_csv_file (str | None): Output csv file, If None, dot save
        bandpass (bool): If True, read bandpass table instead of gain table and plot vs channels.
        bchan (int | None): Beginning channel index (inclusive) for bandpass mode.
        echan (int | None): Ending channel index (exclusive) for bandpass mode.
    """
    # Discover metadata to fill defaults
    meta = get_gain_table_metadata(gain_table_path)

    if scan is None:
        if len(meta['scans']) == 0:
            raise ValueError("No scans available in gain or bandpass table.")
        scan = meta['scans'][0]

    if antenna_list is None or len(antenna_list) == 0:
        antenna_list = meta['antennas']
    # Ensure sorted unique antenna list
    antenna_list = sorted(set(antenna_list))

    if stokes_list is None or len(stokes_list) == 0:
        stokes_list = meta['stokes'] if len(meta['stokes']) > 0 else None

    # Read gains for requested antennas and scan
    # Note: Mean subtraction is now handled by a separate call in __main__ if requested.
    if bandpass:
        gains = read_casa_bandpass_table(gain_table_path, antenna_list, scan=scan, UseFlags=UseFlags, bchan=bchan, echan=echan)
        chan_idx = gains.get('chan', None)
        if chan_idx is None:
            raise ValueError("No channel indices found in bandpass table.")
        num_chans = len(chan_idx)
    else:
        gains = read_casa_gain_table(gain_table_path, antenna_list, scan=scan, UseFlags=UseFlags)

    # Determine available stokes from the data if not provided
    if stokes_list is None:
        # pick first antenna with data
        stokes_keys = None
        for ant in antenna_list:
            ant_key = str(ant)
            if ant_key in gains and len(gains[ant_key]) > 0:
                stokes_keys = list(gains[ant_key].keys())
                break
        if stokes_keys is None:
            raise ValueError("No stokes data found in gain or bandpass table for requested antennas/scan.")
        stokes_list = stokes_keys

    if bandpass:
        num_times = num_chans
        time_secs = chan_idx
    else:
        # Time vector in seconds (CASA TIME is in seconds since MJD reference)
        time_vals = gains.get('time', None)
        if time_vals is None or len(time_vals) == 0:
            raise ValueError("No time values found for requested scan.")
        # Normalize time to start at 0 seconds for plotting readability
        t0 = float(time_vals[0])
        time_secs = np.array(time_vals - t0, dtype=float)
        num_times = len(time_vals)

    num_ants = len(antenna_list)

    # Prepare figure: rows = number of stokes, columns = 2 (real-1, imag)
    nrows = len(stokes_list)
    ncols = 2
    fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(3.6*ncols + 1.2, 2.4*nrows + 1.2), constrained_layout=True)
    if nrows == 1 and ncols == 2:
        axes = np.array([axes])  # make it 2D array [row, col]

    # Choose diverging colormap and set bad (masked) to white
    cmap = plt.get_cmap('coolwarm').copy()
    cmap.set_bad(color='white')

    # For color scaling, we will compute percent values and then use a symmetric range based on the 99th percentile to reduce outliers
    all_percent_values = []

    # Precompute percent arrays per stokes for stats and scaling
    stokes_data = {}
    for s_idx, s in enumerate(stokes_list):
        # Build arrays [time, antenna]
        real_minus1 = np.full((num_times, num_ants), np.nan, dtype=float)
        imag_vals = np.full((num_times, num_ants), np.nan, dtype=float)
        flag_mask = np.ones((num_times, num_ants), dtype=bool)  # True means flagged

        for a_idx, ant in enumerate(antenna_list):
            ant_key = str(ant)
            ant_dict = gains.get(ant_key, {})
            if s not in ant_dict:
                continue
            # ant_dict[s] has shape [channels, time]
            arr = ant_dict[s]
            # If flags were applied, NaNs should already be present where flagged
            # Aggregate over channels: mean ignoring NaNs
            # real-1 in percent: (real(arr) - 1) * 100
            # For bandpass, arr shape is [pol, chan, time], but here it's [channels, time] already
            if bandpass:
                # Channels on vertical axis; time on horizontal axis; arr shape [channels, time]
                real_chan_time = np.real(arr) - 1.0
                imag_chan_time = np.imag(arr)
                # mean over time axis (axis=1)
                with np.errstate(invalid='ignore'):
                    real_time = np.nanmean(real_chan_time, axis=1) * 100.0
                    imag_time = np.nanmean(imag_chan_time, axis=1) * 100.0
                time_flag = np.all(np.isnan(real_chan_time) & np.isnan(imag_chan_time), axis=1)
                # Fill arrays
                if real_time.shape[0] != num_times:
                    m = min(num_times, real_time.shape[0])
                    real_minus1[:m, a_idx] = real_time[:m]
                    imag_vals[:m, a_idx] = imag_time[:m]
                    flag_mask[:m, a_idx] = time_flag[:m]
                else:
                    real_minus1[:, a_idx] = real_time
                    imag_vals[:, a_idx] = imag_time
                    flag_mask[:, a_idx] = time_flag
            else:
                real_chan_time = np.real(arr) - 1.0
                imag_chan_time = np.imag(arr)
                with np.errstate(invalid='ignore'):
                    real_time = np.nanmean(real_chan_time, axis=0) * 100.0
                    imag_time = np.nanmean(imag_chan_time, axis=0) * 100.0
                time_flag = np.all(np.isnan(real_chan_time) & np.isnan(imag_chan_time), axis=0)
                if real_time.shape[0] != num_times:
                    m = min(num_times, real_time.shape[0])
                    real_minus1[:m, a_idx] = real_time[:m]
                    imag_vals[:m, a_idx] = imag_time[:m]
                    flag_mask[:m, a_idx] = time_flag[:m]
                else:
                    real_minus1[:, a_idx] = real_time
                    imag_vals[:, a_idx] = imag_time
                    flag_mask[:, a_idx] = time_flag

        # Create masked arrays for plotting (white where flagged)
        real_masked = np.ma.array(real_minus1, mask=flag_mask)
        imag_masked = np.ma.array(imag_vals, mask=flag_mask)

        stokes_data[s] = (real_masked, imag_masked)

        # Collect values for scaling
        all_percent_values.append(np.abs(real_masked.compressed()))
        all_percent_values.append(np.abs(imag_masked.compressed()))

    if len(all_percent_values) > 0:
        concat_vals = np.concatenate([v for v in all_percent_values if v.size > 0])
        if concat_vals.size > 0:
            vmax = np.percentile(concat_vals, 99.0)
        else:
            vmax = 1.0
    else:
        vmax = 1.0

    if not np.isfinite(vmax) or vmax <= 0:
        vmax = 1.0
    vmin = -vmax

    # Plot each stokes row
    for r, s in enumerate(stokes_list):
        real_masked, imag_masked = stokes_data[s]

        axR = axes[r, 0]
        axI = axes[r, 1]

        imR = axR.pcolormesh(real_masked, cmap=cmap, vmin=vmin, vmax=vmax, shading='auto')
        imI = axI.pcolormesh(imag_masked, cmap=cmap, vmin=vmin, vmax=vmax, shading='auto')

        # Axis labels and ticks
        # X axis: antenna numbers, show every other antenna label
        axR.set_xticks(np.arange(num_ants) + 0.5)
        axI.set_xticks(np.arange(num_ants) + 0.5)
        ant_labels = [str(a) if (i % 2 == 0) else '' for i, a in enumerate(antenna_list)]
        axR.set_xticklabels(ant_labels, rotation=0)
        axI.set_xticklabels(ant_labels, rotation=0)
        axR.set_xlim(0, num_ants)
        axI.set_xlim(0, num_ants)

        # Y axis: time in seconds or channels, use raw index mapped to seconds or channel indices
        nticks = min(6, num_times)
        tick_idx = np.linspace(0, num_times, nticks, endpoint=False, dtype=int)
        axR.set_yticks(tick_idx + 0.5)
        axI.set_yticks(tick_idx + 0.5)
        if bandpass:
            axR.set_yticklabels([f"{chan_idx[i]:d}" for i in tick_idx])
            axI.set_yticklabels([f"{chan_idx[i]:d}" for i in tick_idx])
            axR.set_ylabel('Channel')
            axI.set_ylabel('Channel')
        else:
            axR.set_yticklabels([f"{time_secs[i]:.0f}" for i in tick_idx])
            axI.set_yticklabels([f"{time_secs[i]:.0f}" for i in tick_idx])
            axR.set_ylabel('Time (s)')
            axI.set_ylabel('Time (s)')

        axR.set_ylim(0, num_times)
        axI.set_ylim(0, num_times)

        # Subplot titles with stats
        def stats_str(masked_arr):
            vals = masked_arr.compressed()
            if vals.size == 0:
                return "mean=nan std=nan skew=nan curt=nan"
            return (
                f"mean={np.nanmean(vals):.2f} std={np.nanstd(vals):.2f} skew={skew(vals, nan_policy='omit'):.2f} curt={kurtosis(vals, nan_policy='omit'):.2f}"
            )

        axR.set_title(f"Stokes {s} Real-1\n{stats_str(real_masked)}", fontsize=9)
        axI.set_title(f"Stokes {s} Imag\n{stats_str(imag_masked)}", fontsize=9)

        # Colorbars on the right of each column
        #cbarR = fig.colorbar(imR, ax=axR, orientation='vertical', fraction=0.046, pad=0.04)
    cbarI = fig.colorbar(imI, ax=[axes[r, 1] for r in range(nrows)], orientation='vertical', fraction=0.1, pad=0.04)
        # Compact tick labels for colorbars
    def _set_compact_cbar_ticks(cbar):
        ticks = cbar.get_ticks()
        cbar.set_ticklabels([_format_compact(t) for t in ticks])
    #_set_compact_cbar_ticks(cbarR)
    _set_compact_cbar_ticks(cbarI)

    # Set x-labels only on bottom row
    for c in range(ncols):
        axes[nrows - 1, c].set_xlabel('Antenna')

    # Global title
    table_name = os.path.basename(gain_table_path)
    fig.suptitle(f"Gain Table: {table_name} | Scan: {scan} [%]", fontsize=12)

    # Output file
    if output_plot_file is not None:
        fig.savefig(output_plot_file, dpi=150)
    plt.close(fig)
  
    # Optionally save CSV of plotted data
    if save_csv_file is not None:
        # Save per-stokes, per-antenna, per-time/channel aggregated series used in the plot
        # Columns: stokes, antenna, time_sec/channel, real_minus1_pct, imag_pct, flagged
        rows = []
        for s in stokes_list:
            real_masked, imag_masked = stokes_data[s]
            # Convert masked arrays to filled arrays and flags
            real_filled = real_masked.filled(np.nan)
            imag_filled = imag_masked.filled(np.nan)
            flags = real_masked.mask | imag_masked.mask  # True where flagged or NaN
            for t_idx in range(num_times):
                for a_idx, ant in enumerate(antenna_list):
                    val_time = float(time_secs[t_idx]) if not bandpass else float(chan_idx[t_idx])
                    rows.append([
                        s,
                        ant,
                        val_time,
                        float(real_filled[t_idx, a_idx]),
                        float(imag_filled[t_idx, a_idx]),
                        int(bool(flags[t_idx, a_idx]))
                    ])
        header = 'stokes,antenna,time_or_channel,real_minus1_pct,imag_pct,flagged'
        try:
            np.savetxt(save_csv_file, np.array(rows, dtype=float), delimiter=',', header=header, comments='')
        except Exception:
            # Fall back to manual write to support mixed dtypes
            with open(save_csv_file, 'w') as f:
                f.write(header + '\n')
                for r in rows:
                    f.write(','.join(map(str, r)) + '\n')

    return output_plot_file

@timer
def plot_gain_histogram(gain_table_path, antenna_list=None, stokes_list=None, scan=None, output_plot_file=None, nbin=64, hist_range=None, UseFlags=True, save_csv_file=None, bandpass=True, bchan=None, echan=None):
    """
    Plot 2D histograms of gain values per antenna for each Stokes and component.

    - Y axis: gain values (percent), symmetric about 0 and including extrema unless `hist_range` is provided.
    - X axis: antenna index (discrete bins centered on each antenna).
    - Color: log10 percentage of samples falling into each (antenna, gain) bin.

    Args:
        gain_table_path (str): Path to CASA gain or bandpass table.
        antenna_list (list[int] | None): Antennas to include. If None, use all from table.
        stokes_list (list | None): Stokes indices/labels to include. If None, use all available.
        scan (int | None): Scan number to plot. If None, defaults to first available scan.
        output_plot_file (str | None): Output image file. If None, defaults to f"gains_hist_scan{scan}.png".
        nbin (int): Number of bins along gain value axis (default 64).
        hist_range (tuple[float, float] | None): Range for gain values (min, max). If None, auto symmetric full range.
        UseFlags (bool): Apply FLAG column to mask data.
        save_csv_file (str | None): Output csv file, If None, dot save
        bandpass (bool): If True, read bandpass table instead of gain table.
        bchan (int | None): Beginning channel index (inclusive) for bandpass mode.
        echan (int | None): Ending channel index (exclusive) for bandpass mode.
    """
    # Discover metadata and defaults
    meta = get_gain_table_metadata(gain_table_path)
    if scan is None:
        if len(meta['scans']) == 0:
            raise ValueError("No scans available in gain or bandpass table.")
        scan = meta['scans'][0]
    if antenna_list is None or len(antenna_list) == 0:
        antenna_list = meta['antennas']
    antenna_list = sorted(set(antenna_list))
    if stokes_list is None or len(stokes_list) == 0:
        stokes_list = meta['stokes'] if len(meta['stokes']) > 0 else None

    # Read gains
    # Note: Mean subtraction is now handled by a separate call in __main__ if requested.
    if bandpass:
        gains = read_casa_bandpass_table(gain_table_path, antenna_list, scan=scan, UseFlags=UseFlags, bchan=bchan, echan=echan)
    else:
        gains = read_casa_gain_table(gain_table_path, antenna_list, scan=scan, UseFlags=UseFlags)

    # Determine available stokes if not provided
    if stokes_list is None:
        stokes_keys = None
        for ant in antenna_list:
            ant_key = str(ant)
            if ant_key in gains and len(gains[ant_key]) > 0:
                stokes_keys = list(gains[ant_key].keys())
                break
        if stokes_keys is None:
            raise ValueError("No stokes data found in gain or bandpass table for requested antennas/scan.")
        stokes_list = stokes_keys

    num_ants = len(antenna_list)

    # Prepare figure layout similar to colormap: rows = stokes, cols = 2 (Real-1, Imag)
    nrows = len(stokes_list)
    ncols = 2
    fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(3.6*ncols + 1.2, 2.4*nrows + 1.2), constrained_layout=True)
    if nrows == 1 and ncols == 2:
        axes = np.array([axes])

    cmap = plt.get_cmap('coolwarm').copy()
    cmap.set_bad(color='white')

    # Build histograms per stokes and component
    stokes_hist = {}

    # Collect all values to define default symmetric range when hist_range is None
    all_vals = []

    for s in stokes_list:
        # Arrays of values per antenna for real-1 and imag
        # We'll flatten across time and channels per antenna
        real_vals_per_ant = [[] for _ in range(num_ants)]
        imag_vals_per_ant = [[] for _ in range(num_ants)]

        for a_idx, ant in enumerate(antenna_list):
            ant_key = str(ant)
            ant_dict = gains.get(ant_key, {})
            if s not in ant_dict:
                continue
            arr = ant_dict[s]  # shape [channels, time]
            if bandpass:
                # For bandpass, flatten over time axis to reduce to channels
                real_vals = (np.real(arr) - 1.0) * 100.0
                imag_vals = (np.imag(arr)) * 100.0
            else:
                real_vals = (np.real(arr) - 1.0) * 100.0
                imag_vals = (np.imag(arr)) * 100.0
            rv = real_vals[np.isfinite(real_vals)]
            iv = imag_vals[np.isfinite(imag_vals)]
            if rv.size > 0:
                real_vals_per_ant[a_idx].append(rv.ravel())
                all_vals.append(rv.ravel())
            if iv.size > 0:
                imag_vals_per_ant[a_idx].append(iv.ravel())
                all_vals.append(iv.ravel())

        # Concatenate per antenna
        real_vals_per_ant = [np.concatenate(v) if len(v) > 0 else np.array([]) for v in real_vals_per_ant]
        imag_vals_per_ant = [np.concatenate(v) if len(v) > 0 else np.array([]) for v in imag_vals_per_ant]

        stokes_hist[s] = (real_vals_per_ant, imag_vals_per_ant)

    # Determine histogram range
    if hist_range is None:
        if len(all_vals) == 0:
            vmin, vmax = -1.0, 1.0
        else:
            concat = np.concatenate([v for v in all_vals if v.size > 0])
            if concat.size == 0:
                vmin, vmax = -1.0, 1.0
            else:
                vmax_abs = np.max(np.abs(concat))
                # Include extrema symmetrically
                vmin, vmax = -vmax_abs, vmax_abs
    else:
        vmin, vmax = hist_range
    # Ensure non-degenerate range
    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmin == vmax:
        vmin, vmax = -1.0, 1.0

    # Bin edges for gain axis
    y_edges = np.linspace(vmin, vmax, nbin + 1)

    # X bins for antennas: create edges so each antenna occupies one column centered at integer index
    x_edges = np.arange(0, num_ants + 1, 1)

    # Plot
    for r, s in enumerate(stokes_list):
        real_vals_per_ant, imag_vals_per_ant = stokes_hist[s]

        # Build 2D hist matrices (nbin_y x num_ants)
        H_real = np.zeros((nbin, num_ants), dtype=float)
        H_imag = np.zeros((nbin, num_ants), dtype=float)

        # Fill hist counts per antenna
        for a_idx in range(num_ants):
            rv = real_vals_per_ant[a_idx]
            iv = imag_vals_per_ant[a_idx]
            if rv.size > 0:
                counts, _ = np.histogram(rv, bins=y_edges)
                H_real[:, a_idx] = counts
            if iv.size > 0:
                counts, _ = np.histogram(iv, bins=y_edges)
                H_imag[:, a_idx] = counts

        # Convert counts to percentage per antenna (column-wise)
        def to_percent(H):
            H_pct = np.zeros_like(H, dtype=float)
            col_sums = H.sum(axis=0)
            for a_idx in range(num_ants):
                total = col_sums[a_idx]
                if total > 0:
                    H_pct[:, a_idx] = (H[:, a_idx] / total) * 100.0
            return H_pct

        H_real_pct = to_percent(H_real)
        H_imag_pct = to_percent(H_imag)

        # For visualization, take log10 on positive percentages; keep zeros as masked so they appear white
        eps = 0.0
        H_real_vis = np.ma.array(np.where(H_real_pct > 0.0, np.log10(H_real_pct), np.nan))
        H_imag_vis = np.ma.array(np.where(H_imag_pct > 0.0, np.log10(H_imag_pct), np.nan))
        # Mask zeros (nan) so cmap shows them as white
        H_real_vis.mask = np.isnan(H_real_vis)
        H_imag_vis.mask = np.isnan(H_imag_vis)

        # Determine color limits in log space based on actual percentage min>0 and max
        def log_limits(H_pct):
            positive = H_pct[H_pct > 0.0]
            if positive.size == 0:
                return -2.0, 0.0  # default range (0.01% to 1%)
            vmin = np.log10(np.nanmin(positive))
            vmax = np.log10(np.nanmax(positive))
            if not np.isfinite(vmin) or not np.isfinite(vmax) or vmin == vmax:
                vmin, vmax = -2.0, 0.0
            return vmin, vmax

        vminR, vmaxR = log_limits(H_real_pct)
        vminI, vmaxI = log_limits(H_imag_pct)

        axR = axes[r, 0]
        axI = axes[r, 1]

        # pcolormesh expects (ny, nx) for C and edges for X,Y
        X, Y = np.meshgrid(x_edges, y_edges)
        imR = axR.pcolormesh(X, Y, H_real_vis, cmap=cmap, shading='auto', vmin=vminR, vmax=vmaxR)
        imI = axI.pcolormesh(X, Y, H_imag_vis, cmap=cmap, shading='auto', vmin=vminI, vmax=vmaxI)

        # X ticks: antenna labels as before
        axR.set_xticks(np.arange(num_ants) + 0.5)
        axI.set_xticks(np.arange(num_ants) + 0.5)
        ant_labels = [str(a) if (i % 2 == 0) else '' for i, a in enumerate(antenna_list)]
        axR.set_xticklabels(ant_labels, rotation=0)
        axI.set_xticklabels(ant_labels, rotation=0)
        axR.set_xlim(0, num_ants)
        axI.set_xlim(0, num_ants)

        # Y: gain values range
        axR.set_ylim(vmin, vmax)
        axI.set_ylim(vmin, vmax)

        # Titles (removed subheading text)
        axR.set_title(f"Stokes {s} Real-1 [%]", fontsize=9)
        axI.set_title(f"Stokes {s} Imag [%]", fontsize=9)

    # Colorbars on the right of each column
    #cbarR = fig.colorbar(imR, ax=axR, orientation='vertical', fraction=0.046, pad=0.04)
    cbarI = fig.colorbar(imI, ax=[axes[r, 1] for r in range(nrows)], orientation='vertical', fraction=0.1, pad=0.04)
    # Compact tick labels for colorbars
    def _set_compact_cbar_ticks(cbar):
        ticks = cbar.get_ticks()
        cbar.set_ticklabels([_format_compact(t) for t in ticks])
    #_set_compact_cbar_ticks(cbarR)
    _set_compact_cbar_ticks(cbarI)

    # Set shared axis labels only on left column and bottom row
    for r, s in enumerate(stokes_list):
        ax_left = axes[r, 0]
        ax_left.set_ylabel('Gain value [%]')
    # Set x-labels only on bottom row
    for c in range(ncols):
        axes[nrows - 1, c].set_xlabel('Antenna')

    # Global title shows table name and units in title only
    table_name = os.path.basename(gain_table_path)
    fig.suptitle(f"Gain Histogram: {table_name} | Scan: {scan} [%]", fontsize=12)

    if output_plot_file is not None:
        fig.savefig(output_plot_file, dpi=150)
    plt.close(fig)
    

    # Optionally save CSV of histogram matrices (percentages per antenna per bin)
    if save_csv_file is not None:
        # We will save, for each stokes and component, the y-bin centers and the percentage per antenna
        rows = []
        def bin_centers(edges):
            return 0.5 * (edges[:-1] + edges[1:])
        y_cent = bin_centers(y_edges)
        for s in stokes_list:
            real_vals_per_ant, imag_vals_per_ant = stokes_hist[s]
            # Rebuild percentage matrices to ensure consistency
            H_real = np.zeros((nbin, num_ants), dtype=float)
            H_imag = np.zeros((nbin, num_ants), dtype=float)
            for a_idx in range(num_ants):
                rv = real_vals_per_ant[a_idx]
                iv = imag_vals_per_ant[a_idx]
                if rv.size > 0:
                    counts, _ = np.histogram(rv, bins=y_edges)
                    H_real[:, a_idx] = counts
                if iv.size > 0:
                    counts, _ = np.histogram(iv, bins=y_edges)
                    H_imag[:, a_idx] = counts
            def to_percent(H):
                H_pct = np.zeros_like(H, dtype=float)
                col_sums = H.sum(axis=0)
                for a_idx in range(num_ants):
                    total = col_sums[a_idx]
                    if total > 0:
                        H_pct[:, a_idx] = (H[:, a_idx] / total) * 100.0
                return H_pct
            H_real_pct = to_percent(H_real)
            H_imag_pct = to_percent(H_imag)
            for bi in range(nbin):
                for a_idx, ant in enumerate(antenna_list):
                    rows.append([s, ant, float(y_cent[bi]), float(H_real_pct[bi, a_idx]), float(H_imag_pct[bi, a_idx])])
        header = 'stokes,antenna,gain_bin_center_pct,real_pct,imag_pct'
        np.savetxt(save_csv_file, np.array(rows, dtype=float), delimiter=',', header=header, comments='')

    return output_plot_file


def compute_structure_function(data1, data2=None, tmin=None, tmax=None, Nbin=32, bintype='log', NJack=1, output_file=None, S2Thr=0.9, output_plot_file=None, title=None, SpanRedFactor=1.):
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
    - SpanRedFactor:optional reduce span by this factor
    
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
        Warning("Input data arrays must contain finite values.")
        tau_centers =  S2 = err = counts = np.zeros(NBin)
        return tau_centers, S2, err, counts

    # Sort by time
    idx1 = np.argsort(t1)
    t1 = t1[idx1]
    x1 = x1[idx1]
    idx2 = np.argsort(t2)
    t2 = t2[idx2]
    x2 = x2[idx2]

    def smallest_nonzero(arr):
        arr = np.asarray(arr)
        nonzero = arr[arr != 0.]
        return nonzero.min() if nonzero.size > 0 else 0.
        
    # Determine default tmin and tmax
    if tmin is None:
        dt1 = np.abs(np.diff(t1))
        dt1 = dt1[dt1 > 0]
        dt2 = np.abs(np.diff(t2))
        dt2 = dt2[dt2 > 0]
        dt_candidates = []
        if dt1.size > 0:
            dt_candidates.append(smallest_nonzero(dt1))
        if dt2.size > 0:
            dt_candidates.append(smallest_nonzero(dt2))
        if len(dt_candidates) == 0:
            tmin = 1.
        else:
            tmin = float(np.min(np.abs(dt_candidates)))

    if tmax is None:
        span1 = t1.max() - t1.min()
        span2 = t2.max() - t2.min()
        span = max(span1, span2)
        tmax = float(span / SpanRedFactor) if span > 0 else float(span)

    if tmax <= tmin:
        tmax = span
        Warning("tmax must be greater than tmin.")

    if tmax == 0 or tmin == 0:
        Warning("Input data have zero span.")
        tau_centers =  S2 = err = counts = np.zeros(NBin)
        return tau_centers, S2, err, counts

    # Build lag bins
    if bintype.lower() == 'lin':
        edges = np.linspace(tmin, tmax, Nbin + 1)
    else:
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
        sigma2 = np.sqrt (var1 * var2)
    norm = 2.0 * sigma2 if sigma2 > 0 else 1.0

    s2_sum = np.zeros(Nbin, dtype=float)
    counts = np.zeros(Nbin, dtype=int)

    for i in range(t1.size):
        ti = t1[i]
        tau = np.abs(ti - t2)
        m = (tau >= tmin) & (tau <= tmax)
        if not np.any(m):
            continue
        tau_sel = tau[m]
        diff = x1[i] - x2[m]
        val = diff * diff
        bin_idx = np.searchsorted(edges, tau_sel, side='right') - 1
        valid = (bin_idx >= 0) & (bin_idx < Nbin)
        if np.any(valid):
            b = bin_idx[valid]
            np.add.at(s2_sum, b, val[valid])
            np.add.at(counts, b, 1)

    with np.errstate(invalid='ignore', divide='ignore'):
        S2 = s2_sum / counts
        S2 = S2 / norm

    err = None
    if NJack is not None and NJack > 1:
        n = t1.size
        folds = np.array_split(np.arange(n), NJack)
        JK = []
        for fold in folds:
            keep_mask = np.ones(n, dtype=bool)
            keep_mask[fold] = False
            t1_j = t1[keep_mask]
            x1_j = x1[keep_mask]
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
        err = np.sqrt((NJack - 1) * np.nanvar(JK, axis=0, ddof=0))

    def _interp_nan(x, y):
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        y_out = y.copy()
        m = np.isfinite(y)
        if np.count_nonzero(m) >= 2:
            y_out[~m] = np.interp(x[~m], x[m], y[m])
        return y_out

    if output_file is not None:
        if err is None:
            err_out = np.full_like(S2, np.nan, dtype=float)
        else:
            err_out = err
        out = np.column_stack([tau_centers, S2, err_out, counts])
        header = "tau_center S2_norm err counts"
        np.savetxt(output_file, out, header=header)

    if output_plot_file is not None:
        fig, ax = plt.subplots(figsize=(5.0, 3.2))
        if err is not None:
            ax.errorbar(tau_centers, S2, yerr=err, fmt='o', ms=3, lw=1, capsize=2)
        else:
            ax.plot(tau_centers, S2, 'o', ms=3, lw=1)
        S2_line = _interp_nan(tau_centers, S2)
        ax.plot(tau_centers, S2_line, '-', lw=2, color='blue')
        ax.axhline(1., color='green', lw=2)
        ax.axhline(S2Thr, color='red', lw=2, linestyle='--')
        ax.set_xlabel(r'$\tau$ [sec]')
        ax.set_ylabel(r'$S_2 / (2\,\sigma^2)$')
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

def plot_single_structure_function(gain_table_path, antenna, stokes, scan, component='imag', S2Thr=0.9, Nbin=32, bintype='log', UseFlags=True, output_plot_file=None, NJack=32, bandpass=False, bchan=None, echan=None):
    """
    Compute and plot the structure function for a single antenna, stokes, component.

    Args:
        gain_table_path (str): Path to CASA gain table.
        antenna (int): Antenna index.
        stokes: Stokes index or label.
        scan (int): Scan index.
        component (str): 'real' or 'imag' component to process.
        S2Thr (float): Threshold for plotting horizontal line.
        Nbin (int): Number of bins.
        bintype (str): 'log' or 'lin' binning.
        UseFlags (bool): Apply flags.
        output_plot_file (str or None): Output filename.
        NJack (int): Jackknife resampling count for error; if 1, no error is computed (default 32).
        bandpass (bool): If True, read bandpass data and use channels as x-axis.
        bchan (int | None): Beginning channel index (inclusive) for bandpass mode.
        echan (int | None): Ending channel index (exclusive) for bandpass mode.

    Returns:
        tuple: (output_plot_file, tau, S2)
    """
    if bandpass:
        bandmeta = get_bandpass_table_metadata(gain_table_path)
        dcMHz = bandmeta['dcMHz']
        gains = read_casa_bandpass_table(gain_table_path, [antenna], scan=scan, UseFlags=UseFlags, bchan=bchan, echan=echan)
        
        ant_key = str(antenna)
        if ant_key not in gains:
            raise ValueError(f"Antenna {antenna} not found in bandpass gains for scan {scan}.")
        if stokes not in gains[ant_key]:
            raise ValueError(f"Stokes {stokes} not found for antenna {antenna} in scan {scan} bandpass data.")

        arr = gains[ant_key][stokes]  # shape [channels, time]
        real_series = np.nanmean((np.real(arr) - 1.0) * 100.0, axis=1)
        imag_series = np.nanmean(np.imag(arr) * 100.0, axis=1)

        chan_idx = gains.get('chan')
        if chan_idx is None:
            raise ValueError("Channel indices missing in bandpass gain data.")

        if component == 'real':
            series = real_series
        elif component == 'imag':
            series = imag_series
        else:
            raise ValueError(f"Invalid component '{component}', must be 'real' or 'imag'.")

        mfin = np.isfinite(series) & np.isfinite(chan_idx)
        ts = chan_idx[mfin]
        vs = series[mfin]

        if output_plot_file is None:
            output_plot_file = f"s2_single_bpass_ant{antenna}_scan{scan}_stokes{stokes}_{component}.png"
        else:
            PTH = Path(output_plot_file)
            output_plot_file = PTH.with_name(f"{PTH.stem}_{component}{PTH.suffix}")

        title = f"Bandpass antenna:{antenna}, scan:{scan}, stokes:{stokes}, {component} (channel)"

        tau, S2, _, _ = compute_structure_function(
            (ts, vs), data2=None, tmin=None, tmax=None,
            Nbin=Nbin, bintype=bintype, NJack=NJack, S2Thr=S2Thr,
            output_file=None, output_plot_file=output_plot_file,
            title=title
        )
    else:
        gains = read_casa_gain_table(gain_table_path, [antenna], scan=scan, UseFlags=UseFlags)

        ant_key = str(antenna)
        if ant_key not in gains:
            raise ValueError(f"Antenna {antenna} not found in gains for scan {scan}.")
        if stokes not in gains[ant_key]:
            raise ValueError(f"Stokes {stokes} not found for antenna {antenna} in scan {scan}.")

        arr = gains[ant_key][stokes]  # shape [channels, time]

        if component == 'real':
            series = np.nanmean((np.real(arr) - 1.0) * 100.0, axis=0)
        elif component == 'imag':
            series = np.nanmean((np.imag(arr) - 0.0) * 100.0, axis=0)
        else:
            raise ValueError(f"Invalid component '{component}', must be 'real' or 'imag'.")

        time_vals = gains.get('time')
        if time_vals is None:
            raise ValueError("Time values missing in gain data.")

        mfin = np.isfinite(series) & np.isfinite(time_vals)
        ts = time_vals[mfin]
        vs = series[mfin]

        if output_plot_file is None:
            output_plot_file = f"s2_single_ant{antenna}_scan{scan}_stokes{stokes}_{component}.png"
        else:
            PTH = Path(output_plot_file)
            output_plot_file = PTH.with_name(f"{PTH.stem}_{component}{PTH.suffix}")

        title = f"antenna:{antenna}, scan:{scan}, stokes:{stokes}, {component}"

        tau, S2, _, _ = compute_structure_function(
            (ts, vs), data2=None, tmin=None, tmax=None,
            Nbin=Nbin, bintype=bintype, NJack=NJack, S2Thr=S2Thr,
            output_file=None, output_plot_file=output_plot_file,
            title=title
        )
    
    
    return output_plot_file, tau, S2

def plot_single_antenndaGainTime(gain_table_path, antenna, stokes, scan, component='both', UseFlags=True, output_plot_file=None):
    """
    Plot gain time series for a single antenna, stokes, and component (real, imag, or both).

    Args:
        gain_table_path (str): Path to CASA gain table.
        antenna (int): Antenna index.
        stokes: Stokes index or label.
        scan (int): Scan index.
        component (str): 'real', 'imag', or 'both' (default 'both').
        UseFlags (bool): Apply flags.
        output_plot_file (str or None): Output filename.

    Returns:
        str: Path to saved plot file.
    """
    gains = read_casa_gain_table(gain_table_path, [antenna], scan=scan, UseFlags=UseFlags)

    ant_key = str(antenna)
    if ant_key not in gains:
        raise ValueError(f"Antenna {antenna} not found in gains for scan {scan}.")
    if stokes not in gains[ant_key]:
        raise ValueError(f"Stokes {stokes} not found for antenna {antenna} in scan {scan}.")

    arr = gains[ant_key][stokes]  # shape [channels, time]

    real_series = np.nanmean((np.real(arr) - 1.0) * 100.0, axis=0)
    imag_series = np.nanmean(np.imag(arr) * 100.0, axis=0)

    time_vals = gains.get('time')
    if time_vals is None:
        raise ValueError("Time values missing in gain data.")

    t0 = float(time_vals[0])
    time_secs = np.array(time_vals - t0, dtype=float)

    if component == 'both':
        fig, axs = plt.subplots(2, 1, figsize=(6, 5), sharex=True)
        axs[0].plot(time_secs, real_series, color='blue')
        axs[0].set_ylabel('Real-1 [%]')
        axs[0].set_title(f"Antenna {antenna}, Scan {scan}, Stokes {stokes} - Real Component")
        axs[0].grid(True, ls=':')

        axs[1].plot(time_secs, imag_series, color='red')
        axs[1].set_ylabel('Imag [%]')
        axs[1].set_xlabel('Time [s]')
        axs[1].set_title(f"Antenna {antenna}, Scan {scan}, Stokes {stokes} - Imag Component")
        axs[1].grid(True, ls=':')
        fig.tight_layout()
    elif component == 'real':
        fig, ax = plt.subplots(figsize=(6, 3))
        ax.plot(time_secs, real_series, color='blue')
        ax.set_ylabel('Real-1 [%]')
        ax.set_xlabel('Time [s]')
        ax.set_title(f"Antenna {antenna}, Scan {scan}, Stokes {stokes} - Real Component")
        ax.grid(True, ls=':')
        fig.tight_layout()
    elif component == 'imag':
        fig, ax = plt.subplots(figsize=(6, 3))
        ax.plot(time_secs, imag_series, color='red')
        ax.set_ylabel('Imag [%]')
        ax.set_xlabel('Time [s]')
        ax.set_title(f"Antenna {antenna}, Scan {scan}, Stokes {stokes} - Imag Component")
        ax.grid(True, ls=':')
        fig.tight_layout()
    else:
        raise ValueError("component must be 'real', 'imag', or 'both'.")

    if output_plot_file is None:
        output_plot_file = f"gain_time_ant{antenna}_scan{scan}_stokes{stokes}_{component}.png"
   
    fig.savefig(output_plot_file, dpi=150)
    plt.close(fig)
    return output_plot_file

def plot_single_antenndaBpassChennel(gain_table_path, antenna, stokes, scan, component='both', UseFlags=True, output_plot_file=None, bchan=None, echan=None):
    """
    Plot bandpass gain per channel for a single antenna, stokes, and component (real, imag, or both).

    Args:
        gain_table_path (str): Path to CASA bandpass table.
        antenna (int): Antenna index.
        stokes: Stokes index or label.
        scan (int): Scan index.
        component (str): 'real', 'imag', or 'both' (default 'both').
        UseFlags (bool): Apply flags.
        output_plot_file (str or None): Output filename.
        bchan (int | None): Beginning channel index (inclusive).
        echan (int | None): Ending channel index (exclusive).

    Returns:
        str: Path to saved plot file.
    """
    gains = read_casa_bandpass_table(gain_table_path, [antenna], scan=scan, UseFlags=UseFlags, bchan=bchan, echan=echan)

    ant_key = str(antenna)
    if ant_key not in gains:
        raise ValueError(f"Antenna {antenna} not found in bandpass gains for scan {scan}.")
    if stokes not in gains[ant_key]:
        raise ValueError(f"Stokes {stokes} not found for antenna {antenna} in scan {scan} bandpass data.")

    arr = gains[ant_key][stokes]  # shape [channels, time]
    real_series = np.nanmean((np.real(arr) - 1.0) * 100.0, axis=1)
    imag_series = np.nanmean(np.imag(arr) * 100.0, axis=1)

    chan_idx = gains.get('chan')
    if chan_idx is None:
        raise ValueError("Channel indices missing in bandpass gain data.")

    if component == 'both':
        fig, axs = plt.subplots(2, 1, figsize=(6, 5), sharex=True)
        axs[0].plot(chan_idx, real_series, color='blue')
        axs[0].set_ylabel('Real-1 [%]')
        axs[0].set_title(f"Bandpass: Antenna {antenna}, Scan {scan}, Stokes {stokes} - Real Component")
        axs[0].grid(True, ls=':')

        axs[1].plot(chan_idx, imag_series, color='red')
        axs[1].set_ylabel('Imag [%]')
        axs[1].set_xlabel('Channel')
        axs[1].set_title(f"Bandpass: Antenna {antenna}, Scan {scan}, Stokes {stokes} - Imag Component")
        axs[1].grid(True, ls=':')
        fig.tight_layout()
    elif component == 'real':
        fig, ax = plt.subplots(figsize=(6, 3))
        ax.plot(chan_idx, real_series, color='blue')
        ax.set_ylabel('Real-1 [%]')
        ax.set_xlabel('Channel')
        ax.set_title(f"Bandpass: Antenna {antenna}, Scan {scan}, Stokes {stokes} - Real Component")
        ax.grid(True, ls=':')
        fig.tight_layout()
    elif component == 'imag':
        fig, ax = plt.subplots(figsize=(6, 3))
        ax.plot(chan_idx, imag_series, color='red')
        ax.set_ylabel('Imag [%]')
        ax.set_xlabel('Channel')
        ax.set_title(f"Bandpass: Antenna {antenna}, Scan {scan}, Stokes {stokes} - Imag Component")
        ax.grid(True, ls=':')
        fig.tight_layout()
    else:
        raise ValueError("component must be 'real', 'imag', or 'both'.")

    if output_plot_file is None:
        output_plot_file = f"bpass_time_ant{antenna}_scan{scan}_stokes{stokes}_{component}.png"

    fig.savefig(output_plot_file, dpi=150)
    plt.close(fig)
    return output_plot_file

def plot_single_histogram(gain_table_path, antenna, stokes, scan, component='imag', nbin=64, hist_range=None, UseFlags=True, output_plot_file=None):
    """
    Plot 1D histogram of gain values for a single antenna, stokes, and component.

    Args:
        gain_table_path (str): Path to CASA gain table.
        antenna (int): Antenna index.
        stokes: Stokes index or label.
        scan (int): Scan index.
        component (str): 'real' or 'imag' (default 'imag').
        nbin (int): Number of bins.
        hist_range (tuple or None): Histogram range. If None, auto symmetric about 0.
        UseFlags (bool): Apply flags.
        output_plot_file (str or None): Output filename.

    Returns:
        str: Path to saved plot file.
    """
    gains = read_casa_gain_table(gain_table_path, [antenna], scan=scan, UseFlags=UseFlags)

    ant_key = str(antenna)
    if ant_key not in gains:
        raise ValueError(f"Antenna {antenna} not found in gains for scan {scan}.")
    if stokes not in gains[ant_key]:
        raise ValueError(f"Stokes {stokes} not found for antenna {antenna} in scan {scan}.")

    arr = gains[ant_key][stokes]  # shape [channels, time]

    if component == 'real':
        vals = (np.real(arr) - 1.0) * 100.0
    elif component == 'imag':
        vals = np.imag(arr) * 100.0
    else:
        raise ValueError("component must be 'real' or 'imag'.")

    vals = vals[np.isfinite(vals)].ravel()

    if hist_range is None:
        if vals.size == 0:
            vmin, vmax = -1.0, 1.0
        else:
            vmax_abs = np.max(np.abs(vals))
            vmin, vmax = -vmax_abs, vmax_abs
    else:
        vmin, vmax = hist_range
    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmin == vmax:
        vmin, vmax = -1.0, 1.0

    fig, ax = plt.subplots(figsize=(6, 3))
    ax.hist(vals, bins=nbin, range=(vmin, vmax), color='tab:blue', alpha=0.7, edgecolor='black')
    ax.set_xlabel('Gain value [%]')
    ax.set_ylabel('Counts')
    ax.set_title(f"Antenna {antenna}, Scan {scan}, Stokes {stokes} - {component.capitalize()} Histogram")
    ax.grid(True, ls=':')

    if output_plot_file is None:
        output_plot_file = f"gain_hist_ant{antenna}_scan{scan}_stokes{stokes}_{component}.png"
    else:
        PTH = Path(output_plot_file)
        output_plot_file = PTH.with_name(f"{PTH.stem}_{component}{PTH.suffix}")

    fig.tight_layout()
    fig.savefig(output_plot_file, dpi=150)
    plt.close(fig)
    return output_plot_file

@timer
def plot_structure_function_colormap(gain_table_path, antenna_list=None, stokes_list=None, scan=None, tmin=None, tmax=None, S2Thr=0.9, Nbin=32, bintype='log', output_plot_file=None, UseFlags=True, save_npy_file=None, bandpass=False, bchan=None, echan=None):
    """
    Plot structure function S2(tau) as a colormap with tau on the vertical axis and antenna on the horizontal axis.
    For each stokes, two columns are shown: Real-1 and Imag components.

    - Color encodes log10(S2), with the color scale shared across the four panels (or all panels) and limited to
      [log10(S2_min_all), log10(1.5)], where S2_min_all is the minimum positive S2 across all computed panels.
    - Jackknife errors are not computed (NJack fixed to 1 in calls).
    - If save_npy_file is not None, saves a compressed .npz file containing:
        's2_data': ndarray with shape (Nbin+1, num_ants, n_stokes, 2), where index 0 along axis=0 is unused for coordinates,
                   coordinates such as tau_common or tau_common * dcMHz are stored in metadata dict instead,
        'params': dict of parameters used in the computation (gain_table_path, antenna_list, stokes_list, scan, tmin,
                  tmax, S2Thr, Nbin, bintype, bandpass, bchan, echan, UseFlags, tau_common, dcMHz (if bandpass))

    Inputs:
        gain_table_path (str)
        antenna_list (list[int] | None)
        stokes_list (list | None)
        scan (int | None)
        tmin, tmax: if None, defaults to time resolution and span/10
        Nbin (int): default 32
        bintype (str): 'log' or 'lin', default 'log'
        output_plot_file (str | None): default to f"s2_colormap_scan{scan}.png"
        UseFlags (bool): apply flags when reading gains
        save_npy_file (str | None): Output compressed npz file, If None, do not save
        bandpass (bool | False): If True, read bandpass table and use channel indices instead of time
        bchan (int | None): Beginning channel index (inclusive) for bandpass mode.
        echan (int | None): Ending channel index (exclusive) for bandpass mode.

    Returns:
        tuple: (output_plot_file (str), tau_at_threshold (dict))
            tau_at_threshold is a dict keyed by stokes with values {'real': np.ndarray, 'imag': np.ndarray}
            each array has length num_ants and contains tau values where S2 crosses the threshold S2Thr.
    """
    # Discover metadata to fill defaults
    meta = get_gain_table_metadata(gain_table_path)
    if scan is None:
        if len(meta['scans']) == 0:
            raise ValueError("No scans available in gain or bandpass table.")
        scan = meta['scans'][0]
    if antenna_list is None or len(antenna_list) == 0:
        antenna_list = meta['antennas']
    antenna_list = sorted(set(antenna_list))
    if stokes_list is None or len(stokes_list) == 0:
        stokes_list = meta['stokes'] if len(meta['stokes']) > 0 else None

    # Read gains
    # Note: Mean subtraction is now handled by a separate call in __main__ if requested.
    if bandpass:
        bandmeta = get_bandpass_table_metadata(gain_table_path)
        dcMHz = bandmeta['dcMHz']
        gains = read_casa_bandpass_table(gain_table_path, antenna_list, scan=scan, UseFlags=UseFlags, bchan=bchan, echan=echan)
    else:
        gains = read_casa_gain_table(gain_table_path, antenna_list, scan=scan, UseFlags=UseFlags)

    # Resolve stokes if None from data
    if stokes_list is None:
        stokes_keys = None
        for ant in antenna_list:
            ant_key = str(ant)
            if ant_key in gains and len(gains[ant_key]) > 0:
                stokes_keys = list(gains[ant_key].keys())
                break
        if stokes_keys is None:
            raise ValueError("No stokes data found in gain or bandpass table for requested antennas/scan.")
        stokes_list = stokes_keys

    n_stokes = len(stokes_list)
    num_ants = len(antenna_list)

    if bandpass:
        chan_idx = gains.get('chan', None)
        if chan_idx is None:
            raise ValueError("No channel indices found in bandpass table.")
        nrows = n_stokes
        ncols = 2

        # Prepare arrays to hold S2 per panel to determine global color scale and common tau grid
        panels_data = {}  # key: (stokes, comp) -> (tau, S2_matrix)
        S2_min_pos = np.inf
        for s in stokes_list:
            S2_real_mat = np.full((Nbin, num_ants), np.nan, dtype=float)
            S2_imag_mat = np.full((Nbin, num_ants), np.nan, dtype=float)
            tau_ref = None
            for a_idx, ant in enumerate(antenna_list):
                ant_key = str(ant)
                ant_dict = gains.get(ant_key, {})
                if s not in ant_dict:
                    continue
                arr = ant_dict[s]  # [channels, time]
                # Build channel series for Real-1 and Imag in percent by averaging over time axis (axis=1)
                with np.errstate(invalid='ignore'):
                    real_series = np.nanmean((np.real(arr) - 1.0) * 100.0, axis=1)
                    imag_series = np.nanmean((np.imag(arr)) * 100.0, axis=1)
                c = np.arange(arr.shape[0], dtype=float)  # channels as x-axis
                mR = np.isfinite(real_series) & np.isfinite(c)
                mI = np.isfinite(imag_series) & np.isfinite(c)
                if np.any(mR):
                    tauR, S2R, _, _ = compute_structure_function((c[mR], real_series[mR]), data2=None, tmin=tmin, tmax=tmax, Nbin=Nbin, bintype=bintype, NJack=1, output_file=None, output_plot_file=None)
                    if tau_ref is None:
                        tau_ref = tauR
                    if tauR.shape == tau_ref.shape and np.allclose(tauR, tau_ref):
                        S2_real_mat[:, a_idx] = S2R
                    else:
                        S2_real_mat[:, a_idx] = np.interp(tau_ref, tauR, S2R, left=np.nan, right=np.nan)
                    pos = S2R[S2R > 0]
                    if pos.size > 0:
                        S2_min_pos = min(S2_min_pos, float(np.nanmin(pos)))
                if np.any(mI):
                    tauI, S2I, _, _ = compute_structure_function((c[mI], imag_series[mI]), data2=None, tmin=tmin, tmax=tmax, Nbin=Nbin, bintype=bintype, NJack=1, output_file=None, output_plot_file=None)
                    if tau_ref is None:
                        tau_ref = tauI
                    if tauI.shape == tau_ref.shape and np.allclose(tauI, tau_ref):
                        S2_imag_mat[:, a_idx] = S2I
                    else:
                        S2_imag_mat[:, a_idx] = np.interp(tau_ref, tauI, S2I, left=np.nan, right=np.nan)
                    pos = S2I[S2I > 0]
                    if pos.size > 0:
                        S2_min_pos = min(S2_min_pos, float(np.nanmin(pos)))
            if tau_ref is None:
                raise ValueError("Could not compute structure function for any antenna.")
            panels_data[(s, 'real')] = (tau_ref, S2_real_mat)
            panels_data[(s, 'imag')] = (tau_ref, S2_imag_mat)
            tau_common = tau_ref

        # Save npz array if requested
        if save_npy_file is not None:
            # Create array with shape (Nbin+1, num_ants, n_stokes, 2)
            # Index 0 along axis=0 is unused for coordinates to avoid broadcasting errors.
            # Coordinates such as tau_common*dcMHz are stored in metadata instead.
            s2_array = np.full((Nbin + 1, num_ants, n_stokes, 2), np.nan, dtype=float)
            # Do NOT assign coordinate arrays into s2_array[0]
            for s_idx, s in enumerate(stokes_list):
                tau_ref, S2_real_mat = panels_data[(s, 'real')]
                _, S2_imag_mat = panels_data[(s, 'imag')]
                s2_array[1:, :, s_idx, 0] = S2_real_mat
                s2_array[1:, :, s_idx, 1] = S2_imag_mat

            metadata_dict = {
                'gain_table_path': gain_table_path,
                'antenna_list': antenna_list,
                'stokes_list': stokes_list,
                'scan': scan,
                'tmin': tmin,
                'tmax': tmax,
                'S2Thr': S2Thr,
                'Nbin': Nbin,
                'bintype': bintype,
                'bandpass': bandpass,
                'bchan': bchan,
                'echan': echan,
                'UseFlags': UseFlags,
                'tau_common': tau_common,
                'dcMHz': dcMHz,
            }
            np.savez_compressed(save_npy_file, s2_data=s2_array, params=metadata_dict)

        # Determine color scale in log space
        if not np.isfinite(S2_min_pos) or S2_min_pos <= 0:
            S2_min_pos = 1e-3
        vmin_log = np.log10(S2_min_pos)
        vmax_log = np.log10(1.5)

        # Prepare figure
        fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(3.3*ncols + 1.6, 2.4*nrows + 1.2), constrained_layout=True)
        if nrows == 1 and ncols == 2:
            axes = np.array([axes])

        cmap = plt.get_cmap('coolwarm').copy()
        cmap.set_bad(color='white')

        # Build Y edges from tau_common
        tau_c = np.asarray(tau_common)
        dtau = np.diff(tau_c)
        lower = tau_c[0] - dtau[0] / 2 if tau_c.size > 1 else tau_c[0] * 0.9
        upper = tau_c[-1] + dtau[-1] / 2 if tau_c.size > 1 else tau_c[-1] * 1.1
        y_edges = np.concatenate([[lower], 0.5 * (tau_c[:-1] + tau_c[1:]), [upper]])

        x_edges = np.arange(0, num_ants + 1, 1)

        def _interp_nan_vec(x, y):
            x = np.asarray(x, dtype=float)
            y = np.asarray(y, dtype=float)
            out = y.copy()
            m = np.isfinite(y)
            if np.count_nonzero(m) >= 2:
                out[~m] = np.interp(x[~m], x[m], y[m])
            return out

        def _tau_at_threshold(tau_vec, s2_vec, thr):
            tau_vec = np.asarray(tau_vec, dtype=float)
            s2_vec = np.asarray(s2_vec, dtype=float)
            m = np.isfinite(tau_vec) & np.isfinite(s2_vec)
            if np.count_nonzero(m) < 2:
                return np.nan
            tau_f = tau_vec[m]
            S2_f = s2_vec[m]
            order = np.argsort(tau_f)
            tau_f = tau_f[order]
            S2_f = S2_f[order]

            tmin_eff = float(np.nanmin(tau_f)) if tau_f.size > 0 else np.nan
            tmax_eff = float(np.nanmax(tau_f)) if tau_f.size > 0 else np.nan

            above_mask = S2_f > thr
            n_above = int(np.count_nonzero(above_mask))
            n_total = int(S2_f.size)

            if n_above <= 1:
                return tmax_eff
            if n_above >= n_total - 1:
                return tmin_eff

            diff = S2_f - thr
            sign = np.sign(diff)
            cross = sign[:-1] * sign[1:] <= 0
            idxs = np.where(cross)[0]
            if idxs.size == 0:
                frac_above = n_above / max(n_total, 1)
                return tmin_eff if frac_above > 0.5 else tmax_eff
            i = int(idxs[0])
            x0, x1 = tau_f[i], tau_f[i+1]
            y0, y1 = S2_f[i], S2_f[i+1]
            if not (np.isfinite(x0) and np.isfinite(x1) and np.isfinite(y0) and np.isfinite(y1)):
                return np.nan
            if x1 == x0 or y1 == y0:
                above_idx = np.where(S2_f > thr)[0]
                return tau_f[int(above_idx[0])] if above_idx.size > 0 else tmax_eff
            w = (thr - y0) / (y1 - y0)
            return x0 + w * (x1 - x0)

        tau_at_threshold_out = {}

        for r, s in enumerate(stokes_list):
            tau_ref, S2_real_mat = panels_data[(s, 'real')]
            _, S2_imag_mat = panels_data[(s, 'imag')]

            S2_real_mat = np.column_stack([_interp_nan_vec(tau_ref, S2_real_mat[:, i]) for i in range(S2_real_mat.shape[1])])
            S2_imag_mat = np.column_stack([_interp_nan_vec(tau_ref, S2_imag_mat[:, i]) for i in range(S2_imag_mat.shape[1])])

            tau_at_thr_real = np.array([_tau_at_threshold(tau_ref, S2_real_mat[:, i], S2Thr) for i in range(S2_real_mat.shape[1])])
            tau_at_thr_imag = np.array([_tau_at_threshold(tau_ref, S2_imag_mat[:, i], S2Thr) for i in range(S2_imag_mat.shape[1])])

            tau_at_threshold_out[s] = {'real': tau_at_thr_real, 'imag': tau_at_thr_imag}

            H_real_vis = np.ma.array(np.where(S2_real_mat > 0.0, np.log10(S2_real_mat), np.nan))
            H_imag_vis = np.ma.array(np.where(S2_imag_mat > 0.0, np.log10(S2_imag_mat), np.nan))
            H_real_vis.mask = np.isnan(H_real_vis)
            H_imag_vis.mask = np.isnan(H_imag_vis)

            axR = axes[r, 0]
            axI = axes[r, 1]

            X, Y = np.meshgrid(x_edges, y_edges)
            imR = axR.pcolormesh(X, Y, H_real_vis, cmap=cmap, shading='auto', vmin=vmin_log, vmax=vmax_log)
            imI = axI.pcolormesh(X, Y, H_imag_vis, cmap=cmap, shading='auto', vmin=vmin_log, vmax=vmax_log)

            for i, tau_i in enumerate(tau_at_thr_real):
                if np.isfinite(tau_i):
                    axR.hlines(tau_i, i, i+1, colors='white', linestyles='-', linewidth=2)
            for i, tau_i in enumerate(tau_at_thr_imag):
                if np.isfinite(tau_i):
                    axI.hlines(tau_i, i, i+1, colors='white', linestyles='-', linewidth=2)
            axR.set_xticks(np.arange(num_ants) + 0.5)
            axI.set_xticks(np.arange(num_ants) + 0.5)
            ant_labels = [str(a) if (i % 2 == 0) else '' for i, a in enumerate(antenna_list)]
            axR.set_xticklabels(ant_labels, rotation=0, fontsize=8)
            axI.set_xticklabels(ant_labels, rotation=0, fontsize=8)
            axR.set_xlim(0, num_ants)
            axI.set_xlim(0, num_ants)

            axR.set_ylim(y_edges[0], y_edges[-1])
            axI.set_ylim(y_edges[0], y_edges[-1])
            
            # Move primary y-axis to right
            axR.yaxis.tick_right()
            axR.yaxis.set_label_position("right")
            axR.tick_params(axis='y', labelsize=9)

            axI.yaxis.tick_right()
            axI.yaxis.set_label_position("right")

            # Define transformation
            def right_to_left(y):
                return y * dcMHz

            def left_to_right(y):
                return y / dcMHz

            # Development PD 180226
            # Add secondary y-axis on left
            secaxR = axR.secondary_yaxis('left',
                                         functions=(right_to_left, left_to_right))
            secaxI = axI.secondary_yaxis('left',
                                         functions=(right_to_left, left_to_right))

            secaxR.set_ylabel("Δν (MHz)", fontsize=10)   # or whatever physical meaning
            #secaxI.set_ylabel("Δν (MHz)")
            secaxR.tick_params(axis='y', labelsize=9)
            if bintype.lower() == 'log':
                axR.set_yscale('log')
                axI.set_yscale('log')

            axR.set_title(f"Stokes {s} Real-1", fontsize=9)
            axI.set_title(f"Stokes {s} Imag", fontsize=9)
            
        cbarI = fig.colorbar(imI, ax=[axes[r, 1] for r in range(nrows)], orientation='vertical', fraction=0.1, pad=0.04)
        ticks_log = np.linspace(vmin_log, vmax_log, num=5)
        ticks_lin = np.power(10.0, ticks_log)
            #cbarR.set_ticks(ticks_log); cbarR.set_ticklabels([_format_compact(t) for t in ticks_lin])
            #cbarI.set_ticks(ticks_log); cbarI.set_ticklabels([_format_compact(t) for t in ticks_lin])
        cbarI.set_ticks(ticks_log)
        cbarI.set_ticklabels([f"{10**t:.2f}" for t in ticks_log])
        
        for r, s in enumerate(stokes_list):
            axes[r, 1].set_ylabel('Δc (channels)', fontsize=10)
        for c in range(ncols):
            axes[nrows - 1, c].set_xlabel('Antenna', fontsize=10)

        table_name = os.path.basename(gain_table_path)
        fig.suptitle(f"Structure Function: {table_name} | Scan: {scan}", fontsize=12)
        # Add extra horizontal (x) margin for clarity
        fig.subplots_adjust(right=0.95, left=0.37, top=0.92, bottom=0.11, wspace=0.23)
        if output_plot_file is not None:
            fig.savefig(output_plot_file, dpi=150)
        plt.close(fig)
        return output_plot_file, tau_at_threshold_out
    
    else:
        # Original time-based implementation (unchanged except bandpass param)
        time_vals = gains.get('time', None)
        if time_vals is None or len(time_vals) == 0:
            raise ValueError("No time values found for requested scan.")

        nrows = len(stokes_list)
        ncols = 2

        S2_min_pos = np.inf
        panels_data = {}

        for s in stokes_list:
            S2_real_mat = np.full((Nbin, num_ants), np.nan, dtype=float)
            S2_imag_mat = np.full((Nbin, num_ants), np.nan, dtype=float)
            tau_ref = None
            for a_idx, ant in enumerate(antenna_list):
                ant_key = str(ant)
                ant_dict = gains.get(ant_key, {})
                if s not in ant_dict:
                    continue
                arr = ant_dict[s]  # [channels, time]
                with np.errstate(invalid='ignore'):
                    real_series = np.nanmean((np.real(arr) - 1.0) * 100.0, axis=0)
                    imag_series = np.nanmean((np.imag(arr)) * 100.0, axis=0)
                t = np.asarray(time_vals, dtype=float)
                mR = np.isfinite(real_series) & np.isfinite(t)
                mI = np.isfinite(imag_series) & np.isfinite(t)
                if np.any(mR):
                    tauR, S2R, _, _ = compute_structure_function((t[mR], real_series[mR]), data2=None, tmin=tmin, tmax=tmax, Nbin=Nbin, bintype=bintype, NJack=1, output_file=None, output_plot_file=None)
                    if tau_ref is None:
                        tau_ref = tauR
                    if tauR.shape == tau_ref.shape and np.allclose(tauR, tau_ref):
                        S2_real_mat[:, a_idx] = S2R
                    else:
                        S2_real_mat[:, a_idx] = np.interp(tau_ref, tauR, S2R, left=np.nan, right=np.nan)
                    pos = S2R[S2R > 0]
                    if pos.size > 0:
                        S2_min_pos = min(S2_min_pos, float(np.nanmin(pos)))
                if np.any(mI):
                    tauI, S2I, _, _ = compute_structure_function((t[mI], imag_series[mI]), data2=None, tmin=tmin, tmax=tmax, Nbin=Nbin, bintype=bintype, NJack=1, output_file=None, output_plot_file=None)
                    if tau_ref is None:
                        tau_ref = tauI
                    if tauI.shape == tau_ref.shape and np.allclose(tauI, tau_ref):
                        S2_imag_mat[:, a_idx] = S2I
                    else:
                        S2_imag_mat[:, a_idx] = np.interp(tau_ref, tauI, S2I, left=np.nan, right=np.nan)
                    pos = S2I[S2I > 0]
                    if pos.size > 0:
                        S2_min_pos = min(S2_min_pos, float(np.nanmin(pos)))
            if tau_ref is None:
                raise ValueError("Could not compute structure function for any antenna.")
            panels_data[(s, 'real')] = (tau_ref, S2_real_mat)
            panels_data[(s, 'imag')] = (tau_ref, S2_imag_mat)
            tau_common = tau_ref

        # Save npz array if requested
        if save_npy_file is not None:
            # Create array with shape (Nbin+1, num_ants, n_stokes, 2)
            # Index 0 along axis=0 is unused for coordinates to avoid broadcasting errors.
            # Coordinates such as tau_common are stored in metadata instead.
            s2_array = np.full((Nbin + 1, num_ants, n_stokes, 2), np.nan, dtype=float)
            # Do NOT assign coordinate arrays into s2_array[0]
            for s_idx, s in enumerate(stokes_list):
                tau_ref, S2_real_mat = panels_data[(s, 'real')]
                _, S2_imag_mat = panels_data[(s, 'imag')]
                s2_array[1:, :, s_idx, 0] = S2_real_mat
                s2_array[1:, :, s_idx, 1] = S2_imag_mat

            metadata_dict = {
                'gain_table_path': gain_table_path,
                'antenna_list': antenna_list,
                'stokes_list': stokes_list,
                'scan': scan,
                'tmin': tmin,
                'tmax': tmax,
                'S2Thr': S2Thr,
                'Nbin': Nbin,
                'bintype': bintype,
                'bandpass': bandpass,
                'bchan': bchan,
                'echan': echan,
                'UseFlags': UseFlags,
                'tau_common': tau_common,
            }
            np.savez_compressed(save_npy_file, s2_data=s2_array, params=metadata_dict)

        if not np.isfinite(S2_min_pos) or S2_min_pos <= 0:
            S2_min_pos = 1e-3
        vmin_log = np.log10(S2_min_pos)
        vmax_log = np.log10(1.5)

        fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(3.6*ncols + 1.2, 2.4*nrows + 1.2), constrained_layout=True)
        if nrows == 1 and ncols == 2:
            axes = np.array([axes])

        cmap = plt.get_cmap('coolwarm').copy()
        cmap.set_bad(color='white')

        tau_c = np.asarray(tau_common)
        dtau = np.diff(tau_c)
        lower = tau_c[0] - dtau[0] / 2 if tau_c.size > 1 else tau_c[0] * 0.9
        upper = tau_c[-1] + dtau[-1] / 2 if tau_c.size > 1 else tau_c[-1] * 1.1
        y_edges = np.concatenate([[lower], 0.5 * (tau_c[:-1] + tau_c[1:]), [upper]])

        x_edges = np.arange(0, num_ants + 1, 1)

        def _interp_nan_vec(x, y):
            x = np.asarray(x, dtype=float)
            y = np.asarray(y, dtype=float)
            out = y.copy()
            m = np.isfinite(y)
            if np.count_nonzero(m) >= 2:
                out[~m] = np.interp(x[~m], x[m], y[m])
            return out

        def _tau_at_threshold(tau_vec, s2_vec, thr):
            tau_vec = np.asarray(tau_vec, dtype=float)
            s2_vec = np.asarray(s2_vec, dtype=float)
            m = np.isfinite(tau_vec) & np.isfinite(s2_vec)
            if np.count_nonzero(m) < 2:
                return np.nan
            tau_f = tau_vec[m]
            S2_f = s2_vec[m]
            order = np.argsort(tau_f)
            tau_f = tau_f[order]
            S2_f = S2_f[order]

            tmin_eff = float(np.nanmin(tau_f)) if tau_f.size > 0 else np.nan
            tmax_eff = float(np.nanmax(tau_f)) if tau_f.size > 0 else np.nan

            above_mask = S2_f > thr
            n_above = int(np.count_nonzero(above_mask))
            n_total = int(S2_f.size)

            if n_above <= 1:
                return tmax_eff
            if n_above >= n_total - 1:
                return tmin_eff

            diff = S2_f - thr
            sign = np.sign(diff)
            cross = sign[:-1] * sign[1:] <= 0
            idxs = np.where(cross)[0]
            if idxs.size == 0:
                frac_above = n_above / max(n_total, 1)
                return tmin_eff if frac_above > 0.5 else tmax_eff
            i = int(idxs[0])
            x0, x1 = tau_f[i], tau_f[i+1]
            y0, y1 = S2_f[i], S2_f[i+1]
            if not (np.isfinite(x0) and np.isfinite(x1) and np.isfinite(y0) and np.isfinite(y1)):
                return np.nan
            if x1 == x0 or y1 == y0:
                above_idx = np.where(S2_f > thr)[0]
                return tau_f[int(above_idx[0])] if above_idx.size > 0 else tmax_eff
            w = (thr - y0) / (y1 - y0)
            return x0 + w * (x1 - x0)

        tau_at_threshold_out = {}

        for r, s in enumerate(stokes_list):
            tau_ref, S2_real_mat = panels_data[(s, 'real')]
            _, S2_imag_mat = panels_data[(s, 'imag')]

            S2_real_mat = np.column_stack([_interp_nan_vec(tau_ref, S2_real_mat[:, i]) for i in range(S2_real_mat.shape[1])])
            S2_imag_mat = np.column_stack([_interp_nan_vec(tau_ref, S2_imag_mat[:, i]) for i in range(S2_imag_mat.shape[1])])

            tau_at_thr_real = np.array([_tau_at_threshold(tau_ref, S2_real_mat[:, i], S2Thr) for i in range(S2_real_mat.shape[1])])
            tau_at_thr_imag = np.array([_tau_at_threshold(tau_ref, S2_imag_mat[:, i], S2Thr) for i in range(S2_imag_mat.shape[1])])

            tau_at_threshold_out[s] = {'real': tau_at_thr_real, 'imag': tau_at_thr_imag}

            H_real_vis = np.ma.array(np.where(S2_real_mat > 0.0, np.log10(S2_real_mat), np.nan))
            H_imag_vis = np.ma.array(np.where(S2_imag_mat > 0.0, np.log10(S2_imag_mat), np.nan))
            H_real_vis.mask = np.isnan(H_real_vis)
            H_imag_vis.mask = np.isnan(H_imag_vis)

            axR = axes[r, 0]
            axI = axes[r, 1]

            X, Y = np.meshgrid(x_edges, y_edges)
            imR = axR.pcolormesh(X, Y, H_real_vis, cmap=cmap, shading='auto', vmin=vmin_log, vmax=vmax_log)
            imI = axI.pcolormesh(X, Y, H_imag_vis, cmap=cmap, shading='auto', vmin=vmin_log, vmax=vmax_log)

            for i, tau_i in enumerate(tau_at_thr_real):
                if np.isfinite(tau_i):
                    axR.hlines(tau_i, i, i+1, colors='white', linestyles='-', linewidth=2)
            for i, tau_i in enumerate(tau_at_thr_imag):
                if np.isfinite(tau_i):
                    axI.hlines(tau_i, i, i+1, colors='white', linestyles='-', linewidth=2)

            axR.set_xticks(np.arange(num_ants) + 0.5)
            axI.set_xticks(np.arange(num_ants) + 0.5)
            ant_labels = [str(a) if (i % 2 == 0) else '' for i, a in enumerate(antenna_list)]
            axR.set_xticklabels(ant_labels, rotation=0, fontsize=8)
            axI.set_xticklabels(ant_labels, rotation=0, fontsize=8)
            axR.set_xlim(0, num_ants)
            axI.set_xlim(0, num_ants)

            axR.set_ylim(y_edges[0], y_edges[-1])
            axI.set_ylim(y_edges[0], y_edges[-1])
            if bintype.lower() == 'log':
                axR.set_yscale('log')
                axI.set_yscale('log')

            axR.set_title(f"Stokes {s} Real-1", fontsize=9)
            axI.set_title(f"Stokes {s} Imag", fontsize=9)

            #cbarR = fig.colorbar(imR, ax=axR, orientation='vertical', fraction=0.046, pad=0.04)
        cbarI = fig.colorbar(imI, ax=[axes[r, 1] for r in range(nrows)], orientation='vertical', fraction=0.1, pad=0.04)
        ticks_log = np.linspace(vmin_log, vmax_log, num=5)
        ticks_lin = np.power(10.0, ticks_log)
        #cbarR.set_ticks(ticks_log); cbarR.set_ticklabels([_format_compact(t) for t in ticks_lin])
        cbarI.set_ticks(ticks_log); cbarI.set_ticklabels([_format_compact(t) for t in ticks_lin])

        for r, s in enumerate(stokes_list):
            axes[r, 0].set_ylabel(r'$\tau$ (sec)', fontsize=14)
        for c in range(ncols):
            axes[nrows - 1, c].set_xlabel('Antenna', fontsize=14)

        table_name = os.path.basename(gain_table_path)
        fig.suptitle(f"Structure Function: {table_name} | Scan: {scan}", fontsize=12)

        if output_plot_file is not None:
            fig.savefig(output_plot_file, dpi=150)
        plt.close(fig)
        return output_plot_file, tau_at_threshold_out

@timer
def plot_antenna_gain_stats_grid(
    gain_table_path,
    antenna_list=None,
    stokes_list=None,
    scan=None,
    output_plot_file=None,
    UseFlags=True,
    save_csv_file=None,
    subtract_mean=False,
    bandpass=True,
    bchan=None,
    echan=None
):
    """
    Compute and plot per-antenna statistics (mean-1, std, skewness, kurtosis) for real-1 and imag
    components (in percent) for the given scan and stokes. The figure is a 2x2 grid arranged
    clockwise as: mean-1 (top-left), std (top-right), skewness (bottom-right), kurtosis (bottom-left).

    - Each subplot contains series per stokes/component labeled like "LL-re" and "LL-im", where
      real/imag share the same marker shape but real is filled and imag is hollow.
    - X-axis shows antenna numbers; label every two antennas to reduce clutter.

    Optionally, if save_data_path is provided, saves a CSV file with computed statistics:
    mean, median, std, skewness, kurtosis for each antenna, stokes, and component.

    Args:
        gain_table_path (str): Path to CASA gain or bandpass table
        antenna_list (list[int] | None): Antennas to include (defaults to all)
        stokes_list (list | None): Stokes to include (defaults to all)
        scan (int | None): Scan number (defaults to first available)
        output_plot_file (str | None): Output filename; default auto-generated
        UseFlags (bool): Whether to apply flags
        save_csv_file (str | None): Path to save CSV statistics (optional)
        subtract_mean (bool): If True, subtract the mean of the complex gains per antenna and stokes
            (real and imaginary parts separately) before computing statistics.
        bandpass (bool): If True, read bandpass table and compute stats accordingly.
        bchan (int | None): Beginning channel index (inclusive) for bandpass mode.
        echan (int | None): Ending channel index (exclusive) for bandpass mode.

    Returns:
        str: Path to saved plot
    """
    meta = get_gain_table_metadata(gain_table_path)
    if scan is None:
        if len(meta['scans']) == 0:
            raise ValueError("No scans available in gain or bandpass table.")
        scan = meta['scans'][0]
    if antenna_list is None or len(antenna_list) == 0:
        antenna_list = meta['antennas']
    antenna_list = sorted(set(antenna_list))
    if stokes_list is None or len(stokes_list) == 0:
        stokes_list = meta['stokes'] if len(meta['stokes']) > 0 else None

    if bandpass:
        gains = read_casa_bandpass_table(gain_table_path, antenna_list, scan=scan, UseFlags=UseFlags, bchan=bchan, echan=echan)
    else:
        gains = read_casa_gain_table(gain_table_path, antenna_list, scan=scan, UseFlags=UseFlags)

    if stokes_list is None:
        stokes_keys = None
        for ant in antenna_list:
            ant_key = str(ant)
            if ant_key in gains and len(gains[ant_key]) > 0:
                stokes_keys = list(gains[ant_key].keys())
                break
        if stokes_keys is None:
            raise ValueError("No stokes data found in gain or bandpass table for requested antennas/scan.")
        stokes_list = stokes_keys

    if bandpass:
        time_vals = gains.get('chan', None)
        if time_vals is None or len(time_vals) == 0:
            raise ValueError("No channel indices found for requested scan.")
    else:
        time_vals = gains.get('time', None)
        if time_vals is None or len(time_vals) == 0:
            raise ValueError("No time values found for requested scan.")

    num_ants = len(antenna_list)
    nrows = len(stokes_list)
    ncols = 2
    
    if subtract_mean:
        for ant in antenna_list:
            ant_key = str(ant)
            for s in stokes_list:
                arr = gains.get(ant_key)[s]
                if arr.size == 0:
                    continue
                mean_real = np.nanmean(np.real(arr))
                mean_imag = np.nanmean(np.imag(arr))
                real_corr = np.real(arr) - (mean_real if np.isfinite(mean_real) else 0.0)
                imag_corr = np.imag(arr) - (mean_imag if np.isfinite(mean_imag) else 0.0)
                gains[ant_key][s] = real_corr + 1j * imag_corr
    #    print("\n\n===Applied per-antenna/stokes mean subtraction to complex gains.\n\n")
    
    stats = {}

    for s in stokes_list:
        stats[s] = {
            'real': {k: np.full(num_ants, np.nan, dtype=float) for k in ['mean','std','skew','kurt','median']},
            'imag': {k: np.full(num_ants, np.nan, dtype=float) for k in ['mean','std','skew','kurt','median']},
        }
        for i, ant in enumerate(antenna_list):
            ant_key = str(ant)
            arr = gains.get(ant_key)[s]
            if arr is None:
                continue
            
            if subtract_mean:
                real_vals = np.real(arr)
            else:
                real_vals = (np.real(arr) - 1.)
            imag_vals = (np.imag(arr))
            rv = real_vals[np.isfinite(real_vals)].ravel()
            iv = imag_vals[np.isfinite(imag_vals)].ravel()
            if rv.size > 0:
                stats[s]['real']['mean'][i] = np.nanmean(rv) * 100.0
                stats[s]['real']['std'][i] = np.nanstd(rv) * 100.0
                stats[s]['real']['skew'][i] = skew(rv, bias=False, nan_policy='omit')
                stats[s]['real']['kurt'][i] = kurtosis(rv, bias=False, nan_policy='omit')
                stats[s]['real']['median'][i] = np.nanmedian(rv)
            if iv.size > 0:
                stats[s]['imag']['mean'][i] = np.nanmean(iv) * 100.0
                stats[s]['imag']['std'][i] = np.nanstd(iv) * 100.0
                stats[s]['imag']['skew'][i] = skew(iv, bias=False, nan_policy='omit')
                stats[s]['imag']['kurt'][i] = kurtosis(iv, bias=False, nan_policy='omit')
                stats[s]['imag']['median'][i] = np.nanmedian(iv)

    fig, axes = plt.subplots(2, 2, figsize=(10, 7), constrained_layout=True)
    ax_mean = axes[0, 0]
    ax_std = axes[0, 1]
    ax_skew = axes[1, 1]
    ax_kurt = axes[1, 0]

    base_markers = ['o', 's', '^', 'D', 'v', 'P', 'X']
    colors = plt.rcParams['axes.prop_cycle'].by_key().get('color', ['C0','C1','C2','C3','C4','C5','C6'])

    def stokes_label(st):
        if isinstance(st, (int, np.integer)):
            return str(int(st))
        return str(st)

    xs = np.arange(num_ants)
    xticklabels = [str(a) if (i % 2 == 0) else '' for i, a in enumerate(antenna_list)]

    global_ranges = {
        'mean': [], 'std': [], 'skew': [], 'kurt': []
    }
    for s in stokes_list:
        for metric in ['mean','std','skew','kurt']:
            for comp in ['real','imag']:
                vals = stats[s][comp][metric]
                finite = vals[np.isfinite(vals)]
                if finite.size > 0:
                    global_ranges[metric].append([np.min(finite), np.max(finite)])

    def metric_limits(metric):
        pairs = global_ranges[metric]
        if not pairs:
            return (-1.0, 1.0)
        vmin = np.min([p[0] for p in pairs])
        vmax = np.max([p[1] for p in pairs])
        if not np.isfinite(vmin) or not np.isfinite(vmax) or vmin == vmax:
            return (0.0 - 1.0, 0.0 + 1.0)
        pad = 0.05 * (vmax - vmin) if vmax > vmin else 1.0
        return (vmin - pad, vmax + pad)

    ylims = {m: metric_limits(m) for m in ['mean','std','skew','kurt']}

    for idx, s in enumerate(stokes_list):
        color = colors[idx % len(colors)]
        marker = base_markers[idx % len(base_markers)]
        label_base = stokes_label(s)
        ax_mean.plot(xs, stats[s]['real']['mean'], marker=marker, ms=5, color=color, linestyle='-', label=f"{label_base}-re", markerfacecolor=color)
        ax_std.plot(xs, stats[s]['real']['std'], marker=marker, ms=5, color=color, linestyle='-', label=f"{label_base}-re", markerfacecolor=color)
        ax_skew.plot(xs, stats[s]['real']['skew'], marker=marker, ms=5, color=color, linestyle='-', label=f"{label_base}-re", markerfacecolor=color)
        ax_kurt.plot(xs, stats[s]['real']['kurt'], marker=marker, ms=5, color=color, linestyle='-', label=f"{label_base}-re", markerfacecolor=color)
        ax_mean.plot(xs, stats[s]['imag']['mean'], marker=marker, ms=5, color=color, linestyle='--', label=f"{label_base}-im", markerfacecolor='white')
        ax_std.plot(xs, stats[s]['imag']['std'], marker=marker, ms=5, color=color, linestyle='--', label=f"{label_base}-im", markerfacecolor='white')
        ax_skew.plot(xs, stats[s]['imag']['skew'], marker=marker, ms=5, color=color, linestyle='--', label=f"{label_base}-im", markerfacecolor='white')
        ax_kurt.plot(xs, stats[s]['imag']['kurt'], marker=marker, ms=5, color=color, linestyle='--', label=f"{label_base}-im", markerfacecolor='white')

    for ax, title, metric in [
        (ax_mean, 'Mean-1 [%]', 'mean'),
        (ax_std, 'Std [%]', 'std'),
        (ax_skew, 'Skewness', 'skew'),
        (ax_kurt, 'Kurtosis', 'kurt'),
    ]:
        ax.set_xlim(-0.5, num_ants - 0.5)
        ax.set_xticks(xs)
        ax.set_xticklabels(xticklabels)
        ax.set_ylim(ylims[metric])
        ax.set_title(title, fontsize=10)
        ax.grid(True, ls=':', alpha=0.4)

    handles, labels = ax_mean.get_legend_handles_labels()
    seen = set()
    uniq = []
    for h, l in zip(handles, labels):
        if l not in seen:
            seen.add(l)
            uniq.append((h, l))
    ax_mean.legend(
        [h for h, _ in uniq], [l for _, l in uniq],
        loc='upper right', frameon=True, fontsize=8, ncol=1
    )

    axes[1, 0].set_xlabel('Antenna')
    axes[1, 1].set_xlabel('Antenna')

    if output_plot_file is not None:
        fig.suptitle(f"Per-antenna Gain Statistics (Scan {scan})", fontsize=12)
        fig.tight_layout(rect=[0, 0, 1, 0.95])
        fig.savefig(output_plot_file, dpi=150)
    plt.close(fig)

    if save_csv_file is not None:
        import csv
        with open(save_csv_file, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            header = ['antenna', 'stokes', 'component', 'mean', 'median', 'std', 'skew', 'kurt']
            writer.writerow(header)
            for i, ant in enumerate(antenna_list):
                for s in stokes_list:
                    for comp in ['real', 'imag']:
                        row = [
                            ant,
                            s,
                            comp,
                            stats[s][comp]['mean'][i],
                            stats[s][comp]['median'][i],
                            stats[s][comp]['std'][i],
                            stats[s][comp]['skew'][i],
                            stats[s][comp]['kurt'][i],
                        ]
                        writer.writerow(row)

    return output_plot_file

@timer
def plot_antenna_gain_ks_grid(
    gain_table_path,
    antenna_list=None,
    stokes_list=None,
    scan=None,
    output_plot_file=None,
    UseFlags=True,
    save_csv_file=None,
    bandpass=True,
    bchan=None,
    echan=None
):
    """
    Compute and plot per-antenna KS D-statistics (percent) for real and imag components
    (against normal distribution) per stokes.
    - Only D-statistics are plotted as solid lines.
    - Markers: o for stokes 0 real, s for stokes 1 real, o (open) for stokes 0 imag, s (open) for stokes 1 imag.
    - Colors: different for each of the series.
    Optionally saves stats as CSV if save_data_path is provided.

    Args:
        gain_table_path (str): Path to CASA gain or bandpass table
        antenna_list (list[int] | None): Antennas to include (defaults to all)
        stokes_list (list | None): Stokes to include (defaults to all)
        scan (int | None): Scan number (defaults to first available)
        output_plot_file (str | None): Output filename; default auto-generated
        UseFlags (bool): Whether to apply flags
        save_csv_file (str | None): Path to save CSV statistics (optional)
        bandpass (bool): If True, read bandpass table and process accordingly.
        bchan (int | None): Beginning channel index (inclusive) for bandpass mode.
        echan (int | None): Ending channel index (exclusive) for bandpass mode.

    Returns:
        str: Path to saved plot
    """
    meta = get_gain_table_metadata(gain_table_path)
    if scan is None:
        if len(meta['scans']) == 0:
            raise ValueError("No scans available in gain or bandpass table.")
        scan = meta['scans'][0]
    if antenna_list is None or len(antenna_list) == 0:
        antenna_list = meta['antennas']
    antenna_list = sorted(set(antenna_list))
    if stokes_list is None or len(stokes_list) == 0:
        stokes_list = meta['stokes'] if len(meta['stokes']) > 0 else None

    if bandpass:
        gains = read_casa_bandpass_table(gain_table_path, antenna_list, scan=scan, UseFlags=UseFlags, bchan=bchan, echan=echan)
    else:
        gains = read_casa_gain_table(gain_table_path, antenna_list, scan=scan, UseFlags=UseFlags)

    if stokes_list is None:
        stokes_keys = None
        for ant in antenna_list:
            ant_key = str(ant)
            if ant_key in gains and len(gains[ant_key]) > 0:
                stokes_keys = list(gains[ant_key].keys())
                break
        if stokes_keys is None:
            raise ValueError("No stokes data found in gain or bandpass table for requested antennas/scan.")
        stokes_list = stokes_keys

    time_vals = gains.get('chan' if bandpass else 'time', None)
    if time_vals is None or len(time_vals) == 0:
        raise ValueError("No time or channel values found for requested scan.")

    num_ants = len(antenna_list)
    nrows = len(stokes_list)
    ncols = 2
  
    ks = {
        s: {
            'real': {'d': np.full(num_ants, np.nan)},
            'imag': {'d': np.full(num_ants, np.nan)},
        } for s in stokes_list
    }
    for s in stokes_list:
        for i, ant in enumerate(antenna_list):
            arr = gains.get(str(ant))[s]
            if arr is not None and arr.size > 0:
                if bandpass:
                    rv = np.nanmean(np.real(arr), axis=1)
                    iv = np.nanmean(np.imag(arr), axis=1)
                else:
                    rv = np.real(arr).ravel()
                    iv = np.imag(arr).ravel()
                rv = rv[np.isfinite(rv)]
                iv = iv[np.isfinite(iv)]
                if rv.size > 0:
                    d, _ = kstest(rv, 'norm', args=(np.mean(rv), np.std(rv, ddof=1)))
                    ks[s]['real']['d'][i] = d * 100.0
                if iv.size > 0:
                    d, _ = kstest(iv, 'norm', args=(np.mean(iv), np.std(iv, ddof=1)))
                    ks[s]['imag']['d'][i] = d * 100.0
    fig, ax = plt.subplots(figsize=(10, 6))
    base_markers = ['o', 's']
    colors = ['C0', 'C1', 'C2', 'C3']
    xs = np.arange(num_ants)
    xticklabels = [str(a) for a in antenna_list]
    legend_entries = []
    for idx, s in enumerate(stokes_list):
        color_real = colors[(2 * idx) % len(colors)]
        color_imag = colors[(2 * idx + 1) % len(colors)]
        marker = base_markers[idx % len(base_markers)]
        label_base = str(s) if not isinstance(s, float) else f"{s:.2f}"
        l1, = ax.plot(xs, ks[s]['real']['d'], color=color_real, linestyle='-', marker=marker, label=f"{label_base}-re", markerfacecolor=color_real)
        l3, = ax.plot(xs, ks[s]['imag']['d'], color=color_imag, linestyle='-', marker=marker, label=f"{label_base}-im", markerfacecolor='white')
        legend_entries.extend([l1, l3])
    ax.set_xticks(xs)
    ax.set_xticklabels(xticklabels)
    ax.set_xlabel('Antenna', fontsize=14)
    ax.set_ylabel('KS-statistic [%]', fontsize=14)
    ax.set_title(f'Antenna Gain KS Statistics (Scan {scan})', fontsize=14)
    ax.grid(True, ls=':')
    ax.legend(fontsize=14, ncol=2)
    ax.tick_params(axis='both', labelsize=12)
    if output_plot_file is None:
        output_plot_file = f"antenna_gain_ks_stats_scan{scan}.png"
    fig.tight_layout()
    fig.savefig(output_plot_file, dpi=150)
    plt.close(fig)
    if save_csv_file is not None:
        import csv
        with open(save_csv_file, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['antenna', 'stokes', 'component', 'ks_D_percent'])
            for i, ant in enumerate(antenna_list):
                for s in stokes_list:
                    for comp in ['real', 'imag']:
                        row = [ant, s, comp, ks[s][comp]['d'][i]]
                        writer.writerow(row)
    return output_plot_file
    
def parse_arguments():
    parser = argparse.ArgumentParser(description="Analyze and plot CASA gain table data.")
      
    parser.add_argument('--input-gain-table', type=str, default=None, help='Input gain or bandpass table path.')
    parser.add_argument('--mode', type=str, choices=['bandpass', 'gain'], default='bandpass', help='Select data source: bandpass (channels/Δc) or gain (time/τ).')
  
    parser.add_argument('--bchan', type=int, default=None, help='Beginning channel index (inclusive) for bandpass mode.')
    parser.add_argument('--echan', type=int, default=None, help='Ending channel index (exclusive) for bandpass mode.')
    parser.add_argument('--scan', type=int, default=None, help='Scan number. If omitted, run across all available scans.')
    parser.add_argument('--antmin', type=int, default=0)
    parser.add_argument('--antmax', type=int, default=30)
    parser.add_argument('--no-flags', action='store_false', dest='use_flags', default=True)
    parser.add_argument('--no-subtract-mean', action='store_true', default=False, help='Subtract mean of complex gains per antenna/stokes (real and imag separately) before computing stats.')
   
    parser.add_argument('--plot-dir', type=str, default='./plots')
    parser.add_argument('--csv-dir', type=str, default='./csvs')
    
    parser.add_argument('--s2thr', type=float, default=0.75)
    parser.add_argument('--nbin-hist', type=int, default=64)
    parser.add_argument('--nbin-sf', type=int, default=32)
    parser.add_argument('--bintype-sf', type=str, choices=['log', 'lin'], default='log')
    parser.add_argument('--njack-sf', type=int, default=32)

    parser.add_argument('--do-all', action='store_true', default=False)
    parser.add_argument('--gain-all', nargs='?', const=True, default=False)
    parser.add_argument('--gain-hist-all', nargs='?', const=True, default=False)
    parser.add_argument('--s2-all', nargs='?', const=True, default=False)
    parser.add_argument('--tcorr-all', nargs='?', const=True, default=False)
    parser.add_argument('--stats', nargs='?', const=True, default=False, help='Generate statistics plot and CSV using the default file prefix (if used as --stat), or the given prefix (if used as --stat prefix). Files go to --plot-dir/ and --csv-dir/.')
    parser.add_argument('--ks', nargs='?', const=True, default=False, help='Generate KS plot and CSV using the default file prefix (if used as --ks), or the given prefix (if used as --ks prefix). Files go to --plot-dir/ and --csv-dir/.')
    parser.add_argument('--single', nargs='*', default=False, help='[ant] [scan] [stokes] [comp] [prefix]')
  
    
    return parser.parse_args()

def main():
    args = parse_arguments()
    print(f"mode: {args.mode}")
    if args.do_all:
        args.gain_all = True
        args.gain_hist_all = True
        args.s2_all = True
        args.tcorr_all = True
        args.stats = True
        args.ks = True
        args.single = True

    if args.input_gain_table is not None:
        args_path = args.input_gain_table
    else:
        args_path = defbandpath if args.mode == 'bandpass' else defgainpath
        
    subtract_mean_Flag = not(args.no_subtract_mean)
    bandpass_mode = (args.mode == 'bandpass')
    if bandpass_mode:
        bchan = args.bchan
        echan = args.echan
    else:
        bchan = None
        echan = None
        
    for d in [args.plot_dir, args.csv_dir]: os.makedirs(d, exist_ok=True)

    
    meta = get_gain_table_metadata(args_path)
    print(meta)
    if args.scan is None:
        target_scans = list(meta['scans']) if meta['scans'] else [0]
    else:
        if args.scan not in meta['scans']:
            raise ValueError(f"Requested --scan {args.scan} not in available scans: {meta['scans']}")
        target_scans = [args.scan]
    requested_ants = sorted([ant for ant in meta['antennas'] if args.antmin <= ant < args.antmax])

    def prepare_path(arg_val, default_prefix, ext, dir_path, current_scan):
        prefix = f"{default_prefix}_scan{current_scan}" if arg_val is True else str(arg_val)
        return os.path.join(dir_path, f"{prefix}{ext}")

    def get_single_params(arg_list, meta):
        res = {
            'ant': requested_ants[0] if requested_ants else meta['antennas'][0],
            'stokes': meta['stokes'][0] if meta['stokes'] else 0,
            'comp': 'both',
            'prefix': None
        }
        if not isinstance(arg_list, list): return res
        if len(arg_list) >= 1: res['ant'] = int(arg_list[0])
        if len(arg_list) >= 2: res['stokes'] = int(arg_list[1]) if arg_list[1].isdigit() else arg_list[1]
        if len(arg_list) >= 3: res['comp'] = arg_list[2]
        if len(arg_list) >= 4: res['prefix'] = arg_list[3]
        return res

    if bandpass_mode:
        dmode = f'bpass'
        subord = f'_{bchan}' if bchan is not None else '_{0}'
        subord = subord + f'_{echan}' if echan is not None else '_all'
        dmode = dmode + subord
    else:
        dmode = 'gain'
    for target_scan in target_scans:
        print(f"Running scan: {target_scan}")
        if args.gain_all is not False:
            p = prepare_path(args.gain_all, f"{dmode}_colormap", ".png", args.plot_dir, target_scan)
            c = prepare_path(args.gain_all, f"{dmode}_colormap", ".csv", args.csv_dir, target_scan)
            plot_gain_colormap(args_path, requested_ants, scan=target_scan, output_plot_file=p, UseFlags=args.use_flags, save_csv_file=c, bandpass=bandpass_mode, bchan=bchan, echan=echan)
        if args.gain_hist_all is not False:
            p = prepare_path(args.gain_hist_all, f"{dmode}_hist", ".png", args.plot_dir, target_scan)
            c = prepare_path(args.gain_hist_all, f"{dmode}_hist", ".csv", args.csv_dir, target_scan)
            plot_gain_histogram(args_path, requested_ants, scan=target_scan, output_plot_file=p, nbin=args.nbin_hist, UseFlags=args.use_flags, save_csv_file=c, bandpass=bandpass_mode, bchan=bchan, echan=echan)
        if args.s2_all is not False:
            p = prepare_path(args.s2_all, f"{dmode}_s2_colormap", ".png", args.plot_dir, target_scan)
            c = prepare_path(args.s2_all, f"{dmode}_s2_colormap", ".npz", args.csv_dir, target_scan)
            plot_structure_function_colormap(args_path, requested_ants, scan=target_scan, S2Thr=args.s2thr, Nbin=args.nbin_sf, bintype=args.bintype_sf, output_plot_file=p, UseFlags=args.use_flags, save_npy_file=c, bandpass=bandpass_mode, bchan=bchan, echan=echan)
        
        # Kept off, need correction
        args.tcorr_all = False
        if args.tcorr_all is not False:
            p = prepare_path(args.tcorr_all, f"{dmode}_tcorr_matrices", ".png", args.plot_dir, target_scan)
            f = prepare_path(args.tcorr_all, f"{dmode}_tcorr_matrices", ".fits", args.csv_dir, target_scan)
            compute_tcorr_matrices_and_plot(args_path, target_scan, requested_ants, S2Thr=args.s2thr, Nbin=args.nbin_sf, bintype=args.bintype_sf, UseFlags=args.use_flags, output_plot_file=p, output_fits_file=f, bandpass=bandpass_mode, bchan=bchan, echan=echan)
        if args.stats is not False:
            p = prepare_path(args.stats, f"{dmode}_stats", ".png", args.plot_dir, target_scan)
            c = prepare_path(args.stats, f"{dmode}_stats", ".csv", args.csv_dir, target_scan)
            plot_antenna_gain_stats_grid(args_path, requested_ants, scan=target_scan, output_plot_file=p, UseFlags=args.use_flags, save_csv_file=c, subtract_mean=subtract_mean_Flag, bandpass=bandpass_mode, bchan=bchan, echan=echan)
        if args.ks is not False:
            p = prepare_path(args.ks, f"{dmode}_ks", ".png", args.plot_dir, target_scan)
            c = prepare_path(args.ks, f"{dmode}_ks", ".csv", args.csv_dir, target_scan)
            plot_antenna_gain_ks_grid(args_path, requested_ants, scan=target_scan, output_plot_file=p, UseFlags=args.use_flags, save_csv_file=c, bandpass=bandpass_mode, bchan=bchan, echan=echan)
     
    if args.single is not False:
        parts = args.single if isinstance(args.single, list) else []
        default_ant = requested_ants[0] if requested_ants else (meta['antennas'][0] if meta['antennas'] else 0)
        default_scan = target_scans[0] if target_scans else (meta['scans'][0] if meta['scans'] else 0)
        default_stokes = (meta['stokes'][0] if meta['stokes'] else 0)
        default_comp = 'both'
        ant = default_ant
        scan = default_scan
        stokes_val = default_stokes
        comp = default_comp
        prefix = None
        if len(parts) >= 1:
            try: ant = int(parts[0])
            except: ant = default_ant
        if len(parts) >= 2:
            try: scan = int(parts[1])
            except: scan = default_scan
        if len(parts) >= 3:
            stokes_str = parts[2]
            stokes_val = int(stokes_str) if str(stokes_str).isdigit() else stokes_str
        if len(parts) >= 4:
            comp = parts[3]
        if len(parts) >= 5:
            prefix = parts[4]
        if not prefix:
            comp_tag = comp
            prefix = f"{dmode}_single_ant{ant}_scan{scan}_stokes{stokes_val}_{comp_tag}"
        plot_path_ts = os.path.join(args.plot_dir, f"{prefix}_timeseries.png")
        csv_path_ts  = os.path.join(args.csv_dir,  f"{prefix}_timeseries.csv")
        plot_path_s2 = os.path.join(args.plot_dir, f"{prefix}_s2.png")
        csv_path_s2  = os.path.join(args.csv_dir,  f"{prefix}_s2.csv")
        plot_path_h  = os.path.join(args.plot_dir, f"{prefix}_hist.png")
        csv_path_h   = os.path.join(args.csv_dir,  f"{prefix}_hist.csv")
        if bandpass_mode:
            plot_single_antenndaBpassChennel(args_path, ant, stokes_val, scan, component=comp, UseFlags=args.use_flags, output_plot_file=plot_path_ts, bchan=bchan, echan=echan)
        else:
            plot_single_antenndaGainTime(args_path, ant, stokes_val, scan, component=comp, UseFlags=args.use_flags, output_plot_file=plot_path_ts)
        if comp == 'both':
            plot_single_structure_function(args_path, ant, stokes_val, scan, component='real', S2Thr=args.s2thr, Nbin=args.nbin_sf, bintype=args.bintype_sf, UseFlags=args.use_flags, output_plot_file=plot_path_s2, NJack=args.njack_sf, bandpass=bandpass_mode, bchan=bchan, echan=echan)
            plot_single_histogram(args_path, ant, stokes_val, scan, component='real', nbin=args.nbin_hist, hist_range=None, UseFlags=args.use_flags, output_plot_file=plot_path_h)
            plot_single_structure_function(args_path, ant, stokes_val, scan, component='imag', S2Thr=args.s2thr, Nbin=args.nbin_sf, bintype=args.bintype_sf, UseFlags=args.use_flags, output_plot_file=plot_path_s2, NJack=args.njack_sf, bandpass=bandpass_mode, bchan=bchan, echan=echan)
            plot_single_histogram(args_path, ant, stokes_val, scan, component='imag', nbin=args.nbin_hist, hist_range=None, UseFlags=args.use_flags, output_plot_file=plot_path_h)
        else:
            plot_single_structure_function(args_path, ant, stokes_val, scan, component=comp, S2Thr=args.s2thr, Nbin=args.nbin_sf, bintype=args.bintype_sf, UseFlags=args.use_flags, output_plot_file=plot_path_s2, NJack=args.njack_sf, bandpass=bandpass_mode, bchan=bchan, echan=echan)
            plot_single_histogram(args_path, ant, stokes_val, scan, component=comp, nbin=args.nbin_hist, hist_range=None, UseFlags=args.use_flags, output_plot_file=plot_path_h)
        #print(f"Saved single plots with prefix '{prefix}' to {args.plot_dir} and CSVs to {args.csv_dir}")

if __name__ == "__main__":
    main()
