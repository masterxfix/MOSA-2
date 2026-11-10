const fs=require('node:fs'),vm=require('node:vm'), assert=require('node:assert/strict');
class E{constructor(tag='div'){this.tagName=tag;this.children=[];this.dataset={};this.textContent='';this.attrs={};this.disabled=false;}
 append(...items){this.children.push(...items)} replaceChildren(...items){this.children=items.flatMap(e=>e.children??[e])} setAttribute(name,value){this.attrs[name]=value} addEventListener(event,fn){this[event]=fn} querySelector(sel){return this.map?.[sel]??null}}
const form=new E('form'),input=new E('input'),button=new E('button'),steps=new E('ol'),list=new E('ol'),counter=new E('p');
input.value='DE000A0JBPG2';form.map={'[data-isin-input]':input,'button[type=submit]':button};form.parentElement={querySelector:q=>q==='[data-isin-steps]'?steps:null};
counter.firstChild={textContent:'00'};
const document={querySelectorAll:s=>s==='[data-isin-form]'?[form]:s==='[data-isin-list]'?[list]:[],querySelector:s=>s==='[data-isin-count]'?counter:null,createElement:t=>new E(t),createDocumentFragment:()=>new E('fragment')};
const storage=new Map(),localStorage={getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)};
const calls=[];
async function fetch(url,opts){
  calls.push([url,opts]);const body=JSON.parse(opts.body);
  const keys=['lang_schwarz_quote','lang_schwarz_trade','tradegate_quote','tradegate_trade','boerse_frankfurt_trade','yahoo_home_market'];
  const records=keys.map((key,i)=>({status:'ok',isin:body.isin,provider:key,source:key,price:(5.4+i/100).toFixed(3),
    currency:i===5?'NOK':'EUR',quote_type:i===5?'Heimatmarktkurs':'Letzter Handel',
    market_at:'2026-11-02T12:30:00Z',captured_at:'2026-11-02T12:31:00Z'}));
  return {ok:true,body:null,json:async()=>({status:'ok',isin:body.isin,name:'PNE AG',records})};
}
const sandbox={document,localStorage,fetch,AbortController,Intl,Date,JSON,Number,String,Object,Array,Set,Math,Error,setTimeout,clearTimeout}; sandbox.globalThis=sandbox;
vm.runInNewContext(fs.readFileSync(__dirname+'/../assets/js/isin_quotes.js','utf8'),sandbox);
assert.equal(calls.length,0,'No automatic provider request on page load');
form.submit({preventDefault(){}});
setTimeout(()=>{assert.equal(calls.length,1,'One shared MOSA comparison per click');assert.equal(JSON.parse(calls[0][1].body).provider,'all');assert.equal(counter.firstChild.textContent,'01');assert.ok(storage.get('mosa2-isin-lookup-v1').includes('PNE AG'));assert.ok(steps.children.length>=7);assert.ok(storage.get('mosa2-isin-lookup-v1').includes('yahoo_home_market'));console.log('PASS client click -> four MOSA providers / six quote types; no page-load GET');},30);
