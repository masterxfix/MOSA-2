(function () {
  "use strict";

  var node = document.querySelector("[data-page-load-time]");
  if (!node) return;

  function show() {
    if (typeof performance.getEntriesByType !== "function") return;
    var entries = performance.getEntriesByType("navigation");
    var entry = entries && entries[0];
    var duration = entry && entry.duration;
    if (!Number.isFinite(duration) || duration < 0) return;

    var milliseconds = Math.round(duration);
    var value = milliseconds >= 1000
      ? (milliseconds / 1000).toLocaleString("de-DE", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      }) + " s"
      : milliseconds + " ms";

    node.textContent = value;
    node.setAttribute("aria-label", "Seitenladezeit " + value);
    node.title = "Seitenladezeit: " + value;
  }

  window.addEventListener("load", function () {
    // Navigation duration includes loadEventEnd, available after this event returns.
    window.setTimeout(show, 0);
  }, { once: true });
}());
