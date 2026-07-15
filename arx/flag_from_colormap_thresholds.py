#!/usr/bin/env python3
import argparse
import ast
import os
import shutil
from typing import Optional, Sequence

import numpy as np

try:
    from casatools import table as casatable
except Exception as exc:
    raise RuntimeError("Could not import casatools.table. Run inside CASA/casa6.") from exc


def _pick_data_column(colnames: Sequence[str], mode: str) -> str:
    if mode == "gain":
        if "GAIN" in colnames:
            return "GAIN"
        if "CPARAM" in colnames:
            return "CPARAM"
        raise RuntimeError("Gain mode requires GAIN or CPARAM column.")
    if mode == "bandpass":
        if "CPARAM" in colnames:
            return "CPARAM"
        if "FPARAM" in colnames:
            return "FPARAM"
        raise RuntimeError("Bandpass mode requires CPARAM or FPARAM column.")
    raise ValueError(f"Unsupported mode: {mode}")


def _parse_scan_list(text: Optional[str]) -> Optional[np.ndarray]:
    if text is None:
        return None
    t = str(text).strip()
    if t == "":
        return None
    vals = []
    for part in t.split(","):
        p = part.strip()
        if p == "":
            continue
        vals.append(int(p))
    if not vals:
        return None
    return np.asarray(sorted(set(vals)), dtype=int)


def _parse_threshold_schedule(text: Optional[str]) -> Sequence[float]:
    default_schedule = (7.0, 7.0, 6.0, 6.0, 5.0, 5.0, 4.0, 4.0)
    if text is None:
        return default_schedule
    t = str(text).strip()
    if t == "":
        return default_schedule

    # Accept Python literals like "(7,7,6,6)" or "[7,7,6,6]"
    try:
        parsed = ast.literal_eval(t)
    except Exception as exc:
        raise ValueError(
            f"Could not parse --threshold-schedule '{text}'. "
            "Use tuple/list form, e.g. '(7,7,6,6,5,5,4,4)'."
        ) from exc

    if not isinstance(parsed, (list, tuple)) or len(parsed) == 0:
        raise ValueError("--threshold-schedule must be a non-empty tuple/list of numbers.")

    out = []
    for i, v in enumerate(parsed):
        try:
            fv = float(v)
        except Exception as exc:
            raise ValueError(f"Invalid threshold at index {i}: {v!r}") from exc
        if fv <= 0:
            raise ValueError(f"Threshold at index {i} must be > 0, got {fv}")
        out.append(fv)
    return tuple(out)


def _parse_float_tuple(text: Optional[str]) -> Optional[Sequence[float]]:
    if text is None:
        return None
    t = str(text).strip()
    if t == "":
        return None
    try:
        parsed = ast.literal_eval(t)
    except Exception as exc:
        raise ValueError(
            f"Could not parse tuple/list from '{text}'. Use form like '(10,12)' or '[10,12]'."
        ) from exc
    if not isinstance(parsed, (list, tuple)) or len(parsed) == 0:
        raise ValueError("Expected non-empty tuple/list of numbers.")
    out = []
    for i, v in enumerate(parsed):
        try:
            fv = float(v)
        except Exception as exc:
            raise ValueError(f"Invalid numeric value at index {i}: {v!r}") from exc
        if fv < 0:
            raise ValueError(f"Threshold at index {i} must be >= 0, got {fv}")
        out.append(fv)
    return tuple(out)


def _prepare_output_table(input_table: str, output_table: str, if_exists: str) -> None:
    if not os.path.isdir(input_table):
        raise FileNotFoundError(f"Input table not found: {input_table}")
    if if_exists not in {"error", "overwrite", "modify"}:
        raise ValueError(f"Unsupported --if-exists: {if_exists}")

    if not os.path.exists(output_table):
        shutil.copytree(input_table, output_table)
        return
    if if_exists == "error":
        raise FileExistsError(f"Output table already exists: {output_table}")
    if if_exists == "overwrite":
        shutil.rmtree(output_table)
        shutil.copytree(input_table, output_table)
        return
    if if_exists == "modify":
        if not os.path.isdir(output_table):
            raise NotADirectoryError(f"Output path exists but is not a directory: {output_table}")
        return


