// HIST-12: browser acceptance of the INERT historical interface against LOCAL builds and SYNTHETIC fixtures (loopback only; nothing is deployed).
// Driven by tests/hist12/browser.py. Env: CHROME_PATH, OUT_DIR, FIXTURES, DIST_PRODUCTION, DIST_TEST, LEGACY_JSON, VALID_SHA, NODE_PATH.
import {createRequire} from 'node:module';
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';

const require = createRequire(import.meta.url);
const {chromium} = require('playwright');
const E = process.env;
fs.mkdirSync(E.OUT_DIR, {recursive: true});
const results = [];
const check = (id, name, ok, detail = '') => {results.push({id, name, ok: !!ok}); console.log(`${ok ? 'PASS' : 'FAIL'}  ${id}  ${name}${!ok && detail !== '' ? `  [${String(detail).slice(0, 200)}]` : ''}`)};
const legacy = fs.readFileSync(E.LEGACY_JSON);
const fixture = n => fs.readFileSync(path.join(E.FIXTURES, `${n}.json`));

function serve(dir) {
  const types = {'.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml'};
  const srv = http.createServer((req, res) => {
    const u = new URL(req.url, 'http://x').pathname;
    const f = path.join(dir, u === '/' ? 'index.html' : u);
    if (!f.startsWith(dir) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); res.end(); return; }
    res.writeHead(200, {'content-type': types[path.extname(f)] || 'application/octet-stream'}); res.end(fs.readFileSync(f));
  });
  return new Promise(r => srv.listen(0, '127.0.0.1', () => r({srv, base: `http://127.0.0.1:${srv.address().port}/`})));
}
const browser = await chromium.launch({executablePath: E.CHROME_PATH, args: ['--no-sandbox']});
const prod = await serve(E.DIST_PRODUCTION), test = await serve(E.DIST_TEST);

// hist: fixture name | null (file answers 404)
async function open(base, hist, {width = 1280, init, suffix = ''} = {}) {
  const ctx = await browser.newContext({viewport: {width, height: 900}});
  const page = await ctx.newPage();
  const errors = [], pageErrors = [], requests = [];
  page.on('console', m => m.type() === 'error' && errors.push(m.text()));
  page.on('pageerror', e => pageErrors.push(String(e)));
  if (init) await page.addInitScript(init);
  await page.route('**/data/monthly.json*', route => route.fulfill({status: 200, contentType: 'application/json', body: legacy}));
  await page.route('**/data/historical.json*', route => {
    requests.push(route.request().url());
    if (hist === null) return route.fulfill({status: 404, body: 'not found'});
    return route.fulfill({status: 200, contentType: 'application/json', body: fixture(hist)});
  });
  await page.goto(base + suffix, {waitUntil: 'networkidle'});
  await page.waitForTimeout(500);
  return {ctx, page, errors, pageErrors, requests};
}
const body = p => p.innerText('body');
const tabs = p => p.getByRole('tab').count();
const actueelOk = async p => (await p.locator('#h-chart').count()) === 1 && /Nederlandse huizenprijzen/.test(await body(p));
const noOverflow = p => p.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
const seed = `try{localStorage.setItem('view','historisch');localStorage.setItem('hist','1');localStorage.setItem('historisch','true');sessionStorage.setItem('view','historisch');sessionStorage.setItem('hist','1')}catch(e){}`;
const HOSTILE = '?historisch=1&hist=1&view=historisch&tab=historisch#historisch';

