import React from 'react';
import {createRoot} from 'react-dom/client';
import {LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ReferenceLine, ResponsiveContainer} from 'recharts';
import './style.css';

import {SERIES,CATEGORIES,CARD_KEYS,visibleKeys,chartViews,presetRange,clampRange,sliceRange,viewAnnotations,viewHasGold,goldPeriod,GOLD_SOURCE_ASOF,GOLD_SOURCE_LINKS,GOLD_OWN_CALC_TEXT,GOLD_METHOD_TEXT,GOLD_BREAK_TEXT,METHODOLOGY_URL,MONTH_RE,ok} from './series';
import type {SeriesKey,Point,Kind,Range,PresetId} from './series';
import {activateBtc,applyBtc,btcNote,btcDefaultFrom,btcQualitiesIn,btcMissingSummary,BTC_QUALITY_TEXT,BTC_SOURCE_LINKS,BTC_LICENSE_URL,BTC_ATTRIBUTION_TEXT,BTC_DERIVED_TEXT,BTC_MODIFICATION_TEXT,BTC_METHOD_TEXT,BTC_INTERPRETATION_TEXT,BTC_HOLD_TEXT,BTC_HEADING_TEXT,BTC_NOTE_HEADER} from './btc';
import type {BtcRoot} from './btc';
import {useDark,useNarrow} from './hooks';
import {loadHist} from './histLoad';
import {histHashRequested,setHistHash,onHashChange} from './histNav';
import type {HistData} from './hist';
import {HistoricView} from './HistoricView';

const PRESETS:{id:PresetId;label:string}[]=[{id:'all',label:'Alles'},{id:'2008',label:'Sinds 2008'},{id:'10y',label:'Laatste 10 jaar'}];
const WARNING='De reeks toont de prijs van een gemiddeld verkochte bestaande koopwoning uitgedrukt in de gekozen rekeneenheid. De mix van verkochte woningen kan veranderen; de reeks meet geen constante woningkwaliteit of algemene betaalbaarheid. Dit is geen beleggingsadvies.';
const MIX_HINT='De verandering van de gemiddelde verkoopprijs weerspiegelt niet alleen prijsontwikkeling. Ze hangt ook af van welke woningen in de begin- en eindmaand zijn verkocht (transactiemix) en van uitschieters in een afzonderlijke maand. De CBS-huizenprijsindex corrigeert voor kwaliteitsverschillen en is daarvoor de betere maatstaf.';

const nf0=new Intl.NumberFormat('nl-NL',{maximumFractionDigits:0});
const nf1=new Intl.NumberFormat('nl-NL',{minimumFractionDigits:1,maximumFractionDigits:1});
const nf8=new Intl.NumberFormat('nl-NL',{minimumFractionDigits:2,maximumFractionDigits:8});
const nf2=new Intl.NumberFormat('nl-NL',{maximumFractionDigits:2});
const euro=new Intl.NumberFormat('nl-NL',{style:'currency',currency:'EUR',maximumFractionDigits:0});
const pct=new Intl.NumberFormat('nl-NL',{style:'percent',minimumFractionDigits:1,maximumFractionDigits:1,signDisplay:'exceptZero'});
function fmt(kind:Kind,v:number){return kind==='eur'?euro.format(v):kind==='gram'?`${nf0.format(v)} g`:kind==='sat'?`${nf0.format(v)} sat`:kind==='btc'?`${nf8.format(v)} BTC`:nf1.format(v)}
async function sha256Hex(buf:ArrayBuffer):Promise<string|null>{
 try{const d=await crypto.subtle.digest('SHA-256',buf);return [...new Uint8Array(d)].map(b=>b.toString(16).padStart(2,'0')).join('')}catch{return null}
}
function month(p:string){const [y,m]=p.split('-').map(Number);return new Date(Date.UTC(y,m-1,1)).toLocaleDateString('nl-NL',{month:'long',year:'numeric',timeZone:'UTC'})}
const colorOf=(k:SeriesKey,dark:boolean)=>dark?SERIES[k].dark:SERIES[k].light;

