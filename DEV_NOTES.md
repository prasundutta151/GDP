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
