#!/usr/bin/env python3
import argparse
import ast
import datetime as dt
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional


DEFAULT_INPUT_ROOT = "/Volumes/Work/Data/gain_band3/270226/ELAIS_all"
DEFAULT_OUTPUT_ROOT = "/Volumes/Work/Data/gain_band3/060326/ELAIS_all"
DEFAULT_ANALYSIS_TAG = "May05_2017"
DEFAULT_INPUT_GAIN_TABLE = f"{DEFAULT_INPUT_ROOT}/gain_May05_int_md.g"


def _ask_input_gain_table(default_path: str) -> str:
    while True:
        text = input(f"Input gain table [{default_path}]: ").strip()
        path = text if text else default_path
        if not os.path.isdir(path):
            print(f"Not found: {path}")
            continue
        if "/270226/" not in path:
            print("Warning: path does not include '/270226/' as requested.")
        return path


def _collect_manual_rules() -> str:
    print("\nStep 5 manual flag rules input.")
    print("Enter one tuple per line, examples:")
    print("  (9, 7)")
    print("  (18, 2, -1)")
    print("  ((11,12,13,14), 4, -1)")
    print("  (15, (2,3,4,5,6), 1)")
    print("Type 'end' when done.\n")

    rules: List[object] = []
    while True:
        line = input("rule> ").strip()
        if line.lower() == "end":
            if not rules:
                print("At least one rule is required before 'end'.")
                continue
            break
        if line == "":
            continue
        try:
            obj = ast.literal_eval(line)
        except Exception as exc:
            print(f"Could not parse tuple: {exc}")
            continue
        if not isinstance(obj, (list, tuple)):
            print("Rule must be a tuple/list like (ant, scan) or (ant, scan, stokes).")
            continue
        if len(obj) not in (2, 3):
            print("Rule tuple must have 2 or 3 items.")
            continue
        rules.append(obj)

    return repr(rules)


def _derive_flagged_table_path(input_table: str, output_root: str) -> str:
    base_name = os.path.basename(input_table.rstrip("/"))
    root, ext = os.path.splitext(base_name)
    if ext == "":
        return os.path.join(output_root, f"{base_name}_af")
    return os.path.join(output_root, f"{root}_af{ext}")


def _discover_stats_csvs(csv_dir: str, mode: str, bchan: Optional[int] = None, echan: Optional[int] = None) -> List[str]:
    if mode == "gain":
        patterns = [re.compile(r"^gain_stats_scan[_-]?(\d+)\.csv$", flags=re.IGNORECASE)]
    else:
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
    found = []
    for name in os.listdir(csv_dir):
        for patt in patterns:
            m = patt.match(name)
            if m:
                found.append((int(m.group(1)), os.path.join(csv_dir, name)))
                break
    found.sort(key=lambda x: (x[0], x[1]))
    return [p for _, p in found]


def _discover_prefixed_cross_csvs(csv_dir: str, mode: str) -> List[str]:
    prefix = "gain_cross_tcorr_scan" if mode == "gain" else "bpass_cross_tcorr_scan"
    patt = re.compile(rf"^{re.escape(prefix)}[_-]?(\d+)\.csv$", flags=re.IGNORECASE)
    found = []
    for name in os.listdir(csv_dir):
        m = patt.match(name)
        if not m:
            continue
        found.append((int(m.group(1)), os.path.join(csv_dir, name)))
    found.sort(key=lambda x: (x[0], x[1]))
    return [p for _, p in found]


def _scan_from_filename(path: str) -> int:
    m = re.search(r"scan[_-]?(\d+)", os.path.basename(path), flags=re.IGNORECASE)
    return int(m.group(1)) if m else -1


def _append_bandpass_chan_args(cmd: List[str], mode: str, bchan: Optional[int], echan: Optional[int]) -> List[str]:
    if mode != "bandpass":
        return cmd
    if bchan is not None:
        cmd.extend(["--bchan", str(int(bchan))])
    if echan is not None:
        cmd.extend(["--echan", str(int(echan))])
    return cmd


