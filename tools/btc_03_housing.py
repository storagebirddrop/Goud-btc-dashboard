"""BTC-03 research only: Dutch housing prices in BTC and satoshis on ARCH-02. NOTHING IS PUBLISHED.

Segments stay separate and are never spliced: Mt. Gox USD (early, Q3 research), Bitstamp USD converted with the ECB
rate (USD-derived BTC/EUR, Q3 until sustained liquidity, Q2 from it) and Bitstamp EUR (EUR-native, Q1 once liquid).
PROPOSED methods (not accepted by Project Control): A1 = arithmetic mean of all daily UTC closes of a COMPLETE calendar
month; C1 = mean(USD closes) / mean(ECB USD-per-EUR over valid days). Missing days and months are explicit nulls.
Raw third-party exchange data are read in memory in GitHub Actions only; nothing raw is committed or uploaded.
Offline tests use synthetic data and prove code, not data.
"""
import argparse
import contextlib
import hashlib
import io
import json
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from etl import hist_model as hm  # noqa: E402
from tools import btc_02_history as H  # noqa: E402
from tools import hist_08_bundle as hb  # noqa: E402
from tools import hist_10_gold_housing as h10  # noqa: E402

METHOD_ID = "BTC03_A1_C1_V1"
METHOD_FLAG = f"METHOD:{METHOD_ID}"
PROPOSED_FLAG = "PROPOSED_METHOD"
RESEARCH_FLAG = "BITCOIN_RESEARCH_ONLY"
RETRIEVED = "2026-10-22T00:00:00+00:00"  # default for offline tests; a real run records its actual UTC acquisition time
LIQUID_USD_NOTIONAL = H.DEFAULT_LIQUID_USD_NOTIONAL_PER_DAY
SATS = H.SATS_PER_BTC
RESEARCH_CUTOFF = "2026-08"  # last month with a CBS house price; derived pins stop here
MIN_FX_COVERAGE = Decimal("0.5")  # same provisional rule as HIST-10 for monthly FX means
PIN_WINDOWS = {"bitstamp_usd_daily": ("2011-01-01", "2026-08-31"), "bitstamp_eur_daily": ("2011-01-01", "2026-08-31"),
               "mtgox_usd_daily": ("2010-01-01", "2014-12-31"), "kraken_eur_daily": ("2014-01-01", "2021-04-30"),
               "ecb_usd_per_eur_daily": ("1999-01-04", "2026-08-31")}
SEGMENTS = {"mtgox_usd_derived": "Mt. Gox USD x ECB (C1), early research, Q3",
            "bitstamp_usd_derived": "Bitstamp USD x ECB (C1), Q3 until sustained liquidity then Q2",
            "bitstamp_eur_native": "Bitstamp EUR native (A1), Q1 once liquid"}


class Btc03Error(hm.ModelError):
    """Input or consistency defect: fail closed."""


# ------------------------------------------------------------------ quality levels (PROPOSED, BTC-02 rules)
def quality_months(usd_close: dict, usd_vol: dict, eur_close: dict | None = None) -> dict:
    """{'liquid_start': 'YYYY-MM'|None, 'bitstamp_usd': {month: Q}, 'bitstamp_eur': {month: Q}} for COMPLETE months.

    Liquidity = mean daily USD notional (close x volume) >= 1,000,000 sustained: every month from `liquid_start` on.
    USD-derived: Q2 from liquid_start, else Q3. EUR-native: Q1 from liquid_start, else Q3. Mt. Gox is always Q3.
    """
    notional = H.monthly_notional(usd_close, usd_vol)
    start = H.sustained_from(notional, LIQUID_USD_NOTIONAL)
    liquid = lambda m: start is not None and m >= start  # noqa: E731
    usd_stats, eur_stats = H.monthly_stats(usd_close), H.monthly_stats(eur_close or {})
    return {"liquid_start": start,
            "bitstamp_usd": {m: ("Q2" if liquid(m) else "Q3") for m, s in usd_stats.items() if s["complete"]},
            "bitstamp_eur": {m: ("Q1" if liquid(m) else "Q3") for m, s in eur_stats.items() if s["complete"]},
            "notional_by_month": notional}


