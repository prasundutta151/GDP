# GDP Developer Notes

This file is the running developer log for GDP (Gain Diagnostic Product). Add a
new timestamped entry whenever the code, documentation, packaging, or workflow
changes.

Entry format:

```text
## YYYY-MM-DD HH:MM:SS TZ

Prompt / Request
- Polished summary of what was asked.

Changes Made
- What changed in code, docs, data products, packaging, or workflow.

Verification
- Commands or checks run.

Notes
- Follow-up context, assumptions, or cautions.
```

## 2026-07-15 11:09:52 IST

Prompt / Request
- Create the initial GDP project folder in `Documents`, using the GMRTCAL
  project files as a reference pattern.
- Add documentation files, a version file, a git push helper, workflow folders,
  and an `arx/` folder containing the Python scripts from GainStat.

Changes Made
- Created the top-level GDP project layout.
- Added `arx/` and copied all top-level GainStat Python scripts into it.
- Added `script/`, `rundir/`, `sample_plots/`, and `pipelines/` folders.
- Added `README.md`, `README.html`, `VERSION`, `DEV_NOTES.md`,
  `push_to_git.sh`, and `.gitignore`.

Verification
- Confirmed the source GainStat folder contained 18 Python scripts.
- Confirmed the new GDP `arx/` folder contains the copied Python scripts.

Notes
- `rundir/` is intended for runtime products and is ignored by git except for
  its `.gitkeep` placeholder.

## 2026-07-15 11:16:00 IST

Prompt / Request
- Add a maintained requirements note and keep it updated whenever a Python
  package, CASA version, CASA tool, or other dependency is needed.

Changes Made
- Added `REQUIREMENTS.md` with current required packages, CASA/casa6 tool
  requirements, optional packages, and a maintenance rule.
- Updated `README.md` and `README.html` to point to `REQUIREMENTS.md`.

Verification
- Scanned `arx/*.py` imports for non-standard dependencies.
- Identified required `numpy`, `matplotlib`, `scipy`, and CASA `casatools`
  usage, plus optional `scikit-learn` and `astropy`.

Notes
- The exact tested CASA/casa6 version has not yet been recorded; add it to
  `REQUIREMENTS.md` after testing in the target CASA environment.

## 2026-07-15 11:24:00 IST

Prompt / Request
- Keep flag products, plots, and data products under `rundir` rather than as
  top-level project directories.

Changes Made
- Moved the planned runtime directory layout to `rundir/data-product`,
  `rundir/plots/png`, and `rundir/flag`.
- Removed the top-level runtime placeholders for `data-product`, `plots`, and
  `flag`.
- Updated `.gitignore`, `DEV_PLAN.md`, `README.md`, and `README.html` to
  reflect the `rundir`-based layout.

Verification
- Created `.gitkeep` placeholders for the expected `rundir` subdirectories.

Notes
- Runtime products remain ignored by git; only placeholder files are tracked to
  preserve the layout.

## 2026-07-15 11:31:00 IST

Prompt / Request
- Add the planned `gdp-setup` interface to the development plan.

Changes Made
- Updated `DEV_PLAN.md` with `gdp-setup` as the command responsible for
  initializing a GDP runtime directory, creating expected subfolders, recording
  the source-data directory, and saving configuration for other GDP commands.

Verification
- Confirmed the plan now lists the minimum remembered configuration: runtime
  directory, source-data directory, data-product path, plot path, flag-product
  path, and future project-level defaults.

Notes
- The exact configuration file location and format remain design decisions for
  the implementation phase.

## 2026-07-15 12:05:38 IST

Prompt / Request
- From now on, record all further development in `DEV_NOTES.md` and create the
  necessary README and sub-HTML documentation files in `doc`.
- Implement `gdp-setup` in the active scripts folder.
- Implement `gdp-util` with table-information utilities such as a `--header`
  command-line mode.

Changes Made
- Added `script/gdp-setup`, an executable CLI that creates a GDP runtime
  directory, builds the standard subfolder structure, records the source-data
  directory, and writes a reusable JSON configuration.
- Added `script/gdp-util`, an executable CLI that can print saved GDP setup
  configuration and read CASA table metadata through modes including
  `--header`, `--date`, and `--channel-width`.
- Updated `.gitignore` for the current `rundir` subfolder layout and ignored
  the local `.gdp-config.json` setup state.
- Added tracked placeholders for the current runtime subfolders:
  `rundir/data-product/stats/npz`, `rundir/data-product/stats/csv`,
  `rundir/data-product/flag/npz`, `rundir/data-product/flag/csv`,
  `rundir/plots/png`, `rundir/plots/eps`, and `rundir/plots/pdf`.
- Reworked `doc/README.md` and `doc/README.html` as the documentation entry
  point.
- Added `doc/gdp-setup.html`, `doc/gdp-util.html`, and `doc/style.css`.
- Updated `REQUIREMENTS.md` so active requirements are based on maintained
  scripts in `script/`, not archived reference scripts in `arx/`.

Verification
- `python3 -m py_compile script/gdp-setup script/gdp-util`
- Parsed all `doc/*.html` files with Python `html.parser`.
- `script/gdp-setup --source-data /tmp --rundir /tmp/gdp-rundir-dryrun --dry-run`
- `script/gdp-util --config --json`

Notes
- `gdp-util` currently requires CASA/casa6 only for table-reading modes. The
  `--config` mode works without CASA.
- `gdp-setup` uses only the Python standard library.

## 2026-07-15 12:21:37 IST

Prompt / Request
- Add `gdp-util --git-push` to create a versioned archive, add it to git, and
  stage/commit/push project notes and documentation files.
- Add `gdp-stats` based on the AntStat-style statistics workflow, saving NPZ by
  default and optional CSV output.
- Update README/documentation and developer notes.

Changes Made
- Extended `script/gdp-util` with `--git-push`, `--message`, and `--no-push`.
  The new mode creates `gdp-<VERSION>.tgz`, stages core GDP files and docs,
  force-adds the version archive, commits staged changes, and pushes the
  current branch unless `--no-push` is supplied.
- Added `script/gdp-stats`, which reads CASA gain/bandpass tables, applies
  optional FLAG masking, optionally subtracts real/imag means, computes
  antenna-wise statistics by scan/stokes/component, and writes a GDP stats NPZ
  product.
- Added optional CSV output for `gdp-stats`.
- Documented the GDP stats NPZ format in `doc/gdp-stats.html`.
- Updated `doc/README.md`, `doc/README.html`, and `doc/gdp-util.html`.
- Updated `REQUIREMENTS.md` to include active `gdp-stats` dependencies and the
  external `git` executable requirement for `gdp-util --git-push`.

Verification
- `python3 -m py_compile script/gdp-setup script/gdp-util script/gdp-stats`
- Parsed all `doc/*.html` files with Python `html.parser`.
- Checked `script/gdp-stats --help`.
- Checked `script/gdp-util --help`.

Notes
- `gdp-stats` computes skewness and excess kurtosis with NumPy to avoid adding
  SciPy as an active dependency.
- `gdp-util --git-push` was not executed during verification to avoid making an
  unintended commit or remote push.

## 2026-07-15 12:29:57 IST

Prompt / Request
- Add a `gdp-plan-run` script that can read a plan file and run GDP commands
  such as `gdp-stats`.
- Support internal variables in the plan.
- Add a sample plan under `pipelines`.
- Update README/documentation and developer notes.

Changes Made
- Added `script/gdp-plan-run`, a plan runner that reads `variables:` blocks and
  GDP intent blocks, expands `${variable}` references, translates intent
  key/value lines into CLI flags, and runs GDP scripts from `script/`.
- Added support for saved `gdp-setup` paths as plan variables when
  `.gdp-config.json` exists.
- Added `--dry-run` and `--only` options to the plan runner.
- Added `pipelines/sample_stats.plan` as a working example plan for
  `gdp-stats`.
- Added `doc/gdp-plan-run.html`.
- Updated `doc/README.md`, `doc/README.html`, `DEV_PLAN.md`, and
  `REQUIREMENTS.md`.

Verification
- `python3 -m py_compile script/gdp-plan-run`
- `script/gdp-plan-run pipelines/sample_stats.plan --dry-run`
- Parsed all `doc/*.html` files with Python `html.parser`.
- Checked `script/gdp-plan-run --help`.

Notes
- The sample plan uses placeholder input data so it can be dry-run on a fresh
  checkout. Replace the placeholder path with a real CASA table or use
  `${source_data}` after running `gdp-setup`.

## 2026-07-15 12:31:38 IST

Prompt / Request
- Improve readability of text inside the black code boxes in the HTML
  documentation.

Changes Made
- Updated `doc/style.css` so `<pre>` code blocks use a brighter light-blue text
  color.

Verification
- Parsed all `doc/*.html` files with Python `html.parser`.

Notes
- This affects all documentation pages that use the shared `doc/style.css`.

## 2026-07-15 12:33:09 IST

Prompt / Request
- Remove the unreadable dark/background styling from documentation code boxes.

Changes Made
- Updated `doc/style.css` so inline code and block code use transparent
  backgrounds.
- Changed `<pre>` blocks to use normal page text color with a light border
  instead of a dark filled box.

Verification
- Parsed all `doc/*.html` files with Python `html.parser`.

Notes
- This keeps code examples visible on the normal documentation page background.

## 2026-07-15 12:34:41 IST

Prompt / Request
- Keep documentation code blocks with a black background and light-blue
  foreground.

Changes Made
- Updated `doc/style.css` so `<pre>` blocks use a near-black background and
  bright light-blue text.
- Added explicit `pre code` styling so nested code text inherits the same
  light-blue foreground.

Verification
- Parsed all `doc/*.html` files with Python `html.parser`.

Notes
- Inline code outside code blocks remains on a transparent background.

## 2026-07-15 12:45:38 IST

Prompt / Request
- Make `gdp-setup` remember the gain directory and runtime directory so later
  commands such as `gdp-stats` do not need those paths by default.
- Extend `gdp-stats` with subtask flags: `--gains`, `--stats`, `--ks`,
  `--self-corr`, `--cross-corr`, and `--all`.
- Add per-task log files and console timing messages.
- Update the sample plan and documentation.

Changes Made
- Extended `script/gdp-setup` with `--gain-dir` and saved both `gain_dir` and
  `source_data` in `.gdp-config.json`.
- Added runtime paths for gains products, KS products, self/cross-correlation
  products, and logs.
- Reworked `script/gdp-stats` into a task-oriented command. If no input table
  is provided, it now defaults to the saved `gain_dir` or `source_data`.
- Added `--gains` to write long-table-style raw selected gain samples in NPZ.
- Kept `--stats` as the mean/std/skew/kurtosis statistics product, now with
  explicit subtask selection.
- Added `--ks` as a documented KS product schema placeholder.
- Added `--self-corr` and `--cross-corr` as logged planned subtasks.
- Added `--all` to request all GDP stats subtasks.
- Added timestamped log files under the configured `logs_dir`, with start/done
  messages and elapsed seconds printed to the terminal as well.
- Updated `pipelines/sample_stats.plan` so it relies on saved setup input paths
  rather than repeating the gain table path.
- Updated `doc/README.md`, `doc/README.html`, `doc/gdp-setup.html`,
  `doc/gdp-stats.html`, and `doc/gdp-plan-run.html`.

Verification
- `python3 -m py_compile script/gdp-setup script/gdp-stats script/gdp-plan-run script/gdp-util`
- `script/gdp-setup --gain-dir /tmp/example.g --rundir /tmp/gdp-rundir-setup-test --allow-missing-source --dry-run`
- `script/gdp-plan-run pipelines/sample_stats.plan --dry-run`
- `script/gdp-stats --help`
- Parsed all `doc/*.html` files with Python `html.parser`.

Notes
- Full KS sample calculation and structure-function self/cross correlation are
  still future implementation work; the CLI and product locations are now
  reserved and logged.

## 2026-07-15 12:48:46 IST

Prompt / Request
- Use the self and cross correlation algorithms from archived Python scripts in
  `arx` to fill the `gdp-stats` correlation gaps.

Changes Made
- Added a native structure-function implementation to `script/gdp-stats`,
  adapted from the archived GainStat/AntStat correlation logic.
- Implemented `--self-corr` as a real product that computes normalized order-2
  self structure functions for selected scan, antenna, stokes, and component
  combinations.
- Implemented `--cross-corr` as a real product that computes cross structure
  functions and writes threshold-based `tcorr` values for selected
  antenna/stokes/component pairs.
- Added correlation controls: `--corr-threshold`, `--corr-nbin`,
  `--corr-bintype`, and `--corr-njack`.
- Added output controls: `--output-self-corr-npz` and
  `--output-cross-corr-csv`.
- Updated `doc/gdp-stats.html`, `doc/README.md`, `doc/README.html`, and
  `REQUIREMENTS.md` to document the active correlation products.

Verification
- `python3 -m py_compile script/gdp-stats script/gdp-setup script/gdp-plan-run script/gdp-util`
- `script/gdp-stats --help`
- `script/gdp-plan-run pipelines/sample_stats.plan --dry-run`
- Parsed all `doc/*.html` files with Python `html.parser`.

Notes
- `--ks` is still a schema placeholder; the self/cross structure-function
  products are now implemented.

## 2026-07-15 12:51:46 IST

Prompt / Request
- Keep standard output names for all NPZ data products and document those names
  and formats in sub-HTML pages.

Changes Made
- Standardized default GDP product filenames in `script/gdp-stats`:
  `gdp-gains-<mode>-<scan>.npz`, `gdp-stats-<mode>-<scan>.npz`,
  `gdp-ks-<mode>-<scan>.npz`, and
  `gdp-self-corr-<mode>-<scan>.npz`.
- Kept cross-correlation CSV naming aligned as
  `gdp-cross-corr-<mode>-<scan>.csv`.
- Added dedicated product-format pages:
  `doc/gdp-product-gains.html`, `doc/gdp-product-stats.html`,
  `doc/gdp-product-ks.html`, and `doc/gdp-product-self-corr.html`.
