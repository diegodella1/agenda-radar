import assert from 'node:assert/strict';
import {mkdir, writeFile} from 'node:fs/promises';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base=process.env.SMOKE_BASE_URL || 'http://127.0.0.1:8879';
const output=process.env.SMOKE_OUTPUT || 'artifacts/showcase';
await mkdir(output,{recursive:true});
const browser=await chromium.launch({headless:true,executablePath:'/usr/bin/chromium',args:['--no-sandbox','--disable-dev-shm-usage']});
const errors=[],requests=[],blockedEdgeAnalytics=[];
try {
 const context=await browser.newContext({viewport:{width:1440,height:1000}});
 const page=await context.newPage();
 page.setDefaultTimeout(20000);
 page.on('pageerror',error=>errors.push(error.message));
 page.on('request',request=>requests.push(request.url()));
 page.on('requestfailed',request=>{
  const url=new URL(request.url());
  if(url.hostname==='static.cloudflareinsights.com' && url.pathname.startsWith('/beacon.min.js/') && request.failure()?.errorText==='csp') blockedEdgeAnalytics.push(request.url());
 });
 const began=Date.now();
 await page.goto(base+'/demo/');
 await page.getByRole('heading',{name:'Your next editorial meeting, in one view'}).waitFor();
 const initialMs=Date.now()-began;
 assert.equal(await page.locator('html').getAttribute('lang'),'en');
 await page.getByRole('button',{name:'Skip guide'}).click();
 await page.reload();
 await page.getByRole('heading',{name:'See the story beyond your agenda.'}).waitFor();
 assert.equal(await page.locator('dialog[open]').count(),0);
 const skip=async()=>{if(await page.locator('dialog[open]').count())await page.locator('[data-tour="close"]').click();};
 const visit=async path=>{await page.goto(base+'/demo'+path);await page.locator('h1').waitFor();await skip();};
 for(const path of ['/compare','/events','/trends','/alerts','/history','/assistant','/admin/sources','/admin/config','/integrations','/events/1']) {
  await page.goto(base+'/demo'+path);
  await page.locator('dialog[open]').waitFor();
  await page.getByRole('button',{name:'Skip guide'}).click();
  await page.reload();await page.locator('h1').waitFor();
  assert.equal(await page.locator('dialog[open]').count(),0,`${path}: first-visit guide repeated`);
 }
 await page.locator('[name="reason"]').fill('Review the night-service impact for commuters.');
 await page.getByRole('button',{name:'Record decision'}).click();
 await visit('/history');
 await page.getByText('Review the night-service impact for commuters.',{exact:true}).waitFor();
 await visit('/admin/config');
 await page.locator('#weight-environment').fill('200');
 await page.locator('#weight-environment').dispatchEvent('input');
 await page.getByRole('button',{name:'Preview ranking'}).click();
 await page.locator('[name="reason"]').fill('Make the river restoration more visible.');
 await page.getByRole('button',{name:'Publish sample priorities'}).click();
 await page.getByRole('button',{name:'Restore previous weights'}).waitFor();
 await visit('/admin/sources');
 await page.locator('[data-source="city"]').uncheck();
 await visit('/');
 assert.equal(await page.locator('.metrics>div').nth(1).locator('strong').textContent(),'3');
 await page.getByRole('button',{name:'Simulate a new signal'}).click();
 await page.getByRole('button',{name:'Sample update applied'}).waitFor();
 await visit('/assistant');
 await page.getByRole('button',{name:'Where is our biggest coverage gap?'}).click();
 await page.locator('#answer').getByRole('heading',{name:'Night buses could reconnect the south district'}).waitFor();
 await page.locator('[name="question"]').fill('Unrelated subject outside this sample');
 await page.getByRole('button',{name:/^Explore the evidence/}).click();
 await page.getByText('This demo only answers questions about',{exact:false}).waitFor();
 for(const lang of ['en','es']) {
  await page.selectOption('#language',lang);
  for(const path of ['/','/compare','/events/1','/trends','/alerts','/history','/assistant','/admin/sources','/admin/config','/integrations']) {
   await visit(path);
   assert.equal(await page.locator('html').getAttribute('lang'),lang);
   for(const width of [1440,390,320]) {
    await page.setViewportSize({width,height:1000});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`${lang} ${path} overflow at ${width}`);
   }
  }
  await visit('/');
  await page.setViewportSize({width:1440,height:1000});
  await page.screenshot({path:`${output}/${lang}-desktop.png`,fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:`${output}/${lang}-mobile.png`,fullPage:true});
 }
 await page.getByRole('button',{name:/^Guía de esta función/}).click();
 await page.getByRole('heading',{name:'Tu próxima reunión editorial, en una vista'}).waitFor();
 await page.keyboard.press('Escape');
 assert.equal(await page.locator('dialog[open]').count(),0);
 page.once('dialog',dialog=>dialog.accept());
 await page.getByRole('button',{name:'Reiniciar demo',exact:true}).click();
 await visit('/history');
 assert.equal(await page.getByText('Review the night-service impact for commuters.',{exact:true}).count(),0);
 const externalRequests=requests.filter(url=>!url.startsWith(base+'/'));
 assert.equal(externalRequests.length,blockedEdgeAnalytics.length,'Unexpected external request in demo');
 assert.ok(externalRequests.every(url=>blockedEdgeAnalytics.includes(url)),'External request was not a CSP-blocked edge beacon');
 assert.equal(requests.filter(url=>url.includes('/api/')).length,0,'API request in static demo');
 assert.deepEqual(errors,[]);
 const report={passed:true,initialInteractiveMs:initialMs,languages:['en','es'],widths:[1440,390,320],routes:10,externalRequests:externalRequests.length-blockedEdgeAnalytics.length,blockedEdgeAnalytics:blockedEdgeAnalytics.length,apiRequests:0,checks:['first-visit tours','dismiss/replay','language persistence','decisions','weights/preview/publish','sources','sample update','assistant','reset','responsive layout']};
 await writeFile(`${output}/results.json`,JSON.stringify(report,null,2));
 console.log(JSON.stringify(report));
} finally {await browser.close();}
