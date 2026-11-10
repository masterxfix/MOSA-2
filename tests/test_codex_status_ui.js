const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const code = fs.readFileSync(require('node:path').join(__dirname,'../assets/js/codex_status.js'),'utf8');
const dot = {dataset:{}, attrs:{},title:'',setAttribute(k,v){this.attrs[k]=v;}};
const handlers = {};
const queue = [
  {status:200,ok:true,json:async()=>({contract_version:'mosa2_codex_status_v1',state:'running'})},
  {status:200,ok:true,json:async()=>({contract_version:'mosa2_codex_status_v1',state:'idle'})},
  {status:200,ok:true,json:async()=>({contract_version:'mosa2_codex_status_v1',state:'unavailable'})},
  {status:200,ok:true,json:async()=>({contract_version:'mosa2_codex_status_v1',state:'invalid'})},
  {status:401,ok:false}
];
let calls=0;
let scheduled;
const document={hidden:false,querySelector(){return dot;},addEventListener(k,fn){handlers[k]=fn;}};
const window={addEventListener(k,fn){handlers[k]=fn;}};
vm.runInNewContext(code,{document,window,performance:{now:()=>120},fetch:async()=>{calls++;return queue.shift()},
  setTimeout:(fn,ms)=>{assert.equal(ms,5000);scheduled=fn;return 1},clearTimeout:()=>{},Error});
const flush = async()=>{for(let i=0;i<12;i++)await Promise.resolve();};
(async()=>{
 await flush();assert.equal(dot.dataset.state,'running');assert.equal(dot.title,'Codex arbeitet');assert.equal(dot.dataset.readyMs,'120');
 scheduled();await flush();assert.equal(dot.dataset.state,'idle');assert.equal(dot.attrs['aria-label'],'Kein aktiver Codex-Auftrag');
 scheduled();await flush();assert.equal(dot.dataset.state,'unavailable');assert.equal(dot.attrs['aria-label'],'Codex-Status unbekannt');
 handlers.focus();await flush();assert.equal(dot.dataset.state,'unavailable');
 handlers.focus();await flush();assert.equal(dot.dataset.state,'unavailable');assert.equal(dot.attrs['aria-hidden'],undefined);const n=calls;
 handlers.focus();await flush();assert.equal(calls,n,'401 stops polling');
 console.log('Codex UI: 5 checks OK');
})().catch(e=>{console.error(e);process.exitCode=1});