- Updated `doc/gdp-stats.html` to list standard filenames and link to the
  product-format pages.
- Updated `doc/README.html`, `doc/README.md`, and
  `pipelines/sample_stats.plan`.

Verification
- `python3 -m py_compile script/gdp-stats script/gdp-setup script/gdp-plan-run script/gdp-util`
- Parsed all `doc/*.html` files with Python `html.parser`.
- `script/gdp-plan-run pipelines/sample_stats.plan --dry-run`

Notes
- The scan field is `allscans` by default, or `scan1-2`/`scan5` style when
  `--scan` is supplied.

## 2026-07-15 12:54:30 IST

Prompt / Request
- Clarify the product format documentation for cross correlation.

Changes Made
- Added `doc/gdp-product-cross-corr.html` to document the standard
  `gdp-cross-corr-<mode>-<scan>.csv` product name, output location, columns,
  and related CLI options.
- Updated `doc/gdp-stats.html` and the documentation index pages to link the
  cross-correlation CSV format alongside the NPZ product-format pages.

Notes
- Cross correlation is currently a CSV product, not an NPZ product.

Follow-up
- Reworded `doc/gdp-stats.html` so cross correlation appears as its own CSV
  product format in the product-format table, instead of being described as an
  exception below an NPZ-only section.

## 2026-07-15 12:57:42 IST

Prompt / Request
- Add the documentation tree to all HTML pages so every page can navigate to
  the other documentation pages.

Changes Made
- Added a shared documentation tree block to every `doc/*.html` page.
- Removed the single-purpose back links from command and product pages.
- Added `.doc-tree` styling in `doc/style.css` so the tree reads as a compact
  navigation panel.

## 2026-07-15 13:01:03 IST

Prompt / Request
- Change cross-correlation saving so it writes NPZ by default like the other
  GDP data products, while keeping CSV as an optional secondary output.

Changes Made
- Added `--output-cross-corr-npz` to `script/gdp-stats`.
- Changed `gdp-stats --cross-corr` to write
  `gdp-cross-corr-<mode>-<scan>.npz` by default under
  `data-product/cross-corr/npz`.
- Kept cross-correlation CSV output optional through `--csv` or
  `--output-cross-corr-csv`.
- Added `cross_corr_npz_dir` to `gdp-setup` runtime configuration and added
  the `rundir/data-product/cross-corr/npz` placeholder directory.
- Updated cross-correlation docs from CSV-default to NPZ-default and documented
  the optional CSV export.

## 2026-07-15 13:02:54 IST

Prompt / Request
- Keep `Documentation Tree` and `Product Formats` as separated blocks in the
  HTML documentation.

Changes Made
- Split the product-format links out of the shared `Documentation Tree` block
  on every `doc/*.html` page.
- Added a separate shared `Product Formats` block with links to each product
  format page.
- Updated `doc/style.css` so both navigation blocks use consistent compact
  styling.

## 2026-07-15 13:04:16 IST

Prompt / Request
- In usage examples, mention the purpose of each command line after the line or
  in brackets.

Changes Made
- Added bracketed purpose notes to each command line in the Usage sections for
  `gdp-setup`, `gdp-util`, `gdp-stats`, and `gdp-plan-run`.
- Added matching bracketed notes to the quick-start command block in
  `doc/README.html`.

## 2026-07-15 13:12:04 IST

Prompt / Request
- Check archived plotting scripts and create `gdp-plot`.
- `gdp-plot` should use NPZ files created by `gdp-stats`; if those NPZ files
  do not exist, it should run `gdp-stats` first and then create plots.
- Add a `gdp-plot` intent example for `gdp-plan-run`.

Changes Made
- Added `script/gdp-plot`.
- Implemented plotting from GDP NPZ products for:
  `--gain-colormap`, `--stats`, `--ks`, `--self-corr-colormap`, and
  `--cross-corr-colormap`.
- Added `--mode {gain,bandpass,both}`, `--antenna`, `--all`, `--plot-dir`,
  `--format`, `--recompute`, and `--dry-run`.
- `gdp-plot` discovers standard GDP product names and runs `script/gdp-stats`
  with the matching subtask when a requested NPZ is missing.
- Added `doc/gdp-plot.html`, linked `gdp-plot` from all HTML documentation
  trees, and updated the main README docs.
- Added a `gdp-plot` intent to `pipelines/sample_stats.plan`.
- Updated `REQUIREMENTS.md` to include `matplotlib`.

Notes
- `--all` currently means gain colormap, stats, and KS plots, following the
  requested grouping. Self/cross correlation plots remain explicit flags.

## 2026-07-15 13:25:06 IST

Prompt / Request
- Change of plan: add the gain/bandpass colormap option to `gdp-stats` as well.
- The option should be off by default. When set, it should produce plots.

Changes Made
- Added `--gain-colormap` to `script/gdp-stats`.
- Added `--output-gain-colormap` and `--plot-format {png,pdf,eps}` to control
  the optional plot output.
- `gdp-stats --gain-colormap` now turns on the gains NPZ product, then writes
  `gdp-plot-gain-colormap-<mode>-<scan>.png` by default under
  `rundir/plots/png`.
- Updated `doc/gdp-stats.html`, `doc/gdp-plot.html`, `doc/README.html`, and
  `REQUIREMENTS.md`.

Notes
- `gdp-stats --all` remains product-only and does not automatically make plots.

## 2026-07-15 13:29:43 IST

Prompt / Request
- Add a `combine-scans` option to both `gdp-stats` and `gdp-plot`.
- Default should be false, so scan-specific products and plots are made
  separately. When combined, use `allscans` naming.

Changes Made
- Added `--combine-scans` to `script/gdp-stats`.
- Changed the default `gdp-stats` behavior to write one product per scan:
  `scan1`, `scan2`, etc.
- With `gdp-stats --combine-scans`, selected scans are written as one combined
  product using `allscans` naming when no explicit scan list is supplied.
- Added `--combine-scans` to `script/gdp-plot`.
- Changed the default `gdp-plot` behavior to plot one product per scan, while
  `--combine-scans` plots one combined product.
- Updated `pipelines/sample_stats.plan` to use `combine-scans: true` because it
  supplies explicit allscans output paths.
- Updated command docs and product format examples to explain scan-specific and
  combined naming.

## 2026-07-15 13:51:35 IST

Prompt / Request
- Correct the `gain-colormap` output in both `gdp-stats` and `gdp-plot`.
- It should follow the `plot_gain_colormap` style from `arx/AntStat.py`, not
  the temporary median-amplitude plot.

Changes Made
- Replaced the median-amplitude gain colormap in `script/gdp-stats` with
  AntStat-style Real-1 and Imag percent colormap panels.
- Made `script/gdp-plot --gain-colormap` use the same Real-1/Imag percent
  plotting logic.
- Flagged or missing data are masked to white, and the color scale is symmetric
  around zero using the 99th percentile absolute value.
- Updated CLI help and HTML docs to describe the Real-1/Imag percent colormap
  behavior.

## 2026-07-15 14:15:00 IST

Prompt / Request
- Make the gain colormap look closer to `arx/AntStat.py`.
- Use elapsed seconds on the vertical axis, read the integration time for each
  timestamp, simplify the plot title to include the scan number, and reduce
  horizontal/vertical tick-label font size.

Changes Made
- Added `time` and `interval` arrays to the GDP gains NPZ product, sourced from
  the CASA `TIME` and `INTERVAL` columns.
- Updated `script/gdp-stats --gain-colormap` and `script/gdp-plot
  --gain-colormap` to use elapsed seconds for gain-mode plot geometry and tick
  labels, with interval-aware time-bin edges.
- Kept bandpass colormaps on channel axes.
- Changed colormap figure titles to `<mode> <scan> colormap [%]`, for example
  `gain scan3 colormap [%]`.
- Reduced x/y tick-label sizes on gain colormap panels and colorbars.
- Updated the gains product-format page and the `gdp-stats`/`gdp-plot` HTML
  pages.

## 2026-07-15 14:28:38 IST

Prompt / Request
- Show mean, std, skew, and kurtosis at the top of each gain-colormap subplot.

Changes Made
- Restored per-panel statistics in the subplot titles for both
  `script/gdp-stats --gain-colormap` and `script/gdp-plot --gain-colormap`.
- The values are computed over the unmasked points displayed in that exact
  subplot.

## 2026-07-15 14:31:38 IST

Prompt / Request
- Format the full gain-colormap title as
  `Gain Table: <table> | Scan: <scan> [%]`.
- Make the colorbar span the plot from top to bottom, remove the right-column
  y-axis label, and reduce whitespace between subplots.

Changes Made
- Updated both `script/gdp-stats --gain-colormap` and `script/gdp-plot
  --gain-colormap` to use the requested full-figure title format.
- `gdp-plot` reads the input table name from the gains NPZ `header_json`; the
  direct `gdp-stats` path uses the in-memory gains header.
- The shared colorbar now attaches to all gain-colormap subplot axes.
- Removed repeated y-axis labels from the right column and tightened subplot
  horizontal/vertical spacing.

## 2026-07-15 14:35:35 IST

Prompt / Request
- `gdp-setup` should have separate options for gain and bandpass tables.

Changes Made
- Added `--gain-table` and `--bandpass-table` to `script/gdp-setup`.
- Kept `--gain-dir` as a backward-compatible alias for `--gain-table`.
- Saved separate `gain_table` and `bandpass_table` keys in `.gdp-config.json`.
- Updated `script/gdp-stats` so gain mode defaults to `gain_table` and bandpass
  mode defaults to `bandpass_table` when no explicit input table is supplied.
- Added `--gain-table` and `--bandpass-table` forwarding to `script/gdp-plot`
  for missing-product creation.
- Updated `script/gdp-util` to fall back to saved gain or bandpass tables when
  no general `source_data` path is configured.
- Updated setup, stats, plot, plan-run, and README documentation.

## 2026-07-15 14:42:11 IST

Prompt / Request
- Add the `plot_gain_histogram` functionality from `arx/AntStat.py` to
  `gdp-plot` with a `--gain-hist` CLI option.
- Use the GDP gains NPZ product that stores the full gain-table samples.

Changes Made
- Added `gdp-plot --gain-hist`, backed by the existing gains NPZ product
  created by `gdp-stats --gains`.
- Added missing-product creation for `--gain-hist`, so `gdp-plot` runs
  `gdp-stats --gains` first when the required gains NPZ is absent.
- Replicated the AntStat histogram behavior: per-Stokes rows, Real-1 and Imag
  columns, gain value in percent on the y-axis, antenna on the x-axis, and
  log10 percentage per antenna as the color value with empty bins masked white.
- Added `--hist-bins` and `--hist-range MIN,MAX` for histogram binning control.
- Updated plot documentation, README examples, and standard plot-name notes.

## 2026-07-15 14:46:46 IST

Prompt / Request
- Replace individual `gdp-plot` plot-selection flags with a `-pmode` option.
- Supported modes should include `gain-colormap`, `gain-hist`, `antenna`,
  `stats`, `ks`, `self-corr-colormap`, `self-corr-antenna`, and
  `cross-corr-colormap`.
- Use the AntStat single-antenna gain-time and bandpass-channel plotting style
  for `-pmode antenna`.

Changes Made
- Added `-pmode`/`--pmode` to `script/gdp-plot`, accepting comma-separated or
  space-separated plot mode names.
- Kept the older individual flags as hidden compatibility aliases.
- Added `-pmode antenna`, using the GDP gains NPZ to write separate plots for
  each selected antenna and Stokes. Gain mode plots Real-1 and Imag versus
  elapsed seconds; bandpass mode plots Real-1 and Imag versus channel.
- Added `-pmode self-corr-antenna`, which writes per-antenna self-correlation
  line plots from the self-corr NPZ product.
- Updated documentation examples to use `-pmode`.

## 2026-07-15 15:02:00 IST

Prompt / Request
- When `-pmode` is `antenna`, allow antenna numbers to be written directly
  after `antenna`, and plot Real/Imag for both Stokes if both are present.

Changes Made
- Added hidden trailing positional values to `script/gdp-plot`.
- If `-pmode antenna` is selected and `--antenna` is not supplied, trailing
  values such as `3` or `3,5` are treated as the antenna list.
- The existing antenna plotter already writes one Real/Imag plot per selected
  antenna and every Stokes present in the gains NPZ.
- Updated `gdp-plot` and README documentation examples.

## 2026-07-15 15:11:54 IST

Prompt / Request
- Add mean, std, skew, and kurtosis values to gain histogram plots.

Changes Made
- Added per-panel sample statistics to `gdp-plot -pmode gain-hist` subplot
  titles.
- Statistics are computed from the Real-1 or Imag samples used to build each
  histogram panel, after antenna/stokes/flag filtering.

## 2026-07-15 15:14:14 IST

Prompt / Request
- In `-pmode antenna`, plot both Stokes side by side.

Changes Made
- Changed `gdp-plot -pmode antenna` from one file per antenna/Stokes to one
  file per antenna.
- Each antenna plot now has Stokes as columns and Real-1/Imag as stacked rows.
- Updated `gdp-plot` and README documentation to describe the side-by-side
  Stokes layout.

## 2026-07-15 15:15:24 IST

Prompt / Request
- If an antenna is absent, mention it in terminal/log output instead of giving
  an error.

Changes Made
- Updated `gdp-plot -pmode antenna` to print a skip message for requested
  antennas that are absent from the gains NPZ.
- Fully flagged or otherwise non-finite selected antennas are also reported as
  skipped with sample/flag counts.
- The plot task now continues with any remaining valid antennas and no longer
  raises an error when all requested antennas are absent or unusable.

## 2026-07-15 15:25:17 IST

Prompt / Request
- Rework `pmode stats`, `pmode ks`, `pmode self-corr-colormap`, and
  `pmode self-corr-antenna` to follow the corresponding plotting functions in
  `arx/AntStat.py`.

Changes Made
- Changed `pmode stats` to use the full gains NPZ and plot an AntStat-style
  2x2 per-antenna grid: mean, std, skewness, and kurtosis.
