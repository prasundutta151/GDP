import numpy as np
import shutil
from casatools import table
import os
import argparse


def _copy_subdirs(src_root, dst_root):
    for item in os.listdir(src_root):
        src = os.path.join(src_root, item)
        dst = os.path.join(dst_root, item)
        if os.path.isdir(src):
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst)


def modify_casa_cal_table(
    input_table,
    output_table=None,
    mode='gain',
    operation='subtract',
    scan=None,
):
    """
    Modify CASA gain/bandpass table stream-by-stream.

    Grouping is per (spw, scan, stokes/state, antenna1).

    For each group:
    - real part:
        * operation='subtract': real <- real - mean(real)
        * operation='divide':   real <- real / mean(real)
      then add Gaussian noise with mean 0 and std std(real).
    - imaginary part: left unchanged.

    If scan is None, all scans are processed scan-by-scan.
    """
    if mode not in {'gain', 'bandpass'}:
        raise ValueError(f"Unsupported mode '{mode}'. Use 'gain' or 'bandpass'.")
    if operation not in {'subtract', 'divide'}:
        raise ValueError(f"Unsupported operation '{operation}'. Use 'subtract' or 'divide'.")

    if output_table is None:
        output_table = os.path.abspath('modified_gain.tb' if mode == 'gain' else 'modified_bandpass.tb')

    tb_in = table()
    tb_in.open(input_table, nomodify=True)

    colnames = tb_in.colnames()
    if mode == 'gain':
        data_col = "GAIN" if "GAIN" in colnames else "CPARAM"
    else:
        data_col = "CPARAM"
    if data_col not in colnames:
        tb_in.close()
        raise ValueError(f"Input table does not contain required column '{data_col}' for mode={mode}.")

    # Read required columns
    gain_data = tb_in.getcol(data_col)  # shape: (npol, nchan, nrow)
    flag_data = tb_in.getcol('FLAG') if 'FLAG' in colnames else None
    spw_data = tb_in.getcol('SPECTRAL_WINDOW_ID') if 'SPECTRAL_WINDOW_ID' in colnames else None
    scan_data = tb_in.getcol('SCAN_NUMBER') if 'SCAN_NUMBER' in colnames else None
    stokes_data = tb_in.getcol('STATE_ID') if 'STATE_ID' in colnames else None
    antenna1_data = tb_in.getcol('ANTENNA1') if 'ANTENNA1' in colnames else None

    nrows = tb_in.nrows()
    npol, nchan, _ = gain_data.shape

    if spw_data is None:
        spw_data = np.zeros(nrows, dtype=int)
    if scan_data is None:
        scan_data = np.zeros(nrows, dtype=int)
    if stokes_data is None:
        stokes_data = np.zeros(nrows, dtype=int)
    if antenna1_data is None:
        antenna1_data = np.zeros(nrows, dtype=int)

    if scan is not None:
        scan = int(scan)
        if not np.any(scan_data == scan):
            tb_in.close()
            raise ValueError(f"Requested scan {scan} not present in table.")

    if os.path.exists(output_table):
        shutil.rmtree(output_table)
    shutil.copytree(input_table, output_table)

    tb_out = table()
    tb_out.open(output_table, nomodify=False)

    modified_gain_data = gain_data.copy()

    if scan is None:
        scans_to_process = np.unique(scan_data)
    else:
        scans_to_process = np.array([scan], dtype=scan_data.dtype)

    for scan_val in scans_to_process:
        # Per-scan grouping, so processing is explicitly scan-by-scan.
        scan_mask = (scan_data == scan_val)
        unique_groups = np.unique(
            np.vstack((spw_data[scan_mask], stokes_data[scan_mask], antenna1_data[scan_mask])).T,
            axis=0
        )

        for spw_val, stokes_val, ant1_val in unique_groups:
            idx = np.where(
                (scan_data == scan_val) &
                (spw_data == spw_val) &
                (stokes_data == stokes_val) &
                (antenna1_data == ant1_val)
            )[0]

            if idx.size == 0:
                continue

            group_data = gain_data[:, :, idx]
            if flag_data is not None:
                group_flag = flag_data[:, :, idx]
            else:
                group_flag = np.zeros_like(group_data, dtype=bool)

            valid_mask = ~group_flag
            valid_real = group_data.real[valid_mask]
            if valid_real.size == 0:
                continue

            mean_real = np.mean(valid_real)
            std_real = np.std(valid_real)

            modified_group = group_data.copy()

            if operation == 'subtract':
                modified_group.real -= mean_real
            else:
                if np.isclose(mean_real, 0.0):
                    continue
                modified_group.real /= mean_real

            noise_real = np.random.normal(loc=0.0, scale=std_real, size=modified_group.shape)
            modified_group.real += noise_real

            modified_gain_data[:, :, idx] = modified_group

    tb_out.putcol(data_col, modified_gain_data)

    tb_out.close()
    tb_in.close()

    _copy_subdirs(input_table, output_table)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Modify CASA gain or bandpass table using subtract/divide operation and real-part Gaussian noise.')
    parser.add_argument('--mode', choices=['gain', 'bandpass'], default='gain', help='Table mode: gain or bandpass.')
    parser.add_argument('--input-gain-table', required=True, type=str, help='Input CASA table path.')
    parser.add_argument('--output-gain-table', required=True, type=str, help='Output CASA table path.')
    parser.add_argument('--scan', type=int, default=None, help='Scan to process. If omitted, all scans are processed scan-by-scan.')
    parser.add_argument('--operation', choices=['subtract', 'divide'], default='subtract',
                        help='Operation on real part before adding noise.')

    args = parser.parse_args()

    modify_casa_cal_table(
        input_table=args.input_gain_table,
        output_table=args.output_gain_table,
        mode=args.mode,
        operation=args.operation,
        scan=args.scan,
    )
