# GDP Documentation

GDP version: `0.1.5`

GDP (Gain Diagnostic Product) is being developed as a command-line toolkit for
gain and bandpass diagnostics, statistics products, plotting, diagnosis, and
flag-product generation.

## Documentation Tree

- `README.html`: main browser entry point.
- `gdp-setup.html`: setup command for runtime, gain-table, and bandpass-table configuration.
- `gdp-util.html`: utility command for reading metadata from CASA tables.
- `gdp-stats.html`: statistics command and GDP data-product formats.
- `gdp-flag.html`: flag sidecar creation and versioning command.
- `gdp-plot.html`: plotting command for GDP NPZ products.
- `gdp-plan-run.html`: plan-file runner for repeatable GDP workflows.
- `gdp-product-gains.html`: gains NPZ product format.
- `gdp-product-flags.html`: versioned `.flg` flag sidecar format.
- `gdp-product-stats.html`: stats NPZ product format.
- `gdp-product-ks.html`: KS NPZ product format.
- `gdp-product-self-corr.html`: self-correlation NPZ product format.
- `gdp-product-cross-corr.html`: cross-correlation NPZ product format.

## Active Commands

- `script/gdp-setup`: initializes and remembers the GDP runtime directory and
  separate gain and bandpass table locations.
- `script/gdp-util`: reads useful metadata from CASA gain, bandpass, or
  MeasurementSet tables, and provides `--git-push` release/git workflow
  support.
- `script/gdp-stats`: computes gain/bandpass products including raw gains,
  antenna-wise statistics, KS products, and self-correlation products, with
  optional CSV output. By default it writes one product per scan; use
  `--combine-scans` for one combined `allscans` product.
- `script/gdp-flag`: creates versioned `.flg` flag sidecar files from CASA
  table flags, manual antenna flags, or manual bandpass channel flags.
- `script/gdp-plot`: plots GDP NPZ products and runs `gdp-stats` first when a
  requested product is missing. By default it writes one plot per scan; use
  `--combine-scans` for one combined `allscans` plot, or `--npz-path` to plot
  directly from a selected NPZ file.
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
script/gdp-setup --setup-file project-a-setup.json --gain-table /path/to/table.g --rundir /path/to/rundir
```

Show the saved setup:

```bash
script/gdp-setup --show
```

Read a CASA table header:

```bash
script/gdp-util --input-table /path/to/table.g --header
script/gdp-util --gain-table --header
script/gdp-util --bandpass-table --header
```

Compute GDP statistics:

```bash
script/gdp-stats --smode stats,ks
script/gdp-stats --smode all
script/gdp-stats --mode gain --scan 17 --smode gains
script/gdp-plot --mode gain --scan 17 -pmode colormap --range 20
script/gdp-plot --mode bandpass -pmode colormap -pchans "[16,64]" --range 20
script/gdp-stats --mode gain --scan 17 --smode gains --flagver 1
script/gdp-stats --mode gain --scan 17 --smode stats,ks --use-flags --flagver 1
script/gdp-stats --antennas [0,9] --smode stats
script/gdp-stats --antennas 1 2 3 4 13 --smode stats
script/gdp-stats --antennas "(1,5)" 6 "(9-12)" 15 16 19 --smode stats
script/gdp-stats --smode stats --csv
```

Create GDP flag versions:

```bash
script/gdp-flag --mode gain --scan 17 --fmode casa-flags
script/gdp-flag --mode gain --scan 17 --fmode man-antenna --man-antenna 3,4 --use-flags
script/gdp-flag --mode bandpass --scan 18 --bchan 800 --echan 3000 --fmode man-chann --man-chann "[900,1200]" --new-flags
```

Plot AntStat-style gain histograms from the gains NPZ product:

```bash
script/gdp-plot --mode gain -pmode hist
script/gdp-plot --mode gain -pmode all
```

`-pmode all` runs only `colormap`, `hist`, `stats`, and `ks`.

Plot a selected NPZ directly:

```bash
script/gdp-plot --mode gain --scan 17 -pmode colormap --npz-path /path/to/gdp-gains-gain-scan17.npz
```

Plot pooled Real-1 versus Imag diagnostics for selected antennas:

```bash
script/gdp-plot --mode gain --scan 17 -pmode reim --antenna "[0,29]"
script/gdp-plot --mode bandpass --scan 18 --bchan 800 --echan 3000 -pmode reim --antenna "[0,29]"
```

Plot selected antennas as AntStat-style gain-time plots with Stokes side by side:

```bash
script/gdp-plot --mode gain --scan 17 -pmode antenna --antenna "[0,29]"
script/gdp-plot --mode bandpass --scan 18 --bchan 800 --echan 3000 -pmode antenna --antenna "[0,29]"
```

Read table date and channel-width metadata as JSON:

```bash
script/gdp-util --input-table /path/to/table.ms --date --channel-width --json
```

Create a version archive, commit, and push:

```bash
script/gdp-util --git-push -m "Describe the change"
```

Run a plan:

```bash
script/gdp-plan-run pipelines/sample_stats.plan --dry-run
```
