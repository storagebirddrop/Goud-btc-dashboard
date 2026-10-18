"""Read-only full-history CBS 85773NED coverage and revision diagnostics.

Compares committed monthly source observations with current official CBS OData.
No data changes, imputations, source substitutions or publication approval.
"""
import argparse
import csv
import hashlib
import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from etl.sources.cbs import BASE, fetch_pages, make_session, parse_rows, resolve_fields, resolve_period_dimension

SERIES = ("nl_hpi", "nl_house_avg_eur")
SAMPLE_MONTHS = ("2000-01", "2010-01", "2020-01", "2025-01")
MONTH_RE = re.compile(r"^20[0-9]{2}-(0[1-9]|1[0-2])$")
# This tolerance is diagnostic, not permission to change or ignore source values.
ROUNDING_TOLERANCE = {"nl_hpi": 0.05, "nl_house_avg_eur": 0.5}


def month_range(first, last):
    if not MONTH_RE.fullmatch(first) or not MONTH_RE.fullmatch(last):
        raise ValueError("Invalid YYYY-MM month")
    start = int(first[:4]) * 12 + int(first[5:]) - 1
    end = int(last[:4]) * 12 + int(last[5:]) - 1
    if end < start:
        raise ValueError("Reversed month range")
    return [f"{i // 12:04d}-{i % 12 + 1:02d}" for i in range(start, end + 1)]


def read_committed(path):
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["date", "series", "value"]:
            raise ValueError("Unexpected committed CSV columns")
        result = {}
        previous_key = None
        for line, row in enumerate(reader, 2):
            if None in row or any(v is None for v in row.values()):
                raise ValueError(f"Malformed committed CSV row {line}")
            key = (row["date"], row["series"])
            if key in result:
                raise ValueError(f"Duplicate committed observation {key}")
            if previous is not None and key < previous:
                raise ValueError(f"Nonchronological committed CSV row {line}: {key}")
            previous = key
            if previous_key is not None and key < previous_key:
                raise ValueError(f"Non-chronological committed CSV at line {line}")
            previous_key = key
            if not MONTH_RE.fullmatch(key[0]) or key[1] not in SERIES:
                raise ValueError(f"Invalid month or series at line {line}: {key}")
            try:
                value = float(row["value"])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid numeric value at line {line}") from exc
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"Invalid positive finite value at line {line}")
            result[key] = value
    return result


def inspect_coverage(values, start="2000-01", end=None):
    if not values:
        raise ValueError("Empty dataset cannot establish coverage")
    months = [month for month, series in values]
    if end is None:
        end = max(months)
    expected = month_range(start, end)
    expected_keys = {(month, series) for month in expected for series in SERIES}
    observed_keys = set(values)
    return {"start": start, "end": end, "expected_months": len(expected),
            "expected_observations": len(expected_keys), "observed_observations": len(observed_keys),
            "missing": [{"month": m, "series": s} for m, s in sorted(expected_keys - observed_keys)],
            "outside_window": [{"month": m, "series": s} for m, s in sorted(observed_keys - expected_keys)]}


def classify(committed, observed, series):
    if committed is None:
        return "MISSING_COMMITTED"
    if observed is None:
        return "MISSING_LIVE"
    if committed == observed:
        return "MATCH"
    if abs(committed - observed) <= ROUNDING_TOLERANCE[series]:
        return "ROUNDING_DIFFERENCE"
    # A changed value is a potential source revision, not a proven revision:
    # historical CBS snapshots and consistent definitions would be required.
    return "VALUE_DIFFERENCE"


