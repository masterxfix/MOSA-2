const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const cacheVersion='overview-market-1';
for(const file of ['marktdaten.html']){
  const html=fs.readFileSync(__dirname+'/../'+file,'utf8');
  assert.ok(html.includes('assets/js/isin_quotes.js?v='+cacheVersion),file+' uses the current ISIN script cache version');
  assert.doesNotMatch(html,/data-isin-steps|class="isin-steps"/,file+' has no progress list');
  assert.match(html,/<p[^>]*data-isin-error[^>]*role="status"[^>]*hidden/);
}

const {E}=require('./fixtures/isin_dom.cjs');

const form=new E('form'),input=new E('input'),submit=new E('button'),refresh=new E('button'),clear=new E('button'),table=new E('tbody');
table.dataset.isinActions='';
const removeButtons=()=>table.children.map(row=>row.cells[10]?.firstElementChild).filter(Boolean);
submit.type='submit';refresh.type='button';input.value='CNE100000296';
form.map={'[data-isin-input]':input,'button[type=submit]':submit};
const document={
  querySelectorAll:selector=>selector==='[data-isin-form]'?[form]:selector==='[data-isin-refresh]'?[refresh]:selector==='[data-isin-clear]'?[clear]:selector==='[data-isin-remove]'?removeButtons():selector==='[data-isin-table]'?[table]:[],
  querySelector:()=>null,
  createElement:tag=>new E(tag),
  createDocumentFragment:()=>new E('fragment')
};

const oldDroneShield={provider:'tradegate_quote',source:'Tradegate BSX · Geld/Brief',price:'1.0000000000',currency:'EUR',quote_type:'Mid (Geld/Brief)',market_at:'2026-11-02T12:00:00Z',captured_at:'2026-11-02T12:01:00Z',isin:'AU000000DRO2'};
const oldEtf={provider:'boerse_frankfurt_trade',source:'Börse Frankfurt · letzter Handel',price:'5.0000000000',currency:'EUR',quote_type:'Letzter Handel',market_at:'2026-11-02T12:02:00Z',captured_at:'2026-11-02T12:03:00Z',isin:'IE00BMYDM794'};
const initial=[{isin:'AU000000DRO2',name:'DroneShield',quotes:[oldDroneShield],errors:[]},{isin:'IE00BMYDM794',name:'L&G Hydrogen Economy ETF',quotes:[oldEtf],errors:[]}];
const storage=new Map([['mosa2-isin-lookup-v1',JSON.stringify(initial)],['unrelated-key','keep']]),localStorage={getItem:key=>storage.get(key),setItem:(key,value)=>storage.set(key,value),removeItem:key=>storage.delete(key)};
let confirmCalls=0;
const errorStatus=new E('p');errorStatus.hidden=true;
form.parentElement={querySelector:selector=>selector==='[data-isin-error]'?errorStatus:null};
const calls=[];let active=0,maxActive=0;
const providers=['lang_schwarz_quote','lang_schwarz_trade','tradegate_quote','tradegate_trade','boerse_frankfurt_trade','yahoo_home_market'];
function successResult(isin,name){return {status:'ok',isin,name,instrument_type:'stock',instrument_type_source:'lang_schwarz',instrument_type_verified_at:'2026-11-03T08:01:00Z',records:providers.map((provider,index)=>({status:'ok',isin,provider,source:provider,price:(10+index/10).toFixed(3),currency:'EUR',quote_type:'Letzter Handel',market_at:'2026-11-03T08:00:00Z',captured_at:'2026-11-03T08:01:00Z'}))};}
function failedResult(isin,name){return {status:'error',isin,name,instrument_type:'etf',instrument_type_source:'lang_schwarz',instrument_type_verified_at:'2026-11-03T08:02:00Z',records:providers.map(provider=>({status:'error',isin,provider,code:'SOURCE_TIMEOUT',captured_at:'2026-11-03T08:02:00Z'}))};}
async function fetch(url,options){
  const body=JSON.parse(options.body);calls.push({url,body});active++;maxActive=Math.max(maxActive,active);
  assert.equal(options.method,'POST');assert.equal(body.provider,'all');
  assert.equal(refresh.disabled,true,'Refresh is disabled during an update');assert.equal(submit.disabled,true,'OK is disabled during an update');
  assert.ok(removeButtons().length && removeButtons().every(button=>button.disabled),'Single-delete buttons are disabled during an update');
  assert.equal(clear.disabled,true,'Clear-all is disabled during an update');
  await new Promise(setImmediate);active--;
  return {ok:true,body:null,json:async()=>body.isin==='AU000000DRO2'?successResult(body.isin,'DroneShield'):body.isin==='IE00BMYDM794'?failedResult(body.isin,'L&G Hydrogen Economy ETF'):successResult(body.isin,'BYD')};
}

