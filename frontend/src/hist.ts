// Historical view gate and logic (hist-publication/1, HIST-12). Pure data and functions: no React, no fetch, no storage, no URL access.
//
// The historical interface is INERT: `HIST_APPROVED_PAYLOAD_SHA256` is empty, so `activateHist` returns null for every input and the app does not even
// request /data/historical.json. A payload is accepted only when the SHA-256 of its exact bytes is pinned AND its structure matches the approved HD2 scope
// (series, frequency, currency, unit, definitions, exact periods, quality, flags, provenance, comparison). A label, a flag, a query parameter or browser
// storage never authorizes anything. This file is the TypeScript counterpart of etl/hist_publication.py; tests/test_hist_12_frontend.py keeps them equal.

export type HistId='hist_nvm_median_nlg_h'|'hist_nvm_median_eur_retro_h'|'hist_cbs_avg_eur_m'|'hist_cbs_avg_eur_h';
export type HistSpec={frequency:'semiannual'|'monthly';currency:'NLG'|'EUR';unit:string;kind:string;definition_id:string;layer:string;first:string;last:string;count:number;flags:string[]};
export type HistPoint={period:string;value:string;quality:string;flags:string[]};
export type HistSeries={series_id:HistId;points:HistPoint[]};
export type HistData={release:{id:string;decision_ref:string};provenance:{sources:{id:string;title:string;rights_status:string;vintage:string}[]};series:Record<HistId,HistSeries>;comparison:{authorized:boolean;first:string;last:string};synthetic:boolean};

// The approved Phase C0 series (HIST-11 HD2). Nothing else can be expressed: no gold, grams, index, CPI, Bitcoin, fuel or equity series.
export const HIST_APPROVED_PAYLOAD_SHA256:readonly string[]=[];
export const HIST_ALLOW_SYNTHETIC=false;
export const HIST_SPEC:Record<HistId,HistSpec>={
 hist_nvm_median_nlg_h:{frequency:'semiannual',currency:'NLG',unit:'NLG',kind:'median_price',definition_id:'nvm_median_existing_homes_nominal',layer:'normalized',first:'1975-H1',last:'2000-H2',count:52,flags:[]},
 hist_nvm_median_eur_retro_h:{frequency:'semiannual',currency:'EUR',unit:'EUR',kind:'median_price',definition_id:'nvm_median_existing_homes_nominal_retro_eur',layer:'normalized',first:'1975-H1',last:'2000-H2',count:52,flags:['RETROSPECTIVE_EUR']},
 hist_cbs_avg_eur_m:{frequency:'monthly',currency:'EUR',unit:'EUR',kind:'average_price',definition_id:'cbs_average_price_existing_homes',layer:'normalized',first:'1995-01',last:'1999-12',count:60,flags:['RETROSPECTIVE_EUR']},
 hist_cbs_avg_eur_h:{frequency:'semiannual',currency:'EUR',unit:'EUR',kind:'average_price',definition_id:'cbs_average_price_existing_homes_halfyear_weighted',layer:'derived',first:'1995-H1',last:'2000-H2',count:12,flags:['RETROSPECTIVE_EUR','HALF_YEAR_WEIGHTED']}
};
export const HIST_NLG_PER_EUR=2.20371;
export const HIST_SYNTHETIC_MARKER='SYNTHETIC_TEST_ONLY';
export const HIST_QUALITY_TEXT:Record<string,string>={CONFIRMED:'bevestigd',PROPOSED:'voorlopig'};
export const HIST_FLAG_TEXT:Record<string,string>={
 RETROSPECTIVE_EUR:'in euro omgerekend (geen waargenomen europrijs)',
 VISUAL_P135_PER_PROJECT_CONTROL:'handmatig gecontroleerd',
 HALF_YEAR_WEIGHTED:'halfjaargemiddelde, gewogen met het aantal transacties',
 [HIST_SYNTHETIC_MARKER]:'SYNTHETISCHE TESTDATA, geen echte waarnemingen'
};
const COMPARISON_SERIES:HistId[]=['hist_nvm_median_eur_retro_h','hist_cbs_avg_eur_h'];
const HEX64=/^[0-9a-f]{64}$/;
const VALUE=/^[0-9]+(\.[0-9]+)?$/;
const ROOT_KEYS=['comparison','provenance','release','schema','series'];
const REL_KEYS=['authorized_on','authorizer','comparison_authorized','decision_ref','id','publication_authorized','release_sha256','series_ids'];
const SRC_KEYS=['acquired_at','id','rights_status','sha256','title','vintage'];
const SER_KEYS=['asset_class','basis','breaks','currency','definition_id','frequency','index_base','inputs','kind','layer','observations','points','series_id','transforms','unit'];
const CMP_KEYS=['authorized','first','last','series','warning'];
const rec=(x:unknown):x is Record<string,unknown>=>typeof x==='object'&&x!==null&&!Array.isArray(x);
const keysIs=(o:unknown,k:string[])=>rec(o)&&JSON.stringify(Object.keys(o).sort())===JSON.stringify(k);
const str=(x:unknown):x is string=>typeof x==='string'&&x.length>0;

