import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base=process.env.AUDIT_BASE_URL || 'http://127.0.0.1:8766';
const local=new URL(base).hostname==='127.0.0.1';
const widths=(process.env.AUDIT_WIDTHS || '1440,1024,768,390,320').split(',').map(Number);
const report={base,checks:[],errors:[],assets:[],consoleErrors:[]};
const browser=await chromium.launch({headless:true,executablePath:'/usr/bin/chromium',args:['--no-sandbox','--disable-dev-shm-usage']});
const context=await browser.newContext();
const page=await context.newPage();
page.setDefaultTimeout(15000);page.setDefaultNavigationTimeout(20000);
page.on('pageerror',e=>report.consoleErrors.push(e.message));
page.on('response',r=>{if(/\.(css|ttf)(\?|$)/.test(r.url()))report.assets.push({url:r.url(),status:r.status()});});
page.on('requestfailed',r=>{if(/\.(css|ttf)(\?|$)/.test(r.url()))report.errors.push({asset:r.url(),error:r.failure()?.errorText});});
await mkdir('artifacts/css-audit',{recursive:true});
let csrf='',demo=false;
async function inspect(path){
 console.log(`CHECK ${path}`);
 try{
  const response=await page.goto(base+path,{waitUntil:'domcontentloaded'});
  assert.equal(response.status(),200);
  await page.waitForFunction(()=>document.styleSheets.length>0 && [...document.styleSheets].every(s=>{try{return s.cssRules.length>0;}catch{return false;}}));
  await page.waitForFunction(()=>document.fonts.status==='loaded' && [...document.fonts].some(f=>f.family==='Radar Sans' && f.status==='loaded') && document.fonts.check('16px "Radar Sans"'));
  for(const width of widths){
   await page.setViewportSize({width,height:900});
   const metrics=await page.evaluate(()=>{
    const h=document.querySelector('h1');
    return {overflow:document.documentElement.scrollWidth>innerWidth,font:getComputedStyle(document.body).fontFamily,headingFont:h?getComputedStyle(h).fontFamily:null,background:getComputedStyle(document.body).backgroundColor,sheets:[...document.styleSheets].map(s=>s.href),inputs:[...document.querySelectorAll('input:not([type=hidden]),select')].filter(e=>e.getClientRects().length).map(e=>({name:e.name,height:e.getBoundingClientRect().height})),nav:document.querySelector('.workspace-nav')?getComputedStyle(document.querySelector('.workspace-nav')).display:null};
   });
   assert.equal(metrics.overflow,false,`Document overflow ${width}`);
   assert.match(metrics.font,/Radar Sans/);
   if(metrics.headingFont)assert.match(metrics.headingFont,/Radar Sans/);
   assert.equal(metrics.background,'rgb(243, 246, 251)');
   assert.ok(metrics.inputs.every(i=>i.height>=42),`Small input ${width}`);
   if(metrics.nav)assert.equal(metrics.nav,width<=760?'none':'block',`Navigation visibility ${width}`);
   // Opening read-only disclosures must not break mobile layouts or clip controls.
   await page.evaluate(()=>document.querySelectorAll('details').forEach(d=>d.open=true));
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`Expanded overflow ${width}`);
   await page.evaluate(()=>document.querySelectorAll('details').forEach(d=>d.open=false));
   if(metrics.nav && width<=760){
    await page.locator('[data-nav-toggle]').click();
    assert.equal(await page.locator('#workspace-nav').isVisible(),true);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'Open navigation overflow');
    await page.keyboard.press('Escape');
    assert.equal(await page.locator('[data-nav-toggle]').getAttribute('aria-expanded'),'false');
   }
   report.checks.push({path,width,...metrics});
   if(process.env.AUDIT_SCREENSHOTS==='1' && [1440,320].includes(width) && ['/home','/login','/','/admin/sources','/admin/config','/admin/providers','/events/1'].includes(path)){
    await page.screenshot({path:`artifacts/css-audit/${local?'local':'public'}-${path.replaceAll('/','_')||'root'}-${width}.png`,timeout:15000});
   }
  }
  console.log(`PASS ${path} (${widths.join(',')})`);
 }catch(error){report.errors.push({path,error:error.message});console.log(`FAIL ${path}: ${error.message}`);}
}
try{
 if(!local)await inspect('/');
 for(const path of ['/home','/about','/funcionalidades','/casos-de-uso','/roadmap','/login','/demo/login'])await inspect(path);
 if(local)await inspect('/setup');
 const loginPath=local?'/api/v1/auth/login':'/demo/api/v1/auth/login';
 const result=await context.request.post(base+loginPath,{headers:{'X-Requested-With':'AgendaRadar'},data:local?{email:'css-audit@example.test',password:'local-css-audit-only-2026'}:{email:'demo',password:'demo'},timeout:20000});
 assert.equal(result.status(),200,'Audit login');csrf=(await result.json()).csrf;demo=!local;
 const prefix=local?'':'/demo';
 const routes=['/','/compare','/events','/events/1','/trends','/alerts','/history','/assistant','/admin/sources','/admin/config'];
 if(local)routes.push('/account','/admin/users','/admin/providers','/admin/prompts','/admin/operations','/admin/audit');else routes.push('/integrations');
 for(const path of routes)await inspect(prefix+path);
 if(!local){
  const comparison=await context.request.get(base+'/demo/api/v1/agendas/compare',{timeout:15000});
  assert.equal(comparison.status(),200);
  const evidence=(await comparison.json()).rows.flatMap(r=>r.documents)[0];
  assert.ok(evidence,'Demo evidence available');
  await inspect(new URL(evidence.url).pathname);
 }
}finally{
 if(csrf){try{await context.request.post(base+(demo?'/demo':'')+'/api/v1/auth/logout',{headers:{'X-Requested-With':'AgendaRadar','X-CSRF-Token':csrf},data:{},timeout:5000});}catch{}}
 await writeFile(`artifacts/css-audit/${local?'local':'public'}-report.json`,JSON.stringify(report,null,2));
 await browser.close();
}
console.log(JSON.stringify({checks:report.checks.length,errors:report.errors,consoleErrors:report.consoleErrors},null,2));
if(report.errors.length || report.consoleErrors.length)process.exitCode=1;