- Changed `pmode ks` to use the full gains NPZ and compute/plot AntStat-style
  per-antenna normal KS D-statistics for Real-1 and Imag by Stokes.
- Updated `pmode self-corr-colormap` to use Stokes rows, Real-1/Imag columns,
  antenna x-axis, tau y-axis, log10(S2) color, and threshold markers.
- Updated `pmode self-corr-antenna` to use AntStat-style structure-function
  line plots with S2=1 and threshold reference lines.
- Added `--s2-thr` to control the self-correlation threshold marker.

## 2026-07-15 15:30:56 IST

Prompt / Request
- Fix `gdp-stats --self-corr` crash when flagged or missing data leaves empty
  antenna samples; skipped antennas should not stop the scan, and plots should
  show missing products as white/blank cells.

Changes Made
- Fixed NPZ header serialization by converting NumPy arrays and scalar values
  to JSON-safe Python types before writing `header_json`.
- Updated self-correlation generation to keep fixed lag-bin rows for
  antenna/stokes/component series with fewer than two finite unflagged samples.
  These rows save NaN `s2`/`err` values and zero `count`, so plotting can leave
  them white.
- Added terminal skip messages for unusable self-correlation series while
  allowing the remaining antennas to continue.
- Removed empty-slice warnings from the time/channel averaging step and made
  jackknife error calculation tolerant of empty lag bins.

## 2026-07-15 15:33:01 IST

Prompt / Request
- In the `gdp-plot` HTML documentation, keep the `-pmode` options together and
  color their background light blue.

Changes Made
- Grouped all `-pmode` option rows together in `doc/gdp-plot.html`.
- Added a shared CSS style for `pmode` rows with a light-blue table background.

## 2026-07-15 15:36:03 IST

Prompt / Request
- Modify `gdp-stats` so the saved statistics products use the proper
  per-antenna calculations implied by the AntStat plotting functions:
  `plot_antenna_gain_stats_grid`, `plot_antenna_gain_ks_grid`,
  `plot_structure_function_colormap`, and `plot_single_structure_function`.

Changes Made
- Updated the stats product calculation to follow the AntStat convention:
  real samples are `real(gain)-1`, imaginary samples are `imag(gain)`, and
  mean/std/median/MAD/min/max are saved in percent while skew/kurtosis remain
  dimensionless.
- Changed `--subtract-mean` default to false so the default statistics match
  AntStat plot behavior.
- Replaced the KS placeholder with an actual AntStat-style fitted-normal KS
  D-statistic product, saved in percent per scan/antenna/stokes/component.
- Documented the updated stats and KS product conventions in the HTML docs.

## 2026-07-15 15:39:50 IST

Prompt / Request
- Fix `gdp-plot -pmode stats` and `gdp-plot -pmode ks`, which were still
  plotting only one antenna instead of the full antenna-wise products.

Changes Made
- Routed `pmode stats` to the stats NPZ directory and `gdp-stats --stats`
  instead of the gains NPZ product.
- Routed `pmode ks` to the KS NPZ directory and `gdp-stats --ks` instead of
  the gains NPZ product.
- Updated the stats and KS plotting functions to read the saved product axes
  directly, so the plots use the full `antennas` axis in the stats/KS NPZ.
- Updated `gdp-plot` documentation to describe stats and KS as product-based
  plots rather than gains-NPZ-derived plots.

## 2026-07-15 15:50:50 IST

Prompt / Request
- Copy representative generated plots into `doc/sample_plots` and add a
  `Sample Plots` block to every HTML documentation page with links,
  descriptions, and the commands used to produce them.

Changes Made
- Copied representative gain colormap, gain histogram, antenna time-series,
  stats, KS, self-correlation colormap, and self-correlation antenna plots into
  `doc/sample_plots`.
- Added a shared `Sample Plots` section to every HTML page.
- Added CSS styling for the shared sample plot block and command column.

## 2026-07-15 15:58:23 IST

Prompt / Request
- Add a `gdp-util` option to change `VERSION`: bare `--version` should bump a
  lower version number, `--version main` should bump/start a higher main version
  number, and `--version <number>` should set a specific version.

Changes Made
- Added `script/gdp-util --version` with optional value handling.
- Bare `--version` bumps the patch number.
- `--version main` bumps the major number and resets minor/patch to zero.
- `--version NUMBER` validates and writes the requested semantic version.
- Updated `gdp-util` HTML documentation with usage examples and option details.

## 2026-07-15 16:00:05 IST

Prompt / Request
- If `--version` and `--git-push` are used together, both actions should run.

Changes Made
- Changed `gdp-util` so `--version` updates `VERSION` first and then continues
  into the `--git-push` workflow when requested.
- Updated `gdp-util` documentation to describe combined version bump and git
  push behavior.

## 2026-07-15 16:41:58 IST

Prompt / Request
- Add a step-by-step software guide linked from `README.html`, including what
  to do, command boxes, runtime output boxes, and plot links. Keep it as a
  guide that should be updated as GDP develops.

Changes Made
- Added `doc/gdp-step-by-step.html` with setup, inspection, stats/KS,
  self-correlation, plotting, plan-running, and release workflow steps.
- Added command blocks, expected runtime-output blocks, and sample plot links.
- Linked the guide from `doc/README.html` in the documentation tree and a
  dedicated step-by-step section.
- Added an update-policy section stating that the guide should be maintained as
  GDP commands, products, plots, and release steps evolve.

## 2026-07-15 17:33:16 IST

Prompt / Request
- In each individual product format page, add a box section with Python
  commands that read the format and explain what is obtained after reading.

Changes Made
- Added `Read This Product In Python` sections to gains, stats, KS,
  self-corr, and cross-corr product format pages.
- Each section includes a NumPy loading example, header parsing, key axis/data
  arrays, and a short explanation of what the arrays represent.
- Added shared styling for format-reader blocks.

## 2026-07-29 10:46:56 IST

Prompt / Request
- Clarify what `--source-data`, `--gain-dir`, `--gain-table`, and
  `--bandpass-table` do, determine whether some are redundant, and keep the
  setup model focused on gain and bandpass table paths with full
  functionality.

Changes Made
- Made `--gain-table` and `--bandpass-table` the documented canonical setup
  inputs.
- Removed public `--source-data` and `--gain-dir` usage from command
  documentation and the saved configuration.
- Kept hidden setup compatibility for old `--source-data`, `--gain-dir`, and
  `--allow-missing-source` command lines without writing those legacy keys.
- Updated `gdp-stats`, `gdp-plot`, and `gdp-util` input resolution so defaults
  come from `gain_table` and `bandpass_table` only.

## 2026-07-29 10:50:02 IST

Prompt / Request
- Add horizontal and vertical scroll bars to the black Usage/code windows in
  the HTML documentation files.

Changes Made
- Updated the shared documentation stylesheet so all `<pre>` code panels have a
  fixed maximum height and both horizontal and vertical scroll bars.

## 2026-07-29 10:53:18 IST

Prompt / Request
- The black Usage windows still did not show visible scroll bars and long text
  was cut in the browser.

Changes Made
- Made documentation code panels use explicit horizontal and vertical scrolling,
  visible light-blue scroll thumbs, and full-width inner code blocks so long
  command lines can be scrolled instead of clipped.

## 2026-07-29 10:56:35 IST

Prompt / Request
- Add a `--setup-file` option so a particular setup filename can be given and
  stored in the runtime directory. If no setup filename is given, use a default
  setup file and archive the earlier default copy with a datetime suffix each
  time it is overwritten.

Changes Made
- Added `script/gdp-setup --setup-file NAME`, storing the setup JSON under the
  selected runtime directory.
- Added the default runtime setup file name `gdp-setup.json`.
- Added automatic archive rotation for the default setup file before overwrite,
  using a `.YYYYMMDDTHHMMSS` suffix.
- Kept the project `.gdp-config.json` active configuration updated so existing
  GDP commands continue to find the current setup.
- Updated setup and quick-start documentation with the new option.

## 2026-07-29 11:04:37 IST

Prompt / Request
- Add `gdp-util` options for gain or bandpass table selection so headers and
  other metadata can be read from the corresponding configured tables.

Changes Made
- Added `script/gdp-util --gain-table [PATH]` and
  `script/gdp-util --bandpass-table [PATH]`.
- When used without a path, the options read the saved `gain_table` or
  `bandpass_table` from `gdp-setup`.
- Positional input and `--input-table PATH` continue to override the
  mode-specific table selectors.
- Updated utility documentation, README quick-start examples, and the
  step-by-step guide.

## 2026-07-29 11:13:53 IST

Prompt / Request
- Add a `gdp-stats --smode` option with suboptions `gains`,
  `gain-colormap`, `stats`, `ks`, `self-corr`, `all`, and `cross-corr`.
  The `all` mode should run the modes listed before it, and `cross-corr`
  should remain a placeholder for now. In the HTML options table, show these
  modes with a different background color like the `gdp-plot` `pmode` block.

Changes Made
- Added `script/gdp-stats --smode MODE[,MODE...]` with comma-or-space parsing.
- Implemented `--smode all` as `gains`, `gain-colormap`, `stats`, `ks`, and
  `self-corr`.
- Made `cross-corr` a placeholder path that logs the task but does not write a
  cross-corr product.
- Kept backward-compatible individual flags, including `--gains`, `--stats`,
  `--ks`, `--self-corr`, `--gain-colormap`, `--all`, and `--cross-corr`.
- Added a light-green `smode` option block to `doc/gdp-stats.html`.
- Added `--smode` examples to the main README documentation.

## 2026-07-29 11:22:54 IST

Prompt / Request
- Remove older `gdp-stats` task options such as standalone `--stats`, update
  `gdp-plan-run` and help files accordingly, and add setup-file selection for
  stats and plan workflows. In plan-run, allow a setup file to be set at the
  top of the plan.

Changes Made
- Removed public `gdp-stats` task selector flags (`--gains`,
  `--gain-colormap`, `--stats`, `--ks`, `--self-corr`, `--cross-corr`,
  `--all`) so task selection now goes through `--smode`.
- Added `--setup-file` to `gdp-stats`, `gdp-plot`, and `gdp-plan-run`.
- Setup-file names are resolved under the active runtime directory; if omitted,
  commands use the setup file last activated by `gdp-setup`.
- Updated `gdp-plot` missing-product calls to invoke `gdp-stats --smode ...`.
- Added top-level `setup-file: NAME` support to GDP plan files.
- Updated `pipelines/sample_stats.plan`, `gdp-plan-run` documentation,
  `gdp-stats` documentation, product pages, README examples, and the
  step-by-step guide.

## 2026-07-29 11:26:56 IST

Prompt / Request
- Change `gdp-stats --antennas LIST` to support two input styles: inclusive
  range syntax like `(0,9)` or `[0-9]`, and explicit antenna IDs like
  `1,2,3,4,13` or `1 2 3 4 13`.

Changes Made
- Added antenna-list parsing to `gdp-stats` where `(start,end)` or
  `[start,end]` expands inclusively.
- Added space-separated antenna values in addition to comma-separated values.
- Mirrored the same parser in `gdp-plot --antenna` so plotting and missing
  `gdp-stats` product creation use the same antenna selection syntax.
- Updated README, `gdp-stats`, `gdp-plot`, and step-by-step documentation with
  examples.

## 2026-07-29 11:32:45 IST

Prompt / Request
- If a user accidentally runs a mode/table combination with a scan number that
  is not present in the selected table, execution should check this, print a
  text error message, and stop.

Changes Made
- Added an early `gdp-stats` scan validation step after the input table is
  resolved and before product/log batches are started.
- The error message reports the selected mode, table path, missing scan(s), and
  available scan(s).
- Updated `gdp-stats` documentation to mention the validation behavior.

## 2026-07-29 11:39:22 IST

Prompt / Request
- Correct gain colormap plots so the right-side colorbar is separated from the
  plots and does not hide the right-column antenna panels. Add a right-side
  timestamp axis to the right column and include the timestamp width
  (`Delta t`) in the full plot title.

Changes Made
- Updated both `gdp-stats --smode gain-colormap` and
  `gdp-plot -pmode gain-colormap` to use a dedicated colorbar GridSpec column.
- Added right-column timestamp axes for gain-time colormaps, with labels in
  IST.
- Added median positive integration interval as `Delta t = ... s` in the
  figure title when time information is available.
- Updated `gdp-stats` and `gdp-plot` HTML documentation.

## 2026-07-29 11:46:09 IST

Prompt / Request
- For gain colormap plots, remove the duplicated left-side time tick labels
  from the right column, show time row numbers on the right-side axis instead
  of timestamp strings, and make the overall figure 4:3.

Changes Made
- Updated both `gdp-stats --smode gain-colormap` and
  `gdp-plot -pmode gain-colormap` so right-column gain-time panels hide their
  left y-axis tick labels and use a right y-axis labeled `Time row`.
- Time row labels are derived from elapsed seconds divided by the median
  positive integration interval (`Delta t`), so they run from 0 upward.
- Set the gain colormap figure size to a 4:3 aspect ratio while preserving the
  separated colorbar column.
- Updated the `gdp-stats` and `gdp-plot` HTML documentation.

## 2026-07-29 11:52:00 IST

Prompt / Request
- Increase the default PNG plot resolution by a factor of 2.

Changes Made
- Added `DEFAULT_PLOT_DPI = 320` in both `gdp-plot` and `gdp-stats`.
- Replaced all GDP plot `savefig` calls that used `160 dpi` with the shared
  `320 dpi` default.
- Updated the `gdp-plot` and `gdp-stats` HTML option descriptions to mention
  the PNG resolution.

## 2026-07-29 12:01:36 IST

Prompt / Request
- In `gdp-plot -pmode antenna`, set the vertical ranges for all four panels
  from the highest modulus across the four plotted series.

Changes Made
- Updated `plot_single_antenna_gain_products` so each selected antenna figure
  computes one shared absolute y-limit from all finite Real-1 and Imag values
  across the Stokes panels.
- Applied the same symmetric `[-max_abs, +max_abs]` y-range to every panel in
  that antenna figure.
- Updated the `gdp-plot` HTML documentation for the antenna plot mode.