// ---------------------------------------------------------------- H01 production build: inert whatever is served, requested or stored
for (const width of [1280, 375]) {
  const {ctx, page, errors, pageErrors, requests} = await open(prod.base, 'valid', {width, init: seed, suffix: HOSTILE});
  const t = await body(page);
  check('H01', `production ${width}px: Actueel works`, await actueelOk(page));
  check('H01', `production ${width}px: no tabs, no Historisch text, even with a valid file served, hostile URL and seeded storage`, (await tabs(page)) === 0 && !/\bhistorisch\b/i.test(t) && !/SYNTHETIC/i.test(t), t.slice(0, 120));
  check('H01', `production ${width}px: the historical file is never requested (empty pin list)`, requests.length === 0, requests.join(','));
  check('H01', `production ${width}px: no console or page errors`, errors.length === 0 && pageErrors.length === 0, errors.concat(pageErrors).join(' | '));
  await ctx.close();
}
// bundle scan: no fixture, no pinned hash, no historical file in the production output
{
  const files = []; const walk = d => fs.readdirSync(d, {withFileTypes: true}).forEach(e => e.isDirectory() ? walk(path.join(d, e.name)) : files.push(path.join(d, e.name)));
  walk(E.DIST_PRODUCTION);
  const all = files.map(f => fs.readFileSync(f, 'latin1')).join('\n');
  check('H01', 'production output: no historical.json and no fixture values or hashes', !files.some(f => /hist.*\.json$/i.test(f)) && !all.includes(E.VALID_SHA) && !/SYNTHETIC_TEST_ONLY_SOURCE/.test(all) && !all.includes('hist_gold'));
}

// ---------------------------------------------------------------- H02 test build, valid synthetic payload
{
  const {ctx, page, errors, pageErrors} = await open(test.base, 'valid');
  check('H02', 'tab list appears only with the authorized payload; Actueel is selected by default', (await tabs(page)) === 2 && (await page.locator('#tab-actueel').getAttribute('aria-selected')) === 'true' && await actueelOk(page));
  await page.locator('#tab-historisch').click(); await page.waitForTimeout(400);
  let t = await body(page);
  check('H02', 'Historisch view shows three panels, the notice and the synthetic alert', /NVM, mediane verkoopprijs/.test(t) && /CBS, gemiddelde verkoopprijs/.test(t) && /Vergelijking NVM \(mediaan\) en CBS \(gemiddelde\)/.test(t) && /niet gelijk te stellen met de actuele reeks/.test(t) && /SYNTHETIC_TEST_ONLY: dit zijn synthetische testgegevens/.test(t));
  check('H02', 'the current dashboard content is not shown inside the historical view', (await page.locator('#h-chart').count()) === 0 && (await page.url()).endsWith('#historisch'));
  check('H02', 'warnings: median vs mean, retrospective euro, no joining', /mediaan \(NVM\) en een gemiddelde \(CBS\)/.test(t) && /omgerekend uit guldens tegen 2,20371/.test(t) && /Er is niets aangevuld/.test(t));
  await page.locator('details.sources > summary').click(); await page.waitForTimeout(150); t = await body(page);
  check('H02', 'quality and source descriptions visible', /Kwaliteit per halfjaar/.test(t) && /Bron: SYNTHETIC_TEST_ONLY source/.test(t) && /rechtenstatus: SYNTHETIC_TEST_ONLY_NOT_A_RIGHTS_STATEMENT/.test(t));
  // tables
  for (const [id, rows, first] of [['t-nvm', 52, ['1975 H1', 'ƒ 7.777']], ['t-cbs', 60, ['1995-01', '€ 5.555']], ['t-cmp', 12, ['1995 H1']]]) {
    await page.locator(`button[aria-controls="${id}"]`).click(); await page.waitForTimeout(150);
    const trs = await page.$$eval(`#${id} tbody tr`, rs => rs.map(r => [...r.children].map(c => c.textContent)));
    check('H02', `table ${id}: ${rows} rows and the first row`, trs.length === rows && first.every(x => trs[0].some(c => c.replace(/ /g, ' ').includes(x))), JSON.stringify(trs[0]));
  }
  const nvm = await page.$$eval('#t-nvm tbody tr', rs => rs.map(r => [...r.children].map(c => c.textContent.replace(/ /g, ' '))));
  check('H02', 'NVM: original guilders and converted euro (÷ 2,20371) both shown; flags and quality in words', nvm[0][1] === 'ƒ 7.777' && nvm[0][2] === '€ 3.529' && nvm[0][3] === 'bevestigd' && /handmatig gecontroleerd/.test(nvm[0][4]) && /SYNTHETISCHE TESTDATA/.test(nvm[0][4]), JSON.stringify(nvm[0]));
  const cbs = await page.$$eval('#t-cbs tbody tr', rs => rs.map(r => r.firstElementChild.textContent));
  check('H02', 'CBS months stay separate: 1995-01 .. 1999-12, nothing after', cbs[0] === '1995-01' && cbs[59] === '1999-12' && !cbs.some(m => m >= '2000'));
  const cmp = await page.$$eval('#t-cmp tbody tr', rs => rs.map(r => r.firstElementChild.textContent.replace(/ /g, ' ')));
  check('H02', 'comparison: matching half-years 1995 H1 .. 2000 H2 as two separate columns', cmp[0] === '1995 H1' && cmp[11] === '2000 H2' && (await page.$$eval('#t-cmp thead th', hs => hs.map(h => h.textContent))).length === 3);
  // unit toggle
  await page.getByRole('button', {name: 'Euro, omgerekend (÷ 2,20371)'}).click(); await page.waitForTimeout(250);
  const lbl = await page.locator('#h-nvm').locator('xpath=ancestor::section[1]').locator('figure.chart').getAttribute('aria-label');
  check('H02', 'unit toggle switches the NVM chart to converted euro', /euro \(omgerekend\)/.test(lbl) && /Eenheid: euro, omgerekend uit guldens/.test(await body(page)));
  await page.getByRole('button', {name: 'Gulden (origineel)'}).click();
  check('H02', 'no console or page errors in the historical view', errors.length === 0 && pageErrors.length === 0, errors.concat(pageErrors).join(' | '));
  // back to Actueel
  await page.locator('#tab-actueel').click(); await page.waitForTimeout(400);
  check('H02', 'switching back restores the unchanged Actueel dashboard', await actueelOk(page) && !/mediane verkoopprijs/.test(await body(page)));
  await ctx.close();
}

