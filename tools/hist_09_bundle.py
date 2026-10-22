"""HIST-09: verified Dutch housing research inputs -> ARCH-02 (`hist-model/1`) research bundles. RESEARCH ONLY.

Inputs (pinned, in the fixtures directory hist09): the HIST-09 package (NVM half-year medians 1975-2000, CBS
monthly 1995-2000, overlap CSV, manifest, validation JSON) and the original CBS StatLine 85773NED export zip.
Nothing here publishes, splices or interpolates. The NVM median (nominal, NLG, source population NVM brokers /
Vastgoedmarkt / press reports) and the CBS mean (registered sales) are different statistics and stay separate
series; their relation is only the derived `statistic_ratio`.

CLI: python -m tools.hist_09_bundle --inputs DIR --out OUTDIR
Writes hist09_A_nvm.json, hist09_B_cbs.json, hist09_C_overlap.json and hist09_outputs.json (sha256 of each).
"""
import argparse
import csv
import hashlib
import io
import json
import sys
import zipfile
from decimal import Decimal, getcontext
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from etl import hist_model as hm  # noqa: E402
from tools import hist_08_bundle as hb  # noqa: E402

getcontext().prec = hm.PREC
CBS_ZIP_NAME = "85773NED-202609220630.zip"
CBS_ZIP_SHA256 = "01d2aea00c19026e41b18ccd3a17b6beb004cd1b914a8a4a3f6683e15700584f"  # the owner-supplied export
NVM_CSV_SHA256 = "099489a42548f81c009607d464756871d11b8a646bfc54d0a28e687e3d5dffda"
CBS_EXPORTED = "2026-09-22T06:30:00+00:00"  # taken from the export file name (202609220630); not independently verified
NVM_RETRIEVED = "2026-10-22T00:00:00+00:00"  # HIST-09 verification date (owner screenshot of OTB page 136)
NVM_DEFINITION = "nvm_otb_median_existing_homes_nominal"
CBS_DEFINITION = hb.CBS_DEFINITION
MEASURES = {"M001534": "price", "M001532_2": "count", "M001535": "value"}
P136 = {(1995, 2): 227800, (1996, 1): 240900, (1996, 2): 250500, (1997, 1): 265100, (1997, 2): 271600,
        (1998, 1): 283400, (1998, 2): 301000, (1999, 1): 328000, (1999, 2): 352200, (2000, 1): 381700,
        (2000, 2): 394100}  # the 11 values read from the owner-supplied page 136 screenshot
FILES = ("HIST09_CBS_1995_2000_MONTHLY.csv", "HIST09_FINAL_REPORT.md", "HIST09_NVM_1975_2000_RESEARCH.csv",
         "HIST09_NVM_CBS_OVERLAP_1995_2000.csv", "HIST09_VALIDATION_RESULTS.json", "hist09_finalize.py")


class InputError(hm.ModelError):
    """The HIST-09 inputs fail an integrity or consistency check."""


