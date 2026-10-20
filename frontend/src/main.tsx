import React from 'react';
import {createRoot} from 'react-dom/client';
import {LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ReferenceLine, ResponsiveContainer} from 'recharts';
import './style.css';

type SeriesKey='house_eur'|'hpi'|'hpi_index'|'gold_index'|'gold_grams_per_house';
type Point={period:string;gold_eur_oz:number|null;house_eur:number|null;hpi:number|null;gold_grams_per_house:number|null;gold_index:number|null;hpi_index:number|null};
type Kind='eur'|'index'|'gram';
type SeriesDef={label:string;short:string;kind:Kind;unit:string;light:string;dark:string;dash?:string;source:string;gold?:boolean};

// Registry: a series is only offered when the loaded data holds at least one finite value for it.
// New datasets (real EUR, gold, BTC) join by adding an entry here; nothing else has to change.
// Raw gold_eur_oz is deliberately not part of the registry: it is never shown.
const SERIES:Record<SeriesKey,SeriesDef>={
 house_eur:{label:'Gemiddelde verkoopprijs',short:'Verkoopprijs',kind:'eur',unit:'EUR',light:'#2a78d6',dark:'#3987e5',source:'CBS StatLine 85773NED'},
 hpi:{label:'CBS-huizenprijsindex',short:'Prijsindex',kind:'index',unit:'indexpunten, 2020 = 100',light:'#0e8a5f',dark:'#2fbf8c',source:'CBS StatLine 85773NED'},
 hpi_index:{label:'CBS-huizenprijsindex',short:'Prijsindex',kind:'index',unit:'indexpunten, januari 2000 = 100',light:'#0e8a5f',dark:'#2fbf8c',source:'CBS StatLine 85773NED, eigen herbasering'},
 gold_index:{label:'Goudprijsindex',short:'Goudprijs',kind:'index',unit:'indexpunten, januari 2000 = 100',light:'#a87400',dark:'#eda100',dash:'6 3',source:'World Bank / ECB, eigen berekening',gold:true},
 gold_grams_per_house:{label:'Gram goud per woning',short:'Goud per woning',kind:'gram',unit:'gram',light:'#6250d6',dark:'#9085e9',dash:'6 3',source:'World Bank / ECB / CBS, eigen berekening',gold:true}
};
const LEVEL_KEYS:SeriesKey[]=['house_eur','hpi','gold_grams_per_house'];
const CARD_KEYS:SeriesKey[]=['house_eur','hpi','gold_index','gold_grams_per_house'];
const BASES:{id:string;label:string;caption:string;keys:SeriesKey[]}[]=[
 {id:'2000',label:'Januari 2000 = 100',caption:'januari 2000 = 100',keys:['hpi_index','gold_index']},
 {id:'2020',label:'2020 = 100 (CBS)',caption:'2020 = 100 (CBS-basis)',keys:['hpi']}
];
const PRESETS=[{id:'all',label:'Alles'},{id:'2008',label:'Sinds 2008'},{id:'10y',label:'Laatste 10 jaar'}] as const;
type Preset=typeof PRESETS[number]['id'];
const WARNING='De reeks toont de prijs van een gemiddeld verkochte bestaande koopwoning uitgedrukt in de gekozen rekeneenheid. De mix van verkochte woningen kan veranderen; de reeks meet geen constante woningkwaliteit of algemene betaalbaarheid. Dit is geen beleggingsadvies.';
const MIX_HINT='De verandering van de gemiddelde verkoopprijs weerspiegelt niet alleen prijsontwikkeling. Ze hangt ook af van welke woningen in de begin- en eindmaand zijn verkocht (transactiemix) en van uitschieters in een afzonderlijke maand. De CBS-huizenprijsindex corrigeert voor kwaliteitsverschillen en is daarvoor de betere maatstaf.';