def _copy_all_subdirs(src_path: str, dst_path: str) -> None:
    if not os.path.isdir(src_path):
        raise FileNotFoundError(f"Source path not found: {src_path}")
    os.makedirs(dst_path, exist_ok=True)
    for item in os.listdir(src_path):
        src_item = os.path.join(src_path, item)
        dst_item = os.path.join(dst_path, item)
        if os.path.isdir(src_item):
            shutil.copytree(src_item, dst_item, dirs_exist_ok=True)


def _component_threshold(mean_val: float, std_val: float, mean_k: float, std_k: float, eps: float = 1e-9) -> float:
    base_mean = abs(mean_val)
    return mean_k * max(base_mean, eps) + std_k * max(std_val, 0.0)


def _weighted_mean_std(values: np.ndarray, weights: np.ndarray) -> tuple[float, float]:
    wsum = float(np.sum(weights))
    if wsum <= 0:
        return np.nan, np.nan
    mean = float(np.sum(weights * values) / wsum)
    var = float(np.sum(weights * (values - mean) ** 2) / wsum)
    return mean, float(np.sqrt(max(var, 0.0)))


def _whole_antenna_outlier_mask(
    real_pct: np.ndarray,
    imag_pct: np.ndarray,
    updated_flag: np.ndarray,
    ant1: np.ndarray,
    target_rows: np.ndarray,
    ants: np.ndarray,
    use_real: bool,
    use_imag: bool,
    whole_ant_k: float,
) -> np.ndarray:
    """
    Return row-level mask for antennas whose weighted std/|mean| is far from global.
    Weighting is by number of unflagged finite samples per antenna.
    """
    npol, nchan, nrow = updated_flag.shape
    row_mask_2d = np.broadcast_to(target_rows[np.newaxis, :], (nchan, nrow))
    ant_cv: list[float] = []
    ant_w: list[float] = []
    ant_ids: list[int] = []

    components = []
    if use_real:
        components.append(real_pct)
    if use_imag:
        components.append(imag_pct)

    for ant in ants:
        ant_rows = (ant1 == ant) & target_rows
        if not np.any(ant_rows):
            continue
        ant_mask_2d = np.broadcast_to(ant_rows[np.newaxis, :], (nchan, nrow))
        cvs: list[float] = []
        ws: list[float] = []
        for p in range(npol):
            for comp_vals in components:
                plane = comp_vals[p, :, :]
                valid = (~updated_flag[p, :, :]) & ant_mask_2d & np.isfinite(plane)
                vals = plane[valid]
                if vals.size < 2:
                    continue
                m = float(np.mean(vals))
                s = float(np.std(vals, ddof=0))
                cv = s / max(abs(m), 1e-9)
                cvs.append(cv)
                ws.append(float(vals.size))
        if len(cvs) == 0:
            continue
        c = np.asarray(cvs, dtype=float)
        w = np.asarray(ws, dtype=float)
        ant_cv_val, _ = _weighted_mean_std(c, w)
        ant_cv.append(ant_cv_val)
        ant_w.append(float(np.sum(w)))
        ant_ids.append(int(ant))

    if len(ant_cv) < 2:
        return np.zeros(nrow, dtype=bool)

    cv_arr = np.asarray(ant_cv, dtype=float)
    w_arr = np.asarray(ant_w, dtype=float)
    g_mean, g_std = _weighted_mean_std(cv_arr, w_arr)
    if not np.isfinite(g_mean) or not np.isfinite(g_std):
        return np.zeros(nrow, dtype=bool)

    outlier_ant_rows = np.zeros(nrow, dtype=bool)
    for ant, cv in zip(ant_ids, cv_arr):
        if abs(cv - g_mean) > whole_ant_k * max(g_std, 1e-9):
            outlier_ant_rows |= (ant1 == ant) & target_rows
    return outlier_ant_rows


