import React from 'react';
import {createRoot} from 'react-dom/client';
import {LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer} from 'recharts';
import './style.css';

type Point={period:string;gold_eur_oz:number|null;house_eur:number|null;hpi:number|null;gold_grams_per_house:number|null;gold_index:number|null;hpi_index:number|null};
type Metric='hpi'|'house_eur'|'gold_index'|'gold_grams_per_house';
const metrics:Record<Metric,{label:string;unit:string;color:string}>={
 hpi:{label:'CBS huizenprijsindex',unit:'indexpunten',color:'#2563eb'},
 house_eur:{label:'Gemiddelde verkoopprijs',unit:'EUR',color:'#0f766e'},
 gold_index:{label:'Goudprijsindex',unit:'indexpunten',color:'#b8860b'},
 gold_grams_per_house:{label:'Goud per woning',unit:'gram',color:'#9333ea'}
};
const euro=new Intl.NumberFormat('nl-NL',{style:'currency',currency:'EUR',maximumFractionDigits:0});
const decimal=new Intl.NumberFormat('nl-NL',{maximumFractionDigits:2});
function App(){
 const [data,setData]=React.useState<Point[]>([]);
 const [error,setError]=React.useState('');
 const [loading,setLoading]=React.useState(true);
 const [metric,setMetric]=React.useState<Metric>('hpi');
 React.useEffect(()=>{fetch('/data/monthly.json').then(r=>{if(!r.ok)throw Error(`HTTP ${r.status}`);return r.json()}).then((j:{data:Point[]})=>{if(!Array.isArray(j.data))throw Error('Ongeldig API-formaat');setData(j.data)}).catch(e=>setError(String(e))).finally(()=>setLoading(false))},[]);
 const valid=data.filter(p=>p[metric]!==null&&Number.isFinite(p[metric]));
 const first=valid[0]?.period, last=valid[valid.length-1]?.period;
 return <main><h1>Goud versus Nederlandse huizenprijzen</h1><p>Maandelijkse historische vergelijking vanaf 2000 · EUR</p>
 {error?<p role="alert">Dashboardgegevens niet beschikbaar: {error}</p>:loading?<p>Gegevens laden…</p>:data.length===0?<p>Nog geen gevalideerde brongegevens geladen.</p>:<>
 <h2>Historische reeksen</h2>
 <label htmlFor="metric">Kies een reeks: </label> <select id="metric" value={metric} onChange={e=>setMetric(e.target.value as Metric)}>{(Object.keys(metrics) as Metric[]).map(k=><option key={k} value={k}>{metrics[k].label}</option>)}</select>
 {valid.length===0?<p>Voor deze reeks zijn nog geen gegevens beschikbaar.</p>:<>
 <p>{valid.length} maanden met gegevens · {first} t/m {last}</p>
 <ResponsiveContainer width="100%" height={360}><LineChart data={data}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="period" minTickGap={35}/><YAxis tickFormatter={v=>metric==='house_eur'?euro.format(Number(v)):decimal.format(Number(v))}/><Tooltip formatter={v=>[metric==='house_eur'?euro.format(Number(v)):decimal.format(Number(v)),metrics[metric].unit]}/><Legend/><Line type="monotone" dataKey={metric} name={metrics[metric].label} dot={false} stroke={metrics[metric].color} connectNulls={false}/></LineChart></ResponsiveContainer>
 </>}
 <p>De CBS-gemiddelde verkoopprijs is gevoelig voor de samenstelling van verkochte woningen. De CBS-huizenprijsindex corrigeert voor kwaliteitsverschillen en is geschikter voor prijsontwikkeling. Goudgerelateerde reeksen verschijnen pas zodra gevalideerde gouddata zijn geïmporteerd.</p>
 </>}
 </main>
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
