// HIST-13: PRIVATE browser verification of the REAL historical candidate (loopback only; REDACTED output: no value is ever printed, no screenshot, nothing stored).
// Driven by tests/hist13/private_browser.py. Env: CHROME_PATH, CAND_DIR, DIST_PRODUCTION, DIST_TEST, LEGACY_JSON, NODE_PATH.
import {createRequire} from 'node:module';
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';

const require = createRequire(import.meta.url);
const {chromium} = require('playwright');
const E = process.env;
const results = [];
const check = (id, name, ok) => {results.push({id, name, ok: !!ok}); console.log(`${ok ? 'PASS' : 'FAIL'}  ${id}  ${name}`)};   // never prints a detail
const legacy = fs.readFileSync(E.LEGACY_JSON);
const read = n => fs.readFileSync(path.join(E.CAND_DIR, n));
const on = read('preflight_on.json'), off = read('preflight_off.json'), candidate = read('historical.candidate.json');
const tampered = Buffer.from(on); tampered[tampered.indexOf(Buffer.from('"CONFIRMED"'))] ^= 0x01;   // one flipped byte inside a quality label
const doc = JSON.parse(on.toString('utf8'));
const S = id => doc.series.find(s => s.series_id === id).points;

const nl = new Intl.NumberFormat('nl-NL', {maximumFractionDigits: 0});
const eurF = new Intl.NumberFormat('nl-NL', {style: 'currency', currency: 'EUR', maximumFractionDigits: 0});
const norm = t => t.replace(/ /g, ' ').trim();
const nlg = v => `ƒ ${nl.format(v)}`, eur = v => eurF.format(v);
const half = p => `${p.slice(0, 4)} ${p.slice(5)}`;
const FLAG = {RETROSPECTIVE_EUR: 'in euro omgerekend (geen waargenomen europrijs)', VISUAL_P135_PER_PROJECT_CONTROL: 'handmatig gecontroleerd', HALF_YEAR_WEIGHTED: 'halfjaargemiddelde, gewogen met het aantal transacties'};
const flagsText = f => f.map(x => FLAG[x]).filter(Boolean).join('; ');
const QUAL = {CONFIRMED: 'bevestigd', PROPOSED: 'voorlopig'};

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
async function open(base, payload, {width = 1280, suffix = ''} = {}) {
  const ctx = await browser.newContext({viewport: {width, height: 900}});
  const page = await ctx.newPage();
  const errors = [], requests = [];
  page.on('console', m => m.type() === 'error' && errors.push('c'));
  page.on('pageerror', () => errors.push('p'));
  await page.route('**/data/monthly.json*', r => r.fulfill({status: 200, contentType: 'application/json', body: legacy}));
  await page.route('**/data/historical.json*', r => { requests.push(1); return r.fulfill({status: 200, contentType: 'application/json', body: payload}); });
  await page.goto(base + suffix, {waitUntil: 'networkidle'});
  await page.waitForTimeout(500);
  return {ctx, page, errors, requests};
}
const body = p => p.innerText('body');
const tabs = p => p.getByRole('tab').count();
const rowsOf = (page, id) => page.$$eval(`#${id} tbody tr`, rs => rs.map(r => [...r.children].map(c => c.textContent)));
const same = (got, want) => got.length === want.length && got.every((r, i) => r.length === want[i].length && r.every((c, j) => norm(c) === norm(want[i][j])));

