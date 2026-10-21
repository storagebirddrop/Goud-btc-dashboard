// GOLD-04: read-only browser check of the PUBLIC production site (desktop 1280 px and mobile 375 px).
// Needs playwright-core and a Chrome binary (CHROME_PATH). Writes screenshots to OUT_DIR only.
import {chromium} from 'playwright-core';
import fs from 'node:fs';
import {scan} from './gold_04_boundary.mjs';

const BASE = process.env.BASE_URL || 'https://goud-btc-dashboard.pages.dev/';
const OUT = process.env.OUT_DIR || 'gold04-shots';
fs.mkdirSync(OUT, {recursive: true});
const results = [];
const check = (name, ok, detail = '') => {results.push(!!ok); console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail !== '' ? `  [${detail}]` : ''}`)};


// Collects leaf elements mentioning Bitcoin terms, control labels and chart texts, then classifies them (gold_04_boundary.mjs).
async function boundaryScan(page) {
  const raw = await page.evaluate(() => {
    const re = /bitcoin|\bbtc\b|satoshi|\bsats?\b/i;
    const anc = e => { const a = []; for (let x = e.parentElement; x; x = x.parentElement) a.push(x.tagName); return a; };
    const leaves = [];
    for (const e of document.body.querySelectorAll('*')) {
      if (!re.test(e.textContent || '')) continue;
      if ([...e.children].some(c => re.test(c.textContent || ''))) continue; // leaf-most element only
      leaves.push({tag: e.tagName, cls: typeof e.className === 'string' ? e.className : '', ancestors: anc(e), text: e.textContent,
                   inControl: !!e.closest('button,a,[role=tab],[role=option],option,select,input,label'), inSvg: !!e.closest('svg')});
    }
    const controls = [];
    for (const e of document.querySelectorAll('button,a,[role=tab],[role=option],option,select,input,[aria-label],[title],img[alt]')) {
      for (const [k, v] of [['text', e.textContent], ['aria-label', e.getAttribute('aria-label')], ['title', e.getAttribute('title')],
                            ['value', e.value], ['alt', e.getAttribute('alt')]]) if (v) controls.push({kind: `${e.tagName}/${k}`, label: v});
    }
    const svgTexts = [...document.querySelectorAll('svg')].map(s => s.textContent || '');
    return {leaves, controls, svgTexts};
  });
  return scan(raw);
}

// Bypass probes: URL state and a poisoned JSON response (browser-side interception only; nothing is sent to the server).
async function bypassProbes(browser) {
  const probes = [['?series=sat_per_house', null], ['#sat_per_house', null], ['?view=sat_per_house&metric=btc', null], ['', 'inject']];
  for (const [suffix, mode] of probes) {
    const page = await browser.newPage({viewport: {width: 1280, height: 900}});
    if (mode === 'inject') {
      await page.route('**/data/monthly.json*', async route => {
        const res = await route.fetch();
        const body = await res.json();
        body.data = body.data.map(r => ({...r, sat_per_house: 123456789, btc_per_house: 1.2345, btc_eur: 61000}));
        await route.fulfill({response: res, json: body});
      });
    }
    await page.goto(BASE + suffix, {waitUntil: 'networkidle'});
    await page.waitForTimeout(1200);
    for (const cat of ['Prijsindex', 'Alternatieve waardering']) {
      const tab = page.getByText(cat, {exact: true}).first();
      if (await tab.waitFor({timeout: 8000}).then(() => true, () => false)) { await tab.click(); await page.waitForTimeout(500); }
    }
    const b = await boundaryScan(page);
    check(`bypass ${mode === 'inject' ? 'poisoned JSON (sat_per_house, btc_per_house, btc_eur in every row)' : suffix}: withheld series stay hidden`, b.violations.length === 0, b.violations.join(' | '));
    await page.close();
  }
}

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
  for (const cat of ['Prijsindex', 'Alternatieve waardering']) {
    const tab = page.getByText(cat, {exact: true}).first();
    const found = await tab.waitFor({timeout: 8000}).then(() => true, () => false);
    check(`${label}/${cat}: category control present`, found);
    if (!found) continue;
    await tab.click();
    await page.waitForTimeout(800);
    const text = await page.innerText('body');
    const l = text.toLowerCase();
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
  const boundary = await boundaryScan(page);
  check(`${label}: no Bitcoin/satoshi value, series, chart or control (copy note excepted)`, boundary.violations.length === 0, boundary.violations.join(' | '));
  console.log(`NOTE ${label}: approved Bitcoin copy found: ${JSON.stringify(boundary.allowed)}`);
  check(`${label}: no console/page errors`, errors.length === 0, errors.join(' | '));
  // A link actually resolves (HTTP status of the first source link)
  const href = await page.$$eval('a[href*="opendata.cbs.nl"]', as => as[0]?.href);
  if (href) {
    const r = await page.request.get(href).catch(e => ({status: () => `ERR ${e.message}`}));
    check(`${label}: CBS source link reachable`, Number(r.status()) < 400, r.status());
  }
  await page.close();
}
await bypassProbes(browser);
await browser.close();
const ok = results.every(Boolean);
console.log(`\nRESULT: ${ok ? 'ALL CHECKS PASSED' : 'FAILURES PRESENT'} (${results.filter(Boolean).length}/${results.length})`);
process.exit(ok ? 0 : 1);