const nf0=new Intl.NumberFormat('nl-NL',{maximumFractionDigits:0});
const nf1=new Intl.NumberFormat('nl-NL',{minimumFractionDigits:1,maximumFractionDigits:1});
const euro=new Intl.NumberFormat('nl-NL',{style:'currency',currency:'EUR',maximumFractionDigits:0});
const pct=new Intl.NumberFormat('nl-NL',{style:'percent',minimumFractionDigits:1,maximumFractionDigits:1,signDisplay:'exceptZero'});
function fmt(kind:Kind,v:number){return kind==='eur'?euro.format(v):kind==='gram'?`${nf0.format(v)} g`:nf1.format(v)}
function month(p:string){const [y,m]=p.split('-').map(Number);return new Date(Date.UTC(y,m-1,1)).toLocaleDateString('nl-NL',{month:'long',year:'numeric',timeZone:'UTC'})}
const ok=(v:number|null|undefined):v is number=>typeof v==='number'&&Number.isFinite(v);
function useDark(){
 const q='(prefers-color-scheme: dark)';
 const [d,setD]=React.useState(()=>window.matchMedia?.(q).matches??false);
 React.useEffect(()=>{const m=window.matchMedia?.(q);if(!m)return;const h=(e:MediaQueryListEvent)=>setD(e.matches);m.addEventListener('change',h);return()=>m.removeEventListener('change',h)},[]);
 return d;
}
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
  <h3><span id={`c-${k}`}>{s.label}</span>{k==='house_eur'&&<InfoHint id="hint-card"/>}</h3>
  <p className="big">{fmt(s.kind,b)}</p>
  <p className="sub">{month(last.period)} · {s.kind==='eur'?'EUR, nominaal':s.unit}</p>
  <dl>
   <div><dt>Begin periode, {month(first.period)}</dt><dd>{fmt(s.kind,a)}</dd></div>
   <div><dt>Verandering sinds begin periode</dt><dd className="delta">{ch===null?'n.v.t.':pct.format(ch)}</dd></div>
  </dl>
  <p className="status">Bron: {s.source}. {vals.length} {vals.length===1?'maand':'maanden'} met gegevens.</p>
 </article>
}

type TipProps={active?:boolean;payload?:{dataKey:string;value:number}[];label?:string};
function Tip({active,payload,label}:TipProps){
 if(!active||!payload?.length||!label)return null;
 return <div className="tip"><strong>{month(label)}</strong>{payload.filter(p=>ok(p.value)).map(p=>{const s=SERIES[p.dataKey as SeriesKey];return <div key={p.dataKey}>{s.short}: <b>{fmt(s.kind,p.value)}</b>{s.kind==='index'&&<small> ({s.unit})</small>}</div>})}</div>
}

function isoDot(rows:Point[],k:SeriesKey,color:string){
 // Isolated finite values (no finite neighbour) would be invisible as a line; show them as a dot.
 return (p:{cx?:number;cy?:number;index?:number})=>{const i=p.index??-1;const iso=i>=0&&ok(rows[i]?.[k])&&!ok(rows[i-1]?.[k])&&!ok(rows[i+1]?.[k]);
  return iso&&p.cx!==undefined&&p.cy!==undefined?<circle key={`d-${k}-${i}`} cx={p.cx} cy={p.cy} r={4} fill={color}/>:<g key={`d-${k}-${i}`}/>}
}
function Chart({rows,keys,dark,ariaLabel,yLabel,baseLine,annotate}:{rows:Point[];keys:SeriesKey[];dark:boolean;ariaLabel:string;yLabel:string;baseLine?:boolean;annotate?:boolean}){
 const kind=SERIES[keys[0]].kind;
 const years=rows.length/12;const step=years<=6?1:years<=12?2:years<=20?4:5;
 const ticks=rows.map(r=>r.period).filter(p=>p.endsWith('-01')&&Number(p.slice(0,4))%step===0);
 const grid=dark?'#3a3a38':'#e4e3df',axis=dark?'#c3c2b7':'#52514e';
 const goldKeys=keys.filter(k=>SERIES[k].gold);
 const hasJune=!!annotate&&goldKeys.some(k=>rows.some(r=>r.period<'2025-06'&&ok(r[k]))&&rows.some(r=>r.period>='2025-06'&&ok(r[k])))&&rows.some(r=>r.period==='2025-06');
 return <figure className="chart" role="img" aria-label={ariaLabel}>
  <ResponsiveContainer width="100%" height={340}>
   <LineChart data={rows} margin={{top:8,right:16,bottom:4,left:4}}>
    <CartesianGrid stroke={grid} vertical={false}/>
    <XAxis dataKey="period" ticks={ticks} interval={0} tickFormatter={(p:string)=>p.slice(0,4)} tick={{fill:axis,fontSize:12}} stroke={grid} tickMargin={6}/>
    <YAxis width={kind==='eur'?78:48} domain={['auto','auto']} tickFormatter={(v:number)=>kind==='eur'?euro.format(v):nf0.format(v)} tick={{fill:axis,fontSize:12}} stroke={grid}/>
    <Tooltip content={<Tip/>} cursor={{stroke:axis,strokeDasharray:'3 3'}}/>
    {keys.length>1&&<Legend verticalAlign="top" height={30} formatter={(_v,e)=>{const k=(e as {dataKey?:string}).dataKey as SeriesKey;return <span style={{color:axis}}>{SERIES[k].short}</span>}}/>}
    {baseLine&&<ReferenceLine y={100} stroke={axis} strokeDasharray="2 4" label={{value:'basis = 100',position:'insideBottomRight',fill:axis,fontSize:11}}/>}
    {hasJune&&<ReferenceLine x="2025-06" stroke={axis} strokeDasharray="4 3" label={{value:'jun 2025: bronwijziging goud',position:'insideTopLeft',fill:axis,fontSize:11}}/>}
    {keys.map(k=><Line key={k} type="monotone" dataKey={k} name={SERIES[k].label} dot={isoDot(rows,k,colorOf(k,dark))} stroke={colorOf(k,dark)} strokeWidth={2} strokeDasharray={SERIES[k].dash} connectNulls={false} isAnimationActive={false} activeDot={{r:5,stroke:dark?'#1a1a19':'#fcfcfb',strokeWidth:2}}/>)}
   </LineChart>
  </ResponsiveContainer>
  <figcaption className="ycap">Verticale as: {yLabel}</figcaption>
 </figure>
}

