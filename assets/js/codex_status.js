(function () {
  "use strict";
  var dot = document.querySelector("[data-codex-status]");
  if (!dot) return;

  var timer = null;
  var pending = false;
  var stopped = false;
  var interval = 5000;

  function display(state) {
    dot.dataset.state = state;
    var label = state === "running" ? "Codex arbeitet" :
      state === "idle" ? "Kein aktiver Codex-Auftrag" : "Codex-Status unbekannt";
    dot.setAttribute("aria-label", label);
    dot.title = label;
  }

  function schedule() {
    if (stopped || document.hidden) return;
    if (timer !== null) clearTimeout(timer);
    timer = setTimeout(poll, interval);
  }

  async function poll() {
    if (stopped || pending || document.hidden) return;
    if (timer !== null) clearTimeout(timer);
    timer = null;
    pending = true;
    try {
      var response = await fetch("api/codex_status.php", {
        credentials: "same-origin", cache: "no-store", headers: { "Accept": "application/json" }
      });
      if (response.status === 401 || response.status === 403) {
        stopped = true;
        display("unavailable");
        return;
      }
      if (!response.ok) throw new Error("unavailable");
      var data = await response.json();
      if (!data || data.contract_version !== "mosa2_codex_status_v1" ||
          !["running", "idle", "unavailable"].includes(data.state)) {
        throw new Error("invalid_status");
      }
      display(data.state);
      if (!dot.dataset.readyMs) dot.dataset.readyMs = String(Math.round(performance.now()));
    } catch (_) {
      display("unavailable");
    } finally {
      pending = false;
      schedule();
    }
  }

  document.addEventListener("visibilitychange", function () {
    if (document.hidden) {
      if (timer !== null) clearTimeout(timer);
      timer = null;
    } else poll();
  });
  window.addEventListener("focus", poll);
  display("unavailable");
  poll();
}());
