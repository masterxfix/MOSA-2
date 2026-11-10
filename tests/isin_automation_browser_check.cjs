const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const cacheVersion='isin-20261110-manual';
const html=fs.readFileSync(__dirname+'/../marktdaten.html','utf8');
const indexHtml=fs.readFileSync(__dirname+'/../index.html','utf8');
assert.ok(html.includes('assets/js/isin_quotes.js?v='+cacheVersion),'marktdaten.html uses the manual cache version');
assert.ok(!html.includes('data-isin-automation'),'Market page has no automation control');
assert.ok(!indexHtml.includes('data-isin-automation'),'Index page has no second automation control or trigger');

class E {
  constructor(tag='div'){this.tagName=tag;this.children=[];this.dataset={};this.textContent='';this.disabled=false;this.events={};this.attributes={};this.value='';}
  append(...items){this.children.push(...items);this.textContent=this.children.map(item=>item?.textContent??'').join('');}
  replaceChildren(...items){this.children=items.flatMap(item=>item.children??[item]);this.textContent=this.children.map(item=>item?.textContent??'').join('');}
  addEventListener(event,fn){this.events[event]=fn;}
  setAttribute(name,value){this.attributes[name]=value;this[name]=value;}
  querySelector(selector){return this.map?.[selector]??null;}
}

const form=new E('form'),input=new E('input'),submit=new E('button'),refresh=new E('button'),steps=new E('ol'),table=new E('tbody');
submit.type='submit';input.value='DE0000000001';
form.map={'[data-isin-input]':input,'button[type=submit]':submit};
form.parentElement={querySelector:selector=>selector==='[data-isin-steps]'?steps:selector==='[data-isin-table]'?table:null};
const detailsToggle=new E('button');
const automationRoot=new E('div'),automationInterval=new E('input'),automationToggle=new E('button'),automationStatus=new E('p');
automationInterval.value='300';automationRoot.map={'[data-isin-automation-interval]':automationInterval,'[data-isin-automation-toggle]':automationToggle,'[data-isin-automation-status]':automationStatus};
const visibilityHandlers=[];
const document={visibilityState:'visible',querySelectorAll:selector=>selector==='[data-isin-form]'?[form]:selector==='[data-isin-refresh]'?[refresh]:selector==='[data-isin-table]'?[table]:[],querySelector:selector=>selector==='[data-isin-details-toggle]'?detailsToggle:selector==='[data-isin-automation]'?automationRoot:null,createElement:tag=>new E(tag),createDocumentFragment:()=>new E('fragment'),addEventListener:(event,fn)=>{if(event==='visibilitychange')visibilityHandlers.push(fn);}};
const initial=[{isin:'DE0000000001',name:'Test AG',instrument_type:'stock',quotes:[{isin:'DE0000000001',provider:'tradegate_trade',source:'Test',price:'10.00',currency:'EUR',quote_type:'Trade',market_at:'2026-11-07T10:00:00Z',captured_at:'2026-11-07T10:01:00Z'}],errors:[]}];
const storage=new Map([['mosa2-isin-lookup-v1',JSON.stringify(initial)],['mosa2-isin-automation-v1',JSON.stringify({intervalSeconds:300,enabled:true,lastUpdatedAt:'2000-01-01T00:00:00Z'})],['unrelated-key','keep']]);
const localStorage={getItem:key=>storage.get(key),setItem:(key,value)=>storage.set(key,value),removeItem:key=>storage.delete(key)};
const RealDate=Date;
class TestDate extends RealDate { constructor(...args){super(...(args.length?args:[TestDate.nowValue]));} static now(){return TestDate.nowValue;} static parse=value=>RealDate.parse(value); static UTC(...args){return RealDate.UTC(...args);} }
TestDate.nowValue=RealDate.parse('2026-11-08T12:00:00Z');
const providers=['lang_schwarz_quote','lang_schwarz_trade','tradegate_quote','tradegate_trade','boerse_frankfurt_trade','yahoo_home_market'];
function successResult(isin){return {status:'ok',isin,name:'Test AG',instrument_type:'stock',instrument_type_source:'lang_schwarz',instrument_type_verified_at:'2026-11-08T08:00:00Z',records:providers.map(provider=>({status:'ok',isin,provider,source:provider,price:'10.00',currency:'EUR',quote_type:'Trade',market_at:'2026-11-08T08:00:00Z',captured_at:'2026-11-08T08:01:00Z'}))};}
let timerId=0;const timers=new Map();
function fakeSetTimeout(fn,delay){const id=++timerId;const wrapped=async()=>{timers.delete(id);return fn();};timers.set(id,{fn:wrapped,delay});return id;}
function fakeClearTimeout(id){timers.delete(id);}
let calls=0,active=0,maxActive=0,holdNext=false,releaseNext=null;
async function fetch(_url, options){assert.equal(options.headers["X-MOSA2-Quote-Intent"],"manual");calls++;active++;maxActive=Math.max(maxActive,active);if(holdNext)await new Promise(resolve=>{releaseNext=resolve;});active--;return {ok:true,body:null,json:async()=>successResult('DE0000000001')};}
const sandbox={document,localStorage,fetch,AbortController,Intl,Date:TestDate,JSON,Number,String,Object,Array,Set,Math,Error,setTimeout:fakeSetTimeout,clearTimeout:fakeClearTimeout,window:{confirm:()=>true}};sandbox.globalThis=sandbox;
vm.runInNewContext(fs.readFileSync(__dirname+'/../assets/js/isin_quotes.js','utf8'),sandbox);

(async()=>{
  assert.equal(sandbox.MosaIsinAutomation,undefined);
  assert.equal(calls,0,'Persisted active setting cannot start a request');
  assert.equal(timers.size,0,'No recurring or initial timer');
  assert.equal(visibilityHandlers.length,0,'Tab activation cannot start a request');
  assert.deepEqual(automationToggle.events,{});
  assert.equal(storage.get('mosa2-isin-lookup-v1'),JSON.stringify(initial),'Initial cache remains untouched');
  await refresh.events.click();
  assert.equal(calls,1,'Manual refresh works with the protected endpoint');
  assert.equal(timers.size,0,'Manual refresh does not schedule a new cycle');
  assert.equal(storage.get('unrelated-key'),'keep');
  console.log('PASS manual only: legacy active setting ignored; cache and manual refresh intact');
})().catch(error=>{console.error(error);process.exit(1);});