function summary(rows:Point[],keys:SeriesKey[]){
 return keys.map(k=>{const v=rows.filter(p=>ok(p[k]));if(!v.length)return '';const s=SERIES[k];return `${s.label}: van ${fmt(s.kind,v[0][k] as number)} in ${month(v[0].period)} naar ${fmt(s.kind,v[v.length-1][k] as number)} in ${month(v[v.length-1].period)}.`}).join(' ')
}

function App(){
 const [data,setData]=React.useState<Point[]>([]);
 const [error,setError]=React.useState('');
 const [loading,setLoading]=React.useState(true);
 const [preset,setPreset]=React.useState<Preset>('all');
 const [level,setLevel]=React.useState<SeriesKey>('house_eur');
 const [baseId,setBaseId]=React.useState('2000');
 const [open,setOpen]=React.useState(false);
 const [table,setTable]=React.useState(false);
 const dark=useDark();
 React.useEffect(()=>{fetch('/data/monthly.json').then(r=>{if(!r.ok)throw Error(`HTTP ${r.status}`);return r.json()}).then((j:{data:Point[]})=>{if(!Array.isArray(j.data))throw Error('Ongeldig dataformaat');setData(j.data)}).catch(e=>setError(String(e))).finally(()=>setLoading(false))},[]);

 const avail=React.useMemo(()=>{const a=new Set<SeriesKey>();(Object.keys(SERIES) as SeriesKey[]).forEach(k=>{if(data.some(p=>ok(p[k])))a.add(k)});return a},[data]);
 const levelKeys=LEVEL_KEYS.filter(k=>avail.has(k));
 const bases=BASES.map(b=>({...b,keys:b.keys.filter(k=>avail.has(k))})).filter(b=>b.keys.length);
 const curLevel=levelKeys.includes(level)?level:levelKeys[0];
 const curBase=bases.find(b=>b.id===baseId)??bases[0];
 const start=(()=>{if(preset==='2008'){const i=data.findIndex(p=>p.period>='2008-01');return i<0?0:i}if(preset==='10y')return Math.max(0,data.length-120);return 0})();
 const rows=data.slice(start);
 const cardKeys=CARD_KEYS.filter(k=>avail.has(k)&&rows.some(p=>ok(p[k])));
 const hasGold=[...avail].some(k=>SERIES[k].gold);
 const missing=['reële EUR',...(hasGold?[]:['goud']),'Bitcoin'].join(', ').replace(/, ([^,]*)$/,' en $1');
 const shown=(Object.keys(SERIES) as SeriesKey[]).filter(k=>avail.has(k));
 const first=data[0]?.period,last=data[data.length-1]?.period;

 return <main>
  <header>
   <h1>Nederlandse huizenprijzen</h1>
   {data.length>0&&<p className="lede">Maandelijkse CBS-reeksen, {month(first)} t/m {month(last)}: gemiddelde verkoopprijs in euro en prijsindex.</p>}
   {!error&&!loading&&<p className="muted">Nog niet beschikbaar: {missing}.</p>}
  </header>
  {error?<p role="alert" className="notice">Dashboardgegevens niet beschikbaar: {error}</p>:loading?<p role="status">Gegevens laden…</p>:data.length===0||avail.size===0?<p className="notice">Nog geen gevalideerde brongegevens geladen.</p>:<>
  <div className="toolbar" role="group" aria-label="Periode">
   <span className="tl">Periode</span>
   <span className="segs">{PRESETS.map(p=><button key={p.id} type="button" className="seg" aria-pressed={preset===p.id} onClick={()=>setPreset(p.id)}>{p.label}</button>)}</span>
   <span className="muted">{month(rows[0].period)} t/m {month(rows[rows.length-1].period)} ({rows.length} maanden)</span>
  </div>

  <section aria-labelledby="h-cards"><h2 id="h-cards" className="sec-h">Prijsontwikkeling in de gekozen periode</h2><p className="cap">Nominale waarden en procentuele verandering tussen de eerste en laatste maand met gegevens. Dit is geen maat voor betaalbaarheid of koopkracht.</p><div className="cards">{cardKeys.map(k=><Card key={k} k={k} rows={rows}/>)}</div></section>

  <aside className="warn" role="note"><strong>Let op bij interpretatie.</strong> {WARNING}</aside>

  {curLevel&&<section className="panel" aria-labelledby="h-level">
   <div className="panel-head"><h2 id="h-level">Niveau in eigen eenheid</h2>
    {levelKeys.length>1&&<div className="segs" role="group" aria-label="Kies een reeks">{levelKeys.map(k=><button key={k} type="button" className="seg" aria-pressed={curLevel===k} onClick={()=>setLevel(k)}>{SERIES[k].short}</button>)}</div>}</div>
   <p className="cap">{SERIES[curLevel].label}, {SERIES[curLevel].unit}{curLevel==='house_eur'&&<InfoHint id="hint-chart"/>}</p>
   <Chart rows={rows} keys={[curLevel]} dark={dark} yLabel={SERIES[curLevel].unit} ariaLabel={`Lijngrafiek. ${summary(rows,[curLevel])}`}/>
  </section>}

  {curBase&&<section className="panel" aria-labelledby="h-idx">
   <div className="panel-head"><h2 id="h-idx">Relatieve verandering (index)</h2>
    {bases.length>1&&<div className="segs" role="group" aria-label="Indexbasis">{bases.map(b=><button key={b.id} type="button" className="seg" aria-pressed={curBase.id===b.id} onClick={()=>setBaseId(b.id)}>{b.label}</button>)}</div>}</div>
   <p className="cap">Relatieve verandering, indexbasis {curBase.caption}. Dit is geen prijs in euro.</p>
   <Chart rows={rows} keys={curBase.keys} dark={dark} yLabel={`index, ${curBase.caption}`} baseLine annotate ariaLabel={`Lijngrafiek, indexbasis ${curBase.caption}. ${summary(rows,curBase.keys)}`}/>
  </section>}

  <details className="sources" open={open} onToggle={e=>setOpen((e.currentTarget as HTMLDetailsElement).open)}>
   <summary>Bronnen &amp; methode</summary>
   <div className="src-body">
    <h3>Woningdata</h3>
    <p><a href="https://opendata.cbs.nl/CBS/nl/dataset/85773NED/table">CBS StatLine 85773NED</a>: gemiddelde verkoopprijs bestaande koopwoningen (EUR) en prijsindex bestaande koopwoningen (2020 = 100). De index met januari 2000 = 100 is een eigen herbasering van dezelfde CBS-index.</p>
    <p>Dekking: {month(first)} t/m {month(last)}, {data.length} maanden. Ontbrekende maanden worden niet aangevuld.</p>
    <p>De CBS-gemiddelde verkoopprijs is gevoelig voor de samenstelling van verkochte woningen. De prijsindex corrigeert voor kwaliteitsverschillen en is geschikter voor prijsontwikkeling.</p>
    {hasGold&&<><h3>Goud</h3>
    <p><a href="https://www.worldbank.org/en/research/commodity-markets">World Bank Commodity Markets (Pink Sheet), GOLD, USD per troy ounce</a>. Valutakoers: <a href="https://data.ecb.europa.eu/data/datasets/EXR/EXR.D.USD.EUR.SP00.A">ECB EXR.D.USD.EUR.SP00.A</a>, USD per EUR. Maandgemiddelden, omrekening, indexering en gram per woning zijn eigen berekeningen; geen bronorganisatie onderschrijft deze toepassing.</p>
    <p><strong>Definitiewijziging juni 2025:</strong> World Bank GOLD gebruikte tot en met mei 2025 London afternoon fixing (99,5% goud); vanaf juni 2025 gemiddelde dagelijkse spotprijzen. De goudreeks is daardoor niet volledig benchmarkhomogeen.</p></>}
    <h3>Gegevens als tabel</h3>
    <button type="button" className="seg" aria-expanded={table} aria-controls="data-table" onClick={()=>setTable(!table)}>{table?'Verberg tabel':'Toon als tabel'}</button>
    {table&&<div className="table-wrap" tabIndex={0} role="region" aria-label="Maandgegevens (scrollbaar)"><table id="data-table"><caption>Maandelijkse waarden; leeg betekent geen gegevens.</caption>
     <thead><tr><th scope="col">Maand</th>{shown.map(k=><th scope="col" key={k}>{SERIES[k].label} ({SERIES[k].unit})</th>)}</tr></thead>
     <tbody>{data.map(p=><tr key={p.period}><th scope="row">{p.period}</th>{shown.map(k=><td key={k}>{ok(p[k])?fmt(SERIES[k].kind,p[k] as number):''}</td>)}</tr>)}</tbody></table></div>}
   </div>
  </details>
  </>}
 </main>
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
