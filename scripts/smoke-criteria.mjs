import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base=process.env.SMOKE_BASE_URL || 'http://127.0.0.1:8766';
const browser=await chromium.launch({headless:true,executablePath:'/usr/bin/chromium',args:['--no-sandbox','--disable-dev-shm-usage']});
const context=await browser.newContext();
const page=await context.newPage();page.setDefaultTimeout(30000);page.setDefaultNavigationTimeout(45000);
const errors=[];page.on('pageerror',e=>{errors.push(e.message);console.error(e.message);});
await mkdir('artifacts/criteria',{recursive:true});
try{
 const authenticate=()=>context.request.post(base+'/demo/api/v1/auth/login',{headers:{'X-Requested-With':'AgendaRadar'},data:{email:'demo',password:'demo'}});
 let login=await authenticate();
 const loginDeadline=Date.now()+300000;
 while(login.status()===202 && Date.now()<loginDeadline){await new Promise(resolve=>setTimeout(resolve,2000));login=await authenticate();}
 assert.equal(login.status(),200);
 await page.goto(base+'/demo/admin/config',{waitUntil:'domcontentloaded'});
 await page.waitForFunction(()=>window.configEditor);console.log('Editor ready');
 const original=await page.evaluate(()=>window.configEditor.read());
 assert.equal(await page.locator('#criteria-publish').isDisabled(),true);
 assert.equal(await page.locator('[data-criterion="ai_enabled"]').count(),0);
 const topic=page.getByLabel('Agregar en Prioridad por tema',{exact:true});
 await topic.fill('prueba editorial');
 await page.locator('.criteria-dictionary').filter({has:topic}).getByRole('button',{name:'Agregar ajuste',exact:true}).click();
 const weight=page.getByRole('spinbutton',{name:'prueba editorial · valor',exact:true});
 await weight.fill('3');
 assert.equal(await page.evaluate(()=>window.configEditor.read().topic_priorities['prueba editorial']),3);
 await weight.fill('6');
 await page.getByRole('button',{name:'Comparar con versión activa'}).click();
 assert.equal(await page.locator('#preview-result').isVisible(),false);
 await weight.fill('3');
 const range=page.getByRole('slider',{name:'prueba editorial · deslizador'});
 await range.focus();await page.keyboard.press('ArrowLeft');
 assert.ok((await page.evaluate(()=>window.configEditor.read().topic_priorities['prueba editorial']))<3);
 console.log('Validation and keyboard passed');
 // Local inputs stay in draft until a publish request succeeds.
 let active=await context.request.get(base+'/demo/api/v1/admin/config');
 assert.deepEqual((await active.json()).config.topic_priorities,original.topic_priorities);
 await page.getByRole('button',{name:'Comparar con versión activa'}).click();
 await page.locator('#preview-result').waitFor({state:'visible'});
 assert.equal(await page.locator('#criteria-publish').isEnabled(),true);
 await weight.fill('2');
 assert.equal(await page.locator('#criteria-publish').isDisabled(),true);
 assert.equal(await page.locator('#preview-result').isVisible(),false);
 // Named sources use IDs internally, preserving unrelated global settings.
 const sourceSection=page.locator('.criteria-section').filter({has:page.locator('h3').filter({hasText:'Fuentes de referencia'})});
 await sourceSection.locator('summary').click();
 const source=page.getByRole('combobox',{name:'Agregar en Fuentes de referencia'});
 const sourceId=await source.inputValue();
 await sourceSection.getByRole('button',{name:'Agregar ajuste'}).click();
 const sourceWeight=sourceSection.getByRole('spinbutton').last();await sourceWeight.fill('45');
 assert.equal(await page.evaluate(id=>window.configEditor.read().source_weights[id],sourceId),45);
 await page.getByRole('button',{name:'Comparar con versión activa'}).click();
 await page.locator('#preview-result').waitFor({state:'visible'});
 console.log('Preview passed');
 for(const width of [1440,768,390,320]){
  await page.setViewportSize({width,height:950});
  await page.evaluate(()=>document.querySelectorAll('.criteria-editor details').forEach(d=>d.open=true));
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'Overflow '+width);
  assert.ok(await page.locator('.criteria-comparison').count()>0);
  await page.screenshot({path:'artifacts/criteria/editor-'+width+'.png',timeout:30000});
 }
 await page.getByRole('textbox',{name:'Motivo del cambio'}).fill('Prueba aislada del editor visual');
 const expected=await page.evaluate(()=>window.configEditor.read());
 await Promise.all([page.waitForNavigation({waitUntil:'domcontentloaded'}),page.waitForResponse(r=>r.url().endsWith('/config/publish')&&r.status()===200),page.locator('#criteria-publish').click()]);
 await page.waitForLoadState('domcontentloaded');
 active=await context.request.get(base+'/demo/api/v1/admin/config');
 assert.deepEqual((await active.json()).config,expected);
 await page.waitForFunction(()=>window.configEditor);
 const newTopic=page.getByRole('spinbutton',{name:'prueba editorial · valor',exact:true});
 await newTopic.fill('4');
 await page.locator('#criteria-reset').click();
 assert.deepEqual(await page.evaluate(()=>window.configEditor.read()),expected);
 assert.equal(await page.locator('#criteria-publish').isDisabled(),true);
 assert.deepEqual(errors,[]);
 console.log('PASS: draft, keyboard slider, validation, preview invalidation, source names, mobile, publish persistence, reset and demo isolation.');
}finally{
 const token=await page.locator('meta[name="csrf-token"]').getAttribute('content').catch(()=>null);
 if(token)await context.request.post(base+'/demo/api/v1/auth/logout',{headers:{'X-Requested-With':'AgendaRadar','X-CSRF-Token':token},data:{}}).catch(()=>{});
 await browser.close();
}