function InfoHint({id}:{id:string}){
 const [open,setOpen]=React.useState(false);
 return <span className="hint"><button type="button" className="hint-btn" aria-expanded={open} aria-controls={id} aria-label="Toelichting: gemiddelde verkoopprijs en transactiemix" onClick={()=>setOpen(!open)}>ⓘ</button>{open&&<span id={id} className="hint-text" role="note">{MIX_HINT}</span>}</span>
}

function Card({k,rows}:{k:SeriesKey;rows:Point[]}){
 const s=SERIES[k];const vals=rows.filter(p=>ok(p[k]));
 const first=vals[0],last=vals[vals.length-1];
 const a=first[k] as number,b=last[k] as number;const ch=vals.length>1&&a!==0?b/a-1:null;
 return <article className="card" aria-labelledby={`c-${k}`}>
  <h4><span id={`c-${k}`}>{s.label}</span>{k==='house_eur'&&<InfoHint id="hint-card"/>}</h4>
  <p className="big">{fmt(s.kind,b)}</p>
  <p className="sub">{month(last.period)} · {s.kind==='eur'?'EUR, nominaal':s.unit}</p>
  <dl>
   <div><dt>Begin periode, {month(first.period)}</dt><dd>{fmt(s.kind,a)}</dd></div>
   <div><dt>Verandering sinds begin periode</dt><dd className="delta">{ch===null?'n.v.t.':pct.format(ch)}</dd></div>
  </dl>
  <p className="status">Bron: {s.source}. {vals.length} {vals.length===1?'maand':'maanden'} met gegevens.</p>
 </article>
}

function asOfText(){const [y,m,d]=GOLD_SOURCE_ASOF.date.split('-').map(Number);return new Date(Date.UTC(y,m-1,d)).toLocaleDateString('nl-NL',{day:'numeric',month:'long',year:'numeric',timeZone:'UTC'})}
function BtcSources({rows,root}:{rows:Point[];root:BtcRoot}){
 const qs=btcQualitiesIn(rows,root),gaps=btcMissingSummary(rows,root);
 return <aside className="gold-src btc-src" aria-labelledby="h-btc-src">
  <h3 id="h-btc-src">{BTC_HEADING_TEXT}</h3>
  <ul>{BTC_SOURCE_LINKS.map(l=><li key={l.url}>{l.name}, {l.detail}: <a href={l.url}>{l.linkText}</a></li>)}</ul>
  <p>{BTC_ATTRIBUTION_TEXT} Licentie: <a href={BTC_LICENSE_URL}>CC BY-NC 4.0</a>.</p>
  <p>{BTC_DERIVED_TEXT}</p>
  <p data-btc-modification>{BTC_MODIFICATION_TEXT}</p>
  <p>Bronstand: <span data-btc-vintage>{root.provenance.snapshot_id}</span>, vastgelegd op <time dateTime={root.provenance.vintage_reference_utc}>{root.provenance.vintage_reference_utc.slice(0,10)}</time> (UTC). Latere bronrevisies zijn hierin niet verwerkt.</p>
  <p><strong>Methode.</strong> {BTC_METHOD_TEXT.join(' ')} <a href={METHODOLOGY_URL}>Volledige methodologie</a></p>
  <p>{BTC_INTERPRETATION_TEXT}</p>
  <p>Release: <span data-btc-release>{root.release.id}</span>, besluit {root.release.decision_ref}. Geautoriseerde periode: {month(root.coverage.authorized_from)} t/m {month(root.coverage.authorized_through)}.</p>
  {qs.length>0&&<ul className="btc-quality" aria-label="Kwaliteit per periode">{qs.map(q=><li key={q} data-q={q}>{BTC_QUALITY_TEXT[q]}</li>)}</ul>}
  {gaps.length>0&&<ul className="btc-gaps" aria-label="Maanden zonder waarde">{gaps.map(g=><li key={g.reason} data-reason={g.reason}>{g.text} ({g.months.length===1?month(g.months[0]):`${g.months.length} maanden`})</li>)}</ul>}
  {gaps.some(g=>g.reason==='RESEARCH_ONLY_HOLD')&&<p className="gold-break">{BTC_HOLD_TEXT}</p>}
  <p className="gold-break">Dit is geen beleggingsadvies en geen koersvoorspelling.</p>
 </aside>
}
function GoldSources({data,keys}:{data:Point[];keys:SeriesKey[]}){
 const per=goldPeriod(data,keys);
 return <aside className="gold-src" aria-labelledby="h-gold-src">
  <h3 id="h-gold-src">Bronnen en methode van de goudreeksen</h3>
  <ul>{GOLD_SOURCE_LINKS.map(l=><li key={l.url}>{l.name}, {l.detail}: <a href={l.url}>{l.linkText}</a></li>)}</ul>
  <p>{GOLD_OWN_CALC_TEXT}</p>
  <p>Periode goudreeks: {per?`${month(per.from)} t/m ${month(per.to)} (${per.months} ${per.months===1?'maand':'maanden'})`:'geen gegevens'}. Peildatum bronstand: <time dateTime={GOLD_SOURCE_ASOF.date}>{asOfText()}</time>.</p>
  <p><strong>Methode.</strong> {GOLD_METHOD_TEXT.join(' ')} <a href={METHODOLOGY_URL}>Volledige methodologie</a></p>
  <p className="gold-break">{GOLD_BREAK_TEXT}</p>
 </aside>
}

