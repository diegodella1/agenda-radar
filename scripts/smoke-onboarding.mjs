import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.SMOKE_BASE_URL || 'http://127.0.0.1:8881';
const empty = process.env.SMOKE_EMPTY === 'true';
const blockedStorage = process.env.SMOKE_BLOCK_STORAGE === 'true';
const browser = await chromium.launch({headless:true, executablePath:process.env.CHROMIUM_PATH || '/usr/bin/chromium', args:['--no-sandbox','--disable-dev-shm-usage']});
const context = await browser.newContext({viewport:{width:1440,height:950}, reducedMotion:'reduce'});
if (blockedStorage) await context.addInitScript(() => {
  Object.defineProperty(window, 'sessionStorage', {get() {throw new DOMException('Storage blocked','SecurityError');}});
});
const page = await context.newPage();
page.setDefaultTimeout(Number(process.env.SMOKE_TIMEOUT_MS || 60000));
const errors = [], writes = [];
page.on('pageerror', error => errors.push(error.message));
page.on('request', request => {if (request.method() !== 'GET') writes.push(new URL(request.url()).pathname);});
const step = async number => {
  await page.locator(`#demo-tour[open][data-step="${number}"]`).waitFor();
  await page.waitForFunction(() => !document.querySelector('[data-tour-next]').disabled);
  assert.ok(await page.evaluate(() => document.querySelector('#demo-tour').contains(document.activeElement)), 'Focus stays in dialog');
};
const advance = async number => {await page.locator('[data-tour-next]').click(); await step(number);};
const login = async () => {
  await page.goto(base + '/demo/login');
  await page.locator('[name="email"]').fill('demo');
  await page.locator('[name="password"]').fill('demo');
  await page.getByRole('button',{name:'Ingresar',exact:false}).click();
  await step(0);
};
const snapshot = () => page.evaluate(async () => {
  const paths = ['/api/v1/admin/sources', '/api/v1/admin/config', '/history'];
  const results = [];
  for (const path of paths) {
    const response = await fetch('/demo' + path);
    if (!response.ok) throw new Error(`Snapshot failed: ${path}`);
    if (path === '/history') {
      const html = new DOMParser().parseFromString(await response.text(),'text/html');
      results.push(html.querySelector('main').textContent);
    } else results.push(await response.json());
  }
  return results;
});
async function checkLayout(number, width) {
  const layout = await page.evaluate(() => {
    const card = document.querySelector('.tour-card').getBoundingClientRect();
    const spot = document.querySelector('.tour-spotlight');
    const rect = spot.getBoundingClientRect();
    return {
      card:card.toJSON(), dialog:document.querySelector('#demo-tour').getBoundingClientRect().toJSON(),
      inside:card.left >= 0 && card.top >= 0 && card.right <= innerWidth + 1 && card.bottom <= innerHeight + 1,
      overflow:document.documentElement.scrollWidth > innerWidth,
      visible:!spot.hidden,
      overlap:!spot.hidden && card.left < rect.right && card.right > rect.left && card.top < rect.bottom && card.bottom > rect.top
    };
  });
  assert.equal(layout.inside, true, `Card outside viewport at ${width}, step ${number}: ${JSON.stringify(layout)}`);
  assert.equal(layout.overflow, false, `Horizontal overflow at ${width}, step ${number}`);
  assert.equal(layout.overlap, false, `Card hides target at ${width}, step ${number}`);
  if (number > 0 && number < 8 && !(empty && number === 4)) assert.equal(layout.visible, true, `Missing highlight at ${width}, step ${number}`);
}
try {
  await mkdir('artifacts/onboarding',{recursive:true});
  await login();
  console.log('Login and automatic welcome passed');
  const before = await snapshot();
  const loginWrites = writes.length;
  // Native modal traps Tab and leaves the underlying form untouched.
  for (let i=0;i<6;i++) {
    await page.keyboard.press('Tab');
    assert.ok(await page.evaluate(() => document.querySelector('#demo-tour').contains(document.activeElement)));
  }
  const sequence = empty ? [1,2,3,4,5,8] : [1,2,3,4,5,6,7,8];
  for (const number of sequence) {
    await advance(number);
    console.log(`Step ${number}: ${new URL(page.url()).pathname}`);
    if (number === 6) assert.ok(!(await page.locator('[data-tour="evidence"]').first().textContent()).includes('[Cobertura simulada]'));
    if (number === 2) {
      await page.reload(); await step(2);
      await page.locator('[data-tour-back]').click(); await step(1);
      await advance(2);
    }
    for (const width of [1440,768,390,320]) {
      await page.setViewportSize({width,height:width < 760 ? 740 : 950});
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      await checkLayout(number,width);
      if ([1440,390].includes(width) && [1,2,8].includes(number)) {
        await page.screenshot({path:`artifacts/onboarding/${empty?'empty':blockedStorage?'storage-blocked':'ready'}-${width}-step-${number}.png`});
      }
    }
    await page.setViewportSize({width:1440,height:950});
  }
  assert.equal(await page.locator('#tour-title').textContent(), empty ? 'Estamos preparando tu radar' : 'Ya está todo listo para explorar tu agenda');
  assert.equal(await page.locator('#tour-checklist .is-ready').count(), empty ? 2 : 3);
  assert.equal(writes.length,loginWrites,'The tutorial must not send writes');
  assert.deepEqual(await snapshot(),before,'Sources, criteria and decisions remain unchanged');
  await page.locator('[data-tour-next]').click();
  await page.reload();
  assert.equal(await page.locator('#demo-tour').isVisible(),false);
  await page.locator('[data-help]').first().click(); await step(0);
  await page.keyboard.press('Escape');
  await page.goto(base + '/demo/admin/sources');
  assert.equal(await page.locator('#demo-tour').isVisible(),false);
  await page.locator('[data-help]').first().click(); await step(0);
  await page.getByRole('button',{name:'Omitir tutorial',exact:true}).click();
  await page.reload();
  assert.equal(await page.locator('#demo-tour').isVisible(),false);
  // Reset does not rearm the tour; a new login does.
  page.once('dialog', dialog => dialog.accept());
  await Promise.all([
    page.waitForResponse(response => response.url().endsWith('/demo/') && response.request().isNavigationRequest()),
    page.getByRole('button',{name:'Reiniciar demo',exact:true}).click()
  ]);
  await page.waitForLoadState('domcontentloaded');
  assert.equal(await page.locator('#demo-tour').isVisible(),false);
  await page.getByRole('button',{name:'Salir',exact:true}).click();
  await page.waitForURL(base + '/demo/login');
  await login();
  await page.getByRole('button',{name:'Omitir tutorial',exact:true}).click();
  assert.deepEqual(errors,[]);
  console.log(`PASS onboarding: ${empty?'pending data':'ready data'}, ${blockedStorage?'blocked':'normal'} storage, 7 steps, final screen, keyboard, reload/back, skip, replay, reset, new login, 4 widths, no writes.`);
} catch (error) {
  await page.screenshot({path:'artifacts/onboarding/failure.png'}).catch(() => {});
  console.error('Browser errors:', errors);
  throw error;
} finally {
  const csrf = await page.locator('meta[name="csrf-token"]').getAttribute('content').catch(() => null);
  if (csrf) await context.request.post(base+'/demo/api/v1/auth/logout',{headers:{'X-Requested-With':'AgendaRadar','X-CSRF-Token':csrf},data:{}}).catch(() => {});
  await browser.close();
}
