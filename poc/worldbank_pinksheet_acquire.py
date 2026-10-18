"""Read-only World Bank Pink Sheet monthly GOLD acquisition. No raw data committed."""
import argparse,csv,hashlib,io,json,sys,urllib.request,zipfile,xml.etree.ElementTree as ET
from datetime import datetime,timezone,timedelta
from decimal import Decimal,InvalidOperation
from pathlib import Path
from collections import Counter

URL="https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/related/CMO-Historical-Data-Monthly.xlsx"
NS={"x":"http://schemas.openxmlformats.org/spreadsheetml/2006/main","r":"http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
def parse_xlsx(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names=z.namelist()
        shared=[]
        if "xl/sharedStrings.xml" in names:
            root=ET.fromstring(z.read("xl/sharedStrings.xml"))
            shared=["".join(t.text or "" for t in si.findall(".//x:t",NS)) for si in root.findall("x:si",NS)]
        wb=ET.fromstring(z.read("xl/workbook.xml"))
        sheets=[s.attrib["name"] for s in wb.findall(".//x:sheets/x:sheet",NS)]
        selected=next((s for s in sheets if "monthly prices" in s.lower()),None)
        if not selected:raise ValueError("Monthly Prices worksheet not found: "+repr(sheets))
        sheet_el=next(s for s in wb.findall(".//x:sheets/x:sheet",NS) if s.attrib["name"]==selected)
        rid=sheet_el.attrib["{"+NS["r"]+"}id"]
        relroot=ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        rel=next(x for x in relroot if x.attrib["Id"]==rid)
        target=rel.attrib["Target"].lstrip("/")
        sheetpath=target if target.startswith("xl/") else "xl/"+target
        root=ET.fromstring(z.read(sheetpath))
        rows=[]
        for row in root.findall(".//x:sheetData/x:row",NS):
            cells={}
            for c in row.findall("x:c",NS):
                ref=c.attrib.get("r","")
                col="".join(ch for ch in ref if ch.isalpha())
                v=c.find("x:v",NS)
                inline=c.find("x:is",NS)
                value=(v.text if v is not None else "".join(t.text or "" for t in inline.findall(".//x:t",NS)) if inline is not None else "")
                if c.attrib.get("t")=="s" and value:value=shared[int(value)]
                cells[col]=value
            rows.append(cells)
        header=next((i for i,r in enumerate(rows) if any(str(v).strip().upper()=="GOLD" for v in r.values())),None)
        if header is None:raise ValueError("GOLD column not found")
        goldcol=next(k for k,v in rows[header].items() if str(v).strip().upper()=="GOLD")
        datecol="A"
        if goldcol==datecol:raise ValueError("Date column overlaps GOLD")
        results={};invalid=[];duplicates=[]
        for n,r in enumerate(rows[header+1:],header+2):
            rawdate=str(r.get(datecol,"")).strip()
            rawvalue=str(r.get(goldcol,"")).strip()
            if not rawdate:continue  # header/metadata rows without observation date
            try:
                if rawdate.replace(".","",1).isdigit():
                    d=(datetime(1899,12,30)+timedelta(days=float(rawdate))).date()
                else:
                    d=datetime.strptime(rawdate[:7],"%YM%m").date() if "M" in rawdate else datetime.strptime(rawdate[:7],"%Y-%m").date()
                period=d.strftime("%Y-%m")
                if period<"2000-01":continue
                value=Decimal(rawvalue)
                if not value.is_finite() or value<=0:raise ValueError("nonpositive/nonfinite")
                if period in results:duplicates.append(period)
                results[period]=value
            except (ValueError,InvalidOperation,OverflowError) as e:
                invalid.append({"row":n,"date":rawdate,"reason":str(e)})
        return selected,goldcol,results,invalid,duplicates,rows[:header+1]
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",help="Local private CSV path (never commit)")
    a=p.parse_args()
    request=urllib.request.Request(URL,headers={"User-Agent":"GoldDashboard-PoC/1.0"})
    timestamp=datetime.now(timezone.utc).isoformat()
    with urllib.request.urlopen(request,timeout=35) as response:
        status=response.status;ctype=response.headers.get("Content-Type");final=response.url;raw=response.read(15000001)
    if len(raw)>15000000:raise ValueError("Download exceeded 15MB")
    if not raw.startswith(b"PK"):raise ValueError("Response not XLSX ZIP")
    sheet,col,prices,invalid,duplicates,header=parse_xlsx(raw)
    months=sorted(prices)
    if not months:raise ValueError("No GOLD observations since 2000")
    expected=[]
    y,m=2000,1
    while (y,m)<=tuple(map(int,months[-1].split("-"))):
        expected.append(f"{y:04d}-{m:02d}");m+=1
        if m==13:y,m=y+1,1
    missing=sorted(set(expected)-set(months))
    sample=[p for p in ("2000-01","2002-01","2004-01","2006-01","2008-09","2010-01","2012-01","2015-03","2018-01","2020-04","2025-01","2025-09") if p in prices]
    result={"retrieved_at_utc":timestamp,"url":URL,"final_url":final,"http_status":status,"content_type":ctype,"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest(),"worksheet":sheet,"gold_column":col,"unit_claim":"USD per troy ounce (verify against workbook metadata)","count":len(months),"first":months[0],"last":months[-1],"missing_months":missing,"duplicate_months":duplicates,"invalid_rows":invalid,"sample":[{"month":m,"gold_usd_oz":str(prices[m])} for m in sample],"source_status":"UNVERIFIED_RIGHTS","publication_authorized":False}
    print(json.dumps(result,indent=2))
    if a.out:
        path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True)
        with path.open("w",newline="") as f:
            writer=csv.writer(f);writer.writerow(("month","gold_usd_oz"))
            writer.writerows((m,str(prices[m])) for m in months)
    if months[0]!="2000-01" or missing or duplicates or invalid:sys.exit(2)
if __name__=="__main__":main()