## 2026-07-29 12:03:03 IST

Prompt / Request
- For `gdp-plot -pmode antenna`, replace subplot titles with legends in the
  top-right corners, showing labels such as `ST 0, Re` and `ST 1, Im`.
- Add a time-row axis to the top of the upper row, similar to the gain
  colormap time-row labels.

Changes Made
- Removed per-subplot titles from antenna plots and added per-panel legends
  that identify the Stokes and Real/Imag component.
- Added a top x-axis labeled `Time row` for gain-time antenna plots on the
  upper row panels, with row numbers derived from elapsed time divided by the
  median positive integration interval.
- Updated the `gdp-plot` HTML documentation for antenna plot mode.

## 2026-07-29 12:04:57 IST

Prompt / Request
- Add an overall antenna-plot title like the colormap title, including gain
  table, scan, and `Delta t` information.

Changes Made
- Updated `gdp-plot -pmode antenna` to read the table name from the gains NPZ
  header and include it in the figure title.
- The antenna plot title now includes table name, antenna number, scan label,
  percent units, and gain-mode `Delta t` when time information is available.
- Updated `gdp-plot` HTML documentation for the antenna plot title format.

## 2026-07-29 12:06:22 IST

Prompt / Request
- For antenna plots, remove the left-axis levels from the right column and make
  the overall plot 4:3.

Changes Made
- Updated `gdp-plot -pmode antenna` so right-column panels hide duplicate
  left-side y-axis tick marks and labels.
- Changed antenna plot figure sizing to a 4:3 aspect ratio.
- Updated the `gdp-plot` HTML documentation for antenna plot layout.

## 2026-07-29 12:09:58 IST

Prompt / Request
- In antenna subplot legends, use labels such as `Stokes 0` and `Stokes 1`
  instead of abbreviated labels that include `ST`, `Re`, or `Im`.

Changes Made
- Updated `gdp-plot -pmode antenna` legend labels to show only the Stokes
  number, while the row y-axis labels continue to indicate Real-1 and Imag.
- Updated the `gdp-plot` HTML documentation for the antenna legend labels.

## 2026-07-29 12:13:35 IST

Prompt / Request
- For `gdp-plot -pmode gain-hist`, match the colormap plot style for the four
  panel labels, the right-side colorbar position, and colorbar levels.

Changes Made
- Updated gain histogram panels to use `Stokes <n> Real-1` and
  `Stokes <n> Imag` titles with the same compact summary-statistic line used
  by gain colormap panels.
- Changed gain histogram layout to use the same separated right-side colorbar
  GridSpec column as gain colormap plots.
- Changed gain histogram color scaling to a single shared log10 percentage
  range across all panels, so the right colorbar describes every panel.
- Suppressed duplicate y-axis tick marks and labels on right-column histogram
  panels.
- Saved gain histogram plots without tight cropping to preserve the figure
  aspect and colorbar placement.

## 2026-07-29 12:16:18 IST

Prompt / Request
- Add horizontal grids in the gain histogram plots.

Changes Made
- Added horizontal dotted grid lines to each `gdp-plot -pmode gain-hist`
  panel.
- The grid is drawn above the histogram image so the gain-value levels remain
  visible.
- Updated the `gdp-plot` HTML documentation for gain histogram panels.

## 2026-07-29 12:20:20 IST

Prompt / Request
- Make gain histogram plot margins smaller, place the colorbar closer, show
  colorbar levels in percentage even though the plotted values remain log10,
  and keep the figure aspect ratio at 4:3.

Changes Made
- Tightened `gdp-plot -pmode gain-hist` GridSpec spacing and figure margins
  while preserving the 4:3 canvas.
- Moved the separated right colorbar closer to the histogram panels.
- Kept the histogram color scale in log10 percent, but changed colorbar tick
  labels to display percentage values.
- Updated the `gdp-plot` HTML documentation for the colorbar labels.

## 2026-07-29 12:24:26 IST

Prompt / Request
- For gain colormap plots, keep percentage colorbar levels to one decimal
  place and show them on the left side of the colorbar.

Changes Made
- Updated both `gdp-plot -pmode gain-colormap` and
  `gdp-stats --smode gain-colormap` colorbars so percent tick labels are
  formatted with one decimal place.
- Moved gain colormap colorbar ticks and label to the left side.
- Updated the `gdp-plot` and `gdp-stats` HTML documentation.

## 2026-07-29 12:30:03 IST

Prompt / Request
- For the histogram percentage colorbar levels, use consistent two-decimal
  labels such as `0.25`, `0.50`, `1.00`, `2.00`, `4.00`, `8.00`, and `16.00`,
  without appending a `%` sign to each value.

Changes Made
- Updated `gdp-plot -pmode gain-hist` so the colorbar still uses log10
  percent internally but displays fixed percentage levels at the requested
  powers-of-two sequence.
- The histogram color scale is expanded when needed so the standard
  `0.25` through `16.00` tick sequence is visible consistently.
- Colorbar labels are formatted with two decimal places and do not include a
  trailing percent sign.
- Updated the `gdp-plot` HTML documentation for gain histogram colorbar levels.

## 2026-07-29 12:34:04 IST

Prompt / Request
- Make sure colorbar levels start from `0.25` and then increase by factors of
  two to the highest value available in the corresponding antenna/scan
  combination.

Changes Made
- Added a reusable factor-of-two colorbar level helper.
- Updated `gdp-plot -pmode gain-hist` so percent colorbar ticks are generated
  dynamically from `0.25` up to the highest factor-of-two level present in the
  plotted scan/antenna selection, with two-decimal labels and no `%` suffix.
- Applied the same positive log-colorbar level rule to
  `gdp-plot -pmode self-corr-colormap`.
- Updated the `gdp-plot` HTML documentation for dynamic histogram colorbar
  levels.

## 2026-07-29 12:51:57 IST

Prompt / Request
- In `gdp-plot -pmode stats`, use the colormap-style title with the table name
  and scan information.
- Remove the `--subtract-mean` / `--no-subtract-mean` options from `gdp-stats`.
- Keep mean subtraction as a plot-only option in `gdp-plot`, disabled by
  default, and include `subtract-mean` in the output filename when it is used.

Changes Made
- Routed `gdp-plot -pmode stats` through the full gains NPZ product so plot-time
  statistics can be calculated directly from antenna samples.
- Added `gdp-plot --subtract-mean` for stats plots. When enabled, each selected
  antenna/stokes/component sample distribution is centered before the plotted
  statistics are calculated.
- Updated stats plot filenames to use
  `gdp-plot-stats-<mode>-<scan>-subtract-mean.<format>` when centering is
  enabled.
- Removed the public subtract-mean CLI from `gdp-stats`; stats products are now
  written without mean subtraction by default.
- Updated `gdp-plot`, `gdp-stats`, README, and step-by-step HTML documentation.

## 2026-07-29 13:03:05 IST

Prompt / Request
- Replace the `gdp-plot --subtract-mean` stats-plot option with
  `--divide-mean`.
- For `--divide-mean`, calculate the mean over all selected antennas for each
  stokes/real-imag combination, then divide every antenna sample in that
  combination by the shared mean.

Changes Made
- Renamed the plot-side stats option to `gdp-plot --divide-mean`.
- Changed `gdp-plot -pmode stats --divide-mean` to normalize gain samples by a
  shared all-antenna mean for each stokes/component before calculating mean,
  std, skewness, and kurtosis for the plotted grid.
- Updated stats plot filenames to use
  `gdp-plot-stats-<mode>-<scan>-divide-mean.<format>` when normalization is
  enabled.
- Updated the `gdp-plot` HTML usage and option documentation.

## 2026-07-29 13:08:05 IST

Prompt / Request
- Replace the `gdp-plot --divide-mean` option with `--adjust-mean`.
- For the adjustment, divide only the real samples by the shared all-antenna
  mean, while subtracting the shared all-antenna mean from the imaginary
  samples.

Changes Made
- Renamed the plot-side stats option to `gdp-plot --adjust-mean`.
- Updated `gdp-plot -pmode stats --adjust-mean` so real values are divided by
  the all-selected-antenna mean for each stokes/real combination, while
  imaginary values subtract the all-selected-antenna mean for each stokes/imag
  combination.
- Updated stats plot filenames to use
  `gdp-plot-stats-<mode>-<scan>-adjust-mean.<format>` when this adjustment is
  enabled.
- Updated the `gdp-plot` HTML usage and option documentation.

## 2026-07-29 13:10:36 IST

Prompt / Request
- In the stats plot mean panel, plot the real gain quantity with the `-1`
  convention but do not apply `-1` to the imaginary quantity.
- Change the top-left stats subplot title to `Mean [%]`.
- Mark real legend entries with `-1`.

Changes Made
- Updated `gdp-plot -pmode stats` to calculate stats-plot values from raw gain
  samples, then apply the display convention: real mean is shown as
  `(real - 1) * 100`, while imaginary mean is shown as `imag * 100`.
- Preserved the `--adjust-mean` behavior before display scaling: real samples
  are divided by the shared real mean, and imaginary samples subtract the shared
  imaginary mean.
- Changed the mean subplot title to `Mean [%]`.
- Changed stats plot real legend labels from `re` to `re-1`.
- Updated the `gdp-plot` HTML documentation.

## 2026-07-29 13:15:08 IST

Prompt / Request
- In the stats plots, add a black horizontal dashed line with linewidth 2 in
  the mean, skewness, and kurtosis panels.

Changes Made
- Added a black dashed zero-reference line with linewidth 2 to the mean,
  skewness, and kurtosis panels in `gdp-plot -pmode stats`.
- Included zero in the y-axis range calculation for those panels so the
  reference line remains visible.
- Updated the `gdp-plot` HTML documentation.

## 2026-07-29 13:21:25 IST

Prompt / Request
- In the KS plot, add a title in the same style as the recently updated
  colormap and stats plots.

Changes Made
- Updated `gdp-plot -pmode ks` to use a figure title of the form
  `Gain Table: <table> | Scan: <scan> [%]`, reading the table name from the KS
  product header when available.
- Adjusted the KS plot layout so the new figure title has reserved space.
- Updated the `gdp-plot` HTML documentation.

## 2026-07-29 13:22:42 IST

Prompt / Request
- Make the KS and stats plots use a 4:3 aspect ratio.

Changes Made
- Updated `gdp-plot -pmode stats` to use a `10 x 7.5` inch figure.
- Updated `gdp-plot -pmode ks` to use a `10 x 7.5` inch figure.
- Updated the `gdp-plot` HTML documentation.

## 2026-07-29 13:25:49 IST

Prompt / Request
- In the KS plot, add dashed lines for each Stokes/real-imag option comparing
  two simulated Gaussian samples with the same sample size as each antenna.

Changes Made
- Added an internal two-sample KS helper for simulated Gaussian comparisons.
- Updated `gdp-plot -pmode ks` to read `sample_count` from the KS NPZ product
  and overlay same-color dashed reference lines for each Stokes/component
  series.
- For gains-product fallback plotting, the simulated reference uses the finite
  sample count read directly from the selected gain samples.
- Updated the `gdp-plot` HTML documentation.

## 2026-07-29 13:28:53 IST

Prompt / Request
- For the KS plot, replace the per-antenna simulated Gaussian KS references
  with a horizontal representative line for each Stokes/real-imag combination.

Changes Made
- Changed `gdp-plot -pmode ks` so measured KS values remain plotted per
  antenna, while the simulated Gaussian comparison is drawn as one same-color
  horizontal dashed line per Stokes/component series.
- The horizontal reference uses the median representative sample count across
  the selected antennas for that series.
- Set the simulated reference line width to 1.
- Updated the `gdp-plot` HTML documentation.

## 2026-07-29 13:31:15 IST

Prompt / Request
- Adjust the KS plot range so the highest measured KS value and the highest
  horizontal simulated reference line are both included.

Changes Made
- Updated `gdp-plot -pmode ks` to collect measured KS values and simulated
  horizontal reference levels while plotting.
- Set the KS y-axis range from zero to a padded maximum over both measured and
  simulated values.
- Updated the `gdp-plot` HTML documentation.

## 2026-07-29 13:32:51 IST

Prompt / Request
- Calculate each KS simulated horizontal reference line from 128 realizations
  of Gaussian sample pairs, then use the mean over those realizations.

Changes Made
- Updated the simulated Gaussian KS helper used by `gdp-plot -pmode ks` to run
  128 two-sample Gaussian-pair realizations by default.
- The horizontal simulated reference value is now the mean KS statistic over
  those 128 realizations for the representative sample size.
- Updated the `gdp-plot` HTML documentation.

## 2026-07-29 13:35:04 IST

Prompt / Request
- The `0-im sim` horizontal reference line in the KS plot is not visible.

Changes Made
- Confirmed that the active KS product has valid `0-im` sample counts, and that
  the simulated reference levels are very close to the other Stokes/component
  references.
- Changed `gdp-plot -pmode ks` simulated references from plain axis-wide
  horizontal lines to explicit horizontal line segments with higher z-order.
- Added distinct dash patterns and right-edge text labels for each simulated
  reference line so close levels such as `0-im sim` remain identifiable.
- Updated the `gdp-plot` HTML documentation.

## 2026-07-29 13:38:21 IST

Prompt / Request
- Remove inline KS simulated-reference labels such as `0-im sim`.
- Put the KS legend at the bottom in a four-column by two-row layout, with the
  dashed simulated entries in the bottom row.

Changes Made
- Removed right-edge inline text labels from `gdp-plot -pmode ks`.
- Moved the KS legend below the plot with four columns. The legend entries are
  ordered as measured/simulated pairs so measured solid lines appear in the top
  row and dashed simulated references appear in the bottom row.
- Reserved bottom layout space for the legend.
- Updated the `gdp-plot` HTML documentation.

## 2026-07-29 13:40:41 IST

Prompt / Request
- Keep the KS legend labels inside the plot rather than outside, and make the
  plot fill the figure edges properly while keeping a 4:3 aspect ratio.

