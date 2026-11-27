import assert from 'node:assert/strict';
import {mkdir, writeFile} from 'node:fs/promises';
const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.SMOKE_BASE_URL || 'http://127.0.0.1:8879';
const output = process.env.SMOKE_OUTPUT || 'artifacts/seo-public';
await mkdir(output, {recursive:true});
const browser = await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox','--disable-dev-shm-usage']});
try {
  const context = await browser.newContext({javaScriptEnabled:false});
  const page = await context.newPage();
  const pages = [];
  for (const lang of ['en','es']) {
    for (const path of ['/home','/funcionalidades','/casos-de-uso','/about','/roadmap']) {
      const url = `${base}${path}?lang=${lang}`;
      const response = await page.goto(url, {waitUntil:'domcontentloaded'});
      assert.equal(response.status(),200);
      assert.equal(await page.locator('html').getAttribute('lang'),lang);
      assert.equal(await page.locator('link[rel=canonical]').getAttribute('href'),url);
      assert.equal(await page.locator('link[hreflang]').count(),3);
      assert.equal(await page.locator('h1').count(),1);
      assert.equal(await page.locator('[itemprop=description]').count(),1);
      assert.equal((await page.locator('body').innerText()).includes('demo / demo'),false);
      assert.equal(await page.locator('.closing a.button').getAttribute('href'),'/demo/');
      for (const width of [1440,390,320]) {
        await page.setViewportSize({width,height:900});
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`${url}: overflow at ${width}`);
        if (path==='/home') assert.ok(await page.evaluate(()=>document.querySelector('.radar-preview').getBoundingClientRect().bottom <= document.querySelector('.principles').getBoundingClientRect().top), `${url}: preview overlaps next section at ${width}`);
        if (['/home','/roadmap'].includes(path) && width!==320) await page.screenshot({path:`${output}/${path.slice(1)}-${lang}-${width}.png`,fullPage:true});
      }
      pages.push({url,title:await page.title()});
    }
  }
  const robots = await context.request.get(base+'/robots.txt');
  assert.equal(robots.status(),200);
  assert.ok((await robots.text()).includes(`Sitemap: ${base}/sitemap.xml`));
  const sitemap = await context.request.get(base+'/sitemap.xml');
  assert.equal(sitemap.status(),200);
  const xml = await sitemap.text();
  assert.equal((xml.match(/<loc>/g)||[]).length,10);
  for (const {url} of pages) assert.ok(xml.includes(url));
  for (const path of ['/demo/','/demo/events/1','/login','/unknown-seo-check']) {
    const response=await context.request.get(base+path);
    assert.match(response.headers()['x-robots-tag'],/noindex/);
  }
  const report={passed:true,javascriptDisabled:true,pages,widths:[1440,390,320],checks:['canonical','hreflang','visible product schema','noindex','sitemap','robots','demo CTA','responsive']};
  await writeFile(`${output}/results.json`,JSON.stringify(report,null,2));
  console.log('SEO checks passed: 10 language URLs, no JavaScript, sitemap, robots, noindex and mobile layout.');
} finally { await browser.close(); }
