// BTC-07B P3: browser acceptance B01-B11 against LOCAL builds and SYNTHETIC fixtures (loopback only; nothing is deployed).
// Driven by tools/btc_07b_browser.py. Env: CHROME_PATH, OUT_DIR, FIXTURES, DIST_PRODUCTION, DIST_TEST, NODE_PATH (for playwright).
import {createRequire} from 'node:module';
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {scan} from './gold_04_boundary.mjs';

const require = createRequire(import.meta.url);
const {chromium} = require('playwright');
const E = process.env;
const OUT = E.OUT_DIR; fs.mkdirSync(OUT, {recursive: true});
const FX = E.FIXTURES;
const results = [];
const check = (id, name, ok, detail = '') => {results.push({id, name, ok: !!ok, detail: String(detail).slice(0, 300)}); console.log(`${ok ? 'PASS' : 'FAIL'}  ${id}  ${name}${detail !== '' ? `  [${String(detail).slice(0, 200)}]` : ''}`)};
const fixture = n => fs.readFileSync(path.join(FX, `${n}.json`));

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

async function open(base, fixtureName, {width = 1280, init, query = ''} = {}) {
  const ctx = await browser.newContext({viewport: {width, height: 900}});
  const page = await ctx.newPage();
  const errors = [];
  page.on('console', m => m.type() === 'error' && errors.push(m.text()));
  page.on('pageerror', e => errors.push(String(e)));
  if (init) await page.addInitScript(init);
  await page.route('**/data/monthly.json*', route => route.fulfill({status: 200, contentType: 'application/json', body: fixture(fixtureName)}));
  await page.goto(base + query, {waitUntil: 'networkidle'});
  await page.waitForTimeout(500);
  return {ctx, page, errors};
}
const body = page => page.innerText('body');
async function pick(page, cat, view) {
  if (cat) await page.getByRole('button', {name: cat, exact: true}).click();
  if (view) await page.getByRole('button', {name: view, exact: true}).click();
  await page.waitForTimeout(400);
}
async function openTable(page) {
  await page.locator('details.sources > summary').click();
  const btn = page.getByRole('button', {name: 'Toon als tabel'});
  if (await btn.count()) await btn.click();
  await page.waitForTimeout(300);
}
async function tableRows(page) {
  return page.$$eval('#data-table tbody tr', trs => trs.map(tr => [...tr.children].map(c => c.textContent)));
}
async function headers(page) { return page.$$eval('#data-table thead th', ths => ths.map(t => t.textContent)); }
const figLabel = page => page.locator('figure.chart').getAttribute('aria-label');
const nlBtc = v => new Intl.NumberFormat('nl-NL', {minimumFractionDigits: 2, maximumFractionDigits: 8}).format(v);
const nlSat = v => new Intl.NumberFormat('nl-NL', {maximumFractionDigits: 0}).format(v);
const BTC_VIEW = 'Bitcoin per woning', SAT_VIEW = 'Satoshi per woning', ALT = 'Alternatieve waardering';
const FORBID = /bitcoin per woning|satoshi per woning|\bbtc\b|\bsats?\b|kwaliteit van de bitcoinreeksen/i;
const stripNote = t => t.replace(/Nog niet beschikbaar: [^.\n]*\./g, '');

