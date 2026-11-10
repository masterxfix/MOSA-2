// Offline execution of the shipped Fundamentals renderer; no network or database.
const fs=require('node:fs'),vm=require('node:vm');
class Element {
  constructor(tag='div'){this.tag=tag;this.dataset={};this.children=[];this.attributes={};this.textContent='';this.className='';this.handlers={};}
  append(...children){this.children.push(...children);}
  replaceChildren(...children){this.children=children.flatMap(child=>child.tag==='fragment'?child.children:[child]);}
  setAttribute(key,value){this.attributes[key]=String(value);}
  addEventListener(name,handler){this.handlers[name]=handler;}
  click(){if(this.handlers.click)this.handlers.click();}
  querySelectorAll(selector){return selector==='button'?this.children.filter(child=>child.tag==='button'):[];}
}
const root=new Element('main'),assets=new Element('aside'),detail=new Element('div'),status=new Element('span'),summary=new Element('p'),total=new Element('span');
root.querySelector=selector=>({'[data-fundamental-assets]':assets,'[data-fundamental-detail]':detail,'[data-fundamental-status]':status,'[data-fundamental-summary]':summary,'[data-fundamental-total]':total}[selector]);
const scenario=process.argv[3];let resolve;const requests=[];
const context={document:{createElement:tag=>new Element(tag),createDocumentFragment:()=>new Element('fragment'),querySelector:selector=>selector==='[data-fundamentals-view]'?root:null},
  AbortController, setTimeout:()=>1, clearTimeout:()=>{}, fetch:(url,options)=>{requests.push([url,options.method]);return new Promise(a=>{resolve=a;});}};
vm.runInNewContext(fs.readFileSync(process.argv[2],'utf8'),context);
const fact=(metric,metric_name,value,year,current=false)=>({observation_id:metric+year,metric_key:metric,metric_name,value,period_type:'fy',fiscal_year:String(year),fiscal_quarter:null,period_start:year+'-01-01',period_end:year+'-12-31',unit_key:'CNY_THOUSAND',unit_name:'CNY thousands',currency:'CNY',source:'HKEX annual report',source_url:'https://example.invalid',captured_at:'2026-11-02 12:00:00.000000Z',fetch_id:'100',field_path:'facts/'+metric+'/'+year,evidence_sha256:'a'.repeat(64),current});
const data={status:'ok',as_of:'2026-11-02 12:30:00.000000',totals:{assets:2,fundamental_observations:4,fundamental_current:2},items:[
  {name:'BYD',isin:'CNE100000296',observations:[fact('revenue','Umsatz','803964958',2025,true),fact('revenue','Umsatz','777102455',2024)],current:[{metric_key:'revenue',period_type:'fy',fiscal_year:'2025',fiscal_quarter:null,period_start:'2025-01-01',period_end:'2025-12-31',observation_id:'revenue2025',value:'803964958',unit_key:'CNY_THOUSAND',unit_version:'1',updated_at:'2026-11-02 12:00:00.000000Z'}]},
  {name:'Ubtech Robotics',isin:'CNE100006CQ4',observations:[fact('revenue','Umsatz','2000999',2025,true),fact('revenue','Umsatz','1305361',2024)],current:[{metric_key:'revenue',period_type:'fy',fiscal_year:'2025',fiscal_quarter:null,period_start:'2025-01-01',period_end:'2025-12-31',observation_id:'revenue2025',value:'2000999',unit_key:'CNY_THOUSAND',unit_version:'1',updated_at:'2026-11-02 12:00:00.000000Z'}]}
]};
if(scenario==='snapshot')data.items[0].observations.push({
  ...fact('shares_issued','Registrierte Aktien','1838457834',2025),period_type:'snapshot',
  fiscal_year:null,period_start:null,period_end:null,as_of_at:'2025-03-25 00:00:00.000000',unit_key:'SHARE_COUNT'
});
if(scenario==='empty'||scenario==='invalid-empty'){
  data.items=[];
  data.totals={assets:scenario==='empty'?0:1,fundamental_observations:0,fundamental_current:0};
  data.as_of='2026-11-02 12:30:00.000000Z';
}
resolve({ok:scenario!=='error',json:async()=>data});
function tree(node,tag=[]){const result=[];if(node.tag==='td')result.push(node.textContent);node.children.forEach(child=>result.push(...tree(child,tag)));return result;}
setImmediate(()=>{
  const byd=tree(detail), buttons=assets.querySelectorAll('button');
  if(buttons[1]) buttons[1].click();
  process.stdout.write(JSON.stringify({loading:status.textContent,summary:summary.textContent,total:total.textContent,
    assets:buttons.map(button=>button.children[1].textContent),byd,ubtech:tree(detail),
    error:status.textContent==='Fundamentaldaten nicht verfügbar'?status.textContent:null,
    detail:detail.children.map(child=>child.textContent),requests}));
});
