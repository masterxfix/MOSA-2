const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const cacheVersion='isin-20261108-automation';
const html=fs.readFileSync(__dirname+'/../marktdaten.html','utf8');
const indexHtml=fs.readFileSync(__dirname+'/../index.html','utf8');
assert.ok(html.includes('assets/js/isin_quotes.js?v='+cacheVersion),'marktdaten.html uses the automation cache version');
assert.ok(html.includes('data-isin-automation-interval')&&html.includes('data-isin-automation-toggle'),'Automation controls are present');
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
const storage=new Map([['mosa2-isin-lookup-v1',JSON.stringify(initial)],['mosa2-isin-automation-v1',JSON.stringify({intervalSeconds:300,enabled:false,lastUpdatedAt:'2000-01-01T00:00:00Z'})],['unrelated-key','keep']]);
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
async function fetch(){calls++;active++;maxActive=Math.max(maxActive,active);if(holdNext)await new Promise(resolve=>{releaseNext=resolve;});active--;return {ok:true,body:null,json:async()=>successResult('DE0000000001')};}
const sandbox={document,localStorage,fetch,AbortController,Intl,Date:TestDate,JSON,Number,String,Object,Array,Set,Math,Error,setTimeout:fakeSetTimeout,clearTimeout:fakeClearTimeout,window:{confirm:()=>true}};sandbox.globalThis=sandbox;
vm.runInNewContext(fs.readFileSync(__dirname+'/../assets/js/isin_quotes.js','utf8'),sandbox);
const calendar=sandbox.MosaIsinAutomation;
assert.equal(calendar.clampInterval(4),5,'Interval lower bound clamps to 5 seconds');
assert.equal(calendar.clampInterval(301),300,'Interval upper bound clamps to 300 seconds');
assert.equal(calendar.intervalFor(new Date('2026-11-09T10:00:00+01:00'),5),5,'Monday uses configured interval');
assert.equal(calendar.intervalFor(new Date('2026-11-07T10:00:00+01:00'),300),3600,'Saturday uses fixed 60-minute interval');
assert.equal(calendar.intervalFor(new Date('2026-04-03T10:00:00+02:00'),300),3600,'Good Friday uses fixed 60-minute interval');
assert.equal(calendar.intervalFor(new Date('2026-04-06T10:00:00+02:00'),300),3600,'Easter Monday is calculated as a Baden-Württemberg holiday');
assert.equal(calendar.intervalFor(new Date('2026-05-14T10:00:00+02:00'),300),3600,'Ascension Day is calculated as a Baden-Württemberg holiday');
assert.equal(calendar.intervalFor(new Date('2026-05-15T10:00:00+02:00'),300),300,'Following Friday returns to configured interval');

(async()=>{
  assert.equal(automationToggle.textContent,'Automatik starten','Automation starts inactive');
  await automationInterval.events.change();
  assert.equal(automationInterval.value,'300','Valid interval is retained');
  automationInterval.value='4';await automationInterval.events.change();
  assert.equal(automationInterval.value,'5','Changed interval is clamped and saved');
  automationInterval.value='300';await automationInterval.events.change();
  await automationToggle.events.click();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(JSON.parse(storage.get('mosa2-isin-automation-v1')).enabled,true,'Start persists activation');
  assert.equal(calls,1,'Start performs one automatic cycle for saved ISINs');
  assert.equal(maxActive,1,'Automatic cycle has no overlapping provider request');
  assert.ok(JSON.parse(storage.get('mosa2-isin-automation-v1')).lastUpdatedAt,'Automatic cycle persists last update');
  const scheduled=[...timers.values()].find(timer=>timer.delay>=5000);
  assert.ok(scheduled,'Completed cycle schedules the next run');
  holdNext=true;
  TestDate.nowValue+=3601000;
  const firstRun=scheduled.fn();
  await Promise.resolve();await Promise.resolve();
  assert.equal(active,1,'A scheduled cycle marks the existing run busy');
  await scheduled.fn();
  assert.equal(calls,2,'A second timer signal does not start a parallel cycle');
  holdNext=false;releaseNext();await firstRun;
  assert.equal(maxActive,1,'Automatic cycles remain non-overlapping');
  document.visibilityState='hidden';visibilityHandlers[0]();assert.equal(timers.size,0,'Hidden tab pauses its timer');
  document.visibilityState='visible';visibilityHandlers[0]();assert.ok(timers.size>0,'Returning to a visible tab resumes without a catch-up series');
  await automationToggle.events.click();
  assert.equal(JSON.parse(storage.get('mosa2-isin-automation-v1')).enabled,false,'Stop persists deactivation');
  assert.equal(timers.size,0,'Stopping clears the pending timer');
  assert.equal(storage.get('unrelated-key'),'keep','Automation leaves unrelated LocalStorage keys untouched');
  console.log('PASS automation: bounds, Baden-Württemberg holidays, mode switching, persistence, pause/resume, and no overlap');
})().catch(error=>{console.error(error);process.exit(1);});
