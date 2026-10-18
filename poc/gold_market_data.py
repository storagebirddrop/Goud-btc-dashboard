"""Isolated gold PoC. Input: CSV daily gold date,price (USD/oz); FX date,usd_per_eur; CBS date,series,value. No fetch, no publication."""
import csv, json, hashlib, argparse
from pathlib import Path
from datetime import date
from decimal import Decimal
from collections import defaultdict
from etl.asset_quality import positive_decimal, TROY_OUNCE_GRAMS, house_in_gold_grams

def load(path, columns, value):
    raw=Path(path).read_bytes()
    rows=list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
    if not rows or set(rows[0]) != set(columns): raise ValueError("Invalid CSV schema")
    data={}
    for r in rows:
        d=date.fromisoformat(r["date"])
        if d.isoformat()!=r["date"] or d in data: raise ValueError("Duplicate/noncanonical date")
        data[d]=positive_decimal(r[value],value)
    return data,hashlib.sha256(raw).hexdigest()

def housing(path):
    raw=Path(path).read_bytes()
    rows=list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
    if not rows or set(rows[0])!={"date","series","value"}: raise ValueError("Invalid housing CSV")
    result={}
    for r in rows:
        if r["series"]!="nl_house_avg_eur": continue
        month=r["date"][:7]
        if month in result: raise ValueError("Duplicate housing month")
        result[month]=positive_decimal(r["value"],"house_eur")
    return result,hashlib.sha256(raw).hexdigest()

def calculate(gold,fx,homes,base="2000-01",end="2026-08"):
    grouped=defaultdict(list);missing_fx=[]
    for day,usd in sorted(gold.items()):
        month=day.strftime("%Y-%m")
        if not ("2000-01"<=month<=end):continue
        if day not in fx:missing_fx.append(day.isoformat());continue
        grouped[month].append(usd/fx[day])
    means={month:sum(values)/len(values) for month,values in grouped.items()}
    basis=means.get(base)
    year,month=2000,1;out=[]
    while f"{year:04d}-{month:02d}"<=end:
        key=f"{year:04d}-{month:02d}";price=means.get(key);home=homes.get(key)
        out.append({"period":key,"gold_eur_oz":str(price) if price else None,
          "gold_eur_gram":str(price/TROY_OUNCE_GRAMS) if price else None,
          "house_eur":str(home) if home else None,
          "gold_grams_per_house":str(house_in_gold_grams(home,price)) if home and price else None,
          "gold_index":str(100*price/basis) if price and basis else None,
          "observed_fx_matched_days":len(grouped[key]),
          "expected_benchmark_days":None,
          "quality":"PROVISIONAL_OBSERVED" if price else "MISSING"})
        month+=1
        if month==13:year+=1;month=1
    return {"status":"AUDIT_ONLY","publication_authorized":False,"base_month":base,
      "methodology":"PROVISIONAL: arithmetic mean of same-day FX-matched daily gold observations; no fill; benchmark calendar unverified",
      "missing_fx_dates":missing_fx,"months":out}

def main():
    p=argparse.ArgumentParser()
    for key in ("gold","fx","housing","out"):p.add_argument("--"+key,required=True)
    p.add_argument("--end",default="2026-08");a=p.parse_args()
    gold,gh=load(a.gold,("date","price"),"price")
    fx,fh=load(a.fx,("date","usd_per_eur"),"usd_per_eur")
    homes,hh=housing(a.housing)
    result=calculate(gold,fx,homes,end=a.end)
    result["input_sha256"]={"gold":gh,"fx":fh,"housing":hh}
    Path(a.out).write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print("priced_months",sum(x["gold_eur_oz"] is not None for x in result["months"]))
if __name__=="__main__":main()
