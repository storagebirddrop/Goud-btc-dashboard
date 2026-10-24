// The ONLY place that touches the URL hash for the historical view (HIST-12). The hash can select the Historisch TAB, and only after an exact payload has been
// authorized by hash (main.tsx never calls these without a validated payload). It can never select a series, a range or authorize anything.
const HASH='#historisch';
export const histHashRequested=():boolean=>window.location.hash===HASH;
export function setHistHash(on:boolean){window.history.replaceState(null,'',on?HASH:window.location.href.split('#')[0])}
export function onHashChange(fn:()=>void):()=>void{window.addEventListener('hashchange',fn);return()=>window.removeEventListener('hashchange',fn)}
