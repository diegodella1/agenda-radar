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
  await page.goto(base+path,{waitUntil:'domcontentloaded'});
  await page.locator('input[name="email"]').fill('demo');
  await page.getByLabel('Contraseña',{exact:true}).fill('demo');
  await page.getByRole('button',{name:'Ingresar'}).click();
  await page.waitForURL(base+'/demo/');
  await page.getByRole('heading',{name:'Radar editorial'}).waitFor();
 }
 await login(page, '/login');
 await page.locator('select[name="window"]').selectOption('7d');
 await page.locator('.filter-more > summary').click();
 await page.locator('select[name="channel"]').selectOption('web');
 await page.getByRole('button',{name:'Aplicar',exact:true}).click();
 await page.waitForURL(url=>url.searchParams.get('window')==='7d' && url.searchParams.get('channel')==='web');
 await page.locator('.active-filters').getByText('Canal: web',{exact:true}).waitFor();

 const second=await browser.newContext();contexts.push(second);
 const other=await second.newPage();other.setDefaultTimeout(60000);await login(other);
 await page.getByRole('button',{name:'Ayuda · 3 pasos',exact:true}).click();
 await page.getByRole('dialog').waitFor();
 await page.getByRole('button',{name:'Siguiente →',exact:true}).click();
 await page.getByRole('heading',{name:'Entender y contrastar'}).waitFor();
 await page.keyboard.press('Escape');
 assert.equal(await page.getByRole('dialog').isVisible(),false);
 assert.equal(await page.getByRole('button',{name:'Ayuda · 3 pasos',exact:true}).evaluate(el=>el===document.activeElement),true);
 await page.goto(base+'/demo/compare?window=7d',{waitUntil:'domcontentloaded'});
 const gap=page.locator('.gap-row').first();
 await gap.locator('summary').focus();await page.keyboard.press('Enter');
 assert.equal(await gap.getAttribute('open'),'');
 await gap.locator('a').last().focus();await page.keyboard.press('Escape');
 assert.equal(await gap.getAttribute('open'),null);
 await page.locator('.matrix-cell').first().click();
 assert.ok(page.url().includes('window=7d') && page.url().includes('evidence_source='));
 await page.getByText('Evidencia de', {exact:false}).waitFor();
 await page.goto(base+'/demo/events/1',{waitUntil:'domcontentloaded'});
 await page.locator('input[name="reason"]').fill('Decisión privada del navegador de prueba');
 await page.getByRole('button',{name:'Registrar decisión'}).click();
 await page.getByText('follow — Decisión privada del navegador de prueba',{exact:false}).waitFor();
 await other.goto(base+'/demo/events/1',{waitUntil:'domcontentloaded'});
 assert.equal(await other.getByText('Decisión privada del navegador de prueba',{exact:false}).count(),0);
 const href=await page.locator('a[href*="/demo/evidence/"]').first().getAttribute('href');
 await page.goto(href,{waitUntil:'domcontentloaded'});await page.getByText('Contenido sintético de demostración. No es una noticia real.').waitFor();
 await page.getByRole('button',{name:'Simular novedades'}).click();
 await page.getByText('Se incorporaron 10 publicaciones ficticias', {exact:false}).waitFor();
 await page.goto(base+'/demo/assistant',{waitUntil:'domcontentloaded'});
 await page.getByLabel('Tu consulta').fill('transporte');
 await page.getByRole('button',{name:'Consultar →',exact:true}).click();
 await page.locator('#query-result .answer').waitFor();
 assert.ok(await page.locator('#query-result a').count()>0);
 await mkdir('artifacts/screenshots',{recursive:true});
 for(const width of [1440,1024,768,390,320]) {
  await page.setViewportSize({width,height:1000});
  for(const path of ['/','/compare','/events','/events/1','/trends','/alerts','/history','/assistant','/integrations','/admin/sources','/admin/config']) {
   const response=await page.goto(base+'/demo'+path,{waitUntil:'domcontentloaded'});
   assert.equal(response.status(),200,path);
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`${path} overflow ${width}`);
   if(path==='/' && width<=760){
    const toggle=page.locator('[data-nav-toggle]');
    await toggle.click();
    await page.getByRole('navigation',{name:'Principal',exact:true}).waitFor({state:'visible'});
    assert.equal(await toggle.getAttribute('aria-expanded'),'true');
    await page.getByRole('navigation',{name:'Principal',exact:true}).getByRole('link',{name:'Agenda comparada',exact:true}).focus();
    await page.keyboard.press('Escape');
    assert.equal(await toggle.getAttribute('aria-expanded'),'false');
    assert.equal(await toggle.evaluate(el=>document.activeElement===el),true);
    assert.equal(await page.getByRole('navigation',{name:'Principal',exact:true}).isVisible(),false);
   }
   if(path==='/'){
    await page.evaluate(()=>document.fonts.ready);
    assert.equal(await page.evaluate(()=>document.fonts.check('16px "Radar Sans"')),true);
    if(process.env.SMOKE_SCREENSHOTS!=='0'){
     await page.screenshot({path:`artifacts/screenshots/demo-${width}.png`,fullPage:true});
     await page.screenshot({path:`artifacts/screenshots/workspace-${width}.png`,fullPage:false});
    }
   }
   if(process.env.SMOKE_SCREENSHOTS!=='0' && ['/compare','/events/1','/admin/sources'].includes(path) && [1440,390].includes(width))await page.screenshot({path:`artifacts/screenshots/workspace-${path.replaceAll('/','-')}-${width}.png`,fullPage:false});
  }
 }
 page.once('dialog', dialog=>dialog.accept());
 await page.getByRole('button',{name:'Reiniciar demo'}).click();
 await page.waitForURL(base+'/demo/');
 await page.goto(base+'/demo/history',{waitUntil:'domcontentloaded'});
 assert.equal(await page.getByText('Decisión privada del navegador de prueba',{exact:false}).count(),0);
 await page.getByRole('button',{name:'Salir',exact:true}).click();
 await page.waitForURL(base+'/demo/login');
 assert.deepEqual(errors,[]);
 // Cloudflare injects its beacon at the edge; CSP blocks it before network access.
 assert.equal(requests.filter(r=>!r.url().startsWith(base+'/') && !(new URL(r.url()).hostname==='static.cloudflareinsights.com' && blocked.has(r))).length,0,'Unexpected external browser requests');
 console.log('Demo smoke passed: login demo/demo, two visitors, decision isolation, evidence, news, assistant, 11 screens at 5 widths, mobile navigation and focus, reset and logout.');
} finally {
 for(const context of contexts){
  for(const page of context.pages().slice(0,1)){
   try{await page.evaluate(async()=>fetch('/demo/api/v1/auth/logout',{method:'POST',headers:{'X-Requested-With':'AgendaRadar','X-CSRF-Token':document.querySelector('meta[name="csrf-token"]')?.content||''}}));}catch{}
  }
 }
 await browser.close();
}
