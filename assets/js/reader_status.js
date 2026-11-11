(function () {
  "use strict";

  const symbol = document.querySelector("[data-reader-status]");
  if (!symbol) return;

  const labels = new Map([
    ["ready", "Lesegerät einsatzbereit"],
    ["unavailable", "Lesegerät nicht verbunden oder nicht erreichbar"],
    ["error", "Lesegerät erkannt, aber nicht einsatzbereit"]
  ]);
  const interval = 5000;
  let permission = null;
  let connected = false;
  let pending = false;
  let timer = null;

  function display(state, label = labels.get(state)) {
    symbol.dataset.state = state;
    symbol.setAttribute("aria-label", label);
    symbol.title = label;
  }

  function cancelTimer() {
    clearTimeout(timer);
    timer = null;
  }

  async function poll(onClick = false) {
    if (document.hidden || pending) return;
    cancelTimer();
    if (!onClick && permission?.state !== "granted" && !connected) {
      const label = permission?.state === "denied"
        ? "Lesegerät nicht erreichbar. Lokalen Zugriff in den Chrome-Website-Einstellungen erlauben."
        : "Lesegerät prüfen und lokalen Zugriff erlauben";
      display("unavailable", label);
      return;
    }

    pending = true;
    const started = performance.now();
    try {
      const response = await fetch("http://127.0.0.1:8765/m2-reader-health", {
        credentials: "omit",
        cache: "no-store",
        redirect: "error",
        targetAddressSpace: "loopback",
        signal: AbortSignal.timeout(1500)
      });
      if (!response.ok) throw Error("Reader status unavailable");
      const result = await response.json();
      if (result?.contract_version !== "mosa_m2_reader_health_v1" || !labels.has(result.state)) {
        throw Error("Invalid reader status response");
      }
      if (permission?.state === "denied") return;
      connected = true;
      if (!document.hidden) display(result.state);
      symbol.dataset.readyMs ??= String(Math.round(performance.now()));
    } catch {
      if (!document.hidden) display("unavailable");
    } finally {
      pending = false;
      if (!document.hidden && (connected || permission?.state === "granted")) {
        timer = setTimeout(poll, Math.max(0, interval - (performance.now() - started)));
      }
    }
  }

  symbol.addEventListener("click", () => poll(true));
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      cancelTimer();
      display("unavailable");
    } else {
      poll();
    }
  });

  (async () => {
    try {
      permission = await navigator.permissions.query({name: "loopback-network"});
      permission.addEventListener("change", () => {
        if (permission.state !== "granted") {
          connected = false;
          display("unavailable");
        }
        poll();
      });
    } catch {
      // Browsers without granular permission queries can connect on click.
    }
    poll();
  })();
}());