export function histPeriods(first:string,last:string,freq:'semiannual'|'monthly'):string[]{
 const out:string[]=[];
 if(freq==='semiannual'){
  let y=Number(first.slice(0,4)),h=Number(first[6]);const ey=Number(last.slice(0,4)),eh=Number(last[6]);
  while(y<ey||(y===ey&&h<=eh)){out.push(`${y}-H${h}`);if(h===2){y++;h=1}else h=2}
 }else{
  let y=Number(first.slice(0,4)),m=Number(first.slice(5));const ey=Number(last.slice(0,4)),em=Number(last.slice(5));
  while(y<ey||(y===ey&&m<=em)){out.push(`${y}-${String(m).padStart(2,'0')}`);if(m===12){y++;m=1}else m++}
 }
 return out;
}

// Returns the validated historical data only for exactly approved bytes; `sha` is the lowercase hex SHA-256 of the response body (null when it could not be
// computed). Every failure returns null WITHOUT any message: no payload detail may reach the interface.
export function activateHist(sha:string|null,doc:unknown,pins:readonly string[]=HIST_APPROVED_PAYLOAD_SHA256,allowSynthetic:boolean=HIST_ALLOW_SYNTHETIC):HistData|null{
 try{return activate(sha,doc,pins,allowSynthetic)}catch{return null}
}
function activate(sha:string|null,doc:unknown,pins:readonly string[],allowSynthetic:boolean):HistData|null{
 if(typeof sha!=='string'||!HEX64.test(sha)||!pins.includes(sha)||!keysIs(doc,ROOT_KEYS)||!rec(doc))return null;
 if(doc.schema!=='hist-publication/1')return null;
 const synthetic=JSON.stringify(doc).toLowerCase().includes(HIST_SYNTHETIC_MARKER.toLowerCase());
 if(synthetic&&!allowSynthetic)return null;
 if(!synthetic&&allowSynthetic)return null;
 const rel=doc.release,prov=doc.provenance,cmp=doc.comparison;
 if(!keysIs(rel,REL_KEYS)||!rec(rel)||rel.publication_authorized!==true||typeof rel.comparison_authorized!=='boolean'||!str(rel.id)||!str(rel.decision_ref)||!str(rel.authorizer)||!str(rel.authorized_on)||typeof rel.release_sha256!=='string'||!HEX64.test(rel.release_sha256))return null;
 if(!Array.isArray(doc.series)||!Array.isArray(rel.series_ids))return null;
 const ids=Object.keys(HIST_SPEC).sort();
 if(JSON.stringify([...rel.series_ids].sort())!==JSON.stringify(ids))return null;
 const got=doc.series.map(s=>rec(s)?s.series_id:null);
 if(JSON.stringify([...got].sort())!==JSON.stringify(ids))return null;
 // provenance
 if(!rec(prov)||JSON.stringify(Object.keys(prov).sort())!==JSON.stringify(['method_ids','sources'])||!Array.isArray(prov.method_ids)||!prov.method_ids.length||!prov.method_ids.every(str)||!Array.isArray(prov.sources)||!prov.sources.length)return null;
 const srcIds=new Set<string>();
 for(const s of prov.sources){if(!keysIs(s,SRC_KEYS)||!rec(s)||!SRC_KEYS.every(k=>str(s[k]))||!HEX64.test(String(s.sha256))||srcIds.has(String(s.id)))return null;srcIds.add(String(s.id))}
 const byId={} as Record<HistId,HistSeries>;
 for(const raw of doc.series){
  if(!rec(raw)||!keysIs(raw,SER_KEYS))return null;
  const id=raw.series_id as HistId,spec=HIST_SPEC[id];
  if(!spec||byId[id])return null;
  if(raw.frequency!==spec.frequency||raw.currency!==spec.currency||raw.unit!==spec.unit||raw.kind!==spec.kind||raw.definition_id!==spec.definition_id||raw.layer!==spec.layer)return null;
  if(raw.asset_class!=='housing'||raw.basis!=='nominal'||raw.index_base!==null||!Array.isArray(raw.observations)||raw.observations.length||!Array.isArray(raw.breaks)||!raw.breaks.every(b=>keysIs(b,['period','reason']))||!Array.isArray(raw.transforms)||!raw.transforms.length)return null;
  if(!Array.isArray(raw.inputs)||!raw.inputs.length)return null;
  for(const ref of raw.inputs){if(!Array.isArray(ref)||ref.length!==2||!HEX64.test(String(ref[1]))||!(srcIds.has(String(ref[0]))||ids.includes(String(ref[0]))))return null}
  const periods=histPeriods(spec.first,spec.last,spec.frequency);
  if(!Array.isArray(raw.points)||raw.points.length!==spec.count||periods.length!==spec.count)return null;
  const points:HistPoint[]=[];
  for(let i=0;i<periods.length;i++){
   const p=raw.points[i];
   if(!keysIs(p,['flags','period','quality','value'])||!rec(p)||p.period!==periods[i]||typeof p.value!=='string'||!VALUE.test(p.value)||!(Number(p.value)>0)||!Number.isFinite(Number(p.value)))return null;
   if(typeof p.quality!=='string'||!(p.quality in HIST_QUALITY_TEXT)||!Array.isArray(p.flags))return null;
   const flags=p.flags as unknown[];
   if(!flags.every(f=>typeof f==='string'&&f in HIST_FLAG_TEXT)||!spec.flags.every(f=>flags.includes(f))||(flags.includes(HIST_SYNTHETIC_MARKER)!==synthetic))return null;
   points.push({period:p.period as string,value:p.value,quality:p.quality,flags:flags as string[]});
  }
  byId[id]={series_id:id,points};
 }
 // retrospective euro = guilder / 2.20371 (denomination only)
 for(let i=0;i<byId.hist_nvm_median_nlg_h.points.length;i++){
  const nlg=Number(byId.hist_nvm_median_nlg_h.points[i].value),eur=Number(byId.hist_nvm_median_eur_retro_h.points[i].value),want=nlg/HIST_NLG_PER_EUR;
  if(Math.abs(eur-want)>1e-6*want)return null;
 }
 // comparison: disabled, or exactly the approved scope; the panel exists only when this block says so
 if(!keysIs(cmp,CMP_KEYS)||!rec(cmp)||typeof cmp.authorized!=='boolean'||cmp.warning!=='STATISTICS_DIFFER'||JSON.stringify(cmp.series)!==JSON.stringify(COMPARISON_SERIES)||cmp.first!=='1995-H1'||cmp.last!=='2000-H2')return null;
 if(cmp.authorized!==rel.comparison_authorized)return null;
 return {release:{id:rel.id as string,decision_ref:rel.decision_ref as string},provenance:{sources:(prov.sources as Record<string,string>[]).map(s=>({id:s.id,title:s.title,rights_status:s.rights_status,vintage:s.vintage}))},series:byId,comparison:{authorized:cmp.authorized,first:'1995-H1',last:'2000-H2'},synthetic};
}

export const HIST_HEADING_TEXT='Historische reeksen (1975 t/m 2000)';
export const HIST_NOTICE_TEXT='Historische reeksen zijn niet gelijk te stellen met de actuele reeks. NVM geeft een mediaan, CBS een gemiddelde; NVM is halfjaarlijks, CBS maandelijks. Er is niets aangevuld of geïnterpoleerd en de reeksen zijn niet aan elkaar of aan de actuele reeks gekoppeld.';
export const HIST_CMP_WARNING_TEXT='Let op: een mediaan (NVM) en een gemiddelde (CBS) zijn verschillende statistieken met een verschillende populatie. De twee lijnen zijn niet onderling vervangbaar en nooit samengevoegd; een verschil tussen de lijnen is geen meetfout of trend.';
export const HIST_RETRO_TEXT='Bedragen in euro vóór 2002 zijn omgerekend uit guldens tegen 2,20371 NLG per euro; ze zijn geen waargenomen europrijzen.';
export const HIST_BOUNDARY_TEXT='De actuele reeks (CBS, vanaf januari 2000) staat op het tabblad Actueel. Er is geen lijn tussen beide weergaven getrokken.';