def _low_remaining_mask(
    current_flag: np.ndarray,
    ant1: np.ndarray,
    target_rows: np.ndarray,
    ants: np.ndarray,
    min_remaining_pct: Optional[float],
    min_remaining_pct_by_stokes: Optional[Sequence[float]],
) -> np.ndarray:
    """
    Flag full antenna blocks per stokes if remaining unflagged percentage is too low.
    This is stokes-specific and therefore identical for real/imag within same stokes.
    """
    npol, nchan, nrow = current_flag.shape
    out = np.zeros_like(current_flag, dtype=bool)

    def _thr_for_stokes(p: int) -> Optional[float]:
        if min_remaining_pct_by_stokes is not None:
            if len(min_remaining_pct_by_stokes) == 0:
                return None
            idx = p if p < len(min_remaining_pct_by_stokes) else len(min_remaining_pct_by_stokes) - 1
            return float(min_remaining_pct_by_stokes[idx])
        if min_remaining_pct is None:
            return None
        return float(min_remaining_pct)

    for p in range(npol):
        thr = _thr_for_stokes(p)
        if thr is None or thr <= 0:
            continue
        for ant in ants:
            ant_rows = (ant1 == ant) & target_rows
            nr = int(np.count_nonzero(ant_rows))
            if nr == 0:
                continue
            total = nchan * nr
            rem = int(np.count_nonzero(~current_flag[p, :, ant_rows]))
            rem_pct = 100.0 * (rem / float(total))
            if rem_pct < thr:
                out[p, :, ant_rows] = True

    return out


