#!/usr/bin/env python3
import argparse
import csv
import math
import os
import re
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import numpy as np


METRICS = ["mean", "std", "skew", "kurt"]


def _find_column(fieldnames: List[str], target: str) -> Optional[str]:
    target_l = target.strip().lower()
    for name in fieldnames:
        if name.strip().lower() == target_l:
            return name
    return None


def _parse_float(value: str) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    try:
        out = float(text)
    except ValueError:
        return None
    if math.isnan(out):
        return None
    return out


def _extract_scan_from_filename(path: str) -> Optional[int]:
    fname = os.path.basename(path)
    match = re.search(r"scan[_-]?(\d+)", fname, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def _discover_scan_csvs(
    path: str,
    mode: str = "gain",
    bchan: Optional[int] = None,
    echan: Optional[int] = None,
) -> List[str]:
    """
    Find files named like:
      - gain mode: gain_stats_scan#.csv
      - bandpass mode:
          bpass_<bchan>_<echan>_stats_scan#.csv (when bchan/echan provided)
          else bpass_*_stats_scan#.csv
    If path is a directory, scan it.
    If path is a file, scan its parent directory.
    """
    if os.path.isdir(path):
        base_dir = path
    else:
        base_dir = os.path.dirname(path) or "."

    out: List[Tuple[int, str]] = []
    if mode == "gain":
        patterns = [re.compile(r"^gain_stats_scan[_-]?(\d+)\.csv$", flags=re.IGNORECASE)]
    elif mode == "bandpass":
        if bchan is not None and echan is not None:
            patterns = [
                re.compile(
                    rf"^bpass_{int(bchan)}_{int(echan)}_stats_scan[_-]?(\d+)\.csv$",
                    flags=re.IGNORECASE,
                )
            ]
        else:
            patterns = [
                re.compile(r"^bpass_stats_scan[_-]?(\d+)\.csv$", flags=re.IGNORECASE),
                re.compile(r"^bpass_\d+_\d+_stats_scan[_-]?(\d+)\.csv$", flags=re.IGNORECASE),
            ]
    else:
        raise ValueError(f"Unsupported mode: {mode}")

    for name in os.listdir(base_dir):
        matched = False
        for patt in patterns:
            m = patt.match(name)
            if m:
                scan_id = int(m.group(1))
                out.append((scan_id, os.path.join(base_dir, name)))
                matched = True
                break
        if matched:
            continue

    out.sort(key=lambda x: (x[0], x[1]))
    return [p for _, p in out]


def summarize_gain_stats(input_csv: str) -> Tuple[List[Dict[str, object]], Optional[int]]:
    with open(input_csv, "r", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("Input CSV has no header.")

        fieldnames = reader.fieldnames
        stokes_col = _find_column(fieldnames, "stokes")
        component_col = _find_column(fieldnames, "component")
        antenna_col = _find_column(fieldnames, "antenna")
        metric_cols = {m: _find_column(fieldnames, m) for m in METRICS}

        missing = []
        if stokes_col is None:
            missing.append("stokes")
        if component_col is None:
            missing.append("component")
        if antenna_col is None:
            missing.append("antenna")
        for m, col in metric_cols.items():
            if col is None:
                missing.append(m)
        if missing:
            raise ValueError(f"Missing required columns: {', '.join(missing)}")

        grouped: Dict[Tuple[str, str], Dict[str, List[float]]] = defaultdict(
            lambda: {m: [] for m in METRICS}
        )
        stokes_valid_antennas: Dict[str, set] = defaultdict(set)

        for row in reader:
            stokes = str(row.get(stokes_col, "")).strip()
            component = str(row.get(component_col, "")).strip()
            antenna = str(row.get(antenna_col, "")).strip()
            key = (stokes, component)
            row_has_valid = False
            for m in METRICS:
                val = _parse_float(row.get(metric_cols[m], ""))
                if val is not None:
                    grouped[key][m].append(val)
                    row_has_valid = True
            if row_has_valid and antenna != "":
                stokes_valid_antennas[stokes].add(antenna)

    scan_id = _extract_scan_from_filename(input_csv)

    summary_rows: List[Dict[str, object]] = []
    for (stokes, component), metric_map in sorted(grouped.items(), key=lambda x: (x[0][0], x[0][1])):
        out: Dict[str, object] = {"stokes": stokes, "component": component}
        if scan_id is not None:
            out["scan"] = scan_id
        out["stokes_n"] = int(len(stokes_valid_antennas.get(stokes, set())))

        for m in METRICS:
            vals = np.asarray(metric_map[m], dtype=float)
            if vals.size == 0:
                out[f"{m}_mean"] = np.nan
                out[f"{m}_std"] = np.nan
            else:
                out[f"{m}_mean"] = float(np.mean(vals))
                out[f"{m}_std"] = float(np.std(vals, ddof=0))

        summary_rows.append(out)

    return summary_rows, scan_id


def _fmt_float(v: object) -> str:
    if isinstance(v, float):
        if math.isnan(v):
            return "nan"
        return f"{v:.2f}"
    return str(v)


def print_summary(rows: List[Dict[str, object]]) -> None:
    if not rows:
        print("No rows to summarize.")
        return

    columns = list(rows[0].keys())
    widths = {c: len(c) for c in columns}
    for r in rows:
        for c in columns:
            widths[c] = max(widths[c], len(_fmt_float(r.get(c, ""))))

    header = " | ".join(c.ljust(widths[c]) for c in columns)
    sep = "-+-".join("-" * widths[c] for c in columns)
    print(header)
    print(sep)
    for r in rows:
        line = " | ".join(_fmt_float(r.get(c, "")).ljust(widths[c]) for c in columns)
        print(line)


def print_summary_plain(rows: List[Dict[str, object]]) -> None:
    if not rows:
        print("No rows to summarize.")
        return
    columns = list(rows[0].keys())
    print(",".join(columns))
    for r in rows:
        print(",".join(_fmt_float(r.get(c, "")) for c in columns))


def _format_rows(rows: List[Dict[str, object]]) -> List[Dict[str, object]]:
    formatted_rows: List[Dict[str, object]] = []
    for row in rows:
        out_row: Dict[str, object] = {}
        for k, v in row.items():
            if isinstance(v, float):
                out_row[k] = "nan" if math.isnan(v) else f"{v:.2f}"
            else:
                out_row[k] = v
        formatted_rows.append(out_row)
    return formatted_rows


def _scan_matches(scan_value: str, scan_id: int) -> bool:
    txt = str(scan_value).strip()
    if txt == "":
        return False
    try:
        return int(float(txt)) == int(scan_id)
    except ValueError:
        return False


def write_summary(
    rows: List[Dict[str, object]],
    output_csv: str,
    scan_id: Optional[int],
    modify: bool,
    append: bool,
) -> str:
    if not rows:
        raise ValueError("No summary rows to write.")
    formatted_rows = _format_rows(rows)
    new_fields = list(formatted_rows[0].keys())

    # Fresh file: just write.
    if not os.path.exists(output_csv):
        with open(output_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=new_fields)
            writer.writeheader()
            writer.writerows(formatted_rows)
        return "created"

    # Existing file: decide modify/append behavior.
    with open(output_csv, "r", newline="") as f:
        reader = csv.DictReader(f)
        existing_fields = list(reader.fieldnames or [])
        existing_rows = list(reader)

    out_fields = list(existing_fields)
    for col in new_fields:
        if col not in out_fields:
            out_fields.append(col)
    if not out_fields:
        out_fields = new_fields

    same_scan_exists = False
    if scan_id is not None and "scan" in out_fields:
        for r in existing_rows:
            if _scan_matches(r.get("scan", ""), scan_id):
                same_scan_exists = True
                break

    if same_scan_exists and modify:
        existing_rows = [r for r in existing_rows if not _scan_matches(r.get("scan", ""), scan_id)]
        merged_rows = existing_rows + formatted_rows
        action = "modified"
    elif (not same_scan_exists) and append:
        merged_rows = existing_rows + formatted_rows
        action = "appended"
    elif same_scan_exists and (not modify) and append:
        merged_rows = existing_rows + formatted_rows
        action = "appended_duplicate_scan"
    else:
        merged_rows = existing_rows
        action = "unchanged"

    with open(output_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields)
        writer.writeheader()
        writer.writerows(merged_rows)

    return action


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Summarize gain/bandpass antenna stats CSV by (stokes, component): "
            "mean/std of mean, std, skew, kurt using only non-NaN values."
        )
    )
    p.add_argument("input_csv", nargs="?", default=None, help="Input stats CSV path (positional, optional)")
    p.add_argument("--input-csv-file", default=None, help="Input stats CSV path")
    p.add_argument("--mode", choices=["gain", "bandpass"], default="gain", help="Input stats mode")
    p.add_argument("--bchan", type=int, default=None, help="Bandpass mode: bchan used in filename pattern")
    p.add_argument("--echan", type=int, default=None, help="Bandpass mode: echan used in filename pattern")
    p.add_argument(
        "--all",
        action="store_true",
        help=(
            "Process all files matching mode-specific scan stats from the given path "
            "(if path is a file, uses its parent directory)."
        ),
    )
    p.add_argument(
        "--output",
        default=None,
        help="Optional output CSV path for summary table",
    )
    p.add_argument(
        "--pretty",
        action="store_true",
        help="Print terminal output as an aligned table (does not affect --output CSV).",
    )
    p.add_argument(
        "--modify",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "If output exists and same scan is present, replace those scan rows "
            "(default: enabled; use --no-modify to disable)."
        ),
    )
    p.add_argument(
        "--append",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "If output exists and scan is not present, append new rows "
            "(default: enabled; use --no-append to disable)."
        ),
    )
    return p


