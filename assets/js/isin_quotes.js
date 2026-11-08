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
  const typeLabels = Object.freeze({stock:"Aktie",etf:"ETF",fund:"Fonds",other:"Sonstiges",unknown:"Unbekannt"});
  const confirmedTypes = new Set(["stock","etf","fund","other"]);
  const valid = value => typeof value === "string" && /^[A-Z]{2}[A-Z0-9]{9}[0-9]$/.test(value);
  const validQuote = (quote, isin) => Boolean(quote && quote.isin===isin && providers.some(provider=>provider.key===quote.provider)
    && typeof quote.price === "string" && /^\d+(?:\.\d{1,12})?$/.test(quote.price)
    && typeof quote.currency === "string" && quote.currency !== ""
    && typeof quote.market_at === "string" && Number.isFinite(Date.parse(quote.market_at)));
  const forms = [...document.querySelectorAll("[data-isin-form]")];
  if (!forms.length) return;
  const detailsToggle = document.querySelector("[data-isin-details-toggle]");
  const automationRoot = document.querySelector("[data-isin-automation]");
  const automationInterval = automationRoot?.querySelector("[data-isin-automation-interval]");
  const automationToggle = automationRoot?.querySelector("[data-isin-automation-toggle]");
  const automationStatus = automationRoot?.querySelector("[data-isin-automation-status]");
  const AUTOMATION_KEY = "mosa2-isin-automation-v1";
  const DEFAULT_INTERVAL_SECONDS = 60;
  const WEEKEND_INTERVAL_SECONDS = 3600;
  const clampInterval = value => Math.min(300, Math.max(5, Math.round(Number(value) || DEFAULT_INTERVAL_SECONDS)));
  function berlinDateParts(value = new Date()) {
    const parts = new Intl.DateTimeFormat("en-GB", {timeZone:"Europe/Berlin", year:"numeric", month:"2-digit", day:"2-digit"})
      .formatToParts(value).reduce((result, part) => { if (part.type !== "literal") result[part.type] = part.value; return result; }, {});
    return {year:Number(parts.year), month:Number(parts.month), day:Number(parts.day)};
  }
  function dateKey(year, month, day) { return year+"-"+String(month).padStart(2,"0")+"-"+String(day).padStart(2,"0"); }
  function utcDateKey(value) { return dateKey(value.getUTCFullYear(), value.getUTCMonth()+1, value.getUTCDate()); }
  function addUtcDays(value, days) { return new Date(value.getTime() + days*86400000); }
  function easterSunday(year) {
    const a=year%19,b=Math.floor(year/100),c=year%100,d=Math.floor(b/4),e=b%4,f=Math.floor((b+8)/25),g=Math.floor((b-f+1)/3),h=(19*a+b-d-g+15)%30;
    const i=Math.floor(c/4),k=c%4,l=(32+2*e+2*i-h-k)%7,m=Math.floor((a+11*h+22*l)/451);
    const month=Math.floor((h+l-7*m+114)/31),day=((h+l-7*m+114)%31)+1;
    return new Date(Date.UTC(year,month-1,day));
  }
  function bwHolidayKeys(year) {
    const easter=easterSunday(year), keys=new Set([
      dateKey(year,1,1), dateKey(year,1,6), dateKey(year,5,1), dateKey(year,10,3), dateKey(year,11,1),
      dateKey(year,12,25), dateKey(year,12,26)
    ]);
    for (const days of [-2,1,39,50,60]) keys.add(utcDateKey(addUtcDays(easter,days)));
    return keys;
  }
  function isBadenWuerttembergHoliday(value = new Date()) {
    const parts=berlinDateParts(value);
    return bwHolidayKeys(parts.year).has(dateKey(parts.year,parts.month,parts.day));
  }
  function dayMode(value = new Date()) {
    if (isBadenWuerttembergHoliday(value)) return "Feiertag Baden-Württemberg";
    const parts=berlinDateParts(value), weekday=new Date(Date.UTC(parts.year,parts.month-1,parts.day)).getUTCDay();
    return weekday===0 || weekday===6 ? "Wochenende" : "Werktag";
  }
  function intervalFor(value = new Date(), configuredSeconds = DEFAULT_INTERVAL_SECONDS) {
    return dayMode(value) === "Werktag" ? clampInterval(configuredSeconds) : WEEKEND_INTERVAL_SECONDS;
  }
  function berlinOffsetMs(value) {
    const zone=new Intl.DateTimeFormat("en-US", {timeZone:"Europe/Berlin", timeZoneName:"longOffset", hour:"2-digit", minute:"2-digit", hour12:false})
      .formatToParts(value).find(part => part.type === "timeZoneName")?.value || "GMT+01:00";
    const match=zone.match(/GMT([+-])(\d{1,2})(?::?(\d{2}))?/);
    if (!match) return 3600000;
    return (match[1] === "-" ? -1 : 1) * (Number(match[2])*60 + Number(match[3] || 0))*60000;
  }
  function nextBerlinMidnight(value = new Date()) {
    const parts=berlinDateParts(value), utcMidnight=Date.UTC(parts.year,parts.month-1,parts.day+1,0,0,0);
    return utcMidnight-berlinOffsetMs(new Date(utcMidnight));
  }
  function restoreAutomation() {
    if (!automationRoot) return {intervalSeconds:DEFAULT_INTERVAL_SECONDS,enabled:false,lastUpdatedAt:null};
    try {
      const saved=JSON.parse(localStorage.getItem(AUTOMATION_KEY) || "{}");
      return {intervalSeconds:clampInterval(saved.intervalSeconds),enabled:saved.enabled === true,
        lastUpdatedAt:typeof saved.lastUpdatedAt === "string" && Number.isFinite(Date.parse(saved.lastUpdatedAt)) ? saved.lastUpdatedAt : null};
    } catch { return {intervalSeconds:DEFAULT_INTERVAL_SECONDS,enabled:false,lastUpdatedAt:null}; }
  }
  let automation=restoreAutomation(), automationTimer=null;
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
        instrument_type:confirmedTypes.has(entry.instrument_type)?entry.instrument_type:"unknown",
        instrument_type_source:typeof entry.instrument_type_source === "string" && entry.instrument_type_source.length <= 80 ? entry.instrument_type_source : null,
        instrument_type_verified_at:typeof entry.instrument_type_verified_at === "string" && entry.instrument_type_verified_at.length <= 80 ? entry.instrument_type_verified_at : null,
        quotes:Array.isArray(entry.quotes)?entry.quotes.filter(q => validQuote(q,entry.isin)).slice(0,6):[],
        errors:Array.isArray(entry.errors)?entry.errors.filter(e=>e && (e.provider==="all" || providers.some(p=>p.key===e.provider)) && typeof e.code==="string").slice(0,6):[]}));
    } catch {return [];}
  }
  let entries = restore(), busy = false, detailsOpen = false;
  const save = () => {try {
    if (entries.length) localStorage.setItem(KEY, JSON.stringify(entries));
    else localStorage.removeItem(KEY);
  } catch { /* Browser storage is optional. */ }};
  function saveAutomation() {
    if (!automationRoot) return;
    try { localStorage.setItem(AUTOMATION_KEY, JSON.stringify(automation)); } catch { /* Browser storage is optional. */ }
  }
  function formatAutomationInterval(seconds) {
    return seconds >= 3600 ? String(Math.round(seconds/60))+" Min." : String(seconds)+" Sek.";
  }
  function formatAutomationTimestamp(value) { return value ? date(value) : "—"; }
  function updateAutomationStatus() {
    if (!automationRoot) return;
    const activeInterval=intervalFor(new Date(),automation.intervalSeconds), mode=dayMode(new Date());
    if (automationInterval && automationInterval.value !== String(automation.intervalSeconds)) automationInterval.value=String(automation.intervalSeconds);
    if (automationToggle) {
      automationToggle.textContent=automation.enabled ? "Automatik stoppen" : "Automatik starten";
      automationToggle.setAttribute("aria-pressed",String(automation.enabled));
      automationToggle.disabled=busy;
    }
    if (automationStatus) automationStatus.textContent=(automation.enabled ? "Automatik aktiv" : "Automatik inaktiv")+
      " · Aktives Intervall: "+formatAutomationInterval(activeInterval)+(automation.enabled ? "" : " (inaktiv)")+" · Modus: "+mode+
      " · Letzte Aktualisierung: "+formatAutomationTimestamp(automation.lastUpdatedAt);
  }
  function clearAutomationTimer() {
    if (automationTimer !== null) { clearTimeout(automationTimer); automationTimer=null; }
  }
  function scheduleAutomation(value = new Date()) {
    clearAutomationTimer();
    updateAutomationStatus();
    if (!automationRoot || !automation.enabled || document.visibilityState === "hidden" || busy || !entries.length) return;
    const interval=intervalFor(value,automation.intervalSeconds), last=Date.parse(automation.lastUpdatedAt || ""),
      due=Number.isFinite(last) ? last+interval*1000 : value.getTime()+interval*1000,
      next=Math.min(due,nextBerlinMidnight(value)), delay=Math.max(250,Math.min(2147483647,next-value.getTime()));
    automationTimer=setTimeout(runAutomaticCycle,delay);
  }
  async function runAutomaticCycle() {
    automationTimer=null;
    if (!automationRoot || !automation.enabled || document.visibilityState === "hidden" || busy || !entries.length) { scheduleAutomation(); return; }
    const now=new Date(), last=Date.parse(automation.lastUpdatedAt || "");
    if (Number.isFinite(last) && now.getTime() < last+intervalFor(now,automation.intervalSeconds)*1000) { scheduleAutomation(now); return; }
    await refreshAll(null,true);
  }
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
    return entry.quotes.filter(quote=>validQuote(quote,entry.isin)).slice().sort((a,b)=>Date.parse(b.market_at)-Date.parse(a.market_at) || providers.findIndex(p=>p.key===a.provider)-providers.findIndex(p=>p.key===b.provider))[0] || null;
  }
  function age(quote) {
    const stamp=Date.parse(quote.market_at);
    return Number.isFinite(stamp) ? String(Math.max(0,Math.round((Date.now()-stamp)/60000)))+" Min." : "—";
  }
  function typeLabel(entry) {return typeLabels[entry.instrument_type] || typeLabels.unknown;}
  function itemCell(row,label,value) {const cell=document.createElement("td");cell.dataset.label=label;cell.textContent=value;row.append(cell);return cell;}
  function syncDeleteButtons() {
    for (const button of document.querySelectorAll("[data-isin-remove]")) button.disabled = busy;
    for (const button of document.querySelectorAll("[data-isin-clear]")) button.disabled = busy || !entries.length;
  }
  function paint() {
    for (const list of document.querySelectorAll("[data-isin-list]")) {
      const fragment=document.createDocumentFragment();
      for (const [index,entry] of entries.entries()) {
        const quote=best(entry), li=document.createElement("li");
        const number=document.createElement("span");number.textContent=String(index+1).padStart(2,"0");
        const link=document.createElement("a");link.href="marktdaten.html";link.textContent=entry.name || entry.isin;
        const detail=document.createElement("small");detail.textContent=entry.isin+" · "+typeLabel(entry)+(quote ? " · "+fmtPrice(quote.price)+" "+quote.currency+" · "+quote.source+(old(quote)?" · Veraltet":"") : " · Noch kein Abruf");
        link.append(detail);
        const remove=document.createElement("button");remove.type="button";remove.className="isin-delete";remove.dataset.isinRemove=entry.isin;remove.textContent="Entfernen";remove.setAttribute("aria-label",entry.isin+" entfernen");
        const arrow=document.createElement("span");arrow.textContent="↗";
        li.append(number,link,remove,arrow);fragment.append(li);
      }
      if (!entries.length) {const li=document.createElement("li");li.className="isin-empty";li.textContent="Noch keine ISIN eingegeben.";fragment.append(li);}
      list.replaceChildren(fragment);
    }
    const number=document.querySelector("[data-isin-count]");if(number) number.firstChild.textContent=String(entries.length).padStart(2,"0");
    for (const tbody of document.querySelectorAll("[data-isin-table]")) {
      const fragment=document.createDocumentFragment();
      for (const entry of entries) {
        const latest=best(entry), quotes=entry.quotes.filter(quote=>validQuote(quote,entry.isin));
        if (!detailsOpen) {
          if (latest) renderQuoteRow(fragment,entry,latest);
          else renderMissingRow(fragment,entry);
          continue;
        }
        if (!quotes.length) renderMissingRow(fragment,entry);
        for (const quote of quotes) renderQuoteRow(fragment,entry,quote);
        for(const error of entry.errors||[]) renderErrorRow(fragment,entry,error);
      }
      if(!entries.length){const tr=document.createElement("tr");tr.className="market-placeholder";const td=itemCell(tr,"ISIN","Noch keine ISIN eingegeben.");td.colSpan=10;fragment.append(tr);}
      tbody.replaceChildren(fragment);
    }
    if(detailsToggle){detailsToggle.disabled=busy;detailsToggle.textContent=detailsOpen?"Weniger anzeigen":"Alle Details anzeigen";detailsToggle.setAttribute("aria-expanded",String(detailsOpen));}
    for (const label of document.querySelectorAll("[data-isin-summary]")) label.textContent=entries.length+" ISIN"+(entries.length===1?"":"s")+" · Manuell abgefragte Kurse";
    syncDeleteButtons();
    updateAutomationStatus();
  }
  function renderQuoteRow(fragment,entry,quote) {
    const tr=document.createElement("tr");tr.dataset.status=old(quote)?"stale":"stored";
    itemCell(tr,"Wertpapier",entry.name||entry.isin);itemCell(tr,"Typ",typeLabel(entry));
    const price=itemCell(tr,"Kurs",fmtPrice(quote.price)+" "+quote.currency);price.className="market-price";
    itemCell(tr,"Währung / Einheit",quote.currency+" · "+quote.quote_type);
    itemCell(tr,"Quelle / Handelsplatz",quote.source);
    itemCell(tr,"Marktzeit",date(quote.market_at));
    itemCell(tr,"Abgerufen",date(quote.captured_at));
    itemCell(tr,"Datenalter",age(quote));
    itemCell(tr,"ISIN",entry.isin);
    itemCell(tr,"Status",old(quote)?"Veraltet":"Kurs abgerufen");fragment.append(tr);
  }
  function renderMissingRow(fragment,entry) {
    const tr=document.createElement("tr");tr.dataset.status="missing";
    itemCell(tr,"Wertpapier",entry.name||entry.isin);itemCell(tr,"Typ",typeLabel(entry));itemCell(tr,"Kurs","—");itemCell(tr,"Währung / Einheit","—");
    itemCell(tr,"Quelle / Handelsplatz","—");itemCell(tr,"Marktzeit","—");itemCell(tr,"Abgerufen","—");itemCell(tr,"Datenalter","—");
    itemCell(tr,"ISIN",entry.isin);itemCell(tr,"Status","Kein erfolgreicher Kurs vorhanden");fragment.append(tr);
  }
  function renderErrorRow(fragment,entry,error) {
    const tr=document.createElement("tr");tr.dataset.status="error";
    itemCell(tr,"Wertpapier",entry.name||entry.isin);itemCell(tr,"Typ",typeLabel(entry));itemCell(tr,"Kurs","—");itemCell(tr,"Währung / Einheit","—");
    itemCell(tr,"Quelle / Handelsplatz",sourceLabel(error.provider));
    itemCell(tr,"Marktzeit","—");itemCell(tr,"Abgerufen",date(error.captured_at));itemCell(tr,"Datenalter","—");
    itemCell(tr,"ISIN",entry.isin);itemCell(tr,"Status","Fehler: "+error.code);fragment.append(tr);
  }
  function removeEntry(isin) {
    if (busy) return;
    const index=entries.findIndex(entry=>entry.isin===isin);
    if (index<0) return;
    entries.splice(index,1);save();paint();
  }
  function clearEntries() {
    if (busy || !entries.length || !window.confirm("Alle gespeicherten ISINs in diesem Browser löschen?")) return;
    entries=[];save();paint();
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
    if(confirmedTypes.has(result.instrument_type) && typeof result.instrument_type_source === "string" && result.instrument_type_source !== ""){
      entry.instrument_type=result.instrument_type;
      entry.instrument_type_source=result.instrument_type_source;
      entry.instrument_type_verified_at=typeof result.instrument_type_verified_at === "string" ? result.instrument_type_verified_at : null;
    }else if(result.instrument_type === "unknown" && result.instrument_type_source === "lang_schwarz_conflict"){
      entry.instrument_type="unknown";entry.instrument_type_source=result.instrument_type_source;entry.instrument_type_verified_at=null;
    }
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
    if(detailsToggle) detailsToggle.disabled=value;
    if(automationToggle) automationToggle.disabled=value;
    syncDeleteButtons();
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
      if (automationRoot) { automation.lastUpdatedAt=new Date().toISOString(); saveAutomation(); }
      save();paint();
      scheduleAutomation();
    }
  }
  async function refreshAll(button, automatic=false) {
    if(busy)return false;
    entries=restore();paint();
    const form=forms[0],list=form.parentElement.querySelector("[data-isin-steps]");
    if(list)list.replaceChildren();
    if(!entries.length){progress(form,"Keine gespeicherten ISINs. Es wurde keine Abfrage ausgelöst.");scheduleAutomation();return false;}
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
      setBusy(false);save();
      if (automationRoot) { automation.lastUpdatedAt=new Date().toISOString(); saveAutomation(); }
      paint();scheduleAutomation();
    }
    return true;
  }
  for(const form of forms) form.addEventListener("submit",event=>{event.preventDefault();submit(form);});
  for(const button of document.querySelectorAll("[data-isin-refresh]"))button.addEventListener("click",()=>refreshAll(button));
  for(const list of document.querySelectorAll("[data-isin-list]")) list.addEventListener("click",event=>{
    const button=event.target.closest("[data-isin-remove]");
    if(button) removeEntry(button.dataset.isinRemove);
  });
  for(const button of document.querySelectorAll("[data-isin-clear]")) button.addEventListener("click",clearEntries);
  if(detailsToggle) detailsToggle.addEventListener("click",()=>{if(busy)return;detailsOpen=!detailsOpen;paint();});
  if (automationRoot) {
    automationInterval.addEventListener("change",()=>{
      automation.intervalSeconds=clampInterval(automationInterval.value);
      automationInterval.value=String(automation.intervalSeconds);
      saveAutomation();paint();scheduleAutomation();
    });
    automationToggle.addEventListener("click",()=>{
      if (busy) return;
      automation.enabled=!automation.enabled;saveAutomation();paint();
      if (automation.enabled) runAutomaticCycle(); else clearAutomationTimer();
    });
    document.addEventListener("visibilitychange",()=>{
      if (document.visibilityState === "hidden") clearAutomationTimer();
      else { paint();scheduleAutomation(); }
    });
  }
  paint();
  if (automationRoot) scheduleAutomation();
  globalThis.MosaIsinLookup=Object.freeze({valid});
  globalThis.MosaIsinAutomation=Object.freeze({clampInterval,intervalFor,isBadenWuerttembergHoliday,dayMode});
}());