// ---------------------------------------------------------------- H03 deep link and keyboard (authorized payload)
{
  const {ctx, page} = await open(test.base, 'valid', {suffix: '#historisch'});
  check('H03', 'deep link opens Historisch only because the payload is authorized', (await page.locator('#tab-historisch').getAttribute('aria-selected')) === 'true' && /NVM, mediane/.test(await body(page)));
  await page.locator('#tab-historisch').focus();
  await page.keyboard.press('ArrowLeft'); await page.waitForTimeout(200);
  check('H03', 'ArrowLeft moves to Actueel (roving tabindex, focus follows)', (await page.locator('#tab-actueel').getAttribute('aria-selected')) === 'true' && (await page.locator('#tab-actueel').getAttribute('tabindex')) === '0' && (await page.locator('#tab-historisch').getAttribute('tabindex')) === '-1' && await page.evaluate(() => document.activeElement.id) === 'tab-actueel');
  await page.keyboard.press('ArrowRight'); await page.waitForTimeout(200);
  check('H03', 'ArrowRight moves to Historisch; End and Home work', (await page.locator('#tab-historisch').getAttribute('aria-selected')) === 'true');
  await page.keyboard.press('Home'); await page.waitForTimeout(150);
  const home = (await page.locator('#tab-actueel').getAttribute('aria-selected')) === 'true';
  await page.keyboard.press('End'); await page.waitForTimeout(150);
  check('H03', 'Home selects Actueel, End selects Historisch', home && (await page.locator('#tab-historisch').getAttribute('aria-selected')) === 'true');
  const tb = page.locator('button[aria-controls="t-nvm"]'); await tb.focus(); await page.keyboard.press('Enter'); await page.waitForTimeout(150);
  check('H03', 'the table toggle is keyboard operable and exposes aria-expanded', (await tb.getAttribute('aria-expanded')) === 'true' && (await page.locator('#t-nvm').count()) === 1);
  const roles = await page.$$eval('[role=tablist]', n => n.length);
  check('H03', 'one tablist with two tabs and a labelled tabpanel; charts have text alternatives', roles === 1 && (await page.locator('[role=tabpanel][aria-labelledby=tab-historisch]').count()) === 1 && (await page.locator('figure.chart[role=img][aria-label]').count()) === 3);
  await ctx.close();
}