def _run(cmd: List[str], cwd: Path) -> None:
    print("\n$ " + " ".join(shlex.quote(x) for x in cmd))
    t0 = time.perf_counter()
    subprocess.run(cmd, cwd=str(cwd), check=True)
    dt = time.perf_counter() - t0
    print(f"[done in {dt:.2f} sec]")


def _fmt_hms(seconds: float) -> str:
    total = int(round(max(0.0, float(seconds))))
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def _run_plots_only_pipeline(
    py: str,
    cwd: Path,
    mode: str,
    input_csv_dir: str,
    output_plot_dir: str,
    date_text: str,
    s2_threshold: float,
    s2_alpha: float,
    hist_shade_alpha: float,
    bchan: Optional[int] = None,
    echan: Optional[int] = None,
    summary_csv_file: Optional[str] = None,
) -> None:
    mode_prefix = "gain" if mode == "gain" else "bpass"
    in_csv_dir = os.path.abspath(input_csv_dir)
    out_plot_dir = os.path.abspath(output_plot_dir)
    if not os.path.isdir(in_csv_dir):
        raise NotADirectoryError(f"Not a directory: {in_csv_dir}")
    os.makedirs(out_plot_dir, exist_ok=True)

    summary_csv = (
        os.path.abspath(summary_csv_file)
        if summary_csv_file is not None
        else os.path.join(in_csv_dir, f"{mode_prefix}_stats_summary.csv")
    )

    if not os.path.exists(summary_csv):
        if mode == "gain":
            _run(
                [
                    py,
                    "summarize_gain_stats.py",
                    "--input-csv-file",
                    in_csv_dir,
                    "--all",
                    "--output",
                    summary_csv,
                ],
                cwd=cwd,
            )
        else:
            stats_files = _discover_stats_csvs(in_csv_dir, mode="bandpass", bchan=bchan, echan=echan)
            if len(stats_files) == 0:
                raise FileNotFoundError(
                    f"No bpass_stats_scan#.csv found in {in_csv_dir}; cannot build bandpass summary CSV."
                )
            for i, stats_csv in enumerate(stats_files):
                cmd = [
                    py,
                    "summarize_gain_stats.py",
                    "--mode",
                    "bandpass",
                    "--input-csv-file",
                    stats_csv,
                    "--output",
                    summary_csv,
                ]
                if bchan is not None:
                    cmd.extend(["--bchan", str(bchan)])
                if echan is not None:
                    cmd.extend(["--echan", str(echan)])
                if i == 0:
                    cmd.append("--modify")
                    cmd.append("--append")
                _run(cmd, cwd=cwd)

    # summary_statistics
    _run(
        [
            py,
            "plot_gain_stats_summary.py",
            summary_csv,
            "--output",
            os.path.join(out_plot_dir, f"{mode_prefix}_stats_summary.png"),
            "--date",
            date_text,
        ],
        cwd=cwd,
    )

    # s2_across_antenna
    _run(
        [
            py,
            "plot_gain_s2_median_from_npz.py",
            "--mode",
            mode,
            "--in-csv-dir",
            in_csv_dir,
            "--plot-dir",
            out_plot_dir,
            "--threshold",
            str(s2_threshold),
            "--alpha",
            str(s2_alpha),
            "--date",
            date_text,
        ]
        + (["--bchan", str(bchan)] if bchan is not None else [])
        + (["--echan", str(echan)] if echan is not None else []),
        cwd=cwd,
    )

    # cross_tcorr_colormap + summary_histogram
    cross_scan_csvs = _discover_prefixed_cross_csvs(in_csv_dir, mode=mode)
    if len(cross_scan_csvs) == 0:
        raise FileNotFoundError(
            f"No {mode_prefix}_cross_tcorr_scan#.csv files found in {in_csv_dir} for cross-tcorr plots."
        )
    for in_csv in cross_scan_csvs:
        sc = _scan_from_filename(in_csv)
        _run(
            [
                py,
                "plot_tcorr_colormap_from_csv.py",
                "--input-csv-file",
                in_csv,
                "--output-plot-file",
                os.path.join(out_plot_dir, f"{mode_prefix}_cross_tcorr_colormap_scan{sc}.png"),
                "--date",
                date_text,
            ],
            cwd=cwd,
        )
        _run(
            [
                py,
                "plot_tcorr_combo_mirror_hist.py",
                "--input-csv-file",
                in_csv,
                "--output-plot-file",
                os.path.join(out_plot_dir, f"{mode_prefix}_cross_tcorr_hist_scan{sc}.png"),
                "--date",
                date_text,
                "--shade-alpha",
                str(hist_shade_alpha),
            ],
            cwd=cwd,
        )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Automate RUNLOG workflow with one interactive pause for manual "
            "--rules input after reviewing step-4 gain colormaps."
        )
    )
    p.add_argument("--input-gain-table", default=None, help="Input gain table (if omitted, prompt at runtime).")
    p.add_argument("--mode", choices=["gain", "bandpass"], default="gain", help="Run pipeline mode.")
    p.add_argument("--bchan", type=int, default=None, help="Bandpass mode: start channel (inclusive).")
    p.add_argument("--echan", type=int, default=None, help="Bandpass mode: end channel (exclusive).")
    p.add_argument("--input-root", default=DEFAULT_INPUT_ROOT, help="Expected root for input table (default from RUNLOG).")
    p.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT, help="Output root (default from RUNLOG).")
    p.add_argument("--analysis-tag", default=DEFAULT_ANALYSIS_TAG, help="Tag used under analysis/ (default: May05_2017).")
    p.add_argument("--date", default=None, help="Date label for plot titles; default uses --analysis-tag.")
    p.add_argument(
        "--start-from-step",
        type=int,
        default=2,
        help="Start RUNLOG pipeline from this step number (allowed: 2,3,4,5,6,7,8,12,9,10,11).",
    )
    p.add_argument(
        "--plots-only",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Run only plotting pipeline: cross_tcorr_colormap, summary_statistics, summary_histogram, s2_across_antenna.",
    )
    p.add_argument("--plots-input-csv-dir", default=None, help="Plots-only mode: input CSV directory.")
    p.add_argument("--plots-output-plot-dir", default=None, help="Plots-only mode: output plot directory.")
    p.add_argument("--plots-summary-csv-file", default=None, help="Plots-only mode: optional precomputed summary CSV path.")

    p.add_argument("--flag-max-rounds", type=int, default=7)
    p.add_argument("--flag-threshold-schedule", default="(3,3,3,4,4,5,5)")
    p.add_argument("--flag-whole-ant-k", type=float, default=4.0)
    p.add_argument("--flag-min-remaining-pct", type=float, default=35.0)

    p.add_argument("--cross-threshold", type=float, default=0.7)
    p.add_argument("--cross-nbin", type=int, default=32)
    p.add_argument("--cross-bintype", choices=["log", "lin"], default="log")
    p.add_argument("--cross-jobs", type=int, default=12)

    p.add_argument("--s2-threshold", type=float, default=0.7)
    p.add_argument("--s2-alpha", type=float, default=0.4)
    p.add_argument("--hist-shade-alpha", type=float, default=1.0)

    p.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable to run sub-scripts (default: current interpreter).",
    )
    return p


