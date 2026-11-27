import assert from 'node:assert/strict';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const base=process.env.SMOKE_BASE_URL||'http://127.0.0.1:8879';
const output=process.env.SMOKE_OUTPUT||'artifacts/collaboration';
const production=process.env.PRODUCTION_CREDENTIALS==='true';
const credentials=production?JSON.parse(await readFile('secrets/initial-admin.json','utf8')):{email:'admin@example.test',password:'local-preview-password'};
await mkdir(output,{recursive:true});
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox','--disable-dev-shm-usage']});
try{
 const page=await browser.newPage();const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base+'/login?lang=en');
 await page.locator('[name=email]').fill(credentials.email);
 await page.locator('[name=password]').fill(credentials.password);
 await page.locator('form button[type=submit],form button:not([type])').first().click();
 await page.waitForURL(base+'/');
 await page.goto(base+'/collaboration?lang=en');
 await page.getByRole('heading',{name:'Agents & collaboration',exact:true}).waitFor();
 await page.locator('#collab-status .collab-row').first().waitFor();
 if(!production){
  const profileName='Enterprise test '+Date.now(),agentName='Morning briefing '+Date.now();
  const form=page.locator('#profile-form');
  await form.locator('[name=name]').fill(profileName);
  await form.locator('[name=model]').fill('local-model');
  await form.locator('[name=base_url]').fill('http://model.internal:11434/v1');
  await form.getByRole('button',{name:'Save',exact:true}).click();
  await page.locator('#profile-list').getByText(profileName,{exact:false}).waitFor();
  assert.equal(await form.locator('[name=enabled]').isChecked(),false);
  await form.getByRole('button',{name:'New',exact:true}).click();
  assert.equal(await form.locator('[name=id]').inputValue(),'');
  assert.equal(await form.locator('[name=timeout_seconds]').inputValue(),'45');
  const agent=page.locator('#agent-form');
  await agent.locator('[name=name]').fill(agentName);
  await agent.locator('[name=kind]').selectOption('briefing');
  await agent.getByRole('button',{name:'Save',exact:true}).click();
  await page.locator('#agent-list').getByText(agentName,{exact:false}).waitFor();
  await page.locator('#agent-list .collab-row').filter({hasText:agentName}).getByRole('button',{name:'Preview',exact:true}).click();
  await page.getByRole('heading',{name:'Preview — nothing sent'}).waitFor();
  assert.match(await page.locator('#agent-preview').innerText(),/No eligible evidence/);
 }
 for(const lang of ['en','es']){
  await page.goto(base+'/collaboration?lang='+lang);
  await page.locator('#collab-status .collab-row').first().waitFor();
  for(const width of [1440,390,320]){
   await page.setViewportSize({width,height:1000});
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,lang+' overflow '+width);
  }
  await page.screenshot({path:output+'/'+lang+'-mobile.png',fullPage:true});
 }
 assert.deepEqual(errors,[]);
 assert.equal(await page.locator('#collab-notice').innerText(),'');
 await writeFile(output+'/results.json',JSON.stringify({passed:true,languages:['en','es'],widths:[1440,390,320],readOnly:production,errors},null,2));
 console.log('Collaboration UI passed: bilingual, role-aware forms, mobile layout'+(production?' (read-only).':', disabled profile and agent preview.'));
}finally{await browser.close();}
