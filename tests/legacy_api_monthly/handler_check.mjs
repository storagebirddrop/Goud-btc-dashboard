// Direct handler check for the legacy Pages Function (synthetic fake env; no Cloudflare, no network).
// Run: node tests/legacy_api_monthly/handler_check.mjs   (Node >= 22.18, native TypeScript type stripping)
import assert from 'node:assert/strict';
import {onRequestGet} from '../../frontend/functions/api/monthly.ts';

const SYNTHETIC = [
  {period: '2000-01', gold_eur_oz: 280, house_eur: 150000, hpi: 50},
  {period: '2000-02', gold_eur_oz: 300, house_eur: 160000, hpi: 55},
];
const queries = [];
const db = {prepare(q) { queries.push(q); return {all: async () => ({results: SYNTHETIC})}; }};
const GOLD = ['gold_eur_oz', 'gold_index', 'gold_grams_per_house'];

// 1. default (no flag, with and without DB): 404, DB never touched
for (const env of [{}, {DB: db}, {DB: db, LEGACY_D1_API_ENABLED: 'TRUE'}, {DB: db, LEGACY_D1_API_ENABLED: '1'}, {DB: db, LEGACY_D1_API_ENABLED: 'false'}]) {
  const r = await onRequestGet({env});
  assert.equal(r.status, 404, JSON.stringify(env));
  assert.equal(r.headers.get('cache-control'), 'no-store');
}
assert.equal(queries.length, 0, 'DB must not be queried while disabled');

// 2. enabled but no binding: 503, not a TypeError/500
assert.equal((await onRequestGet({env: {LEGACY_D1_API_ENABLED: 'true'}})).status, 503);

// 3. enabled with DB: 200, gold fields always null even if D1 holds gold values
const r = await onRequestGet({env: {DB: db, LEGACY_D1_API_ENABLED: 'true'}});
assert.equal(r.status, 200);
const {data} = await r.json();
assert.equal(data.length, 2);
for (const row of data) for (const k of GOLD) assert.equal(row[k], null, k);
assert.deepEqual(data.map(x => x.hpi_index), [100, 110]);
assert.ok(queries.length === 1 && !/gold/i.test(queries[0]), 'SQL must not select gold series');
console.log('legacy monthly handler checks passed');