Changes Made
- Moved the `gdp-plot -pmode ks` legend inside the lower center of the plotting
  axes, preserving the four-column by two-row legend layout.
- Replaced the extra bottom legend band with tighter manual subplot margins so
  the plot fills the 4:3 figure more effectively.
- Updated the `gdp-plot` HTML documentation.

## 2026-07-29 13:51:49 IST

Prompt / Request
- Change `gdp-stats` flag handling from the paired
  `--use-flags` / `--no-use-flags` options to a single opt-in
  `--use-flags` option.
- When `--use-flags` is set, check and use the table `FLAG` column. If the
  table has no `FLAG` column, print a warning and stop. If the option is not
  set, do not use flags.

Changes Made
- Changed `gdp-stats --use-flags` to a simple `store_true` option with default
  disabled.
- Added a shared flag-column check. `gdp-stats` now stops with a warning if
  `--use-flags` is requested for a table without `FLAG`.
- Updated gains, stats, KS, and structure-function series reading so `FLAG` is
  read only when `--use-flags` is enabled.
- Updated `gdp-plot` missing-product forwarding to use `--use-flags` instead
  of the removed `--no-use-flags`.
- Updated the `gdp-stats` and `gdp-plot` HTML documentation.

## 2026-07-31 14:25:41 IST

Prompt / Request
- Begin bandpass-mode work.
- When both `--bchan` and `--echan` are provided for `gdp-stats` or
  `gdp-plot`, include that channel range in output product names for NPZ, CSV,
  and plot files, using a channel tag such as `chan_0_128`.

Changes Made
- Added channel-tag helpers in `gdp-stats` and `gdp-plot`.
- Updated default `gdp-stats` output names so bandpass products with both
  `--bchan` and `--echan` append `-chan_<bchan>_<echan>` after the scan label.
  This applies to gains NPZ, stats NPZ/CSV, KS NPZ, self-corr NPZ, and direct
  gain-colormap plot output.
- Updated `gdp-plot` product lookup and output plot naming so bandpass plotting
  with both channel bounds uses the same channel-tagged NPZ and plot names.
- Updated `gdp-stats`, `gdp-plot`, and the gains/stats/KS/self-corr product
  format HTML documentation.

## 2026-07-31 14:38:20 IST

Prompt / Request
- Add a `gdp-stats --antenna-flag` option that accepts a list of antennas to
  consider flagged.

Changes Made
- Added `--antenna-flag LIST` to `gdp-stats`, using the same explicit-list and
  inclusive-range syntax as `--antennas`.
- Applied forced antenna flags in gains, stats, KS, self-correlation, and the
  internal series reader. Forced antennas remain present in output axes, but
  their samples are treated as flagged or non-finite.
- Recorded forced antenna flags in product `header_json` metadata as
  `antenna_flags`.
- Updated `gdp-stats` and the affected product-format HTML documentation.

## 2026-07-31 14:46:16 IST

Prompt / Request
- Add a `-pchans "[pbchan-pechan]"` option in `gdp-stats` and `gdp-plot`.
- When provided, plots should be limited to those channels and subplot-title
  statistics should be calculated from only those channels.

Changes Made
- Added `-pchans` / `--pchans` parsing as a plot-channel window with start
  channel inclusive and end channel exclusive.
- Updated `gdp-stats --smode gain-colormap` so `-pchans` limits the displayed
  channels and the mean/std/skew/kurtosis shown in each subplot title without
  changing the gains NPZ product.
- Updated `gdp-plot` gains-based plot modes (`gain-colormap`, `gain-hist`,
  `antenna`, and `stats`) so `-pchans` filters the channels used for plotting
  and for plot-time statistics.
- Added `pchan_<start>_<end>` to default plot filenames when `-pchans` is used.
- Updated the main README, step-by-step guide, and the `gdp-stats` /
  `gdp-plot` HTML documentation.

## 2026-07-31 15:07:00 IST

Prompt / Request
- Handle tables where the FLAG array has fewer channels than the data array.
- Provide an option so channels outside the known FLAG coverage are treated as
  flagged and processing can continue.
- Stop with a clear text error if channel options are used in gain mode.

Changes Made
- Added `gdp-stats --flag-chans [START-END]` for shorter FLAG channel axes.
  The option declares which original data channels the shorter FLAG array
  covers; all channels outside that coverage are treated as flagged.
- Expanded FLAG normalization so stats, gains, KS, and self-correlation can
  process shorter FLAG arrays against larger data-channel axes.
- Recorded `flag_chans` in NPZ product headers.
- Added `gdp-plot --flag-chans` as a pass-through when missing NPZ products are
  created by `gdp-plot`.
- Added gain-mode validation so `--bchan`, `--echan`, `-pchans`, and
  `--flag-chans` stop with a clear message when used with `--mode gain`.
- Updated README, step-by-step, `gdp-stats`, `gdp-plot`, and product-format
  HTML documentation.

## 2026-07-31 15:07:28 IST

Prompt / Request
- Standardize gain and bandpass colormap plot appearance.
- For bandpass colormaps, add channel width as `Delta nu` in MHz to the title,
  show `Delta nu` in MHz on left-column left axes, show channel numbers on the
  right axes of right-column panels, remove duplicate left-axis labels from
  right-column panels, keep a symmetric percentage colorbar, and preserve a 4:3
  overall aspect ratio.

Changes Made
- Added `SPECTRAL_WINDOW` channel frequency and channel width extraction to
  gains NPZ products as `channel_freq_hz` and `channel_width_hz`.
- Updated direct `gdp-stats --smode gain-colormap` plotting and
  `gdp-plot -pmode gain-colormap` plotting to use frequency-offset MHz axes
  for bandpass colormaps when channel metadata is available.
- Added right-side channel-number axes to the right-column bandpass colormap
  panels and removed duplicate left-axis labels there.
- Changed gain/bandpass colormap color scaling to use the maximum absolute
  percentage value, with symmetric limits from `-xx` to `+xx` and two-decimal
  colorbar labels.
- Updated README, step-by-step, `gdp-stats`, `gdp-plot`, and gains product
  format HTML documentation.

## 2026-07-31 15:11:12 IST

Prompt / Request
- Make antenna range examples match the bracket style used by `-pchans`, while
  keeping explicit antenna lists such as `--antennas 2,3,4,31`.

Changes Made
- Updated `gdp-stats` and `gdp-plot` CLI help/error text to use bracketed
  antenna range examples such as `--antennas [0-9]` and `--antenna [0-9]`.
- Kept explicit antenna-list parsing for comma-separated and space-separated
  values, including `--antennas 2,3,4,31`.
- Updated README, step-by-step, `gdp-stats`, and `gdp-plot` HTML examples.

## 2026-07-31 15:15:14 IST

Prompt / Request
- For gain/bandpass colormap plots, show `nu` in MHz on the left axes of
  left-column bandpass panels.
- Add a `--range` option to set the colormap percentage saturation range.
- Use seven colorbar labels at multiples of 5, including `0`, with no decimal
  places.

Changes Made
- Added `--range` to `gdp-stats --smode gain-colormap` and
  `gdp-plot -pmode gain-colormap`. The value is used as the requested
  saturation half-range in percent and is rounded upward to a multiple of 5.
- Updated bandpass colormap axes to show absolute `nu` in MHz on the left
  column while keeping channel numbers on the right axes of right-column
  panels.
- Updated colormap colorbar ticks to seven integer labels at multiples of 5,
  centered on zero.
- Updated README, step-by-step, `gdp-stats`, and `gdp-plot` HTML
  documentation.

## 2026-07-31 15:17:53 IST

Prompt / Request
- Ensure `--range` is available for gain-mode colormap plots as well.

Changes Made
- Confirmed the shared colormap implementation applies `--range` to both gain
  and bandpass modes.
- Updated CLI help and HTML usage examples to make gain-mode `--range` support
  explicit for both `gdp-stats` and `gdp-plot`.

## 2026-07-31 15:20:03 IST

Prompt / Request
- Format bandpass colormap `nu` axis labels with no decimal places.
- Show `Delta nu` in the title in kHz with two decimal places.
- Keep channel indices ordered from the bottom upward, even when frequency
  decreases upward.

Changes Made
- Updated direct `gdp-stats --smode gain-colormap` and
  `gdp-plot -pmode gain-colormap` bandpass plotting to keep the saved channel
  order instead of sorting by frequency.
- Changed bandpass left-axis `nu` labels to whole-MHz labels.
- Changed bandpass colormap title text to report `Delta nu` in kHz with two
  decimal places.

## 2026-07-31 15:24:24 IST

Prompt / Request
- Keep the extreme end labels on the left-column and right-column bandpass
  colormap y axes, rounded to the nearest integer.

Changes Made
- Updated gain/bandpass colormap tick selection in both `gdp-stats` and
  `gdp-plot` so the first and last y-axis rows are always labeled.
- This keeps the bandpass left-axis whole-MHz end labels and the right-axis
  integer channel end labels visible.

## 2026-07-31 15:36:47 IST

Prompt / Request
- Increase the spacing between the two colormap subplot columns by a factor of
  two for both gain and bandpass colormap plots.

Changes Made
- Updated the shared gain/bandpass colormap GridSpec layout in both
  `gdp-stats` and `gdp-plot`, increasing `wspace` from `0.05` to `0.10`.

## 2026-07-31 15:47:46 IST

Prompt / Request
- Add a `--npz-path` option to `gdp-plot` so a specific NPZ product can be
  selected directly.

Changes Made
- Added `gdp-plot --npz-path PATH`.
- When supplied, `gdp-plot` uses the given NPZ file for the selected `-pmode`
  and skips default product discovery or missing-product creation through
  `gdp-stats`.
- Output labels are inferred from standard GDP NPZ filenames where possible,
  otherwise the NPZ filename stem is used.
- Updated README and `gdp-plot` HTML usage/options documentation.

## 2026-07-31 15:50:21 IST

Prompt / Request
- For both gain and bandpass colormap plots, show subplot mean/std/skew/kurtosis
  values to one decimal place.

Changes Made
- Updated the colormap subplot summary formatter in both
  `gdp-stats --smode gain-colormap` and `gdp-plot -pmode gain-colormap`.
- Updated `gdp-stats` and `gdp-plot` HTML documentation.

## 2026-07-31 15:54:23 IST

Prompt / Request
- Bring the gain-hist left-column y-axis percentage levels closer to the plot
  axes.

Changes Made
- Reduced the left-column y tick padding and `Gain value [%]` label padding in
  `gdp-plot -pmode gain-hist`.

## 2026-07-31 15:57:01 IST

Prompt / Request
- Show all gain-hist subplot summary statistics, including mean/std/skew/kurt,
  to one decimal place.

Changes Made
- Updated the `gdp-plot -pmode gain-hist` summary-statistic formatter to use
  one decimal place.
- Updated the `gdp-plot` HTML documentation.

## 2026-07-31 16:02:28 IST

Prompt / Request
- For `gdp-plot --mode bandpass -pmode antenna`, add `Delta nu` in kHz to the
  title and adjust the title font to fit.
- Add top channel-number axes to the upper-row panels, with the leftmost tick as
  the lowest channel number.
- Label the bottom axes of the lower-row panels as `nu` in MHz, with integer
  frequency labels and endpoint ticks included.

Changes Made
- Updated bandpass antenna plots to read `channel_freq_hz` and
  `channel_width_hz` from the gains NPZ when available.
- Added top channel axes for bandpass antenna upper panels and integer-MHz
  frequency labels on lower-panel bottom axes.
- Added bandpass `Delta nu` title text in kHz with two decimal places and
  adaptive title font sizing.
- Updated `gdp-plot` HTML documentation.

## 2026-07-31 16:04:35 IST

Prompt / Request
- Make the `gdp-plot -pmode antenna` title use two rows and a smaller font.

Changes Made
- Split the antenna plot figure title into a table/antenna row and a scan/detail
  row.
- Reduced the adaptive title font range and left more top margin for the
  two-line title.
- Updated the `gdp-plot` HTML documentation.

## 2026-07-31 16:06:52 IST

Prompt / Request
- Remove `[%]` from all plot titles.
- For bandpass `gdp-plot -pmode antenna`, reduce the large gap between the
  two-line title and the subplots.

Changes Made
- Removed title-level `[%]` text from gain/bandpass colormap, gain histogram,
  antenna, stats, and KS figure titles in `gdp-plot`.
- Removed title-level `[%]` text from direct `gdp-stats --smode gain-colormap`
  figure titles.
- Kept percent units on axes, colorbars, and subplot labels where they describe
  the plotted data.
- Tightened the top layout rectangle for bandpass antenna plots so subplots sit
  closer to the two-line title.
- Updated `gdp-plot` HTML documentation.

## 2026-07-31 16:09:33 IST

Prompt / Request
- Further reduce the gap between the bandpass antenna plot title and the
  subplots.

Changes Made
- Lowered the bandpass antenna plot suptitle position and increased the
  `tight_layout` top rectangle so the panels sit closer to the two-line title.

## 2026-07-31 16:15:09 IST

Prompt / Request
- Check that README and related documentation are updated before pushing a new
  version.

Changes Made
- Audited the HTML documentation for recent `gdp-stats` and `gdp-plot` changes,
  including `--range`, `--npz-path`, bandpass `Delta nu`, antenna plot axes,
  one-decimal summary statistics, and title-unit cleanup.
- Updated `doc/README.md` so it matches the current command examples and
  version target.
- Added a `.gitignore` rule for `casa-*.log` so generated CASA logs remain out
  of release commits when the git-push utility stages GDP directories.

## 2026-07-31 17:25:30 IST

Prompt / Request
- Add `all` as a `-pmode` value in `gdp-plot`.
- `-pmode all` should run only `gain-colormap`, `gain-hist`, `stats`, and `ks`.

Changes Made
- Added `all` to `gdp-plot -pmode`.
- `-pmode all` expands to `gain_colormap`, `gain_hist`, `stats`, and `ks` only.
- Kept antenna, self-correlation, and cross-correlation plot modes out of the
  `all` expansion.
- Updated README and `gdp-plot` documentation.

## 2026-08-05 11:02:09 IST

