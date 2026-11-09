(function () {
  "use strict";

  const root = document.querySelector("[data-fundamentals-view]");
  if (!root) return;
  const state = { items: [], selected: null };
  const elements = {
    assets: root.querySelector("[data-fundamental-assets]"),
    detail: root.querySelector("[data-fundamental-detail]"),
    status: root.querySelector("[data-fundamental-status]"),
    summary: root.querySelector("[data-fundamental-summary]"),
    total: root.querySelector("[data-fundamental-total]")
  };

  function text(value) {
    return value === null || value === undefined || value === "" ? "—" : String(value);
  }
  function period(row) {
    if (row.period_type === "fy" && row.fiscal_year) return "FY" + row.fiscal_year;
    if (row.period_type === "fq" && row.fiscal_year && row.fiscal_quarter) return "Q" + row.fiscal_quarter + " " + row.fiscal_year;
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
        return match ? text(match.value) + (match.current ? " · Current" : "") : "—";
      });
      return [metric.metric_name, ...values, metric.unit_key, [...new Set(facts.filter((row) => row.metric_key === metric.metric_key).map((row) => row.source))].join(" · ")];
    });
    return table("Jahresvergleich", ["Kennzahl", ...years.map((year) => "FY" + year), "Einheit", "Quelle"], rows, "comparison-table");
  }
  function details(item) {
    const rows = item.observations.map((row) => [row.metric_name, period(row) + (row.current ? " · Current" : ""), row.value, row.unit_key, row.source]);
    return table("Gespeicherte Kennzahlen", ["Kennzahl", "Zeitraum / Stichtag", "Wert", "Einheit", "Quelle"], rows, "observation-table");
  }
  function select(isin) {
    const item = state.items.find((candidate) => candidate.isin === isin);
    if (!item) return;
    state.selected = item.isin;
    elements.assets.querySelectorAll("button").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.isin === item.isin)));
    const fragment = document.createDocumentFragment();
    const header = document.createElement("div");header.className = "fundamental-detail-heading";
    const title = document.createElement("h2");title.textContent = item.name;header.append(title);
    const identity = document.createElement("p");identity.className = "fundamental-identity";identity.textContent = "ISIN " + item.isin + " · " + item.observations.length + " Observations · " + item.current.length + " Current";header.append(identity);
    const timing = document.createElement("p");timing.className = "fundamental-capture";const latest = item.observations.map((row) => row.captured_at).sort().at(-1);timing.textContent = "Erfasst bis " + date(latest) + ". Gespeicherter Datenbankstand, kein Live-Abruf.";header.append(timing);fragment.append(header);
    const compare = comparison(item);if (compare) fragment.append(compare);fragment.append(details(item));
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
    select(data.items[0].isin);
    elements.status.textContent = "Gespeicherte Fundamentaldaten";
  }
  async function load() {
    elements.status.textContent = "Fundamentaldaten werden geladen …";
    const controller = new AbortController();const timeout = setTimeout(() => controller.abort(), 8000);
    try {
      const response = await fetch("api/fundamentals.php", {method: "GET", credentials: "same-origin", cache: "no-store", signal: controller.signal, headers: {Accept: "application/json"}});
      if (!response.ok) throw Error("response");
      render(await response.json());
    } catch (error) {
      elements.detail.replaceChildren();elements.status.textContent = "Fundamentaldaten nicht verfügbar";elements.summary.textContent = "Die gespeicherten Daten konnten nicht gelesen werden.";
      const message = document.createElement("p");message.className = "fundamental-error";message.textContent = "Bitte später erneut versuchen. Es wurde kein Import gestartet.";elements.detail.append(message);
    } finally {clearTimeout(timeout);}
  }
  globalThis.MosaFundamentals = Object.freeze({date,period,render});
  load();
}());