def _iterative_flagging(
    real_pct: np.ndarray,
    imag_pct: np.ndarray,
    flag: np.ndarray,
    ant1: np.ndarray,
    target_rows: np.ndarray,
    global_mean_k: float,
    global_std_k: float,
    ant_mean_k: float,
    min_new_flag_pct: float,
    max_rounds: int,
    use_real: bool,
    use_imag: bool,
    threshold_schedule: Sequence[float],
    global_only: bool,
    whole_ant_enable: bool,
    whole_ant_k: float,
    min_remaining_pct: Optional[float],
    min_remaining_pct_by_stokes: Optional[Sequence[float]],
) -> tuple[np.ndarray, list[tuple[int, int, float]]]:
    npol, nchan, nrow = flag.shape
    row_mask_2d = np.broadcast_to(target_rows[np.newaxis, :], (nchan, nrow))
    target_total = int(np.count_nonzero(row_mask_2d)) * npol
    if target_total == 0:
        return flag.copy(), []

    ants = np.unique(ant1[target_rows])
    updated = flag.copy()
    history: list[tuple[int, int, float]] = []

    components = []
    if use_real:
        components.append(real_pct)
    if use_imag:
        components.append(imag_pct)

    for r in range(1, max_rounds + 1):
        sch_idx = min(r - 1, len(threshold_schedule) - 1)
        k_round = float(threshold_schedule[sch_idx])
        round_new = np.zeros_like(updated, dtype=bool)

        # Optional whole-antenna flagging based on weighted std/|mean| outliers.
        if whole_ant_enable:
            bad_rows = _whole_antenna_outlier_mask(
                real_pct=real_pct,
                imag_pct=imag_pct,
                updated_flag=updated,
                ant1=ant1,
                target_rows=target_rows,
                ants=ants,
                use_real=use_real,
                use_imag=use_imag,
                whole_ant_k=whole_ant_k,
            )
            if np.any(bad_rows):
                bad_mask_2d = np.broadcast_to(bad_rows[np.newaxis, :], (nchan, nrow))
                for p in range(npol):
                    to_flag_whole = (~updated[p, :, :]) & bad_mask_2d
                    round_new[p, :, :] |= to_flag_whole

        for p in range(npol):
            for comp_vals in components:
                plane = comp_vals[p, :, :]
                valid = (~updated[p, :, :]) & row_mask_2d & np.isfinite(plane)
                vals = plane[valid]
                if vals.size == 0:
                    continue

                g_mean = float(np.mean(vals))
                g_std = float(np.std(vals, ddof=0))
                g_mean_k_use = global_mean_k if global_mean_k is not None else k_round
                g_std_k_use = global_std_k if global_std_k is not None else k_round
                ant_mean_k_use = ant_mean_k if ant_mean_k is not None else k_round

                g_thr = _component_threshold(g_mean, g_std, g_mean_k_use, g_std_k_use)
                global_out = (np.abs(plane - g_mean) > g_thr) & row_mask_2d & np.isfinite(plane)

                ant_out = np.zeros_like(global_out, dtype=bool)
                if not global_only:
                    for ant in ants:
                        ant_rows = (ant1 == ant) & target_rows
                        if not np.any(ant_rows):
                            continue
                        ant_mask_2d = np.broadcast_to(ant_rows[np.newaxis, :], (nchan, nrow))
                        ant_valid = (~updated[p, :, :]) & ant_mask_2d & np.isfinite(plane)
                        avals = plane[ant_valid]
                        if avals.size == 0:
                            continue
                        a_mean = float(np.mean(avals))
                        a_thr = ant_mean_k_use * max(abs(a_mean), 1e-9)
                        ant_out |= (np.abs(plane - a_mean) > a_thr) & ant_mask_2d & np.isfinite(plane)

                to_flag = (~updated[p, :, :]) & (global_out | ant_out) & row_mask_2d
                round_new[p, :, :] |= to_flag

        # Optional: flag full antenna blocks if remaining percentage is too low.
        if (min_remaining_pct is not None and min_remaining_pct > 0) or (
            min_remaining_pct_by_stokes is not None and len(min_remaining_pct_by_stokes) > 0
        ):
            tmp_flag = updated | round_new
            low_rem_mask = _low_remaining_mask(
                current_flag=tmp_flag,
                ant1=ant1,
                target_rows=target_rows,
                ants=ants,
                min_remaining_pct=min_remaining_pct,
                min_remaining_pct_by_stokes=min_remaining_pct_by_stokes,
            )
            round_new |= (~updated) & low_rem_mask

        new_count = int(np.count_nonzero(round_new))
        new_pct = 100.0 * (new_count / float(target_total))
        history.append((r, new_count, new_pct))
        if new_count == 0:
            break

        updated[round_new] = True
        if new_pct < min_new_flag_pct:
            break

    return updated, history


