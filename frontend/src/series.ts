// Series registry for the dashboard. Pure data and functions: no React, no fetch, no side effects.
//
// A series is shown only when BOTH hold:
//   1. its `publication` is not 'withheld', and
//   2. the loaded /data/monthly.json holds at least one finite value for it.
// Neither condition authorizes publication on its own. A label here is not an approval, and a value in the
// JSON does not make a withheld series visible. What may reach the JSON is decided by the export pipeline
// (etl/static_export.py, etl/data_quality.py and the gold publication gate), never by this file.
//
// Publication values:
//   'open'     CBS data that the public export carries.
//   'gated'    derived gold series; the JSON stays null until the export pipeline's gate is opened.
//   'withheld' reserved for a future series (no approved method or source); never shown, whatever the JSON holds.
//
// New datasets join by adding one entry to SERIES (one entry per line; tests/test_frontend_series.py parses it).
// Raw gold_eur_oz is deliberately not part of the registry: it is never shown.

import type {BtcMeta} from './btc';
export type SeriesKey='house_eur'|'hpi'|'hpi_index'|'gold_index'|'gold_grams_per_house'|'btc_per_house'|'sat_per_house';
// sat_per_house is NOT part of the public JSON contract (etl/static_export.py does not emit it); the optional
// field only lets the registry type-check until a separate decision adds it.
export type Point={period:string;gold_eur_oz:number|null;house_eur:number|null;hpi:number|null;gold_grams_per_house:number|null;gold_index:number|null;hpi_index:number|null;sat_per_house?:number|null;btc_per_house?:number|null;btc_meta?:BtcMeta|null};
export type Kind='eur'|'index'|'gram'|'sat'|'btc';
export type Category='nominal'|'index'|'alternative';
export type Publication='open'|'gated'|'pinned'|'withheld';
export type BaseId='2000'|'2020';
// An annotation marks a documented definition or source break of THAT series; it is drawn only in views that contain such a series.
export type Annotation={period:string;label:string};
export type SeriesDef={label:string;short:string;kind:Kind;category:Category;publication:Publication;unit:string;base?:BaseId;light:string;dark:string;dash?:string;source:string;gold?:boolean;annotations?:Annotation[]};
const WB_GOLD_BREAK:Annotation[]=[{period:'2025-06',label:'jun 2025: bronwijziging goud'}];

export const SERIES:Record<SeriesKey,SeriesDef>={
 house_eur:{label:'Gemiddelde verkoopprijs',short:'Verkoopprijs',kind:'eur',category:'nominal',publication:'open',unit:'EUR',light:'#2a78d6',dark:'#3987e5',source:'CBS StatLine 85773NED'},
 hpi:{label:'CBS-huizenprijsindex',short:'Prijsindex',kind:'index',category:'index',publication:'open',unit:'indexpunten, 2020 = 100',base:'2020',light:'#0e8a5f',dark:'#2fbf8c',source:'CBS StatLine 85773NED'},
 hpi_index:{label:'CBS-huizenprijsindex',short:'Prijsindex',kind:'index',category:'index',publication:'open',unit:'indexpunten, januari 2000 = 100',base:'2000',light:'#0e8a5f',dark:'#2fbf8c',source:'CBS StatLine 85773NED, eigen herbasering'},
 gold_index:{label:'Goudprijsindex',short:'Goudprijs',kind:'index',category:'index',publication:'gated',unit:'indexpunten, januari 2000 = 100',base:'2000',light:'#a87400',dark:'#eda100',dash:'6 3',source:'World Bank (GOLD) en ECB (EXR.D.USD.EUR.SP00.A), eigen berekening',gold:true,annotations:WB_GOLD_BREAK},
 gold_grams_per_house:{label:'Gram goud per woning',short:'Goud per woning',kind:'gram',category:'alternative',publication:'gated',unit:'gram',light:'#6250d6',dark:'#9085e9',dash:'6 3',source:'World Bank (GOLD), ECB (EXR.D.USD.EUR.SP00.A) en CBS StatLine 85773NED, eigen berekening',gold:true,annotations:WB_GOLD_BREAK},
 btc_per_house:{label:'Bitcoin per woning',short:'BTC per woning',kind:'btc',category:'alternative',publication:'pinned',unit:'BTC',light:'#8a4bd6',dark:'#b58cf0',dash:'2 3',source:'Coin Metrics Community (PriceUSD), ECB (EXR.D.USD.EUR.SP00.A) en CBS StatLine 85773NED, eigen berekening'},
 sat_per_house:{label:'Satoshi per woning',short:'Sat per woning',kind:'sat',category:'alternative',publication:'pinned',unit:'satoshi',light:'#c4541a',dark:'#ef8a55',dash:'2 3',source:'Coin Metrics Community (PriceUSD), ECB (EXR.D.USD.EUR.SP00.A) en CBS StatLine 85773NED, eigen berekening'}
};