const sandbox={document,localStorage,fetch,AbortController,Intl,Date,JSON,Number,String,Object,Array,Set,Math,Error,setTimeout,clearTimeout,window:{confirm:()=>{confirmCalls++;return true;}}};sandbox.globalThis=sandbox;
(async()=>{
  vm.runInNewContext(fs.readFileSync(__dirname+'/../assets/js/isin_quotes.js','utf8'),sandbox);
  assert.equal(calls.length,0,'No provider request is made on page load');
  assert.equal(typeof refresh.events.click,'function','Refresh button has a click handler');
  await refresh.events.click();
  assert.equal(calls.length,2,'Exactly one request per saved ISIN');
  assert.equal(maxActive,1,'Saved ISINs are requested sequentially');
  const stored=JSON.parse(storage.get('mosa2-isin-lookup-v1'));
  assert.deepEqual(stored.map(entry=>entry.isin),['AU000000DRO2','IE00BMYDM794'],'ISINs remain unique and ordered');
  assert.equal(stored[0].name,'DroneShield');assert.equal(stored[0].quotes.length,6,'All six existing quote records remain available');
  assert.equal(stored[0].quotes.find(quote=>quote.provider==='tradegate_quote').price,'10.200');
  assert.equal(stored[1].name,'L&G Hydrogen Economy ETF');
  assert.equal(stored[0].instrument_type,'stock');
  assert.equal(stored[1].instrument_type,'etf');
  assert.ok(table.textContent.includes('Aktie')&&table.textContent.includes('ETF'),'L1 table renders the verified type labels');
  const retained=stored[1].quotes.find(quote=>quote.provider==='boerse_frankfurt_trade');
  assert.equal(retained.market_at,oldEtf.market_at,'Failed refresh keeps the old market timestamp');
  assert.equal(retained.captured_at,oldEtf.captured_at,'Failed refresh keeps the old capture timestamp');
  assert.ok(retained.refresh_failed_at,'Failed refresh marks the retained quote as stale');
  assert.equal(stored[1].errors[0].code,'SOURCE_TIMEOUT','The actual provider error is stored');
  assert.equal(errorStatus.textContent,'Mindestens eine Kursabfrage konnte nicht erfolgreich aktualisiert werden.');

  const callsBeforeDelete=calls.length;
  const firstRemove=removeButtons()[0];
  await table.events.click({target:{closest:()=>firstRemove}});
  assert.equal(calls.length,callsBeforeDelete,'Single deletion makes no provider request');
  assert.equal(JSON.parse(storage.get('mosa2-isin-lookup-v1')).length,1,'Single deletion persists the remaining list');
  assert.equal(storage.get('unrelated-key'),'keep','Single deletion leaves other LocalStorage keys untouched');
  assert.ok(!table.textContent.includes('DroneShield'),'Single deletion updates the table immediately');

  vm.runInNewContext(fs.readFileSync(__dirname+'/../assets/js/isin_quotes.js','utf8'),sandbox);
  assert.equal(JSON.parse(storage.get('mosa2-isin-lookup-v1')).length,1,'Single deletion survives reload');

  form.events.submit({preventDefault(){}});
  await new Promise(setImmediate);
  assert.equal(calls.length,3,'The existing OK flow still starts one shared request');
  assert.equal(calls[2].body.isin,'CNE100000296');
  assert.equal(JSON.parse(storage.get('mosa2-isin-lookup-v1')).length,2,'OK adds the new ISIN without duplicating saved entries');
  const persistedAfterReload=JSON.parse(storage.get('mosa2-isin-lookup-v1'));
  vm.runInNewContext(fs.readFileSync(__dirname+'/../assets/js/isin_quotes.js','utf8'),sandbox);
  assert.equal(calls.length,3,'Reload does not trigger an automatic provider request');
  assert.equal(JSON.parse(storage.get('mosa2-isin-lookup-v1'))[1].quotes[0].captured_at,persistedAfterReload[1].quotes[0].captured_at,'Stored quotes survive reload');
  await clear.events.click();
  assert.equal(confirmCalls,1,'Clear-all asks for exactly one confirmation');
  assert.equal(calls.length,3,'Clear-all makes no provider request');
  assert.equal(storage.has('mosa2-isin-lookup-v1'),false,'Clear-all removes only the ISIN LocalStorage key');
  assert.equal(storage.get('unrelated-key'),'keep','Clear-all leaves other LocalStorage keys untouched');
  assert.equal(clear.disabled,true,'Clear-all is disabled after the list is empty');
  storage.set('mosa2-isin-lookup-v1','[]');
  await refresh.events.click();
  assert.equal(calls.length,3,'An empty saved list triggers no provider request');
  assert.equal(errorStatus.hidden,true,'Empty refresh does not show an error');
  input.value='UNGÜLTIG';
  form.events.submit({preventDefault(){}});
  await new Promise(setImmediate);
  assert.equal(calls.length,3,'Invalid ISIN does not contact a provider');
  assert.equal(errorStatus.hidden,false);
  assert.match(errorStatus.textContent,/Ungültige ISIN/);

  input.value='AU000000DRO2';
  form.events.submit({preventDefault(){}});
  await new Promise(setImmediate);
  assert.equal(calls.length,4,'OK works without a progress list');
  assert.equal(errorStatus.hidden,true,'A successful query clears the previous error');
  assert.match(table.textContent,/DroneShield.*10,00 EUR/);

  input.value='IE00BMYDM794';
  form.events.submit({preventDefault(){}});
  await new Promise(setImmediate);
  assert.equal(calls.length,5);
  assert.equal(errorStatus.hidden,false);
  assert.match(errorStatus.textContent,/Kein Anbieter hat einen bestätigten Kurs geliefert/);
  await refresh.events.click();
  assert.equal(calls.length,7,'Refresh works without a progress list');
  assert.equal(errorStatus.hidden,false);
  assert.equal(errorStatus.textContent,'Mindestens eine Kursabfrage konnte nicht erfolgreich aktualisiert werden.');
  assert.match(table.textContent,/DroneShield.*10,00 EUR/);
  console.log('PASS refresh and OK: sequential requests, persistence, one inline error at a time');
})().catch(error=>{console.error(error);process.exit(1)});
