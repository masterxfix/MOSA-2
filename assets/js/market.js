(function () {
  "use strict";
  const states = Object.freeze({loading: "Wird geladen", missing: "Noch kein Kurs", stale: "Veraltet", stored: "Gespeichert", error: "Nicht verfügbar"});
  function decimal(value) {
    if (typeof value !== "string" || !/^-?\d+\.\d{10}$/.test(value)) throw Error("price");
    const parts = value.split(".");
    const fraction = parts[1].replace(/0+$/, "").padEnd(2, "0");
    return parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ".") + "," + fraction;
  }
  function time(value) {
    if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{6}Z$/.test(value)) throw Error("time");
    return value.slice(8,10) + "." + value.slice(5,7) + "." + value.slice(0,4) + " · " + value.slice(11,19) + " UTC";
  }
  function cell(row, label, text) {
    const node = document.createElement("td");node.dataset.label = label;node.textContent = text;row.append(node);return node;
  }
  function render(root, state, items = []) {
    if (!(state in states) || !Array.isArray(items) || items.length > 10) throw Error("state");
    const body = root.querySelector("[data-market-rows]");const fragment = document.createDocumentFragment();
    for (const item of items) {
      if (!["missing", "stale", "stored"].includes(item.status) || ![item.name,item.source,item.venue].every(v => typeof v === "string")) throw Error("item");
      if(item.status!=="missing" && (typeof item.unit!=="string" || typeof item.unit_version!=="string" || (item.quantity_basis_amount!==null && (typeof item.quantity_basis_amount!=="string" || typeof item.quantity_basis_unit!=="string"))))throw Error("unit");
      const row = document.createElement("tr");row.dataset.status = item.status;
      cell(row, "Asset", item.name);
      const price = item.status === "missing" ? "—" : decimal(item.price) + " " + item.unit + (item.quantity_basis_amount === null ? "" : " / " + item.quantity_basis_amount + " " + item.quantity_basis_unit);
      const priceNode = cell(row, "Kurs", price);priceNode.className = "market-price";
      if(item.status!=="missing"){priceNode.dataset.nativePrice=item.price;priceNode.dataset.unit=item.unit;priceNode.dataset.unitVersion=item.unit_version;row.dataset.marketAt=item.market_at;row.dataset.observedAt=item.observed_at;}
      cell(row, "Quelle / Handelsplatz", item.source + " · " + item.venue);
      cell(row, "Zeitpunkt", item.status === "missing" ? "—" : time(item.market_at) + "\nErfasst: " + time(item.observed_at));
      cell(row, "Datenstatus", states[item.status]);fragment.append(row);
    }
    if (items.length === 0) {
      const row=document.createElement("tr");row.className="market-placeholder";const td=cell(row,"Datenstatus",state==="missing"?"Noch keine gespeicherten Marktdaten.":states[state]);td.colSpan=5;fragment.append(row);
    }
    body.replaceChildren(fragment);root.dataset.state=state;
    root.querySelector("[data-market-region]").setAttribute("aria-busy",String(state==="loading"));
    root.querySelector("[data-market-summary]").textContent=state==="stored"?items.length+" Assets · Stand aus der Datenbank":states[state];
  }
  function ready(root, ok) {
    // Two animation frames: rows have reached a browser paint before measurement.
    requestAnimationFrame(() => requestAnimationFrame(() => {
      const ms=Math.round(performance.now());root.dataset.dataReadyMs=String(ms);root.dataset.dataSuccess=String(ok);
      if(typeof performance.getEntriesByType==="function"){const paint=performance.getEntriesByType("paint").find(p=>p.name==="first-contentful-paint");if(paint)root.dataset.firstContentfulPaintMs=String(paint.startTime);}
      const node=document.querySelector("[data-data-ready-time]");
      if(node){node.textContent=ms+" ms";node.setAttribute("aria-label",(ok?"Darstellung mit Daten ":"Fehleranzeige nach ")+ms+" ms");}
    }));
  }
  async function load(root) {
    render(root,"loading");const controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),8000);
    try {
      const response=await fetch("api/market.php",{method:"GET",credentials:"same-origin",cache:"no-store",signal:controller.signal,headers:{Accept:"application/json"}});
      if(!response.ok)throw Error("response");const data=await response.json();
      if(data.status!=="ok"||!Array.isArray(data.items))throw Error("payload");
      render(root,data.items.length?"stored":"missing",data.items);ready(root,true);
    }catch(error){render(root,"error");ready(root,false);}finally{clearTimeout(timeout);}
  }
  globalThis.MosaMarket=Object.freeze({decimal,time,render});
  const root=document.querySelector("[data-market-view]");if(root){root.dataset.shellReadyMs=String(Math.round(performance.now()));root.dataset.viewport=String(window.innerWidth)+"x"+String(window.innerHeight);load(root);}
}());