export const CATEGORIES:{id:Category;label:string;caption:string}[]=[
 {id:'nominal',label:'Nominale woningprijs',caption:'Gemiddelde verkoopprijs in euro, niet gecorrigeerd voor de samenstelling van de verkochte woningen.'},
 {id:'index',label:'Prijsindex',caption:'Relatieve verandering met een expliciete indexbasis. Een index is geen prijs in euro.'},
 {id:'alternative',label:'Alternatieve waardering',caption:'De woningprijs uitgedrukt in een andere eenheid dan euro.'}
];

export const CARD_KEYS:SeriesKey[]=['house_eur','hpi','gold_index','gold_grams_per_house'];

const BASE_TEXT:Record<BaseId,{label:string;caption:string}>={
 '2000':{label:'Januari 2000 = 100',caption:'januari 2000 = 100'},
 '2020':{label:'2020 = 100 (CBS)',caption:'2020 = 100 (CBS-basis)'}
};
const BASE_ORDER:BaseId[]=['2000','2020'];
export const BASES:{id:BaseId;label:string;caption:string;keys:SeriesKey[]}[]=BASE_ORDER.map(id=>({
 id,...BASE_TEXT[id],
 keys:(Object.keys(SERIES) as SeriesKey[]).filter(k=>SERIES[k].kind==='index'&&SERIES[k].base===id)
}));

export const ok=(v:number|null|undefined):v is number=>typeof v==='number'&&Number.isFinite(v);

export function isWithheld(k:SeriesKey):boolean{return SERIES[k].publication==='withheld'}

// The only gate between loaded data and the interface. A 'pinned' series (Bitcoin) is visible only when `pinned` is true, and the
// caller sets that only when the exact bytes of the loaded JSON match an approved composite hash (btc.ts, activateBtc); a field,
// a flag or a URL in the loaded data never does.
export function visibleKeys(data:Point[],pinned:boolean=false):SeriesKey[]{
 return (Object.keys(SERIES) as SeriesKey[]).filter(k=>!isWithheld(k)&&(SERIES[k].publication!=='pinned'||pinned)&&data.some(p=>ok(p[k])));
}

// ---- Chart views: what the central chart can show, derived only from the visible series ----
// A view is one selectable chart: a nominal level, one index base, or one alternative valuation.
export type View={id:string;category:Category;label:string;keys:SeriesKey[];kind:Kind;unit:string;baseLine:boolean};

export function chartViews(visible:SeriesKey[]):View[]{
 const vis=new Set(visible);const all=Object.keys(SERIES) as SeriesKey[];const views:View[]=[];
 for(const c of CATEGORIES){
  if(c.id==='index'){
   for(const b of BASES){const keys=b.keys.filter(k=>vis.has(k));if(keys.length)views.push({id:`index-${b.id}`,category:'index',label:b.label,keys,kind:'index',unit:`indexpunten, ${b.caption}`,baseLine:true})}
  }else{
   for(const k of all){const s=SERIES[k];if(s.category===c.id&&s.kind!=='index'&&vis.has(k))views.push({id:k,category:c.id,label:s.label,keys:[k],kind:s.kind,unit:s.unit,baseLine:false})}
  }
 }
 return views;
}

// ---- Period selection: one range ('YYYY-MM' .. 'YYYY-MM'), presets and free months share it ----
export type Range={from:string;to:string};
export type PresetId='all'|'2008'|'10y';
export const MONTH_RE=/^\d{4}-(0[1-9]|1[0-2])$/;

export function presetRange(id:PresetId,periods:string[]):Range|null{
 if(!periods.length)return null;
 const first=periods[0],last=periods[periods.length-1];
 if(id==='2008'){const f=periods.find(p=>p>='2008-01');return {from:f??first,to:last}}
 if(id==='10y')return {from:periods[Math.max(0,periods.length-120)],to:last};
 return {from:first,to:last};
}
// Keeps both ends inside the available months and from <= to; an invalid end falls back to the bound.
export function clampRange(r:Range,periods:string[]):Range|null{
 if(!periods.length)return null;
 const first=periods[0],last=periods[periods.length-1];
 let from=MONTH_RE.test(r.from)?r.from:first,to=MONTH_RE.test(r.to)?r.to:last;
 if(from<first)from=first;if(to>last)to=last;if(from>last)from=last;if(to<first)to=first;
 if(from>to)to=from;
 return {from,to};
}
export function sliceRange(data:Point[],r:Range):Point[]{return data.filter(p=>p.period>=r.from&&p.period<=r.to)}

