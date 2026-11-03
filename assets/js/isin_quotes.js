(function () {
  "use strict";
  const KEY = "mosa2-isin-lookup-v1";
  const providers = Object.freeze([
    {key:"lang_schwarz_quote",label:"Lang & Schwarz · Geld/Brief"},
    {key:"lang_schwarz_trade",label:"Lang & Schwarz · letzter Handel"},
    {key:"tradegate_quote",label:"Tradegate BSX · Geld/Brief"},
    {key:"tradegate_trade",label:"Tradegate BSX · letzter Handel"},
    {key:"boerse_frankfurt_trade",label:"Börse Frankfurt · letzter Handel"},
    {key:"yahoo_home_market",label:"Yahoo Finance · Heimatmarkt"}
  ]);
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
        quotes:Array.isArray(entry.quotes)?entry.quotes.filter(q => q && q.isin===entry.isin && providers.some(p=>p.key===q.provider) && typeof q.price==="string" && typeof q.market_at==="string").slice(0,6):[],
        errors:Array.isArray(entry.errors)?entry.errors.filter(e=>e && (e.provider==="all" || providers.some(p=>p.key===e.provider)) && typeof e.code==="string").slice(0,6):[]}));
    } catch {return [];}
  }
  let entries = restore(), busy = false;
  const save = () => {try {localStorage.setItem(KEY, JSON.stringify(entries));} catch { /* Browser storage is optional. */ }};
  const fmtPrice = p => {
    const num=Number(p);
    return typeof p==="string" && /^\d+(?:\.\d{1,12})?$/.test(p) && Number.isFinite(num)
      ? new Intl.NumberFormat("de-DE",{minimumFractionDigits:2,maximumFractionDigits:10}).format(num) : "—";
  };
  function date(value) {
    const stamp=Date.parse(value);
    return Number.isFinite(stamp) ? new Intl.DateTimeFormat("de-DE",{timeZone:"Europe/Berlin",dateStyle:"short",timeStyle:"medium"}).format(stamp)+" Uhr" : "—";
  }
  function old(quote) {
    const stamp=Date.parse(quote.market_at);
    return Boolean(quote.refresh_failed_at) || !Number.isFinite(stamp) || Date.now()-stamp>1800000;
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
        for (const quote of entry.quotes.length?entry.quotes:((entry.errors||[]).length?[]:[null])) {
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
        for(const error of entry.errors||[]){
          const tr=document.createElement("tr");tr.dataset.status="error";
          itemCell(tr,"Aktie",entry.name||entry.isin);itemCell(tr,"Kurs","—");itemCell(tr,"Einheit / Kursart","—");
          itemCell(tr,"Quelle / Handelsplatz",sourceLabel(error.provider));
          itemCell(tr,"Marktzeit","—");itemCell(tr,"Abgerufen",date(error.captured_at));itemCell(tr,"Datenalter","—");
          itemCell(tr,"ISIN",entry.isin);itemCell(tr,"Status","Kein bestätigter Kurs: "+error.code);fragment.append(tr);
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
  async function requestAll(code, onEvent) {
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),90000);
    try {
      const response=await fetch("api/isin_quote.php",{
        method:"POST",credentials:"same-origin",cache:"no-store",signal:controller.signal,
        headers:{"Accept":"application/x-ndjson","Content-Type":"application/json","X-Requested-With":"XMLHttpRequest"},
        body:JSON.stringify({isin:code,provider:"all"})
      });
      if(!response.ok)throw Error("HTTP_"+response.status);
      if(response.body && typeof response.body.getReader==="function"){
        const reader=response.body.getReader(), decoder=new TextDecoder("utf-8");
        let buffer="",result=null;
        function event(line){
          if(!line.trim())return;
          const message=JSON.parse(line);
          if(message.event==="result")result=message.data;
          else if(message.event==="failure")throw Error(message.code||"SOURCE_COMPARISON_FAILED");
          else onEvent(message);
        }
        for(;;){
          const {value,done}=await reader.read();
          if(done)break;
          buffer+=decoder.decode(value,{stream:true});
          if(buffer.length>200000)throw Error("INVALID_RESPONSE");
          let at;
          while((at=buffer.indexOf("\n"))!==-1){event(buffer.slice(0,at));buffer=buffer.slice(at+1);}
        }
        buffer+=decoder.decode();
        if(buffer.trim())event(buffer);
        if(!result)throw Error("NO_RESULT");
        return result;
      }
      const data=await response.json();
      return data.event==="result"?data.data:data;
    }finally{clearTimeout(timer);}
  }
  function reportStep(form,event) {
    if(event.event==="started"){progress(form,"ISIN bestätigt: "+event.isin,"success");return;}
    if(event.event!=="request")return;
    if(event.stage==="started"){progress(form,event.name+": Anfrage gestartet.");return;}
    if(event.stage==="finished"){
      const code=event.code || (event.http_status===200?null:"HTTP_"+(event.http_status??"unbekannt"));
      const duration=Number.isInteger(event.duration_ms)?" · "+event.duration_ms+" ms":"";
      progress(form,event.name+": "+(code?"Fehler "+code:"HTTP 200")+duration,code?"error":"success");
    }
  }
  function sourceLabel(provider) {
    return providers.find(p=>p.key===provider)?.label || "MOSA-Quellenvergleich";
  }
  function applyResult(entry,result,form,preserveExisting) {
    if(!result||result.isin!==entry.isin||!Array.isArray(result.records)||result.records.length!==providers.length)
      throw Error("INVALID_RESULT");
    let quotes=preserveExisting?entry.quotes.slice():[];
    let errors=preserveExisting?entry.errors.filter(error=>error.provider!=="all"):[];
    const seen=new Set();let successful=0,failed=0;
    for(const record of result.records){
      if(!record||!providers.some(p=>p.key===record.provider)||seen.has(record.provider))throw Error("INVALID_PROVIDER_RESULT");
      seen.add(record.provider);
      const label=sourceLabel(record.provider);
      if(record.status==="ok"&&typeof record.price==="string"&&/^\d+(?:\.\d{1,12})?$/.test(record.price)
        &&typeof record.market_at==="string"&&typeof record.currency==="string"){
        const fresh={...record};delete fresh.refresh_failed_at;
        quotes=quotes.filter(quote=>quote.provider!==record.provider);quotes.push(fresh);
        errors=errors.filter(error=>error.provider!==record.provider);successful++;
        progress(form,label+": "+fmtPrice(record.price)+" "+record.currency+" · "+record.quote_type+
          " · Marktzeit "+date(record.market_at)+(old(record)?" · Veraltet":""),"success");
      }else{
        const reason=typeof record.code==="string"?record.code:"QUOTE_UNAVAILABLE";
        const capturedAt=typeof record.captured_at==="string"?record.captured_at:new Date().toISOString();
        if(preserveExisting)quotes=quotes.map(quote=>quote.provider===record.provider?{...quote,refresh_failed_at:capturedAt}:quote);
        errors=errors.filter(error=>error.provider!==record.provider);
        errors.push({provider:record.provider,code:reason,captured_at:capturedAt});failed++;
        progress(form,label+": kein bestätigter Kurs ("+reason+").","error");
      }
    }
    entry.quotes=quotes;entry.errors=errors;
    if(typeof result.name==="string"&&result.name)entry.name=result.name;
    return {successful,failed};
  }
  function markRequestFailure(entry,reason) {
    const capturedAt=new Date().toISOString();
    entry.quotes=entry.quotes.map(quote=>({...quote,refresh_failed_at:capturedAt}));
    entry.errors=entry.errors.filter(error=>error.provider!=="all");
    entry.errors.push({provider:"all",code:reason,captured_at:capturedAt});
  }
  function setBusy(value) {
    busy=value;
    for(const form of forms){const button=form.querySelector("button[type=submit]");if(button)button.disabled=value;}
    for(const button of document.querySelectorAll("[data-isin-refresh]"))button.disabled=value;
  }
  async function submit(form) {
    if(busy)return;
    const code=form.querySelector("[data-isin-input]").value.trim().toUpperCase();
    const list=form.parentElement.querySelector("[data-isin-steps]");if(list)list.replaceChildren();
    if(!valid(code)){progress(form,"Ungültige ISIN. Bitte zwölf Zeichen einschließlich Prüfziffer eingeben.","error");return;}
    let entry=entries.find(e=>e.isin===code);
    if(!entry){
      if(entries.length>=30){progress(form,"Die Liste enthält bereits 30 ISINs.","error");return;}
      entry={isin:code,name:null,quotes:[],errors:[]};entries.unshift(entry);
    }
    entry.quotes=[];entry.errors=[]; // The last result is never relabelled as a new request.
    setBusy(true);
    save();paint();progress(form,"MOSA-Quellenvergleich für "+code+" gestartet.");
    try{
      const result=await requestAll(code,event=>reportStep(form,event));
      const outcome=applyResult(entry,result,form,false);save();paint();
      if(outcome.successful){
        const winner=best(entry);
        progress(form,"Ergebnis: "+(entry.name||code)+" · "+fmtPrice(winner.price)+" "+winner.currency+
          " · "+winner.source+" · Erfasst "+date(winner.captured_at)+(old(winner)?" · Marktzeit veraltet":""),"success");
      }else progress(form,"Kein Anbieter hat einen bestätigten Kurs geliefert. Es wird kein alter Wert als aktuell ausgegeben.","error");
    }catch(error){
      const reason=error.name==="AbortError"?"Zeitüberschreitung":error.message||"Abfrage fehlgeschlagen";
      progress(form,"Quellenvergleich nicht abgeschlossen: "+reason,"error");
    }finally{
      setBusy(false);
      save();paint();
    }
  }
  async function refreshAll(button) {
    if(busy)return;
    entries=restore();paint();
    const form=forms[0],list=form.parentElement.querySelector("[data-isin-steps]");
    if(list)list.replaceChildren();
    if(!entries.length){progress(form,"Keine gespeicherten ISINs. Es wurde keine Abfrage ausgelöst.");return;}
    const snapshot=entries.slice();let successful=0,failed=0;
    setBusy(true);progress(form,"Aktualisierung gestartet: "+snapshot.length+" ISIN"+(snapshot.length===1?"":"s")+".");
    try{
      for(const [index,entry] of snapshot.entries()){
        const label=entry.name||entry.isin;
        progress(form,"Aktualisiere "+(index+1)+" von "+snapshot.length+": "+label);
        try{
          const result=await requestAll(entry.isin,event=>reportStep(form,event));
          const outcome=applyResult(entry,result,form,true);
          if(outcome.successful){
            successful++;
            progress(form,label+": "+outcome.successful+" Kurs"+(outcome.successful===1?"":"e")+" aktualisiert"+
              (outcome.failed?", "+outcome.failed+" Quellenfehler":""),outcome.failed?"info":"success");
          }else{
            failed++;progress(form,label+": fehlgeschlagen: kein bestätigter Kurs.","error");
          }
        }catch(error){
          failed++;
          const reason=error.name==="AbortError"?"Zeitüberschreitung":error.message||"Abfrage fehlgeschlagen";
          markRequestFailure(entry,reason);progress(form,label+": fehlgeschlagen: "+reason,"error");
        }
        save();paint();
      }
      progress(form,"Aktualisierung abgeschlossen: "+successful+" erfolgreich, "+failed+" fehlgeschlagen.",failed?"error":"success");
    }finally{
      setBusy(false);save();paint();
    }
  }
  for(const form of forms) form.addEventListener("submit",event=>{event.preventDefault();submit(form);});
  for(const button of document.querySelectorAll("[data-isin-refresh]"))button.addEventListener("click",()=>refreshAll(button));
  paint();
  globalThis.MosaIsinLookup=Object.freeze({valid});
}());