// P01 production build: real payload served, empty pins -> never requested, no tab
for (const width of [1280, 375]) {
  const {ctx, page, errors, requests} = await open(prod.base, on, {width, suffix: '?historisch=1#historisch'});
  check('P01', `production build ${width}px: no request, no tab, no historical text, no errors`, requests.length === 0 && (await tabs(page)) === 0 && !/\bhistorisch\b/i.test(await body(page)) && errors.length === 0);
  await ctx.close();
}
// P02 test build with the in-memory-authorized real payload
{
  const {ctx, page, errors} = await open(test.base, on);
  check('P02', 'authorized (temporary pin): two tabs, Actueel selected by default', (await tabs(page)) === 2 && (await page.locator('#tab-actueel').getAttribute('aria-selected')) === 'true');
  await page.locator('#tab-historisch').click(); await page.waitForTimeout(400);
  const t = await body(page);
  check('P02', 'three panels, interpretation notice, median/mean warning, retrospective-euro text, no synthetic text',
    /NVM, mediane verkoopprijs/.test(t) && /CBS, gemiddelde verkoopprijs/.test(t) && /Vergelijking NVM \(mediaan\) en CBS \(gemiddelde\)/.test(t) && /niet gelijk te stellen met de actuele reeks/.test(t) &&
    /mediaan \(NVM\) en een gemiddelde \(CBS\)/.test(t) && /omgerekend uit guldens tegen 2,20371/.test(t) && !/SYNTHETIC/i.test(t));
  for (const id of ['t-nvm', 't-cbs', 't-cmp']) { await page.locator(`button[aria-controls="${id}"]`).click(); await page.waitForTimeout(120); }
  const nlgP = S('hist_nvm_median_nlg_h'), eurP = S('hist_nvm_median_eur_retro_h'), cbsP = S('hist_cbs_avg_eur_m'), halfP = S('hist_cbs_avg_eur_h');
  const wantNvm = nlgP.map((p, i) => [half(p.period), nlg(Number(p.value)), eur(Number(eurP[i].value)), QUAL[p.quality], flagsText(p.flags)]);
  const gotNvm = await rowsOf(page, 't-nvm');
  check('P02', 'NVM table: 52 half-years, original guilders, retrospective euros, quality and flags equal the candidate', gotNvm.length === 52 && same(gotNvm, wantNvm));
  check('P02', 'NVM: exactly 41 rows carry the page-135 verification label', gotNvm.filter(r => /handmatig gecontroleerd/.test(r[4])).length === 41);
  const wantCbs = cbsP.map(p => [p.period, eur(Number(p.value)), QUAL[p.quality], flagsText(p.flags)]);
  const gotCbs = await rowsOf(page, 't-cbs');
  check('P02', 'CBS table: 60 months 1995-01..1999-12 equal the candidate, none after 1999-12', gotCbs.length === 60 && same(gotCbs, wantCbs) && gotCbs[59][0] === '1999-12');
  const wantCmp = halfP.map(p => [half(p.period), eur(Number(eurP.find(e => e.period === p.period).value)), eur(Number(p.value))]);
  const gotCmp = await rowsOf(page, 't-cmp');
  check('P02', 'comparison table: 12 matching half-years, NVM median and CBS mean in separate columns', gotCmp.length === 12 && same(gotCmp, wantCmp));
  await page.locator('details.sources > summary').click(); await page.waitForTimeout(150);
  const t2 = await body(page);
  check('P02', 'source annotations: both sources with vintage, rights status UNVERIFIED for the NVM table, quality and flag explanations', /OTB 2001 Table B3\.8/.test(t2) && /CBS StatLine 85773NED/.test(t2) && /rechtenstatus: UNVERIFIED/.test(t2) && /CC BY 4\.0/.test(t2) && /bevestigd \(CONFIRMED\)/.test(t2) && /handmatig gecontroleerd/.test(t2));
  await page.getByRole('button', {name: 'Euro, omgerekend (÷ 2,20371)'}).click(); await page.waitForTimeout(200);
  check('P02', 'unit toggle switches the NVM panel to converted euro', /Eenheid: euro, omgerekend uit guldens/.test(await body(page)));
  check('P02', 'no console or page errors', errors.length === 0);
  await page.locator('#tab-actueel').click(); await page.waitForTimeout(300);
  check('P02', 'switching back restores the unchanged Actueel dashboard', (await page.locator('#h-chart').count()) === 1);
  await ctx.close();
}
// P03 comparison disabled
{
  const {ctx, page} = await open(test.base, off, {suffix: '#historisch'});
  const t = await body(page);
  check('P03', 'comparison panel absent when the payload does not authorize it; NVM and CBS panels remain', !/Vergelijking NVM/.test(t) && (await page.locator('#t-cmp').count()) === 0 && /NVM, mediane/.test(t) && /CBS, gemiddelde/.test(t));
  await ctx.close();
}
// P04 refusals on the real payloads
for (const [name, payload] of [['candidate with PENDING owner fields (pinned, structurally unauthorized)', candidate], ['one flipped byte (not pinned)', tampered]]) {
  const {ctx, page} = await open(test.base, payload, {suffix: '?historisch=1#historisch'});
  check('P04', `refused: ${name}: no tab, Actueel works, nothing historical rendered`, (await tabs(page)) === 0 && (await page.locator('#h-chart').count()) === 1 && !/\bhistorisch\b|mediane verkoopprijs|ƒ/i.test(await body(page)));
  await ctx.close();
}
// P05 mobile
{
  const {ctx, page, errors} = await open(test.base, on, {width: 375, suffix: '#historisch'});
  await page.locator('button[aria-controls="t-cmp"]').click(); await page.waitForTimeout(150);
  check('P05', 'mobile 375px: historical view renders without horizontal page scroll or errors', /NVM, mediane/.test(await body(page)) && await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1) && errors.length === 0);
  await ctx.close();
}
const failed = results.filter(r => !r.ok);
console.log(`\nRESULT: ${failed.length ? 'FAILURES PRESENT' : 'ALL CHECKS PASSED'} (${results.length - failed.length}/${results.length})`);
await browser.close(); prod.srv.close(); test.srv.close();
process.exit(failed.length ? 1 : 0);