# ------------------------------------------------------------------ model construction
def daily_btc_series(series_id, closes: dict, currency, *, source_id, raw_sha, month_quality=None, fixed_quality=None,
                     acquired_at=RETRIEVED) -> hm.Series:
    """Daily UTC closes {YYYY-MM-DD: Decimal} -> source series (asset bitcoin, unit '<CCY>_per_BTC').

    Quality flag BTC_Qn is set per day from its month (or fixed). Floats, non-ISO days and non-positive prices are rejected.
    """
    if currency not in ("USD", "EUR"):
        raise Btc03Error(f"{series_id}: unknown quote currency {currency!r}")
    if not closes:
        raise Btc03Error(f"{series_id}: no observations")
    unit = f"{currency}_per_BTC"
    rows = []
    for day in sorted(closes):
        value = closes[day]
        if isinstance(value, (float, bool)):
            raise Btc03Error(f"{series_id} {day}: float input refused")
        if date.fromisoformat(day).isoformat() != day:
            raise Btc03Error(f"{series_id}: noncanonical day {day!r}")
        q = fixed_quality or (month_quality or {}).get(day[:7], "Q3")
        rows.append(hm.Observation(series_id, day, value, currency, unit, f"{source_id}_daily_close_utc", source_id, raw_sha,
                                   acquired_at, f"sha:{raw_sha[:12]}", "PROPOSED",
                                   (METHOD_FLAG, PROPOSED_FLAG, RESEARCH_FLAG, f"BTC_{q}")))
    s = hm.Series(series_id, "source", "bitcoin", "daily", currency, unit, f"{source_id}_daily_close_utc", "spot_price",
                  "nominal", None, (), tuple(rows))
    hm.validate_series(s)
    return s


def ecb_daily_series(daily: dict, raw_sha: str, acquired_at=RETRIEVED) -> hm.Series:
    """ECB EXR.D.USD.EUR.SP00.A: USD per 1 EUR. The direction is part of the unit and enforced on use."""
    if not daily:
        raise Btc03Error("ecb: no observations")
    rows = tuple(hm.Observation("ecb_usd_per_eur_daily", d, v, "USD", "USD_per_EUR", "ecb_ref_usd_per_eur_daily", "ecb_exr_d_usd",
                                raw_sha, acquired_at, f"sha:{raw_sha[:12]}", "CONFIRMED", (METHOD_FLAG,))
                 for d, v in sorted(daily.items()))
    s = hm.Series("ecb_usd_per_eur_daily", "source", "fx", "daily", "USD", "USD_per_EUR", "ecb_ref_usd_per_eur_daily", "fx_rate",
                  "nominal", None, (), rows)
    hm.validate_series(s)
    return s


def build_btc(sources: dict) -> dict:
    """sources: {'bitstamp_usd','bitstamp_eur','mtgox_usd','kraken_eur' (optional), 'ecb'} daily series.

    Monthly A1 uses min_coverage = 1: only COMPLETE calendar months get a value, everything else is an explicit null.
    """
    out = dict(sources)
    one = Decimal(1)
    ecb_m = hm.monthly_mean(sources["ecb"], min_coverage=MIN_FX_COVERAGE, series_id="ecb_usd_per_eur_monthly",
                            complete_final_month=True)
    out["ecb_usd_per_eur_monthly"] = ecb_m
    for key, sid in (("bitstamp_usd", "bitstamp_usd_monthly_a1"), ("bitstamp_eur", "bitstamp_eur_monthly_a1"),
                     ("mtgox_usd", "mtgox_usd_monthly_a1"), ("kraken_eur", "kraken_eur_monthly_a1")):
        if key in sources:
            out[sid] = hm.monthly_mean(sources[key], min_coverage=one, series_id=sid)
    for key, sid in (("bitstamp_usd", "bitstamp_usd_derived_eur_c1"), ("mtgox_usd", "mtgox_usd_derived_eur_c1")):
        if key in sources:
            out[sid] = hm.convert_currency(out[f"{key}_monthly_a1"], ecb_m, to_currency="EUR", series_id=sid)
    return out


SEGMENT_SERIES = {"mtgox_usd_derived": "mtgox_usd_derived_eur_c1", "bitstamp_usd_derived": "bitstamp_usd_derived_eur_c1",
                  "bitstamp_eur_native": "bitstamp_eur_monthly_a1"}


def build_housing(btc: dict, house: hm.Series) -> dict:
    """BTC and satoshi per house for one housing statistic and every available segment (separate series, no splice)."""
    stem = {"average_price": "cbs", "median_price": "nvm"}.get(house.kind)
    if stem is None:
        raise Btc03Error(f"{house.series_id}: only mean (CBS) and median (NVM) housing prices are supported")
    out = {}
    for seg, sid in SEGMENT_SERIES.items():
        if sid in btc:
            out[f"{stem}_btc_per_house_{seg}"] = hm.btc_per_house(house, btc[sid], series_id=f"{stem}_btc_per_house_{seg}")
            out[f"{stem}_sats_per_house_{seg}"] = hm.sats_per_house(house, btc[sid], series_id=f"{stem}_sats_per_house_{seg}")
    return out


