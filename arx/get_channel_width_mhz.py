#!/usr/bin/env python3
import argparse
import os
from typing import Optional

import numpy as np

try:
    from casatools import table as casatable
except Exception as exc:
    raise RuntimeError("Could not import casatools.table. Run inside CASA/casa6.") from exc


def _open_table_for_spw(input_path: str) -> str:
    """Prefer SPECTRAL_WINDOW subtable when present."""
    spw = os.path.join(input_path, "SPECTRAL_WINDOW")
    if os.path.isdir(spw):
        return spw
    return input_path


def _get_channel_width_hz(path: str) -> np.ndarray:
    tb = casatable()
    tb.open(path)
    try:
        cols = tb.colnames()
        if "CHANNEL_WIDTH" in cols:
            cw = np.asarray(tb.getcol("CHANNEL_WIDTH"), dtype=float)
            return np.abs(cw).ravel()

        if "CHAN_WIDTH" in cols:
            cw = np.asarray(tb.getcol("CHAN_WIDTH"), dtype=float)
            return np.abs(cw).ravel()

        if "CHAN_FREQ" in cols:
            cf = np.asarray(tb.getcol("CHAN_FREQ"), dtype=float)
            cf = cf.reshape((-1, cf.shape[-1])) if cf.ndim > 1 else cf.reshape((-1, 1))
            diffs = np.abs(np.diff(cf, axis=0)).ravel()
            return diffs

        raise RuntimeError(
            f"No CHANNEL_WIDTH/CHAN_WIDTH/CHAN_FREQ columns in table: {path}"
        )
    finally:
        tb.close()


def _fmt(v: float) -> str:
    return f"{v:.6g}"


def main() -> None:
    p = argparse.ArgumentParser(description="Find channel width in MHz from CASA table/MS.")
    p.add_argument("--input-table", required=True, help="Input MS/CASA table path")
    args = p.parse_args()

    in_path = os.path.abspath(args.input_table)
    if not os.path.isdir(in_path):
        raise FileNotFoundError(f"Not found: {in_path}")

    tab = _open_table_for_spw(in_path)
    widths_hz = _get_channel_width_hz(tab)
    widths_hz = widths_hz[np.isfinite(widths_hz) & (widths_hz > 0)]
    if widths_hz.size == 0:
        raise RuntimeError(f"No valid positive channel widths found in: {tab}")

    widths_mhz = widths_hz / 1e6
    print(f"Input: {in_path}")
    print(f"Table used: {tab}")
    print(f"n_width: {widths_mhz.size}")
    print(f"channel_width_mhz_mean: {_fmt(float(np.mean(widths_mhz)))}")
    print(f"channel_width_mhz_min:  {_fmt(float(np.min(widths_mhz)))}")
    print(f"channel_width_mhz_max:  {_fmt(float(np.max(widths_mhz)))}")


if __name__ == "__main__":
    main()
