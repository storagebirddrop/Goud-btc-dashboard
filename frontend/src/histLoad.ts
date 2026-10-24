import {activateHist,HIST_APPROVED_PAYLOAD_SHA256} from './hist';
import type {HistData} from './hist';

// The ONLY request for the historical payload (HIST-12). With an empty pin list (the shipped state) NOTHING is requested. Every failure is silent: no message,
// no state, no detail about the payload reaches the interface.
async function sha256Hex(buf:ArrayBuffer):Promise<string|null>{
 try{const d=await crypto.subtle.digest('SHA-256',buf);return [...new Uint8Array(d)].map(b=>b.toString(16).padStart(2,'0')).join('')}catch{return null}
}
export async function loadHist(pins:readonly string[]=HIST_APPROVED_PAYLOAD_SHA256):Promise<HistData|null>{
 if(pins.length===0)return null;
 try{
  const r=await fetch('/data/historical.json',{cache:'no-store'});
  if(!r.ok)return null;
  const buf=await r.arrayBuffer();
  return activateHist(await sha256Hex(buf),JSON.parse(new TextDecoder().decode(buf)),pins);
 }catch{return null}
}