def nvm_overlap_report(nvm_half: hm.Series, btc_monthly: dict) -> dict:
    """Half-years with an NVM value AND six complete BTC months. NVM is semiannual: nothing is inferred or spread."""
    nv = {p: o for p, o in ((o.period, o.value) for o in nvm_half.observations)}
    first_btc = {}
    for name, s in btc_monthly.items():
        vals = [p.period for p in s.points if p.value is not None]
        first_btc[name] = (vals[0], vals[-1]) if vals else None
    halves = {}
    for name, s in btc_monthly.items():
        have = {p.period for p in s.points if p.value is not None}
        halves[name] = sorted(h for h in nv if all(m in have for m in h10.half_months(h)))
    return {"nvm_first": min(nv), "nvm_last": max(nv), "n_nvm": len(nv), "btc_first_last_complete_month": first_btc,
            "overlapping_half_years": halves, "n_overlap": {k: len(v) for k, v in halves.items()},
            "reason": "NVM ends " + max(nv) + "; no complete BTC month exists that early" if not any(halves.values()) else ""}


def lineage(allseries: dict, members) -> list:
    return h10.lineage_closure(allseries, members)


def bundles(allseries: dict) -> dict:
    g = allseries
    spec = {"A_btc_source": [k for k in ("bitstamp_usd_monthly_a1", "bitstamp_eur_monthly_a1", "mtgox_usd_monthly_a1",
                                         "kraken_eur_monthly_a1") if k in g],
            "B_btc_eur": [k for k in ("mtgox_usd_derived_eur_c1", "bitstamp_usd_derived_eur_c1", "bitstamp_eur_monthly_a1") if k in g],
            "C_cbs_btc_sats": [k for k in g if k.startswith("cbs_btc_per_house_") or k.startswith("cbs_sats_per_house_")]}
    return {name: lineage(g, [g[i] for i in ids]) for name, ids in spec.items() if ids}


def write_bundles(bundle_map: dict, out) -> dict:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    digests = {}
    for name, series in bundle_map.items():
        raw = hb.bundle_bytes(hb.build_bundle(series))
        path = out / f"btc03_{name}.json"
        path.write_bytes(raw)
        digests[path.name] = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "series": len(series),
                              "derived_ids": [s.series_id for s in series if s.layer != "source"]}
    return digests


# ------------------------------------------------------------------ vintage: window pins and derived-value hash
def derived_values_sha256(series: dict, cutoff=RESEARCH_CUTOFF) -> str:
    """Identity of the derived research values by VALUE up to the research cutoff (no timestamps, no provenance)."""
    names = sorted(k for k in series if series[k].layer != "source" and series[k].frequency == "monthly"
                   and (k.endswith("_monthly_a1") or k.endswith("_eur_c1") or k.startswith("cbs_")))
    lines = "".join(f"{n}|{p.period}|{'' if p.value is None else hm.dec_str(p.value)}\n"
                    for n in names for p in series[n].points if p.period <= cutoff)
    return hashlib.sha256(lines.encode()).hexdigest()


def source_windows(daily: dict) -> dict:
    """daily: {name: {day: Decimal}} -> pin windows (first, last, n, sha256) for every name in PIN_WINDOWS present."""
    return {n: h10.window_hash(daily[n], *PIN_WINDOWS[n]) for n in PIN_WINDOWS if n in daily}


def check_pins(current: dict, derived_hash: str, pins) -> dict:
    """MATCH / SOURCE_REVISED / DEFECT_DERIVED_DRIFT / METHOD_CHANGED / UNPINNED (same semantics as HIST-10)."""
    if not pins:
        return {"status": "UNPINNED", "sources": {k: "UNPINNED" for k in current}}
    if pins.get("method_id") != METHOD_ID:
        return {"status": "METHOD_CHANGED", "pinned_method": pins.get("method_id"), "method": METHOD_ID}
    per = {}
    for name, cur in current.items():
        pin = pins.get("sources", {}).get(name)
        per[name] = "UNPINNED" if not pin else "MATCH" if (pin["sha256"], pin["n"], pin["first"], pin["last"]) == (
            cur["sha256"], cur["n"], cur["first"], cur["last"]) else "REVISED"
    if "REVISED" in per.values() or "UNPINNED" in per.values():
        return {"status": "SOURCE_REVISED" if "REVISED" in per.values() else "UNPINNED", "sources": per}
    return {"status": "MATCH" if pins.get("derived", {}).get("values_sha256") == derived_hash else "DEFECT_DERIVED_DRIFT", "sources": per}