def flag_table_from_colormap_thresholds(
    input_table: str,
    output_table: str,
    mode: str = "gain",
    bchan: Optional[int] = None,
    echan: Optional[int] = None,
    scans: Optional[Sequence[int]] = None,
    global_mean_k: Optional[float] = None,
    global_std_k: Optional[float] = None,
    ant_mean_k: Optional[float] = None,
    min_new_flag_pct: float = 0.05,
    max_rounds: int = 8,
    if_exists: str = "overwrite",
    use_real: bool = True,
    use_imag: bool = True,
    threshold_schedule: Sequence[float] = (7.0, 7.0, 6.0, 6.0, 5.0, 5.0, 4.0, 4.0),
    global_only: bool = False,
    whole_ant_enable: bool = False,
    whole_ant_k: float = 3.0,
    min_remaining_pct: Optional[float] = 25.0,
    min_remaining_pct_by_stokes: Optional[Sequence[float]] = None,
) -> None:
    """
    Read gain/bandpass table, compute colormap-like values
      real_pct = (real - 1)*100, imag_pct = imag*100
    and perform iterative threshold flagging:
      - Global threshold uses both mean and std terms.
      - Per-antenna threshold uses mean term only.
    Flags are written to output_table.
    """
    if not use_real and not use_imag:
        raise ValueError("At least one component must be enabled (--use-real and/or --use-imag).")
    if len(threshold_schedule) == 0:
        raise ValueError("threshold_schedule must contain at least one value.")

    _prepare_output_table(input_table, output_table, if_exists)

    tb = casatable()
    tb.open(input_table, nomodify=True)
    try:
        cols = tb.colnames()
        data_col = _pick_data_column(cols, mode)
        if "FLAG" not in cols:
            raise RuntimeError("Input table has no FLAG column.")
        if "ANTENNA1" not in cols:
            raise RuntimeError("Input table has no ANTENNA1 column.")

        data = tb.getcol(data_col)
        flag = tb.getcol("FLAG")
        ant1 = tb.getcol("ANTENNA1")
        scan_col = tb.getcol("SCAN_NUMBER") if "SCAN_NUMBER" in cols else np.zeros(tb.nrows(), dtype=int)
    finally:
        tb.close()

    if data.ndim != 3 or flag.ndim != 3:
        raise RuntimeError(
            f"Expected data and FLAG shape (npol,nchan,nrow). Got {data.shape} and {flag.shape}"
        )
    if data.shape != flag.shape:
        if data.shape[0] != flag.shape[0] or data.shape[2] != flag.shape[2]:
            raise RuntimeError(f"Data shape {data.shape} does not match FLAG shape {flag.shape}")
        nchan_common = min(int(data.shape[1]), int(flag.shape[1]))
        if nchan_common <= 0:
            raise RuntimeError(f"No common channels between data {data.shape} and FLAG {flag.shape}")
        print(
            f"Warning: channel mismatch data={data.shape[1]} vs flag={flag.shape[1]}; "
            f"using first {nchan_common} channels."
        )
        data = data[:, :nchan_common, :]
        flag = flag[:, :nchan_common, :]

    if not np.iscomplexobj(data):
        data = data.astype(float) + 0j
    if flag.dtype != np.bool_:
        flag = flag.astype(bool, copy=False)

    if mode == "bandpass":
        _b0 = 0 if bchan is None else int(bchan)
        _b1 = int(data.shape[1]) if echan is None else int(echan)
        if _b0 < 0 or _b1 <= _b0 or _b1 > int(data.shape[1]):
            raise ValueError(
                f"Invalid channel range for bandpass mode: bchan={bchan}, echan={echan}, "
                f"available nchan={data.shape[1]}"
            )
        data = data[:, _b0:_b1, :]
        flag = flag[:, _b0:_b1, :]

    real_pct = (data.real - 1.0) * 100.0
    imag_pct = data.imag * 100.0

    if scans is None:
        scan_list = np.unique(scan_col).tolist()
    else:
        scan_list = sorted(set(int(s) for s in scans))

    updated_flag = flag.copy()
    history_by_scan: dict[int, list[tuple[int, int, float]]] = {}
    per_scan_stats: dict[int, tuple[float, float, float]] = {}
    for sc in scan_list:
        target_rows = scan_col == sc
        if not np.any(target_rows):
            history_by_scan[int(sc)] = []
            per_scan_stats[int(sc)] = (0.0, 0.0, 0.0)
            continue

        npol, nchan, _ = updated_flag.shape
        target_elems = int(np.count_nonzero(target_rows)) * nchan * npol
        before_count = int(np.count_nonzero(flag[:, :, target_rows]))
        updated_flag, hist = _iterative_flagging(
            real_pct=real_pct,
            imag_pct=imag_pct,
            flag=updated_flag,
            ant1=ant1,
            target_rows=target_rows,
            global_mean_k=global_mean_k,
            global_std_k=global_std_k,
            ant_mean_k=ant_mean_k,
            min_new_flag_pct=min_new_flag_pct,
            max_rounds=max_rounds,
            use_real=use_real,
            use_imag=use_imag,
            threshold_schedule=threshold_schedule,
            global_only=global_only,
            whole_ant_enable=whole_ant_enable,
            whole_ant_k=whole_ant_k,
            min_remaining_pct=min_remaining_pct,
            min_remaining_pct_by_stokes=min_remaining_pct_by_stokes,
        )
        history_by_scan[int(sc)] = hist
        after_count = int(np.count_nonzero(updated_flag[:, :, target_rows]))
        new_count = max(after_count - before_count, 0)
        if target_elems > 0:
            before_pct = 100.0 * before_count / float(target_elems)
            after_pct = 100.0 * after_count / float(target_elems)
            new_pct = 100.0 * new_count / float(target_elems)
        else:
            before_pct = 0.0
            after_pct = 0.0
            new_pct = 0.0
        per_scan_stats[int(sc)] = (before_pct, after_pct, new_pct)

    tb_out = casatable()
    tb_out.open(output_table, nomodify=False)
    try:
        tb_out.putcol("FLAG", updated_flag)
    finally:
        tb_out.close()

    # Ensure all table subdirectories from input are present in output.
    _copy_all_subdirs(input_table, output_table)

    total_before = int(np.count_nonzero(flag))
    total_after = int(np.count_nonzero(updated_flag))
    total_new = total_after - total_before

    print(f"Input table:  {input_table}")
    print(f"Output table: {output_table}")
    print(f"Mode: {mode}")
    print(f"Flagging mode: {'global-only' if global_only else 'global+per-antenna'}")
    print(f"Whole-antenna outlier mode: {'on' if whole_ant_enable else 'off'} (k={whole_ant_k})")
    print(
        f"Low-remaining mode: min_remaining_pct={min_remaining_pct}, "
        f"by_stokes={tuple(min_remaining_pct_by_stokes) if min_remaining_pct_by_stokes is not None else None}"
    )
    print(f"Scans processed: {scan_list}")
    print("Round summary per scan (round, newly_flagged, newly_flagged_pct_of_target):")
    for sc in scan_list:
        print(f"  Scan {sc}:")
        hist = history_by_scan.get(int(sc), [])
        if not hist:
            print("     no matching rows")
            continue
        for rr, cnt, pct in hist:
            print(f"    {rr:2d}: {cnt:8d}, {pct:8.4f}%")
        b, a, n = per_scan_stats.get(int(sc), (0.0, 0.0, 0.0))
        print(f"    flagged pct (before/after/new): {b:.4f}% / {a:.4f}% / {n:.4f}%")
    print(f"Total newly flagged elements: {total_new}")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Threshold-based iterative flagging from gain/bandpass colormap-like values. "
            "Global threshold uses mean+std terms; per-antenna threshold uses mean term."
        )
    )
    p.add_argument("input_table", nargs="?", default=None, help="Input gain/bandpass CASA table (positional, optional)")
    p.add_argument("output_table", nargs="?", default=None, help="Output table path (positional, optional)")
    p.add_argument("--input-gain-table", default=None, help="Input gain/bandpass CASA table")
    p.add_argument("--output-gain-table", default=None, help="Output table path to write updated FLAG column")
    p.add_argument("--mode", choices=["gain", "bandpass"], default="gain", help="Table mode")
    p.add_argument("--bchan", type=int, default=None, help="Bandpass mode: starting channel (inclusive)")
    p.add_argument("--echan", type=int, default=None, help="Bandpass mode: ending channel (exclusive)")
    p.add_argument(
        "--scans",
        default=None,
        help="Comma-separated scans to process (default: all), e.g. 1,2,5",
    )
    p.add_argument(
        "--global-mean-k",
        type=float,
        default=None,
        help="Global mean coefficient (default: per-round schedule 7,7,6,6,5,5,4,4).",
    )
    p.add_argument(
        "--global-std-k",
        type=float,
        default=None,
        help="Global std coefficient (default: per-round schedule 7,7,6,6,5,5,4,4).",
    )
    p.add_argument(
        "--ant-mean-k",
        type=float,
        default=None,
        help="Per-antenna mean coefficient (default: per-round schedule 7,7,6,6,5,5,4,4).",
    )
    p.add_argument(
        "--min-new-flag-pct",
        type=float,
        default=0.05,
        help="Stop when a round adds less than this percentage of target elements",
    )
    p.add_argument("--max-rounds", type=int, default=8, help="Maximum number of flagging rounds")
    p.add_argument(
        "--if-exists",
        choices=["error", "overwrite", "modify"],
        default="overwrite",
        help="Behavior if output table exists",
    )
    p.add_argument(
        "--use-real",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use real component for thresholding (default: true)",
    )
    p.add_argument(
        "--use-imag",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use imag component for thresholding (default: true)",
    )
    p.add_argument(
        "--global-only",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "If enabled, flagging uses only global statistics recalculated before each round "
            "(disables per-antenna thresholding)."
        ),
    )
    p.add_argument(
        "--threshold-schedule",
        default=None,
        help=(
            "Tuple/list of per-round thresholds used by default logic, "
            "e.g. '(7,7,6,6,5,5,4,4)'. "
            "If provided, this schedule is used (unless per-term fixed k overrides are set)."
        ),
    )
    p.add_argument(
        "--whole-ant-enable",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "Enable whole-antenna flagging using weighted std/|mean| distance from global "
            "computed just before each round."
        ),
    )
    p.add_argument(
        "--whole-ant-k",
        type=float,
        default=3.0,
        help="Sigma-like multiplier for whole-antenna outlier test (default: 3.0).",
    )
    p.add_argument(
        "--min-remaining-pct",
        type=float,
        default=25.0,
        help=(
            "If remaining unflagged percentage for an antenna+stokes falls below this, "
            "flag that full antenna+stokes block."
        ),
    )
    p.add_argument(
        "--min-remaining-pct-by-stokes",
        default=None,
        help=(
            "Tuple/list thresholds by stokes index, e.g. '(10,15)'. "
            "Overrides --min-remaining-pct per stokes."
        ),
    )
    return p


