# GDP Development Plan

This document records the current development direction for GDP (Gain
Diagnostic Product). It is intended as a planning note and should evolve as the
software design becomes more concrete.

## 1. Shared Function Library

Core reusable functions should be kept in a shared library module, provisionally
named `gdp-funcs.py`. This module will provide the common computational,
I/O, diagnostic, plotting, and flagging functionality used by the GDP command
line interfaces.

The command-line tools should be thin interfaces over this library wherever
possible. This will keep the implementation maintainable, reduce duplication,
and allow the same functions to be used from scripts, pipelines, notebooks, and
future automated workflows.

## 2. Command-Line Interfaces

GDP may provide several command-line interfaces. The initial planned interfaces
are listed below; additional tools may be added later as the workflow matures.

### `gdp-stats`

`gdp-stats` will calculate antenna-wise gain and bandpass statistics and save
the results in a defined NPZ data-product format. Optional CSV output may also
be supported.

The NPZ format, including array names, metadata fields, headers, dimensions,
and conventions, should be documented in the README files. Generated NPZ and
CSV files should be written under `rundir/data-product`.

By default, `rundir/data-product` should be created inside the GDP project
directory. The output location should also be configurable through the CLI so a
user can choose a different work path.

### `gdp-plot`

`gdp-plot` will create plots from GDP statistics and data products. It should
support plotting all standard diagnostics as well as selecting particular plot
types when needed. It should also support focused plots, such as plots for a
single antenna, selected antennas, scans, stokes, components, or other
diagnostic subsets.

Plot products should be saved as PNG by default under `rundir/plots/png` inside
the GDP project directory. If a work path is supplied, the plot directory should
be created there instead. Alternative output formats such as EPS and PDF should
be supported when requested.

### `gdp-diagnose`

`gdp-diagnose` will inspect the statistics and identify problematic gain or
bandpass behavior. It should determine which parts of the gain are bad and
produce antenna-based flag recommendations.

The diagnostic logic should support different statistical modes, including
single-antenna tests and real/imaginary component tests. Even when a diagnostic
is based on one component, the resulting flagging policy may apply to both real
and imaginary components where scientifically appropriate.

The tool should support iterative operation, allowing diagnosis and flag
generation to run in loops. Loop count, thresholds, statistic choices, and
related diagnostic controls should be available through CLI options.

### `gdp-flag`

`gdp-flag` will translate antenna-based flag recommendations into baseline or
MeasurementSet-level flags. It should be able to create a flag version that can
be applied to a MeasurementSet, and where appropriate it may add or update a
flag column in an MS.

This interface should also be able to run `gdp-stats` with flags applied, so
users can evaluate the effect of flagging on the resulting statistics.

Antenna-based flag products should be saved under `rundir/flag` using a defined
NPZ format. The flag NPZ format, including metadata, dimensions, and meaning of
each array, should be documented in the README files.

### `gdp-setup`

`gdp-setup` will initialize a GDP working environment. It should create the
runtime directory at a user-selected location and build the expected runtime
subfolder structure below it.

The setup command should also record the source-data folder that GDP commands
will use as their default input location. Other GDP tools should be able to
read this saved configuration so users do not need to repeatedly provide the
same runtime path and source-data path.

The remembered configuration should include, at minimum:

- the GDP runtime directory;
- the source-data directory;
- paths for data products, plots, and flag products;
- any future project-level defaults needed by the CLI tools or pipeline runner.

The configuration format should be simple, inspectable, and documented. It may
be stored as a file inside the GDP project or inside the selected runtime
directory, depending on which approach best supports portability and repeated
use.

## 3. Pipeline Design

GDP should support pipeline setup files for repeatable workflows. A pipeline
will be composed of named intents. Intents are implemented by internal GDP
Python scripts or command-line tools.

Intent names should generally match the command names without the `.py`
extension. For example, a pipeline may contain an intent named `gdp-diagnose`.

Each intent block should provide inputs in a simple name/value style. CLI input
names and values may be written on separate lines using `:` between the input
name and value. Only non-default values need to be specified in the pipeline
file.

Pipeline values should also be able to reference pipeline-internal variables.
This will allow common paths, scan selections, thresholds, and product
locations to be defined once and reused across multiple intents.

The initial runner for this design is `gdp-plan-run`. It should read a plan
file, expand internal variables and saved setup paths, translate intent
key/value lines into CLI flags, and run GDP command scripts from `script/`.

## 4. Documentation Structure

GDP documentation should eventually live under a `doc/` directory rather than
as a single top-level README page.

The documentation should include multiple HTML pages organized as a hierarchical
tree. The main page should describe the major GDP functionality and link to
separate pages for the major functions, command-line interfaces, data-product
formats, flag-product formats, pipeline configuration, and examples.

Separate functions or command groups should have their own HTML pages. These
pages should be linked from the main documentation tree in a clear hierarchy.

The documentation should explain all available options and product formats.
Eventually, generated plot documentation should include representative example
plots so users can understand the expected outputs visually.

## 5. Development Notes

These points should remain active considerations during development:

- Keep active requirements based on the maintained scripts in `script/`.
  Archive/reference code under `arx/` should not drive long-term requirements.
- Keep CLI tools consistent in naming, option style, output paths, and data
  product conventions.
- Document every stable NPZ product format before treating it as part of the
  public GDP workflow.
- Update README files and `REQUIREMENTS.md` whenever new behavior,
  dependencies, or product formats are introduced.
