(function () {
  "use strict";

  const symbol = document.querySelector("[data-nova-status]");
  if (!symbol || symbol.dataset.monitoring) return;
  symbol.dataset.monitoring = "true";

  const labels = new Map([
    ["running", "NOVA arbeitet"],
    ["idle", "NOVA bereit"],
    ["unavailable", "NOVA-Status nicht verfügbar"]
  ]);
  const interval = 5000;
  let timer = null;
  let pending = false;

  function display(state) {
    symbol.dataset.state = state;
    symbol.setAttribute("aria-label", labels.get(state));
    symbol.title = labels.get(state);
  }

  function cancelTimer() {
    clearTimeout(timer);
    timer = null;
  }

  async function poll() {
    if (document.hidden || pending) return;
    cancelTimer();
    pending = true;
    const started = performance.now();

    try {
      const response = await fetch("api/nova_status.php", {
        credentials: "same-origin",
        cache: "no-store",
        headers: {Accept: "application/json"},
        signal: AbortSignal.timeout(4500)
      });
      if (!response.ok) throw Error("NOVA status unavailable");
      const result = await response.json();
      if (result?.contract_version !== "mosa2_nova_status_v1" || !labels.has(result.state)) {
        throw Error("Invalid NOVA status response");
      }
      display(result.state);
      symbol.dataset.readyMs ??= String(Math.round(performance.now()));
    } catch {
      display("unavailable");
    } finally {
      pending = false;
      if (!document.hidden) {
        timer = setTimeout(poll, Math.max(0, interval - (performance.now() - started)));
      }
    }
  }

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) cancelTimer();
    else poll();
  });
  poll();
}());