// ---------------------------------------------------------------- B01 production build, legacy JSON, 1280 and 375 px
for (const width of [1280, 375]) {
  const {ctx, page, errors} = await open(prod.base, 'legacy', {width});
  const txt = await body(page);
  check('B01', `${width}px: legacy period and CBS content, no horizontal scroll`, /januari 2000 t\/m augustus 2026 \(320 maanden\)/.test(txt.toLowerCase()) && await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
  await pick(page, 'Prijsindex');
  await openTable(page);
  const h = await headers(page);
  check('B01', `${width}px: table opens with CBS columns only`, h.length > 1 && !h.some(x => FORBID.test(x)), h.join('|'));
  const raw = await page.evaluate(() => {
    const re = /bitcoin|\bbtc\b|satoshi|\bsats?\b/i;
    const leaves = [];
    for (const e of document.body.querySelectorAll('*')) {
      if (!re.test(e.textContent || '') || [...e.children].some(c => re.test(c.textContent || ''))) continue;
      const a = []; for (let x = e.parentElement; x; x = x.parentElement) a.push(x.tagName);
      leaves.push({tag: e.tagName, cls: typeof e.className === 'string' ? e.className : '', ancestors: a, text: e.textContent, inControl: !!e.closest('button,a,[role=tab],select,input,label'), inSvg: !!e.closest('svg')});
    }
    const controls = [...document.querySelectorAll('button,a,select,input,[aria-label],[title]')].flatMap(e => [['t', e.textContent], ['a', e.getAttribute('aria-label')], ['ti', e.getAttribute('title')]].filter(x => x[1]).map(x => ({kind: e.tagName, label: x[1]})));
    return {leaves, controls, svgTexts: [...document.querySelectorAll('svg')].map(s => s.textContent || '')};
  });
  const b = scan(raw);
  check('B01', `${width}px: no Bitcoin value, series, chart or control (approved copy note excepted)`, b.violations.length === 0, b.violations.join(' | '));
  check('B01', `${width}px: no console errors`, errors.length === 0, errors.join(' | '));
  await page.screenshot({path: `${OUT}/B01-${width}.png`, fullPage: true});
  await ctx.close();
}

// ---------------------------------------------------------------- B02 exact numbers and formatting
{
  const {ctx, page, errors} = await open(test.base, 'exact');
  await pick(page, ALT, BTC_VIEW);
  const label = await figLabel(page);
  check('B02', 'BTC view: 6 BTC and exact 8-decimal value in NL notation', label.includes(`${nlBtc(6)} BTC`) && label.includes(`${nlBtc(5.5)} BTC`), label.slice(0, 160));
  await openTable(page);
  let rows = await tableRows(page), hs = await headers(page);
  const bi = hs.findIndex(x => x.startsWith('Bitcoin per woning')), si = hs.findIndex(x => x.startsWith('Satoshi per woning'));
  const r2 = rows.find(r => r[0] === '2014-03');
  check('B02', 'table: 6,12345678 BTC (max 8 decimals) and 612.345.678 sat (0 decimals)', r2 && r2[bi] === `${nlBtc(6.12345678)} BTC` && r2[si] === `${nlSat(612345678)} sat`, r2 && `${r2[bi]} / ${r2[si]}`);
  const r1 = rows.find(r => r[0] === '2014-02');
  check('B02', 'table: H=300000, P=60000, F=1.2 gives 6,00 BTC and 600.000.000 sat', r1 && r1[bi] === '6,00 BTC' && r1[si] === '600.000.000 sat', r1 && `${r1[bi]} / ${r1[si]}`);
  await pick(page, null, SAT_VIEW);
  const l2 = await figLabel(page);
  check('B02', 'SAT view: unit satoshi, integer notation', l2.includes('600.000.000 sat') && !/,\d+ sat/.test(l2), l2.slice(0, 160));
  check('B02', 'no console errors', errors.length === 0, errors.join(' | '));
  await page.screenshot({path: `${OUT}/B02.png`, fullPage: true});
  await ctx.close();
}

// ---------------------------------------------------------------- B03 default start 2014-02, no earlier numeric history; CBS keeps its full range
{
  const {ctx, page} = await open(test.base, 'real_default');
  await pick(page, ALT, BTC_VIEW);
  check('B03', 'default BTC view starts at 2014-02', (await page.inputValue('#from')) === '2014-02');
  await page.getByRole('button', {name: 'Alles', exact: true}).click();
  await page.waitForTimeout(300);
  check('B03', '"Alles" widens the range to the CBS start', (await page.inputValue('#from')) === '2000-01');
  await openTable(page);
  let rows = await tableRows(page), hs = await headers(page);
  const bi = hs.findIndex(x => x.startsWith('Bitcoin per woning'));
  const firstValue = rows.find(r => r[bi] !== '');
  const earlier = rows.filter(r => r[0] < '2014-02' && r[bi] !== '');
  check('B03', 'first numeric BTC month is 2014-02; no earlier numeric history', firstValue && firstValue[0] === '2014-02' && earlier.length === 0, firstValue && firstValue[0]);
  await page.fill('#from', '2005-01'); await page.waitForTimeout(300);
  rows = await tableRows(page);
  check('B03', 'wider free month range still shows no earlier numeric BTC value', rows.filter(r => r[0] < '2014-02' && r[bi] !== '').length === 0 && rows[0][0] === '2005-01');
  await pick(page, 'Nominale woningprijs');
  await page.getByRole('button', {name: 'Alles', exact: true}).click();
  check('B03', 'CBS view keeps its own full range from 2000-01', (await page.inputValue('#from')) === '2000-01' && /320 maanden/.test(await body(page)));
  await ctx.close();
}

// ---------------------------------------------------------------- B04 quality labels (table + tooltip), explained as evidence coverage
{
  const {ctx, page} = await open(test.base, 'real_default');
  await pick(page, ALT, BTC_VIEW);
  const txt = await body(page);
  check('B04', 'quality block explains Q2 and Q1-candidate as evidence coverage', /Q2:.*(USD-referentieprijzen|kwaliteitsindeling)/.test(txt) && /Q1-kandidaat:.*(bewijsdekking|niet als definitief)/.test(txt) && !/foutmarge/i.test(txt));
  await openTable(page);
  const rows = await tableRows(page), hs = await headers(page), ni = hs.length - 1;
  const q = p => (rows.find(r => r[0] === p) || [])[ni];
  check('B04', 'table: 2014-02 is Q2 and 2016-05 is Q1-kandidaat', q('2014-02') === 'Q2' && q('2016-05') === 'Q1-kandidaat', `${q('2014-02')} / ${q('2016-05')}`);
  // tooltips along the chart: first month and a late month
  await page.locator('figure.chart').scrollIntoViewIfNeeded();
  const box = await page.locator('figure.chart svg.recharts-surface').boundingBox();
  const tips = [];
  for (let dx = 40; dx < box.width - 10; dx += 12) { await page.mouse.move(box.x + dx, box.y + box.height / 2); await page.waitForTimeout(120); tips.push((await page.evaluate(() => document.querySelector('.recharts-tooltip-wrapper')?.innerText || '')).replace(/\n/g, ' / ')); }
  check('B04', 'tooltip of the first months (2014) names Q2', tips.some(t => /^(Februari|Maart|April) 2014 .*\(Q2\)/.test(t)), tips.find(t => /2014/.test(t)));
  check('B04', 'tooltip names Q1-kandidaat for a month from 2016-05 on', tips.some(t => /\(Q1-kandidaat\)/.test(t)), tips.find(t => /Q1-kandidaat/.test(t)));
  await ctx.close();
}

// ---------------------------------------------------------------- B05 early profile: Q3 caveat, June 2011 gap, two separate line subpaths
{
  const {ctx, page} = await open(test.base, 'real_early');
  await pick(page, ALT, BTC_VIEW);
  await page.getByRole('button', {name: 'Alles', exact: true}).click();
  await page.waitForTimeout(400);
  const txt = await body(page);
  check('B05', 'Q3 caveat shown (indicative)', /Q3:.*indicatief/.test(txt) || /Q3 \(indicatief\)/.test(txt));
  check('B05', 'June 2011 explained as deliberately withheld; hold text shown', /Juni 2011 is bewust niet beschikbaar/.test(txt) && /achtergehouden maand/.test(txt));
  const sub = await page.$$eval('figure.chart path.recharts-line-curve', ps => ps.map(p => (p.getAttribute('d').match(/M/g) || []).length));
  check('B05', 'the Bitcoin line consists of exactly two separate subpaths (no bridge across June 2011)', sub.length === 1 && sub[0] === 2, JSON.stringify(sub));
  await openTable(page);
  const rows = await tableRows(page), hs = await headers(page), bi = hs.findIndex(x => x.startsWith('Bitcoin per woning'));
  const g = p => rows.find(r => r[0] === p);
  check('B05', '2011-05 and 2011-07 have values, 2011-06 has none', g('2011-05')[bi] !== '' && g('2011-07')[bi] !== '' && g('2011-06')[bi] === '', `${g('2011-05')[bi]} | ${g('2011-06')[bi]} | ${g('2011-07')[bi]}`);
  await page.screenshot({path: `${OUT}/B05.png`, fullPage: true});
  await ctx.close();
}

// ---------------------------------------------------------------- B06 reasons are readable, never 0 or an empty field alone
{
  const {ctx, page} = await open(test.base, 'incomplete');
  await pick(page, ALT, BTC_VIEW);
  await openTable(page);
  const rows = await tableRows(page), hs = await headers(page), bi = hs.findIndex(x => x.startsWith('Bitcoin per woning')), ni = hs.length - 1;
  const r = rows.find(x => x[0] === '2015-07');
  check('B06', 'INCOMPLETE_PERIOD: value cell empty (not 0) and a human reason in the note column', r && r[bi] === '' && /onvolledige brongegevens/.test(r[ni]), r && r[ni]);
  check('B06', 'visible explanation outside the table lists the missing month', /onvolledige brongegevens in deze maand\. \(juli 2015\)/.test(await body(page)));
  await ctx.close();
  const e = await open(test.base, 'real_early');
  await pick(e.page, ALT, BTC_VIEW);
  await e.page.getByRole('button', {name: 'Alles', exact: true}).click();
  await openTable(e.page);
  const er = await tableRows(e.page), eh = await headers(e.page);
  const june = er.find(x => x[0] === '2011-06');
  check('B06', 'June 2011: empty value and RESEARCH_ONLY_HOLD reason text', june && june[eh.findIndex(x => x.startsWith('Bitcoin per woning'))] === '' && /bewust achtergehouden maand/.test(june[eh.length - 1]), june && june[eh.length - 1]);
  await e.ctx.close();
}

// ---------------------------------------------------------------- B07 / B08 sources, method, interpretation
{
  const {ctx, page} = await open(test.base, 'real_default');
  await pick(page, ALT, BTC_VIEW);
  const txt = await body(page), l = txt.toLowerCase();
  const links = await page.$$eval('aside.btc-src a[href]', as => as.map(a => a.href));
  for (const host of ['docs.coinmetrics.io', 'data.ecb.europa.eu', 'opendata.cbs.nl', 'creativecommons.org/licenses/by-nc/4.0']) check('B07', `link to ${host}`, links.some(h => h.includes(host)), links.join(' '));
  for (const [n, re] of [['own calculations', /eigen berekeningen/], ['full UTC calendar months', /volledige kalendermaanden \(utc\)/], ['USD-derived euro price', /afgeleid uit een usd-referentieprijs/], ['nominal CBS numerator', /nominale cbs-gemiddelde verkoopprijs/], ['no endorsement', /onderschrijft/], ['not investment advice', /geen beleggingsadvies/], ['authorized period shown', /februari 2014 t\/m augustus 2026/], ['release id shown', /synthetic-browser-fixture/]])
    check('B07', n, re.test(l));
  check('B08', 'interpretation: fewer BTC per average sold house, no claim of an identical house getting cheaper', /minder btc per gemiddeld verkochte woning/.test(l) && /dit zegt niet dat een identieke woning goedkoper is geworden/.test(l));
  await page.screenshot({path: `${OUT}/B07.png`, fullPage: true});
  await ctx.close();
}

// ---------------------------------------------------------------- B07b BTC-08B source vintage, modification notice and non-endorsement
{
  const {ctx, page} = await open(test.base, 'real_default');
  await pick(page, ALT, BTC_VIEW);
  const l = (await body(page)).toLowerCase();
  const vint = await page.$eval('aside.btc-src [data-btc-vintage]', e => e.textContent || '').catch(() => '');
  check('B07b', 'source vintage (snapshot id) is shown', /^btc04e-[0-9a-f]+$/.test(vint.trim()));
  check('B07b', 'modification notice is shown', /wijzigingen ten opzichte van de bronnen/.test(l) && /ruwe dagreeksen worden niet verspreid/.test(l));
  check('B07b', 'no source organisation is presented as publisher or endorser', /geen publicatie van coin metrics, de ecb of het cbs/.test(l) && /geen bronorganisatie onderschrijft/.test(l));
  await ctx.close();
}

// ---------------------------------------------------------------- B09 URL and storage cannot select or unlock anything
{
  const init = () => { try { localStorage.setItem('view', 'sat_per_house'); localStorage.setItem('series', 'sat_per_house'); sessionStorage.setItem('btc_range', '2000-01'); localStorage.setItem('early_history', 'true'); } catch (e) {} };
  const q = '?series=sat_per_house&view=sat_per_house#sat_per_house';
  const a = await open(prod.base, 'legacy', {init, query: q});
  check('B09', 'production build + query/hash/storage: no Bitcoin value or control', !FORBID.test(stripNote(await body(a.page))));
  await a.ctx.close();
  const b = await open(test.base, 'real_default', {init, query: q});
  const pressed = await b.page.$$eval('button[aria-pressed="true"]', bs => bs.map(x => x.textContent));
  check('B09', 'approved BTC build + query/hash/storage: BTC view not preselected, default range unchanged', !pressed.includes(BTC_VIEW) && !pressed.includes(SAT_VIEW) && (await b.page.inputValue('#from')) === '2000-01', pressed.join('|'));
  await pick(b.page, ALT, BTC_VIEW);
  await openTable(b.page);
  const rows = await tableRows(b.page), hs = await headers(b.page), bi = hs.findIndex(x => x.startsWith('Bitcoin per woning'));
  await b.page.getByRole('button', {name: 'Alles', exact: true}).click();
  const all = await tableRows(b.page);
  check('B09', 'stored "early_history" does not unlock numeric history before 2014-02', all.filter(r => r[0] < '2014-02' && r[bi] !== '').length === 0);
  await b.ctx.close();
}

// ---------------------------------------------------------------- B10 claims in the JSON never show Bitcoin by themselves
for (const [name, why] of [['poisoned_legacy', 'unauthorised numbers + publication flag in legacy rows'], ['unpinned_authorized_claim', 'full valid payload claiming publication_authorized=true, bytes not approved'],
                           ['pinned_bad_root', 'approved bytes but wrong method/contract id'], ['pinned_no_meta', 'approved bytes but rows without metadata']]) {
  const {ctx, page, errors} = await open(test.base, name);
  const txt = stripNote(await body(page));
  const svg = (await page.$$eval('svg', s => s.map(x => x.textContent || ''))).join(' ');
  const cats = await page.$$eval('button', bs => bs.map(x => x.textContent));
  check('B10', `${why}: no Bitcoin text, series, control or chart text`, !FORBID.test(txt) && !FORBID.test(svg) && !cats.some(c => FORBID.test(c)));
  await pick(page, 'Prijsindex');
  check('B10', `${why}: legacy gold/CBS view still renders`, (await page.locator('svg.recharts-surface').count()) > 0 && /320 maanden/.test(await body(page)));
  check('B10', `${why}: no console errors`, errors.length === 0, errors.join(' | '));
  await ctx.close();
}

// ---------------------------------------------------------------- B11 back to the legacy JSON: no stale Bitcoin
{
  const ctx = await browser.newContext({viewport: {width: 1280, height: 900}});
  const page = await ctx.newPage();
  let current = 'real_default';
  await page.route('**/data/monthly.json*', route => route.fulfill({status: 200, contentType: 'application/json', body: fixture(current)}));
  await page.goto(test.base, {waitUntil: 'networkidle'});
  await page.waitForTimeout(400);
  await pick(page, ALT, BTC_VIEW);
  check('B11', 'precondition: BTC view available on the approved payload', /Bitcoin per woning/.test(await body(page)));
  current = 'legacy';
  await page.reload({waitUntil: 'networkidle'});
  await page.waitForTimeout(400);
  const txt = stripNote(await body(page));
  const storage = await page.evaluate(() => localStorage.length + sessionStorage.length);
  check('B11', 'legacy JSON restored: Bitcoin gone, gold/CBS works, nothing stored', !FORBID.test(txt) && /320 maanden/.test(await body(page)) && storage === 0, `storage=${storage}`);
  await ctx.close();
}

await browser.close(); prod.srv.close(); test.srv.close();
const failed = results.filter(r => !r.ok);
fs.writeFileSync(`${OUT}/result.json`, JSON.stringify({executed: true, total: results.length, failed: failed.length, results}, null, 1) + '\n');
console.log(`\nRESULT: ${failed.length === 0 ? 'ALL CHECKS PASSED' : 'FAILURES PRESENT'} (${results.length - failed.length}/${results.length})`);
process.exit(failed.length === 0 ? 0 : 1);
