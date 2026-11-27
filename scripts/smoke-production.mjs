import {readFile,mkdir} from 'node:fs/promises';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const credentials=JSON.parse(await readFile('secrets/initial-admin.json','utf8'));
const base=process.env.SMOKE_BASE_URL || 'https://aradar.diegodella.ar';
const browser=await chromium.launch({headless:true,executablePath:'/usr/bin/chromium',args:['--no-sandbox','--disable-dev-shm-usage']});
try {
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base+'/login');
 await page.locator('input[name="email"]').fill(credentials.email);
 await page.getByLabel('Contraseña',{exact:true}).fill(credentials.password);
 await page.getByRole('button',{name:'Ingresar'}).click();
 await page.waitForURL(base+'/');
 await page.getByRole('heading',{name:'Radar editorial'}).waitFor();
 for(const path of ['/compare','/trends','/alerts','/history','/assistant','/admin/sources','/admin/config','/admin/users','/admin/providers','/admin/prompts','/admin/operations','/admin/audit','/account']){
  const response=await page.goto(base+path);if(response.status()!==200)throw new Error(path+' '+response.status());
  if(process.env.SMOKE_IDLE_MS) await page.waitForTimeout(Number(process.env.SMOKE_IDLE_MS));
 }
 await page.goto(base+'/admin/operations');
 await page.getByRole('button',{name:'Ver diagnóstico de configuración'}).click();
 await page.locator('#readiness-result pre').waitFor();
 const cookies=await page.context().cookies();
 if(!cookies.some(c=>c.name==='radar_session' && c.secure && c.httpOnly))throw new Error('Missing secure session');
 await page.setViewportSize({width:390,height:844});await page.goto(base+'/');
 if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw new Error('Mobile overflow');
 await mkdir('artifacts/screenshots',{recursive:true});
 await page.screenshot({path:'artifacts/screenshots/production-mobile.png',fullPage:true});
 await page.getByRole('button',{name:'Salir',exact:true}).click();await page.waitForURL(base+'/login');
 if(errors.length)throw new Error(errors.join('\n'));
 console.log('HTTPS production smoke OK: login, 13 screens, diagnosis, secure cookie, mobile, logout. No media or provider data changed.');
} finally {await browser.close();}
