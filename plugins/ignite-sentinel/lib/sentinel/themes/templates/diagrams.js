(function () {
  "use strict";
  // IMP-273: render each card's Mermaid code with the vendored mermaid inlined in the page.
  // No network: the CSP refuses every connection, and mermaid needs none.
  var cards = Array.prototype.slice.call(document.querySelectorAll("[data-diagram]"));
  var lib = window.mermaid;
  if (!lib || typeof lib.render !== "function") {
    cards.forEach(function (card) {
      var code = card.querySelector(".diagram-code");
      if (code) code.open = true;
    });
    return;
  }
  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }
  var sequence = 0;
  var running = null;
  function configure() {
    lib.initialize({
      startOnLoad: false,
      securityLevel: "strict",
      theme: "base",
      fontFamily: cssVar("--font") || "sans-serif",
      themeVariables: {
        background: cssVar("--bg"),
        primaryColor: cssVar("--surface"),
        primaryTextColor: cssVar("--text"),
        primaryBorderColor: cssVar("--line"),
        secondaryColor: cssVar("--surface-2"),
        tertiaryColor: cssVar("--bg"),
        lineColor: cssVar("--text-muted"),
        textColor: cssVar("--text"),
        mainBkg: cssVar("--surface"),
        nodeBorder: cssVar("--line"),
        clusterBkg: cssVar("--surface"),
        clusterBorder: cssVar("--line"),
        titleColor: cssVar("--text"),
        edgeLabelBackground: cssVar("--bg"),
        actorBkg: cssVar("--surface"),
        actorBorder: cssVar("--line"),
        actorTextColor: cssVar("--text"),
        actorLineColor: cssVar("--text-muted"),
        signalColor: cssVar("--text"),
        signalTextColor: cssVar("--text"),
        labelBoxBkgColor: cssVar("--surface"),
        labelTextColor: cssVar("--text"),
        noteBkgColor: cssVar("--surface-2"),
        noteTextColor: cssVar("--text")
      }
    });
  }
  async function renderAll() {
    configure();
    for (var i = 0; i < cards.length; i++) {
      var card = cards[i];
      var src = card.querySelector(".mermaid-src");
      if (!src) continue;
      var out = card.querySelector(".diagram-render");
      var note = card.querySelector(".unrendered");
      try {
        sequence += 1;
        var result = await lib.render("mmd-" + sequence, src.textContent);
        out.innerHTML = result.svg;
        out.hidden = false;
        note.hidden = true;
      } catch (error) {
        out.hidden = true;
        note.hidden = false;
        note.textContent = note.getAttribute("data-error") + " " + (error && error.message ? error.message : String(error));
        var code = card.querySelector(".diagram-code");
        if (code) code.open = true;
      }
    }
  }
  function schedule() {
    running = (running || Promise.resolve()).then(renderAll);
  }
  schedule();
  // The colour-mode toggle changes the theme tokens: render again with the new ones.
  new MutationObserver(schedule).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
})();
