// LEGACY / SUPERSEDED (ADR-001: static JSON + Cloudflare Pages, no D1 in production).
// The UI reads /data/monthly.json, not this route. This Pages Function is retained only for the
// local D1 integration tests (the integration workflow lives on an unmerged branch, not on main).
// Fail-closed: the route answers 404 unless LEGACY_D1_API_ENABLED is exactly 'true', and even then it
// never returns gold values: the gold publication gate (GOLD_PUBLICATION_*, validate_gold) must not be bypassable here.
interface D1Statement { all(): Promise<{results: Record<string, unknown>[]}> }
interface D1Database { prepare(query: string): D1Statement }
interface Env { DB?: D1Database; LEGACY_D1_API_ENABLED?: string }
interface PagesContext { env: Env }
const NO_STORE = {'Cache-Control': 'no-store'};
export const onRequestGet = async ({env}: PagesContext): Promise<Response> => {
 if (env?.LEGACY_D1_API_ENABLED !== 'true') return Response.json({error: 'not_found'}, {status: 404, headers: NO_STORE});
 if (!env.DB) return Response.json({error: 'legacy_d1_unavailable'}, {status: 503, headers: NO_STORE});
 // Gold series are deliberately not selected: gold_* fields below are always null.
 let results: Record<string, unknown>[];
 try {
  ({results}=await env.DB.prepare(`SELECT period, MAX(CASE WHEN series_id='nl_house_avg_eur' THEN value END) AS house_eur, MAX(CASE WHEN series_id='nl_hpi' THEN value END) AS hpi FROM observations WHERE period >= '2000-01' GROUP BY period ORDER BY period`).all());
 } catch {
  // Controlled failure: no D1/driver error details are returned to the client.
  return Response.json({error: 'legacy_d1_unavailable'}, {status: 503, headers: NO_STORE});
 }
 const rows=results as Record<string,number|string|null>[];
 const firstHpi=rows.find(r=>r.hpi!=null)?.hpi as number|undefined;
 const data=rows.map(r=>({period:r.period,gold_eur_oz:null,house_eur:r.house_eur,hpi:r.hpi,gold_grams_per_house:null,gold_index:null,hpi_index:r.hpi!=null&&firstHpi?100*Number(r.hpi)/firstHpi:null}));
 return Response.json({data},{headers:{'Cache-Control':'public, max-age=3600'}});
};