# ------------------------------------------------------------------ exact helpers and sensitivity (Fractions / Decimals)
def fr(x) -> Fraction:
    return Fraction(x) if not isinstance(x, Fraction) else x


def a1_months(daily: dict) -> dict:
    """{month: Fraction mean of daily closes} for COMPLETE months only."""
    complete = {m for m, s in H.monthly_stats(daily).items() if s["complete"]}
    groups = {}
    for day, v in daily.items():
        if day[:7] in complete:
            groups.setdefault(day[:7], []).append(fr(v))
    return {m: sum(v) / len(v) for m, v in groups.items()}  # exact Fractions: independent of the ambient Decimal context


def a2_months(daily: dict) -> dict:
    """Month-end close (last calendar day) for complete months."""
    return {m: fr(daily[f"{m}-{s['calendar_days']:02d}"]) for m, s in H.monthly_stats(daily).items() if s["complete"]}


def ecb_month_means(ecb: dict) -> dict:
    groups = {}
    for d, v in ecb.items():
        groups.setdefault(d[:7], []).append(fr(v))
    return {m: sum(v) / len(v) for m, v in groups.items() if len(v) >= 1}


def c1_months(usd_daily: dict, ecb: dict) -> dict:
    a1, fx = a1_months(usd_daily), ecb_month_means(ecb)
    return {m: v / fx[m] for m, v in a1.items() if m in fx}


def per_house(house_eur, btc_eur) -> tuple:
    btc = fr(house_eur) / fr(btc_eur)
    return btc, btc * 10 ** 8


