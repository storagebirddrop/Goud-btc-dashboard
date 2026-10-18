"""Read-only CBS 85773NED spot-check against independently fetched live observations.

This is a diagnostic audit, not a refresh, backfill, publication approval or
revision policy. Never modifies the committed source or public JSON.
"""
import argparse
import csv
import json
from pathlib import Path

from etl.sources.cbs import fetch_pages, make_session, parse_rows, resolve_fields, resolve_period_dimension

SAMPLE_MONTHS = ("2000-01", "2010-01", "2020-01", "2025-01")
SERIES = ("nl_hpi", "nl_house_avg_eur")


def read_committed(path):
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["date", "series", "value"]:
            raise ValueError("Unexpected committed CSV columns")
        result = {}
        for line, row in enumerate(reader, 2):
            if None in row or any(v is None for v in row.values()):
                raise ValueError(f"Malformed committed CSV row {line}")
            key = (row["date"], row["series"])
            if key in result:
                raise ValueError(f"Duplicate committed observation {key}")
            result[key] = float(row["value"])
    return result


def compare_samples(committed, live, months=SAMPLE_MONTHS):
    """Compare actual observations, not derived values. No imputation."""
    current = {(month, series): value for month, series, value in live}
    checks = []
    for month in months:
        for series in SERIES:
            key = (month, series)
            stored = committed.get(key)
            observed = current.get(key)
            # Exact numeric comparison is intentional: any revision is flagged,
            # not silently accepted or reconciled.
            status = "MATCH" if stored is not None and observed is not None and stored == observed else (
                "MISSING_COMMITTED" if stored is None else
                "MISSING_LIVE" if observed is None else "DIFF"
            )
            checks.append({"month": month, "series": series, "status": status,
                           "committed": stored, "live": observed})
    return checks


def fetch_live_samples(session, months=SAMPLE_MONTHS):
    fields = resolve_fields(fetch_pages(session, "MeasureCodes"))
    period = resolve_period_dimension(fetch_pages(session, "Dimensions"))
    codes = list(fields.values())
    # Restrict both measures and sample periods, without assuming row order.
    conditions = " or ".join(f"Measure eq '{code}'" for code in codes)
    periods = " or ".join(f"{period} eq '{month.replace('-', 'MM')}'" for month in months)
    rows = fetch_pages(session, "Observations",
                       params={"$filter": f"({conditions}) and ({periods})"})
    return parse_rows(rows, fields, period)


def main():
    parser = argparse.ArgumentParser(description="Read-only CBS source spot-check")
    parser.add_argument("--csv", default="data/cbs-housing.csv")
    parser.add_argument("--output", default="-", help="Diagnostic JSON path or '-' for stdout")
    args = parser.parse_args()
    checks = compare_samples(read_committed(args.csv), fetch_live_samples(make_session()))
    report = {"source": "CBS 85773NED live OData v4", "publication_approved": False,
              "sample_months": list(SAMPLE_MONTHS), "checks": checks,
              "all_match": all(x["status"] == "MATCH" for x in checks)}
    rendered = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output == "-":
        print(rendered, end="")
    else:
        Path(args.output).write_text(rendered, encoding="utf-8")
    if not report["all_match"]:
        raise SystemExit("CBS source spot-check mismatches; review source revisions before changing data")


if __name__ == "__main__":
    main()
