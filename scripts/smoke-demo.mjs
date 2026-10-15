import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base=process.env.SMOKE_BASE_URL || 'http://127.0.0.1:8766';
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH || '/usr/bin/chromium',args:['--no-sandbox','--disable-dev-shm-usage']});
const contexts=[];
try {
 const context=await browser.newContext({viewport:{width:1440,height:1000}});contexts.push(context);
 const page=await context.newPage();page.setDefaultTimeout(60000);page.setDefaultNavigationTimeout(60000); const errors=[]; const requests=[]; const blocked=new Set();
 page.on('pageerror', e=>errors.push(e.message)); page.on('request', r=>requests.push(r)); page.on('requestfailed', r=>{if(['csp','net::ERR_BLOCKED_BY_CSP'].includes(r.failure()?.errorText))blocked.add(r);});
 async function login(page, path='/demo/login') {
  await page.goto(base+path);
  await page.locator('input[name="email"]').fill('demo');
  await page.getByLabel('Contraseña',{exact:true}).fill('demo');
  await page.getByRole('button',{name:'Ingresar'}).click();
  await page.waitForURL(base+'/demo/');
  await page.getByRole('heading',{name:'Radar editorial'}).waitFor();
 }
 await login(page, '/login');
 const second=await browser.newContext();contexts.push(second);
 const other=await second.newPage();other.setDefaultTimeout(60000);await login(other);
 await page.goto(base+'/demo/events/1');
 await page.locator('input[name="reason"]').fill('Decisión privada del navegador de prueba');
 await page.getByRole('button',{name:'Registrar decisión'}).click();
 await page.getByText('follow — Decisión privada del navegador de prueba',{exact:false}).waitFor();
 await other.goto(base+'/demo/events/1');
 assert.equal(await other.getByText('Decisión privada del navegador de prueba',{exact:false}).count(),0);
 const href=await page.locator('a[href*="/demo/evidence/"]').first().getAttribute('href');
 await page.goto(href);await page.getByText('Contenido sintético de demostración. No es una noticia real.').waitFor();
 await page.getByRole('button',{name:'Simular novedades'}).click();
 await page.getByText('Se incorporaron 10 publicaciones ficticias', {exact:false}).waitFor();
 await page.goto(base+'/demo/assistant');
 await page.getByLabel('Tu consulta').fill('transporte');
 await page.getByRole('button',{name:'Consultar →',exact:true}).click();
 await page.locator('#query-result .answer').waitFor();
 assert.ok(await page.locator('#query-result a').count()>0);
 await mkdir('artifacts/screenshots',{recursive:true});
 for(const width of [1440,390,320]) {
  await page.setViewportSize({width,height:1000});
  for(const path of ['/','/compare','/events','/events/1','/trends','/alerts','/history','/assistant','/integrations','/admin/sources','/admin/config']) {
   const response=await page.goto(base+'/demo'+path);
   assert.equal(response.status(),200,path);
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`${path} overflow ${width}`);
   if(path==='/')await page.screenshot({path:`artifacts/screenshots/demo-${width}.png`,fullPage:true});
  }
 }
 page.once('dialog', dialog=>dialog.accept());
 await page.getByRole('button',{name:'Reiniciar demo'}).click();
 await page.waitForURL(base+'/demo/');
 await page.goto(base+'/demo/history');
 assert.equal(await page.getByText('Decisión privada del navegador de prueba',{exact:false}).count(),0);
 await page.getByRole('button',{name:'Salir',exact:true}).click();
 await page.waitForURL(base+'/demo/login');
 assert.deepEqual(errors,[]);
 // Cloudflare injects its beacon at the edge; CSP blocks it before network access.
 assert.equal(requests.filter(r=>!r.url().startsWith(base+'/') && !(new URL(r.url()).hostname==='static.cloudflareinsights.com' && blocked.has(r))).length,0,'Unexpected external browser requests');
 console.log('Demo smoke passed: login demo/demo, two visitors, decision isolation, evidence, news, assistant, 11 screens at 3 widths, reset and logout.');
} finally {
 for(const context of contexts){
  for(const page of context.pages().slice(0,1)){
   try{await page.evaluate(async()=>fetch('/demo/api/v1/auth/logout',{method:'POST',headers:{'X-Requested-With':'AgendaRadar','X-CSRF-Token':document.querySelector('meta[name="csrf-token"]')?.content||''}}));}catch{}
  }
 }
 await browser.close();
}
