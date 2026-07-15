# GDP Requirements

Keep this file current whenever GDP gains a new runtime dependency. A
dependency can be a Python package, a CASA/casa6 requirement, a command-line
tool, or a version constraint discovered during development.

## Current Status

Last reviewed: `2026-07-15`

The active dependency list is based on maintained tools in `script/`. The
`arx/` folder is archive/reference material and should not drive active
requirements unless code is promoted from `arx/` into `script/`.

## Core Python Version

- Python 3.9 or newer is recommended.
- Python 3.8 may work for many scripts, but the project should be treated as a
  modern Python 3 codebase.

## Required Python Packages

These are required by the current active scripts:

- `numpy`
- `matplotlib`

`numpy` is used by `script/gdp-util` for CASA column summarization and numeric
metadata calculations, and by `script/gdp-stats` for gain/bandpass statistics,
structure functions, correlation products, and NPZ output.

`matplotlib` is used by `script/gdp-plot` and by
`script/gdp-stats --gain-colormap` to write PNG, PDF, and EPS diagnostic plots
from GDP NPZ products.

## CASA / casa6 Requirements

`script/gdp-util` and `script/gdp-stats` require CASA/casa6 when they read CASA
calibration tables or Measurement Sets because they import `casatools.table`.

Required CASA tools currently used:

- `casatools.table`

Scripts known to require CASA/casa6 for normal operation:

- `script/gdp-util` for `--header`, `--date`, and `--channel-width`
- `script/gdp-stats` for gain/bandpass table statistics
- `script/gdp-plot` indirectly requires CASA/casa6 only when it has to run
  `script/gdp-stats` to create a missing NPZ product.

Recommended environment note:

- Run CASA-dependent scripts inside CASA Python or an environment where
  `casatools` imports cleanly.
- Record the exact CASA/casa6 version here once GDP is tested against a
  specific installed version.

## Optional Python Packages

No optional active-script Python packages are currently required.

## Standard-Library Only Scripts

- `script/gdp-setup` uses only the Python standard library.
- `script/gdp-util --git-push` uses only the Python standard library plus the
  external `git` executable.
- `script/gdp-plan-run` uses only the Python standard library and runs the
  underlying GDP command dependencies for each intent.

## External Commands

- `git`: required by `script/gdp-util --git-push`.

## Maintenance Rule

Whenever code imports a new non-standard package, requires a particular CASA
tool or CASA version, or relies on an external executable, update this file in
the same change.
