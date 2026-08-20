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
  const page = (window.location.pathname.split("/").pop() || "index.html").toLowerCase();
  const isMain = page === "index.html" || page === "readme.html";
  const version = "0.1.17";
  const headerTitle = document.querySelector("header h1");
  if (!isMain && headerTitle && !headerTitle.querySelector(".documentation-version")) {
    const title = headerTitle.textContent.trim();
    headerTitle.textContent = "";
    const titleText = document.createElement("span");
    titleText.textContent = title;
    const versionText = document.createElement("span");
    versionText.className = "documentation-version";
    versionText.textContent = `GDP Version: ${version}`;
    headerTitle.classList.add("documentation-title");
    headerTitle.append(titleText, versionText);
  }
  const current = main.querySelector("section.sample-plots");
  if (isMain) {
    if (current) {
      current.outerHTML = samplePlots;
    } else {
      main.insertAdjacentHTML("beforeend", samplePlots);
    }
  } else if (current) {
    current.remove();
  }

  const introduction = `
    <section class="gdp-introduction">
      <h2>GDP (Gain Diagnostic Product)</h2>
      <p>GDP (Gain Diagnostic Product) is a command-line toolkit for reading CASA gain and bandpass calibration tables, creating portable diagnostic products, identifying problematic data, and writing reproducible plots and flag sidecars. It keeps CASA table access, numerical products, flags, models, and plots connected through a configured runtime directory.</p>
      <p>A typical workflow saves a gains NPZ with <code>gdp-stats</code>, optionally models it with <code>gdp-model</code>, creates or applies flags with <code>gdp-flag</code> and <code>gdp-apply</code>, then produces diagnostics with <code>gdp-plot</code>. Plans make the same sequence repeatable, while the product pages describe every saved format.</p>
    </section>`;
  const components = `
    <section class="doc-tree" aria-labelledby="components">
      <h2 id="components">Components</h2>
      <ul>
        <li><a href="index.html">Main documentation</a></li>
        <li><a href="gdp-setup.html">gdp-setup</a>: configure the runtime and input tables.</li>
        <li><a href="gdp-util.html">gdp-util</a>: inspect CASA table metadata and manage releases.</li>
        <li><a href="gdp-stats.html">gdp-stats</a>: write gains, statistics, correlation, and KS products.</li>
        <li><a href="gdp-model.html">gdp-model</a>: add model samples to saved gains products.</li>
        <li><a href="gdp-flag.html">gdp-flag</a>: create versioned GDP flag sidecars.</li>
        <li><a href="gdp-apply.html">gdp-apply</a>: write GDP samples and flags into a copied CASA table.</li>
        <li><a href="gdp-plot.html">gdp-plot</a>: create diagnostic plots.</li>
        <li><a href="gdp-show.html">gdp-show</a>: browse existing plots.</li>
        <li><a href="gdp-plan-run.html">gdp-plan-run</a>: run reproducible workflow plans.</li>
        <li><a href="gdp-step-by-step.html">Step-by-step guide</a></li>
      </ul>
    </section>`;
  const tree = main.querySelector("section.doc-tree");
  if (tree) {
    tree.insertAdjacentHTML("beforebegin", introduction);
    tree.outerHTML = components;
  } else {
    main.insertAdjacentHTML("afterbegin", introduction + components);
  }

  const mainOnlyHeadings = new Set(["Product Formats", "Runtime Layout", "Quick Start", "Sample Plots", "Step-by-Step Guide"]);
  if (!isMain) {
    for (const section of main.querySelectorAll(":scope > section")) {
      const heading = section.querySelector(":scope > h2");
      if (heading && mainOnlyHeadings.has(heading.textContent.trim())) section.remove();
    }
  }

  const commandDescriptions = {
    "gdp-setup.html": "Configure the active runtime directory and remembered gain/bandpass CASA tables. It also provides cautious cleanup of generated runtime outputs.",
    "gdp-util.html": "Inspect CASA calibration metadata, channel/time summaries, setup configuration, and the GDP release version.",
    "gdp-stats.html": "Read CASA calibration data and write gains, statistics, KS, self-correlation, and cross-correlation products. Named CASA/model data columns keep derived analysis reproducible.",
    "gdp-model.html": "Fit per-antenna, Stokes, and component gain or bandpass models into the saved gains NPZ model column.",
    "gdp-flag.html": "Create versioned GDP flag sidecars using manual selections and statistical or GPR-based flagging modes.",
    "gdp-apply.html": "Copy a CASA calibration table, replace selected samples from a GDP gains NPZ, and optionally apply a GDP flag sidecar.",
    "gdp-plot.html": "Turn GDP data products into gain, bandpass, statistics, correlation, and diagnostic plots.",
    "gdp-show.html": "Open a filterable browser gallery of plots that already exist in the runtime directory, without recalculation.",
    "gdp-plan-run.html": "Execute ordered GDP command intents from a declarative plan, including variables, defaults, iterations, and cairn selection."
  };
  const generatedOptions = {
    "gdp-model.html": [
      ["--mode, --mod", "Choose gain or bandpass input. Default: gain."],
      ["--scan, --antenna, --stokes, --complex", "Restrict the antenna, polarization, and real/imaginary series to model."],
      ["--mmode", "Choose polynomial, harmonic, poly-harmonic, Gauss-Hermite, or GPR local-kernel fitting."],
      ["--use-flags, --flagversion", "Exclude samples from the selected/highest flag sidecar while fitting."],
      ["--output-gains-npz", "Write a modelled copy instead of updating the matching saved gains NPZ."],
      ["--dry-run, --estimate, --parallel, --output-csv", "Preview, estimate, parallelize, or export model samples."]
    ],
    "gdp-apply.html": [
      ["--mode, --scan, --antenna, --chans", "Select CASA gain/bandpass samples to replace. Channels are bandpass-only."],
      ["--datacolumn {casa,model}", "Use CASA samples by default or model samples written by gdp-model."],
      ["--use-flags, --flagver", "Apply the selected/highest flag sidecar; absent versions produce an error and leave flags unchanged."],
      ["--output-casa-table PATH", "Required destination for the copied CASA table."],
      ["--force", "Overwrite an existing output CASA table without the confirmation prompt."]
    ]
  };
  const description = commandDescriptions[page];
  if (description) {
    for (const section of main.querySelectorAll(":scope > section")) {
      const heading = section.querySelector(":scope > h2");
      if (!heading) continue;
      if (heading.textContent.trim() === "Purpose" || heading.textContent.trim() === "Behavior") section.remove();
      if (heading.textContent.trim() === "Workflow" && page === "gdp-model.html") heading.textContent = "Usage";
    }

    const commandName = page.replace(".html", "");
    const overview = `<section class="command-overview"><h2>${commandName}</h2><p>${description}</p></section>`;
    main.querySelector("section.doc-tree")?.insertAdjacentHTML("afterend", overview);
    let optionsHeading = [...main.querySelectorAll("h2")].find((heading) => heading.textContent.trim() === "Options");
    if (!optionsHeading && generatedOptions[page]) {
      const rows = generatedOptions[page].map(([option, text]) => `<tr><td><code>${option}</code></td><td>${text}</td></tr>`).join("");
      const generated = `<section class="options-section"><h2>Options</h2><table><tr><th>Option</th><th>Description</th></tr>${rows}</table></section>`;
      const usageSection = [...main.querySelectorAll(":scope > section")].find((section) => section.querySelector(":scope > h2")?.textContent.trim() === "Usage");
      (usageSection || main.querySelector("section.command-overview"))?.insertAdjacentHTML("afterend", generated);
      optionsHeading = [...main.querySelectorAll("h2")].find((heading) => heading.textContent.trim() === "Options");
    }
    if (optionsHeading) optionsHeading.closest("section")?.classList.add("options-section");
    const modelModesSection = page === "gdp-model.html"
      ? [...main.querySelectorAll(":scope > section")].find((section) => section.querySelector(":scope > h2")?.textContent.trim() === "Model Modes")
      : null;
    if (modelModesSection) {
      modelModesSection.classList.add("options-section");
      optionsHeading?.closest("section")?.insertAdjacentElement("afterend", modelModesSection);
    }
    const productLinks = {
      "gdp-setup.html": ["<a href=\"index.html#runtime-layout\">Runtime directory layout</a>"],
      "gdp-util.html": ["<a href=\"gdp-product-gains.html\">Gains NPZ</a>"],
      "gdp-stats.html": ["<a href=\"gdp-product-gains.html\">Gains NPZ</a>", "<a href=\"gdp-product-stats.html\">Statistics NPZ</a>", "<a href=\"gdp-product-ks.html\">KS NPZ</a>", "<a href=\"gdp-product-self-corr.html\">Self-correlation NPZ</a>", "<a href=\"gdp-product-cross-corr.html\">Cross-correlation NPZ</a>"],
      "gdp-model.html": ["<a href=\"gdp-product-gains.html\">Gains NPZ with model data column</a>"],
      "gdp-flag.html": ["<a href=\"gdp-product-flags.html\">Flag sidecar (FLG)</a>"],
      "gdp-apply.html": ["<a href=\"gdp-product-gains.html\">Gains NPZ</a>", "<a href=\"gdp-product-flags.html\">Flag sidecar (FLG)</a>", "Copied CASA calibration table"],
      "gdp-show.html": ["<a href=\"gdp-plot.html\">GDP plot files</a>"],
      "gdp-plan-run.html": ["<a href=\"gdp-product-gains.html\">GDP runtime products</a>", "<a href=\"index.html#runtime-layout\">Runtime directory layout</a>"]
    };
    const links = productLinks[page] || [];
    const output = page === "gdp-plot.html"
      ? `<section class="command-output command-samples"><h2>Sample Plots</h2><p>Examples are available in the <a href="index.html#sample-plots">main Sample Plots gallery</a>. Select an image there to inspect it in the documentation viewer.</p></section>`
      : `<section class="command-output"><h2>Product Formats</h2><p>${links.length ? `Relevant products: ${links.join(", ")}.` : "This command does not create a standalone numerical product."} See the <a href="index.html#product-formats">Product Formats</a> reference for layouts and naming conventions.</p></section>`;
    const optionsSection = modelModesSection || optionsHeading?.closest("section");
    const usageSection = [...main.querySelectorAll(":scope > section")].find((section) => section.querySelector(":scope > h2")?.textContent.trim() === "Usage");
    (optionsSection || usageSection || main.querySelector("section.command-overview"))?.insertAdjacentHTML("afterend", output);
  }

  if (!isMain) {
    const details = `<section class="details-links"><h2>Details</h2><a href="index.html#product-formats">Product Formats</a><a href="index.html#runtime-layout">Runtime Layout</a><a href="index.html#quick-start">Quick Start</a><a href="index.html#sample-plots">Sample Plots</a><a href="gdp-step-by-step.html">Step-by-Step Guide</a></section>`;
    main.insertAdjacentHTML("beforeend", details);
  }
  const license = `<section class="license"><h2>Licence</h2><p>GDP is developed by Prasun Dutta and Saikat Gayen at IIT (BHU), Varanasi. Appropriate citation of GDP is requested in publications, reports, and other work that uses this software.</p><p>GDP may be modified and redistributed, provided that all modifications are shared through this repository and submitted to the authors for review and incorporation.</p></section>`;
  main.insertAdjacentHTML("beforeend", license);
})();