def rel_stats(a: dict, b: dict) -> dict:
    """|a-b|/b over common months; percent strings. None when no overlap."""
    ms = sorted(m for m in set(a) & set(b) if a[m] is not None and b[m] is not None)
    if not ms:
        return {"n": 0}
    dev = {m: abs(fr(a[m]) - fr(b[m])) / fr(b[m]) for m in ms}
    signed = [(fr(a[m]) - fr(b[m])) / fr(b[m]) for m in ms]
    srt = sorted(dev.values())
    p = lambda f: f"{float(f * 100):.3f}"  # noqa: E731
    worst = max(dev, key=lambda k: (dev[k], k))
    return {"n": len(ms), "first": ms[0], "last": ms[-1], "mean_pct": p(sum(srt) / len(srt)), "p50_pct": p(srt[(len(srt) - 1) // 2]),
            "p99_pct": p(srt[min(len(srt) - 1, -(-len(srt) * 99 // 100) - 1)]), "max_pct": p(srt[-1]), "max_at": worst,
            "signed_mean_pct": p(sum(signed) / len(signed))}


def half_year_methods(daily: dict, half: str):
    """BTC half-year price under alternative aggregation rules; None unless ALL six calendar months are complete.

    M1 mean of the six monthly A1; D mean of all daily closes of the half-year (day-weighted); M3 A1 of the last month;
    M4 A1 of the first month; M5 median of the six monthly A1; M6 close of the last day. Sensitivity only.
    """
    months = h10.half_months(half)
    m = a1_months(daily)
    if any(x not in m for x in months):
        return None
    days = [fr(v) for d, v in sorted(daily.items()) if d[:7] in months]
    s = sorted(m[x] for x in months)
    last_month = months[-1]
    from calendar import monthrange
    close = fr(daily[f"{last_month}-{monthrange(int(last_month[:4]), int(last_month[5:]))[1]:02d}"])
    return {"M1_mean_of_monthly_a1": sum(m[x] for x in months) / 6, "D_day_weighted": sum(days) / len(days),
            "M3_last_month": m[months[-1]], "M4_first_month": m[months[0]], "M5_median_of_months": (s[2] + s[3]) / 2,
            "M6_last_day_close": close}


def half_year_sensitivity(daily: dict, first="2010-H2", last="2026-H1") -> dict:
    """Deviation of each alternative from M1 over all complete half-years of one price series."""
    devs, counts = {}, 0
    for y in range(int(first[:4]), int(last[:4]) + 1):
        for h in (1, 2):
            half = f"{y}-H{h}"
            if not (first <= half <= last):
                continue
            r = half_year_methods(daily, half)
            if r is None:
                continue
            counts += 1
            for k, v in r.items():
                if k != "M1_mean_of_monthly_a1":
                    devs.setdefault(k, {})[half] = v / r["M1_mean_of_monthly_a1"] - 1
    return {"n_half_years": counts, "methods": {k: h10.dev_summary(v) for k, v in devs.items()}}


# ------------------------------------------------------------------ real-data run (GitHub Actions only)
def _prov(registry) -> dict:
    out = {}
    for r in registry:
        if r.name.startswith("cdx"):
            continue
        if r.name in out and out[r.name]["bytes"] >= r.bytes:
            continue  # a retried or failed attempt never replaces the run that actually delivered bytes
        out[r.name] = {"url": r.url, "acquired_at_utc": r.t, "http": r.http, "pages": r.pages, "bytes": r.bytes,
                       "raw_sha256": r.h.hexdigest()}
    return out


def acquire():
    """Fetch the registered sources (BTC-02 / HIST-08 helpers). Returns (data, prov, notes, missing)."""
    from tools import btc_02_probe as P
    from tools import hist_08_btc_definition as B8
    registry, notes, missing = [], io.StringIO(), []

    class Recording(P.Run):
        def __init__(self, name, url):
            super().__init__(name, url)
            registry.append(self)
    P.Run = Recording
    data = {}
    with contextlib.redirect_stdout(notes):
        ecb = P.fetch_ecb()
        bsu, vol_u = P.fetch_bitstamp("btcusd", "USD")
        bse, vol_e = P.fetch_bitstamp("btceur", "EUR")
        mg = B8.load_archive(P, "mtgoxUSD")
        kr = B8.load_archive(P, "krakenEUR")
    for key, val in (("ecb", ecb), ("bitstamp_usd", bsu), ("bitstamp_eur", bse)):
        if val is None:
            missing.append(key)
    data["ecb"] = ecb.as_dict() if ecb else None
    data["bitstamp_usd"], data["bitstamp_eur"] = (bsu.as_dict() if bsu else None), (bse.as_dict() if bse else None)
    data["vol_usd"], data["vol_eur"] = vol_u, vol_e
    data["mtgox_usd"] = B8.DAILY.get("mtgoxUSD") if mg else None
    data["kraken_eur"] = B8.DAILY.get("krakenEUR") if kr else None
    data["archive_rows"] = {"mtgox": mg, "kraken": kr}
    for key in ("mtgox_usd", "kraken_eur"):
        if data[key] is None:
            missing.append(key)
    return data, _prov(registry), notes.getvalue(), missing


def sha_for(prov: dict, *needles) -> str:
    for name, p in prov.items():
        if all(n.lower() in name.lower() for n in needles):
            return p["raw_sha256"]
    return hashlib.sha256(b"unavailable").hexdigest()


def run(args):  # noqa: C901
    from tools import btc_02_probe as P  # noqa: F401  (import check)
    from tools import hist_08_btc_definition as B8
    data, prov, notes, missing = acquire()
    R = {"caveat": "research only; PROPOSED methods; nothing approved or published; rights UNVERIFIED; no raw data stored",
         "method_id": METHOD_ID, "missing_sources": missing,
         "source_notes": [ln[:260] for ln in notes.splitlines() if ln.strip()][:40], "provenance": prov}
    if any(k in missing for k in ("ecb", "bitstamp_usd", "bitstamp_eur")):
        R["status"] = "INCOMPLETE"
        return R
    acquired_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    R["acquired_at_utc"] = acquired_at
    q = quality_months(data["bitstamp_usd"], data["vol_usd"], data["bitstamp_eur"])
    R["quality"] = {"liquid_start": q["liquid_start"], "q2_months": sum(v == "Q2" for v in q["bitstamp_usd"].values()),
                    "q3_usd_months": sum(v == "Q3" for v in q["bitstamp_usd"].values()),
                    "q1_months": sum(v == "Q1" for v in q["bitstamp_eur"].values()),
                    "q3_eur_months": sum(v == "Q3" for v in q["bitstamp_eur"].values()),
                    "early_notional_usd": {m: f"{float(v):.0f}" for m, v in sorted(q["notional_by_month"].items())
                                           if "2011-09" <= m <= "2013-06"}}
    sources = {"ecb": ecb_daily_series(data["ecb"], sha_for(prov, "ECB"), acquired_at),
               "bitstamp_usd": daily_btc_series("bitstamp_usd_daily", data["bitstamp_usd"], "USD", source_id="bitstamp_btcusd",
                                                raw_sha=sha_for(prov, "btcusd"), month_quality=q["bitstamp_usd"], acquired_at=acquired_at),
               "bitstamp_eur": daily_btc_series("bitstamp_eur_daily", data["bitstamp_eur"], "EUR", source_id="bitstamp_btceur",
                                                raw_sha=sha_for(prov, "btceur"), month_quality=q["bitstamp_eur"], acquired_at=acquired_at)}
    if data["mtgox_usd"]:
        sources["mtgox_usd"] = daily_btc_series("mtgox_usd_daily", data["mtgox_usd"], "USD", source_id="mtgox_btcusd_archive",
                                                raw_sha=sha_for(prov, "mtgox"), fixed_quality="Q3", acquired_at=acquired_at)
    if data["kraken_eur"]:
        sources["kraken_eur"] = daily_btc_series("kraken_eur_daily", data["kraken_eur"], "EUR", source_id="kraken_btceur_archive",
                                                 raw_sha=sha_for(prov, "kraken"), fixed_quality="Q3", acquired_at=acquired_at)

    csv_house = hb.cbs_2000_series(args.cbs_csv)

    def construct():
        btc_ = build_btc(sources)
        housing_ = build_housing(btc_, csv_house)
        allx = h10.all_series(btc_, housing_, csv_house)
        return btc_, housing_, allx, bundles(allx)

    btc, housing, allseries, bm = construct()
    again = construct()[-1]
    R["rebuild_identical"] = {n: hashlib.sha256(hb.bundle_bytes(hb.build_bundle(bm[n]))).hexdigest()
                              == hashlib.sha256(hb.bundle_bytes(hb.build_bundle(again[n]))).hexdigest() for n in bm}
    digests = write_bundles(bm, args.bundles_out) if args.bundles_out else {
        n: {"sha256": hashlib.sha256(hb.bundle_bytes(hb.build_bundle(s))).hexdigest(), "series": len(s)} for n, s in bm.items()}
    R["bundles"] = digests
    R["bundle_validation"] = {n: len(hm.validate_bundle(json.loads(hb.bundle_bytes(hb.build_bundle(s))))) for n, s in bm.items()}
    R["coverage"] = coverage_matrix(btc, housing, data)
    nvm = h9_nvm(args)
    R["nvm_overlap"] = nvm_overlap_report(nvm, {k: btc[v] for k, v in SEGMENT_SERIES.items() if v in btc})
    R["independent"] = independent_check(data, btc, housing, csv_house)
    R["sensitivity"] = sensitivity(data, btc, q, csv_house, B8)
    R["half_year_btc"] = {name: half_year_sensitivity(daily) for name, daily in
                          (("bitstamp_eur_native", data["bitstamp_eur"]), ("bitstamp_usd_usd", data["bitstamp_usd"]))}
    windows = source_windows({k: v for k, v in (("bitstamp_usd_daily", data["bitstamp_usd"]), ("bitstamp_eur_daily", data["bitstamp_eur"]),
                                                ("mtgox_usd_daily", data["mtgox_usd"]), ("kraken_eur_daily", data["kraken_eur"]),
                                                ("ecb_usd_per_eur_daily", data["ecb"])) if v})
    derived_hash = derived_values_sha256({**btc, **housing})
    pins = json.loads(Path(args.pins).read_text(encoding="utf-8")) if args.pins else None
    R["vintage_check"] = check_pins(windows, derived_hash, pins)
    R["pins_candidate"] = {"method_id": METHOD_ID, "pinned_on": acquired_at[:10], "sources": windows,
                           "derived": {"values_sha256": derived_hash, "cutoff": RESEARCH_CUTOFF}}
    R["hist10_ecb_pin_consistency"] = hist10_ecb_consistency(windows, args)
    R["manifest"] = {"method_id": METHOD_ID, "status": "PROPOSED research method; not accepted", "acquired_at_utc": acquired_at,
                     "provenance": prov, "source_windows": windows, "derived_values_sha256": derived_hash,
                     "bundle_sha256": {k: v["sha256"] for k, v in digests.items()}, "vintage_check": R["vintage_check"],
                     "quality_flags": {"BTC_Q1": "EUR-native, liquid (Bitstamp EUR, sustained from liquid_start)",
                                       "BTC_Q2": "USD-derived (C1), liquid", "BTC_Q3": "thin, early or archive-copy: research only"},
                     "note": "raw hashes identify the downloaded bytes of this run, not an archive of them; window hashes and the "
                             "derived values hash are the stable identity; no raw third-party data is stored"}
    if args.bundles_out:
        (Path(args.bundles_out) / "btc03_manifest.json").write_bytes(hm.canonical_json(R["manifest"]))
    R["status"] = "COMPLETE_RESEARCH" if not missing else "PARTIAL"
    return R


def h9_nvm(args):
    from tools import hist_09_bundle as h9
    d = Path(args.inputs)
    h9.verify_package(d)
    return h9.nvm_nlg_series(h9.read_nvm_csv(d), h9.NVM_CSV_SHA256)


def hist10_ecb_consistency(windows: dict, args) -> dict:
    """The ECB window must equal the HIST-10 pin (same source, same window): a cross-check between research phases."""
    if not args.hist10_pins:
        return {"status": "NOT_CHECKED"}
    pin = json.loads(Path(args.hist10_pins).read_text(encoding="utf-8"))["sources"]["ecb_usd_per_eur_daily"]
    cur = windows["ecb_usd_per_eur_daily"]
    return {"status": "EQUAL" if (pin["sha256"], pin["n"]) == (cur["sha256"], cur["n"]) else "DIFFERENT",
            "hist10_n": pin["n"], "btc03_n": cur["n"]}


def coverage_matrix(btc, housing, data) -> dict:
    out = {}
    for k in ("bitstamp_usd", "bitstamp_eur", "mtgox_usd", "kraken_eur", "ecb"):
        d = data.get(k)
        if d:
            days = sorted(d)
            gaps = H.missing_days(days)
            out[f"{k}_daily"] = {"first": days[0], "last": days[-1], "n": len(days), "calendar_gaps": len(gaps),
                                 "first_gaps": gaps[:5]}
    for name, s in list(btc.items()) + list(housing.items()):
        if s.layer == "source":
            continue
        vals = [p for p in s.points if p.value is not None]
        out[name] = {"first": vals[0].period if vals else None, "last": vals[-1].period if vals else None, "n": len(vals),
                     "n_null": len(s.points) - len(vals), "null_sample": [p.period for p in s.points if p.value is None][:6]}
    return out


def independent_check(data, btc, housing, house: hm.Series) -> dict:
    """Exact Fraction recomputation from the raw daily dicts for representative months, vs the model values."""
    hv = {o.period: fr(o.value) for o in house.observations}
    plan = (("2010-08", "mtgox_usd_derived", data.get("mtgox_usd"), True), ("2013-04", "bitstamp_usd_derived", data["bitstamp_usd"], True),
            ("2016-05", "bitstamp_usd_derived", data["bitstamp_usd"], True), ("2016-05", "bitstamp_eur_native", data["bitstamp_eur"], False),
            ("2026-08", "bitstamp_eur_native", data["bitstamp_eur"], False), ("2026-08", "bitstamp_usd_derived", data["bitstamp_usd"], True))
    out = {}
    for month, seg, daily, derived in plan:
        if not daily or month not in hv:
            out[f"{month} {seg}"] = {"status": "NOT_AVAILABLE"}
            continue
        exact = c1_months(daily, data["ecb"]).get(month) if derived else a1_months(daily).get(month)
        if exact is None:
            out[f"{month} {seg}"] = {"status": "NO_COMPLETE_MONTH"}
            continue
        btc_ex, sat_ex = per_house(hv[month], exact)
        mb = {p.period: p.value for p in housing.get(f"cbs_btc_per_house_{seg}").points} if f"cbs_btc_per_house_{seg}" in housing else {}
        ms = {p.period: p.value for p in housing.get(f"cbs_sats_per_house_{seg}").points} if f"cbs_sats_per_house_{seg}" in housing else {}
        out[f"{month} {seg}"] = {"btc_eur": f"{float(exact):.4f}", "house_eur": str(hv[month]), "btc_per_house_exact": f"{float(btc_ex):.10f}",
                                 "sats_per_house_exact": f"{float(sat_ex):.4f}",
                                 "btc_rel_diff": f"{float(abs(fr(mb[month]) / btc_ex - 1)):.3e}" if mb.get(month) is not None else None,
                                 "sats_rel_diff": f"{float(abs(fr(ms[month]) / sat_ex - 1)):.3e}" if ms.get(month) is not None else None}
    return out


def sensitivity(data, btc, q, house: hm.Series, B8) -> dict:
    """Quantified methodology sensitivity, transitions and cross-source comparisons (percent strings)."""
    S = {}
    bsu, bse, ecb = data["bitstamp_usd"], data["bitstamp_eur"], data["ecb"]
    S["a2_month_end_vs_a1"] = {"bitstamp_usd": rel_stats(a2_months(bsu), a1_months(bsu)), "bitstamp_eur": rel_stats(a2_months(bse), a1_months(bse))}
    usd_series = H.DailySeries("bitstamp_usd", "USD", tuple(sorted(bsu.items())))
    ecb_series = H.DailySeries("ecb", "USD", tuple(sorted(ecb.items())))
    native = a1_months(bse)
    S["usd_to_eur_vs_native_bitstamp_eur"] = {c: rel_stats({m: v["value"] for m, v in B8.convert_usd_to_eur(usd_series, ecb_series, c).items()}, native)
                                              for c in B8.CONVERSIONS}
    c1 = c1_months(bsu, ecb)
    first12 = {m: v for m, v in c1.items() if "2016-05" <= m <= "2017-04"}
    S["transition_2016_05_c1_vs_native_first_12_months"] = rel_stats(first12, native)
    if data.get("kraken_eur"):
        kr = a1_months(data["kraken_eur"])
        S["q2_cross_validation_c1_vs_kraken_eur_2014_02_2016_04"] = rel_stats({m: v for m, v in c1.items() if "2014-02" <= m <= "2016-04"}, kr)
        S["cross_venue_kraken_eur_vs_bitstamp_eur_native"] = rel_stats(kr, native)
    if data.get("mtgox_usd"):
        mg = a1_months(data["mtgox_usd"])
        S["transition_mtgox_vs_bitstamp_usd_shared_months"] = rel_stats(mg, a1_months(bsu))
        S["mtgox_first_last_complete"] = [min(mg), max(mg), len(mg)]
        rows = data["archive_rows"]["mtgox"]
        if rows:
            S["mtgox_trade_definitions_vs_a1"] = {k: rel_stats({m: r[k] for m, r in rows.items() if r["complete"] and r.get(k) is not None},
                                                               {m: r["a1"] for m, r in rows.items() if r["complete"]}) for k in ("a2", "a3", "a3v", "a4")}
        early = {m: f"{float(v):.0f}" for m, v in sorted(q["notional_by_month"].items()) if "2011-09" <= m <= "2013-03"}
        S["early_usd_notional_below_threshold_months"] = len([1 for v in early.values() if Decimal(v) < LIQUID_USD_NOTIONAL])
    if data["archive_rows"].get("kraken"):
        rows = data["archive_rows"]["kraken"]
        S["kraken_trade_definitions_vs_a1"] = {k: rel_stats({m: r[k] for m, r in rows.items() if r["complete"] and r.get(k) is not None},
                                                            {m: r["a1"] for m, r in rows.items() if r["complete"]}) for k in ("a2", "a3", "a3v", "a4")}
    hv = {o.period: fr(o.value) for o in house.observations}
    eff = {}
    for label, other, ref in (("a2_vs_a1_bitstamp_eur", a2_months(bse), native), ("c1_vs_native", c1, native)):
        ms = sorted(set(other) & set(ref) & set(hv))
        if ms:
            d = {m: abs(per_house(hv[m], other[m])[1] - per_house(hv[m], ref[m])[1]) / per_house(hv[m], ref[m])[1] for m in ms}
            eff[label] = h10.dev_summary(d)
    S["sats_per_house_effect"] = eff
    return S


def main(argv=None):
    ap = argparse.ArgumentParser(description="BTC-03 housing in BTC and satoshis (research only)")
    ap.add_argument("--inputs", help="pinned HIST-09 inputs directory (for the NVM overlap check)")
    ap.add_argument("--cbs-csv", help="committed CBS csv (read only)")
    ap.add_argument("--pins", help="pinned source windows and derived values hash (hashes only)")
    ap.add_argument("--hist10-pins", help="HIST-10 pin file, for the ECB window cross-check")
    ap.add_argument("--summary-out")
    ap.add_argument("--bundles-out")
    ap.add_argument("--print-summary")
    ap.add_argument("--keys", default="")
    a = ap.parse_args(argv)
    if a.print_summary:
        S = json.loads(Path(a.print_summary).read_text())
        for key in [k for k in a.keys.split(",") if k]:
            node = S
            for part in key.split("."):
                node = node.get(part) if isinstance(node, dict) else None
            print("SUMMARY", key, json.dumps(node, sort_keys=True, default=str)[:7000])
        return 0
    if not (a.summary_out and a.inputs and a.cbs_csv):
        ap.error("--summary-out, --inputs and --cbs-csv are required")
    out = Path(a.summary_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        R = run(a)
    except (hm.ModelError, Btc03Error, H.HistoryError) as exc:
        out.write_text(json.dumps({"status": "FAILED", "error": f"{type(exc).__name__}: {str(exc)[:400]}"}, indent=1) + "\n")
        print("DEFECT", type(exc).__name__, str(exc)[:400])
        return 1
    out.write_text(json.dumps(R, indent=1, sort_keys=True, default=str) + "\n")
    print("STATUS", R["status"], "missing", R["missing_sources"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
