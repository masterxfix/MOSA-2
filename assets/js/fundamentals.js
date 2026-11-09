(function () {
  "use strict";

  const root = document.querySelector("[data-fundamentals-view]");
  if (!root) return;
  const state = { items: [], selected: null, jobs: new Map() };
  const elements = {
    assets: root.querySelector("[data-fundamental-assets]"),
    detail: root.querySelector("[data-fundamental-detail]"),
    status: root.querySelector("[data-fundamental-status]"),
    summary: root.querySelector("[data-fundamental-summary]"),
    total: root.querySelector("[data-fundamental-total]"),
    history: root.querySelector("[data-history-form]"),
    historyStatus: root.querySelector("[data-history-status]")
  };

  function text(value) {
    return value === null || value === undefined || value === "" ? "—" : String(value);
  }
  function period(row) {
    if (row.period_type === "fy" && row.fiscal_year) return "FY" + row.fiscal_year;
    if (row.period_type === "fq" && row.fiscal_year && row.fiscal_quarter) return "Q" + row.fiscal_quarter + " " + row.fiscal_year;
    if (row.period_type === "ytd" && row.period_start && row.period_end) return "YTD " + row.period_start + " – " + row.period_end;
    if (row.period_type === "snapshot" && /^\d{4}-\d{2}-\d{2}/.test(row.as_of_at || "")) {
      return "Stichtag " + row.as_of_at.slice(0, 10).split("-").reverse().join(".");
    }
    if (row.period_start && row.period_end) return row.period_start + " – " + row.period_end;
    return text(row.period_type);
  }
  function date(value) {
    if (typeof value !== "string") return "—";
    return value.replace("T", " · ").replace("Z", " UTC");
  }
  function cell(row, label, value, className) {
    const node = document.createElement("td");
    node.dataset.label = label;
    node.textContent = text(value);
    if (className) node.className = className;
    row.append(node);
    return node;
  }
  function table(title, headings, rows, className) {
    const wrap = document.createElement("div");
    wrap.className = "fundamental-table-wrap";
    const heading = document.createElement("h3");
    heading.textContent = title;
    wrap.append(heading);
    const tableNode = document.createElement("table");
    tableNode.className = "fundamental-table " + className;
    const caption = document.createElement("caption");
    caption.className = "visually-hidden";
    caption.textContent = title;
    tableNode.append(caption);
    const thead = document.createElement("thead");
    const headerRow = document.createElement("tr");
    headings.forEach((headingText) => {
      const th = document.createElement("th");
      th.scope = "col";
      th.textContent = headingText;
      headerRow.append(th);
    });
    thead.append(headerRow);tableNode.append(thead);
    const tbody = document.createElement("tbody");
    rows.forEach((values) => {
      const row = document.createElement("tr");
      values.forEach((value, index) => cell(row, headings[index], value, index === 1 ? "fundamental-value" : ""));
      tbody.append(row);
    });
    tableNode.append(tbody);wrap.append(tableNode);return wrap;
  }
  function comparison(item) {
    const facts = item.observations.filter((row) => row.period_type === "fy" && row.fiscal_year);
    const years = [...new Set(facts.map((row) => row.fiscal_year))].sort((a, b) => Number(b) - Number(a));
    if (!years.length) return null;
    const metrics = [...new Map(facts.map((row) => [row.metric_key, row])).values()];
    const rows = metrics.map((metric) => {
      const values = years.map((year) => {
        const match = facts.find((row) => row.metric_key === metric.metric_key && row.fiscal_year === year);
        return match ? text(match.value) + " " + match.unit_key + (match.current ? " · Current" : "") : "—";
      });
      return [metric.metric_name, ...values, [...new Set(facts.filter((row) => row.metric_key === metric.metric_key).map((row) => row.source))].join(" · ")];
    });
    return table("Jahresvergleich", ["Kennzahl", ...years.map((year) => "FY" + year), "Quelle"], rows, "comparison-table");
  }
  function details(item) {
    const rows = item.observations.map((row) => [row.metric_name, period(row) + (row.current ? " · Current" : ""), row.value, row.unit_key, row.source]);
    return table("Gespeicherte Kennzahlen", ["Kennzahl", "Zeitraum / Stichtag", "Wert", "Einheit", "Quelle"], rows, "observation-table");
  }
  function select(isin) {
    const item = state.items.find((candidate) => candidate.isin === isin);
    if (!item) return;
    state.selected = item.isin;
    showJob(isin);
    elements.assets.querySelectorAll("button").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.isin === item.isin)));
    const fragment = document.createDocumentFragment();
    const header = document.createElement("div");header.className = "fundamental-detail-heading";
    const title = document.createElement("h2");title.textContent = item.name;header.append(title);
    const identity = document.createElement("p");identity.className = "fundamental-identity";identity.textContent = "ISIN " + item.isin + " · " + item.observations.length + " Observations · " + item.current.length + " Current";header.append(identity);
    const timing = document.createElement("p");timing.className = "fundamental-capture";const latest = item.observations.map((row) => row.captured_at).sort().at(-1);timing.textContent = "Erfasst bis " + date(latest) + ". Gespeicherter Datenbankstand, kein Live-Abruf.";header.append(timing);fragment.append(header);
    const scope = elements.history ? historyScope() : null;
    const visible = scope ? item.observations.filter((row) => {
      const year = Number(row.fiscal_year || (row.as_of_at || "").slice(0, 4));
      return year >= scope.start && year <= scope.end &&
        (scope.kind === "both" || row.period_type === scope.kind || row.period_type === "snapshot");
    }) : item.observations;
    const view = { ...item, observations: visible };
    const compare = comparison(view);if (compare) fragment.append(compare);
    if (visible.length) fragment.append(details(view));
    else {
      const empty = document.createElement("p");
      empty.textContent = "Für diesen Zeitraum sind keine Kennzahlen gespeichert.";
      fragment.append(empty);
    }
    const sourceNote = document.createElement("p");sourceNote.className = "fundamental-reference-note";sourceNote.textContent = "Referenzen: Jede Zeile ist mit Quelle, Fetch-ID, Feldpfad und Evidence-Hash im Read-only-API-Vertrag verknüpft.";fragment.append(sourceNote);
    elements.detail.replaceChildren(fragment);
  }
  function render(data) {
    if (!data || data.status !== "ok" || !Array.isArray(data.items) || !data.items.length || !data.totals) throw Error("payload");
    state.items = data.items;
    elements.assets.replaceChildren();
    data.items.forEach((item, index) => {
      if (typeof item.name !== "string" || typeof item.isin !== "string" || !Array.isArray(item.observations) || !Array.isArray(item.current)) throw Error("asset");
      const button = document.createElement("button");button.type = "button";button.className = "fundamental-asset-button";button.dataset.isin = item.isin;button.setAttribute("aria-pressed", "false");
      const number = document.createElement("span");number.className = "fundamental-asset-number";number.textContent = String(index + 1).padStart(2, "0");
      const name = document.createElement("span");name.className = "fundamental-asset-name";name.textContent = item.name;
      const arrow = document.createElement("span");arrow.className = "fundamental-asset-arrow";arrow.textContent = "↗";
      button.append(number,name,arrow);button.addEventListener("click", () => select(item.isin));elements.assets.append(button);
    });
    elements.total.textContent = String(data.totals.assets).padStart(2, "0");
    elements.summary.textContent = data.totals.fundamental_observations + " Observations · " + data.totals.fundamental_current + " Current · Stand " + date(data.as_of);
    if (elements.history) elements.history.hidden = false;
    select(state.selected || data.items[0].isin);
    elements.status.textContent = "Gespeicherte Fundamentaldaten";
  }
  function historyScope() {
    const {start, end, kind} = elements.history.elements;
    return {start: Number(start.value), end: Number(end.value), kind: kind.value};
  }
  function showJob(isin) {
    if (!elements.history) return;
    const job = state.jobs.get(isin);
    elements.historyStatus.textContent = job?.message || "";
    elements.history.querySelector('button').disabled = Boolean(job?.active);
    const receipt = elements.history.querySelector("[data-history-receipt]");
    if (receipt) receipt.textContent = job?.id ? "Anfrage-ID " + job.id : "";
  }
  function jobStatus(isin, message, active, id = state.jobs.get(isin)?.id) {
    state.jobs.set(isin, {message, active, id});
    if (state.selected === isin) showJob(isin);
  }
  async function historyRequest(method, value) {
    const path = "api/fundamentals_history.php" + (method === "GET" ? "?id=" + encodeURIComponent(value) : "");
    const response = await fetch(path, {
      method, credentials: "same-origin", cache: "no-store",
      headers: {Accept: "application/json", ...(method === "POST" ? {"Content-Type": "application/json"} : {})},
      ...(method === "POST" ? {body: JSON.stringify(value)} : {})
    });
    const result = await response.json();
    if (!response.ok) throw Error(result.message || "Der Abruf konnte nicht gestartet werden.");
    return result;
  }
  async function followJob(isin, result) {
    const active = ["queued", "running"].includes(result.status);
    jobStatus(isin, result.message, active, result.id);
    if (!active) {
      if (result.inserted > 0) {
        const response = await fetch("api/fundamentals.php?isin=" + encodeURIComponent(isin), {cache: "no-store"});
        if (!response.ok) throw Error("Import bestätigt. Die aktualisierten Werte konnten noch nicht angezeigt werden.");
        const data = await response.json();
        const updated = data.items?.find((item) => item.isin === isin);
        if (!updated) throw Error("Import bestätigt. Die aktualisierten Werte konnten noch nicht angezeigt werden.");
        state.items = state.items.map((item) => item.isin === isin ? updated : item);
        if (state.selected === isin) select(isin);
      }
      return;
    }
    setTimeout(async () => {
      try { await followJob(isin, await historyRequest("GET", result.id)); }
      catch { jobStatus(isin, "Jobstatus gerade nicht verfügbar. Du kannst dieselbe Anfrage wieder öffnen.", false); }
    }, 4000);
  }
  if (elements.history) {
    const year = new Date().getFullYear();
    elements.history.elements.end.value = year;
    elements.history.elements.start.max = year;
    elements.history.elements.end.max = year;
    elements.history.addEventListener("change", () => select(state.selected));
    elements.history.addEventListener("submit", async (event) => {
      event.preventDefault();
      const isin = state.selected;
      if (!isin || state.jobs.get(isin)?.active) return;
      const scope = historyScope();
      if (scope.start > scope.end || scope.end - scope.start > 9) {
        jobStatus(isin, "Wähle einen zusammenhängenden Zeitraum von höchstens zehn Jahren.", false);
        return;
      }
      jobStatus(isin, "Gespeicherter Bestand wird geprüft …", true);
      try { await followJob(isin, await historyRequest("POST", {isin, ...scope})); }
      catch (error) { jobStatus(isin, error.message, false); }
    });
  }
  async function load() {
    elements.status.textContent = "Fundamentaldaten werden geladen …";
    const controller = new AbortController();const timeout = setTimeout(() => controller.abort(), 8000);
    try {
      const response = await fetch("api/fundamentals.php", {method: "GET", credentials: "same-origin", cache: "no-store", signal: controller.signal, headers: {Accept: "application/json"}});
      if (!response.ok) throw Error("response");
      render(await response.json());
      const timing = document.querySelector("[data-fundamentals-load-time]");
      if (timing && typeof performance !== "undefined") {
        const dataReady = performance.now();
        const measure = () => setTimeout(() => {
          const navigation = performance.getEntriesByType("navigation")[0];
          const milliseconds = Math.round(Math.max(dataReady, navigation?.duration || 0));
          timing.textContent = milliseconds + " ms";
        }, 0);
        if (document.readyState === "complete") measure();
        else window.addEventListener("load", measure, {once: true});
      }
    } catch (error) {
      elements.detail.replaceChildren();elements.status.textContent = "Fundamentaldaten nicht verfügbar";elements.summary.textContent = "Die gespeicherten Daten konnten nicht gelesen werden.";
      const message = document.createElement("p");message.className = "fundamental-error";message.textContent = "Bitte später erneut versuchen. Es wurde kein Import gestartet.";elements.detail.append(message);
    } finally {clearTimeout(timeout);}
  }
  globalThis.MosaFundamentals = Object.freeze({date,period,render});
  load();
}());