// ---------------------------------------------------------------- H04 mobile
{
  const {ctx, page, errors, pageErrors} = await open(test.base, 'valid', {width: 375, suffix: '#historisch'});
  check('H04', 'mobile 375px: historical view renders without horizontal page scroll', /NVM, mediane/.test(await body(page)) && await noOverflow(page));
  await page.locator('button[aria-controls="t-cmp"]').click(); await page.waitForTimeout(150);
  check('H04', 'mobile 375px: tables scroll inside their container; no page overflow; no errors', await noOverflow(page) && errors.length === 0 && pageErrors.length === 0, errors.join('|'));
  await ctx.close();
}

// ---------------------------------------------------------------- H05 comparison disabled
{
  const {ctx, page} = await open(test.base, 'valid_nocmp', {suffix: '#historisch'});
  const t = await body(page);
  check('H05', 'comparison panel absent when the payload does not authorize it; the other panels remain', !/Vergelijking NVM/.test(t) && /NVM, mediane/.test(t) && /CBS, gemiddelde/.test(t) && (await page.locator('#t-cmp').count()) === 0);
  await ctx.close();
}

// ---------------------------------------------------------------- H06 every refusal keeps Historisch hidden and Actueel working (hostile URL, seeded storage)
const refusals = [['missing file', null], ['malformed JSON', 'malformed'], ['unsupported schema', 'schema2'], ['altered payload (one byte)', 'unpinned_tampered'], ['valid but unpinned release', 'unpinned_other_release'],
  ['pinned, extra unauthorized series', 'pinned_extra_series'], ['pinned, missing half-year', 'pinned_missing_period'], ['pinned, unauthorized extra half-year', 'pinned_extra_period'],
  ['pinned, no provenance', 'pinned_no_provenance'], ['pinned, wrong unit', 'pinned_wrong_unit'], ['pinned, mean series with median kind', 'pinned_median_as_mean'],
  ['pinned, unauthorized comparison scope', 'pinned_bad_scope'], ['pinned, point without quality', 'pinned_no_quality'], ['pinned, synthetic marker missing', 'pinned_no_marker'],
  ['pinned, euro not guilder / 2,20371', 'pinned_eur_mismatch'], ['pinned, release not authorized', 'pinned_unauthorized_release'], ['pinned, wrong frequency', 'pinned_wrong_frequency'], ['pinned, unresolved quality', 'pinned_unresolved_quality']];
for (const [name, fixtureName] of refusals) {
  const {ctx, page, pageErrors} = await open(test.base, fixtureName, {init: seed, suffix: HOSTILE});
  const t = await body(page);
  check('H06', `refused (${name}): no tab, Actueel works, nothing historical or synthetic rendered, no message detail`, (await tabs(page)) === 0 && await actueelOk(page) && !/\bhistorisch\b|SYNTHETIC|mediane verkoopprijs|ƒ/i.test(t) && !/Dashboardgegevens niet beschikbaar/i.test(t) && pageErrors.length === 0, t.slice(0, 100));
  await ctx.close();
}

// ---------------------------------------------------------------- H07 summary
const failed = results.filter(r => !r.ok);
fs.writeFileSync(path.join(E.OUT_DIR, 'result.json'), JSON.stringify({total: results.length, failed: failed.length, results}, null, 1));
console.log(`\nRESULT: ${failed.length ? 'FAILURES PRESENT' : 'ALL CHECKS PASSED'} (${results.length - failed.length}/${results.length})`);
await browser.close(); prod.srv.close(); test.srv.close();
process.exit(failed.length ? 1 : 0);
