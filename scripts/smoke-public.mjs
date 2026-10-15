import { mkdir } from 'node:fs/promises';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.SMOKE_BASE_URL || 'http://127.0.0.1:8766';
const browser = await chromium.launch({headless:true, executablePath:process.env.CHROMIUM_PATH || '/usr/bin/chromium', args:['--no-sandbox','--disable-dev-shm-usage']});
try {
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await mkdir('artifacts/screenshots', {recursive:true});
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({width, height:1000});
    for (const path of ['/', '/home', '/about', '/funcionalidades', '/casos-de-uso', '/roadmap']) {
      const response = await page.goto(base + path);
      if (response.status() !== 200) throw new Error(`${path}: ${response.status()}`);
      if (await page.locator('h1').count() !== 1) throw new Error(`Missing unique h1: ${path}`);
      if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)) throw new Error(`Overflow: ${path} at ${width}`);
      const links = await page.locator('a').evaluateAll(nodes => nodes.map(n => n.getAttribute('href')));
      if (links.some(link => !link || link === '#')) throw new Error(`Placeholder link: ${path}`);
      if (path === '/home') await page.screenshot({path:`artifacts/screenshots/public-${width}.png`, fullPage:true});
    }
  }
  await page.goto(base + '/roadmap');
  await page.getByText('¿Publica noticias automáticamente?', {exact:true}).click();
  await page.getByText('No. El alcance actual es observar', {exact:false}).waitFor({state:'visible'});
  await page.locator('header').getByRole('link', {name:'Ingresar'}).click();
  await page.getByLabel('Correo', {exact:true}).waitFor();
  if (errors.length) throw new Error(errors.join('\n'));
  console.log('Public smoke passed: 6 routes × 3 widths, FAQ, login link, no overflow or JS errors.');
} finally { await browser.close(); }
