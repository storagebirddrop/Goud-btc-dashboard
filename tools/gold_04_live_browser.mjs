// GOLD-04: read-only browser check of the PUBLIC production site (desktop 1280 px and mobile 375 px).
// Needs playwright-core and a Chrome binary (CHROME_PATH). Writes screenshots to OUT_DIR only.
import {chromium} from 'playwright-core';
import fs from 'node:fs';

const BASE = process.env.BASE_URL || 'https://goud-btc-dashboard.pages.dev/';
const OUT = process.env.OUT_DIR || 'gold04-shots';
fs.mkdirSync(OUT, {recursive: true});
const results = [];
const check = (name, ok, detail = '') => {results.push(!!ok); console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail !== '' ? `  [${detail}]` : ''}`)};

const browser = await chromium.launch({executablePath: process.env.CHROME_PATH || '/usr/bin/google-chrome', args: ['--no-sandbox']});
for (const [label, width] of [['desktop', 1280], ['mobile', 375]]) {
  const page = await browser.newPage({viewport: {width, height: 900}});
  const errors = [];
  page.on('console', m => m.type() === 'error' && errors.push(m.text()));
  page.on('pageerror', e => errors.push(String(e)));
  await page.goto(BASE, {waitUntil: 'networkidle'});
  await page.waitForTimeout(1500);
  const noHScroll = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
  check(`${label}: no horizontal page scroll`, noHScroll);
  let everText = (await page.innerText('body')).toLowerCase();
  for (const cat of ['Prijsindex', 'Alternatieve waardering']) {
    await page.getByText(cat, {exact: true}).first().click();
    await page.waitForTimeout(800);
    const text = await page.innerText('body');
    const l = text.toLowerCase();
    everText += '\n' + l;
    const svg = await page.locator('svg.recharts-surface').count();
    check(`${label}/${cat}: chart rendered`, svg > 0, `svg=${svg}`);
    check(`${label}/${cat}: period 'januari 2000 t/m augustus 2026 (320 maanden)'`, /januari 2000 t\/m augustus 2026 \(320 maanden\)/.test(l));
    check(`${label}/${cat}: as-of date shown`, /peildatum bronstand: 19 oktober 2026/.test(l));
    for (const [n, re] of [['World Bank', /world bank/], ['ECB', /\becb\b|europese centrale bank/], ['CBS 85773NED', /85773ned/],
                           ['own calculation', /eigen berekening/], ['not endorsed', /onderschrijf/], ['June 2025 break', /juni 2025/]]) {
      check(`${label}/${cat}: shows ${n}`, re.test(l));
    }
    const links = await page.$$eval('a[href]', as => as.map(a => a.href));
    for (const host of ['worldbank.org', 'data.ecb.europa.eu', 'opendata.cbs.nl']) {
      check(`${label}/${cat}: clickable link to ${host}`, links.some(h => h.includes(host)), links.filter(h => h.includes(host)).join(' '));
    }
    const hasBreak = /jun 2025: bronwijziging goud/i.test(await page.evaluate(() => document.body.innerHTML + (document.querySelector('svg')?.outerHTML || '')));
    check(`${label}/${cat}: chart annotation for June 2025 (when gold in view)`, hasBreak || cat === 'Prijsindex');
    await page.screenshot({path: `${OUT}/${label}-${cat.split(' ')[0]}.png`, fullPage: true});
  }
  check(`${label}: no bitcoin/btc/satoshi text anywhere`, !/bitcoin|\bbtc\b|satoshi/.test(everText));
  check(`${label}: no console/page errors`, errors.length === 0, errors.join(' | '));
  // A link actually resolves (HTTP status of the first source link)
  const href = await page.$$eval('a[href*="opendata.cbs.nl"]', as => as[0]?.href);
  if (href) {
    const r = await page.request.get(href).catch(e => ({status: () => `ERR ${e.message}`}));
    check(`${label}: CBS source link reachable`, Number(r.status()) < 400, r.status());
  }
  await page.close();
}
await browser.close();
const ok = results.every(Boolean);
console.log(`\nRESULT: ${ok ? 'ALL CHECKS PASSED' : 'FAILURES PRESENT'} (${results.filter(Boolean).length}/${results.length})`);
process.exit(ok ? 0 : 1);