def main() -> None:
    args = _build_parser().parse_args()
    input_table = args.input_gain_table if args.input_gain_table is not None else args.input_table
    output_table = args.output_gain_table if args.output_gain_table is not None else args.output_table
    if input_table is None or output_table is None:
        raise ValueError(
            "Provide input/output table via --input-gain-table and --output-gain-table "
            "or via positional input_table output_table."
        )
    scans = _parse_scan_list(args.scans)
    threshold_schedule = _parse_threshold_schedule(args.threshold_schedule)
    min_remaining_pct_by_stokes = _parse_float_tuple(args.min_remaining_pct_by_stokes)
    flag_table_from_colormap_thresholds(
        input_table=input_table,
        output_table=output_table,
        mode=args.mode,
        bchan=args.bchan,
        echan=args.echan,
        scans=scans.tolist() if scans is not None else None,
        global_mean_k=args.global_mean_k,
        global_std_k=args.global_std_k,
        ant_mean_k=args.ant_mean_k,
        min_new_flag_pct=args.min_new_flag_pct,
        max_rounds=args.max_rounds,
        if_exists=args.if_exists,
        use_real=args.use_real,
        use_imag=args.use_imag,
        threshold_schedule=threshold_schedule,
        global_only=args.global_only,
        whole_ant_enable=args.whole_ant_enable,
        whole_ant_k=args.whole_ant_k,
        min_remaining_pct=args.min_remaining_pct,
        min_remaining_pct_by_stokes=min_remaining_pct_by_stokes,
    )


if __name__ == "__main__":
    main()
