const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 for(const width of [1280,390]){
  const page=await browser.newPage({viewport:{width,height:844}});
  let requests=0, failure=false, hold=null, waitHold=false, currentRequests=0;
  const names=['PNE AG','Carl Zeiss Meditec','DroneShield','BYD','Ubtech Robotics'];
  const isins=['DE000A0JBPG2','DE0005313704','AU000000DRO2','CNE100000296','CNE100006CQ4'];
  const data={status:'ok',stale_seconds:1800,items:names.map((name,i)=>({name,isin:isins[i],source:'Synthetic',venue:'XFRA',
    status:'stale',price:'12.3400000000',currency:'EUR',unit:'EUR',unit_version:'1',quantity_basis_amount:null,
    market_at:'2026-01-01 00:00:00.000000Z',observed_at:'2026-01-01 00:00:01.000000Z',age_seconds:3600,observation_id:String(9001+i)}))};
  await page.addInitScript(()=>{window.simHidden=false;Object.defineProperty(document,'hidden',{get:()=>window.simHidden});});
  await page.route('**/*',async route=>{
    const url=new URL(route.request().url());
    if(url.origin!=='http://127.0.0.1:8765')return route.abort();
    if(url.pathname==='/api/market.php'){
      if(!url.search){currentRequests++;return route.fulfill({json:{status:'ok',items:[]}});}
      assert.equal(url.search,'?view=observations');requests++;
      if(waitHold)await new Promise(resolve=>{hold=resolve});
      if(failure)return route.fulfill({status:503,json:{status:'error',message:'PRIVATE_CANARY'}});
      return route.fulfill({json:data});
    }
    return route.continue();
  });
  await page.clock.install();
  await page.goto('http://127.0.0.1:8765/marktdaten.html');
  await page.clock.runFor(250);
  await page.locator('[data-observation-rows] tr[data-observation-id]').first().waitFor();
  assert.equal(requests,1);
  assert.equal(currentRequests,1);
  assert.equal(await page.locator('[data-observation-rows] tr').count(),5);
  assert.equal(await page.locator('[data-market-view] table').count(),1);
  const dims=await page.evaluate(()=>({overflow:document.documentElement.scrollWidth>innerWidth,
     navTop:document.querySelector('nav').getBoundingClientRect().top,
     headerBottom:document.querySelector('header').getBoundingClientRect().bottom}));
  assert.equal(dims.overflow,false);assert.equal(dims.navTop,dims.headerBottom);
  assert((await page.locator('[data-observation-rows]').innerText()).includes('Veraltet'));
  await page.clock.runFor(119000);assert.equal(requests,1);
  await page.clock.runFor(1100);
  await page.waitForFunction(()=>!document.querySelector('[data-observation-refresh]').disabled);
  assert.equal(requests,2);
  await page.evaluate(()=>{window.simHidden=true;document.dispatchEvent(new Event('visibilitychange'));});
  await page.clock.runFor(360000);assert.equal(requests,2);
  await page.evaluate(()=>{window.simHidden=false;document.dispatchEvent(new Event('visibilitychange'));});
  await page.waitForFunction(()=>!document.querySelector('[data-observation-refresh]').disabled);
  assert.equal(requests,3);
  // Hold a refresh while visibility changes; at most one request remains active.
  waitHold=true;
  await page.locator('[data-observation-refresh]').click();
  await page.waitForFunction(()=>document.querySelector('[data-observation-refresh]').disabled);
  assert.equal(requests,4);
  await page.clock.runFor(4000);assert.equal(requests,4);
  waitHold=false;hold();
  await page.waitForFunction(()=>!document.querySelector('[data-observation-refresh]').disabled);
  const previous=await page.locator('[data-observation-rows] tr').first().getAttribute('data-observation-id');
  failure=true;
  await page.locator('[data-observation-refresh]').click();
  await page.waitForFunction(()=>!document.querySelector('[data-observation-refresh]').disabled);
  assert.equal(requests,5);
  assert.equal(await page.locator('[data-observation-rows] tr').first().getAttribute('data-observation-id'),previous);
  assert(!(await page.locator('body').innerText()).includes('PRIVATE_CANARY'));
  await page.clock.runFor(360000);assert.equal(requests,5);
  await page.evaluate(()=>{window.simHidden=true;document.dispatchEvent(new Event('visibilitychange'));window.simHidden=false;document.dispatchEvent(new Event('visibilitychange'));});
  await page.clock.runFor(500);assert.equal(requests,5);
  // Manual recovery only; missing values have an explicit placeholder.
  failure=false;data.items=data.items.map(({name,isin,source,venue})=>({name,isin,source,venue,status:'missing'}));
  await page.locator('[data-observation-refresh]').click();
  await page.waitForFunction(()=>!document.querySelector('[data-observation-refresh]').disabled);
  assert.equal(requests,6);
  assert((await page.locator('[data-observation-rows]').innerText()).includes('Keine Observation'));
  assert.equal(currentRequests,1);
  console.log(width+'px: observations/current, timing, visibility, serialization, retained data, no retry PASS');
  await page.screenshot({path:process.env.RUNNER_TEMP+'/observations-'+width+'.png',fullPage:true});
  await page.close();
 }
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
