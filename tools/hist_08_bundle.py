"""HIST-08: adapters from already pinned historical inputs into ARCH-02 (`hist-model/1`) research bundles.

Research only. Nothing here publishes, touches public data, `frontend/` or `etl/static_export.py`, or fills
a gap. Implemented against real committed inputs: CBS house price 2000-01.. (path passed in by the caller) and the
pinned CBS 1995-1999 fixture. `source_series` is the generic adapter for verified monthly inputs (gold C1/C4,
Bitstamp BTC/EUR, USD-derived BTC) that exist only inside read-only CI runs; it needs explicit provenance and
an explicit per-period quality label, and never interpolates.

CLI: python -m tools.hist_08_bundle cbs --cbs-csv CSV --out BUNDLE.json   (then: python tools/hist_model_check.py BUNDLE.json)
"""
import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from etl import hist_model as hm  # noqa: E402

CBS_FIXTURE = ROOT / "data" / "fixtures" / "cbs-1995-1999-i1.json"
CBS_RETRIEVED = "2026-10-19T00:00:00+00:00"  # CBS snapshot date taken from the pinned provenance filename (20261019)
CBS_DEFINITION = "cbs_avg_price_existing_dwellings_koopsom"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_series(series_id, asset_class, values, *, frequency, currency, unit, kind, definition_id, source_id,
                  raw_sha256, retrieved_at, vintage, quality_of, flags=(), breaks=(), basis="nominal"):
    """Generic adapter: {period: value} -> layer-1 Series. Missing periods stay absent (no fill).

    `quality_of(period)` must return a quality label for every period; there is no default.
    """
    if not values:
        raise hm.ModelError(f"{series_id}: no observations")
    rows = tuple(hm.Observation(series_id, p, v, currency, unit, definition_id, source_id, raw_sha256,
                                retrieved_at, vintage, quality_of(p), flags) for p, v in sorted(values.items()))
    s = hm.Series(series_id, "source", asset_class, frequency, currency, unit, definition_id, kind, basis,
                  None, tuple(breaks), rows)
    hm.validate_series(s)
    return s


def cbs_2000_series(csv_path):
    path = Path(csv_path)
    values = {}
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["series"] == "nl_house_avg_eur":
                if row["date"] in values:
                    raise hm.ModelError(f"duplicate CBS period {row['date']}")
                values[row["date"]] = row["value"]
    digest = _sha(path)
    return source_series("nl_house_avg_eur_2000", "housing", values, frequency="monthly", currency="EUR", unit="EUR",
                         kind="average_price", definition_id=CBS_DEFINITION, source_id="cbs_85773NED_csv",
                         raw_sha256=digest, retrieved_at=CBS_RETRIEVED, vintage=f"csv:{digest[:12]}",
                         quality_of=lambda p: "CONFIRMED")


def cbs_1995_1999_series(fixture_path=CBS_FIXTURE):
    path = Path(fixture_path)
    doc = json.loads(path.read_text(encoding="utf-8"))
    values = {}
    for row in doc["data"]:
        if row["series"] != "nl_house_avg_eur":
            raise hm.ModelError(f"unexpected series {row['series']!r} in fixture")
        if row["date"] in values:
            raise hm.ModelError(f"duplicate fixture period {row['date']}")
        if not isinstance(row["value"], int) or isinstance(row["value"], bool):
            raise hm.ModelError(f"fixture value for {row['date']} is not an integer: {row['value']!r}")
        values[row["date"]] = str(row["value"])
    digest = _sha(path)
    return source_series("nl_house_avg_eur_1995_1999", "housing", values, frequency="monthly", currency="EUR",
                         unit="EUR", kind="average_price", definition_id=CBS_DEFINITION,
                         source_id="cbs_85773NED_fixture_i1", raw_sha256=digest, retrieved_at=CBS_RETRIEVED,
                         vintage=f"fixture:{digest[:12]}", quality_of=lambda p: "CONFIRMED",
                         flags=("RETROSPECTIVE_EUR", "NLG_ORIGINALS_NOT_OBTAINED"),
                         breaks=(hm.Break("1995-01", "start of the pinned 1995-1999 segment; euro values are "
                                                     "retrospective, NLG originals not obtained; kept apart "
                                                     "from the 2000+ series, never spliced"),))


def build_bundle(series, releases=()):
    """Deterministic bundle dict (validated). Lineage hashes are checked by hist_model.validate_bundle."""
    bundle = {"schema": hm.SCHEMA, "series": [json.loads(hm.canonical_json(s)) for s in series],
              "releases": [json.loads(hm.canonical_json(r)) for r in releases]}
    errors = hm.validate_bundle(bundle)
    if errors:
        raise hm.ModelError("; ".join(errors))
    return bundle


def bundle_bytes(bundle) -> bytes:
    return hm.canonical_json(bundle)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["cbs"])
    ap.add_argument("--cbs-csv", required=True, help="committed CBS csv (read only; never written)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    bundle = build_bundle([cbs_1995_1999_series(), cbs_2000_series(args.cbs_csv)])
    raw = bundle_bytes(bundle)
    Path(args.out).write_bytes(raw)
    print(f"bundle {args.out}: {len(bundle['series'])} series, sha256 {hashlib.sha256(raw).hexdigest()}")
    for s in bundle["series"]:
        print(f"  {s['series_id']}: {len(s['observations'])} observations {s['observations'][0]['period']}..{s['observations'][-1]['period']}")


if __name__ == "__main__":
    main()