Prompt / Request
- Add `reim` as a `gdp-plot -pmode` option.
- Rename public plot/stat mode names from `gain-colormap` to `colormap` and
  from `gain-hist` to `hist` for both `gdp-plot` and `gdp-stats`.

Changes Made
- Added `gdp-plot -pmode reim`, backed by the gains NPZ product.
- `reim` writes one plot per selected antenna. Columns are Stokes values; the
  top row plots individual Real-1 versus Imag points, and the bottom row shows
  2D density as both colormap and contour.
- Added dashed vertical and horizontal reference lines at the Real-1 and Imag
  mean values.
- Added Real-1 and Imag mean/std/skew/kurtosis summaries to the Stokes titles
  with one decimal place.
- Added public `-pmode colormap` and `-pmode hist` names, while keeping legacy
  `gain-colormap` and `gain-hist` aliases.
- Added public `--smode colormap` and `--output-colormap` names, while keeping
  legacy `gain-colormap` and `--output-gain-colormap` aliases.
- Changed new default plot filenames to use `gdp-plot-colormap-...` and
  `gdp-plot-hist-...`.
- Updated sample plan, README, HTML documentation, and added a representative
  `reim` sample plot under `doc/sample_plots`.

## 2026-08-05 11:28:12 IST

Prompt / Request
- Change `gdp-plot -pmode reim` so selected antenna data are plotted together
  in one pooled Real-1 versus Imag product, instead of one plot per antenna.

Changes Made
- Updated `reim` plotting to combine all finite unflagged samples from all
  selected antennas for each Stokes panel.
- If no antenna selection is supplied, `reim` now pools all antennas available
  in the gains NPZ.
- The pooled output filename now appends `-allants` or `-ants<list>` to make
  the antenna selection explicit.
- Updated the HTML/Markdown documentation and refreshed the representative
  `reim` sample plot.

## 2026-08-05 11:42:03 IST

Prompt / Request
- Make the `reim` density/histogram panels use log counts while keeping the
  axes as Real-1 and Imag.

Changes Made
- Updated the bottom-row `gdp-plot -pmode reim` panels to display
  `log10(counts)` for the 2D histogram density image.
- Changed the contour levels in those panels to use the same log-count scale.
- Kept the horizontal axis as Real-1 percent and the vertical axis as Imag
  percent.
- Updated documentation wording and refreshed the representative sample plot.

## 2026-08-05 11:53:41 IST

Prompt / Request
- Add a red dashed ellipse to all four `reim` panels showing the Gaussian
  mean/std limit where only one point is expected outside for the plotted
  sample size.

Changes Made
- Added a linewidth-2 dashed red ellipse to each scatter and log-count density
  panel in `gdp-plot -pmode reim`.
- The ellipse is centered on the pooled Real-1 and Imag means, with semi-axes
  `sqrt(2 ln N)` times the corresponding standard deviations. This is the
  2D Gaussian radius where the expected number of exterior points is one for
  the plotted sample count `N`.
- Expanded plot limits when needed so the ellipse remains visible.
- Updated documentation wording and refreshed the representative sample plot.

## 2026-08-05 12:06:18 IST

Prompt / Request
- Make the `reim` density colorbar show point counts in factor-of-two steps.
  This intermediate request was later revised to seven log-spaced levels
  starting at 5 counts.

Changes Made
- Added a seven-level factor-of-two count scale for `gdp-plot -pmode reim`
  density colorbars.
- The density image remains log10-scaled internally, but colorbar ticks are
  labeled as point counts such as `50`, `100`, `200`, and `400`.
- The displayed log-color range is expanded to the selected seven count levels
  so the colorbar consistently shows the full tick sequence.
- Updated documentation wording and refreshed the representative sample plot.

## 2026-08-05 12:14:36 IST

Prompt / Request
- Increase the dynamic range of the `reim` density colormap.

Changes Made
- Temporarily widened the `gdp-plot -pmode reim` density color scale to improve
  sparse-bin contrast. This was later revised so the color scale starts at the
  lowest displayed colorbar count (5).
- Kept the seven visible colorbar labels clean while testing the wider density
  display range.

## 2026-08-05 12:26:44 IST

Prompt / Request
- For `reim`, start the color scale at the lowest colorbar label and use seven
  evenly distributed count labels. This intermediate request was later revised
  to seven log-spaced levels starting at 5 counts.
- Increase the vertical size of the individual subplots while keeping the full
  figure aspect ratio at 4:3, so the whitespace below the main title is
  reduced.

Changes Made
- Replaced the factor-of-two `reim` count colorbar labels with seven evenly
  spaced labels. This was later revised to log-spaced labels starting at 5
  counts.
- The colorbar range now starts at the first displayed count label and extends
  to an adjusted upper label that covers the maximum density-bin count.
- Tightened the `reim` figure layout under the main title and slightly reduced
  the per-column width so the 4:3 figure gives more vertical room to the
  individual subplots.

## 2026-08-05 12:34:58 IST

Prompt / Request
- Revise the `reim` density colorbar to start at 5 counts and use seven levels
  evenly spaced in log scale.

Changes Made
- Replaced the linear count colorbar helper with a log-spaced count helper for
  `gdp-plot -pmode reim`.
- The density colorbar now starts at 5 counts and uses seven geometrically
  spaced count labels up to a rounded upper count that covers the maximum
  density-bin count.
- Updated documentation wording to remove the older multiples-of-50
  description.

## 2026-08-05 12:46:31 IST

Prompt / Request
- Preserve antenna range notation in `reim` output filenames. For example,
  `--antenna "[1-4]"` should use `1-4` in the filename, while explicit antenna
  lists should name only the selected antennas.

Changes Made
- Added range-form detection for `gdp-plot -pmode reim` antenna naming.
- Range inputs such as `[1-4]` now produce pooled output suffixes
  such as `-ants1-4`.
- Explicit selections such as `--antenna 1,2,4` continue to produce suffixes
  such as `-ants1_2_4`.
- Updated the `gdp-plot` documentation for the naming convention.

## 2026-08-05 13:01:22 IST

Prompt / Request
- Allow antenna selections to mix inclusive ranges and individual antenna
  numbers, for example `"[1-5]" 6 "[9-12]" 15 16 19`.

Changes Made
- Updated `gdp-plot --antenna`, `gdp-stats --antennas`, and
  `gdp-stats --antenna-flag` parsing to accept mixed range/list tokens.
- Supported range token forms include `[1-5]`, `[9-12]`, and `9-12`.
- Pooled `gdp-plot -pmode reim` filenames preserve mixed selections with
  suffixes such as `-ants1-5_6_9-12_15_16_19`.
- Updated CLI help and documentation examples.

## 2026-08-05 13:09:43 IST

Prompt / Request
- Put the antenna selection line on the second line of the `reim` plot title.

Changes Made
- Updated the pooled `gdp-plot -pmode reim` figure title to show the gain table
  and scan on the first line, and the antenna selection on the second line.
- Updated the `gdp-plot` documentation.

## 2026-08-05 13:18:47 IST

Prompt / Request
- For `reim` plots, keep both horizontal and vertical axes fixed from `-100`
  to `+100`, and show how many points are outside that box inside the subplot.

Changes Made
- Added a fixed `-100` to `+100` percent display box for both Real-1 and Imag
  axes in all `gdp-plot -pmode reim` panels.
- Added an in-panel outside-count annotation to both scatter and density panels
  for each Stokes column.
- The density histogram is computed from points inside the displayed box, while
  outside counts are computed from all finite pooled points.
- Updated the `gdp-plot` documentation.

## 2026-08-05 13:27:58 IST

Prompt / Request
- In the `reim` plot title, show mixed antenna selections in the same grouped
  style as the input, for example `Antennas: [0-13] 15 [19-22] 26 27`.

Changes Made
- Added a display formatter for pooled `reim` antenna titles.
- Range tokens are shown as bracketed ranges, and individual antennas are shown
  as space-separated values on the second title line.
- Filename suffix formatting is unchanged.
- Updated the `gdp-plot` documentation.

## 2026-08-05 13:39:26 IST

Prompt / Request
- Replace the fixed `-100` to `+100` `reim` plot limits with a shared x/y
  range derived from the red dashed Gaussian ellipse radius, and count points
  outside the red ellipse.

Changes Made
- `gdp-plot -pmode reim` now uses the same symmetric x and y limits for all
  four panels.
- The shared limit is derived from twice the largest red-ellipse radius across
  the Stokes panels, with safeguards to keep each ellipse visible.
- The in-panel annotation now reports `Outside ellipse: n/N` for each Stokes
  panel, using that panel's red Gaussian ellipse.
- Density histograms are computed from points inside the shared displayed
  range; the outside count is computed from all finite pooled points.
- Updated the `gdp-plot` documentation.

## 2026-08-05 13:48:02 IST

Prompt / Request
- For `reim`, choose the shared plot box size as the lower of `100` or
  `1.5` times the red ellipse radius.

Changes Made
- Updated the shared `gdp-plot -pmode reim` x/y half-range to
  `min(100, 1.5 * max_red_ellipse_radius)`.
- Removed the previous `2 * radius` range rule.
- Kept outside counts defined relative to each panel's red ellipse.
- Updated the `gdp-plot` documentation.

## 2026-08-05 13:50:00 IST

Prompt / Request
- Allow the `reim` density colorbars to start at 1 count as the minimum.

Changes Made
- Changed the `gdp-plot -pmode reim` log-count colorbar helper so the default
  first count level is 1 instead of 5.
- Updated the `gdp-plot` documentation and sample-plot description to match
  the new count scale.

## 2026-08-05 13:55:00 IST

Prompt / Request
- Do not keep fractional values in the `reim` density colorbar levels.

Changes Made
- Rounded the `gdp-plot -pmode reim` log-spaced count colorbar levels to whole
  counts and removed fractional tick labels.
- Kept the minimum count label at 1.
- Updated the HTML documentation sample text to describe whole-count labels.

## 2026-08-05 14:00:00 IST

Prompt / Request
- Update all sample plots.

Changes Made
- Regenerated the documentation sample plot set with the current `gdp-plot`
  implementation and existing GDP NPZ products.
- Used scan 4 for gains-based samples because the available scan 2 gains NPZ
  only contains antenna 0, while scan 4 contains the full antenna set.
- Replaced the old `sample-*` image links in the HTML documentation with the
  current default `gdp-plot-*` output names.
- Removed obsolete stale sample PNGs from `doc/sample_plots`.

## 2026-08-05 14:25:00 IST

Prompt / Request
- For sample plots, use gain scan 17 with antennas 0 through 29 and bandpass
  scan 18.

Changes Made
- Regenerated the gain sample plot set from scan 17 using antennas 0-29.
- Created missing gain scan-17 KS and self-correlation NPZ products with a
  CASA-enabled Python environment before plotting those samples.
- Regenerated the bandpass sample plot set from scan 18 using channels
  800-2999 and antennas 0-29.
- Updated the repeated HTML sample tables to include gain scan-17 and bandpass
  scan-18 rows, with antenna 0 linked as the representative per-antenna sample.
- Removed leftover scan-2 and scan-4 sample PNGs from `doc/sample_plots`.

## 2026-08-05 17:10:00 IST

Prompt / Request
- Add versioned `.flg` flag sidecar files matching GDP gains NPZ names, and
  use selected/latest flag versions for flagged stats and plots.

Changes Made
- Added `--flagver` to `gdp-stats` and `gdp-plot`.
- `gdp-stats --smode gains` now writes a matching
  `NAME_fV<version>.flg` sidecar containing sample-level flag arrays from the
  CASA gain or bandpass table.
- If no `--flagver` is supplied while writing gains, GDP writes the next flag
  version number; if `--flagver` is supplied, it writes that exact version.
- For `colormap`, `stats`, `ks`, and `self-corr` with `--use-flags`, GDP now
  loads flags from the matching `.flg` file. If `--flagver` is omitted, the
  highest available flag version is selected and logged.
- `gdp-plot --use-flags` applies the selected `.flg` file to gains-based plots
  and passes `--flagver` through when it creates missing products.
- Added `doc/gdp-product-flags.html` and linked the new flag product format in
  the documentation tree.

## 2026-08-05 17:20:00 IST

Prompt / Request
- If a requested flag version does not exist, mention it in the terminal and
  quit.

Changes Made
- Changed missing requested `--flagver` handling in both `gdp-stats` and
  `gdp-plot` to stop with a concise `ERROR:` terminal message instead of a
  Python traceback.
- Preserved the `--smode all --use-flags` bootstrap behavior where the gains
  step can create the first `.flg` file when no version exists yet and no
  explicit `--flagver` was requested.
- Updated the flag-related HTML documentation.

## 2026-08-05 17:45:00 IST

Prompt / Request
- Move manual flag writing into a dedicated `gdp-flag` command.
- Add a `flag-intent` header to every `.flg` file, with CASA table flags
  recorded as `CASA FLAGS`.
- Keep placeholder flagging modes for later threshold and automatic flagging
  development.

Changes Made
- Added `script/gdp-flag` for creating versioned GDP `.flg` sidecars from the
  setup-selected gain or bandpass table, or from an explicitly supplied table.
- `gdp-flag` supports `--mode`, `--setup-file`, `--scan`,
  `--combine-scans`, `--antennas`, `--bchan`, `--echan`, `--use-flags
  [VERSION]`, `--new-flags`, `--out-fver`, and `--fmode`.
- Implemented `--fmode casa-flags`, `--fmode man-antenna`, and
  `--fmode man-chan`; kept `auto-ante` and `auto-chan` as logged
  placeholders.
- Removed the user-facing `gdp-stats --antenna-flag` and `--flag-chans`
  options so manual flag creation is centralized in `gdp-flag`.
- Updated the HTML and Markdown documentation, added `doc/gdp-flag.html`, and
  added a commented `gdp-flag` intent to the sample pipeline plan.

Follow-up Fix
- Fixed `gdp-flag --fmode man-antenna 9` and similar trailing manual values so
  they are not misread as the optional input table path.
