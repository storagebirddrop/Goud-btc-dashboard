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

export type SeriesKey='house_eur'|'hpi'|'hpi_index'|'gold_index'|'gold_grams_per_house'|'sat_per_house';
// sat_per_house is NOT part of the public JSON contract (etl/static_export.py does not emit it); the optional
// field only lets the registry type-check until a separate decision adds it.
export type Point={period:string;gold_eur_oz:number|null;house_eur:number|null;hpi:number|null;gold_grams_per_house:number|null;gold_index:number|null;hpi_index:number|null;sat_per_house?:number|null};
export type Kind='eur'|'index'|'gram'|'sat';
export type Category='nominal'|'index'|'alternative';
export type Publication='open'|'gated'|'withheld';
export type BaseId='2000'|'2020';
// An annotation marks a documented definition or source break of THAT series; it is drawn only in views that contain such a series.
export type Annotation={period:string;label:string};
export type SeriesDef={label:string;short:string;kind:Kind;category:Category;publication:Publication;unit:string;base?:BaseId;light:string;dark:string;dash?:string;source:string;gold?:boolean;annotations?:Annotation[]};
const WB_GOLD_BREAK:Annotation[]=[{period:'2025-06',label:'jun 2025: bronwijziging goud'}];

export const SERIES:Record<SeriesKey,SeriesDef>={
 house_eur:{label:'Gemiddelde verkoopprijs',short:'Verkoopprijs',kind:'eur',category:'nominal',publication:'open',unit:'EUR',light:'#2a78d6',dark:'#3987e5',source:'CBS StatLine 85773NED'},
 hpi:{label:'CBS-huizenprijsindex',short:'Prijsindex',kind:'index',category:'index',publication:'open',unit:'indexpunten, 2020 = 100',base:'2020',light:'#0e8a5f',dark:'#2fbf8c',source:'CBS StatLine 85773NED'},
 hpi_index:{label:'CBS-huizenprijsindex',short:'Prijsindex',kind:'index',category:'index',publication:'open',unit:'indexpunten, januari 2000 = 100',base:'2000',light:'#0e8a5f',dark:'#2fbf8c',source:'CBS StatLine 85773NED, eigen herbasering'},
 gold_index:{label:'Goudprijsindex',short:'Goudprijs',kind:'index',category:'index',publication:'gated',unit:'indexpunten, januari 2000 = 100',base:'2000',light:'#a87400',dark:'#eda100',dash:'6 3',source:'World Bank / ECB, eigen berekening',gold:true,annotations:WB_GOLD_BREAK},
 gold_grams_per_house:{label:'Gram goud per woning',short:'Goud per woning',kind:'gram',category:'alternative',publication:'gated',unit:'gram',light:'#6250d6',dark:'#9085e9',dash:'6 3',source:'World Bank / ECB / CBS, eigen berekening',gold:true,annotations:WB_GOLD_BREAK},
 sat_per_house:{label:'Satoshi per woning',short:'Sat per woning',kind:'sat',category:'alternative',publication:'withheld',unit:'satoshi',light:'#c4541a',dark:'#ef8a55',dash:'2 3',source:'nog niet vastgesteld'}
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

// The only gate between loaded data and the interface.
export function visibleKeys(data:Point[]):SeriesKey[]{
 return (Object.keys(SERIES) as SeriesKey[]).filter(k=>!isWithheld(k)&&data.some(p=>ok(p[k])));
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
