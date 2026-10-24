import React from 'react';
import {LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer} from 'recharts';
import {useDark,useNarrow} from './hooks';
import {HIST_BOUNDARY_TEXT,HIST_CMP_WARNING_TEXT,HIST_FLAG_TEXT,HIST_HEADING_TEXT,HIST_NLG_PER_EUR,HIST_NOTICE_TEXT,HIST_QUALITY_TEXT,HIST_RETRO_TEXT,HIST_SYNTHETIC_MARKER} from './hist';
import type {HistData,HistId} from './hist';

// The "Historisch" view (HIST-12, inert until an exact payload is pinned). Three separate panels with their own axes, units and notices: nothing is joined to the
// current series, no values are filled in and no curve is fitted, a missing value would break the line (there are none: the gate requires every period).
const nf0=new Intl.NumberFormat('nl-NL',{maximumFractionDigits:0});
const nlg=(v:number)=>`ƒ ${nf0.format(v)}`;
const eur=new Intl.NumberFormat('nl-NL',{style:'currency',currency:'EUR',maximumFractionDigits:0});
const half=(p:string)=>`${p.slice(0,4)} ${p.slice(5)}`;
const monthLabel=(p:string)=>{const [y,m]=p.split('-').map(Number);return new Date(Date.UTC(y,m-1,1)).toLocaleDateString('nl-NL',{month:'long',year:'numeric',timeZone:'UTC'})};
const flagsText=(f:string[])=>f.map(x=>HIST_FLAG_TEXT[x]).filter(Boolean).join('; ');
type Row={period:string;a:number;b?:number;qa:string;fa:string[];qb?:string;fb?:string[]};
const num=(d:HistData,id:HistId)=>d.series[id].points;

function Tip({active,payload,label,render}:{active?:boolean;payload?:{payload:Row}[];label?:string;render:(r:Row)=>React.ReactNode}){
 if(!active||!payload?.length||!label)return null;
 return <div className="tip">{render(payload[0].payload)}</div>
}
function HChart({rows,lines,dark,narrow,tick,aria,yLabel,fmtY,render}:{rows:Row[];lines:{key:'a'|'b';name:string;color:string;dash?:string}[];dark:boolean;narrow:boolean;tick:(p:string)=>boolean;aria:string;yLabel:string;fmtY:(v:number)=>string;render:(r:Row)=>React.ReactNode}){
 const grid=dark?'#3a3a38':'#e4e3df',axis=dark?'#c3c2b7':'#52514e';
 const ticks=rows.map(r=>r.period).filter(tick);
 return <figure className="chart" role="img" aria-label={aria}>
  <ResponsiveContainer width="100%" height={narrow?260:320}>
   <LineChart data={rows} accessibilityLayer margin={{top:8,right:16,bottom:4,left:4}}>
    <CartesianGrid stroke={grid} vertical={false}/>
    <XAxis dataKey="period" ticks={ticks} interval={0} tickFormatter={(p:string)=>p.slice(0,4)} tick={{fill:axis,fontSize:12}} stroke={grid} tickMargin={6}/>
    <YAxis width={78} domain={['auto','auto']} tickFormatter={fmtY} tick={{fill:axis,fontSize:12}} stroke={grid}/>
    <Tooltip content={<Tip render={render}/>} cursor={{stroke:axis,strokeDasharray:'3 3'}}/>
    {lines.length>1&&<Legend verticalAlign="top" height={30} formatter={(_v,e)=>{const k=(e as {dataKey?:string}).dataKey;return <span style={{color:axis}}>{lines.find(l=>l.key===k)?.name}</span>}}/>}
    {lines.map(l=><Line key={l.key} type="linear" dataKey={l.key} name={l.name} stroke={l.color} strokeWidth={2} strokeDasharray={l.dash} dot={{r:2.5,fill:l.color}} connectNulls={false} isAnimationActive={false} activeDot={{r:5}}/>)}
   </LineChart>
  </ResponsiveContainer>
  <figcaption className="ycap">Verticale as: {yLabel}</figcaption>
 </figure>
}
function TableToggle({id,label,children}:{id:string;label:string;children:React.ReactNode}){
 const [on,setOn]=React.useState(false);
 return <div><button type="button" className="seg" aria-expanded={on} aria-controls={id} onClick={()=>setOn(!on)}>{on?'Verberg tabel':'Toon als tabel'}</button>
  {on&&<div className="table-wrap" tabIndex={0} role="region" aria-label={label}>{children}</div>}</div>
}

