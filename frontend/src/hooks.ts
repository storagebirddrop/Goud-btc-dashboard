import React from 'react';

export function useDark(){
 const q='(prefers-color-scheme: dark)';
 const [d,setD]=React.useState(()=>window.matchMedia?.(q).matches??false);
 React.useEffect(()=>{const m=window.matchMedia?.(q);if(!m)return;const h=(e:MediaQueryListEvent)=>setD(e.matches);m.addEventListener('change',h);return()=>m.removeEventListener('change',h)},[]);
 return d;
}
export function useNarrow(){
 const q='(max-width: 560px)';
 const [n,setN]=React.useState(()=>window.matchMedia?.(q).matches??false);
 React.useEffect(()=>{const m=window.matchMedia?.(q);if(!m)return;const h=(e:MediaQueryListEvent)=>setN(e.matches);m.addEventListener('change',h);return()=>m.removeEventListener('change',h)},[]);
 return n;
}
