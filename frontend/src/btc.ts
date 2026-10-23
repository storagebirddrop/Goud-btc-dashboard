// Bitcoin / satoshi interface logic (btc-monthly/1). Pure data and functions: no React, no fetch, no side effects.
//
// ACTIVATION. The interface shows Bitcoin values only when ALL hold:
//   1. the SHA-256 of the exact bytes of the loaded /data/monthly.json is listed in BTC_APPROVED_COMPOSITE_SHA256 (a code pin that is
//      empty today: changing it is a reviewed commit, like the backend registry etl/btc_contract.py ARTIFACT_RECORDS),
//   2. that JSON carries a structurally valid `btc` root block, and
//   3. the month itself is marked PUBLISHED by the contract and lies inside the authorized coverage.
// A JSON field, a boolean in the JSON, a URL, a stored value or an environment variable never activates anything.
import type {Point,SourceLink} from './series';
const ok=(v:number|null|undefined):v is number=>typeof v==='number'&&Number.isFinite(v);

export type BtcQuality='Q3'|'Q2'|'Q1_CANDIDATE';
export type BtcStatus='PUBLISHED'|'WITHHELD'|'MISSING';
export type BtcMeta={quality:BtcQuality|null;status:BtcStatus;missing_reason:string|null;flags:string[]};
export type BtcRoot={contract_version:string;coverage:{supported_from:string;default_from:string;authorized_from:string;authorized_through:string;early_history_authorized:boolean};release:{id:string;decision_ref:string;publication_authorized:true};provenance:{snapshot_id:string;vintage_reference_utc:string}};
// Exact approved composite artifacts (hash of the served bytes). EMPTY: nothing is shown in production.
export const BTC_APPROVED_COMPOSITE_SHA256:readonly string[]=[];
export const BTC_HOLD_MONTHS:readonly string[]=['2011-06'];
const MONTH=/^\d{4}-(0[1-9]|1[0-2])$/;
const HEX64=/^[0-9a-f]{64}$/;
const QUALITIES:readonly string[]=['Q3','Q2','Q1_CANDIDATE'];
const rec=(x:unknown):x is Record<string,unknown>=>typeof x==='object'&&x!==null&&!Array.isArray(x);

// Returns the validated root block only for exactly approved bytes. `sha` is the lowercase hex SHA-256 of the response body, or null
// when it could not be computed (then nothing is shown).
export function activateBtc(sha:string|null,doc:unknown,pins:readonly string[]=BTC_APPROVED_COMPOSITE_SHA256):BtcRoot|null{
 if(typeof sha!=='string'||!HEX64.test(sha)||!pins.includes(sha)||!rec(doc)||!rec(doc.btc))return null;
 const r=doc.btc,cov=r.coverage,rel=r.release,prov=r.provenance;
 if(r.contract_version!=='btc-monthly/1'||!rec(cov)||!rec(rel)||!rec(prov))return null;
 if(typeof prov.snapshot_id!=='string'||!/^btc04e-/.test(prov.snapshot_id)||typeof prov.vintage_reference_utc!=='string'||!/^\d{4}-\d{2}-\d{2}T/.test(prov.vintage_reference_utc))return null;
 const from=cov.authorized_from,through=cov.authorized_through;
 if(typeof from!=='string'||typeof through!=='string'||!MONTH.test(from)||!MONTH.test(through)||from>through)return null;
 if(typeof cov.supported_from!=='string'||typeof cov.default_from!=='string'||!MONTH.test(cov.default_from)||typeof cov.early_history_authorized!=='boolean')return null;
 if(rel.publication_authorized!==true||typeof rel.id!=='string'||!rel.id||typeof rel.decision_ref!=='string'||!rel.decision_ref)return null;
 return {contract_version:'btc-monthly/1',coverage:{supported_from:cov.supported_from,default_from:cov.default_from,authorized_from:from,authorized_through:through,early_history_authorized:cov.early_history_authorized},release:{id:rel.id,decision_ref:rel.decision_ref,publication_authorized:true},provenance:{snapshot_id:prov.snapshot_id,vintage_reference_utc:prov.vintage_reference_utc}};
}

