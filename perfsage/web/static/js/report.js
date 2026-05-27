(function () {
  "use strict";

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
