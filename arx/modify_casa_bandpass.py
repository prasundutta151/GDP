import numpy as np
import shutil
from casatools import table
import os
import argparse


def modify_casa_bandpass_mean(input_bandpass_table, output_bandpass_table=None, std_mean=False):
    """
    Reads a CASA bandpass table, modifies each gain stream by subtracting its mean and:
    - If std_mean is False (Task A): 
        * For the real part, subtract its mean and add 1.
        * For the imaginary part, subtract its mean only (no addition).
    - If std_mean is True (Task B):
        * For the real part, subtract its mean and add Gaussian noise with mean 1 and std equal to the real part's std.
        * For the imaginary part, subtract its mean and add Gaussian noise with mean 0 and std equal to the imaginary part's std.
    The modification is done per unique combination of spw, scan, stokes, antenna1 over all channels,
    considering only unflagged data for the statistics.
    Writes the modified data to a new table directory, copying all subdirectories.
    """
    if output_bandpass_table is None:
        output_bandpass_table = os.path.abspath('modified_bandpass.tb')

    tb_in = table()
    tb_in.open(input_bandpass_table, nomodify=True)

    colnames = tb_in.colnames()
    if 'CPARAM' not in colnames:
        tb_in.close()
        raise ValueError("Input table does not contain 'CPARAM' column, expected for bandpass table.")

    # Read necessary columns
    gain_data = tb_in.getcol('CPARAM')  # shape: (npol, nchan, nrow)
    flag_data = tb_in.getcol('FLAG') if 'FLAG' in colnames else None
    spw_data = tb_in.getcol('SPECTRAL_WINDOW_ID') if 'SPECTRAL_WINDOW_ID' in colnames else None
    scan_data = tb_in.getcol('SCAN_NUMBER') if 'SCAN_NUMBER' in colnames else None
    stokes_data = tb_in.getcol('STATE_ID') if 'STATE_ID' in colnames else None
    antenna1_data = tb_in.getcol('ANTENNA1') if 'ANTENNA1' in colnames else None

    nrows = tb_in.nrows()
    npol, nchan, _ = gain_data.shape

    # If any of the grouping cols are missing, treat whole table as one group
    # But typically all these columns exist in bandpass tables.
    if spw_data is None:
        spw_data = np.zeros(nrows, dtype=int)
    if scan_data is None:
        scan_data = np.zeros(nrows, dtype=int)
    if stokes_data is None:
        stokes_data = np.zeros(nrows, dtype=int)
    if antenna1_data is None:
        antenna1_data = np.zeros(nrows, dtype=int)

    # Prepare output folder: copy input folder to output, removing output if exists
    if os.path.exists(output_bandpass_table):
        shutil.rmtree(output_bandpass_table)
    shutil.copytree(input_bandpass_table, output_bandpass_table)

    tb_out = table()
    tb_out.open(output_bandpass_table, nomodify=False)

    # We'll modify gain_data copy to write back
    modified_gain_data = gain_data.copy()

    # Identify unique grouping keys
    unique_groups = np.unique(
        np.vstack((spw_data, scan_data, stokes_data, antenna1_data)).T,
        axis=0
    )

    # For each group, find indices, modify gain data accordingly
    for spw_val, scan_val, stokes_val, ant1_val in unique_groups:
        # Indices of rows matching this group
        idx = np.where(
            (spw_data == spw_val) &
            (scan_data == scan_val) &
            (stokes_data == stokes_val) &
            (antenna1_data == ant1_val)
        )[0]

        if idx.size == 0:
            continue

        # Extract data and flags for these rows
        # shape: (npol, nchan, nrow_in_group)
        group_data = gain_data[:, :, idx]
        if flag_data is not None:
            group_flag = flag_data[:, :, idx]
        else:
            group_flag = np.zeros_like(group_data, dtype=bool)

        # We only consider unflagged data for statistics
        valid_mask = ~group_flag

        # Extract real and imag parts of unflagged data
        valid_real = group_data.real[valid_mask]
        valid_imag = group_data.imag[valid_mask]

        if valid_real.size == 0:
            # No valid data in this group, skip modification
            continue

        # Compute mean and std separately for real and imag parts
        mean_real = np.mean(valid_real)
        std_real = np.std(valid_real)
        mean_imag = np.mean(valid_imag)
        std_imag = np.std(valid_imag)

        # Create a copy for modification
        modified_group = group_data.copy()

        # Subtract means from all data (including flagged)
        modified_group.real -= mean_real
        modified_group.imag -= mean_imag

        if not std_mean:
            # Add 1 to real part only
            modified_group.real += 1.0
            # Imag part unchanged beyond mean subtraction
        else:
            # Add Gaussian noise with mean=0 and respective std to real and imag parts
            noise_real = np.random.normal(loc=1.0, scale=std_real, size=modified_group.shape)
            noise_imag = np.random.normal(loc=0.0, scale=std_imag, size=modified_group.shape)
            modified_group.real += noise_real
            modified_group.imag += noise_imag

        # Write back modified data for this group into modified_gain_data
        modified_gain_data[:, :, idx] = modified_group

    # Write modified gain data to output table
    tb_out.putcol('CPARAM', modified_gain_data)

    tb_out.close()
    tb_in.close()

    # Copy all subdirectories (except main table files) from input to output
    exclude_files = {'table.f1', 'table.dat', 'table.lock'}
    for item in os.listdir(input_bandpass_table):
        src = os.path.join(input_bandpass_table, item)
        dst = os.path.join(output_bandpass_table, item)
        if os.path.isdir(src) and item not in exclude_files:
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Modify CASA bandpass table by subtracting mean and adding offset or noise.')
    parser.add_argument('input_bandpass_table', type=str, help='Input CASA bandpass table path')
    parser.add_argument('output_bandpass_table', type=str, nargs='?', default=None, help='Output CASA bandpass table path (optional)')
    parser.add_argument('--std-mean', action='store_true',
                        help='If set, add Gaussian noise with mean=0 and std=stream std after mean subtraction; otherwise add 1 to real part only.')

    args = parser.parse_args()

    if args.output_bandpass_table is None:
        output_path = os.path.abspath('modified_bandpass.tb')
    else:
        output_path = args.output_bandpass_table

    # Only support bandpass tables
    # We do a minimal check by presence of CPARAM column inside function
    modify_casa_bandpass_mean(
        input_bandpass_table=args.input_bandpass_table,
        output_bandpass_table=output_path,
        std_mean=args.std_mean
    )

