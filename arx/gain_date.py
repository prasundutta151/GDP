#!/usr/bin/env python3
"""
Get IST observing day(s) from a CASA gain table (e.g., *.gcal, *.K, *.G, *.B).
Assumes TIME column is in seconds since MJD 0 (CASA standard).
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import List, Tuple
import numpy as np

try:
    from casatools import table as casatable
except Exception as e:
    casatable = None


IST = timezone(timedelta(hours=5, minutes=30))
MJD0_UTC = datetime(1858, 11, 17, 0, 0, 0, tzinfo=timezone.utc)


@dataclass(frozen=True)
class ISTDayInfo:
    ist_dates: List[str]          # e.g. ["2017-05-04", "2017-05-05"]
    ist_time_range: Tuple[str, str]  # ("YYYY-MM-DD HH:MM:SS.sss", "...")

def _mjdsec_to_utc_dt(mjd_seconds: float) -> datetime:
    # CASA TIME is seconds since MJD0 (1858-11-17 UTC)
    return MJD0_UTC + timedelta(seconds=float(mjd_seconds))

def gain_table_ist_days(gain_table_path: str) -> ISTDayInfo:
    """
    Read TIME column from a CASA gain table and report observing IST day(s).

    Returns:
        ISTDayInfo with list of IST dates and overall IST time range.
    """
    if casatable is None:
        raise RuntimeError(
            "casatools.table not available. Run inside CASA Python or a CASA-enabled env."
        )

    tb = casatable()
    tb.open(gain_table_path)
    try:
        colnames = tb.colnames()
        if "TIME" not in colnames:
            raise KeyError(f"TIME column not found. Available columns: {colnames}")

        t = tb.getcol("TIME").astype(np.float64).ravel()
        if t.size == 0:
            raise ValueError("TIME column is empty.")

    finally:
        tb.close()

    # Convert min/max to IST for the overall span
    tmin_utc = _mjdsec_to_utc_dt(np.min(t))
    tmax_utc = _mjdsec_to_utc_dt(np.max(t))
    tmin_ist = tmin_utc.astimezone(IST)
    tmax_ist = tmax_utc.astimezone(IST)

    # Convert all times to IST dates (YYYY-MM-DD), unique sorted
    # Vectorize by converting to UTC epoch seconds then to dates via datetime (loop is fine; sizes are not huge)
    ist_dates = sorted({(_mjdsec_to_utc_dt(x).astimezone(IST)).date().isoformat() for x in t})

    def fmt(dt: datetime) -> str:
        # keep milliseconds
        return dt.strftime("%Y-%m-%d %H:%M:%S.") + f"{int(dt.microsecond/1000):03d}"

    return ISTDayInfo(
        ist_dates=ist_dates,
        ist_time_range=(fmt(tmin_ist), fmt(tmax_ist)),
    )


# Optional CLI usage
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Report IST observing day(s) from a CASA gain table.")
    parser.add_argument("gain_table", help="Path to CASA gain table (e.g., *.gcal, *.K, *.G)")
    args = parser.parse_args()

    info = gain_table_ist_days(args.gain_table)
    print("IST date(s):", ", ".join(info.ist_dates))
    print("IST time span:", info.ist_time_range[0], "to", info.ist_time_range[1])
