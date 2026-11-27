import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const base=process.env.SMOKE_BASE_URL||'http://127.0.0.1:8879';
const credentials=process.env.PRODUCTION_CREDENTIALS==='true'?JSON.parse(await readFile('secrets/initial-admin.json','utf8')):{email:'admin@example.test',password:'local-preview-password'};
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox','--disable-dev-shm-usage']});
try {
 for(const valid of [true,false]){
  const context=await browser.newContext();
  const page=await context.newPage();
  await page.goto(base+(valid?'/collaboration?lang=en&event=12':'/login?next=https%3A%2F%2Fexample.org%2F'));
  assert.equal(new URL(page.url()).pathname,'/login');
  await page.locator('[name=email]').fill(credentials.email);
  await page.locator('[name=password]').fill(credentials.password);
  await page.locator('form button').click();
  await page.waitForURL(url=>url.pathname===(valid?'/collaboration':'/'));
  assert.equal(new URL(page.url()).origin,new URL(base).origin);
  if(valid){
   assert.equal(new URL(page.url()).searchParams.get('event'),'12');
   await page.getByRole('heading',{name:'Agents & collaboration',exact:true}).waitFor();
  }
  await context.close();
 }
 console.log('Login return passed: anonymous collaboration redirects, authenticated return preserves destination, external next ignored.');
} finally {await browser.close();}