type TipProps={active?:boolean;payload?:{dataKey:string;value:number}[];label?:string;rows?:Point[]};
function Tip({active,payload,label,rows}:TipProps){
 if(!active||!payload?.length||!label)return null;
 const q=rows?.find(r=>r.period===label)?.btc_meta?.quality;
 return <div className="tip"><strong>{month(label)}</strong>{payload.filter(p=>ok(p.value)).map(p=>{const s=SERIES[p.dataKey as SeriesKey];return <div key={p.dataKey}>{s.short}: <b>{fmt(s.kind,p.value)}</b>{s.kind==='index'&&<small> ({s.unit})</small>}{(s.kind==='btc'||s.kind==='sat')&&q&&<small> ({q==='Q1_CANDIDATE'?'Q1-kandidaat':q})</small>}</div>})}</div>
}

function isoDot(rows:Point[],k:SeriesKey,color:string){
 // Isolated finite values (no finite neighbour) would be invisible as a line; show them as a dot.
 return (p:{cx?:number;cy?:number;index?:number})=>{const i=p.index??-1;const iso=i>=0&&ok(rows[i]?.[k])&&!ok(rows[i-1]?.[k])&&!ok(rows[i+1]?.[k]);
  return iso&&p.cx!==undefined&&p.cy!==undefined?<circle key={`d-${k}-${i}`} cx={p.cx} cy={p.cy} r={4} fill={color}/>:<g key={`d-${k}-${i}`}/>}
}
function Chart({rows,keys,dark,ariaLabel,yLabel,baseLine,height}:{rows:Point[];keys:SeriesKey[];dark:boolean;ariaLabel:string;yLabel:string;baseLine?:boolean;height:number}){
 const kind=SERIES[keys[0]].kind;
 const years=rows.length/12;const step=years<=6?1:years<=12?2:years<=20?4:5;
 const ticks=rows.map(r=>r.period).filter(p=>p.endsWith('-01')&&Number(p.slice(0,4))%step===0);
 const grid=dark?'#3a3a38':'#e4e3df',axis=dark?'#c3c2b7':'#52514e';
 const notes=viewAnnotations(keys,rows);
 return <figure className="chart" role="img" aria-label={ariaLabel}>
  <ResponsiveContainer width="100%" height={height}>
   <LineChart data={rows} accessibilityLayer margin={{top:8,right:16,bottom:4,left:4}}>
    <CartesianGrid stroke={grid} vertical={false}/>
    <XAxis dataKey="period" ticks={ticks} interval={0} tickFormatter={(p:string)=>p.slice(0,4)} tick={{fill:axis,fontSize:12}} stroke={grid} tickMargin={6}/>
    <YAxis width={kind==='eur'?78:kind==='btc'||kind==='sat'?64:48} domain={['auto','auto']} tickFormatter={(v:number)=>kind==='eur'?euro.format(v):kind==='btc'?nf2.format(v):nf0.format(v)} tick={{fill:axis,fontSize:12}} stroke={grid}/>
    <Tooltip content={<Tip rows={rows}/>} cursor={{stroke:axis,strokeDasharray:'3 3'}}/>
    {keys.length>1&&<Legend verticalAlign="top" height={30} formatter={(_v,e)=>{const k=(e as {dataKey?:string}).dataKey as SeriesKey;return <span style={{color:axis}}>{SERIES[k].short}</span>}}/>}
    {baseLine&&<ReferenceLine y={100} stroke={axis} strokeDasharray="2 4" label={{value:'basis = 100',position:'insideBottomRight',fill:axis,fontSize:11}}/>}
    {notes.map(a=><ReferenceLine key={a.period+a.label} x={a.period} stroke={axis} strokeDasharray="4 3" label={{value:a.label,position:'insideTopLeft',fill:axis,fontSize:11}}/>)}
    {keys.map(k=><Line key={k} type="monotone" dataKey={k} name={SERIES[k].label} dot={isoDot(rows,k,colorOf(k,dark))} stroke={colorOf(k,dark)} strokeWidth={2} strokeDasharray={SERIES[k].dash} connectNulls={false} isAnimationActive={false} activeDot={{r:5,stroke:dark?'#1a1a19':'#fcfcfb',strokeWidth:2}}/>)}
   </LineChart>
  </ResponsiveContainer>
  <figcaption className="ycap">Verticale as: {yLabel}</figcaption>
 </figure>
}

