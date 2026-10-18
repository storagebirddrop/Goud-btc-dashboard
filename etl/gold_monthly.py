"""Isolated monthly gold/FX/CBS calculation; read-only source downloads; metadata-only logs."""
import csv,hashlib,io,json,urllib.request
from collections import defaultdict
from decimal import Decimal, getcontext
from pathlib import Path
from datetime import date
from etl.sources.worldbank_gold import URL,parse_xlsx
getcontext().prec=28
ECB="https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?startPeriod=2000-01-01&format=csvdata"
GRAMS=Decimal("31.1034768")
def acquire(url):
    with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"GoldDashboard-PoC/1.0","Accept":"text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*"}),timeout=55) as response:
        raw=response.read(15000001)
        if len(raw)>15000000:raise ValueError("Oversize response")
        print("ACQUIRED",json.dumps({"url":url,"http":response.status,"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest(),"content_type":response.headers.get("Content-Type")}))
        return raw
def parse_ecb(raw):
    reader=csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    if not reader.fieldnames or not {"TIME_PERIOD","OBS_VALUE"}.issubset(reader.fieldnames):raise ValueError("ECB CSV schema mismatch: "+str(reader.fieldnames))
    daily={};group=defaultdict(list);invalid=0
    for row in reader:
        if row.get("CURRENCY") not in (None,"USD") or row.get("CURRENCY_DENOM") not in (None,"EUR"):raise ValueError("Unexpected ECB FX direction")
        dt=row.get("TIME_PERIOD","");value=row.get("OBS_VALUE","")
        if not value:continue
        try:
            day=date.fromisoformat(dt);rate=Decimal(value)
            if not rate.is_finite() or rate<=0:raise ValueError("invalid rate")
            if dt in daily:raise ValueError("duplicate ECB day "+dt)
            daily[dt]=rate;group[dt[:7]].append(rate)
        except Exception as exc:
            invalid+=1
            if invalid<4:print("INVALID_ECB",dt,str(exc))
    if invalid:raise ValueError("Invalid ECB rows: "+str(invalid))
    return {month:sum(vals)/len(vals) for month,vals in group.items()},{month:len(vals) for month,vals in group.items()},len(daily)
def parse_housing(raw):
    reader=csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    if set(reader.fieldnames or [])!={"date","series","value"}:raise ValueError("CBS schema")
    houses={}
    for row in reader:
        if row["series"]!="nl_house_avg_eur":continue
        month=row["date"][:7]
        if month in houses:raise ValueError("Duplicate CBS month")
        value=Decimal(row["value"])
        if not value.is_finite() or value<=0:raise ValueError("Invalid CBS house")
        houses[month]=value
    return houses
def expected_months(first,last):
    y,m=map(int,first.split("-"));end=tuple(map(int,last.split("-")))
    result=[]
    while (y,m)<=end:
        result.append(f"{y:04d}-{m:02d}")
        m+=1
        if m==13:y,m=y+1,1
    return result
def classify_coverage(gold,fx,homes):
    """Separate historic gaps from trailing source-publication lag, preserving all months."""
    sources={"worldbank":gold,"ecb":fx,"cbs":homes}
    if not all(sources.values()):raise ValueError("Empty source")
    latest={name:max(rows) for name,rows in sources.items()}
    months=expected_months("2000-01",max(latest.values()))
    records=[]
    for month in months:
        missing=[name for name,rows in sources.items() if month not in rows]
        historic=[name for name in missing if month<=latest[name]]
        pending=[name for name in missing if month>latest[name]]
        records.append({"month":month,"status":"complete" if not missing else "missing_historical" if historic else "pending_publication","missing_historical":historic,"pending_publication":pending})
    return records
def compute(gold,fx,homes,counts):
    if "2000-01" not in gold or "2000-01" not in fx or "2000-01" not in homes:
        raise ValueError("Incomplete 2000-01 index basis")
    if any(not v.is_finite() or v<=0 for source in (gold,fx,homes) for v in source.values()):
        raise ValueError("Invalid nonpositive/nonfinite source value")
    common=sorted(set(gold)&set(fx)&set(homes))
    base=gold["2000-01"]/fx["2000-01"] if "2000-01" in fx else None
    if base is None:raise ValueError("No 2000-01 FX basis")
    output=[]
    for month in common:
        eur=gold[month]/fx[month];gram=eur/GRAMS
        output.append({"month":month,"gold_usd_oz":str(gold[month]),"usd_per_eur":str(fx[month]),"fx_days":counts[month],"house_eur":str(homes[month]),"gold_eur_oz":str(eur),"gold_eur_gram":str(gram),"gold_grams_per_house":str(homes[month]/gram),"gold_index":str(100*eur/base)})
    return output
def build_candidate(gold,fx,homes,counts):
    """Fail closed on historical gaps; keep trailing publication lag explicit."""
    coverage=classify_coverage(gold,fx,homes)
    historic=[row for row in coverage if row["status"]=="missing_historical"]
    if historic:raise ValueError("Historical source month gap: "+json.dumps(historic[:12]))
    rows=compute(gold,fx,homes,counts)
    if len(rows)!=sum(row["status"]=="complete" for row in coverage):
        raise ValueError("Complete month count differs from joined calculations")
    return {"data":rows,"coverage":coverage,"publication_authorized":False}
def main():
    wb=acquire(URL);sheet,col,gold,invalid,dup,header=parse_xlsx(wb)
    if not gold or invalid or dup or min(gold)!="2000-01":raise ValueError("World Bank invalid")
    fxraw=acquire(ECB);fx,counts,days=parse_ecb(fxraw)
    housing_raw=Path("data/cbs-housing.csv").read_bytes()
    print("CBS_INPUT",json.dumps({"path":"data/cbs-housing.csv","sha256":hashlib.sha256(housing_raw).hexdigest(),"bytes":len(housing_raw)}))
    homes=parse_housing(housing_raw);coverage=classify_coverage(gold,fx,homes)
    print("COVERAGE",json.dumps({"counts":{status:sum(row["status"]==status for row in coverage) for status in ("complete","missing_historical","pending_publication")},"noncomplete":[row for row in coverage if row["status"]!="complete"]}))
    if any(row["status"]=="missing_historical" for row in coverage):raise ValueError("Historical source month gap")
    out=compute(gold,fx,homes,counts)
    selected=["2000-01","2002-01","2004-01","2006-01","2008-09","2010-01","2012-01","2015-03","2018-01","2020-04","2025-01","2025-09"]
    print("SUMMARY",json.dumps({"worldbank_months":len(gold),"ecb_daily_rows":days,"ecb_months":len(fx),"cbs_months":len(homes),"joined_months":len(out),"joined_first":out[0]["month"] if out else None,"joined_last":out[-1]["month"] if out else None,"missing_fx":sorted(set(gold)-set(fx)),"missing_cbs":sorted(set(gold)-set(homes)),"method":"ratio of monthly arithmetic gold USD mean to monthly arithmetic USD-per-EUR FX mean; provisional","publication_authorized":False}))
    for row in out:
        if row["month"] in selected:print("RESULT",json.dumps(row))
    if not out or out[0]["month"]!="2000-01":raise ValueError("No reproducible basis month")
if __name__=="__main__":main()