- Added `--antenna` as an explicit alias for `--antennas` in `gdp-flag`.
- Changed missing CASA/casatools execution to print a concise terminal message
  rather than a Python traceback.

Follow-up Simplification
- Removed legacy optional positional input-table arguments from `gdp-stats`,
  `gdp-util`, and `gdp-flag`.
- GDP table inputs should now be supplied explicitly with `--input-table`,
  `--gain-table`, or `--bandpass-table`, or read from the active `gdp-setup`
  configuration.
- Kept the hidden trailing values in `gdp-plot` because those are used for plot
  mode values such as selected antennas, not for table paths.

## 2026-08-05 18:10:00 IST

Prompt / Request
- Remove the `--smode colormap` option from `gdp-stats`.

Changes Made
- Removed `colormap`, `gain-colormap`, and `gain_colormap` from
  `gdp-stats --smode` parsing.
- Changed `gdp-stats --smode all` to run data-product tasks only:
  `gains`, `stats`, `ks`, and `self-corr`.
- Removed the direct colormap plotting path and related CLI options from
  `gdp-stats`: `-pchans`, `--range`, `--output-colormap`, and
  `--plot-format`.
- Kept colormap plotting in `gdp-plot -pmode colormap`; when a gains NPZ is
  missing, `gdp-plot` already asks `gdp-stats` to create it with
  `--smode gains`.
- Updated the README, `gdp-stats` HTML, and sample plan to use
  `gdp-plot -pmode colormap` for plotting.

## 2026-08-05 18:20:00 IST

Prompt / Request
- `gdp-flag --fmode man-antenna 9` should copy flags from the last flag
  version by default.

Changes Made
- Changed `gdp-flag` so, unless `--new-flags` is set, it automatically carries
  the highest existing `NAME_fV<version>.flg` file into the new output version.
- Kept `--use-flags VERSION` as the way to choose a specific prior flag version.
- If no previous flag version exists, `gdp-flag` now logs that it is writing
  only the newly requested flags.
- Updated flag documentation to describe the default carry-forward behavior.

## 2026-08-05 18:30:00 IST

Prompt / Request
- Add `gdp-flag --fmode remove-version <version>`; if no version is supplied,
  remove the highest available flag version.

Changes Made
- Added `remove-version` aliases to `gdp-flag --fmode`.
- `gdp-flag --fmode remove-version VERSION` removes
  `NAME_fV<VERSION>.flg` for the selected mode/scan/channel product base.
- `gdp-flag --fmode remove-version` removes the highest available matching
  version.
- This removal mode works from product naming metadata and does not read CASA
  table rows.
- Updated the flag command and flag product documentation.

## 2026-08-05 18:40:00 IST

Prompt / Request
- If a required flag version is not present for any flag-version argument,
  print an error message in the terminal log and exit gracefully.

Changes Made
- Added logged error handling in `gdp-flag` for missing versions requested by
  `--use-flags VERSION` and `--fmode remove-version VERSION`.
- Missing matching flag versions now write an `ERROR:` line to the `gdp-flag`
  task log before exiting with `SystemExit`.
- Added task-log error reporting in `gdp-stats` when a requested `--flagver`
  cannot be found for flagged stats/KS/self-correlation processing.
- Updated flag documentation to state that missing required versions are logged
  and exit without a Python traceback.

Follow-up Rename
- Renamed the `gdp-flag` output flag-version option from `--fver VERSION` to
  `--out-fver VERSION` for clarity.
- The input/carry flag-version selector remains `--use-flags [VERSION]`, and
  the remove target remains `--fmode remove-version [VERSION]`.

Follow-up Validation
- Tightened `gdp-flag --fmode man-chan` so it works only in bandpass mode.
- If `--mode gain --fmode man-chan` is requested, GDP now prints a concise
  `ERROR:` terminal message and exits before reading CASA table rows.
- In `--mode auto`, `--fmode man-chan` now infers bandpass mode.

## 2026-08-05 18:28:21 IST

Prompt / Request
- Update the step-by-step guide in all help files.

Changes Made
- Refreshed `doc/gdp-step-by-step.html` to show the current recommended GDP
  workflow: setup, table inspection, gains/stats/KS products, flag-version
  management, self-correlation products, plots, plan execution, and release.
- Added current `gdp-flag` examples for CASA flags, manual antenna flags,
  manual bandpass channel flags, explicit output flag versions, new-only flag
  writes, and flag-version removal.
- Added expected terminal-output patterns for flag carry-forward, missing
  requested flag versions, and invalid gain-mode channel flag requests.
- Added a step-by-step guide link block to every HTML help page and linked the
  guide from every documentation tree.
- Updated `doc/README.md`, `doc/README.html`, and `pipelines/sample_stats.plan`
  so quick-start and dry-run examples match the current `gdp-stats`,
  `gdp-flag`, `gdp-plot`, and `gdp-plan-run` behavior.

## 2026-08-06 11:18:38 IST

Prompt / Request
- Change the flag-version naming convention to use `fV<flagversion>`.
- When writing data products or plots with a flag version, include the same
  `_fV<flagversion>` in the output name.

Changes Made
- Updated shared flag sidecar naming from `NAME_V<version>.flg` to
  `NAME_fV<version>.flg`.
- Updated `gdp-stats`, `gdp-plot`, and `gdp-flag` to parse `fV1`, `V1`, or
  `1` as the same flag-version value.
- Updated default flagged `gdp-stats` derived product names so stats, KS, and
  self-correlation outputs append `_fV<version>` when `--use-flags` is active.
- Updated default flagged `gdp-plot` output names so plots append
  `_fV<version>` when `--use-flags` is active.
- Updated plot discovery for flagged KS/self-correlation products so existing
  `_fV<version>` NPZ products can be found when plotting without an explicit
  scan list.
- Updated command help text and HTML/Markdown documentation to describe the
  new `fV` sidecar and output naming convention.

Follow-up Plot Title
- Removed the plot-only `PChans: ...` text from bandpass colormap plot titles.
  The selected channel window still affects the plotted data and output
  filename; only the redundant title text is suppressed.

## 2026-08-06 11:25:58 IST

Prompt / Request
- Add manual flagging syntax so `gdp-flag --fmode man-antenna` and
  `--fmode man-chan` can flag selected Stokes for selected antennas/channels.

Changes Made
- Added a manual-selection parser for `gdp-flag` that accepts
  `TARGET:STOKES` entries for manual antenna and channel flags.
- Supported examples include `1:0`, `[1-4]:1`, `(1, 3):0`, and mixed forms
  such as `1:0, 3:1, [11-14]:1, 23`.
- Targets without `:STOKES` continue to flag all Stokes for that antenna or
  channel.
- Preserved the existing square-bracket inclusive range convention, so
  `[900-1200]` still flags channels 900 through 1200; hyphen ranges such as
  `[900-1200]:1` are also supported.
- Updated manual flag masks so antenna/channel selection and Stokes selection
  are combined sample-by-sample in the written `.flg` file.
- Updated `gdp-flag`, flag product, README, and step-by-step documentation.

## 2026-08-06 11:30:08 IST

Prompt / Request
- Standardize antenna and channel range selections so bracketed hyphen ranges
  like `[1-400]` mean antennas/channels 1 through 400 everywhere.

Changes Made
- Standardized command help and documentation examples to use `[start-end]`
  for antenna and channel ranges.
- Updated `gdp-plot -pchans` so `[START-END]` is inclusive at both ends.
  Internally GDP still uses an exclusive upper bound for array masking, so
  `[800-1200]` is stored as `(800, 1201)` and filenames keep
  `pchan_800_1200`.
- Verified `[1-4]` parsing for `gdp-stats --antennas`,
  `gdp-plot --antenna`, `gdp-flag --antennas`, manual antenna flags, and
  manual channel flags.

## 2026-08-06 11:33:06 IST

Prompt / Request
- Correct the manual channel fmode spelling to `man-chan`.
- Keep `--fmode man-antenna` working for both gain and bandpass mode, while
  `--fmode man-chan` works only for bandpass mode.

Changes Made
- Updated the public `gdp-flag` CLI and documentation to use `--fmode
  man-chan` and `--man-chan`.
- Removed the misspelled `--man-chann` option from the visible command-line
  help.
- Kept `man-antenna` unrestricted across gain and bandpass flag products.
- Kept `man-chan` guarded so a gain-mode request exits gracefully with
  `ERROR: --fmode man-chan works only with --mode bandpass.`
- Retained the old `man-chann` fmode spelling internally as a compatibility
  alias for older plan files.

## 2026-08-06 11:50:43 IST

Prompt / Request
- Implement `gdp-flag --fmode all-std-thrsld` rather than the older
  `all-thrsld` name.
- Allow an optional threshold value `alpha`; default alpha is `1`.
- For each Stokes, calculate Real-1 and Imag standard deviations, derive the
  same Gaussian one-expected-point RE/IM radius used by `gdp-plot -pmode
  reim`, and flag samples farther than `alpha * R` without subtracting the
  measured Real/Imag means.
- Report the percentage of data flagged in terminal output and task logs.

Changes Made
- Added `all-std-thrsld` as an implemented `gdp-flag` mode for gain and
  bandpass products.
- Removed the old public `all-thrsld` spelling so the supported all-antenna
  standard-deviation threshold mode is unambiguously `all-std-thrsld`.
- Added alpha parsing as either a trailing fmode value, for example
  `--fmode all-std-thrsld 1.5`, or the explicit option `--alpha 1.5`.
- For each Stokes, GDP now computes Real-1 and Imag values in percent,
  estimates per-Stokes standard deviations from finite unflagged samples,
  computes `R = sqrt(2 log N)`, and flags samples whose zero-centered
  normalized RE/IM distance is greater than `alpha * R`.
- The threshold fit excludes CASA table flags and any carried previous GDP
  flag version so already-known bad samples do not set the threshold.
- Terminal output and the task log now report per-Stokes threshold statistics,
  new flag counts, and final flag percentages.
- The `.flg` header now records `threshold_alpha` and the full
  `ALL STD THRESHOLD FLAGS` intent provenance.
- Updated the flag documentation, product-format page, README, and
  step-by-step guide with the new fmode and alpha examples.

## 2026-08-06 12:03:35 IST

Prompt / Request
- Implement `gdp-flag --fmode ante-std-thrsld`, where the same RE/IM
  threshold statistics are calculated separately for each antenna and then
  applied only to that antenna.

Changes Made
- Added `ante-std-thrsld` as an implemented `gdp-flag` threshold mode.
- Reused the same alpha and one-expected-point ellipse rule as
  `all-std-thrsld`, but grouped samples by antenna and Stokes before
  calculating the standard deviations and `R`.
- `all-std-thrsld` remains pooled across all selected antennas for each
  Stokes; `ante-std-thrsld` is per antenna and Stokes.
- Per-antenna threshold runs now log lines such as
  `ante-std-thrsld antenna=0 stokes=0 ... new_flags=... (...)`.
- The `.flg` header records `ANTENNA STD THRESHOLD FLAGS` provenance for
  this mode.
- Updated README, HTML help, flag product documentation, and the step-by-step
  guide with `ante-std-thrsld` examples.

## 2026-08-06 12:47:00 IST

Prompt / Request
- Remove the subtraction of `mean_real` and `mean_imag` from the
  `all-std-thrsld` and `ante-std-thrsld` flagging criteria.

Changes Made
- Changed the standard-deviation threshold distance in `gdp-flag` to be
  zero-centered in the RE/IM plane.
- `all-std-thrsld` and `ante-std-thrsld` now use
  `sqrt((Real-1/std_real)^2 + (Imag/std_imag)^2)` rather than subtracting the
  measured Real/Imag means first.
- Runtime log lines and stored flag-intent text now report only
  `real_std` and `imag_std` for these modes.
- Updated the README, `gdp-flag` HTML help, and the step-by-step guide to
  describe the std-only, zero-centered threshold rule.

## 2026-08-06 12:13:05 IST

Prompt / Request
- Implement `gdp-flag --fmode ante-thrsld`, taking a percentage threshold
  argument.
- If an antenna has enough data already flagged in the flag table, promote the
  entire antenna to flagged.

Changes Made
- Added `ante-thrsld` as an implemented antenna flag-fraction threshold mode.
- Added percent parsing as either a trailing fmode value, for example
  `--fmode ante-thrsld 40`, or the explicit option `--percent 40`.
- Default threshold is `70` percent.
- For each antenna, GDP now measures missing availability against the maximum
  unflagged availability seen for any antenna in the selected data:
  `(Stokes, channel)` units in bandpass mode and `(Stokes, time)` units in
  gain mode. If no previous GDP flag file is carried, CASA table flags are
  used as the source.
- If the missing-availability fraction is at least the requested threshold,
  GDP flags all selected samples for that antenna in the output flag version.
- Terminal output and task logs report the per-antenna source flag fraction,
  whether each antenna was promoted, the promoted antenna list, and the final
  flag percentages.
- The `.flg` header now records `threshold_percent` and
  `ANTENNA FLAG FRACTION THRESHOLD FLAGS` provenance.
- Updated README, HTML help, flag product documentation, and the step-by-step
  guide with `ante-thrsld` examples.

## 2026-08-06 13:18:00 IST

Prompt / Request
- Change `ante-thrsld` percentage calculation so it uses the maximum number of
  unflagged channels in bandpass mode, or unflagged time stamps in gain mode,
  seen for any antenna as the reference denominator.

Changes Made
- Updated `gdp-flag --fmode ante-thrsld` to compute per-antenna availability
  using unique `(Stokes, channel)` units in bandpass mode and unique
  `(Stokes, time)` units in gain mode.
- The reference denominator is now the maximum unflagged availability seen for
  any antenna in the selected data.
- The per-antenna flagged percentage is now the missing fraction relative to
  that reference denominator, rather than the raw fraction of flagged samples
  within the antenna's own sample count.
- Runtime logs now report the selected availability axis, the maximum
  unflagged reference size, each antenna's unflagged availability, and the
  derived flagged fraction used for promotion.
- Updated the README, `gdp-flag` help page, and the step-by-step runtime
  example to describe the new denominator rule.

