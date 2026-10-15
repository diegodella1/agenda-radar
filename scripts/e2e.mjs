import {readFile, mkdir} from 'node:fs/promises';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const credentials=JSON.parse(await readFile('artifacts/e2e/credentials.json','utf8'));
const browser=await chromium.launch({headless:true, executablePath:process.env.CHROMIUM_PATH || '/usr/bin/chromium',args:['--no-sandbox','--disable-dev-shm-usage']});
const page=await browser.newPage({viewport:{width:1440,height:1000}});
const errors=[];page.on('pageerror',error=>errors.push(error.message));
const base=process.env.E2E_BASE_URL || 'http://127.0.0.1:8876';
try {
  await page.goto(base+'/login');
  await page.locator('input[name="email"]').fill(credentials.email);
  await page.getByLabel('Contraseña',{exact:true}).fill(credentials.password);
  await page.getByRole('button',{name:'Ingresar'}).click();
  await page.waitForURL(base+'/');
  await page.getByRole('heading',{name:'Radar editorial'}).waitFor();
  await mkdir('artifacts/screenshots',{recursive:true});
  await page.screenshot({path:'artifacts/screenshots/dashboard.png',fullPage:true});
  await page.locator('.event-title').first().click();
  await page.getByLabel('Motivo',{exact:true}).fill('Revisión editorial E2E');
  await page.getByRole('button',{name:'Registrar decisión'}).click();
  await page.getByText('Revisión editorial E2E',{exact:false}).last().waitFor();
  for (const path of ['/compare','/trends','/alerts','/history','/assistant','/admin/sources','/admin/config','/admin/users','/admin/providers','/admin/prompts','/admin/operations','/admin/audit']) {
    const response=await page.goto(base+path);if(response.status()!==200)throw new Error(path+' '+response.status());
    if(await page.locator('h1').count()!==1)throw new Error('Encabezado ausente '+path);
  }
  await page.setViewportSize({width:390,height:844});await page.goto(base+'/');
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
  if(overflow)throw new Error('Overflow móvil');
  await page.screenshot({path:'artifacts/screenshots/mobile.png',fullPage:true});
  if(errors.length)throw new Error(errors.join('\n'));
  console.log('E2E OK: login, dashboard, decisión, 12 pantallas, móvil sin overflow.');
} finally {await browser.close();}
