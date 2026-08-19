(() => {
  "use strict";

  const samplePlots = `
    <section class="sample-plots" aria-labelledby="sample-plots">
      <h2 id="sample-plots">Sample Plots</h2>
      <p>All sample plots use the current gain scan 13 products. Select an image to open it in the in-page viewer.</p>
      <table>
        <tr><th>Plot Type</th><th>Sample</th><th>Command</th><th>Description</th></tr>
        <tr><td>Colormap</td><td><a href="sample_plots/gdp-plot-colormap-gain-scan13.png">colormap</a></td><td><code>script/gdp-plot --mode gain --scan 13 -pmode colormap</code></td><td>Real-1 and Imag percent colormaps for all antennas.</td></tr>
        <tr><td>Histogram</td><td><a href="sample_plots/gdp-plot-hist-gain-scan13.png">histogram</a></td><td><code>script/gdp-plot --mode gain --scan 13 -pmode hist</code></td><td>Real-1 and Imag distributions for all antennas.</td></tr>
        <tr><td>Antenna</td><td><a href="sample_plots/gdp-plot-antenna-gain-scan13-ant0.png">antenna</a></td><td><code>script/gdp-plot --mode gain --scan 13 -pmode antenna --antenna 0</code></td><td>One antenna gain time series.</td></tr>
        <tr><td>Real-Imag</td><td><a href="sample_plots/gdp-plot-reim-gain-scan13-ants0_1.png">reim</a></td><td><code>script/gdp-plot --mode gain --scan 13 -pmode reim --antenna 0 1</code></td><td>Pooled Real-1 versus Imag diagnostic.</td></tr>
        <tr><td>Statistics</td><td><a href="sample_plots/gdp-plot-stats-gain-scan13.png">stats</a></td><td><code>script/gdp-plot --mode gain --scan 13 -pmode stats</code></td><td>Mean, standard deviation, skewness, and kurtosis grid.</td></tr>
        <tr><td>KS</td><td><a href="sample_plots/gdp-plot-ks-gain-scan13.png">ks</a></td><td><code>script/gdp-plot --mode gain --scan 13 -pmode ks</code></td><td>KS D-statistic grid.</td></tr>
        <tr><td>Self-corr colormap</td><td><a href="sample_plots/gdp-plot-self-corr-colormap-gain-scan13.png">self-corr colormap</a></td><td><code>script/gdp-plot --mode gain --scan 13 -pmode self-corr-colormap</code></td><td>Normalized S2 over antenna and time difference.</td></tr>
        <tr><td>Self-corr antenna</td><td><a href="sample_plots/gdp-plot-self-corr-antenna-gain-scan13-ant0.png">self-corr antenna</a></td><td><code>script/gdp-plot --mode gain --scan 13 -pmode self-corr-antenna --antenna 0</code></td><td>Per-antenna normalized S2 curves.</td></tr>
        <tr><td>Cross-corr antenna</td><td><a href="sample_plots/gdp-plot-cross-corr-antenna-gain-scan13-ant9_13-stokes01-compimim.png">cross-corr antenna</a></td><td><code>script/gdp-plot --mode gain --scan 13 -pmode cross-corr-antenna --ant-pair 9 13 --stokes-pair 01 --cmplx-pair 'im&amp;im'</code></td><td>One saved antenna-pair cross structure function.</td></tr>
        <tr><td>Cross-corr grids</td><td><a href="sample_plots/gdp-plot-cross-corr-grid-gain-scan13-cmp-self.png">same component</a>, <a href="sample_plots/gdp-plot-cross-corr-grid-gain-scan13-cmp-cross.png">mixed component</a></td><td><code>script/gdp-plot --mode gain --scan 13 -pmode cross-corr-grid</code></td><td>All-pair correlation-time grids.</td></tr>
      </table>
    </section>`;

  const main = document.querySelector("main");
  if (!main) return;
  const current = main.querySelector("section.sample-plots");
  if (current) {
    current.outerHTML = samplePlots;
  } else {
    main.insertAdjacentHTML("beforeend", samplePlots);
  }
})();
