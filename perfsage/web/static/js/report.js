(function () {
  "use strict";

  window.PerfSageReport = window.PerfSageReport || {};

  window.PerfSageReport.mountFigures = function (jsonScriptEl) {
    if (!jsonScriptEl) return;
    var figs;
    try {
      figs = JSON.parse(jsonScriptEl.textContent);
    } catch (e) {
      console.error("PerfSage: failed to parse figures JSON", e);
      return;
    }
    for (var divId in figs) {
      var figJson = figs[divId];
      var el = document.getElementById(divId);
      if (!figJson || !el) continue;
      Plotly.newPlot(el, figJson.data, figJson.layout, {
        responsive: true,
        displayModeBar: true,
      }).then(function (gd) {
        gd.classList.add("chart-loaded");
      });
    }
  };

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".chart-tabs").forEach(function (tabs) {
      var buttons = tabs.querySelectorAll(".chart-tab-btn");
      var panels = tabs.querySelectorAll(".chart-tab-panel");
      buttons.forEach(function (btn) {
        btn.addEventListener("click", function () {
          var target = btn.getAttribute("data-tab");
          buttons.forEach(function (b) {
            b.classList.toggle("active", b === btn);
          });
          panels.forEach(function (panel) {
            panel.classList.toggle(
              "active",
              panel.getAttribute("data-panel") === target
            );
          });
          window.dispatchEvent(new Event("resize"));
        });
      });
    });

    document.querySelectorAll(".report-section-toggle").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var section = btn.closest(".report-section");
        if (section) section.classList.toggle("collapsed");
      });
    });
  });
})();
