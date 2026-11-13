(function () {
  "use strict";
  const KEY = "mosa2-isin-lookup-v1";
  // No client-side provider catalog: the MOSA core defines response scopes.
  const sourceKey = value => typeof value==="string" && /^[a-z][a-z0-9_]{2,63}$/.test(value);
  const typeLabels = Object.freeze({stock:"Aktie",etf:"ETF",fund:"Fonds",other:"Sonstiges",unknown:"Unbekannt"});
  const confirmedTypes = new Set(["stock","etf","fund","other"]);
  const valid = value => typeof value === "string" && /^[A-Z]{2}[A-Z0-9]{9}[0-9]$/.test(value);
  const validQuote = (quote, isin) => Boolean(quote && quote.isin===isin && (quote.provider==="stored" || sourceKey(quote.provider))
    && typeof quote.price === "string" && /^\d+(?:\.\d{1,12})?$/.test(quote.price)
    && Number(quote.price)>0 && /^[A-Z]{3}$/.test(quote.currency)
    && typeof quote.market_at === "string" && Number.isFinite(Date.parse(quote.market_at))
    && typeof quote.captured_at === "string" && Date.parse(quote.market_at)<=Date.parse(quote.captured_at));
  let manualOwner = null, currentView = null;
  function mount(root) {
  const forms = [...root.querySelectorAll("[data-isin-form]")];
  if (!forms.length) return {dispose() {}};
  const scope = new AbortController();
  const listeners = {signal:scope.signal};
  const detailsToggle = root.querySelector("[data-isin-details-toggle]");
  const storedQuotes = new Map();
  const registeredAssets = new Map();
  const storedRoot=root===document ? document.querySelector("[data-isin-stored-quotes]") : root;
  const marketView=root.querySelector("[data-isin-market-view]");
  const dbRegistry=marketView?.dataset.marketRegistry!==undefined;
  const confirmDialog=root.querySelector("[data-isin-db-confirm]");
  const countdownLabel=root.querySelector("[data-isin-next-check]");
  let pendingDelete=null;
  const READ_INTERVAL=30000;
  const STORED_URL=marketView?"api/market.php?view=registered":"api/market.php?view=best";
  let storedStatus="loading", storedRead=null, nextStoredAt=null, storedTimer=null, storedStopped=false, readCount=0;
  let countdownTimer=null;
  let cancelRead = null;
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
        errors:Array.isArray(entry.errors)?entry.errors.filter(e=>e && (e.provider==="all" || sourceKey(e.provider)) && typeof e.code==="string")
          .slice(0,12).map(e=>({...e,source:typeof e.source==="string"&&e.source.length<=160?e.source:null})):[]}));
    } catch {return [];}
  }
  let entries = restore(), busy = Boolean(manualOwner), detailsOpen = false;
  const save = () => {try {
    if (entries.length) localStorage.setItem(KEY, JSON.stringify(entries));
    else localStorage.removeItem(KEY);
  } catch { /* Browser storage is optional. */ }};
  const priceFormat=new Intl.NumberFormat("de-DE",{minimumFractionDigits:2,maximumFractionDigits:10});
  const dateFormat=new Intl.DateTimeFormat("de-DE",{timeZone:"Europe/Berlin",dateStyle:"short",timeStyle:"medium"});
  const clockFormat=new Intl.DateTimeFormat("de-DE",{timeZone:"Europe/Berlin",timeStyle:"medium"});
  const berlinDay=new Intl.DateTimeFormat("en-CA",{timeZone:"Europe/Berlin",year:"numeric",month:"2-digit",day:"2-digit"});
  const fmtPrice = p => {
    const num=Number(p);
    return typeof p==="string" && /^\d+(?:\.\d{1,12})?$/.test(p) && Number.isFinite(num)
      ? priceFormat.format(num) : "—";
  };
  function date(value) {
    const stamp=Date.parse(value);
    if(!Number.isFinite(stamp))return "—";
    // The same calendar day in Berlin needs only the clock time.
    // Previous-day data still gets its date even at age 0 min around midnight.
    const sameBerlinDay=berlinDay.format(stamp)===berlinDay.format(Date.now());
    return (sameBerlinDay?clockFormat:dateFormat).format(stamp)+" Uhr";
  }
  function old(quote) {
    const stamp=Date.parse(quote.market_at);
    return Boolean(quote.refresh_failed_at) || (quote.provider==="stored" && storedStatus==="error")
      || !Number.isFinite(stamp) || Date.now()-stamp>1800000;
  }
  function availableQuotes(entry) {
    return [...entry.quotes, storedQuotes.get(entry.isin)].filter(quote=>validQuote(quote,entry.isin));
  }
  function best(entry) {
    return availableQuotes(entry).sort((a,b)=>compareTimestamp(b.market_at,a.market_at)
      || compareTimestamp(b.captured_at,a.captured_at))[0] || null;
  }
  function compareTimestamp(a,b) {
    const fraction=value=>Number((value.match(/\.(\d{4,6})Z$/)?.[1]||"").padEnd(6,"0").slice(3));
    return Date.parse(a)-Date.parse(b) || fraction(a)-fraction(b);
  }
  function updateQuote(previous, record) {
    if (!previous || compareTimestamp(record.market_at,previous.market_at)>0) return record;
    const {refresh_failed_at, ...retained}=previous;
    return {...retained, unchanged:true};
  }
  const tabActive=()=>!document.hidden && document.hasFocus();
  // One lightweight display clock. It reads the scheduler's exact monotonic
  // deadline; it never starts an additional network request.
  function showCountdown() {
    if(!countdownLabel || scope.signal.aborted)return;
    let label;
    if(storedStopped)label="Automatische Aktualisierung angehalten";
    else if(storedRead)label="Daten werden aktualisiert …";
    else if(!tabActive())label="Automatische Aktualisierung pausiert (Tab inaktiv)";
    else if(busy)label="Automatische Aktualisierung pausiert";
    else if(nextStoredAt===null)label="Automatische Aktualisierung startet …";
    else {
      const remaining=Math.max(0,Math.ceil((nextStoredAt-performance.now())/1000));
      label=remaining>0?"Nächste automatische Aktualisierung in "+remaining+" s"
        :"Automatische Aktualisierung startet …";
    }
    if(countdownLabel.textContent!==label)countdownLabel.textContent=label;
  }
  function tickCountdown() {
    if(countdownTimer!==null){clearTimeout(countdownTimer);countdownTimer=null;}
    if(scope.signal.aborted || !marketView || !countdownLabel)return;
    showCountdown();
    if(!storedStopped && tabActive() && !busy){
      countdownTimer=setTimeout(()=>{countdownTimer=null;tickCountdown();},1000);
    }
  }
  function scheduleStoredRead() {
    if(storedTimer!==null){clearTimeout(storedTimer);storedTimer=null;}
    if(scope.signal.aborted || !marketView || !storedRoot)return;
    const active=tabActive();
    if(storedRoot.dataset.isinTabActive!==String(active))storedRoot.dataset.isinTabActive=String(active);
    tickCountdown();
    if(storedStopped || !active || busy || storedRead)return;
    storedTimer=setTimeout(()=>{
      storedTimer=null;
      loadStoredQuotes();
    },nextStoredAt===null?0:Math.max(0,nextStoredAt-performance.now()));
  }
  function loadStoredQuotes() {
    if(scope.signal.aborted || !storedRoot || storedRead || storedStopped || busy
      || (marketView && (document.hidden || (nextStoredAt!==null && !tabActive()))))return;
    const firstRead=nextStoredAt===null;
    nextStoredAt=performance.now()+READ_INTERVAL;
    // MOSA's chart pattern: one same-origin read at a time, separate from provider lookups.
    const started=performance.now();
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),8000);
    cancelRead=()=>{clearTimeout(timer);controller.abort();};
    storedRead=Promise.resolve().then(async()=>{
      let httpStatus=0;
      try {
        const response=await fetch(STORED_URL,{credentials:"same-origin",cache:"no-store",
          signal:controller.signal,headers:{Accept:"application/json"}});
        httpStatus=response.status;
        if(httpStatus===401 || httpStatus===403)storedStopped=true;
        if(!response.ok)throw Error("MARKET_READ");
        const result=await response.json();
        if(result.status!=="ok" || !Array.isArray(result.items) || (marketView && !Array.isArray(result.registered)))throw Error("MARKET_READ");
        const fresh=new Map();
        for(const item of result.items) {
          if(!item || !["stored","stale"].includes(item.status) || !valid(item.isin))continue;
          const utc=value=>typeof value==="string"?value.replace(" ","T"):"";
          const source=item.venue?.toLowerCase().startsWith(item.source?.toLowerCase())?item.venue:item.source+" · "+item.venue;
          const quote={...item,source,provider:"stored",captured_at:utc(item.observed_at),market_at:utc(item.market_at)};
          if(validQuote(quote,item.isin))fresh.set(item.isin,quote);
        }
        registeredAssets.clear();
        for(const asset of result.registered || []) {
          if(!asset || !valid(asset.isin) || typeof asset.name!=="string" || !asset.name.trim())continue;
          const instrument_type=({equity:"stock",etf:"etf",fund:"fund",other:"other"})[asset.asset_class] || "unknown";
          registeredAssets.set(asset.isin,{isin:asset.isin,name:asset.name,instrument_type,quotes:[]});
        }
        storedQuotes.clear();
        for(const [isin,quote] of fresh)storedQuotes.set(isin,quote);
        storedStatus="ok";
      } catch { storedStatus="error"; }
      finally {
        clearTimeout(timer);
        cancelRead=null;
        storedRead=null;
        if(scope.signal.aborted)return;
        if(marketView){
          // Local timings distinguish background requests from initial page readiness.
          storedRoot.dataset.isinReadCount=String(++readCount);
          storedRoot.dataset.isinReadStartedMs=String(Math.round(started));
          storedRoot.dataset.isinReadDurationMs=String(Math.round(performance.now()-started));
          storedRoot.dataset.isinReadHttp=String(httpStatus);
        }
        paint();
        scheduleStoredRead();
        if(firstRead)requestAnimationFrame(()=>requestAnimationFrame(()=>{
          if(scope.signal.aborted)return;
          storedRoot.dataset.dataReadyMs=String(Math.round(performance.now()));
          storedRoot.dataset.dataSuccess=String(storedStatus==="ok");
        }));
      }
    });
    tickCountdown();
    return storedRead;
  }
  function age(quote) {
    const stamp=Date.parse(quote.market_at);
    return Number.isFinite(stamp) ? String(Math.max(0,Math.round((Date.now()-stamp)/60000)))+" Min." : "—";
  }
  function typeLabel(entry) {return typeLabels[entry.instrument_type] || typeLabels.unknown;}
  // Display-only abbreviation. ISIN and the full provider name remain untouched.
  // Fund/share-class legal suffixes are not useful as the primary table label.
  function shortName(entry) {
    const full=typeof entry.name==="string" && entry.name.trim()?entry.name.trim():entry.isin;
    if(entry.instrument_type!=="etf" && entry.instrument_type!=="fund")return full;
    const acc=/\b(?:acc|accumulating|accumulation|thesaurierend)\b/iu.test(full);
    const dist=/\b(?:dist|distributing|distribution|ausschüttend)\b/iu.test(full);
    const variant=acc?" (Acc)":dist?" (Dist)":"";
    const core=full.replace(/\s+(?:UCITS\s+)?ETF\b.*$/iu,"")
      .replace(/\s+UCITS\b.*$/iu,"")
      .replace(/\s*[\s(,-]*(?:Acc|Dist)\)?\s*$/iu,"")
      .replace(/[\s,\-–—]+$/u,"").trim();
    if(core.length<5 || core===entry.isin)return full;
    return core+variant;
  }
  const headings=["Wertpapier","Typ","Kurs","Währung / Einheit","Quelle / Handelsplatz","Marktzeit","Abgerufen","Datenalter","ISIN","Status"];
  function reconcileRows(tbody, rows, fullNames) {
    const actions=tbody.dataset.isinActions!==undefined;
    const existing=new Map(Array.from(tbody.children,row=>[row.dataset.isinRow,row]));
    let next=tbody.firstElementChild;
    for(const [key,status,values,removeIsin,dbIsin] of rows){
      let row=existing.get(key);
      existing.delete(key);
      if(!row){
        row=document.createElement("tr");
        row.dataset.isinRow=key;
        if(key==="empty")row.className="market-placeholder";
        for(let i=0;i<values.length;i++){
          const cell=document.createElement("td");
          cell.dataset.label=key==="empty"?"ISIN":headings[i];
          if(key==="empty")cell.colSpan=actions?11:10;
          if(i===2)cell.className="market-price";
          if(actions && i===headings.length-1)cell.className="isin-quote-status";
          row.append(cell);
        }
        if(actions && key!=="empty"){
          const cell=document.createElement("td");
          cell.className="isin-row-action";
          cell.dataset.label="Meine Liste";
          row.append(cell);
        }
      }
      if(status && row.dataset.status!==status)row.dataset.status=status;
      values.forEach((value,i)=>{if(row.cells[i].textContent!==value)row.cells[i].textContent=value;});
      if(key!=="empty"){
        const original=fullNames.get(values[8])||"";
        const tooltip=original && original!==values[0]?original:"";
        if(row.cells[0].title!==tooltip)row.cells[0].title=tooltip;
      }
      if(actions && key!=="empty"){
        const cell=row.cells[values.length];
        let local=[...cell.children].find(child=>child.dataset.isinRemove!==undefined);
        if(!removeIsin)local?.remove();
        else if(!local){
          local=document.createElement("button");
          local.type="button";
          local.className="isin-delete";
          local.dataset.isinRemove=removeIsin;
          local.textContent="Entfernen";
          local.setAttribute("aria-label",removeIsin+" nur aus diesem Browser entfernen");
          cell.append(local);
        }
        let remote=[...cell.children].find(child=>child.dataset.isinDbDelete!==undefined);
        if(!dbIsin)remote?.remove();
        else if(!remote){
          remote=document.createElement("button");
          remote.type="button";
          remote.className="isin-delete";
          remote.dataset.isinDbDelete=dbIsin;
          remote.textContent="Aus DB löschen";
          remote.setAttribute("aria-label",dbIsin+" und alle zugehörigen Daten aus der Testdatenbank löschen");
          cell.append(remote);
        }
      }
      if(row===next)next=next.nextElementSibling;
      else tbody.insertBefore(row,next);
    }
    for(const row of existing.values())row.remove();
  }
  function syncDeleteButtons() {
    for (const selector of ["[data-isin-remove]", "[data-isin-db-delete]"]) {
      for (const button of root.querySelectorAll(selector)) button.disabled = busy;
    }
    for (const button of root.querySelectorAll("[data-isin-db-clear]")) button.disabled = busy || storedStatus!=="ok";
  }
  function paint() {
    if(scope.signal.aborted)return;
    const ownIsins=new Set(entries.map(entry=>entry.isin));
    const visibleIsins=new Set([...ownIsins,...registeredAssets.keys(),...storedQuotes.keys()]);
    const number=root.querySelector("[data-isin-count]");if(number) number.firstChild.textContent=String(marketView?visibleIsins.size:entries.length).padStart(2,"0");
    for (const tbody of root.querySelectorAll("[data-isin-table]")) {
      const rows=[];
      const displayed=[...entries.map(entry=>{
        const registered=registeredAssets.get(entry.isin);
        return registered?{...entry,name:registered.name,instrument_type:registered.instrument_type}:entry;
      }),...[...registeredAssets.values()].filter(asset=>!ownIsins.has(asset.isin)),...[...storedQuotes.values()]
        .filter(quote=>!ownIsins.has(quote.isin) && !registeredAssets.has(quote.isin))
        .map(quote=>({isin:quote.isin,name:quote.name,quotes:[]}))];
      const fullNames=new Map(displayed.map(entry=>[entry.isin,entry.name||entry.isin]));
      for(const entry of displayed){
        const main=entry.isin+":main";
        const first=rows.length;
        if(!detailsOpen){
          const latest=(marketView?storedQuotes.get(entry.isin):null) || best(entry);
          rows.push(latest?quoteRow(main,entry,latest,true):missingRow(main,entry));
        }else{
          const quotes=availableQuotes(entry);
          if(!quotes.length)rows.push(missingRow(main,entry));
          for(const quote of quotes)rows.push(quoteRow(entry.isin+":quote:"+quote.provider,entry,quote,false));
          for(const error of entry.errors||[])rows.push(errorRow(entry,error));
        }
        if(ownIsins.has(entry.isin))rows[first][3]=entry.isin;
        if(dbRegistry && registeredAssets.has(entry.isin))rows[first][4]=entry.isin;
      }
      if(!rows.length)rows.push(["empty",null,["Noch keine ISIN eingegeben."]]);
      reconcileRows(tbody,rows,fullNames);
    }
    if(detailsToggle){
      const text=detailsOpen?"Weniger anzeigen":"Alle Details anzeigen";
      if(detailsToggle.textContent!==text)detailsToggle.textContent=text;
      if(detailsToggle.getAttribute("aria-expanded")!==String(detailsOpen))
        detailsToggle.setAttribute("aria-expanded",String(detailsOpen));
    }
    const count=marketView?visibleIsins.size:entries.length;
    const summary=count+" ISIN"+(count===1?"":"s")+
      (storedStatus==="loading"?" · Gespeicherte Kurse werden geladen":storedStatus==="error"
        ?" · Gespeicherte Kurse derzeit nicht verfügbar":" · Abgefragte und gespeicherte Kurse");
    for(const label of root.querySelectorAll("[data-isin-summary]")){
      if(label.textContent!==summary)label.textContent=summary;
    }
    syncDeleteButtons();
  }
  function quoteRow(key,entry,quote,compact) {
    const stale=old(quote);
    let status=quote.provider==="stored"?"Gespeichert":quote.unchanged?"Unverändert":"Kurs abgerufen";
    if(compact && marketView && quote.provider!=="stored" && storedStatus!=="loading")
      status+=storedStatus==="ok"?" · Kein neuer gespeicherter Kurs":" · Hintergrundabruf fehlgeschlagen";
    return [key,stale?"stale":"stored",[
      shortName(entry),typeLabel(entry),fmtPrice(quote.price)+" "+(quote.unit||quote.currency),
      (quote.unit && quote.unit!==quote.currency?quote.currency+" / "+quote.unit:quote.currency)+" · "+quote.quote_type,
      quote.source,date(quote.market_at),date(quote.captured_at),age(quote),entry.isin,(stale?"Veraltet · ":"")+status
    ]];
  }
  function missingRow(key,entry) {
    const status=registeredAssets.has(entry.isin)?"In DB registriert · Kein gespeicherter Kurs":"Kein erfolgreicher Kurs vorhanden";
    return [key,"missing",[shortName(entry),typeLabel(entry),"—","—","—","—","—","—",entry.isin,status]];
  }
  function errorRow(entry,error) {
    const missing=error.status==="unavailable";
    return [entry.isin+":error:"+error.provider,missing?"missing":"error",[
      shortName(entry),typeLabel(entry),"—","—",sourceLabel(error),"—",date(error.captured_at),"—",entry.isin,
      (missing?"Nicht verfügbar: ":"Fehler: ")+error.code
    ]];
  }
  function removeEntry(isin) {
    if (busy) return;
    const index=entries.findIndex(entry=>entry.isin===isin);
    if (index<0) return;
    entries.splice(index,1);save();paint();
  }
  // The collector owns the global advisory lock while collecting.
  // A 409 COLLECTOR_BUSY is temporary, not a locked database or invalid ISIN.
  // Keep the current CSRF token, retain the protected writer lock and retry
  // only registration; other conflicts and destructive requests never retry.
  function waitForCollector(ms) {
    return new Promise((resolve,reject)=>{
      if(scope.signal.aborted){reject(Error("Registrierung abgebrochen."));return;}
      const onAbort=()=>{clearTimeout(timer);reject(Error("Registrierung abgebrochen."));};
      const timer=setTimeout(()=>{
        scope.signal.removeEventListener("abort",onAbort);
        resolve();
      },ms);
      scope.signal.addEventListener("abort",onAbort,{once:true});
    });
  }
  async function registryCall(action, code, onBusy=null) {
    const endpoint="api/market_registry.php";
    const tokenReply=await fetch(endpoint,{
      method:"GET",credentials:"same-origin",cache:"no-store",signal:scope.signal,
      headers:{Accept:"application/json"}
    });
    if(!tokenReply.ok)throw Error("DB-Zugriff derzeit nicht verfügbar.");
    const token=await tokenReply.json();
    if(token.status!=="ok" || typeof token.csrf!=="string")throw Error("DB-Sitzung ungültig.");
    const started=performance.now(),maxRetryMs=90000;
    for(;;){
      if(scope.signal.aborted)throw Error("Registrierung abgebrochen.");
      const response=await fetch(endpoint,{
        method:"POST",credentials:"same-origin",cache:"no-store",signal:scope.signal,
        headers:{Accept:"application/json","Content-Type":"application/json","X-Requested-With":"XMLHttpRequest"},
        body:JSON.stringify({action,isin:code,csrf:token.csrf})
      });
      const result=await response.json();
      if(response.status===409 && result.code==="COLLECTOR_BUSY" && action==="register"){
        const left=maxRetryMs-(performance.now()-started);
        if(left<=0)throw Error("Der Kurs-Collector ist weiterhin beschäftigt. Die ISIN wurde nicht registriert. Bitte erneut versuchen.");
        onBusy?.();
        await waitForCollector(Math.min(3000,left));
        continue;
      }
      if(!response.ok){
        if(response.status===422 && action==="register")throw Error("Die ISIN-Prüfziffer stimmt nicht.");
        if(response.status===409){
          if(result.code==="INACTIVE_IDENTITY")throw Error("Die ISIN ist bereits inaktiv registriert. Bitte diesen Eintrag gesondert prüfen.");
          if(result.code==="COLLECTOR_BUSY")throw Error("Der Kurs-Collector arbeitet gerade. Der Vorgang wurde nicht ausgeführt.");
          if(["COLLECTOR_NOT_IDLE","ASSET_HAS_PENDING_WORK"].includes(result.code))
            throw Error("Für dieses Wertpapier läuft noch eine Verarbeitung. Löschen ist derzeit nicht möglich.");
          throw Error("Die ISIN kann aufgrund eines Registrierungskonflikts nicht verarbeitet werden.");
        }
        throw Error("Datenbankvorgang fehlgeschlagen ("+response.status+").");
      }
      return result;
    }
  }
  async function reloadDatabase() {
    nextStoredAt=null;
    await loadStoredQuotes();
  }
  async function changeRegistry(form,action,code) {
    if(busy || !dbRegistry)return;
    showError(form);
    setBusy(true);
    let result;
    try{
      if(storedRead)await storedRead;
      result=await registryCall(action,code,()=>showError(form,
        "Der Kurs-Collector arbeitet gerade. Die ISIN ist noch nicht registriert; M2 versucht es automatisch erneut …"));
      const expected=action==="register"?["registered","existing"]:["deleted","absent"];
      if(!expected.includes(result.status)||(action!=="purge_all"&&result.isin!==code))
        throw Error("Ungültige Datenbankbestätigung.");
      if(action==="purge"){
        entries=entries.filter(entry=>entry.isin!==code);
        save();
      }
    }catch(error){
      showError(form,error.message||"Datenbankvorgang fehlgeschlagen.");
      return;
    }finally{
      setBusy(false);
      paint();
    }
    await reloadDatabase();
    showError(form);
    if(result.readback!=="passed" || storedStatus!=="ok"
        || (action==="purge"&&(registeredAssets.has(code)||storedQuotes.has(code)))
        || (action==="register"&&!registeredAssets.has(code))
        || (action==="purge_all"&&storedQuotes.size!==0))
      showError(form,"Änderung ausgeführt, aber die unabhängige Datenbankprüfung ist noch offen.");
    else if(action==="register")form.querySelector("[data-isin-input]").value="";
  }
  function confirmDatabaseDelete(action, code) {
    if(busy || !dbRegistry || !confirmDialog || confirmDialog.open)return;
    const bulk=action==="purge_all";
    pendingDelete={action,code};
    confirmDialog.returnValue="";
    confirmDialog.querySelector("[data-isin-db-confirm-message]").textContent=bulk
      ?"Alle gespeicherten Testkurse und ihre Historie löschen? Die registrierten ISINs bleiben erhalten."
      :code+" und alle zugehörigen Daten aus der Testdatenbank löschen?";
    confirmDialog.querySelector("[data-isin-db-confirm-bulk]").hidden=!bulk;
    confirmDialog.querySelector("[data-isin-db-confirm-input]").value="";
    confirmDialog.showModal();
  }
  confirmDialog?.addEventListener("close",()=>{
    const request=pendingDelete;
    pendingDelete=null;
    if(!request || confirmDialog.returnValue!=="confirm")return;
    if(request.action==="purge_all" &&
        confirmDialog.querySelector("[data-isin-db-confirm-input]").value!=="ALLE TEST-MARKTDATEN"){
      showError(forms[0],"Bestätigung stimmt nicht. Es wurde nichts gelöscht.");
      return;
    }
    changeRegistry(forms[0],request.action,request.code);
  },listeners);
  function deleteFromDatabase(code) {
    if(registeredAssets.has(code))confirmDatabaseDelete("purge",code);
  }
  function clearDatabaseMarketData() {
    confirmDatabaseDelete("purge_all","ALLE TEST-MARKTDATEN");
  }
  function showError(form,message="") {
    const error=form.parentElement.querySelector("[data-isin-error]");
    if(!error)return;
    error.hidden=!message;
    error.textContent=message;
  }
  async function requestAll(code) {
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),90000);
    try {
      const response=await fetch("api/isin_quote.php",{
        method:"POST",credentials:"same-origin",cache:"no-store",signal:controller.signal,
        headers:{"Accept":"application/x-ndjson","Content-Type":"application/json","X-Requested-With":"XMLHttpRequest","X-MOSA2-Quote-Intent":"manual"},
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
  function sourceLabel(error) {
    return typeof error.source==="string" && error.source.length<=160 && error.source.trim()
      ?error.source : error.provider==="all"?"MOSA-Quellenvergleich":error.provider.replaceAll("_"," ");
  }
  function applyResult(entry,result) {
    if(!result||result.isin!==entry.isin||!Array.isArray(result.records)||result.records.length<1||result.records.length>16)
      throw Error("INVALID_RESULT");
    if(confirmedTypes.has(result.instrument_type) && typeof result.instrument_type_source === "string" && result.instrument_type_source !== ""){
      entry.instrument_type=result.instrument_type;
      entry.instrument_type_source=result.instrument_type_source;
      entry.instrument_type_verified_at=typeof result.instrument_type_verified_at === "string" ? result.instrument_type_verified_at : null;
    }else if(result.instrument_type === "unknown" && result.instrument_type_source === "lang_schwarz_conflict"){
      entry.instrument_type="unknown";entry.instrument_type_source=result.instrument_type_source;entry.instrument_type_verified_at=null;
    }
    let quotes=entry.quotes.slice();
    let errors=entry.errors.filter(error=>error.provider!=="all");
    const seen=new Set();let successful=0,unchanged=0;
    for(const record of result.records){
      if(!record||!sourceKey(record.provider)||seen.has(record.provider))throw Error("INVALID_PROVIDER_RESULT");
      seen.add(record.provider);
      if(record.status==="ok" && validQuote(record,entry.isin)){
        const previous=quotes.find(quote=>quote.provider===record.provider);
        const accepted=updateQuote(previous,record);
        quotes=quotes.filter(quote=>quote.provider!==record.provider);quotes.push(accepted);
        errors=errors.filter(error=>error.provider!==record.provider);
        if (accepted.unchanged) unchanged++; else successful++;
      }else{
        const reason=typeof record.code==="string"?record.code:"QUOTE_UNAVAILABLE";
        const capturedAt=typeof record.captured_at==="string"?record.captured_at:new Date().toISOString();
        quotes=quotes.map(quote=>quote.provider===record.provider?{...quote,refresh_failed_at:capturedAt}:quote);
        errors=errors.filter(error=>error.provider!==record.provider);
        errors.push({provider:record.provider,source:typeof record.source==="string"&&record.source.length<=160?record.source:null,
          status:record.status,code:reason,captured_at:capturedAt});
      }
    }
    entry.quotes=quotes;entry.errors=errors;
    if(typeof result.name==="string"&&result.name)entry.name=result.name;
    return {successful,unchanged};
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
    for(const button of root.querySelectorAll("[data-isin-refresh]"))button.disabled=value;
    if(detailsToggle) detailsToggle.disabled=value;
    syncDeleteButtons();
    scheduleStoredRead();
  }
  const view = () => {
    entries=restore();setBusy(false);paint();
    if(!marketView && nextStoredAt===null)loadStoredQuotes();
  };
  function finishManual() {
    manualOwner=null;
    if(currentView && currentView!==view)currentView();
  }
  async function submit(form) {
    if(busy || manualOwner)return;
    const code=form.querySelector("[data-isin-input]").value.trim().toUpperCase();
    showError(form);
    if(!valid(code)){showError(form,"Ungültige ISIN. Bitte zwölf Zeichen einschließlich Prüfziffer eingeben.");return;}
    if(dbRegistry)return changeRegistry(form,"register",code);
    let entry=entries.find(e=>e.isin===code);
    if(!entry){
      if(entries.length>=30){showError(form,"Die Liste enthält bereits 30 ISINs.");return;}
      entry={isin:code,name:null,quotes:[],errors:[]};entries.unshift(entry);
    }
    manualOwner=view;setBusy(true);
    save();paint();
    try{
      if(storedRead)await storedRead;
      const result=await requestAll(code);
      const outcome=applyResult(entry,result);save();paint();
      if(!outcome.successful && !outcome.unchanged)
        showError(form,"Kein Anbieter hat einen bestätigten Kurs geliefert. Es wird kein alter Wert als aktuell ausgegeben.");
    }catch(error){
      const reason=error.name==="AbortError"?"Zeitüberschreitung":error.message||"Abfrage fehlgeschlagen";
      markRequestFailure(entry,reason);showError(form,"Quellenvergleich nicht abgeschlossen: "+reason);
    }finally{
      setBusy(false);
      save();paint();
      finishManual();
    }
  }
  async function refreshAll() {
    if(busy || manualOwner)return false;
    if(dbRegistry)return reloadDatabase();
    entries=restore();paint();
    const form=forms[0];
    showError(form);
    if(!entries.length)return false;
    const snapshot=entries.slice();let failed=false;
    manualOwner=view;setBusy(true);
    try{
      if(storedRead)await storedRead;
      for(const entry of snapshot){
        try{
          const result=await requestAll(entry.isin);
          const outcome=applyResult(entry,result);
          if(!outcome.successful && !outcome.unchanged)failed=true;
        }catch(error){
          failed=true;
          const reason=error.name==="AbortError"?"Zeitüberschreitung":error.message||"Abfrage fehlgeschlagen";
          markRequestFailure(entry,reason);
        }
        save();paint();
      }
      if(failed)showError(form,"Mindestens eine Kursabfrage konnte nicht erfolgreich aktualisiert werden.");
    }finally{
      setBusy(false);save();
      paint();
      finishManual();
    }
    return true;
  }
  for(const form of forms) form.addEventListener("submit",event=>{event.preventDefault();submit(form);},listeners);
  for(const button of root.querySelectorAll("[data-isin-refresh]"))button.addEventListener("click",refreshAll,listeners);
  for(const table of root.querySelectorAll("[data-isin-table]")) table.addEventListener("click",event=>{
    const button=event.target.closest("[data-isin-remove]");
    if(button) removeEntry(button.dataset.isinRemove);
    const remote=event.target.closest("[data-isin-db-delete]");
    if(remote)deleteFromDatabase(remote.dataset.isinDbDelete);
  },listeners);
  for(const button of root.querySelectorAll("[data-isin-db-clear]")) button.addEventListener("click",clearDatabaseMarketData,listeners);
  if(detailsToggle) detailsToggle.addEventListener("click",()=>{if(busy)return;detailsOpen=!detailsOpen;paint();},listeners);
  if(marketView){
    document.addEventListener("visibilitychange",scheduleStoredRead,listeners);
    window.addEventListener("focus",scheduleStoredRead,listeners);
    window.addEventListener("blur",scheduleStoredRead,listeners);
    window.addEventListener("storage",event=>{
      if(busy || (event.key!==KEY && event.key!==null))return;
      entries=restore();paint();scheduleStoredRead();
    },listeners);
  }
  currentView=view;
  if(busy)setBusy(true);
  paint();
  const ready=loadStoredQuotes();
  return {ready,dispose(){
    scope.abort();
    if(storedTimer!==null)clearTimeout(storedTimer);
    if(countdownTimer!==null)clearTimeout(countdownTimer);
    cancelRead?.();
    if(currentView===view)currentView=null;
  }};
  }
  globalThis.MosaIsinLookup=Object.freeze({valid,mount});
  if (!document.querySelector("[data-site-shell]")) mount(document);
}());
