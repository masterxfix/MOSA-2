const fs=require('node:fs'),vm=require('node:vm'), assert=require('node:assert/strict');
class E{constructor(tag='div'){this.tagName=tag;this.children=[];this.dataset={};this.textContent='';this.attrs={};this.disabled=false;}
 append(...items){this.children.push(...items)} replaceChildren(...items){this.children=items.flatMap(e=>e.children??[e])} addEventListener(event,fn){this[event]=fn} querySelector(sel){return this.map?.[sel]??null}}
const form=new E('form'),input=new E('input'),button=new E('button'),steps=new E('ol'),list=new E('ol'),counter=new E('p');
input.value='DE000A0JBPG2';form.map={'[data-isin-input]':input,'button[type=submit]':button};form.parentElement={querySelector:q=>q==='[data-isin-steps]'?steps:null};
counter.firstChild={textContent:'00'};
const document={querySelectorAll:s=>s==='[data-isin-form]'?[form]:s==='[data-isin-list]'?[list]:[],querySelector:s=>s==='[data-isin-count]'?counter:null,createElement:t=>new E(t),createDocumentFragment:()=>new E('fragment')};
const storage=new Map(),localStorage={getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)};
const calls=[];
async function fetch(url,opts){calls.push([url,opts]);const body=JSON.parse(opts.body);return {ok:true,json:async()=>({status:'ok',isin:body.isin,provider:body.provider,name:'PNE AG',price:body.provider==='tradegate'?'5.475':'5.52',currency:'EUR',quote_type:body.provider==='tradegate'?'Mid (Geld/Brief)':'Letzter Kurs',market_at:'2026-11-02T12:30:00Z',captured_at:'2026-11-02T12:31:00Z',source:body.provider,stale:false})};}
const sandbox={document,localStorage,fetch,AbortController,Intl,Date,JSON,Number,String,Object,Array,Set,Math,Error,setTimeout,clearTimeout}; sandbox.globalThis=sandbox;
vm.runInNewContext(fs.readFileSync(__dirname+'/../assets/js/isin_quotes.js','utf8'),sandbox);
assert.equal(calls.length,0,'No automatic provider request on page load');
form.submit({preventDefault(){}});
setTimeout(()=>{assert.equal(calls.length,2,'Exactly one request per configured source');assert.deepEqual(calls.map(x=>JSON.parse(x[1].body).provider),['tradegate','frankfurt']);assert.equal(counter.firstChild.textContent,'01');assert.ok(storage.get('mosa2-isin-lookup-v1').includes('PNE AG'));assert.ok(steps.children.length>=5);console.log('PASS client click -> two providers and progress; no page-load GET');},30);