// Annotations for a chart: only those declared by the series in the view, and only when that series has values
// on both sides of the break inside the shown rows (a break outside the data or the range is not drawn).
export function viewAnnotations(keys:SeriesKey[],rows:Point[]):Annotation[]{
 const out:Annotation[]=[];
 for(const k of keys){
  for(const a of SERIES[k].annotations??[]){
   const spans=rows.some(r=>r.period<a.period&&ok(r[k]))&&rows.some(r=>r.period>=a.period&&ok(r[k]))&&rows.some(r=>r.period===a.period);
   if(spans&&!out.some(o=>o.period===a.period&&o.label===a.label))out.push(a);
  }
 }
 return out;
}

// ---- Gold transparency (GOLD-03 prep): source block shown under every chart view that contains a gold series ----
// The JSON contract has no date field, so the source reference date ('peildatum bronstand') is ONE constant here.
// It MUST be updated at every release (data refresh) by whoever publishes the gold values.
// Nothing here claims a licence, approval or endorsement by any source organization.
export type GoldSourceAsOf={date:string;note:string};
export const GOLD_SOURCE_ASOF:GoldSourceAsOf={date:'2026-10-19',note:'Datum van de gebruikte bronbestanden (World Bank Pink Sheet-workbook, ECB-koersen, CBS-tabel); bij elke gegevensrelease bijwerken.'};
export const METHODOLOGY_URL='https://github.com/storagebirddrop/Goud-btc-dashboard/blob/main/docs/governance/METHODOLOGY.md';
export type SourceLink={name:string;detail:string;url:string;linkText:string};
export const GOLD_SOURCE_LINKS:SourceLink[]=[
 {name:'World Bank Commodity Markets (Pink Sheet)',detail:'GOLD, USD per troy ounce, maandgemiddelde',url:'https://www.worldbank.org/en/research/commodity-markets',linkText:'worldbank.org, Commodity Markets'},
 {name:'Europese Centrale Bank (ECB), euro foreign exchange reference rates',detail:'reeks EXR.D.USD.EUR.SP00.A (USD per EUR)',url:'https://data.ecb.europa.eu/data/datasets/EXR/EXR.D.USD.EUR.SP00.A',linkText:'data.ecb.europa.eu, EXR.D.USD.EUR.SP00.A'},
 {name:'CBS StatLine 85773NED',detail:'gemiddelde verkoopprijs bestaande koopwoningen',url:'https://opendata.cbs.nl/CBS/nl/dataset/85773NED/table',linkText:'opendata.cbs.nl, 85773NED'}
];
export const GOLD_OWN_CALC_TEXT='Valutaomrekening, indexering en gram goud per woning zijn eigen berekeningen. Geen van de bronorganisaties onderschrijft deze toepassing.';
export const GOLD_METHOD_TEXT:string[]=[
 'Goudprijs in euro per troy ounce = maandgemiddelde World Bank-goudprijs in USD per troy ounce, gedeeld door het maandgemiddelde van de ECB-koers in USD per EUR.',
 'Goudprijsindex = die goudprijs in euro, met januari 2000 = 100.',
 'Gram goud per woning = CBS-gemiddelde verkoopprijs x 31,1034768 gram per troy ounce, gedeeld door de goudprijs in euro per troy ounce.'
];
export const GOLD_BREAK_TEXT='Definitiewijziging juni 2025: de World Bank-goudprijs (GOLD) gebruikte tot en met mei 2025 de London afternoon fixing (99,5% goud) en vanaf juni 2025 gemiddelde dagelijkse spotprijzen. De reeks is daardoor niet volledig benchmarkhomogeen.';
export const isIsoDate=(s:string):boolean=>/^\d{4}-\d{2}-\d{2}$/.test(s)&&(()=>{const t=new Date(`${s}T00:00:00Z`);return !Number.isNaN(t.getTime())&&t.toISOString().slice(0,10)===s})();
export function viewHasGold(keys:SeriesKey[]):boolean{return keys.some(k=>SERIES[k].gold===true)}
// First and last month with a finite value over all gold series of the view, computed from the loaded rows.
export function goldPeriod(data:Point[],keys:SeriesKey[]):{from:string;to:string;months:number}|null{
 const gk=keys.filter(k=>SERIES[k].gold===true);
 const ps=data.filter(p=>gk.some(k=>ok(p[k]))).map(p=>p.period).sort();
 return ps.length?{from:ps[0],to:ps[ps.length-1],months:ps.length}:null;
}
