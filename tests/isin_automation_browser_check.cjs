const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const {E}=require('./fixtures/isin_dom.cjs');
const script=fs.readFileSync(__dirname+'/../assets/js/isin_quotes.js','utf8');
const key='mosa2-isin-lookup-v1', a='DE0007030009', b='DE0005313704';
const base=Date.parse('2026-11-08T12:00:00Z');
const initial=[{isin:a,name:'Alpha',quotes:[],errors:[]},{isin:b,name:'Beta',quotes:[],errors:[]}];
const asset=(isin,name,price)=>({isin,name,price,source:'Tradegate',venue:'Tradegate BSX',
  quote_type:'Mid',currency:'EUR',market_at:'2026-11-08 11:59:00.000000Z',
  observed_at:'2026-11-08 11:59:10.000000Z',status:'stored'});
const stored=[asset(a,'Alpha','10.00'),asset(b,'Beta','20.00')];
const flush=()=>new Promise(setImmediate);
function harness({market=true,entries=initial,lifecycle=false,actions=false,registered=[],initialItems=stored}={}){
  let ms=0,timerId=0,http=200,items=initialItems,hold=false,release,active=0,maxActive=0,writes=0,focused=true;
  const timers=new Map(),calls=[],events={},windowEvents={};
  const storage=new Map([[key,JSON.stringify(entries)],['mosa2-isin-automation-v1','{"enabled":false}']]);
  const form=new E('form'),input=new E('input'),submit=new E('button'),refresh=new E('button');
  const table=new E('tbody'),details=new E('button'),root=new E('body'),summary=new E('span');
  if(actions)table.dataset.isinActions='';
  const error=new E('p');error.hidden=true;
  form.parentElement={querySelector:selector=>selector==='[data-isin-error]'?error:null};
  form.map={'[data-isin-input]':input,'button[type=submit]':submit};
  const document={hidden:false,hasFocus:()=>focused,querySelectorAll:selector=>({
    '[data-isin-form]':[form],'[data-isin-refresh]':market?[refresh]:[],'[data-isin-table]':market?[table]:[],
    '[data-isin-summary]':market?[summary]:[]
  }[selector]??[]),querySelector:selector=>({
    '[data-isin-stored-quotes]':root,'[data-isin-market-view]':market?new E('section'):null,
    '[data-isin-details-toggle]':market?details:null,
    '[data-site-shell]':lifecycle?root:null
  }[selector]??null),createElement:tag=>new E(tag),addEventListener:(name,fn)=>{events[name]=fn;}};
  class TestDate extends Date {constructor(...args){super(...(args.length?args:[TestDate.now()]));} static now(){return base+ms;}}
  const setTimeout=(fn,delay)=>{timers.set(++timerId,{at:ms+delay,fn});return timerId;};
  const clearTimeout=id=>timers.delete(id);
  async function advance(delay){
    const target=ms+delay;
    for(;;){
      const next=[...timers].filter(([,timer])=>timer.at<=target).sort(([,x],[,y])=>x.at-y.at)[0];
      if(!next)break;
      const [id,timer]=next;timers.delete(id);ms=timer.at;timer.fn();await flush();
    }
    ms=target;await flush();
  }
  async function fetch(url,opts){
    calls.push({url,at:ms,opts});active++;maxActive=Math.max(maxActive,active);
    try{
      if(url===(market?'api/market.php?view=registered':'api/market.php?view=best')){
        assert.equal(opts.method,undefined,'The background read is a GET');
        assert.equal(opts.credentials,'same-origin');
        assert.equal(opts.cache,'no-store');
        if(hold)await new Promise(resolve=>{release=resolve;});
        return {ok:http===200,status:http,json:async()=>({status:'ok',items,registered})};
      }
      assert.equal(url,'api/isin_quote.php');
      assert.equal(opts.method,'POST');
      assert.equal(opts.headers['X-MOSA2-Quote-Intent'],'manual');
      const {isin,provider}=JSON.parse(opts.body);
      assert.equal(provider,'all');
      const providers=['lang_schwarz_quote','lang_schwarz_trade','tradegate_quote','tradegate_trade','boerse_frankfurt_trade','yahoo_home_market'];
      const records=providers.map(provider=>({isin,provider,status:'ok',source:'Tradegate',currency:'EUR',price:'30.00',quote_type:'Trade',
        market_at:'2026-11-08T12:00:00Z',captured_at:'2026-11-08T12:00:10Z'}));
      return {ok:true,status:200,body:null,json:async()=>({status:'ok',isin,name:'Manual AG',records})};
    }finally{active--;}
  }
  const localStorage={getItem:k=>storage.get(k),setItem:(k,v)=>{writes++;storage.set(k,v);},
    removeItem:k=>{writes++;storage.delete(k);}};
  const sandbox={document,window:{addEventListener:(name,fn)=>{windowEvents[name]=fn;}},localStorage,fetch,AbortController,
    Date:TestDate,performance:{now:()=>ms},setTimeout,clearTimeout,requestAnimationFrame:fn=>fn()};
  vm.runInNewContext(script,sandbox);
  root.querySelector=document.querySelector;
  root.querySelectorAll=document.querySelectorAll;
  return {table,input,form,refresh,details,root,summary,calls,error,storage,advance,
    mount(){return sandbox.MosaIsinLookup.mount(root);},
    get writes(){return writes;},get maxActive(){return maxActive;},
    hide(value){document.hidden=value;events.visibilitychange();},
    focus(value){focused=value;windowEvents[value?"focus":"blur"]();},
    update(value){items=value;},status(value){http=value;},
    hold(){hold=true;},release(){hold=false;release();}};
}