def compare_history(committed, live, start="2000-01", end=None):
    live_map = {}
    for month, series, value in live:
        key = (month, series)
        if key in live_map:
            raise ValueError(f"Duplicate live observation: {key}")
        if not MONTH_RE.fullmatch(month) or series not in SERIES or not math.isfinite(value) or value <= 0:
            raise ValueError(f"Invalid live observation: {key}")
        live_map[key] = value
    if not live_map:
        raise ValueError("Live source returned no observations")
    if end is None:
        end = max(month for month, _ in committed)
    local_coverage = inspect_coverage(committed, start, end)
    live_coverage = inspect_coverage(live_map, start, end)
    keys = [(month, series) for month in month_range(start, end) for series in SERIES]
    differences = []
    counts = Counter()
    for month, series in keys:
        stored, observed = committed.get((month, series)), live_map.get((month, series))
        status = classify(stored, observed, series)
        counts[status] += 1
        if status != "MATCH":
            differences.append({"month": month, "series": series, "classification": status,
                                "committed": stored, "live": observed,
                                "revision_confirmed": False})
    return {"committed_coverage": local_coverage, "live_coverage": live_coverage,
            "checked_months": len(month_range(start, end)),
            "checked_observations": len(keys),
            "counts": dict(sorted(counts.items())), "differences": differences,
            "complete": not local_coverage["missing"] and not live_coverage["missing"],
            "all_match": counts["MATCH"] == len(keys)}


def compare_samples(committed, live, months=SAMPLE_MONTHS):
    # A sparse sample must not imply complete historical coverage.
    live_map = {(m, s): v for m, s, v in live}
    return [{"month": m, "series": s, "status": classify(committed.get((m, s)), live_map.get((m, s)), s),
             "committed": committed.get((m, s)), "live": live_map.get((m, s))}
            for m in months for s in SERIES]



def fetch_live_history(session):
    fields = resolve_fields(fetch_pages(session, "MeasureCodes"))
    period = resolve_period_dimension(fetch_pages(session, "Dimensions"))
    codes = list(fields.values())
    conditions = " or ".join(f"Measure eq '{code}'" for code in codes)
    rows = fetch_pages(session, "Observations", params={"$filter": f"({conditions})"})
    return parse_rows(rows, fields, period), fields, period


def fetch_live_samples(session, months=SAMPLE_MONTHS):
    fields = resolve_fields(fetch_pages(session, "MeasureCodes"))
    period = resolve_period_dimension(fetch_pages(session, "Dimensions"))
    codes = list(fields.values())
    conditions = " or ".join(f"Measure eq '{code}'" for code in codes)
    periods = " or ".join(f"{period} eq '{month.replace('-', 'MM')}'" for month in months)
    rows = fetch_pages(session, "Observations",
                       params={"$filter": f"({conditions}) and ({periods})"})
    return parse_rows(rows, fields, period)


def main():
    parser = argparse.ArgumentParser(description="Read-only complete CBS source audit")
    parser.add_argument("--csv", default="data/cbs-housing.csv")
    parser.add_argument("--output", default="-", help="Diagnostic JSON path or '-' for stdout")
    args = parser.parse_args()
    now = datetime.now(timezone.utc).isoformat()
    raw = Path(args.csv).read_bytes()
    report = {"source": BASE, "retrieved_at_utc": now,
              "committed_csv_sha256": hashlib.sha256(raw).hexdigest(),
              "publication_approved": False,
              "comparison": "all months 2000-01 through last committed month, both measures; exact numeric equality",
              "rounding_tolerances_diagnostic_only": ROUNDING_TOLERANCE,
              "revision_policy": "VALUE_DIFFERENCE is potential, not confirmed historical revision",
              "status": "UNVERIFIED"}
    exit_code = 1
    try:
        committed = read_committed(args.csv)
        live, fields, period = fetch_live_history(make_session())
        report["source_measure_identifiers"] = fields
        report["source_period_dimension"] = period
        report.update(compare_history(committed, live))
        report["status"] = "PASS" if report["all_match"] and report["complete"] else "DIFFERENCES"
        # Differences are audit findings, not an execution failure.\n        # INCOMPLETE remains a failing result.\n        exit_code = 0
    except Exception as exc:
        # Explicitly fail closed; a network/contract failure must not be a PASS.
        report["status"] = "INCOMPLETE"
        report["error"] = f"{type(exc).__name__}: {exc}"
    rendered = json.dumps(report, indent=2, allow_nan=False, sort_keys=True) + "\n"
    if args.output == "-":
        print(rendered, end="")
    else:
        Path(args.output).write_text(rendered, encoding="utf-8")
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
