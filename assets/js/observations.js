(function () {
  "use strict";
  const root = document.querySelector("[data-observation-view]");
  if (!root) return;
  const summary = root.querySelector("[data-observation-summary]");
  const body = root.querySelector("[data-observation-rows]");
  const region = root.querySelector("[data-observation-region]");
  const button = root.querySelector("[data-observation-refresh]");
  const format = globalThis.MosaMarket;
  const interval = 120000;
  let timer = null, controller = null, busy = false, halted = false, pending = false, generation = 0;
  let saved = null, savedAt = 0;
  const labels = {missing: "Keine Observation", stored: "Gespeichert", stale: "Veraltet"};
  function cell(row, label, value) {
    const node = document.createElement("td");
    node.dataset.label = label; node.textContent = value; row.append(node); return node;
  }
  function render(data, elapsed = 0) {
    if (data.status !== "ok" || !Array.isArray(data.items) || data.items.length > 10 ||
        !Number.isInteger(data.stale_seconds) || data.stale_seconds < 60) throw Error("payload");
    const fragment = document.createDocumentFragment(), seen = new Set();
    for (const item of data.items) {
      if (!["name", "isin", "source", "venue"].every(k => typeof item[k] === "string") ||
          !/^[A-Z]{2}[A-Z0-9]{9}[0-9]$/.test(item.isin) || seen.has(item.isin) || !(item.status in labels)) throw Error("item");
      seen.add(item.isin);
      const row = document.createElement("tr");
      cell(row, "Aktie", item.name);
      let status = item.status;
      if (status === "missing") {
        for (const label of ["Kurs", "Währung / Einheit", "Quelle / Handelsplatz", "Marktzeitpunkt", "Erfasst", "Datenalter", "Observation-ID"])
          cell(row, label, label === "Quelle / Handelsplatz" ? item.source + " · " + item.venue : "—");
      } else {
        if (typeof item.currency !== "string" || typeof item.unit !== "string" || typeof item.unit_version !== "string" ||
            typeof item.observation_id !== "string" || !/^[1-9][0-9]*$/.test(item.observation_id) ||
            !Number.isSafeInteger(item.age_seconds) || item.age_seconds < 0) throw Error("binding");
        const age = item.age_seconds + Math.max(0, Math.floor(elapsed / 1000));
        status = age > data.stale_seconds ? "stale" : status;
        const price = cell(row, "Kurs", format.decimal(item.price)); price.className = "market-price";
        cell(row, "Währung / Einheit", item.currency + " · " + item.unit + " (v" + item.unit_version + ")");
        cell(row, "Quelle / Handelsplatz", item.source + " · " + item.venue);
        cell(row, "Marktzeitpunkt", format.time(item.market_at));
        cell(row, "Erfasst", format.time(item.observed_at));
        cell(row, "Datenalter", age < 60 ? age + " s" : age < 3600 ? Math.floor(age / 60) + " min" : age < 86400 ? Math.floor(age / 3600) + " h" : Math.floor(age / 86400) + " Tage");
        cell(row, "Observation-ID", item.observation_id);
        row.dataset.observationId = item.observation_id;
      }
      cell(row, "Datenstatus", labels[status]); row.dataset.status = status; fragment.append(row);
    }
    body.replaceChildren(fragment);
  }
  function ageSaved() { if (saved) render(saved, performance.now() - savedAt); }
  function schedule() {
    clearTimeout(timer);
    if (!document.hidden && !halted) timer = setTimeout(() => refresh(), interval);
  }
  async function refresh(manual = false) {
    if (document.hidden || busy || (halted && !manual)) return;
    const current = document.querySelector("[data-market-view]");
    if (current && current.dataset.dataSuccess === undefined) { timer = setTimeout(() => refresh(manual), 50); return; }
    if (manual) halted = false;
    clearTimeout(timer); busy = true; pending = false;
    const token = generation; controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);
    region.setAttribute("aria-busy", "true"); button.disabled = true;
    try {
      const response = await fetch("api/market.php?view=observations", {
        method: "GET", credentials: "same-origin", cache: "no-store",
        signal: controller.signal, headers: {Accept: "application/json"}
      });
      if (!response.ok) throw Error("response");
      const data = await response.json();
      if (token !== generation || document.hidden) return;
      render(data); saved = data; savedAt = performance.now();
      summary.textContent = "Gespeicherte Observations · Anzeige alle 120 Sekunden";
    } catch (error) {
      if (token === generation && !document.hidden) {
        halted = true; ageSaved();
        summary.textContent = saved ? "Aktualisierung fehlgeschlagen · bisheriger Datenstand bleibt erhalten. Manuell aktualisieren."
          : "Observations nicht verfügbar. Manuell aktualisieren.";
      }
    } finally {
      clearTimeout(timeout); busy = false; controller = null;
      region.setAttribute("aria-busy", "false"); button.disabled = false;
      if (pending && !document.hidden && !halted) { pending = false; refresh(); }
      else schedule();
    }
  }
  document.addEventListener("visibilitychange", () => {
    clearTimeout(timer); ageSaved();
    if (document.hidden) { generation++; if (controller) controller.abort(); }
    else if (!halted) { if (busy) pending = true; else refresh(); }
  });
  button.addEventListener("click", () => refresh(true));
  if (!document.hidden) refresh();
}());
