"""Deterministic monthly CSV ETL. No automatic remote writes."""
import argparse
from collections import defaultdict
from datetime import date
from pathlib import Path

from etl.validate import MONTHLY, assert_valid, read_observations

SERIES = MONTHLY

def month(value):
    value = value.strip()
    if len(value) == 7:
        value += "-01"
    d = date.fromisoformat(value)
    return d.strftime("%Y-%m") if d.year >= 2000 else None

def load_csv(path):
    assert_valid(path)
    rows, _ = read_observations(path)
    data = defaultdict(list)
    for series, d, value in rows:
        data[(series, d.isoformat() if series == "gold_daily_eur_oz" else d.strftime("%Y-%m"))].append(value)
    return data

def transform(data):
    out = {}
    gold_daily = defaultdict(list)
    for (series, period), values in data.items():
        if series in SERIES:
            if len(values) != 1:
                raise ValueError(f"Duplicate monthly observation: {series}/{period}")
            out[(series, period)] = values[0]
        elif series == "gold_daily_eur_oz":
            if len(values) != 1:
                raise ValueError(f"Duplicate daily observation: {series}/{period}")
            if len(period) != 10:
                raise ValueError(f"Daily gold observation requires YYYY-MM-DD: {period}")
            gold_daily[period[:7]].append(values[0])
        else:
            raise ValueError(f"Unknown series: {series}")
    for period, values in gold_daily.items():
        if ("gold_eur_oz", period) in out:
            raise ValueError(f"Conflicting gold inputs: {period}")
        out[("gold_eur_oz", period)] = sum(values) / len(values)
    return out

def export_sql(observations, path):
    if not observations:
        raise ValueError("Refusing empty import")
    lines = ["BEGIN TRANSACTION;"]
    for (series, period), value in sorted(observations.items()):
        lines.append(f"INSERT INTO observations(series_id,period,value) VALUES ('{series}','{period}',{value:.12g}) ON CONFLICT(series_id,period) DO UPDATE SET value=excluded.value, imported_at=CURRENT_TIMESTAMP;")
    lines.append("COMMIT;")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", nargs="+", required=True)
    parser.add_argument("--output", default="data/upsert.sql")
    args = parser.parse_args()
    merged = defaultdict(list)
    for path in args.input:
        for key, values in load_csv(path).items():
            merged[key].extend(values)
    result = transform(merged)
    export_sql(result, args.output)
    print(f"Exported {len(result)} observations to {args.output}")

if __name__ == "__main__":
    main()
