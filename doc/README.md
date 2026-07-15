# GDP Documentation

GDP version: `0.1.0`

GDP (Gain Diagnostic Product) is being developed as a command-line toolkit for
gain and bandpass diagnostics, statistics products, plotting, diagnosis, and
flag-product generation.

## Documentation Tree

- `README.html`: main browser entry point.
- `gdp-setup.html`: setup command for runtime and source-data configuration.
- `gdp-util.html`: utility command for reading metadata from CASA tables.
- `gdp-stats.html`: statistics command and GDP data-product formats.
- `gdp-plot.html`: plotting command for GDP NPZ products.
- `gdp-plan-run.html`: plan-file runner for repeatable GDP workflows.
- `gdp-product-gains.html`: gains NPZ product format.
- `gdp-product-stats.html`: stats NPZ product format.
- `gdp-product-ks.html`: KS NPZ product format.
- `gdp-product-self-corr.html`: self-correlation NPZ product format.
- `gdp-product-cross-corr.html`: cross-correlation NPZ product format.

## Active Commands

- `script/gdp-setup`: initializes and remembers the GDP runtime directory and
  separate gain, bandpass, and optional source-data locations.
- `script/gdp-util`: reads useful metadata from CASA gain, bandpass, or
  MeasurementSet tables, and provides `--git-push` release/git workflow
  support.
- `script/gdp-stats`: computes gain/bandpass products including raw gains,
  antenna-wise statistics, and KS product schema, with optional CSV output.
  By default it writes one product per scan; use `--combine-scans` for one
  combined `allscans` product.
- `script/gdp-plot`: plots GDP NPZ products and runs `gdp-stats` first when a
  requested product is missing. By default it writes one plot per scan; use
  `--combine-scans` for one combined `allscans` plot.
- `script/gdp-plan-run`: reads a GDP plan file and runs GDP command intents
  with internal variable substitution.

## Runtime Layout

`gdp-setup` creates and remembers a runtime directory. The current standard
subfolders are:

- `data-product/gains/npz`
- `data-product/gains/csv`
- `data-product/stats/npz`
- `data-product/stats/csv`
- `data-product/ks/npz`
- `data-product/ks/csv`
- `data-product/self-corr/npz`
- `data-product/cross-corr/npz`
- `data-product/cross-corr/csv`
- `data-product/flag/npz`
- `data-product/flag/csv`
- `plots/png`
- `plots/eps`
- `plots/pdf`

Inside this repository the default runtime directory is `rundir/`, but
`gdp-setup` can configure a different runtime location.

## Examples

Set up GDP:

```bash
script/gdp-setup --gain-table /path/to/gain/table.g --bandpass-table /path/to/bandpass/table.b --rundir /path/to/rundir
```

Show the saved setup:

```bash
script/gdp-setup --show
```

Read a CASA table header:

```bash
script/gdp-util /path/to/table.g --header
```

Compute GDP statistics:

```bash
script/gdp-stats --stats --csv
```

Plot AntStat-style gain histograms from the gains NPZ product:

```bash
script/gdp-plot --mode gain -pmode gain-hist
```

Plot selected antennas as AntStat-style gain-time plots with Stokes side by side:

```bash
script/gdp-plot --mode gain -pmode antenna 0,1,2
```

Read table date and channel-width metadata as JSON:

```bash
script/gdp-util /path/to/table.ms --date --channel-width --json
```

Create a version archive, commit, and push:

```bash
script/gdp-util --git-push -m "Describe the change"
```

Run a plan:

```bash
script/gdp-plan-run pipelines/sample_stats.plan --dry-run
```