def main() -> None:
    args = build_parser().parse_args()
    cwd = Path(__file__).resolve().parent
    analysis_label = (str(args.date).strip() if args.date is not None and str(args.date).strip() != "" else args.analysis_tag)
    date_text = args.date if args.date is not None else analysis_label
    step_order = [2, 3, 4, 5, 6, 7, 8, 12, 9, 10, 11]
    if args.start_from_step not in step_order:
        raise ValueError(
            f"Invalid --start-from-step={args.start_from_step}. Allowed values: {step_order}"
        )
    start_idx = step_order.index(args.start_from_step)
    enabled_steps = set(step_order[start_idx:])

    def run_step(step_id: int) -> bool:
        return step_id in enabled_steps

    if args.plots_only:
        if args.plots_input_csv_dir is None:
            raise ValueError("--plots-only requires --plots-input-csv-dir")
        if args.plots_output_plot_dir is None:
            raise ValueError("--plots-only requires --plots-output-plot-dir")
        _run_plots_only_pipeline(
            py=args.python,
            cwd=cwd,
            mode=args.mode,
            input_csv_dir=args.plots_input_csv_dir,
            output_plot_dir=args.plots_output_plot_dir,
            date_text=date_text,
            s2_threshold=args.s2_threshold,
            s2_alpha=args.s2_alpha,
            hist_shade_alpha=args.hist_shade_alpha,
            bchan=args.bchan,
            echan=args.echan,
            summary_csv_file=args.plots_summary_csv_file,
        )
        return

    input_gain_table = args.input_gain_table
    if input_gain_table is None:
        input_gain_table = _ask_input_gain_table(DEFAULT_INPUT_GAIN_TABLE)
    input_gain_table = os.path.abspath(input_gain_table)
    if not os.path.isdir(input_gain_table):
        raise FileNotFoundError(f"Input gain table not found: {input_gain_table}")
    if args.input_root and not os.path.abspath(input_gain_table).startswith(os.path.abspath(args.input_root)):
        print(f"Warning: input table is not under --input-root ({args.input_root}).")

    flagged_table = _derive_flagged_table_path(input_gain_table, args.output_root)

    temp_csv_dir = os.path.join(args.output_root, "analysis", "temp", "csvs")
    temp_plot_dir1 = os.path.join(args.output_root, "analysis", "temp", "plots1")
    temp_plot_dir = os.path.join(args.output_root, "analysis", "temp", "plots")
    final_csv_dir = os.path.join(args.output_root, "analysis", analysis_label, "csvs")
    final_plot_dir = os.path.join(args.output_root, "analysis", analysis_label, "plots")
    mode_prefix = "gain" if args.mode == "gain" else "bpass"
    summary_csv = os.path.join(
        final_csv_dir,
        "gain_stats_summary.csv" if args.mode == "gain" else "bpass_stats_summary.csv",
    )
    summary_plot = os.path.join(
        final_plot_dir,
        "gain_stats_summary.png" if args.mode == "gain" else "bpass_stats_summary.png",
    )
    cross_tcorr_csv = os.path.join(final_csv_dir, f"{mode_prefix}_cross_tcorr.csv")
    os.makedirs(temp_csv_dir, exist_ok=True)
    os.makedirs(temp_plot_dir1, exist_ok=True)
    os.makedirs(temp_plot_dir, exist_ok=True)
    os.makedirs(final_csv_dir, exist_ok=True)
    os.makedirs(final_plot_dir, exist_ok=True)

    print("\nRUNLOG automation starting with:")
    print(f"  mode:               {args.mode}")
    if args.mode == "bandpass":
        print(f"  channel range:      bchan={args.bchan}, echan={args.echan}")
    print(f"  input gain table:   {input_gain_table}")
    print(f"  flagged gain table: {flagged_table}")
    print(f"  temp csv dir:       {temp_csv_dir}")
    print(f"  temp plot dir #1:   {temp_plot_dir1}")
    print(f"  temp plot dir #2:   {temp_plot_dir}")
    print(f"  final csv dir:      {final_csv_dir}")
    print(f"  final plot dir:     {final_plot_dir}")
    print(f"  summary csv:        {summary_csv}")
    print(f"  summary plot:       {summary_plot}")
    print(f"  cross tcorr csv:    {cross_tcorr_csv}")
    print(f"  start from step:    {args.start_from_step}")

    py = args.python
    t_all = time.perf_counter()
    wall_start = dt.datetime.now()

    # 2) Initial AntStat colormap run.
    if run_step(2):
        cmd = [
            py,
            "AntStat.py",
            "--input-gain-table",
            input_gain_table,
            "--gain-all",
            "--mode",
            args.mode,
            "--plot-dir",
            temp_plot_dir1,
            "--csv-dir",
            temp_csv_dir,
        ]
        _run(_append_bandpass_chan_args(cmd, args.mode, args.bchan, args.echan), cwd=cwd)

    # 3) Automated threshold flagging.
    if run_step(3):
        cmd = [
            py,
            "flag_from_colormap_thresholds.py",
            "--mode",
            args.mode,
            "--input-gain-table",
            input_gain_table,
            "--output-gain-table",
            flagged_table,
            "--max-rounds",
            str(args.flag_max_rounds),
            "--global-only",
            "--threshold-schedule",
            str(args.flag_threshold_schedule),
            "--whole-ant-enable",
            "--whole-ant-k",
            str(args.flag_whole_ant_k),
            "--min-remaining-pct",
            str(args.flag_min_remaining_pct),
        ]
        _run(_append_bandpass_chan_args(cmd, args.mode, args.bchan, args.echan), cwd=cwd)

    # 4) AntStat inspect run.
    manual_rules: Optional[str] = None
    if run_step(4):
        cmd = [
            py,
            "AntStat.py",
            "--input-gain-table",
            flagged_table,
            "--gain-all",
            "--ks",
            "--stats",
            "--mode",
            args.mode,
            "--plot-dir",
            temp_plot_dir,
            "--csv-dir",
            temp_csv_dir,
        ]
        _run(_append_bandpass_chan_args(cmd, args.mode, args.bchan, args.echan), cwd=cwd)
        print("\nInspect step-4 colormaps/statistics before continuing.")
        print(f"  Inspect plots in: {temp_plot_dir}")
        manual_rules = _collect_manual_rules()

    # 5) Manual flag injection.
    if run_step(5):
        if manual_rules is None:
            manual_rules = _collect_manual_rules()
        _run(
            [
                py,
                "add-flag_gain_table.py",
                "--input-gain-table",
                flagged_table,
                "--output-gain-table",
                flagged_table,
                "--mode",
                args.mode,
                "--if-exists",
                "modify",
                "--rules",
                manual_rules,
            ],
            cwd=cwd,
        )

    # 6) Final AntStat all outputs.
    if run_step(6):
        cmd = [
            py,
            "AntStat.py",
            "--input-gain-table",
            flagged_table,
            "--do-all",
            "--mode",
            args.mode,
            "--plot-dir",
            final_plot_dir,
            "--csv-dir",
            final_csv_dir,
        ]
        _run(_append_bandpass_chan_args(cmd, args.mode, args.bchan, args.echan), cwd=cwd)

    # 7) Summary CSV.
    if run_step(7):
        if args.mode == "gain":
            _run(
                [
                    py,
                    "summarize_gain_stats.py",
                    "--mode",
                    "gain",
                    "--input-csv-file",
                    final_csv_dir,
                    "--all",
                    "--pretty",
                    "--output",
                    summary_csv,
                ],
                cwd=cwd,
            )
        else:
            stats_files = _discover_stats_csvs(final_csv_dir, mode="bandpass", bchan=args.bchan, echan=args.echan)
            if len(stats_files) == 0:
                raise FileNotFoundError(
                    f"No bpass_{args.bchan}_{args.echan}_stats_scan#.csv files found in {final_csv_dir} for bandpass summary."
                )
            for i, stats_csv in enumerate(stats_files):
                cmd = [
                    py,
                    "summarize_gain_stats.py",
                    "--mode",
                    "bandpass",
                    "--input-csv-file",
                    stats_csv,
                    "--pretty",
                    "--output",
                    summary_csv,
                ]
                if args.bchan is not None:
                    cmd.extend(["--bchan", str(args.bchan)])
                if args.echan is not None:
                    cmd.extend(["--echan", str(args.echan)])
                if i == 0:
                    cmd.append("--modify")
                    cmd.append("--append")
                _run(cmd, cwd=cwd)

    # 8) Plot summary.
    if run_step(8):
        _run(
            [
                py,
                "plot_gain_stats_summary.py",
                summary_csv,
                "--output",
                summary_plot,
                "--date",
                date_text,
            ],
            cwd=cwd,
        )

    # 12) Median S2 + GPR plot.
    if run_step(12):
        _run(
            [
                py,
                "plot_gain_s2_median_from_npz.py",
                "--mode",
                args.mode,
                "--in-csv-dir",
                final_csv_dir,
                "--plot-dir",
                final_plot_dir,
                "--threshold",
                str(args.s2_threshold),
                "--alpha",
                str(args.s2_alpha),
                "--date",
                date_text,
            ]
            + (["--bchan", str(args.bchan)] if args.bchan is not None else [])
            + (["--echan", str(args.echan)] if args.echan is not None else []),
            cwd=cwd,
        )

    # 9) Cross-correlation tcorr.
    if run_step(9):
        cmd = [
            py,
            "cross_tcorr_from_table.py",
            "--mode",
            args.mode,
            "--input-gain-table",
            flagged_table,
            "--threshold",
            str(args.cross_threshold),
            "--nbin",
            str(args.cross_nbin),
            "--bintype",
            str(args.cross_bintype),
            "--output-csv-file",
            cross_tcorr_csv,
            "--jobs",
            str(args.cross_jobs),
        ]
        _run(_append_bandpass_chan_args(cmd, args.mode, args.bchan, args.echan), cwd=cwd)

    # 10) Triangular colormap plot (per scan, prefixed filenames).
    cross_scan_csvs: List[str] = []
    if run_step(10) or run_step(11):
        cross_scan_csvs = _discover_prefixed_cross_csvs(final_csv_dir, mode=args.mode)
        if len(cross_scan_csvs) == 0:
            raise FileNotFoundError(
                f"No {mode_prefix}_cross_tcorr_scan#.csv files found in {final_csv_dir}"
            )
    if run_step(10):
        for in_csv in cross_scan_csvs:
            sc = _scan_from_filename(in_csv)
            out_png = os.path.join(final_plot_dir, f"{mode_prefix}_cross_tcorr_colormap_scan{sc}.png")
            _run(
                [
                    py,
                    "plot_tcorr_colormap_from_csv.py",
                    "--input-csv-file",
                    in_csv,
                    "--output-plot-file",
                    out_png,
                    "--date",
                    date_text,
                ],
                cwd=cwd,
            )

    # 11) Mirror histogram plot (per scan, prefixed filenames).
    if run_step(11):
        for in_csv in cross_scan_csvs:
            sc = _scan_from_filename(in_csv)
            out_png = os.path.join(final_plot_dir, f"{mode_prefix}_cross_tcorr_hist_scan{sc}.png")
            _run(
                [
                    py,
                    "plot_tcorr_combo_mirror_hist.py",
                    "--input-csv-file",
                    in_csv,
                    "--output-plot-file",
                    out_png,
                    "--date",
                    date_text,
                    "--shade-alpha",
                    str(args.hist_shade_alpha),
                ],
                cwd=cwd,
            )

    dt_all = time.perf_counter() - t_all
    wall_end = dt.datetime.now()
    print("\nRUNLOG automation complete.")
    print(f"Start time: {wall_start.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"End time:   {wall_end.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total time: {_fmt_hms(dt_all)} ({dt_all:.2f} sec)")


if __name__ == "__main__":
    main()
