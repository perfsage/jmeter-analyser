(function () {
  "use strict";

  var DISMISS_KEY = "perfsage_topmate_nudge_dismissed_until";
  var VIEWED_KEY = "perfsage_reports_viewed_count";
  var DISMISS_DAYS = 30;

  function isDismissed() {
    var until = localStorage.getItem(DISMISS_KEY);
    if (!until) return false;
    return Date.now() < parseInt(until, 10);
  }

  function dismissNudge() {
    var until = Date.now() + DISMISS_DAYS * 24 * 60 * 60 * 1000;
    localStorage.setItem(DISMISS_KEY, String(until));
    var el = document.getElementById("topmate-nudge");
    if (el) el.style.display = "none";
  }

  function maybeShowInlineNudge() {
    var el = document.getElementById("topmate-nudge");
    if (!el || el.getAttribute("data-report-ready") !== "true") return;
    if (isDismissed()) return;

    var count = parseInt(localStorage.getItem(VIEWED_KEY) || "0", 10);
    count += 1;
    localStorage.setItem(VIEWED_KEY, String(count));

    if (count === 1) {
      el.style.display = "flex";
    }
  }

  function showExportToast() {
    if (isDismissed()) return;
    var root = document.getElementById("toast-root");
    if (!root) return;

    var toast = document.createElement("div");
    toast.className = "toast";
    toast.innerHTML =
      "&#10003; Report exported &middot; Need help with perf testing? " +
      '<a href="https://topmate.io/abajpai/" target="_blank" rel="noopener">Book a session &rarr;</a>';
    root.appendChild(toast);

    setTimeout(function () {
      toast.classList.add("toast-fade");
      setTimeout(function () {
        if (toast.parentNode) toast.parentNode.removeChild(toast);
      }, 400);
    }, 8000);
  }

  function initCopyButton() {
    document.addEventListener("click", function (e) {
      var btn = e.target.closest("#ai-copy-btn");
      if (!btn) return;
      var raw = btn.getAttribute("data-ai-raw") || "";
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(raw).then(function () {
          btn.textContent = "Copied!";
          setTimeout(function () {
            btn.textContent = "Copy markdown";
          }, 2000);
        });
      }
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    maybeShowInlineNudge();
    initCopyButton();

    var dismissBtn = document.getElementById("nudge-dismiss");
    if (dismissBtn) {
      dismissBtn.addEventListener("click", dismissNudge);
    }

    document.querySelectorAll("[data-export-link]").forEach(function (link) {
      link.addEventListener("click", showExportToast);
    });
  });
})();
