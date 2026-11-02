(function () {
  "use strict";
  const KEY = "mosa2-isin-lookup-v1";
  const providers = Object.freeze([{key:"tradegate",label:"Tradegate BSX"}, {key:"frankfurt",label:"Börse Frankfurt"}]);
  const valid = value => typeof value === "string" && /^[A-Z]{2}[A-Z0-9]{9}[0-9]$/.test(value);
  const forms = [...document.querySelectorAll("[data-isin-form]")];
  if (!forms.length) return;
  function restore() {
    try {
      const saved = JSON.parse(localStorage.getItem(KEY) || "[]");
      if (!Array.isArray(saved)) return [];
      const seen = new Set();
      return saved.filter(entry => {
        if (!entry || !valid(entry.isin) || seen.has(entry.isin)) return false;
        seen.add(entry.isin);return true;
      }).slice(0,30).map(entry => ({isin:entry.isin,
        name:typeof entry.name === "string" && entry.name.length <= 160 ? entry.name : null,
        quotes:Array.isArray(entry.quotes)?entry.quotes.filter(q => q && q.isin===entry.isin && providers.some(p=>p.key===q.provider) && typeof q.price==="string" && typeof q.market_at==="string").slice(0,2):[]}));
    } catch {return [];}
  }
  let entries = restore(), busy = false;
  const save = () => {try {localStorage.setItem(KEY, JSON.stringify(entries));} catch { /* Browser storage is optional. */ }};
  const fmtPrice = p => {
    const num=Number(p);
    return typeof p==="string" && /^\d+(?:\.\d{1,12})?$/.test(p) && Number.isFinite(num)
      ? new Intl.NumberFormat("de-DE",{minimumFractionDigits:4,maximumFractionDigits:4}).format(num) : "—";
  };
  function date(value) {
    const stamp=Date.parse(value);
    return Number.isFinite(stamp) ? new Intl.DateTimeFormat("de-DE",{timeZone:"Europe/Berlin",dateStyle:"short",timeStyle:"medium"}).format(stamp)+" Uhr" : "—";
  }
  function old(quote) {
    const stamp=Date.parse(quote.market_at);
    return !Number.isFinite(stamp) || Date.now()-stamp>1800000;
  }
  function best(entry) {
    return entry.quotes.slice().sort((a,b)=>Date.parse(b.market_at)-Date.parse(a.market_at) || providers.findIndex(p=>p.key===a.provider)-providers.findIndex(p=>p.key===b.provider))[0] || null;
  }
  function itemCell(row,label,value) {const cell=document.createElement("td");cell.dataset.label=label;cell.textContent=value;row.append(cell);return cell;}
  function paint() {
    for (const list of document.querySelectorAll("[data-isin-list]")) {
      const fragment=document.createDocumentFragment();
      for (const [index,entry] of entries.entries()) {
        const quote=best(entry), li=document.createElement("li");
        const number=document.createElement("span");number.textContent=String(index+1).padStart(2,"0");
        const link=document.createElement("a");link.href="marktdaten.html";link.textContent=entry.name || entry.isin;
        const detail=document.createElement("small");detail.textContent=entry.isin + (quote ? " · "+fmtPrice(quote.price)+" "+quote.currency+" · "+quote.source+(old(quote)?" · Veraltet":"") : " · Noch kein Abruf");
        link.append(detail);const arrow=document.createElement("span");arrow.textContent="↗";
        li.append(number,link,arrow);fragment.append(li);
      }
      if (!entries.length) {const li=document.createElement("li");li.className="isin-empty";li.textContent="Noch keine ISIN eingegeben.";fragment.append(li);}
      list.replaceChildren(fragment);
    }
    const number=document.querySelector("[data-isin-count]");if(number) number.firstChild.textContent=String(entries.length).padStart(2,"0");
    for (const tbody of document.querySelectorAll("[data-isin-table]")) {
      const fragment=document.createDocumentFragment();
      for (const entry of entries) {
        for (const quote of entry.quotes.length?entry.quotes:[null]) {
          const tr=document.createElement("tr");tr.dataset.status=quote?(old(quote)?"stale":"stored"):"missing";
          itemCell(tr,"Aktie",entry.name||entry.isin);
          const price=itemCell(tr,"Kurs",quote?fmtPrice(quote.price)+" "+quote.currency:"—");price.className="market-price";
          itemCell(tr,"Einheit / Kursart",quote?quote.currency+" · "+quote.quote_type:"—");
          itemCell(tr,"Quelle / Handelsplatz",quote?quote.source:"—");
          itemCell(tr,"Marktzeit",quote?date(quote.market_at):"—");
          itemCell(tr,"Abgerufen",quote?date(quote.captured_at):"—");
          itemCell(tr,"Datenalter",quote?String(Math.max(0,Math.round((Date.now()-Date.parse(quote.market_at))/60000)))+" Min.":"—");
          itemCell(tr,"ISIN",entry.isin);
          itemCell(tr,"Status",quote?(old(quote)?"Veraltet":"Kurs abgerufen"):"Noch nicht abgefragt");
          fragment.append(tr);
        }
      }
      if(!entries.length){const tr=document.createElement("tr");tr.className="market-placeholder";const td=itemCell(tr,"ISIN","Noch keine ISIN eingegeben.");td.colSpan=9;fragment.append(tr);}
      tbody.replaceChildren(fragment);
    }
    for (const label of document.querySelectorAll("[data-isin-summary]")) label.textContent=entries.length+" ISIN"+(entries.length===1?"":"s")+" · Manuell abgefragte Kurse";
  }
  function progress(form,message,kind="info") {
    const list=form.parentElement.querySelector("[data-isin-steps]");if(!list)return;
    const item=document.createElement("li");item.dataset.status=kind;item.textContent=message;list.append(item);
  }
  async function request(code, provider) {
    const controller=new AbortController(), timer=setTimeout(()=>controller.abort(),11000);
    try {
      const response=await fetch("api/isin_quote.php",{method:"POST",credentials:"same-origin",cache:"no-store",signal:controller.signal,
        headers:{"Accept":"application/json","Content-Type":"application/json","X-Requested-With":"XMLHttpRequest"},
        body:JSON.stringify({isin:code,provider})});
      const data=await response.json();
      if(!response.ok || data.status!=="ok" || data.isin!==code || data.provider!==provider || !/^\d+(?:\.\d{1,12})?$/.test(data.price))
        throw Error(typeof data.code==="string"?data.code:"SOURCE_UNAVAILABLE");
      return data;
    } finally {clearTimeout(timer);}
  }
  async function submit(form) {
    if(busy)return;
    const code=form.querySelector("[data-isin-input]").value.trim().toUpperCase();
    const list=form.parentElement.querySelector("[data-isin-steps]");if(list)list.replaceChildren();
    if(!valid(code)){progress(form,"Ungültige ISIN. Bitte zwölf Zeichen einschließlich Prüfziffer eingeben.","error");return;}
    let entry=entries.find(e=>e.isin===code);
    if(!entry){if(entries.length>=30){progress(form,"Die Liste enthält bereits 30 ISINs.","error");return;}entry={isin:code,name:null,quotes:[]};entries.unshift(entry);}
    entry.quotes=[]; // Never display an older result as this request runs.
    busy=true;for(const f of forms)f.querySelector("button[type=submit]").disabled=true;
    save();paint();progress(form,"ISIN geprüft: "+code,"success");
    const found=[];
    try{
      for(const provider of providers){
        progress(form,provider.label+": Abfrage gestartet.");
        try{
          const result=await request(code,provider.key);
          found.push(result);
          if(result.name)entry.name=result.name;
          progress(form,provider.label+": "+fmtPrice(result.price)+" "+result.currency+" · "+result.quote_type+(result.stale?" · Kurs ist älter":"")+" · Marktzeit "+date(result.market_at),"success");
        }catch(error){progress(form,provider.label+": kein bestätigter Kurs ("+(error.name==="AbortError"?"Zeitüberschreitung":error.message||"Fehler")+").","error");}
        entry.quotes=found.slice();save();paint();
      }
      if(found.length){const winner=best(entry);progress(form,"Ergebnis: "+(entry.name||code)+" · "+fmtPrice(winner.price)+" "+winner.currency+" · "+winner.source+" · Abgerufen "+date(winner.captured_at)+(old(winner)?" · Marktzeit veraltet":""),"success");}
      else progress(form,"Kein bestätigter Kurs gefunden. Der ältere Datenbankstand wurde nicht als neuer Kurs übernommen.","error");
    }finally{busy=false;for(const f of forms)f.querySelector("button[type=submit]").disabled=false;save();paint();}
  }
  for(const form of forms) form.addEventListener("submit",event=>{event.preventDefault();submit(form);});
  paint();
  globalThis.MosaIsinLookup=Object.freeze({valid});
}());
