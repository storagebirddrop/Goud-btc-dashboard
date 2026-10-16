interface Env { DB: D1Database }
export const onRequestGet: PagesFunction<Env> = async ({env}) => {
 const {results}=await env.DB.prepare(`SELECT period, MAX(CASE WHEN series_id='gold_eur_oz' THEN value END) AS gold_eur_oz, MAX(CASE WHEN series_id='nl_house_avg_eur' THEN value END) AS house_eur, MAX(CASE WHEN series_id='nl_hpi' THEN value END) AS hpi FROM observations WHERE period >= '2000-01' GROUP BY period ORDER BY period`).all();
 const rows=results as Record<string,number|string|null>[];
 const firstGold=rows.find(r=>r.gold_eur_oz!=null)?.gold_eur_oz as number|undefined;
 const firstHpi=rows.find(r=>r.hpi!=null)?.hpi as number|undefined;
 const data=rows.map(r=>({...r,gold_grams_per_house:r.gold_eur_oz!=null&&r.house_eur!=null?Number(r.house_eur)/Number(r.gold_eur_oz)*31.1034768:null,gold_index:r.gold_eur_oz!=null&&firstGold?100*Number(r.gold_eur_oz)/firstGold:null,hpi_index:r.hpi!=null&&firstHpi?100*Number(r.hpi)/firstHpi:null}));
 return Response.json({data},{headers:{'Cache-Control':'public, max-age=3600'}});
};