// Only a month the contract marks PUBLISHED, inside the authorized coverage, with an allowed quality, yields a value.
export function btcShown(p:Point,root:BtcRoot|null):boolean{
 const m=p.btc_meta;
 if(!root||!m||m.status!=='PUBLISHED'||!m.quality||!QUALITIES.includes(m.quality))return false;
 if(p.period<root.coverage.authorized_from||p.period>root.coverage.authorized_through||BTC_HOLD_MONTHS.includes(p.period))return false;
 if(p.period<root.coverage.default_from&&!root.coverage.early_history_authorized)return false;
 return true;
}
export function btcMonthValue(p:Point,root:BtcRoot|null):number|null{return btcShown(p,root)&&ok(p.btc_per_house)&&p.btc_per_house>0?p.btc_per_house:null}
export function satMonthValue(p:Point,root:BtcRoot|null):number|null{return btcShown(p,root)&&ok(p.sat_per_house)&&p.sat_per_house>0?p.sat_per_house:null}
// Rows as the interface may use them: Bitcoin fields are nulled unless the month is shown (and always when there is no active root).
export function applyBtc(rows:Point[],root:BtcRoot|null):Point[]{
 return rows.map(p=>({...p,btc_per_house:btcMonthValue(p,root),sat_per_house:satMonthValue(p,root)}));
}
// Default start of a Bitcoin view: the default coverage start, never the earliest available month.
export function btcDefaultFrom(first:string,root:BtcRoot|null):string{return root&&root.coverage.default_from>first?root.coverage.default_from:first}
export function btcQualitiesIn(rows:Point[],root:BtcRoot|null):BtcQuality[]{
 const out:BtcQuality[]=[];
 for(const p of rows)if(btcShown(p,root)&&p.btc_meta?.quality&&!out.includes(p.btc_meta.quality))out.push(p.btc_meta.quality);
 return (['Q3','Q2','Q1_CANDIDATE'] as BtcQuality[]).filter(q=>out.includes(q));
}
export const BTC_NOTE_HEADER='Bitcoin: kwaliteit of reden zonder waarde';
export const BTC_QUALITY_SHORT:Record<BtcQuality,string>={Q3:'Q3 (indicatief)',Q2:'Q2',Q1_CANDIDATE:'Q1-kandidaat'};
// Table cell: the quality of a shown month, or the human reason why a month of the active coverage has no value. Never a number.
export function btcNote(p:Point,root:BtcRoot|null):string{
 const m=p.btc_meta;
 if(!root||!m)return '';
 if(btcShown(p,root))return m.quality?BTC_QUALITY_SHORT[m.quality]:'';
 if(p.period<root.coverage.default_from&&!root.coverage.early_history_authorized)return '';
 const reason=BTC_HOLD_MONTHS.includes(p.period)?'RESEARCH_ONLY_HOLD':m.missing_reason??'NOT_AUTHORIZED_PERIOD';
 return BTC_REASON_TEXT[reason]??'Geen waarde in deze maand.';
}
// Months of the shown range without a value, grouped by the contract's missing reason (never invented, never filled).
export function btcMissingSummary(rows:Point[],root:BtcRoot|null):{reason:string;text:string;months:string[]}[]{
 if(!root)return [];
 const by:Record<string,string[]>={};
 for(const p of rows){
  const m=p.btc_meta;
  if(!m||btcShown(p,root)||p.period<root.coverage.default_from&&!root.coverage.early_history_authorized)continue;
  const reason=BTC_HOLD_MONTHS.includes(p.period)?'RESEARCH_ONLY_HOLD':m.missing_reason??'NOT_AUTHORIZED_PERIOD';
  (by[reason]??=[]).push(p.period);
 }
 return Object.keys(by).sort().map(reason=>({reason,text:BTC_REASON_TEXT[reason]??'Geen waarde in deze maand.',months:by[reason]}));
}

