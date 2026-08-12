# GDP Documentation

GDP version: `0.1.5`

GDP (Gain Diagnostic Product) is being developed as a command-line toolkit for
gain and bandpass diagnostics, statistics products, plotting, diagnosis, and
flag-product generation.

## Documentation Tree

- `README.html`: main browser entry point.
- `gdp-step-by-step.html`: recommended workflow from setup through products,
  flag versions, plots, plans, and release steps.
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
  separate gain and bandpass table locations, and can clean generated runtime
  outputs with confirmation.
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
- `logs`
- `gaintable`
- `plots/png`
- `plots/eps`
- `plots/pdf`

Inside this repository the default runtime directory is `rundir/`, but
`gdp-setup` can configure a different runtime location. `script/gdp-setup
--clean` removes generated outputs under `data-product/`, `plots/`, `logs/`,
and `gaintable/`, then recreates the standard runtime folders. It asks for
confirmation by default; use `script/gdp-setup --clean --dry-run` to preview
the delete list, or `script/gdp-setup --clean no-stop` for scripted cleanup
without the prompt. Setup JSON files in the runtime root and `.gdp-config.json`
are kept.

Add `--relative-path` to GDP commands when terminal/log output should first
state the runtime directory and then refer to generated runtime files relative
to that directory. This is a display-only option: actual filenames, write
locations, and machine-readable JSON output are unchanged.

## Examples

Set up GDP:

```bash
script/gdp-setup --gain-table /path/to/gain/table.g --bandpass-table /path/to/bandpass/table.b --rundir /path/to/rundir
script/gdp-setup --setup-file project-a-setup.json --gain-table /path/to/table.g --rundir /path/to/rundir
script/gdp-setup --clean --dry-run
script/gdp-setup --clean
script/gdp-setup --clean no-stop
```

Show the saved setup:

```bash
script/gdp-setup --show
```

Read a CASA table header:

```bash
script/gdp-util --input-table /path/to/table.g --header
script/gdp-util --mode gain --header
script/gdp-util --mode bandpass --header
script/gdp-util --mode gain --scans --antenna
script/gdp-util --mode gain --timeinfo
```

Compute GDP statistics:

```bash
casa --nogui --nologger --nologfile --log2term -c script/gdp-stats --smode gains,stats,ks
script/gdp-stats --smode all
script/gdp-stats --smode self-corr
script/gdp-stats --mode gain --scan 17 --smode gains
script/gdp-stats --mode gain --scan 17 --smode gain --adjust-mean
script/gdp-plot --mode gain --scan 17 -pmode colormap --range 20
script/gdp-plot --mode bandpass -pmode colormap -pchans "[16-64]" --range 20
script/gdp-stats --mode gain --scan 17 --smode gains --flagver 1
script/gdp-stats --mode gain --scan 17 --smode stats,ks --use-flags --flagver 1
script/gdp-plot --mode gain --scan 17 -pmode colormap --use-flags --flagver 1
script/gdp-stats --antennas [0-9] --smode stats
script/gdp-stats --antennas 1 2 3 4 13 --smode stats
script/gdp-stats --antennas "[1-5]" 6 "[9-12]" 15 16 19 --smode stats
script/gdp-stats --smode stats --csv
```

Create GDP flag versions:

```bash
script/gdp-flag --mode gain --scan 17 --fmode casa-flags
script/gdp-flag --mode gain --scan 17 --fmode man-antenna --man-antenna 3,4 --use-flags
script/gdp-flag --mode gain --scan 17 --fmode man-antenna --man-antenna "1:0, 3:1, [11-14]:1, 23"
script/gdp-flag --mode gain --scan 17 --fmode man-antenna 9 --new-flags
script/gdp-flag --mode gain --scan 17 --fmode man-antenna --man-antenna 9 --out-fver 5
script/gdp-flag --mode bandpass --scan 18 --fmode man-chan --man-chan "[900-1200]" --new-flags
script/gdp-flag --mode bandpass --scan 18 --fmode man-chan --man-chan "[900-1200]:1, 1300:0"
script/gdp-flag --mode gain --scan 17 --fmode all-std-thrsld
script/gdp-flag --mode gain --scan 17 --fmode all-std-thrsld 1.5
script/gdp-flag --mode gain --scan 17 --fmode ante-std-thrsld
script/gdp-flag --mode gain --scan 17 --fmode ante-std-thrsld --alpha 1.5
script/gdp-flag --mode gain --scan 17 --fmode ante-thrsld
script/gdp-flag --mode gain --scan 17 --fmode ante-thrsld 40
script/gdp-flag --mode gain --scan 17 --fmode ante-thrsld --percent 40
script/gdp-flag --mode gain --scan 17 --fmode ks-thrsld
script/gdp-flag --mode gain --scan 17 --fmode ks-thrsld 1.5
script/gdp-flag --mode gain --scan 17 --fmode ks-thrsld --factor 1.5
script/gdp-flag --mode bandpass --scan 18 --fmode all-std-thrsld --alpha 2
script/gdp-flag --mode gain --scan 17 --fmode remove-version
script/gdp-flag --mode gain --scan 17 --fmode remove-version 3
script/gdp-flag --mode gain --scan 17 --fmode remove-version "[1-3]"
script/gdp-flag --mode gain --scan 17 --fmode remove-version "[1:]"
script/gdp-flag --mode gain --scan 17 --fmode summary
script/gdp-flag --mode gain --scan 17 --fmode summary 3
script/gdp-flag --mode gain --scan 17 --apply-flag
script/gdp-flag --mode gain --scan 17 --apply-flag 3 --output-table /path/to/output/table_fV3.g
```