function summary(rows:Point[],keys:SeriesKey[]){
 return keys.map(k=>{const v=rows.filter(p=>ok(p[k]));if(!v.length)return '';const s=SERIES[k];return `${s.label}: van ${fmt(s.kind,v[0][k] as number)} in ${month(v[0].period)} naar ${fmt(s.kind,v[v.length-1][k] as number)} in ${month(v[v.length-1].period)}.`}).join(' ')
}

function MonthField({id,label,value,min,max,onCommit}:{id:string;label:string;value:string;min:string;max:string;onCommit:(v:string)=>void}){
 // Native month pickers are missing in some desktop browsers and fall back to text: keep a draft and commit only valid months.
 const [draft,setDraft]=React.useState(value);
 React.useEffect(()=>setDraft(value),[value]);
 return <label className="field" htmlFor={id}><span>{label}</span><input id={id} type="month" value={draft} min={min} max={max} placeholder="jjjj-mm" pattern="[0-9]{4}-[0-9]{2}"
  onChange={e=>{const v=e.target.value;setDraft(v);if(MONTH_RE.test(v))onCommit(v)}}
  onBlur={()=>setDraft(value)}/></label>
}

function App(){
 const [data,setData]=React.useState<Point[]>([]);
 const [btc,setBtc]=React.useState<BtcRoot|null>(null);
 const [error,setError]=React.useState('');
 const [loading,setLoading]=React.useState(true);
 const [range,setRange]=React.useState<Range|null>(null);
 const [catId,setCatId]=React.useState('');
 const [viewId,setViewId]=React.useState('');
 const [open,setOpen]=React.useState(false);
 const [hist,setHist]=React.useState<HistData|null>(null);
 const [view,setView]=React.useState<'actueel'|'historisch'>('actueel');
 const [table,setTable]=React.useState(false);
 const dark=useDark();
 const narrow=useNarrow();
 React.useEffect(()=>{fetch('/data/monthly.json').then(async r=>{if(!r.ok)throw Error(`HTTP ${r.status}`);const buf=await r.arrayBuffer();return {sha:await sha256Hex(buf),j:JSON.parse(new TextDecoder().decode(buf)) as {data:Point[]}|null}}).then(({sha,j})=>{if(!j||!Array.isArray(j.data))throw Error('Ongeldig dataformaat');const rows=j.data.filter(p=>p&&typeof p.period==='string'&&/^\d{4}-\d{2}$/.test(p.period));if(rows.length!==j.data.length)throw Error('Ongeldig dataformaat (periode)');const root=activateBtc(sha,j);setBtc(root);setData(applyBtc(rows,root))}).catch(e=>setError(String(e))).finally(()=>setLoading(false))},[]);


 // HIST-12: the historical payload is requested ONLY when a payload hash is pinned (histLoad.ts; default: no request at all). Any failure is silent.
 React.useEffect(()=>{let live=true;loadHist().then(h=>{if(live)setHist(h)});return()=>{live=false}},[]);
 // Deep link: '#historisch' is honoured only once a payload has been authorized by hash; it never grants access (histNav.ts).
 React.useEffect(()=>{
  if(!hist){setView('actueel');return}
  const apply=()=>setView(histHashRequested()?'historisch':'actueel');
  apply();return onHashChange(apply);
 },[hist]);
 const go=(v:'actueel'|'historisch')=>{if(!hist)return;setView(v);setHistHash(v==='historisch')};
 const onTabKey=(e:React.KeyboardEvent)=>{if(e.key==='ArrowRight'||e.key==='ArrowLeft'||e.key==='Home'||e.key==='End'){e.preventDefault();const next=e.key==='Home'?'actueel':e.key==='End'?'historisch':view==='actueel'?'historisch':'actueel';go(next);document.getElementById(`tab-${next}`)?.focus()}};
 const showHist=!!hist&&view==='historisch';

 const avail=React.useMemo(()=>new Set<SeriesKey>(visibleKeys(data,!!btc)),[data,btc]);
 const periods=React.useMemo(()=>data.map(p=>p.period),[data]);
 const full=periods.length?{from:periods[0],to:periods[periods.length-1]}:null;
 const isBtcView=!!btc&&(viewId==='btc_per_house'||viewId==='sat_per_house');
 const eff=(range&&clampRange(range,periods))||(isBtcView&&full?{from:btcDefaultFrom(full.from,btc),to:full.to}:full);
 const rows=eff?sliceRange(data,eff):[];
 const views=chartViews([...avail]);
 const cats=CATEGORIES.filter(c=>views.some(v=>v.category===c.id));
 const curCat=cats.find(c=>c.id===catId)??cats[0];
 const catViews=curCat?views.filter(v=>v.category===curCat.id):[];
 const curView=catViews.find(v=>v.id===viewId)??catViews[0];
 const cardKeys=CARD_KEYS.filter(k=>avail.has(k)&&rows.some(p=>ok(p[k])));
 const hasGold=[...avail].some(k=>SERIES[k].gold);
 const missing=['reële EUR',...(hasGold?[]:['goud']),...(btc?[]:['Bitcoin'])].join(', ').replace(/, ([^,]*)$/,' en $1');
 const shown=(Object.keys(SERIES) as SeriesKey[]).filter(k=>avail.has(k));
 const btcCols=!!btc&&shown.some(k=>SERIES[k].publication==='pinned');
 const first=data[0]?.period,last=data[data.length-1]?.period;
 const pressed=(id:PresetId)=>{const p=presetRange(id,periods);return !!p&&!!eff&&p.from===eff.from&&p.to===eff.to};
 const chartHasData=!!curView&&curView.keys.some(k=>rows.some(p=>ok(p[k])));
 const sources=curView?[...new Set(curView.keys.map(k=>SERIES[k].source))].join('; '):'';

 return <main>
  <header>
   <h1>Nederlandse huizenprijzen</h1>
   {data.length>0&&<p className="lede">Maandelijkse CBS-reeksen, {month(first)} t/m {month(last)}: gemiddelde verkoopprijs in euro en prijsindex.</p>}
   {!error&&!loading&&<p className="muted">Nog niet beschikbaar: {missing}.</p>}
  </header>
  {hist&&<div className="segs" role="tablist" aria-label="Weergave" onKeyDown={onTabKey}>
   <button type="button" role="tab" id="tab-actueel" aria-selected={view==='actueel'} aria-controls="view-main" tabIndex={view==='actueel'?0:-1} className="seg" onClick={()=>go('actueel')}>Actueel</button>
   <button type="button" role="tab" id="tab-historisch" aria-selected={view==='historisch'} aria-controls="view-main" tabIndex={view==='historisch'?0:-1} className="seg" onClick={()=>go('historisch')}>Historisch</button>
  </div>}
  {showHist&&hist?<div id="view-main" role="tabpanel" aria-labelledby="tab-historisch"><HistoricView data={hist}/></div>:error?<p role="alert" className="notice">Dashboardgegevens niet beschikbaar: {error}</p>:loading?<p role="status">Gegevens laden…</p>:data.length===0||avail.size===0||!eff?<p className="notice">Nog geen gevalideerde brongegevens geladen.</p>:<>
  <div className="toolbar" role="group" aria-label="Periode">
   <span className="tl">Periode</span>
   <span className="segs">{PRESETS.map(p=><button key={p.id} type="button" className="seg" aria-pressed={pressed(p.id)} onClick={()=>setRange(presetRange(p.id,periods))}>{p.label}</button>)}</span>
   <MonthField id="from" label="Van" value={eff.from} min={first} max={eff.to} onCommit={v=>setRange(clampRange({from:v,to:eff.to},periods))}/>
   <MonthField id="to" label="Tot en met" value={eff.to} min={eff.from} max={last} onCommit={v=>setRange(clampRange({from:eff.from,to:v},periods))}/>
   <span className="muted" role="status" aria-live="polite">{month(rows[0].period)} t/m {month(rows[rows.length-1].period)} ({rows.length} {rows.length===1?'maand':'maanden'})</span>
  </div>

  {curCat&&curView&&<section className="panel" aria-labelledby="h-chart">
   <div className="panel-head"><h2 id="h-chart">{curView.keys.length===1?curView.label:`Relatieve verandering, ${curView.label}`}</h2>
    {cats.length>1&&<div className="segs" role="group" aria-label="Soort weergave">{cats.map(c=><button key={c.id} type="button" className="seg" aria-pressed={curCat.id===c.id} onClick={()=>{setCatId(c.id);setViewId('')}}>{c.label}</button>)}</div>}</div>
   {catViews.length>1&&<div className="segs sub-segs" role="group" aria-label={curCat.id==='index'?'Indexbasis':'Reeks'}>{catViews.map(v=><button key={v.id} type="button" className="seg" aria-pressed={curView.id===v.id} onClick={()=>setViewId(v.id)}>{v.label}</button>)}</div>}
   <p className="cap">{curCat.caption}</p>
   <p className="cap">Eenheid: <strong>{curView.unit}</strong>{curView.keys[0]==='house_eur'&&<InfoHint id="hint-chart"/>}</p>
   {chartHasData?<Chart rows={rows} keys={curView.keys} dark={dark} height={narrow?260:340} yLabel={curView.unit} baseLine={curView.baseLine} ariaLabel={`Lijngrafiek, ${curView.unit}. ${summary(rows,curView.keys)}`}/>:<p className="notice" role="status">Geen gegevens voor deze weergave in de gekozen periode.</p>}
   {viewHasGold(curView.keys)&&<GoldSources data={data} keys={curView.keys}/>}
   {btc&&curView.keys.some(k=>SERIES[k].publication==='pinned')&&<BtcSources rows={rows} root={btc}/>}
   <p className="status">Bron: {sources}. Gebruik de pijltjestoetsen op de grafiek om waarden per maand te lezen; de tabel onder Bronnen &amp; methode bevat alle waarden.</p>
  </section>}

  <section aria-labelledby="h-cards"><h2 id="h-cards" className="sec-h">Prijsontwikkeling in de gekozen periode</h2><p className="cap">Nominale waarden en procentuele verandering tussen de eerste en laatste maand met gegevens. Dit is geen maat voor betaalbaarheid of koopkracht.</p>{CATEGORIES.map(c=>{const ks=cardKeys.filter(k=>SERIES[k].category===c.id);return ks.length?<div className="card-group" key={c.id}><h3 className="grp-h">{c.label}</h3><p className="cap">{c.caption}</p><div className="cards">{ks.map(k=><Card key={k} k={k} rows={rows}/>)}</div></div>:null})}</section>

  <aside className="warn" role="note"><strong>Let op bij interpretatie.</strong> {WARNING}</aside>

  <details className="sources" open={open} onToggle={e=>setOpen((e.currentTarget as HTMLDetailsElement).open)}>
   <summary>Bronnen &amp; methode</summary>
   <div className="src-body">
    <h3>Woningdata</h3>
    <p><a href="https://opendata.cbs.nl/CBS/nl/dataset/85773NED/table">CBS StatLine 85773NED</a>: gemiddelde verkoopprijs bestaande koopwoningen (EUR) en prijsindex bestaande koopwoningen (2020 = 100). De index met januari 2000 = 100 is een eigen herbasering van dezelfde CBS-index.</p>
    <p>Dekking: {month(first)} t/m {month(last)}, {data.length} maanden. Ontbrekende maanden worden niet aangevuld.</p>
    <p>De CBS-gemiddelde verkoopprijs is gevoelig voor de samenstelling van verkochte woningen. De prijsindex corrigeert voor kwaliteitsverschillen en is geschikter voor prijsontwikkeling.</p>
    {hasGold&&<><h3>Goud</h3>
    <p><a href="https://www.worldbank.org/en/research/commodity-markets">World Bank Commodity Markets (Pink Sheet), GOLD, USD per troy ounce</a>. Valutakoers: <a href="https://data.ecb.europa.eu/data/datasets/EXR/EXR.D.USD.EUR.SP00.A">ECB EXR.D.USD.EUR.SP00.A</a>, USD per EUR. Maandgemiddelden, omrekening, indexering en gram per woning zijn eigen berekeningen; geen bronorganisatie onderschrijft deze toepassing.</p>
    <p>{GOLD_METHOD_TEXT.join(' ')} <a href={METHODOLOGY_URL}>Volledige methodologie</a>. Peildatum bronstand: {asOfText()}.</p>
    <p>{GOLD_BREAK_TEXT}</p></>}
    <h3>Gegevens als tabel</h3>
    <button type="button" className="seg" aria-expanded={table} aria-controls="data-table" onClick={()=>setTable(!table)}>{table?'Verberg tabel':'Toon als tabel'}</button>
    {table&&<div className="table-wrap" tabIndex={0} role="region" aria-label="Maandgegevens (scrollbaar)"><table id="data-table"><caption>Maandelijkse waarden van {month(rows[0].period)} t/m {month(rows[rows.length-1].period)} ({rows.length} {rows.length===1?'maand':'maanden'}, dezelfde periode als de grafiek); leeg betekent geen gegevens.</caption>
     <thead><tr><th scope="col">Maand</th>{shown.map(k=><th scope="col" key={k}>{SERIES[k].label} ({SERIES[k].unit})</th>)}{btcCols&&<th scope="col">{BTC_NOTE_HEADER}</th>}</tr></thead>
     <tbody>{rows.map(p=><tr key={p.period}><th scope="row">{p.period}</th>{shown.map(k=><td key={k}>{ok(p[k])?fmt(SERIES[k].kind,p[k] as number):''}</td>)}{btcCols&&<td data-btc-note>{btcNote(p,btc)}</td>}</tr>)}</tbody></table></div>}
   </div>
  </details>
  </>}
 </main>
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
