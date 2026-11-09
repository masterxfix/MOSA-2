const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const cacheVersion='isin-20261109-clear-steps';
for(const file of ['marktdaten.html','index.html']){
  const html=fs.readFileSync(__dirname+'/../'+file,'utf8');
  assert.ok(html.includes('assets/js/isin_quotes.js?v='+cacheVersion),file+' uses the current ISIN script cache version');
}

class E {
  constructor(tag='div'){this.tagName=tag;this.children=[];this.dataset={};this.textContent='';this.disabled=false;this.events={};this.attributes={};}
  append(...items){this.children.push(...items);this.textContent=this.children.map(item=>item?.textContent??'').join('')}
  replaceChildren(...items){this.children=items.flatMap(item=>item.children??[item]);this.textContent=this.children.map(item=>item?.textContent??'').join('')}
  addEventListener(event,fn){this.events[event]=fn}
  setAttribute(name,value){this.attributes[name]=value;this[name]=value}
  querySelector(selector){return this.map?.[selector]??null}
}

const form=new E('form'),steps=new E('ol'),detailsToggle=new E('button'),table=new E('tbody');
form.parentElement={querySelector:selector=>selector==='[data-isin-steps]'?steps:null};
const document={
  querySelectorAll:selector=>selector==='[data-isin-form]'?[form]:selector==='[data-isin-table]'?[table]:[],
  querySelector:selector=>selector==='[data-isin-details-toggle]'?detailsToggle:null,
  createElement:tag=>new E(tag),
  createDocumentFragment:()=>new E('fragment')
};

const entries=[
  {isin:'US0000000001',name:'Alpha',instrument_type:'stock',quotes:[
    {isin:'US0000000001',provider:'lang_schwarz_quote',source:'Older market time',price:'10.00',currency:'EUR',quote_type:'Mid',market_at:'2026-11-08T22:00:00Z',captured_at:'2026-11-08T23:50:00Z'},
    {isin:'US0000000001',provider:'tradegate_trade',source:'Newest market time',price:'11.00',currency:'USD',quote_type:'Trade',market_at:'2026-11-08T23:00:00Z',captured_at:'2026-11-08T23:05:00Z'},
    {isin:'US0000000001',provider:'yahoo_home_market',source:'Later capture only',price:'12.00',currency:'GBP',quote_type:'Trade',market_at:'2026-11-08T21:00:00Z',captured_at:'2026-11-08T23:55:00Z'}
  ],errors:[]},
  {isin:'DE0000000002',name:'Beta',instrument_type:'stock',quotes:[
    {isin:'DE0000000002',provider:'tradegate_trade',source:'Old successful course',price:'5.00',currency:'EUR',quote_type:'Trade',market_at:'2026-11-07T00:00:00Z',captured_at:'2026-11-07T00:05:00Z',refresh_failed_at:'2026-11-08T10:00:00Z'}
  ],errors:[{provider:'yahoo_home_market',code:'SOURCE_TIMEOUT',captured_at:'2026-11-08T10:01:00Z'}]},
  {isin:'FR0000000003',name:'Gamma',instrument_type:'stock',quotes:[],errors:[{provider:'tradegate_trade',code:'NO_QUOTE',captured_at:'2026-11-08T10:02:00Z'}]}
];
const storage=new Map([['mosa2-isin-lookup-v1',JSON.stringify(entries)]]);
const localStorage={getItem:key=>storage.get(key),setItem:(key,value)=>storage.set(key,value),removeItem:key=>storage.delete(key)};
const sandbox={document,localStorage,Intl,Date,JSON,Number,String,Object,Array,Set,Math,Error,setTimeout,clearTimeout};sandbox.globalThis=sandbox;

vm.runInNewContext(fs.readFileSync(__dirname+'/../assets/js/isin_quotes.js','utf8'),sandbox);
assert.equal(table.children.length,3,'Standard view renders exactly one row per ISIN');
assert.ok(table.children[0].textContent.includes('11,00 USD'),'Latest successful course is selected by market time');
assert.ok(table.children[0].textContent.includes('Newest market time'),'Selected row keeps its source');
assert.ok(!table.children[0].textContent.includes('12,00'),'Later capture time does not override market time');
assert.ok(table.children[1].textContent.includes('Veraltet'),'Old successful course is marked stale');
assert.ok(!table.textContent.includes('SOURCE_TIMEOUT')&&!table.textContent.includes('NO_QUOTE'),'Provider errors are hidden by default');
assert.ok(table.children[2].textContent.includes('Kein erfolgreicher Kurs vorhanden'),'Missing successful course is explicit');
assert.equal(detailsToggle.textContent,'Alle Details anzeigen','Details start closed');
assert.equal(detailsToggle.attributes['aria-expanded'],'false','Details start collapsed');

detailsToggle.events.click();
assert.equal(detailsToggle.textContent,'Weniger anzeigen','Details toggle opens');
assert.equal(detailsToggle.attributes['aria-expanded'],'true','Details report expanded state');
assert.equal(table.children.length,7,'Detail view renders all quotes, errors and missing-state rows');
assert.ok(table.textContent.includes('SOURCE_TIMEOUT')&&table.textContent.includes('NO_QUOTE'),'Provider errors appear only in detail view');
assert.ok(table.textContent.includes('Later capture only'),'All saved provider results appear in detail view');

detailsToggle.events.click();
assert.equal(detailsToggle.textContent,'Alle Details anzeigen','Details toggle closes');
assert.equal(detailsToggle.attributes['aria-expanded'],'false','Details report collapsed state');
assert.equal(table.children.length,3,'Closing details returns to one row per ISIN');
console.log('PASS details: one-row L1 selection by market_at, stale/missing states, hidden errors, and toggle');
