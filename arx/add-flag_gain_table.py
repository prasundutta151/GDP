#!/usr/bin/env python3
import argparse
import ast
import os
import shutil
from typing import List, Sequence, Tuple, Union

import numpy as np

try:
    from casatools import table as casatable
except Exception as exc:
    raise RuntimeError("Could not import casatools.table. Run inside CASA/casa6.") from exc


AntSelector = Union[int, Tuple[int, ...]]
ScanSelector = Union[int, Tuple[int, ...]]
Rule = Tuple[AntSelector, ScanSelector, int]


def parse_rules(rules_text: str) -> List[Rule]:
    """
    Parse rules from a Python-literal list of tuples:
    [
      (ant, scan),
      (ant, scan, stokes),
      (ant, (scan1,scan2,...), stokes),
      ((ant1,ant2,...), scan, stokes),
      ((ant1,ant2,...), (scan1,scan2,...), stokes),
      ...
    ]
    A 2-tuple (ant, scan) is expanded to (ant, scan, -1).
    Wildcards:
      scan=-1   -> all scans (not allowed inside scan list)
      stokes=-1 -> all stokes (all polarizations)
    """
    try:
        parsed = ast.literal_eval(rules_text)
    except Exception as exc:
        raise ValueError(f"Could not parse --rules: {exc}") from exc

    if not isinstance(parsed, (list, tuple)):
        raise ValueError("--rules must be a list/tuple of 4-tuples.")

    rules: List[Rule] = []
    for idx, item in enumerate(parsed):
        if not isinstance(item, (list, tuple)):
            raise ValueError(f"Rule #{idx} is not a tuple/list: {item!r}")
        if len(item) == 2:
            ant_sel_raw, scan = item
            stokes = -1
        elif len(item) == 3:
            ant_sel_raw, scan, stokes = item
        else:
            raise ValueError(
                f"Rule #{idx} must be (ant,scan) or (ant,scan,stokes): {item!r}"
            )
        try:
            stokes = int(stokes)
        except Exception as exc:
            raise ValueError(f"Rule #{idx} has non-integer values: {item!r}") from exc

        if isinstance(ant_sel_raw, (list, tuple)):
            ant_vals: List[int] = []
            for a in ant_sel_raw:
                try:
                    av = int(a)
                except Exception as exc:
                    raise ValueError(f"Rule #{idx} has non-integer antenna in list: {item!r}") from exc
                if av < 0:
                    raise ValueError(f"Rule #{idx}: antenna list entries must be >= 0, got {av}")
                ant_vals.append(av)
            ant_sel: AntSelector = tuple(ant_vals)
        else:
            try:
                ant_sel = int(ant_sel_raw)
            except Exception as exc:
                raise ValueError(f"Rule #{idx} has invalid antenna selector: {item!r}") from exc

        if isinstance(scan, (list, tuple)):
            scan_vals: List[int] = []
            for s in scan:
                try:
                    sv = int(s)
                except Exception as exc:
                    raise ValueError(f"Rule #{idx} has non-integer scan in list: {item!r}") from exc
                if sv < 0:
                    raise ValueError(f"Rule #{idx}: scan list entries must be >= 0, got {sv}")
                scan_vals.append(sv)
            scan_sel: ScanSelector = tuple(scan_vals)
        else:
            try:
                scan_sel = int(scan)
            except Exception as exc:
                raise ValueError(f"Rule #{idx} has invalid scan selector: {item!r}") from exc

        if isinstance(ant_sel, int) and ant_sel < 0:
            raise ValueError(f"Rule #{idx}: antenna must be >= 0, got {ant_sel}")
        if isinstance(scan_sel, int) and scan_sel < -1:
            raise ValueError(f"Rule #{idx}: scan must be >= -1, got {scan_sel}")
        if stokes < -1:
            raise ValueError(f"Rule #{idx}: stokes must be >= -1, got {stokes}")
        rules.append((ant_sel, scan_sel, stokes))

    return rules


def copy_table(input_table: str, output_table: str) -> None:
    if not os.path.isdir(input_table):
        raise FileNotFoundError(f"Input table not found: {input_table}")
    if os.path.exists(output_table):
        raise FileExistsError(f"Output table already exists: {output_table}")
    shutil.copytree(input_table, output_table)


def _validate_table_type(cols: Sequence[str], mode: str) -> None:
    if mode == "gain":
        if "GAIN" not in cols and "CPARAM" not in cols:
            raise RuntimeError(
                "Selected --mode gain, but table has neither GAIN nor CPARAM column."
            )
        return
    if mode == "bandpass":
        if "CPARAM" not in cols and "FPARAM" not in cols:
            raise RuntimeError(
                "Selected --mode bandpass, but table has neither CPARAM nor FPARAM column."
            )
        return
    raise ValueError(f"Unsupported mode: {mode}")


def prepare_output_table(input_table: str, output_table: str, existing: str) -> None:
    if existing not in {"error", "overwrite", "modify"}:
        raise ValueError(f"Unsupported --if-exists mode: {existing}")

    if not os.path.isdir(input_table):
        raise FileNotFoundError(f"Input table not found: {input_table}")

    if not os.path.exists(output_table):
        shutil.copytree(input_table, output_table)
        return

    if existing == "error":
        raise FileExistsError(f"Output table already exists: {output_table}")
    if existing == "overwrite":
        shutil.rmtree(output_table)
        shutil.copytree(input_table, output_table)
        return
    if existing == "modify":
        if not os.path.isdir(output_table):
            raise NotADirectoryError(f"Output path exists but is not a CASA table dir: {output_table}")
        # Keep existing output table contents and apply new flags into it.
        return