## 2026-08-06 13:32:00 IST

Prompt / Request
- Add `gdp-flag --fmode ante-mean-thrsld [ALPHA]`, where an antenna/Stokes
  group is flagged from its antenna-mean location.

Changes Made
- Added `ante-mean-thrsld` as a new implemented `gdp-flag --fmode`.
- For each Stokes, GDP now computes the global Real-1 and Imag standard
  deviations from all unflagged finite samples across all antennas.
- GDP then computes the Real-1 and Imag mean for each antenna/Stokes group and
  the modulus of that antenna mean point.
- The cutoff is now `threshold * sqrt(std_real^2 + std_imag^2)`, using the
  global Stokes-wise point scatter rather than the earlier antenna-mean
  ellipse construction.
- If an antenna/Stokes mean modulus is greater than that cutoff, GDP flags the
  full antenna/Stokes group.
- The mode accepts trailing alpha syntax, for example
  `--fmode ante-mean-thrsld 6`, and the explicit `--alpha VALUE` option.
- Default threshold is now `5` for `ante-mean-thrsld`.
- Runtime logs and stored `flag-intent` entries report the global Stokes-wise
  std values, antenna mean, antenna-mean modulus, cutoff modulus, and
  promotion decision for each antenna/Stokes group.
- Updated the README, `gdp-flag` HTML help, the flag-product documentation,
  and the step-by-step runtime example with `ante-mean-thrsld`.

Follow-up Default
- Changed the default `ante-thrsld` percentage threshold from `30` to `70`.

## 2026-08-06 12:22:18 IST

Prompt / Request
- Implement `gdp-flag --fmode ks-thrsld [optional value]`.
- For each antenna/Stokes/Real/Imag component, calculate the KS statistic.
- For the same sample size, generate 128 Gaussian random realizations,
  calculate the KS for each, average those simulated KS values, and flag if
  the measured KS is greater than the optional multiplier times the simulated
  mean.

Changes Made
- Added `ks-thrsld` as an implemented `gdp-flag` threshold mode.
- Added multiplier parsing as either a trailing fmode value, for example
  `--fmode ks-thrsld 1.5`, or the explicit option `--factor 1.5`.
- Default KS threshold multiplier is `1`.
- For each selected antenna and Stokes, GDP computes fitted-normal KS
  statistics for Real-1 and Imag samples in percent.
- For each component sample size, GDP runs 128 Gaussian-pair KS simulations
  and uses their mean as the reference threshold.
- If either Real or Imag has measured KS greater than `factor * gaussian_mean`,
  the full antenna/Stokes group is flagged in the output flag version.
- Existing CASA and carried GDP flags are excluded while calculating the KS
  statistic and simulation comparison.
- Terminal output and task logs report the measured KS, simulated mean KS,
  threshold, per-component decision, promoted antenna/Stokes list, and final
  flag percentages.
- The `.flg` header now records `threshold_factor` and
  `KS THRESHOLD FLAGS` provenance.
- Updated README, HTML help, flag product documentation, and step-by-step
  guide with `ks-thrsld` examples.

## 2026-08-06 12:24:25 IST

Prompt / Request
- After each flagging cycle, print a table showing how many data points and
  what percentage of each antenna's data are flagged.

Changes Made
- Added a per-antenna final flag summary to `gdp-flag` after each output
  `.flg` file is written.
- The table is written to both terminal output and the task log.
- Columns are `antenna`, `flagged_points`, `total_points`, and
  `flagged_percent`.
- The summary uses the final output flags after all carried previous flags and
  new flags have been combined.
- Updated the `gdp-flag` help page and step-by-step guide to show the new
  runtime table.

## 2026-08-06 12:40:00 IST

Prompt / Request
- Extend `gdp-flag --fmode remove-version [VERSION]` so the version selector
  can also be a closed range like `[1-3]` or an open-ended range like `[1:]`.

Changes Made
- Added range parsing for `gdp-flag --fmode remove-version`.
- `remove-version 3` still removes only `fV3`.
- `remove-version [1-3]` now removes every matching version from `fV1`
  through `fV3`.
- `remove-version [1:]` now removes every matching version at or above `fV1`.
- Closed ranges require every requested version to exist; otherwise GDP writes
  an `ERROR:` message and exits without deleting a partial subset.
- Open-ended ranges remove every existing matching version from the requested
  start upward; if none exist, GDP writes an `ERROR:` message and exits.
- Updated `gdp-flag` HTML help, the flag-product documentation, the README
  command examples, and the step-by-step guide with the new selector forms.

## 2026-08-06 12:58:00 IST

Prompt / Request
- Add `gdp-flag --fmode summary [optional flagversion no]` to print only the
  per-antenna flag summary from the requested version or, if omitted, from the
  highest available matching flag version.

Changes Made
- Added `summary` as the public `gdp-flag --fmode` name for read-only flag
  inspection, while keeping `show` as a backward-compatible internal alias.
- `gdp-flag --fmode summary` now loads the highest matching `.flg` sidecar and
  prints the existing per-antenna summary table without writing a new flag
  version.
- `gdp-flag --fmode summary VERSION` loads that specific `fV<VERSION>` file
  and prints the same summary table.
- Missing requested summary versions now produce a logged `ERROR:` message and
  exit cleanly, matching the other flag-version lookup behaviors.
- Updated the flag help page, the flag-product documentation, the README
  examples, and the step-by-step guide with the new `summary` mode.

## 2026-08-06 13:10:00 IST

Prompt / Request
- Ensure every new flag version updates the stored `flag-intent`, and make
  `gdp-flag --fmode summary` print the `flag-intent` along with the per-antenna
  summary.

Changes Made
- Changed `gdp-flag` so new `.flg` versions keep the previously stored
  `flag-intent` entries when earlier GDP flags are carried, then append the
  new flagging provenance for the current operation.
- Removed the old synthetic `PREVIOUS GDP FLAGS: fV...` marker in favor of
  carrying the actual prior intent history forward.
- Added runtime logging of the stored `flag-intent` block after a new `.flg`
  file is written.
- Updated `gdp-flag --fmode summary` to print the stored `flag-intent` block
  before the per-antenna flagged-point table.
- Updated the `gdp-flag` help page, the flag-product documentation, and the
  step-by-step guide to describe the accumulated intent history and summary
  output.

## 2026-08-06 13:32:00 IST

Prompt / Request
- Add a runtime `gaintable/` folder during setup.
- Extend `gdp-flag` with `--apply-flag [VERSION]` so an existing GDP flag
  version can be written back into a copied CASA gain or bandpass table.
- Support `--output-table` for the copied CASA table path, and keep
  `flag-intent` provenance inside the output CASA table metadata when
  possible.

Changes Made
- Added `gaintable/` to the `gdp-setup` runtime layout and saved
  `gaintable_dir` in the setup/config path map.
- Extended `script/gdp-flag` with a standalone `--apply-flag [VERSION]`
  action that:
  copies the selected gain/bandpass table,
  resolves the requested or highest matching `fV<version>` sidecar,
  writes those flags into the copied CASA table `FLAG` column for the selected
  scan/channel subset, and
  stores applied flag provenance in CASA table keywords and README/comment
  lines when supported by the active CASA table interface.
- Added `--output-table` for explicit copied-table destinations and kept the
  default destination under `rundir/gaintable/` as
  `<original>_fV<version>.<suffix>`.
- Updated the setup, flag, flag-product, README, and step-by-step
  documentation with the new `gaintable` runtime convention and
  `--apply-flag` examples.

Verification
- `python3 -m py_compile script/gdp-setup script/gdp-flag`

Notes
- The active shell here does not include `casatools`, so the CASA metadata
  write-back path could not be live-tested in this environment; the new code
  uses the same CASA table API family GDP already depends on and degrades
  quietly if optional metadata methods are unavailable.

## 2026-08-10 17:15:00 IST

Prompt / Request
- In `gdp-util`, add options for channel width, band width, and integration
  time, reporting the mean value when multiple values are present.

Changes Made
- Kept `--channel-width` as the per-channel width summary and added shared
  positive finite mean/min/max statistics.
- Added `--band-width` with `--bandwidth` as an alias for total band-width
  summaries in MHz, preferring `TOTAL_BANDWIDTH` and falling back to summed
  channel widths where needed.
- Added `--integration-time` summaries in seconds, preferring `INTERVAL` and
  falling back to `EXPOSURE`.
- Updated `doc/gdp-util.html` and `doc/README.md` examples/options.

Verification
- `python3 -m py_compile script/gdp-util`
- `script/gdp-util --help`

## 2026-08-10 17:25:00 IST

Prompt / Request
- Remove self-correlation from `gdp-stats --smode all`; keep self-correlation
  available only as its separate `--smode self-corr` option.

Changes Made
- Changed `SMODE_ALL_TASKS` in `script/gdp-stats` so `all` expands only to
  `gains`, `stats`, and `ks`.
- Updated `gdp-stats` and README documentation examples to describe
  self-correlation as an explicit separate mode.

Verification
- `python3 -m py_compile script/gdp-stats`
- `script/gdp-stats --help`
- Verified `parse_smode("all")` expands to `["gains", "stats", "ks"]`.

## 2026-08-10 17:35:00 IST

Prompt / Request
- In `gdp-util`, read channel width and band width from the bandpass table, and
  read integration time from the `INTERVAL` keyword.

Changes Made
- Changed channel-width and band-width action resolution so, when no explicit
  table is supplied, they use the saved `bandpass_table` rather than falling
  back to the saved gain table first.
- Changed `--integration-time` to read the table `INTERVAL` keyword instead of
  reading the `INTERVAL` or `EXPOSURE` columns.
- Updated CLI help and `gdp-util` documentation to describe the source of each
  value.

Verification
- `python3 -m py_compile script/gdp-util`
- `script/gdp-util --help`

## 2026-08-10 17:45:00 IST

Prompt / Request
- Keep verbose antenna flag-fraction threshold intent messages in the
  `gdp-flag` log, but shorten the terminal output to only
  `ANTENNA FLAG FRACTION THRESHOLD FLAGS:`.
- Apply the same terminal shortening to all other flag-type intent messages.

Changes Made
- Added `TaskLogger.terminal_line()` in `script/gdp-flag` to truncate only
  terminal display for flag-intent lines containing `FLAGS:`.
- Kept the underlying file log write unchanged, so the full per-antenna detail
  remains in the log file and flag intent metadata.

Verification
- `python3 -m py_compile script/gdp-flag`
- Verified the terminal formatter truncates manual, threshold, antenna
  fraction, and KS flag-intent lines while leaving short CASA flag lines
  unchanged.

## 2026-08-11 09:40:00 IST

Prompt / Request
- For `gdp-util --integration-time`, use the gain table and print
  `integration-time_sec`.
- For `--bandwidth` or `--channelwidth`, terminal output should print only
  `band-width_hz` and `chan-width_hz` respectively.
- Revise integration time to calculate the median positive difference between
  MJD timestamp values in one scan, and print channel/band widths in kHz or MHz
  as appropriate.

Changes Made
- Added `--channelwidth` as an alias for `--channel-width`.
- Changed channel-width and bandwidth summaries to return a single mean value
  with unit-aware keys such as `chan-width_kHz` or `band-width_MHz`.
- Changed integration-time resolution to default to the saved gain table and
  calculate `integration-time_sec` as the median positive spacing between
  unique `TIME` values in the first available scan.

Verification
- `python3 -m py_compile script/gdp-util`
- `script/gdp-util --help`

## 2026-08-11 10:05:00 IST

Prompt / Request
- Align the workflow so `gdp-stats` first writes gain/bandpass NPZ products,
  then `gdp-flag` creates flag versions, then other stat modes and plotting are
  run.
- Correct `gdp-stats` default naming so data product filenames do not include
  channel selections or antenna selections. Plot filenames may still include
  specific channel or antenna selections.

Changes Made
- Changed `gdp-stats` default output labels to use only the scan label for
  gains, stats, KS, and self-corr products.
- Changed `gdp-flag` matching gains-product base to use the same channel-free
  filename convention, so `.flg` sidecars remain aligned with the gains NPZ.
- Changed `gdp-plot` source-product discovery and missing-product creation to
  look for channel-free `gdp-stats` products, while preserving plot output
  channel/antenna tags.
- Added `--smode gain` as an alias for `--smode gains`.
- Updated stats and product documentation to describe the channel-free data
  product naming convention.

Verification
- `python3 -m py_compile script/gdp-stats script/gdp-flag script/gdp-plot`
- Verified default `gdp-stats` and `gdp-plot` source product path helpers omit
  `-chan_<bchan>_<echan>`.

## 2026-08-11 10:35:00 IST

Prompt / Request
- Remove the now-unneeded `--bchan` and `--echan` options from stats and
  plots.
- Check that no functionality goes missing from the new workflow.

Changes Made
- Removed `--bchan` and `--echan` from the `gdp-stats` and `gdp-plot`
  user-facing CLIs.
- Kept `gdp-stats` products full-channel and channel-free by default:
  `gdp-gains-<mode>-<scan>.npz`, `gdp-stats-<mode>-<scan>.npz`, and
  `gdp-ks-<mode>-<scan>.npz`.
- Kept plot-only channel selection through `gdp-plot -pchans`, so focused
  bandpass plots can still be made without changing source NPZ names.
- Kept antenna-specific plot naming for plot modes that create selected-antenna
  outputs.
- Preserved the internal channel-window helper arguments used by `gdp-flag`,
  so legacy flag workflows and manual channel flagging are not broken while
  stats/plot CLIs stay simplified.
- Updated the main workflow documentation and HTML examples to stop showing
  `--bchan` / `--echan` for stats and plot commands.

Functionality Check
- Source data products are now always full-channel products, so later flagging,
  stats, and plotting can reuse the same product base.
- Channel-specific flagging remains available through `gdp-flag --fmode
  man-chan --man-chan ...`.
- Plot-only channel windows remain available through `gdp-plot -pchans ...`.
- `--smode all` remains limited to `gains`, `stats`, and `ks`; self-correlation
  remains a separate explicit `--smode self-corr` task.