export function HistoricView({data}:{data:HistData}){
 const dark=useDark(),narrow=useNarrow();
 const [unit,setUnit]=React.useState<'nlg'|'eur'>('nlg');
 const col1=dark?'#3987e5':'#2a78d6',col2=dark?'#2fbf8c':'#0e8a5f',col3=dark?'#eda100':'#a87400';
 const nvmN=num(data,'hist_nvm_median_nlg_h'),nvmE=num(data,'hist_nvm_median_eur_retro_h');
 const nvmRows:Row[]=nvmN.map((p,i)=>({period:p.period,a:unit==='nlg'?Number(p.value):Number(nvmE[i].value),qa:p.quality,fa:p.flags}));
 const cbsM=num(data,'hist_cbs_avg_eur_m');
 const cbsRows:Row[]=cbsM.map(p=>({period:p.period,a:Number(p.value),qa:p.quality,fa:p.flags}));
 const cbsH=num(data,'hist_cbs_avg_eur_h');
 const cmpRows:Row[]=data.comparison.authorized?cbsH.map(p=>{const e=nvmE.find(x=>x.period===p.period)!;return {period:p.period,a:Number(e.value),qa:e.quality,fa:e.flags,b:Number(p.value),qb:p.quality,fb:p.flags}}):[];
 const q=(x:string)=>HIST_QUALITY_TEXT[x];
 return <section className="hist" aria-labelledby="h-hist">
  <h2 id="h-hist" className="sec-h">{HIST_HEADING_TEXT}</h2>
  {data.synthetic&&<p role="alert" className="notice">{HIST_SYNTHETIC_MARKER}: dit zijn synthetische testgegevens, geen echte waarnemingen.</p>}
  <aside className="warn" role="note"><strong>Let op bij interpretatie.</strong> {HIST_NOTICE_TEXT}</aside>
  <p className="cap">{HIST_BOUNDARY_TEXT}</p>

  <section className="panel" aria-labelledby="h-nvm">
   <div className="panel-head"><h3 id="h-nvm">NVM, mediane verkoopprijs bestaande koopwoningen (halfjaar)</h3>
    <div className="segs" role="group" aria-label="Eenheid">
     <button type="button" className="seg" aria-pressed={unit==='nlg'} onClick={()=>setUnit('nlg')}>Gulden (origineel)</button>
     <button type="button" className="seg" aria-pressed={unit==='eur'} onClick={()=>setUnit('eur')}>Euro, omgerekend (÷ 2,20371)</button>
    </div></div>
   <p className="cap">Statistiek: <strong>mediaan</strong> van de nominale verkoopprijs, per halfjaar, {half(nvmN[0].period)} t/m {half(nvmN[nvmN.length-1].period)}. Eenheid: <strong>{unit==='nlg'?'gulden (NLG), origineel':'euro, omgerekend uit guldens'}</strong>.</p>
   <p className="cap">{HIST_RETRO_TEXT}</p>
   <HChart rows={nvmRows} lines={[{key:'a',name:'NVM mediaan',color:col1}]} dark={dark} narrow={narrow} tick={p=>p.endsWith('H1')&&Number(p.slice(0,4))%5===0} yLabel={unit==='nlg'?'gulden (NLG)':'euro (omgerekend)'}
    fmtY={v=>unit==='nlg'?nlg(v):eur.format(v)} aria={`Lijngrafiek NVM mediaan per halfjaar in ${unit==='nlg'?'guldens':'euro (omgerekend)'}, ${half(nvmN[0].period)} t/m ${half(nvmN[nvmN.length-1].period)}, ${nvmN.length} halfjaren.`}
    render={r=>{const i=nvmN.findIndex(p=>p.period===r.period);return <><strong>{half(r.period)}</strong><div>Mediaan: <b>{nlg(Number(nvmN[i].value))}</b> (origineel)</div><div>Omgerekend: <b>{eur.format(Number(nvmE[i].value))}</b></div><small>Kwaliteit: {q(r.qa)}{flagsText(r.fa)?` · ${flagsText(r.fa)}`:''}</small></>}}/>
   <p className="status">Bron: {data.provenance.sources.map(s=>`${s.title} (${s.vintage})`).join('; ')}. Kwaliteit per halfjaar: zie tabel.</p>
   <TableToggle id="t-nvm" label="NVM-waarden (scrollbaar)"><table id="t-nvm"><caption>NVM mediaan per halfjaar</caption>
    <thead><tr><th scope="col">Halfjaar</th><th scope="col">Gulden (origineel)</th><th scope="col">Euro (omgerekend ÷ 2,20371)</th><th scope="col">Kwaliteit</th><th scope="col">Toelichting</th></tr></thead>
    <tbody>{nvmN.map((p,i)=><tr key={p.period}><th scope="row">{half(p.period)}</th><td>{nlg(Number(p.value))}</td><td>{eur.format(Number(nvmE[i].value))}</td><td>{q(p.quality)}</td><td>{flagsText(p.flags)}</td></tr>)}</tbody></table></TableToggle>
  </section>

  <section className="panel" aria-labelledby="h-cbs">
   <div className="panel-head"><h3 id="h-cbs">CBS, gemiddelde verkoopprijs bestaande koopwoningen (maand)</h3></div>
   <p className="cap">Statistiek: <strong>gemiddelde</strong> van de nominale verkoopprijs, per maand, {monthLabel(cbsM[0].period)} t/m {monthLabel(cbsM[cbsM.length-1].period)}. Eenheid: <strong>euro, retrospectief</strong>. Deze reeks eindigt in december 1999; de actuele CBS-reeks begint op het tabblad Actueel.</p>
   <p className="cap">{HIST_RETRO_TEXT}</p>
   <HChart rows={cbsRows} lines={[{key:'a',name:'CBS gemiddelde',color:col2}]} dark={dark} narrow={narrow} tick={p=>p.endsWith('-01')&&Number(p.slice(0,4))%1===0} yLabel="euro (retrospectief)" fmtY={v=>eur.format(v)}
    aria={`Lijngrafiek CBS gemiddelde verkoopprijs per maand in euro, ${monthLabel(cbsM[0].period)} t/m ${monthLabel(cbsM[cbsM.length-1].period)}, ${cbsM.length} maanden.`}
    render={r=><><strong>{monthLabel(r.period)}</strong><div>Gemiddelde: <b>{eur.format(r.a)}</b></div><small>Kwaliteit: {q(r.qa)}{flagsText(r.fa)?` · ${flagsText(r.fa)}`:''}</small></>}/>
   <p className="status">Bron: {data.provenance.sources.map(s=>`${s.title} (${s.vintage})`).join('; ')}.</p>
   <TableToggle id="t-cbs" label="CBS-waarden (scrollbaar)"><table id="t-cbs"><caption>CBS gemiddelde per maand</caption>
    <thead><tr><th scope="col">Maand</th><th scope="col">Euro (retrospectief)</th><th scope="col">Kwaliteit</th><th scope="col">Toelichting</th></tr></thead>
    <tbody>{cbsM.map(p=><tr key={p.period}><th scope="row">{p.period}</th><td>{eur.format(Number(p.value))}</td><td>{q(p.quality)}</td><td>{flagsText(p.flags)}</td></tr>)}</tbody></table></TableToggle>
  </section>

  {data.comparison.authorized&&<section className="panel" aria-labelledby="h-cmp">
   <div className="panel-head"><h3 id="h-cmp">Vergelijking NVM (mediaan) en CBS (gemiddelde), halfjaar</h3></div>
   <aside className="warn" role="note">{HIST_CMP_WARNING_TEXT}</aside>
   <p className="cap">Beide reeksen in euro (NVM omgerekend, CBS retrospectief), {half(data.comparison.first)} t/m {half(data.comparison.last)}. Twee afzonderlijke lijnen met een eigen betekenis; er is geen gecombineerde reeks.</p>
   <HChart rows={cmpRows} lines={[{key:'a',name:'NVM mediaan (omgerekend)',color:col1},{key:'b',name:'CBS gemiddelde (retrospectief)',color:col3,dash:'6 3'}]} dark={dark} narrow={narrow} tick={p=>p.endsWith('H1')} yLabel="euro" fmtY={v=>eur.format(v)}
    aria={`Lijngrafiek met twee afzonderlijke reeksen per halfjaar: NVM mediaan en CBS gemiddelde, ${half(data.comparison.first)} t/m ${half(data.comparison.last)}.`}
    render={r=><><strong>{half(r.period)}</strong><div>NVM mediaan: <b>{eur.format(r.a)}</b></div><div>CBS gemiddelde: <b>{eur.format(r.b as number)}</b></div><small>Statistieken verschillen; niet onderling vervangbaar.</small></>}/>
   <TableToggle id="t-cmp" label="Vergelijkingswaarden (scrollbaar)"><table id="t-cmp"><caption>NVM mediaan en CBS gemiddelde per halfjaar</caption>
    <thead><tr><th scope="col">Halfjaar</th><th scope="col">NVM mediaan (€, omgerekend)</th><th scope="col">CBS gemiddelde (€, retrospectief)</th></tr></thead>
    <tbody>{cmpRows.map(r=><tr key={r.period}><th scope="row">{half(r.period)}</th><td>{eur.format(r.a)}</td><td>{eur.format(r.b as number)}</td></tr>)}</tbody></table></TableToggle>
  </section>}

  <details className="sources"><summary>Bronnen &amp; kwaliteit van de historische reeksen</summary>
   <div className="src-body">
    <ul>{data.provenance.sources.map(s=><li key={s.id}>{s.title}, bronstand {s.vintage}; rechtenstatus: {s.rights_status}</li>)}</ul>
    <p>Kwaliteitsaanduidingen: {Object.entries(HIST_QUALITY_TEXT).map(([k,v])=>`${v} (${k})`).join(', ')}. Markeringen: {Object.values(HIST_FLAG_TEXT).filter(t=>!t.startsWith('SYNTHETISCHE')).join('; ')}.</p>
    <p>Omrekenfactor: {HIST_NLG_PER_EUR.toString().replace('.',',')} gulden per euro; alleen een omrekening van de denominatie, geen inflatiecorrectie.</p>
   </div>
  </details>
 </section>
}
