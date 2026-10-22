#!/usr/bin/env python3
"""HIST-09 research-only reproducible CBS/NVM overlap extraction and validation."""
import csv, io, json, hashlib, zipfile, pathlib, argparse, statistics
from decimal import Decimal, getcontext
from collections import defaultdict
getcontext().prec=34
P=pathlib.Path
D=Decimal
MEASURES={'M001532_2':'transactions','M001534':'average_eur','M001535':'total_value_million_eur'}
EXPECTED_P136={(1995,2):227800,(1996,1):240900,(1996,2):250500,(1997,1):265100,(1997,2):271600,(1998,1):283400,(1998,2):301000,(1999,1):328000,(1999,2):352200,(2000,1):381700,(2000,2):394100}
def sha(b):return hashlib.sha256(b).hexdigest()
def writecsv(path,columns,rows):
 with path.open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=columns,lineterminator='\n');w.writeheader();w.writerows(rows)
def main(a):
 out=P(a.out);out.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(a.cbszip) as z:
  obs=list(csv.DictReader(io.StringIO(z.read('Observations.csv').decode('utf-8-sig')),delimiter=';'))
  measures=list(csv.DictReader(io.StringIO(z.read('MeasureCodes.csv').decode('utf-8-sig')),delimiter=';'))
  props=list(csv.DictReader(io.StringIO(z.read('Properties.csv').decode('utf-8-sig')),delimiter=';'))
 titles={r['Identifier']:r['Title'] for r in measures}
 assert titles['M001534']=='Gemiddelde verkoopprijs' and titles['M001532_2']=='Verkochte woningen'
 monthly,other=defaultdict(dict),defaultdict(dict)
 for r in obs:
  period=r['Perioden']; measure=r['Measure']
  if not ('1995'<=period[:4]<='2000') or measure not in MEASURES:continue
  if not r['Value']:raise ValueError(f'Missing official value {period} {measure}')
  v=D(r['Value'].replace('.','').replace(',','.'))
  target=monthly if 'MM' in period else other
  if measure in target[period]:raise ValueError(f'Duplicate {period}/{measure}')
  target[period][measure]=v
 expected={f'{y}MM{m:02d}' for y in range(1995,2001) for m in range(1,13)}
 assert set(monthly)==expected,(len(monthly),expected-set(monthly))
 for p,row in monthly.items():
  assert len(row)==3 and row['M001532_2']>0 and row['M001534']>0 and row['M001535']>0,p
 nvmrows=list(csv.DictReader(P(a.nvm).open(encoding='utf-8-sig',newline='')))
 assert len(nvmrows)==52
 nvm={}
 for r in nvmrows:
  key=(int(r['year']),int(r['halfyear']))
  assert key not in nvm
  nvm[key]=D(r['nvm_median_nlg'])
 assert len(nvm)==52
 assert all(nvm[k]==v for k,v in EXPECTED_P136.items()),'visual p136 values mismatch'
 months=[]
 for p in sorted(monthly):
  r=monthly[p]
  months.append({'period':p,'average_sale_price_eur':str(r['M001534']),'sold_homes':str(int(r['M001532_2'])),'total_value_million_eur':str(r['M001535'])})
 writecsv(out/'HIST09_CBS_1995_2000_MONTHLY.csv',list(months[0]),months)
 overlap=[];resids=[];vs_quarter=[]
 for year in range(1995,2001):
  for half in [1,2]:
   periods=[f'{year}MM{m:02d}' for m in range(1 if half==1 else 7,7 if half==1 else 13)]
   rows=[monthly[p] for p in periods]
   cnt=sum((x['M001532_2'] for x in rows),D(0))
   sumweighted=sum((x['M001534']*x['M001532_2'] for x in rows),D(0))
   mean=sumweighted/cnt
   # Independent quarter aggregation check against CBS quarterly release
   qids=[f'{year}KW{q:02d}' for q in ([1,2] if half==1 else [3,4])]
   qrows=[other[q] for q in qids]
   qc=sum((q['M001532_2'] for q in qrows),D(0))
   assert cnt==qc, (year,half,'transaction-count mismatch',cnt,qc)
   quarter_mean=sum((q['M001534']*q['M001532_2'] for q in qrows),D(0))/qc
   qdiff=mean-quarter_mean
   vs_quarter.append(abs(qdiff))
   med=nvm[(year,half)]/D('2.20371')
   level=med-mean
   pct=(med/mean-D(1))*D(100)
   overlap.append({'period':f'{year}-H{half}','nvm_median_nlg':str(nvm[(year,half)]),'nvm_median_eur':f'{med:.6f}','cbs_mean_eur_weighted':f'{mean:.6f}','cbs_sold_homes':str(int(cnt)),'nvm_minus_cbs_eur':f'{level:.6f}','nvm_vs_cbs_pct':f'{pct:.6f}','cbs_monthly_vs_quarter_aggregation_eur':f'{qdiff:.6f}'})
 assert len(overlap)==12
 for i,row in enumerate(overlap):
  for lag,name in [(1,'sequential'),(2,'year_over_year')]:
   for k,field in [('nvm_median_eur','nvm'),('cbs_mean_eur_weighted','cbs')]:
    row[f'{name}_{field}_growth_pct']=f'{(D(row[k])/D(overlap[i-lag][k])-1)*100:.6f}' if i>=lag else ''
 writecsv(out/'HIST09_NVM_CBS_OVERLAP_1995_2000.csv',list(overlap[0]),overlap)
 pp=[D(x['nvm_vs_cbs_pct']) for x in overlap]
 summary={'nvm_total_observations':52,'nvm_p136_visual_matches':11,'cbs_monthly_observations':len(months),'cbs_halfyears':len(overlap),'nvm_vs_cbs_pct_min':str(min(pp)),'nvm_vs_cbs_pct_max':str(max(pp)),'nvm_vs_cbs_pct_mean':str(sum(pp)/12),'nvm_vs_cbs_pct_median':str(statistics.median(pp)),'max_abs_monthly_vs_quarter_aggregate_eur':str(max(vs_quarter)),'cbs_csv_zip_sha256':sha(P(a.cbszip).read_bytes()),'nvm_csv_sha256':sha(P(a.nvm).read_bytes()),'source_dataset':'CBS StatLine 85773NED','source_export_file':P(a.cbszip).name,'note':'NVM nominal MEDIAN of broker-related trades vs CBS transaction-weighted MEAN of registered sales; NOT comparable as same estimand; research only'}
 (out/'HIST09_VALIDATION_RESULTS.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 manifest={p.name:sha(p.read_bytes()) for p in sorted(out.iterdir()) if p.is_file()}
 (out/'SHA256_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
 print(json.dumps(summary,indent=2));print('PERIOD NVM_EUR CBS_EUR DIFF_% TRANSACTIONS')
 for x in overlap:print(x['period'],x['nvm_median_eur'],x['cbs_mean_eur_weighted'],x['nvm_vs_cbs_pct'],x['cbs_sold_homes'])
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--cbszip',default='/mnt/data/85773NED-202609220630.zip');ap.add_argument('--nvm',default='/mnt/data/otb_nvm_halfjaarlijks_1975_2000_RESEARCH.csv');ap.add_argument('--out',default='/mnt/data/HIST09_FINAL_VALIDATION');main(ap.parse_args())