Manual flag commands carry the highest previous flag version by default. Use
`--new-flags` to write only the newly requested flags. `man-chan` is valid only
for bandpass mode; requested flag versions that do not exist are reported as
terminal `ERROR:` messages and the command exits without a Python traceback.
`--apply-flag` copies the input CASA table and writes a selected GDP flag
version into the copied table's `FLAG` column, using `rundir/gaintable/` by
default if `--output-table` is not supplied.
Manual antenna/channel values can include `:STOKES`, for example `1:0`,
`[11-14]:1`, or `23` for all Stokes.
`all-std-thrsld` computes per-Stokes Real-1 and Imag standard deviations from
all selected antennas together, then flags points outside `alpha * R` using a
zero-centered normalized RE/IM distance. `ante-std-thrsld` uses the same rule,
but calculates the standard deviations and `R` separately for each antenna and
Stokes. If alpha is omitted, it is `1`; terminal and task logs report the
percentage of data flagged.
`ante-mean-thrsld` works on antenna means instead of individual points: for
each Stokes, GDP computes each antenna's mean Real-1 and mean Imag over the
selected finite unflagged samples, then computes the center and standard
deviation of those antenna means. With `N` valid antennas, GDP derives the
two-sided Gaussian cutoff where only one antenna is expected outside the range.
The full antenna/Stokes group is flagged when its Real-1 or Imag antenna mean
lies outside `threshold * gamma * std_of_antenna_means`. If the threshold is
omitted, it is `1`. Fewer than eight valid antennas is treated as insufficient
for this fmode.
`ante-thrsld` promotes partially flagged antennas to fully flagged antennas:
in bandpass mode, GDP compares each antenna's unflagged `(Stokes, channel)`
availability against the maximum unflagged `(Stokes, channel)` count seen for
any antenna; in gain mode it uses `(Stokes, time)` availability instead. If at
least the requested percent of that reference availability is missing for an
antenna, the whole antenna is flagged. The default percent threshold is `70`.
`ks-thrsld` calculates per-antenna, per-Stokes fitted-normal KS statistics for
Real-1 and Imag samples. For each component, GDP generates 128 Gaussian-pair
realizations with the same sample size and flags the antenna/Stokes group if
the measured KS is greater than `factor` times the mean Gaussian KS. The
default factor is `1`.
Flagged data products and plots append `_fV<version>` before the file
extension, for example `gdp-stats-gain-scan17_fV1.npz` and
`gdp-plot-colormap-gain-scan17_fV1.png`.

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
script/gdp-plot --mode gain --scan 17 -pmode reim --antenna "[0-29]"
script/gdp-plot --mode bandpass --scan 18 -pmode reim -pchans "[800-3000]" --antenna "[0-29]"
```

Plot selected antennas as AntStat-style gain-time plots with Stokes side by side:

```bash
script/gdp-plot --mode gain --scan 17 -pmode antenna --antenna "[0-29]"
script/gdp-plot --mode bandpass --scan 18 -pmode antenna -pchans "[800-3000]" --antenna "[0-29]"
```

Read gain-table integration time and bandpass-table channel/band widths:

```bash
script/gdp-util --mode gain --integration-time
script/gdp-util --mode bandpass --channelwidth --bandwidth
script/gdp-util --mode bandpass --chaninfo
```

Width and frequency values are printed in kHz or MHz as appropriate. Integration
time is printed as `integration-time_sec`; `--timeinfo` also prints `NTime`,
`delta-T_sec`, and start/end times in IST and GMT. Channel information requires
`--mode bandpass`; time information requires `--mode gain`.

Create a version archive, commit, and push:

```bash
script/gdp-util --git-push -m "Describe the change"
```

Run a plan:

```bash
script/gdp-plan-run pipelines/sample_stats.plan --dry-run
```

For the full recommended order, open `doc/gdp-step-by-step.html`.
