import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.SMOKE_BASE_URL || 'http://127.0.0.1:8879';
const browser = await chromium.launch({headless: true, executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium', args: ['--no-sandbox', '--disable-dev-shm-usage']});
try {
  const context = await browser.newContext({viewport: {width: 1440, height: 1000}});
  const page = await context.newPage();
  page.setDefaultTimeout(60000);
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(base + '/demo/login');
  await page.locator('input[name="email"]').fill('demo');
  await page.getByLabel('Contraseña', {exact:true}).fill('demo');
  await page.getByRole('button', {name:'Ingresar', exact:false}).click();
  await page.waitForURL(base + '/demo/');
  await page.getByText('Demo interactiva · Horizonte Federal', {exact:true}).waitFor();
  await page.locator('#demo-tour[open]').waitFor();
  await page.getByRole('button', {name:'Omitir tutorial', exact:true}).click();
  const status = await page.evaluate(async () => (await fetch('/demo/api/v1/demo/status')).json());
  assert.equal(status.ready, true);
  const comparison = await page.evaluate(async () => (await fetch('/demo/api/v1/agendas/compare?window=7d')).json());
  assert.ok(comparison.rows.length > 0);
  const references = comparison.rows.flatMap(row => row.documents).filter(doc => !doc.title.startsWith('[Cobertura simulada]'));
  assert.ok(references.length > 0);
  assert.ok(references.every(doc => doc.url.startsWith('https://') && !doc.url.includes('.example')));
  const event = comparison.rows[0].event_id;
  await page.goto(base + '/demo/events/' + event);
  await page.locator('input[name="reason"]').fill('Prueba privada de fuentes reales');
  await page.getByRole('button', {name:'Registrar decisión'}).click();
  await page.getByText('follow — Prueba privada de fuentes reales', {exact:false}).waitFor();
  await page.getByRole('button', {name:'Cargar novedades', exact:true}).click();
  await page.locator('#notice').waitFor({state:'visible'});
  await page.goto(base + '/demo/history');
  assert.ok((await page.textContent('main')).includes('Prueba privada de fuentes reales'));
  await page.goto(base + '/demo/admin/sources');
  assert.ok(await page.locator('a[href*="instagram.com/"]').count() >= 8);
  await mkdir('artifacts/screenshots', {recursive:true});
  for (const width of [1440, 1024, 768, 390, 320]) {
    await page.setViewportSize({width, height:1000});
    for (const path of ['/', '/compare', '/events/' + event, '/trends', '/admin/sources', '/integrations']) {
      const response = await page.goto(base + '/demo' + path, {waitUntil:'domcontentloaded'});
      assert.equal(response.status(), 200);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, `${path}: overflow at ${width}`);
      if ([1440,390].includes(width) && ['/', '/admin/sources'].includes(path)) {
        await page.screenshot({path:`artifacts/screenshots/real-demo-${width}-${path==='/'?'radar':'sources'}.png`, fullPage:false});
      }
    }
  }
  page.once('dialog', dialog => dialog.accept());
  await page.getByRole('button', {name:'Reiniciar demo', exact:true}).click();
  await page.waitForURL(base + '/demo/');
  await page.goto(base + '/demo/history');
  assert.ok(!(await page.textContent('main')).includes('Prueba privada de fuentes reales'));
  assert.deepEqual(errors, []);
  await page.getByRole('button', {name:'Salir', exact:true}).click();
  await page.waitForURL(base + '/demo/login');
  console.log(`Real demo passed: ${references.length} references, source profiles, decisions, updates, reset, 6 screens at 5 widths.`);
} finally {
  await browser.close();
}
