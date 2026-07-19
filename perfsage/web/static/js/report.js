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
      if (!Object.prototype.hasOwnProperty.call(figs, divId)) continue;
      var figJson = figs[divId];
      var el = document.getElementById(divId);
      if (!figJson || !el) continue;
      var markLoaded = function (gd) {
        (gd || el).classList.add("chart-loaded");
      };
      try {
        var plotPromise = Plotly.newPlot(el, figJson.data, figJson.layout, {
          responsive: true,
          displayModeBar: true,
        });
        if (plotPromise && typeof plotPromise.then === "function") {
          plotPromise.then(markLoaded).catch(function (err) {
            console.error("PerfSage: Plotly.newPlot failed for", divId, err);
            markLoaded(el);
          });
        } else {
          markLoaded(el);
        }
      } catch (err) {
        console.error("PerfSage: Plotly.newPlot failed for", divId, err);
        markLoaded(el);
      }
    }
  };

  document.addEventListener("DOMContentLoaded", function () {
    // Initial report page figures — must run after deferred report.js loads.
    // Do not call mountFigures from an inline script in the content block while
    // report.js uses defer; that race leaves charts at opacity:0 forever.
    window.PerfSageReport.mountFigures(document.getElementById("figures-data"));

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
        if (!section) return;
        var collapsed = section.classList.toggle("collapsed");
        btn.setAttribute("aria-expanded", collapsed ? "false" : "true");
      });
    });
  });
})();
