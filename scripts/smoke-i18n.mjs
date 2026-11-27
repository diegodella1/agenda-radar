import assert from 'node:assert/strict';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base=process.env.SMOKE_BASE_URL || 'http://127.0.0.1:8879';
const credentials=process.env.PRODUCTION_CREDENTIALS ? JSON.parse(await readFile('secrets/initial-admin.json','utf8')) : {email:'admin@example.test',password:'local-preview-password'};
const output=process.env.SMOKE_OUTPUT || 'artifacts/i18n';
await mkdir(output,{recursive:true});
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});
try {
 const context=await browser.newContext();const page=await context.newPage();const errors=[],texts={};
 page.setDefaultTimeout(30000);page.on('pageerror',e=>errors.push(e.message));
 const response=await context.request.post(base+'/api/v1/auth/login',{headers:{'X-Requested-With':'AgendaRadar'},data:credentials});
 assert.equal(response.status(),200,'Administrator login failed');
 for(const language of ['en','es']) {
  await page.goto(base+'/home?lang='+language);
  assert.equal(await page.locator('html').getAttribute('lang'),language);
  for(const path of ['/home','/about','/funcionalidades','/casos-de-uso','/roadmap','/','/compare','/trends','/alerts','/history','/assistant','/admin/sources','/admin/config','/admin/users','/admin/providers','/admin/prompts','/admin/operations','/admin/audit','/account']) {
   const result=await page.goto(base+path);
   assert.equal(result.status(),200,`${language} ${path}`);
   assert.equal(await page.locator('html').getAttribute('lang'),language);
   assert.equal(result.headers()['content-language'],language);
   if(path==='/admin/config') {
    await page.waitForFunction(()=>window.configEditor);
    await page.getByRole('heading',{name:language==='en'?'Priority by topic':'Prioridad por tema',exact:true}).waitFor();
    await page.locator('.criteria-section summary').evaluateAll(nodes=>nodes.forEach(node=>node.parentElement.open=true));
    await page.waitForTimeout(200);
   }
   texts[language+' '+path]=await page.locator('body').innerText();
   for(const width of [1440,390]) {
    await page.setViewportSize({width,height:1000});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`${language} ${path} overflow ${width}`);
   }
  }
  await page.goto(base+'/');
  await page.screenshot({path:`${output}/${language}-workspace.png`,fullPage:true});
 }
 assert.deepEqual(errors,[]);
 await writeFile(`${output}/texts.json`,JSON.stringify(texts,null,2));
 await writeFile(`${output}/results.json`,JSON.stringify({passed:true,pages:19,languages:['en','es'],widths:[1440,390],errors},null,2));
 console.log('Bilingual public site and administrator checks passed: 19 pages, both languages, desktop/mobile.');
} finally {await browser.close();}
