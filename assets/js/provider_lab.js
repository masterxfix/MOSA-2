(function () {
  "use strict";
  const root = document.querySelector("[data-provider-lab]");
  if (!root) return;
  const form = root.querySelector("[data-provider-lab-form]");
  const input = form.querySelector("input[name=isin]");
  const button = form.querySelector("button[type=submit]");
  const status = root.querySelector("[data-provider-lab-status]");
  const output = root.querySelector("[data-provider-lab-results]");
  const names = Object.freeze({
    bid:"Geldkurs", ask:"Briefkurs", mid:"Mittelwert", reported_mid:"Gemeldeter Mittelwert",
    bid_size:"Geld-Stückzahl", ask_size:"Brief-Stückzahl", trade_size:"Stückzahl letzter Handel",
    day_high:"Tageshoch", day_low:"Tagestief", previous_close:"Vortagesschluss",
    volume:"Handelsvolumen", quoted_at:"Marktzeit", currency:"Währung", price:"Kurs",
    spread:"Spread", spread_percent:"Spread (%)", age_seconds:"Datenalter (Sekunden)",
    wkn:"WKN", market_id:"Markt-ID", instrument_id:"Instrumenten-ID",
    instrument_type:"Wertpapiertyp", name:"Wertpapiername", available:"Verfügbar",
    venue_label:"Handelsplatz", provider_label:"Anbieter", freshness:"Aktualität",
    data_type:"Datentyp", symbol:"Börsensymbol", exchange_code:"Börsenkennung",
    unit_label:"Einheit", last_at:"Zeitpunkt letzter Handel",
    http_status:"HTTP-Status", error_code:"Fehlercode"
  });
  const element = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  };
  function listTable(rows, headers, columns) {
    const scroller = element("div","provider-lab-scroll");
    const table = element("table","provider-lab-table");
    const head = element("thead");
    const heading = element("tr");
    for (const label of headers) heading.append(element("th",null,label));
    head.append(heading);table.append(head);
    const body=element("tbody");
    for (const item of rows) {
      const tr=element("tr");
      for (const key of columns) {
        const value=item[key];
        const cell=element("td",key==="value"?"provider-lab-value":null,
          value===null||value===undefined?"—":value);
        tr.append(cell);
      }
      body.append(tr);
    }
    table.append(body);scroller.append(table);
    return scroller;
  }
  function details(title, rows, headers, columns, open=false) {
    const section = element("details","provider-lab-details");
    section.open = open;
    section.append(element("summary",null,title+" ("+rows.length+")"));
    if (rows.length) section.append(listTable(rows,headers,columns));
    else section.append(element("p","context-note","Keine Werte in der Anbieterantwort."));
    return section;
  }
  function render(data) {
    output.replaceChildren();
    const identity=data.identity||{};
    const label=identity.name||"Kein geprüfter Name verfügbar";
    const info=element("p","provider-lab-identity");
    info.textContent=label+" · "+data.isin+" · "+(identity.wkn||"WKN nicht geliefert")
      +" · Typ: "+(identity.instrument_type||"unknown");
    output.append(info);
    const summary=element("p","provider-lab-subnote",
      "Abfrage: "+(data.requested_at||"—")+" · "+data.request_count
      +" echte Anbieter-Requests · keine Datenbankspeicherung.");
    output.append(summary);
    for (const provider of data.providers||[]) {
      const box=element("section","provider-lab-provider");
      box.append(element("h2",null,provider.name));
      box.append(element("p","context-note","Handelsplatz: "+provider.venue));
      const requests=(provider.requests||[]).map(r=>({
        name:r.key,http:r.http_status===null?"—":String(r.http_status),
        latency:r.latency_ms===null?"—":r.latency_ms+" ms",
        bytes:r.response_bytes===null?"—":String(r.response_bytes),
        error:r.error_code||"—"
      }));
      box.append(details("Abrufstatus",requests,
        ["Abruf","HTTP","Dauer","Antwortbytes","Fehler"],
        ["name","http","latency","bytes","error"],true));
      const values=(provider.fields||[]).map(x=>({
        field:(names[x.field]||x.field)+" · "+x.field,
        value:x.value,role:x.role
      }));
      box.append(details("Vom M2-Parser erkannte Felder",values,
        ["Feld","Wert","Quellenrolle"],["field","value","role"],true));
      const raw=provider.raw_fields||[];
      box.append(details("Weitere Rohfelder der Originalantwort",raw,
        ["Originalfeld / Pfad","Gelieferter Wert"],["field","value"]));
      if((provider.raw_fields_truncated||[]).length)
        box.append(element("p","provider-lab-warning",
          "Feldinventar begrenzt bei: "+provider.raw_fields_truncated.join(", ")+
          ". Das Rohdokument wird aus Sicherheitsgründen nicht veröffentlicht."));
      output.append(box);
    }
    if ((data.providers||[]).length!==3)
      status.textContent="Die Anbieterantwort ist unvollständig: Erwartet werden drei Anbieter.";
    else status.textContent="Abfrage abgeschlossen. Alle drei Anbieter sind getrennt dargestellt; ausgefallene Requests bleiben erkennbar.";
  }
  form.addEventListener("submit",async event=>{
    event.preventDefault();
    if(button.disabled)return;
    const isin=input.value.trim().toUpperCase();
    if(!/^[A-Z]{2}[A-Z0-9]{9}[0-9]$/.test(isin)){
      status.textContent="ISIN: zwölf Zeichen einschließlich Prüfziffer erforderlich.";
      return;
    }
    button.disabled=true;output.replaceChildren();
    status.textContent="Manuelle Anbieterabfragen laufen. Keine Datenbankaktion.";
    const controller=new AbortController();
    const timeout=setTimeout(()=>controller.abort(),60000);
    try{
      const reply=await fetch("api/market_provider_lab.php",{
        method:"POST",credentials:"same-origin",cache:"no-store",signal:controller.signal,
        headers:{"Accept":"application/json","Content-Type":"application/json",
          "X-Requested-With":"XMLHttpRequest","X-MOSA2-Quote-Intent":"manual"},
        body:JSON.stringify({isin})
      });
      const data=await reply.json();
      if(!reply.ok||data.status!=="ok"){
        if(reply.status===429)throw Error("Bitte vor dem erneuten Abruf zwölf Sekunden warten.");
        if(data.code==="INVALID_ISIN")throw Error("Ungültige ISIN-Prüfziffer.");
        throw Error("Abruf fehlgeschlagen (HTTP "+reply.status+", "+(data.code||"Fehler")+").");
      }
      render(data);
    }catch(error){
      status.textContent=error.name==="AbortError"?"Abfrage wegen Zeitüberschreitung abgebrochen.":error.message;
    }finally{clearTimeout(timeout);button.disabled=false;}
  });
}());