def add_flags(
    input_table: str,
    output_table: str,
    rules: Sequence[Rule],
    if_exists: str,
    mode: str,
) -> None:
    prepare_output_table(input_table, output_table, if_exists)

    tb = casatable()
    tb.open(output_table, nomodify=False)
    try:
        cols = tb.colnames()
        _validate_table_type(cols, mode)
        if "FLAG" not in cols:
            raise RuntimeError("No FLAG column found in table.")
        if "ANTENNA1" not in cols:
            raise RuntimeError("No ANTENNA1 column found in table.")
        if "SCAN_NUMBER" not in cols:
            raise RuntimeError("No SCAN_NUMBER column found in table.")

        flag = tb.getcol("FLAG")
        ant1 = tb.getcol("ANTENNA1")
        scan = tb.getcol("SCAN_NUMBER")

        if flag.dtype != np.bool_:
            flag = flag.astype(bool, copy=False)

        if flag.ndim != 3:
            raise RuntimeError(
                f"Expected FLAG shape (npol, nchan, nrow); got shape {flag.shape}"
            )

        npol, _nchan, _nrow = flag.shape
        new_flag = flag.copy()

        total_newly_flagged = 0
        for ant_sel, scan_sel, stokes_sel in rules:
            if isinstance(ant_sel, int):
                row_mask = ant1 == ant_sel
            else:
                if len(ant_sel) == 0:
                    continue
                row_mask = np.isin(ant1, np.asarray(ant_sel, dtype=ant1.dtype))
            if isinstance(scan_sel, int):
                if scan_sel != -1:
                    row_mask &= (scan == scan_sel)
            else:
                if len(scan_sel) == 0:
                    continue
                row_mask &= np.isin(scan, np.asarray(scan_sel, dtype=scan.dtype))
            row_idx = np.where(row_mask)[0]
            if row_idx.size == 0:
                continue

            if stokes_sel == -1:
                before = new_flag[:, :, row_idx].copy()
                new_flag[:, :, row_idx] = True
            else:
                if stokes_sel < 0 or stokes_sel >= npol:
                    print(
                        f"Warning: stokes index {stokes_sel} out of range [0,{npol - 1}] for rule "
                        f"(ant={ant_sel}, scan={scan_sel}, stokes={stokes_sel}). Skipping."
                    )
                    continue
                before = new_flag[stokes_sel, :, row_idx].copy()
                new_flag[stokes_sel, :, row_idx] = True

            total_newly_flagged += int(np.count_nonzero(~before))

        tb.putcol("FLAG", new_flag)
        print(f"Wrote output table: {output_table}")
        print(f"Newly flagged FLAG elements: {total_newly_flagged}")
    finally:
        tb.close()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Add extra flags into CASA gain/bandpass table FLAG column. "
            "Existing flags are preserved (logical OR)."
        )
    )
    p.add_argument("input_table", nargs="?", default=None, help="Input CASA calibration table path (positional, optional)")
    p.add_argument("output_table", nargs="?", default=None, help="Output CASA calibration table path (positional, optional)")
    p.add_argument("--input-gain-table", default=None, help="Input CASA gain/bandpass table path")
    p.add_argument("--output-gain-table", default=None, help="Output CASA gain/bandpass table path")
    p.add_argument(
        "--rules",
        required=True,
        nargs="+",
        help=(
            "Rules as Python literal list of tuples: "
            "[(ant, scan), (ant, scan, stokes), (ant, (scan1,scan2,...), stokes), "
            "((ant1,ant2,...), scan, stokes), ...]. "
            "(ant,scan) means all stokes. Use -1 as scan wildcard (all scans) "
            "and stokes=-1 for all stokes."
        ),
    )
    p.add_argument(
        "--mode",
        choices=["gain", "bandpass"],
        default="gain",
        help=(
            "Table type validation mode. "
            "'gain' checks for GAIN/CPARAM, 'bandpass' checks for CPARAM/FPARAM."
        ),
    )
    p.add_argument(
        "--if-exists",
        choices=["error", "overwrite", "modify"],
        default="modify",
        help=(
            "Behavior when output_table already exists: "
            "'modify' (default) apply new flags into existing output_table, "
            "'error' fail, 'overwrite' replace from input_table, "
            "'modify' apply new flags into existing output_table."
        ),
    )
    return p


def main() -> None:
    args = build_parser().parse_args()
    input_table = args.input_gain_table if args.input_gain_table is not None else args.input_table
    output_table = args.output_gain_table if args.output_gain_table is not None else args.output_table
    if input_table is None or output_table is None:
        raise ValueError(
            "Provide input/output via --input-gain-table and --output-gain-table "
            "or via positional input_table output_table."
        )
    rules_text = " ".join(args.rules)
    rules = parse_rules(rules_text)
    add_flags(input_table, output_table, rules, args.if_exists, args.mode)


if __name__ == "__main__":
    main()