export const BTC_QUALITY_TEXT:Record<BtcQuality,string>={Q3:'Q3: vroege markt met beperkte liquiditeit en reconstructieprovenance; indicatief en alleen met een afzonderlijk besluit numeriek getoond.',Q2:'Q2: afgeleid uit USD-referentieprijzen en de ECB-koers; voorlopige kwaliteitsindeling.',Q1_CANDIDATE:'Q1-kandidaat: sterkste bewijsdekking binnen dit onderzoek; nog niet als definitief gekwalificeerd.'};
export const BTC_REASON_TEXT:Record<string,string>={RESEARCH_ONLY_HOLD:'Niet gepubliceerd: bewust achtergehouden maand (onbewezen prijsversheid).',BEFORE_SUPPORTED_MONTH:'Geen waarde: voor augustus 2010 buiten de gevalideerde methodedekking.',NOT_AUTHORIZED_PERIOD:'Niet gepubliceerd: buiten de geautoriseerde periode.',PUBLICATION_NOT_AUTHORIZED:'Niet gepubliceerd: nog niet geautoriseerd.',RIGHTS_NOT_CLEARED:'Niet gepubliceerd: bronvoorwaarden nog niet afgerond.',INCOMPLETE_PERIOD:'Geen waarde: onvolledige brongegevens in deze maand.',SOURCE_NOT_PUBLISHED:'Geen waarde: bron nog niet verschenen.',SOURCE_UNAVAILABLE:'Geen waarde: bron niet beschikbaar.',FAILED_VALIDATION:'Geen waarde: validatie niet geslaagd.'};
export const BTC_SOURCE_LINKS:SourceLink[]=[{name:'Coin Metrics Community',detail:'PriceUSD, dagelijkse BTC-referentieprijs in USD (CC BY-NC 4.0)',url:'https://docs.coinmetrics.io/',linkText:'docs.coinmetrics.io'},{name:'Europese Centrale Bank (ECB), euro foreign exchange reference rates',detail:'reeks EXR.D.USD.EUR.SP00.A (USD per EUR)',url:'https://data.ecb.europa.eu/data/datasets/EXR/EXR.D.USD.EUR.SP00.A',linkText:'data.ecb.europa.eu, EXR.D.USD.EUR.SP00.A'},{name:'CBS StatLine 85773NED',detail:'gemiddelde verkoopprijs bestaande koopwoningen',url:'https://opendata.cbs.nl/CBS/nl/dataset/85773NED/table',linkText:'opendata.cbs.nl, 85773NED'}];
export const BTC_LICENSE_URL='https://creativecommons.org/licenses/by-nc/4.0/';
export const BTC_ATTRIBUTION_TEXT='Bronnen: Coin Metrics Community, reeks PriceUSD (dagelijkse USD-referentiewaarden; CC BY-NC 4.0); Europese Centrale Bank, EXR.D.USD.EUR.SP00.A (USD per EUR; bron: ECB); CBS StatLine 85773NED. Alle getoonde Bitcoin- en satoshiwaarden zijn eigen berekeningen en geen publicatie van Coin Metrics, de ECB of het CBS. Geen bronorganisatie onderschrijft deze toepassing.';
export const BTC_MODIFICATION_TEXT='Wijzigingen ten opzichte van de bronnen: de dagprijzen zijn gemiddeld per volledige UTC-kalendermaand (geen interpolatie of aanvulling van ontbrekende dagen), gedeeld door de maandgemiddelde ECB-koers tot een USD-afgeleide BTC/EUR-maandreferentie; daarmee is de CBS-gemiddelde verkoopprijs omgerekend naar BTC en satoshi per woning. De ruwe dagreeksen worden niet verspreid.';
export const BTC_DERIVED_TEXT='De BTC-prijs in euro is afgeleid uit een USD-referentieprijs en de ECB-koers; het is geen native europrijs en geen beursslotkoers.';
export const BTC_METHOD_TEXT:string[]=['BTC-prijs in euro = maandgemiddelde van de dagelijkse Coin Metrics-prijs in USD, gedeeld door het maandgemiddelde van de ECB-koers in USD per EUR.','BTC per woning = CBS-gemiddelde verkoopprijs gedeeld door die BTC-prijs in euro; satoshi per woning = BTC per woning x 100.000.000.','Alleen volledige kalendermaanden (UTC); ontbrekende maanden blijven leeg en worden niet aangevuld of geïnterpoleerd.'];
export const BTC_INTERPRETATION_TEXT='Een daling betekent minder BTC per gemiddeld verkochte woning volgens deze referentiemethode; dit zegt niet dat een identieke woning goedkoper is geworden. De teller is de nominale CBS-gemiddelde verkoopprijs in euro en hangt af van de samenstelling van de verkochte woningen.';
export const BTC_HOLD_TEXT='Juni 2011 is bewust niet beschikbaar; de lijn wordt niet over deze maand verbonden.';
export const BTC_HEADING_TEXT='Bronnen, methode en kwaliteit van de Bitcoinreeksen';