def main() -> None:
    args = build_parser().parse_args()
    input_path = args.input_csv_file if args.input_csv_file is not None else args.input_csv
    if input_path is None:
        raise ValueError("Provide input via --input-csv-file or positional input_csv.")
    if args.all:
        input_files = _discover_scan_csvs(
            input_path,
            mode=args.mode,
            bchan=args.bchan,
            echan=args.echan,
        )
        if not input_files:
            raise FileNotFoundError(
                f"No mode-matching stats scan files found near: {input_path}"
            )
    else:
        input_files = [input_path]

    output_path = args.output
    if output_path is None and args.all:
        base_dir = input_path if os.path.isdir(input_path) else (os.path.dirname(input_path) or ".")
        output_path = os.path.join(
            base_dir,
            "gain_stats_summary.csv" if args.mode == "gain" else "bpass_stats_summary.csv",
        )

    for input_csv in input_files:
        rows, scan_id = summarize_gain_stats(input_csv)

        print(f"\nInput: {input_csv}")
        if scan_id is not None:
            print(f"Detected scan: {scan_id}")
        else:
            print("Detected scan: none")

        if args.pretty:
            print_summary(rows)
        else:
            print_summary_plain(rows)

        if output_path:
            action = write_summary(
                rows=rows,
                output_csv=output_path,
                scan_id=scan_id,
                modify=args.modify,
                append=args.append,
            )
            print(f"Output CSV: {output_path} ({action})")


if __name__ == "__main__":
    main()