def sha256_file(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_package(inputs) -> dict:
    """Manifest, validation JSON and the pinned zip / NVM hashes must all agree. Returns the validation JSON."""
    d = Path(inputs)
    manifest = json.loads((d / "SHA256_MANIFEST.json").read_text(encoding="utf-8"))
    if sorted(manifest) != sorted(FILES):
        raise InputError(f"manifest lists {sorted(manifest)}, expected {sorted(FILES)}")
    for name, digest in manifest.items():
        if sha256_file(d / name) != digest:
            raise InputError(f"{name}: sha256 differs from the manifest")
    validation = json.loads((d / "HIST09_VALIDATION_RESULTS.json").read_text(encoding="utf-8"))
    if sha256_file(d / CBS_ZIP_NAME) != CBS_ZIP_SHA256 or validation["cbs_csv_zip_sha256"] != CBS_ZIP_SHA256:
        raise InputError("CBS export zip sha256 differs from the pinned / recorded value")
    if sha256_file(d / "HIST09_NVM_1975_2000_RESEARCH.csv") != NVM_CSV_SHA256 or validation["nvm_csv_sha256"] != NVM_CSV_SHA256:
        raise InputError("NVM csv sha256 differs from the pinned / recorded value")
    return validation


def _dutch_decimal(text) -> Decimal:
    return Decimal(text.replace(".", "").replace(",", "."))


def read_cbs_zip(inputs) -> dict:
    """Independent parse of the original CBS export: {measure_name: {'1995-01': Decimal}} for 1995..2000 months."""
    with zipfile.ZipFile(Path(inputs) / CBS_ZIP_NAME) as z:
        titles = {r["Identifier"]: r["Title"] for r in csv.DictReader(
            io.StringIO(z.read("MeasureCodes.csv").decode("utf-8-sig")), delimiter=";")}
        rows = list(csv.DictReader(io.StringIO(z.read("Observations.csv").decode("utf-8-sig")), delimiter=";"))
    if titles.get("M001534") != "Gemiddelde verkoopprijs" or titles.get("M001532_2") != "Verkochte woningen":
        raise InputError("CBS measure titles differ from the expected 85773NED definitions")
    out = {name: {} for name in MEASURES.values()}
    quarterly = {}
    for r in rows:
        period, measure = r["Perioden"], r["Measure"]
        if measure not in MEASURES or not ("1995" <= period[:4] <= "2000"):
            continue
        if not r["Value"]:
            raise InputError(f"missing official value {period} {measure}")
        value = _dutch_decimal(r["Value"])
        if "MM" in period:
            month = f"{period[:4]}-{period[6:]}"
            if month in out[MEASURES[measure]]:
                raise InputError(f"duplicate {month} {measure}")
            out[MEASURES[measure]][month] = value
        elif "KW" in period:
            quarterly[(period, MEASURES[measure])] = value
    expected = {f"{y}-{m:02d}" for y in range(1995, 2001) for m in range(1, 13)}
    for name, values in out.items():
        if set(values) != expected:
            raise InputError(f"{name}: expected 72 months 1995-01..2000-12, got {len(values)}")
        if any(v <= 0 for v in values.values()):
            raise InputError(f"{name}: non-positive value")
    out["_quarterly_counts"] = {p: v for (p, n), v in quarterly.items() if n == "count"}
    return out


def read_nvm_csv(inputs) -> dict:
    rows = list(csv.DictReader((Path(inputs) / "HIST09_NVM_1975_2000_RESEARCH.csv").open(encoding="utf-8-sig", newline="")))
    values = {}
    for r in rows:
        key = f"{int(r['year'])}-H{int(r['halfyear'])}"
        if r["halfyear"] not in ("1", "2") or key in values:
            raise InputError(f"bad or duplicate NVM period {key}")
        if r["price_concept"] != "nominal_median_existing_homes" or r["source_table"] != "OTB_2001_Table_B3.8":
            raise InputError(f"{key}: unexpected NVM definition {r['price_concept']!r}/{r['source_table']!r}")
        values[key] = Decimal(r["nvm_median_nlg"])
    expected = hm.expected_periods("1975-H1", "2000-H2", "semiannual")
    if len(values) != 52 or sorted(values, key=lambda p: hm.period_key(p, "semiannual")) != expected:
        raise InputError("NVM must hold exactly 52 consecutive half-years 1975-H1..2000-H2")
    if any(v <= 0 for v in values.values()):
        raise InputError("non-positive NVM value")
    for (y, h), v in P136.items():
        if values[f"{y}-H{h}"] != v:
            raise InputError(f"{y}-H{h}: NVM csv differs from the page 136 screenshot value {v}")
    return values


def _flags_nvm(period) -> tuple:
    y, h = int(period[:4]), int(period[6])
    on136 = (y, h) in P136
    return ("OTB_2001_B3_8", "VISUAL_P136_SESSION_REVIEW" if on136 else "VISUAL_P135_PER_PROJECT_CONTROL")


def nvm_nlg_series(values, raw_sha) -> hm.Series:
    rows = tuple(hm.Observation("nvm_median_nlg_halfyear", p, v, "NLG", "NLG", NVM_DEFINITION, "otb_2001_table_b3_8",
                                raw_sha, NVM_RETRIEVED, f"csv:{raw_sha[:12]}", "CONFIRMED", _flags_nvm(p))
                 for p, v in values.items())
    s = hm.Series("nvm_median_nlg_halfyear", "source", "housing", "semiannual", "NLG", "NLG", NVM_DEFINITION,
                  "median_price", "nominal", None, (), rows)
    hm.validate_series(s)
    return s


def _monthly(series_id, kind, ccy, unit, values, raw_sha, definition, vintage) -> hm.Series:
    flags = ("CBS_85773NED", "RETROSPECTIVE_EUR") if ccy == "EUR" else ("CBS_85773NED",)
    s = hb.source_series(series_id, "housing", {p: str(v) for p, v in values.items()}, frequency="monthly",
                         currency=ccy, unit=unit, kind=kind, definition_id=definition, source_id="cbs_85773NED_export_zip",
                         raw_sha256=raw_sha, retrieved_at=CBS_EXPORTED, vintage=vintage, quality_of=lambda p: "CONFIRMED",
                         flags=flags)
    return s


def cbs_series(cbs) -> dict:
    vintage = f"zip:{CBS_ZIP_SHA256[:12]}"
    return {
        "price": _monthly("cbs_avg_price_1995_2000", "average_price", "EUR", "EUR", cbs["price"], CBS_ZIP_SHA256,
                          CBS_DEFINITION, vintage),
        "count": _monthly("cbs_sold_homes_1995_2000", "transaction_count", "NONE", "homes", cbs["count"],
                          CBS_ZIP_SHA256, "cbs_registered_sales_count_existing_dwellings", vintage),
        "value": _monthly("cbs_total_value_1995_2000", "transaction_value", "EUR", "EUR_million", cbs["value"],
                          CBS_ZIP_SHA256, "cbs_total_sale_value_existing_dwellings", vintage),
    }


def build_all(inputs):
    """Return (dict of series by id, bundles A/B/C as lists of series). Raises InputError on any defect."""
    verify_package(inputs)
    d = Path(inputs)
    nvm_nlg = nvm_nlg_series(read_nvm_csv(d), NVM_CSV_SHA256)
    cbs = read_cbs_zip(d)
    check_quarter_counts(cbs)
    src = cbs_series(cbs)
    nvm_eur = hm.redenominate_nlg_to_eur(nvm_nlg, series_id="nvm_median_eur_halfyear")
    cbs_half = hm.weighted_half_year_mean(src["price"], src["count"], series_id="cbs_avg_price_eur_halfyear")
    ratio = hm.statistic_ratio(nvm_eur, cbs_half, series_id="nvm_over_cbs_ratio_halfyear")
    growth = {f"{name}_{basis}": hm.growth_ratio(s, basis=basis, series_id=f"{name}_growth_{basis}")
              for name, s in (("nvm_eur", nvm_eur), ("cbs_half", cbs_half))
              for basis in ("sequential", "year_over_year")}
    allseries = {s.series_id: s for s in [nvm_nlg, nvm_eur, *src.values(), cbs_half, ratio, *growth.values()]}
    a = [nvm_nlg, nvm_eur]
    b = [src["price"], src["count"], src["value"], cbs_half]
    c = [nvm_nlg, nvm_eur, src["price"], src["count"], src["value"], cbs_half, ratio, *growth.values()]
    return allseries, {"A_nvm": a, "B_cbs": b, "C_overlap": c}


def check_quarter_counts(cbs):
    """Monthly counts must add up to every official quarterly count (CBS internal consistency)."""
    q = cbs["_quarterly_counts"]
    for year in range(1995, 2001):
        for quarter in range(1, 5):
            months = [f"{year}-{m:02d}" for m in range(3 * quarter - 2, 3 * quarter + 1)]
            if sum(cbs["count"][m] for m in months) != q[f"{year}KW{quarter:02d}"]:
                raise InputError(f"{year} Q{quarter}: monthly counts differ from the official quarterly count")


def reconcile_with_hist08(src, hist08_fixture=None, hist08_csv=None) -> dict:
    """The HIST-08 CBS series (1995-1999 fixture, 2000 csv) must equal the HIST-09 monthly prices; no conflicts."""
    out = {}
    price = {o.period: o.value for o in src["price"].observations}
    for name, series in (("fixture_1995_1999", hb.cbs_1995_1999_series(hist08_fixture) if hist08_fixture
                          else hb.cbs_1995_1999_series()),
                         ("csv_2000", hb.cbs_2000_series(hist08_csv))):
        rows = {o.period: o.value for o in series.observations if o.period in price}
        conflicts = [p for p, v in rows.items() if v != price[p]]
        if conflicts:
            raise InputError(f"{name}: conflicts with the HIST-09 CBS prices at {conflicts[:3]}")
        out[name] = len(rows)
    return out


def verify_against_overlap_csv(allseries, inputs) -> int:
    """Every row of the HIST-09 overlap CSV is reproduced from the bundle (6 decimal places, ROUND_HALF_EVEN as f-format)."""
    rows = list(csv.DictReader((Path(inputs) / "HIST09_NVM_CBS_OVERLAP_1995_2000.csv").open(encoding="utf-8", newline="")))
    nvm_nlg, nvm_eur = allseries["nvm_median_nlg_halfyear"], allseries["nvm_median_eur_halfyear"]
    cbs_half = {p.period: p for p in allseries["cbs_avg_price_eur_halfyear"].points}
    eur = {p.period: p.value for p in nvm_eur.points}
    nlg = {o.period: o.value for o in nvm_nlg.observations}
    ratio = {p.period: p.value for p in allseries["nvm_over_cbs_ratio_halfyear"].points}
    counts = {}
    for o in allseries["cbs_sold_homes_1995_2000"].observations:
        key = f"{o.period[:4]}-H{1 if int(o.period[5:]) <= 6 else 2}"
        counts[key] = counts.get(key, 0) + o.value
    growth = {k: {p.period: p.value for p in allseries[v].points} for k, v in (
        ("seq_nvm", "nvm_eur_growth_sequential"), ("seq_cbs", "cbs_half_growth_sequential"),
        ("yoy_nvm", "nvm_eur_growth_year_over_year"), ("yoy_cbs", "cbs_half_growth_year_over_year"))}

    def f(x):
        return f"{x:.6f}"

    if len(rows) != 12:
        raise InputError("overlap csv must hold 12 rows")
    for index, r in enumerate(rows):
        p = r["period"]
        expect = {"nvm_median_nlg": str(nlg[p]), "nvm_median_eur": f(eur[p]), "cbs_mean_eur_weighted": f(cbs_half[p].value),
                  "cbs_sold_homes": str(int(counts[p])), "nvm_minus_cbs_eur": f(eur[p] - cbs_half[p].value),
                  "nvm_vs_cbs_pct": f((ratio[p] - 1) * 100)}
        # the HIST-09 csv leaves growth blank when the predecessor lies before the 1995-H1 overlap window
        for name, key, lag in (("sequential_nvm_growth_pct", "seq_nvm", 1), ("sequential_cbs_growth_pct", "seq_cbs", 1),
                               ("year_over_year_nvm_growth_pct", "yoy_nvm", 2),
                               ("year_over_year_cbs_growth_pct", "yoy_cbs", 2)):
            expect[name] = f((growth[key][p] - 1) * 100) if index >= lag else ""
        for name, want in expect.items():
            if r[name] != want:
                raise InputError(f"{p} {name}: csv {r[name]!r} differs from the bundle {want!r}")
    return len(rows)


def write_outputs(bundles, out) -> dict:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    digests = {}
    for name, series in bundles.items():
        raw = hb.bundle_bytes(hb.build_bundle(series))
        path = out / f"hist09_{name}.json"
        path.write_bytes(raw)
        digests[path.name] = {"sha256": hashlib.sha256(raw).hexdigest(), "series": [s.series_id for s in series]}
    (out / "hist09_outputs.json").write_bytes(hm.canonical_json(digests))
    return digests


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cbs-csv", help="committed CBS csv, for the HIST-08 reconciliation (read only)")
    args = ap.parse_args(argv)
    allseries, bundles = build_all(args.inputs)
    print(f"overlap csv rows reproduced: {verify_against_overlap_csv(allseries, args.inputs)}/12")
    if args.cbs_csv:
        print("HIST-08 reconciliation (observations compared, 0 conflicts):",
              reconcile_with_hist08(cbs_series(read_cbs_zip(args.inputs)), hist08_csv=args.cbs_csv))
    for name, info in write_outputs(bundles, args.out).items():
        print(f"{name}: sha256 {info['sha256']} ({len(info['series'])} series)")


if __name__ == "__main__":
    main()
