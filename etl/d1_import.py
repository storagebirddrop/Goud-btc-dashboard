"""Build a deterministic, reviewed CBS D1 SQL import; never deploy automatically."""
import argparse
import math
import re
import sqlite3
from pathlib import Path

from etl.sources.cbs import fetch_cbs

ALLOWED = {"nl_hpi", "nl_house_avg_eur"}
MONTH = re.compile(r"^20\d{2}-(?:0[1-9]|1[0-2])$")

def validate(rows):
    result = {}
    for period, series, value in rows:
        if series not in ALLOWED or not MONTH.fullmatch(period):
            raise ValueError(f"Unexpected CBS observation: {series}/{period}")
        if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"Invalid CBS value: {series}/{period}")
        key = (series, period)
        if key in result:
            raise ValueError(f"Duplicate CBS observation: {series}/{period}")
        result[key] = value
    if not result or {series for series, _ in result} != ALLOWED:
        raise ValueError("Both CBS series are required")
    return result

def build_sql(rows):
    observations = validate(rows)
    lines = ["BEGIN TRANSACTION;"]
    for (series, period), value in sorted(observations.items()):
        lines.append(
            "INSERT INTO observations(series_id,period,value) "
            f"VALUES ('{series}','{period}',{value:.12g}) "
            "ON CONFLICT(series_id,period) DO UPDATE SET "
            "value=excluded.value, imported_at=CURRENT_TIMESTAMP;"
        )
    lines.append("COMMIT;")
    return "\n".join(lines) + "\n"

def verify_local(sql):
    db = sqlite3.connect(":memory:")
    db.executescript(Path("db/migrations/0001_init.sql").read_text(encoding="utf-8"))
    db.executescript(sql)
    initial = db.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    db.executescript(sql)
    repeated = db.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    assert initial == repeated, "Import is not idempotent"
    return initial

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/cbs-upsert.sql")
    args = parser.parse_args()
    sql = build_sql(fetch_cbs())
    count = verify_local(sql)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(sql, encoding="utf-8")
    print(f"Verified {count} CBS observations; generated {output} (no D1 writes)")

if __name__ == "__main__":
    main()