(async()=>{
  const m=harness();await flush();
  assert.equal(m.root.dataset.dataSuccess,'true');
  assert.deepEqual(m.calls.map(call=>call.at),[0]);
  assert.equal(m.table.children.length,2);
  const [first,second]=m.table.children, cells=[...first.cells], secondCells=[...second.cells];
  const inserts=m.table.insertions, before=cells.map(c=>c.textWrites);
  const secondBefore=secondCells.map(c=>c.textWrites);
  m.update([{...stored[0],price:'11.00'},stored[1]]);
  await m.advance(29999);assert.equal(m.calls.length,1);
  await m.advance(1);
  assert.deepEqual(m.table.children,[first,second]);
  assert.deepEqual(first.cells,cells);assert.deepEqual(second.cells,secondCells);
  assert.equal(m.table.insertions,inserts);
  assert.equal(cells[2].textContent,'11,00 EUR');
  assert.deepEqual(cells.map((cell,i)=>cell.textWrites-before[i]),[0,0,1,0,0,0,0,1,0,0]);
  assert.deepEqual(secondCells.map((cell,i)=>cell.textWrites-secondBefore[i]),[0,0,0,0,0,0,0,1,0,0]);
  m.details.events.click();
  const detailRows=[...m.table.children], detailInserts=m.table.insertions;
  m.input.value='draft ISIN';
  await m.advance(60000);
  assert.deepEqual(m.calls.map(call=>call.at),[0,30000,60000,90000]);
  assert.deepEqual(m.table.children,detailRows);assert.equal(m.table.insertions,detailInserts);
  assert.equal(m.details.getAttribute('aria-expanded'),'true');
  assert.equal(m.input.value,'draft ISIN');
  assert.equal(m.writes,0,'Background data never rewrites the user list');
  assert.equal(m.root.dataset.isinReadCount,'4');
  assert.equal(m.root.dataset.isinReadHttp,'200');

  m.hide(true);await m.advance(90000);
  assert.equal(m.calls.length,4,'Hidden tab makes no new requests');
  m.status(503);m.hide(false);await m.advance(0);
  assert.equal(m.calls.length,5,'An overdue read resumes when visible');
  assert.equal(m.root.dataset.isinReadHttp,'503');
  assert.deepEqual(m.table.children,detailRows);
  assert.equal(detailRows[0].cells[2].textContent,'11,00 EUR');
  assert.match(detailRows[0].cells[9].textContent,/Veraltet/);
  m.status(200);m.hold();await m.advance(30000);await m.advance(35000);
  assert.equal(m.calls.length,6,'Slow read cannot overlap the next cycle');
  m.release();await flush();await m.advance(0);
  assert.equal(m.calls.length,7);
  assert.equal(m.maxActive,1);
  assert.equal(detailRows[0].cells[9].textContent,'Gespeichert');

  m.focus(false);await m.advance(30000);
  assert.equal(m.calls.length,7,'A visible but unfocused tab makes no new requests');
  assert.equal(m.root.dataset.isinTabActive,'false');
  m.status(403);m.focus(true);await m.advance(0);await m.advance(30000);
  assert.equal(m.calls.length,8,'An overdue read resumes on focus and stops on authorization failure');

  const home=harness({market:false});await flush();await home.advance(45000);
  assert.deepEqual(home.calls.map(call=>call.url),['api/market.php?view=best']);
  const empty=harness({entries:[],initialItems:[]});await flush();await empty.advance(30000);
  assert.equal(empty.calls.length,2,'An empty personal list still reads the DB every 30 seconds');
  const registeredOnly=harness({entries:[],initialItems:[],registered:[{isin:a,name:'DB AG',asset_class:'equity'}]});
  await flush();
  const row=registeredOnly.table.children[0];
  assert.equal(row.cells[0].textContent,'DB AG');
  assert.equal(row.cells[2].textContent,'—');
  assert.match(row.cells[9].textContent,/In DB registriert · Kein gespeicherter Kurs/);
  assert.equal(registeredOnly.writes,0,'DB registrations never overwrite browser storage');
  empty.input.value=b;empty.form.events.submit({preventDefault(){}});await flush();
  assert.equal(empty.calls[2].url,'api/isin_quote.php','The first new ISIN is queried immediately');
  assert.equal(JSON.parse(empty.storage.get(key))[0].isin,b);
  await empty.advance(60000);
  assert.equal(empty.calls[3].url,'api/market.php?view=registered');
  assert.equal(empty.calls[4].at-empty.calls[3].at,30000);
  await empty.refresh.events.click();
  assert.equal(empty.calls.at(-1).url,'api/isin_quote.php','Manual refresh preserves the source comparison');
  assert.equal(empty.error.hidden,true);
  assert.equal(empty.maxActive,1);
  const scoped=harness({lifecycle:true});
  assert.equal(scoped.calls.length,0,'A shared shell does not start the ISIN module automatically');
  scoped.hold();
  const firstVisit=scoped.mount();await flush();
  firstVisit.dispose();
  assert.equal(scoped.calls[0].opts.signal.aborted,true,'Leaving cancels the outstanding stored GET');
  scoped.release();await firstVisit.ready;
  await scoped.advance(30000);
  assert.equal(scoped.calls.length,1,'Disposed Market schedules no further reads');
  const secondVisit=scoped.mount();await secondVisit.ready;
  await scoped.advance(30000);
  assert.equal(scoped.calls.length,3,'A new visit starts a single 30-second polling loop');
  secondVisit.dispose();
  assert.equal(scoped.writes,0,'Mounting and leaving views does not change stored ISINs');
  const mixed=harness({entries:[initial[0]],actions:true});await flush();
  assert.equal(mixed.table.children.length,2,'Database-only results still appear in the same table');
  const owned=mixed.table.children[0].cells[10].firstElementChild;
  assert.equal(owned.dataset.isinRemove,a);
  assert.equal(mixed.table.children[1].cells[10].firstElementChild,null,'Database-only rows cannot be removed');
  mixed.table.events.click({target:{closest:()=>owned}});
  assert.equal(mixed.table.children.length,2,'Removing a local ISIN does not remove its database quote');
  assert.equal(mixed.table.children[0].cells[10].firstElementChild,null);
  console.log('PASS stored-only poll: 30 s, keyed cells, visible tabs, recovery, no overlap, manual source requests');
})().catch(error=>{console.error(error);process.exitCode=1;});
