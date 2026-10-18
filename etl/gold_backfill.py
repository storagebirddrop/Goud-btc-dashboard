"""Opt-in private monthly gold backfill. Never writes public JSON or production DB."""
import argparse,csv,hashlib,json
from pathlib import Path
from etl.gold_monthly import acquire,parse_ecb,parse_housing,build_candidate,ECB
from etl.sources.worldbank_gold import URL,parse_xlsx
def backfill(housing_path):
    raw=acquire(URL)
    sheet,col,gold,invalid,duplicates,_=parse_xlsx(raw)
    if not gold or min(gold)!="2000-01" or invalid or duplicates:raise ValueError("Invalid World Bank GOLD history")
    fxraw=acquire(ECB);fx,counts,_=parse_ecb(fxraw)
    housing_raw=Path(housing_path).read_bytes()
    print("CBS_INPUT",json.dumps({"path":str(housing_path),"sha256":hashlib.sha256(housing_raw).hexdigest()}))
    houses=parse_housing(housing_raw)
    return build_candidate(gold,fx,houses,counts)
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--housing",default="data/cbs-housing.csv")
    p.add_argument("--output",default="")
    args=p.parse_args()
    candidate=backfill(args.housing)
    print("BACKFILL_VALIDATED",json.dumps({"months":len(candidate["data"]),"first":candidate["data"][0]["month"],"last":candidate["data"][-1]["month"],"publication_authorized":False,"coverage_pending":[x for x in candidate["coverage"] if x["status"]!="complete"]}))
    if args.output:
        dest=Path(args.output)
        if dest.resolve().is_relative_to(Path("frontend/public").resolve()):raise ValueError("Public output forbidden")
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(candidate,indent=2)+"\n",encoding="utf-8")
        print("PRIVATE_CANDIDATE_WRITTEN",str(dest))
if __name__=="__main__":main()
