(() => {
  "use strict";

  const plotLinks = Array.from(document.querySelectorAll('a[href^="sample_plots/"]'));
  if (!plotLinks.length) return;

  let currentIndex = 0;
  const panel = document.createElement("aside");
  panel.className = "plot-viewer";
  panel.hidden = true;
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", "Sample plot viewer");
  panel.innerHTML = `
    <div class="plot-viewer__header">
      <strong class="plot-viewer__title">Sample plot</strong>
      <div class="plot-viewer__controls">
        <button type="button" class="plot-viewer__button" data-plot-action="previous" aria-label="Previous sample plot">Previous</button>
        <button type="button" class="plot-viewer__button" data-plot-action="next" aria-label="Next sample plot">Next</button>
        <button type="button" class="plot-viewer__button" data-plot-action="close" aria-label="Close sample plot viewer">Close</button>
      </div>
    </div>
    <a class="plot-viewer__image-link" target="_blank" rel="noopener">
      <img class="plot-viewer__image" alt="Selected GDP sample plot">
    </a>
  `;
  document.body.append(panel);

  const title = panel.querySelector(".plot-viewer__title");
  const image = panel.querySelector(".plot-viewer__image");
  const imageLink = panel.querySelector(".plot-viewer__image-link");

  function show(index) {
    currentIndex = (index + plotLinks.length) % plotLinks.length;
    const link = plotLinks[currentIndex];
    const text = link.textContent.trim() || "Sample plot";
    title.textContent = text;
    const imageUrl = new URL(link.href);
    // Sample filenames are stable; force the viewer to refresh a regenerated image.
    imageUrl.searchParams.set("viewer", String(Date.now()));
    image.src = imageUrl.href;
    image.alt = text;
    imageLink.href = link.href;
    panel.hidden = false;
  }

  function close() {
    panel.hidden = true;
    image.removeAttribute("src");
  }

  plotLinks.forEach((link, index) => {
    link.addEventListener("click", (event) => {
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      show(index);
    });
  });

  panel.addEventListener("click", (event) => {
    const action = event.target.closest("[data-plot-action]")?.dataset.plotAction;
    if (action === "close") close();
    if (action === "previous") show(currentIndex - 1);
    if (action === "next") show(currentIndex + 1);
  });

  document.addEventListener("keydown", (event) => {
    if (panel.hidden) return;
    if (event.key === "Escape") close();
    if (event.key === "ArrowLeft") show(currentIndex - 1);
    if (event.key === "ArrowRight") show(currentIndex + 1);
  });
})();
