// Offline execution of the shipped renderer; no network or market data.
const fs=require('node:fs'),vm=require('node:vm');
class Element {
  constructor(){this.dataset={};this.children=[];this.attributes={};this.textContent='';}
  append(child){this.children.push(child);}
  replaceChildren(fragment){this.children=fragment.children;}
  setAttribute(key,value){this.attributes[key]=value;}
}
const root=new Element(),body=new Element(),region=new Element(),summary=new Element(),timing=new Element();
root.querySelector=selector=>({'[data-market-rows]':body,'[data-market-region]':region,'[data-market-summary]':summary}[selector]);
const scenario=process.argv[3];let resolve,reject,requests=[],frames=[];
const context={document:{createElement:()=>new Element(),createDocumentFragment:()=>new Element(),querySelector:selector=>selector==='[data-market-view]'?root:timing},
  window:{innerWidth:390,innerHeight:844},AbortController,performance:{now:()=>912.4},requestAnimationFrame:fn=>frames.push(fn),setTimeout:()=>1,clearTimeout:()=>{},
  fetch:(url,options)=>{requests.push({url,method:options.method,cache:options.cache});return new Promise((a,b)=>{resolve=a;reject=b;});}};
vm.runInNewContext(fs.readFileSync(process.argv[2],'utf8'),context);
const initial={state:root.dataset.state,busy:region.attributes['aria-busy'],text:body.children[0].children[0].textContent};
const item={name:'Synthetic <asset>',source:'Source',venue:'Venue',status:scenario==='stale'?'stale':scenario==='missing'?'missing':'stored',price:'123456789012345678.1234567890',unit:'GBX',unit_version:'1',quantity_basis_amount:null,quantity_basis_unit:null,market_at:'2026-01-01 00:00:00.000000Z',observed_at:'2026-01-01 01:00:00.000000Z'};
if(scenario==='error')reject(Error('offline'));
else resolve({ok:true,json:async()=>({status:'ok',items:scenario==='empty'?[]:[scenario==='malformed'?{...item,price:12.3}:item]})});
setImmediate(()=>{
  while(frames.length)frames.shift()();
  process.stdout.write(JSON.stringify({initial,requests,state:root.dataset.state,busy:region.attributes['aria-busy'],summary:summary.textContent,
    rows:body.children.map(row=>({data:row.dataset,cells:row.children.map(td=>({text:td.textContent,data:td.dataset}))})),timing:timing.textContent,success:root.dataset.dataSuccess,
    decimals:['123.4500000000','0.0000000001','999999999999999999.9999999999','-1234.0000000000'].map(context.MosaMarket.decimal)}));
});
