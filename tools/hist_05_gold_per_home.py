"""HIST-05 research candidate - not approved: gram gold per average Dutch home, 1995-01..1999-12 (60 months).

Internal, reproducible research calculation. Owner-approved CANDIDATE method, not final, not approved for
publication. Nothing is written to the repository; the CI artifact (14 days) may hold the derived 60-row table.

Inputs
  house   CBS 85773NED monthly AVERAGE PURCHASE PRICE of existing owner-occupied dwellings (price LEVEL, NOT the
          price index), unit euro also for 1995-1998 (retrospective euro denomination). Fetched from the CBS OData
          API (DataProperties + TypedDataSet via tools.hist_05_cbs_kadaster.fetch_status); the measure is identified
          from the metadata (kind PRICE_LEVEL, title 'gemiddelde verkoopprijs', unit euro), sha256 of both bodies is
          recorded. The 60 values are cross-checked offline against the pinned fixture data/fixtures/cbs-1995-1999-i1.json.
  gold    HIST-04 research table (tools.hist_04_gold_nlg.collect, unchanged): 1995-01..1998-12 World Bank USD/oz x
          monthly mean NLG per USD (Fed H.10 noon buying rates) = gold NLG/oz, historical EUR-equivalent = NLG / 2.20371;
          1999-01..1999-12 World Bank USD/oz / ECB monthly mean USD per EUR = gold EUR/oz.
  const   troy ounce = 31.1034768 g; EUR/NLG = 2.20371 (Council Regulation (EC) No 2866/98).

Formula (Decimal, 34 digits): grams per home = house_price_local x 31.1034768 / gold_price_per_troy_oz_in_the_SAME_currency
  EUR route: house_price_eur x 31.1034768 / gold_eur_equiv_per_oz   (1995-1998: EUR-equivalent, 1999: market EUR)
  NLG route: house_price_nlg_equiv (= house_eur x 2.20371, DERIVED, CBS gives euro) x 31.1034768 / gold_nlg_per_oz
             (1995-1998: market-based NLG gold, 1999: gold_eur x 2.20371 = derived fixed-rate conversion, not a market rate)
Both routes are algebraically identical up to rounding; their comparison is a unit/arithmetic consistency check, NOT
an independent validation. Currency and unit consistency is enforced in code (Price carries currency and per-unit;
grams_per_home raises UnitMismatchError on any mismatch).

No interpolation, forward-fill or back-fill: a month missing any input has null outputs and an INCOMPLETE label.
Exit semantics (hist): unreachable sources -> status INCOMPLETE/PARTIAL with explicit missing_sources, exit 0;
real defects (duplicates, invalid values, unit mismatch, structural source failures) -> exit 1.
Methodology: research candidate - not approved. rights_status: UNVERIFIED. Publication: NOT APPROVED.
"""
import argparse
import csv
import hashlib
import io
import json
import sys
from collections import Counter
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path
from typing import NamedTuple

from tools import hist_03_worldbank_validate as wbv
from tools import hist_04_fx as fx
from tools import hist_04_gold_nlg as g
from tools import hist_04_gold_outliers as go
from tools import hist_04_nlg_sources as ns
from tools import hist_05_cbs_kadaster as ck
from tools import hist_03_second_source as ss
from tools.hist_02_coverage import month_range

LABEL = "research candidate - not approved"
METHODOLOGY = "research candidate - not approved"
RIGHTS = "UNVERIFIED"
PUBLICATION = "NOT APPROVED (research candidate - not approved; not approved for publication)"
PREC = 34
WINDOW_START, WINDOW_END = "1995-01", "1999-12"
EXPECTED_MONTHS = 60
LAST_NLG_MONTH = "1998-12"
TROY_OZ_G = Decimal("31.1034768")
NLG_PER_EUR = Decimal("2.20371")
if NLG_PER_EUR != fx.NLG_PER_EUR or NLG_PER_EUR != g.NLG_PER_EUR:  # constants must agree with HIST-04
    raise ImportError("EUR/NLG constant differs from HIST-04")
ROUTE_TOLERANCE = Decimal("1E-25")  # |relative route discrepancy| bound at 34-digit Decimal precision
Q4 = Decimal("0.0001")  # display rounding of the artifact
CBS_TABLE = "85773NED"
CBS_PROPS_ID, CBS_DATA_ID = f"cbs3-{CBS_TABLE}-props", f"cbs3-{CBS_TABLE}-data"
CBS_EXPECTED_KEY = "GemiddeldeVerkoopprijs_7"  # documented in HIST_05_CBS_KADASTER.md; a different key is reported, not trusted
FIXTURE_PATH = ck.FIXTURE_PATH
CBS_ONLY_IDS = (CBS_PROPS_ID, CBS_DATA_ID)
EUR, NLG = "EUR", "NLG"
HOME, TROY_OZ = "home", "troy_oz"

FIELD_NOTES = {
    "house_price_eur": "CBS 85773NED average purchase price of existing dwellings, euro (also for 1995-1998: retrospective euro denomination)",
    "house_price_nlg_equiv": "DERIVED: house_price_eur x 2.20371; CBS gives euro, no NLG original was obtained",
    "gold_usd_oz": "World Bank Pink Sheet monthly gold, USD per troy ounce; whole USD before 2000 (rounding bound 0.5 USD)",
    "fx_applied": "1995-01..1998-12: arithmetic mean of available Fed H.10 daily noon buying rates NLG per USD; 1999: ECB monthly USD per EUR",
    "gold_eur_equiv_per_oz": "1995-1998: historical EUR-equivalent = gold_nlg_per_oz / 2.20371 (not a traded euro price); 1999: market EUR",
    "gold_nlg_per_oz": "1995-1998: usd_oz x NLG per USD; 1999: gold EUR x 2.20371 (DERIVED fixed-rate conversion, not a market rate)",
    "gold_price_local_currency": "gold price per troy oz in the native currency of the period (NLG until 1998-12, EUR from 1999-01)",
    "grams_per_home_eur_route": "house_price_eur x 31.1034768 / gold_eur_equiv_per_oz, rounded to 4 decimals (full precision internally)",
    "grams_per_home_nlg_route": "house_price_nlg_equiv x 31.1034768 / gold_nlg_per_oz, rounded to 4 decimals (full precision internally)",
    "route_discrepancy_rel": "(nlg_route - eur_route) / eur_route at 34-digit precision; algebraically ~0, an arithmetic/unit check only",
    "route_discrepancy_rel_4dp": "same relative difference computed from the 4-decimal display values",
    "wb_usd_rounding_bound_pct": "0.5 / usd_oz in percent when the World Bank value is a whole number; null otherwise",
}

CSV_FIELDS = ["period", "regime", "house_price_eur", "house_price_nlg_equiv", "gold_usd_oz", "fx_applied", "fx_applied_unit",
              "fx_obs_count", "fx_nd_count", "fx_nlg_per_eur_fixed", "gold_price_local_currency", "gold_price_local_currency_code",
              "gold_eur_equiv_per_oz", "gold_nlg_per_oz", "grams_per_home_eur_route", "grams_per_home_nlg_route",
              "route_discrepancy_rel", "route_discrepancy_rel_4dp", "quality_label", "cbs_status", "wb_usd_rounding_bound_pct",
              "outlier_flag", "house_source_url", "house_source_sha256", "usd_oz_source_url", "usd_oz_source_sha256",
              "fx_source_url", "fx_source_sha256", "methodology", "rights_status", "publication_status"]


class UnitMismatchError(fx.DataIntegrityError):
    """Currency or per-unit mismatch in the grams-per-home formula (hard)."""


class InputError(fx.DataIntegrityError):
    """Duplicate, invalid or out-of-contract input (hard)."""


class Price(NamedTuple):
    value: Decimal
    ccy: str  # EUR or NLG
    per: str  # HOME or TROY_OZ


def _price(value, ccy, per):
    if isinstance(value, bool) or not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
        raise InputError(f"INVALID_PRICE value={value!r}")
    if ccy not in (EUR, NLG) or per not in (HOME, TROY_OZ):
        raise UnitMismatchError(f"UNKNOWN_UNIT ccy={ccy!r} per={per!r}")
    return Price(value, ccy, per)


def grams_per_home(house, gold):
    """house x 31.1034768 / gold in the SAME currency. Raises UnitMismatchError on any currency/unit inconsistency."""
    if not isinstance(house, Price) or not isinstance(gold, Price):
        raise UnitMismatchError("UNTYPED_PRICE")
    _price(house.value, house.ccy, house.per)
    _price(gold.value, gold.ccy, gold.per)
    if house.per != HOME or gold.per != TROY_OZ:
        raise UnitMismatchError(f"PER_UNIT_MISMATCH house.per={house.per} gold.per={gold.per}")
    if house.ccy != gold.ccy:
        raise UnitMismatchError(f"CURRENCY_MISMATCH house={house.ccy} gold={gold.ccy}")
    with localcontext() as c:
        c.prec = PREC
        return house.value * TROY_OZ_G / gold.value


def eur_to_nlg(p):
    """DERIVED fixed-rate conversion EUR -> NLG (Reg. (EC) 2866/98); only EUR prices are accepted."""
    if p.ccy != EUR:
        raise UnitMismatchError(f"EUR_EXPECTED_GOT_{p.ccy}")
    with localcontext() as c:
        c.prec = PREC
        return _price(p.value * NLG_PER_EUR, NLG, p.per)


def nlg_to_eur(p):
    if p.ccy != NLG:
        raise UnitMismatchError(f"NLG_EXPECTED_GOT_{p.ccy}")
    with localcontext() as c:
        c.prec = PREC
        return _price(p.value / NLG_PER_EUR, EUR, p.per)


def q4(v):
    return None if v is None else v.quantize(Q4)


def _s(v):
    return None if v is None else format(v, "f")


def sci(v):
    return None if v is None else f"{v:.4E}"


def _dec(text):
    return None if text is None else Decimal(text)


# ----------------------------------------------------------------------------- house input
def normalize_house(points):
    """{period: Decimal|None} for the 60 window months. Accepts a dict or an iterable of (period, value) pairs.

    Hard errors: duplicate period, invalid period, non-Decimal/NaN/non-positive value. Absent or None stays None (never filled).
    Periods outside the window are ignored.
    """
    window = month_range(WINDOW_START, WINDOW_END)
    items = list(points.items()) if isinstance(points, dict) else list(points)
    seen, out = set(), {m: None for m in window}
    for period, value in items:
        if not isinstance(period, str) or len(period) != 7 or period[4] != "-" or not (period[:4] + period[5:]).isdigit():
            raise InputError(f"INVALID_PERIOD {period!r}")
        if period in seen:
            raise InputError(f"DUPLICATE_PERIOD {period}")
        seen.add(period)
        if period not in out:
            continue
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
            raise InputError(f"INVALID_HOUSE_PRICE {period} {value!r}")
        out[period] = value
    return out


def fetch_cbs_house(fetch=None):
    """Fetch DataProperties + TypedDataSet of 85773NED; return (house60 dict, info dict, missing list).

    Unreachable -> house all None, missing entries; structure/unit defects -> InputError/UnitMismatchError (hard)."""
    fetch = fetch or ck.fetch_status
    info, missing, raws = {"table_id": CBS_TABLE, "sources": {}}, [], {}
    for sid in CBS_ONLY_IDS:
        raw, entry = fetch(sid)
        info["sources"][sid] = {k: entry.get(k) for k in ("url", "status", "http_status", "bytes", "sha256", "error")}
        if raw is None:
            missing.append({"source_id": sid, "reason": f"HTTP_{entry['http_status']}" if entry.get("http_status") else "UNREACHABLE",
                            "detail": str(entry.get("error") or "")[:160]})
        else:
            raws[sid] = raw
    if len(raws) != len(CBS_ONLY_IDS):
        return normalize_house({}), info, missing
    try:
        props = ck.parse_props(ck.load_json(raws[CBS_PROPS_ID]))
        doc = ck.load_json(raws[CBS_DATA_ID])
        series, unsupported = ck.parse_typed(doc, props)
    except ck.Hist05Error as exc:
        raise InputError(f"CBS_{CBS_TABLE}: {exc}") from exc
    cands = [k for k, t in props["topics"].items()
             if t["kind"] == "PRICE_LEVEL" and "verkoopprijs" in t["title"].lower() and "gemiddelde" in t["title"].lower()]
    if len(cands) != 1:
        raise InputError(f"CBS_{CBS_TABLE}: AMBIGUOUS_OR_MISSING_AVERAGE_PRICE_MEASURE candidates={cands}")
    key, topic = cands[0], props["topics"][cands[0]]
    if topic["currency"] != EUR:
        raise UnitMismatchError(f"CBS_{CBS_TABLE}: UNIT_NOT_EURO key={key} unit={topic['unit']!r} currency={topic['currency']}")
    monthly = ck.single_series(series, key, "M")
    if monthly is None:
        raise InputError(f"CBS_{CBS_TABLE}: NO_SINGLE_NATIONAL_MONTHLY_SERIES key={key}")
    info.update({"measure_key": key, "measure_title": topic["title"], "measure_unit": topic["unit"], "measure_kind": topic["kind"],
                 "measure_key_matches_documented": key == CBS_EXPECTED_KEY, "monthly_observations_total": len(monthly),
                 "unsupported_period_codes": dict(sorted(unsupported.items())), "odata_next_link_present": "odata.nextLink" in doc})
    return normalize_house(monthly), info, missing


def fixture_crosscheck(house, fixture=None):
    """Offline equality of the 60 CBS values with the pinned fixture. Mismatch is a FLAG (source revision), not a repair."""
    try:
        fx_series = fixture if fixture is not None else ck.load_fixture(FIXTURE_PATH)
    except (OSError, ValueError, KeyError) as exc:
        return {"status": "FIXTURE_NOT_READABLE", "error": str(exc)[:160]}
    window = month_range(WINDOW_START, WINDOW_END)
    res = {"fixture_path": "fixtures/cbs-1995-1999-i1.json", "fixture_sha256": None,
           "fixture_months_in_window": sum(1 for m in window if m in fx_series)}
    try:
        res["fixture_sha256"] = hashlib.sha256(Path(FIXTURE_PATH).read_bytes()).hexdigest()
    except OSError:
        pass
    if not any(v is not None for v in house.values()):
        res["status"] = "NOT_PERFORMED_NO_CBS_VALUES"
        return res
    equal = [m for m in window if house[m] is not None and m in fx_series and house[m] == fx_series[m]]
    diff = [{"period": m, "cbs": _s(house[m]), "fixture": _s(fx_series.get(m))} for m in window
            if house[m] is not None and m in fx_series and house[m] != fx_series[m]]
    absent = [m for m in window if house[m] is None or m not in fx_series]
    res.update({"status": "EQUAL_60_OF_60" if len(equal) == EXPECTED_MONTHS else "DIFFERENCES_OR_GAPS",
                "equal_months": len(equal), "different": diff, "not_comparable_months": absent})
    return res


# ----------------------------------------------------------------------------- table
def _gold_prices(period, gr):
    """(gold_nlg Price|None, gold_eur_equiv Price|None) from one HIST-04 row. 1999: NLG is the derived conversion."""
    if gr is None:
        return None, None
    if period <= LAST_NLG_MONTH:
        if gr.get("regime") != "NLG_FED_H10_MEAN":
            raise UnitMismatchError(f"{period}: REGIME_MISMATCH {gr.get('regime')}")
        if gr["_gold_nlg"] is None:
            return None, None
        gnlg = _price(gr["_gold_nlg"], NLG, TROY_OZ)
        geur = _price(_dec(gr["hist_eur_equivalent_oz"]), EUR, TROY_OZ)
        return gnlg, geur
    if gr.get("regime") != "EUR_ECB_MONTHLY":
        raise UnitMismatchError(f"{period}: REGIME_MISMATCH {gr.get('regime')}")
    if gr["_gold_eur"] is None:
        return None, None
    geur = _price(gr["_gold_eur"], EUR, TROY_OZ)
    return eur_to_nlg(geur), geur


def quality(house, gr, computed):
    missing = []
    if house is None:
        missing.append("NO_HOUSE_PRICE")
    gl = (gr or {}).get("quality_label", "NO_USD_OZ+NO_FX_OBSERVATIONS")
    toks = gl.split("+")
    missing += [t for t in toks if t in ("NO_USD_OZ", "NO_FX_OBSERVATIONS")]
    if not computed and not missing:
        missing.append("NO_GOLD")
    if missing:
        return "INCOMPLETE:" + "+".join(missing)
    return "INCOMPLETE_FEW_OBS" if "INCOMPLETE_FEW_OBS" in toks else "OK"


def compute_month(period, house_eur, gr):
    """Both routes for one month with full-precision Decimal; None outputs when any input is missing."""
    gnlg, geur = _gold_prices(period, gr)
    res = {"gold_nlg": gnlg, "gold_eur": geur, "house_eur": None, "house_nlg": None, "eur": None, "nlg": None, "rel": None,
           "eur4": None, "nlg4": None, "rel4": None}
    if house_eur is None or gnlg is None or geur is None:
        return res
    h_eur = _price(house_eur, EUR, HOME)
    h_nlg = eur_to_nlg(h_eur)
    res["house_eur"], res["house_nlg"] = h_eur, h_nlg
    res["eur"] = grams_per_home(h_eur, geur)
    res["nlg"] = grams_per_home(h_nlg, gnlg)
    with localcontext() as c:
        c.prec = PREC
        res["rel"] = (res["nlg"] - res["eur"]) / res["eur"]
        res["eur4"], res["nlg4"] = q4(res["eur"]), q4(res["nlg"])
        res["rel4"] = (res["nlg4"] - res["eur4"]) / res["eur4"]
    return res


def build_table(house, gold_rows, house_info=None):
    """60 window rows (public dicts) plus the internal computations. Exactly 60 rows by construction; validate_table asserts it."""
    window = month_range(WINDOW_START, WINDOW_END)
    house = normalize_house(house)
    hsrc = (house_info or {}).get("sources", {}).get(CBS_DATA_ID, {})
    rows, calc = [], {}
    for m in window:
        gr = gold_rows.get(m)
        r = compute_month(m, house[m], gr)
        calc[m] = r
        usd = gr["_usd"] if gr else None
        native_nlg = m <= LAST_NLG_MONTH
        if gr is None:
            fx_val, fx_unit = None, None
        elif native_nlg:
            fx_val, fx_unit = gr["_fx_nlg"], "NLG per USD (arithmetic mean of Fed H.10 daily noon buying rates, New York)"
        else:
            fx_val, fx_unit = gr["_fx_eur"], "USD per EUR (ECB EXR M.USD.EUR.SP00.A monthly average)"
        computed = r["eur"] is not None
        bound = None
        if usd is not None and usd == usd.to_integral_value():
            bound = g.pct6(Decimal("0.5") / usd)
        local = r["gold_nlg"] if native_nlg else r["gold_eur"]
        rows.append({
            "period": m, "regime": (gr or {}).get("regime"),
            "house_price_eur": _s(house[m]), "house_price_nlg_equiv": _s(r["house_nlg"].value) if r["house_nlg"] else None,
            "gold_usd_oz": _s(usd), "fx_applied": _s(fx_val), "fx_applied_unit": fx_unit,
            "fx_obs_count": (gr or {}).get("fx_obs_count"), "fx_nd_count": (gr or {}).get("fx_nd_count"),
            "fx_nlg_per_eur_fixed": str(NLG_PER_EUR),
            "gold_price_local_currency": _s(q4(local.value)) if local else None,
            "gold_price_local_currency_code": (NLG if native_nlg else EUR) if local else None,
            "gold_eur_equiv_per_oz": _s(q4(r["gold_eur"].value)) if r["gold_eur"] else None,
            "gold_nlg_per_oz": _s(q4(r["gold_nlg"].value)) if r["gold_nlg"] else None,
            "grams_per_home_eur_route": _s(r["eur4"]), "grams_per_home_nlg_route": _s(r["nlg4"]),
            "route_discrepancy_rel": sci(r["rel"]), "route_discrepancy_rel_4dp": sci(r["rel4"]),
            "quality_label": quality(house[m], gr, computed),
            "cbs_status": "CBS_OBSERVED" if house[m] is not None else "CBS_MISSING",
            "wb_usd_rounding_bound_pct": bound,
            "outlier_flag": (gr or {}).get("outlier_flag"),
            "house_source_url": hsrc.get("url") if house[m] is not None else None,
            "house_source_sha256": hsrc.get("sha256") if house[m] is not None else None,
            "usd_oz_source_url": (gr or {}).get("usd_oz_source_url"), "usd_oz_source_sha256": (gr or {}).get("usd_oz_source_sha256"),
            "fx_source_url": (gr or {}).get("fx_source_url"), "fx_source_sha256": (gr or {}).get("fx_source_sha256"),
            "methodology": METHODOLOGY, "rights_status": RIGHTS, "publication_status": PUBLICATION})
    validate_table(rows)
    return rows, calc


def validate_table(rows):
    """Acceptance: exactly 60 rows, unique, consecutive 1995-01..1999-12, labels present. Hard error otherwise."""
    periods = [r["period"] for r in rows]
    if len(periods) != EXPECTED_MONTHS:
        raise InputError(f"ROW_COUNT_{len(periods)}_NOT_{EXPECTED_MONTHS}")
    if len(set(periods)) != len(periods):
        raise InputError("DUPLICATE_PERIODS")
    if periods != month_range(WINDOW_START, WINDOW_END):
        raise InputError("PERIODS_NOT_CONSECUTIVE_1995_01_1999_12")
    for r in rows:
        if r["methodology"] != METHODOLOGY or r["rights_status"] != RIGHTS or not r["publication_status"].startswith("NOT APPROVED"):
            raise InputError(f"STATUS_FIELDS_MISSING {r['period']}")
        if r["grams_per_home_eur_route"] is None and not r["quality_label"].startswith("INCOMPLETE:"):
            raise InputError(f"NULL_WITHOUT_INCOMPLETE_LABEL {r['period']}")
    return True


# ----------------------------------------------------------------------------- analyses
def _pct_change(a, b):
    with localcontext() as c:
        c.prec = PREC
        return b / a - 1


def route_report(calc):
    done = {m: c for m, c in calc.items() if c["eur"] is not None}
    if not done:
        return {"months_compared": 0, "status": "NOT_COMPUTABLE"}
    worst = max(done, key=lambda m: abs(done[m]["rel"]))
    worst4 = max(done, key=lambda m: abs(done[m]["rel4"]))
    differ4 = [m for m, c in done.items() if c["eur4"] != c["nlg4"]]
    max_full = abs(done[worst]["rel"])
    return {"months_compared": len(done), "tolerance_full_precision": sci(ROUTE_TOLERANCE),
            "max_abs_rel_full_precision": sci(max_full), "max_month_full_precision": worst,
            "within_tolerance": max_full <= ROUTE_TOLERANCE,
            "max_abs_rel_from_4dp_display_values": sci(abs(done[worst4]["rel4"])), "max_month_4dp": worst4,
            "months_where_4dp_values_differ": differ4, "months_4dp_differ_count": len(differ4),
            "max_abs_diff_4dp_grams": _s(max(abs(c["nlg4"] - c["eur4"]) for c in done.values())),
            "reading": ("the routes are algebraically identical (house x 2.20371 x oz / (gold_nlg) = house x oz / (gold_nlg / 2.20371)); "
                        "full-precision differences are Decimal rounding (~1E-33). Rounding to 4 decimals matters only where the exact "
                        "value lies within ~1E-33 relative of a rounding boundary; the count of months where the two displayed values "
                        "differ is given above. This is an arithmetic and unit check, not an independent validation.")}


def yearly(calc):
    out = {}
    for y in range(1995, 2000):
        ms = [m for m in month_range(f"{y}-01", f"{y}-12") if calc[m]["eur"] is not None]
        e = {"months_with_value": len(ms), "complete_year": len(ms) == 12}
        if ms:
            e["mean_grams_per_home_eur_route"] = _s(q4(g.mean_dec([calc[m]["eur"] for m in ms])))
            e["mean_house_price_eur"] = _s(q4(g.mean_dec([calc[m]["house_eur"].value for m in ms])))
            e["mean_gold_eur_equiv_per_oz"] = _s(q4(g.mean_dec([calc[m]["gold_eur"].value for m in ms])))
        out[str(y)] = e
    return out


def development(calc, yrs):
    d = {}
    a, b = yrs["1995"], yrs["1999"]
    if a["months_with_value"] and b["months_with_value"]:
        ma, mb = Decimal(a["mean_grams_per_home_eur_route"]), Decimal(b["mean_grams_per_home_eur_route"])
        d["mean_1995_to_mean_1999"] = {"grams_1995": a["mean_grams_per_home_eur_route"], "grams_1999": b["mean_grams_per_home_eur_route"],
                                        "change_pct": g.pct6(_pct_change(ma, mb)), "months_1995": a["months_with_value"],
                                        "months_1999": b["months_with_value"],
                                        "complete_years": a["complete_year"] and b["complete_year"]}
        d["house_price_eur_mean_change_pct"] = g.pct6(_pct_change(Decimal(a["mean_house_price_eur"]), Decimal(b["mean_house_price_eur"])))
        d["gold_eur_equiv_mean_change_pct"] = g.pct6(_pct_change(Decimal(a["mean_gold_eur_equiv_per_oz"]), Decimal(b["mean_gold_eur_equiv_per_oz"])))
    for lab, p0, p1 in (("1995-01_to_1999-12", "1995-01", "1999-12"), ("1995-12_to_1999-12", "1995-12", "1999-12")):
        if calc[p0]["eur"] is not None and calc[p1]["eur"] is not None:
            d[lab] = {"grams_start": _s(calc[p0]["eur4"]), "grams_end": _s(calc[p1]["eur4"]),
                      "change_pct": g.pct6(_pct_change(calc[p0]["eur"], calc[p1]["eur"]))}
    return d


def extremes(calc):
    done = {m: c["eur"] for m, c in calc.items() if c["eur"] is not None}
    if not done:
        return {"status": "NOT_COMPUTABLE"}
    first, last = min(done), max(done)
    lo, hi = min(done, key=done.get), max(done, key=done.get)
    return {"first": {"period": first, "grams_per_home_eur_route": _s(q4(done[first]))},
            "last": {"period": last, "grams_per_home_eur_route": _s(q4(done[last]))},
            "min": {"period": lo, "grams_per_home_eur_route": _s(q4(done[lo]))},
            "max": {"period": hi, "grams_per_home_eur_route": _s(q4(done[hi]))}}


def transition(calc, gold_rows):
    """1998-12 -> 1999-01: step of grams per home versus its components (house price, gold in EUR terms)."""
    a, b = calc["1998-12"], calc["1999-01"]
    if a["eur"] is None or b["eur"] is None:
        return {"status": "NOT_COMPUTABLE", "reason": "a month of the pair has null output"}
    with localcontext() as c:
        c.prec = PREC
        h = b["house_eur"].value / a["house_eur"].value - 1
        gd = b["gold_eur"].value / a["gold_eur"].value - 1
        gr = b["eur"] / a["eur"] - 1
        resid = abs((1 + gr) - (1 + h) / (1 + gd))
        lh, lg, lgr = (1 + h).ln(), (1 + gd).ln(), (1 + gr).ln()
        r98, r99 = gold_rows["1998-12"], gold_rows["1999-01"]
        usd = r99["_usd"] / r98["_usd"] - 1
        implied98 = fx.implied_usd_per_eur(r98["_fx_nlg"])
        fxc = r99["_fx_eur"] / implied98 - 1
        nlg_gr = b["nlg"] / a["nlg"] - 1
    driver = "gold (EUR terms)" if abs(lg) > abs(lh) else "house price"
    return {"status": "COMPUTED", "grams_per_home_1998_12": _s(a["eur4"]), "grams_per_home_1999_01": _s(b["eur4"]),
            "grams_step_pct": g.pct6(gr), "grams_step_pct_nlg_route": g.pct6(nlg_gr),
            "house_price_eur_1998_12": _s(a["house_eur"].value), "house_price_eur_1999_01": _s(b["house_eur"].value),
            "house_price_step_pct": g.pct6(h),
            "gold_eur_per_oz_1998_12_equiv": _s(q4(a["gold_eur"].value)), "gold_eur_per_oz_1999_01": _s(q4(b["gold_eur"].value)),
            "gold_eur_step_pct": g.pct6(gd),
            "gold_components": {"wb_usd_step_pct": g.pct6(usd), "usd_per_eur_step_pct": g.pct6(fxc),
                                 "implied_usd_per_eur_1998_12": _s(implied98.quantize(Decimal("0.00000001"))),
                                 "ecb_usd_per_eur_1999_01": _s(r99["_fx_eur"])},
            "identity": "(1+grams_step) = (1+house_step)/(1+gold_eur_step); residual " + sci(resid),
            "ln_decomposition": {"ln_grams_step": _s(lgr.quantize(Decimal("0.000001"))), "ln_house_step": _s(lh.quantize(Decimal("0.000001"))),
                                  "minus_ln_gold_eur_step": _s((-lg).quantize(Decimal("0.000001")))},
            "larger_component": driver,
            "reading": ("numbers only: the step of grams per home equals the house-price step divided by the gold step in EUR terms; "
                        "the gold step itself combines the USD gold move and the change from the Fed-mean-implied USD/EUR to the ECB "
                        "monthly average; a definitional share of that FX step is not isolated")}


def definitional_breaks():
    return [
        "Gold FX source: Fed H.10 noon buying rates New York (NLG per USD, arithmetic mean of available daily observations) until 1998-12; "
        "ECB EXR monthly mean USD per EUR from 1999-01 (different source, aggregation and quote direction); see HIST-04 transition numbers",
        "Currency: CBS publishes euro prices also for 1995-1998 (retrospective euro denomination; NLG originals not obtained); the NLG "
        "house price is DERIVED with the fixed rate 2.20371, and the 1999 NLG gold is a derived fixed-rate conversion, not a market rate",
        "Gold EUR 1995-1998 is a historical EUR-equivalent (NLG / 2.20371), not a traded euro price; from 1999 it is a market euro price",
        "World Bank gold is whole USD per oz before 2000: rounding bound 0.5 USD (up to ~0.45% of a monthly value)",
        "House price is a compositional monthly average purchase price (CBS, Kadaster transactions), not a quality-adjusted index; "
        "monthly mean of transactions versus monthly mean of gold quotes are different time aggregations",
    ]


def outlier_note(rows):
    flagged = tuple(go.OUTLIER_MONTHS)
    in_window = [r["period"] for r in rows if r["outlier_flag"]]
    if set(flagged) != {"1980-12", "1983-07", "1985-03"}:
        raise InputError(f"OUTLIER_LIST_CHANGED {flagged}")
    return {"carried_flag_list_unverified_outlier": list(flagged), "flagged_months_inside_window": in_window,
            "note": "the three UNVERIFIED_OUTLIER months of HIST-04 (World Bank values kept) lie outside 1995-01..1999-12; no flagged month is in window"}


def coverage(rows, calc):
    labels = Counter(r["quality_label"] for r in rows)
    nlg = [r for r in rows if r["period"] <= LAST_NLG_MONTH]
    obs = sorted(r["fx_obs_count"] for r in nlg if r["fx_obs_count"] is not None)
    return {"rows": len(rows), "expected_rows": EXPECTED_MONTHS, "rows_exactly_60": len(rows) == EXPECTED_MONTHS,
            "months_with_house_price": sum(1 for r in rows if r["house_price_eur"] is not None),
            "months_with_gold_eur_equiv": sum(1 for c in calc.values() if c["gold_eur"] is not None),
            "months_with_gold_nlg": sum(1 for c in calc.values() if c["gold_nlg"] is not None),
            "months_with_grams_both_routes": sum(1 for c in calc.values() if c["eur"] is not None and c["nlg"] is not None),
            "months_null_output": sum(1 for c in calc.values() if c["eur"] is None),
            "quality_labels": dict(sorted(labels.items())),
            "fed_obs_per_month_min_median_max_1995_1998": [obs[0], obs[len(obs) // 2], obs[-1]] if obs else None,
            "fed_months_below_%d_obs" % g.FEW_OBS: sum(1 for o in obs if o < g.FEW_OBS),
            "fx_nd_days_total_1995_1998": sum(r["fx_nd_count"] or 0 for r in nlg)}


def independent_recompute(rows, house, gold_rows):
    """Exact Fraction check of both routes, not reusing grams_per_home / Price."""
    worst, checked = Fraction(0), 0
    oz, rate = Fraction(TROY_OZ_G), Fraction(NLG_PER_EUR)
    for r in rows:
        m = r["period"]
        gr = gold_rows.get(m)
        if r["grams_per_home_eur_route"] is None or gr is None:
            continue
        h = Fraction(house[m])
        if m <= LAST_NLG_MONTH:
            gnlg = Fraction(gr["_usd"]) * Fraction(gr["_fx_nlg"])
            exp_eur = h * oz / (gnlg / rate)
        else:
            geur = Fraction(gr["_gold_eur"])
            exp_eur = h * oz / geur
            gnlg = geur * rate
        exp_nlg = (h * rate) * oz / gnlg
        for got, exp in ((Fraction(Decimal(r["grams_per_home_eur_route"])), exp_eur), (Fraction(Decimal(r["grams_per_home_nlg_route"])), exp_nlg)):
            checked += 1
            worst = max(worst, abs(got - exp))
    # displayed values are 4-decimal roundings: the absolute deviation must not exceed half a unit of the 4th decimal
    return {"values_checked": checked, "max_abs_deviation_of_4dp_display_grams": f"{Decimal(worst.numerator) / Decimal(worst.denominator):.3E}",
            "pass": worst <= Fraction(1, 20000) + Fraction(1, 10 ** 20)}


# ----------------------------------------------------------------------------- output
def write_table(rows, meta, json_path, csv_path):
    doc = {"label": LABEL, "methodology": METHODOLOGY, "rights_status": RIGHTS, "publication_status": PUBLICATION,
           "field_notes": FIELD_NOTES, **meta, "rows": rows}
    if json_path:
        Path(json_path).parent.mkdir(parents=True, exist_ok=True)
        Path(json_path).write_text(json.dumps(doc, indent=1) + "\n")
    if csv_path:
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=CSV_FIELDS, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r[k]) for k in CSV_FIELDS})
        Path(csv_path).parent.mkdir(parents=True, exist_ok=True)
        Path(csv_path).write_text(buf.getvalue())


def run(workbook=None, cbs_fetch=None, acquire=fx.acquire):
    """Returns (summary, rows). Raises fx.DataIntegrityError subclasses / source errors on real defects."""
    s = {"status": "RUNNING", "label": LABEL, "methodology": METHODOLOGY, "rights_status": RIGHTS, "publication_status": PUBLICATION,
         "publication_authorized": False, "source_approved": False, "window": [WINDOW_START, WINDOW_END],
         "constants": {"troy_oz_grams": str(TROY_OZ_G), "nlg_per_eur": str(NLG_PER_EUR)}, "missing_sources": [], "flags": []}
    gs, grows = g.collect(workbook, acquire=acquire)
    house, cbs_info, cbs_missing = fetch_cbs_house(cbs_fetch)
    gold_rows = {m: grows[m] for m in month_range(WINDOW_START, WINDOW_END) if m in grows}
    s["missing_sources"] = list(gs["missing_sources"]) + cbs_missing
    s["flags"] = list(gs["flags"])
    rows, calc = build_table(house, gold_rows, cbs_info)
    s["gold_collect"] = {"status": gs["status"], "sources": gs["sources"], "checks": gs["checks"], "wb_precision": gs.get("wb_precision")}
    s["cbs"] = cbs_info
    s["cbs_fixture_crosscheck"] = fixture_crosscheck(house)
    if s["cbs_fixture_crosscheck"].get("status") == "DIFFERENCES_OR_GAPS":
        s["flags"].append("CBS_FIXTURE_DIFFERENCE: source revision or gap, human review required")
    if cbs_info.get("measure_key") and not cbs_info["measure_key_matches_documented"]:
        s["flags"].append(f"CBS_MEASURE_KEY_DIFFERS_FROM_DOCUMENTED: {cbs_info['measure_key']} (documented {CBS_EXPECTED_KEY})")
    s["coverage"] = coverage(rows, calc)
    s["results"] = {"extremes": extremes(calc), "yearly": yearly(calc)}
    s["results"]["development_1995_to_1999"] = development(calc, s["results"]["yearly"])
    s["route_discrepancy"] = route_report(calc)
    s["checks"] = {"independent_recompute": independent_recompute(rows, house, gold_rows)}
    if not s["checks"]["independent_recompute"]["pass"]:
        raise InputError("FORMULA_RECOMPUTE_MISMATCH")
    if s["route_discrepancy"].get("within_tolerance") is False:
        raise InputError("ROUTE_DISCREPANCY_ABOVE_TOLERANCE")
    s["outliers"] = outlier_note(rows)
    s["breaks"] = definitional_breaks()
    complete = s["coverage"]["months_null_output"] == 0
    s["transition_1998_12_to_1999_01"] = transition(calc, gold_rows)
    core_ids = set(g.CORE_IDS) | set(CBS_ONLY_IDS)
    core_missing = [m["source_id"] for m in s["missing_sources"] if m["source_id"] in core_ids]
    if core_missing or not complete:
        s["status"] = "INCOMPLETE"
    elif s["missing_sources"]:
        s["status"] = "PARTIAL"
    else:
        s["status"] = "COMPLETE_RESEARCH_CANDIDATE"
    return s, rows


def report_lines(s):
    L = ["REPORT status=%s label=%r missing=%s flags=%s" % (s["status"], LABEL, [m["source_id"] for m in s["missing_sources"]], s["flags"])]
    for key in ("coverage", "results", "route_discrepancy", "checks", "transition_1998_12_to_1999_01", "cbs", "cbs_fixture_crosscheck", "outliers"):
        L.append("REPORT %s=%s" % (key, json.dumps(s.get(key), sort_keys=True, default=str)))
    L.append("REPORT sources=" + json.dumps({k: {"sha256": v["sha256"], "bytes": v["bytes"]} for k, v in s["gold_collect"]["sources"].items()}, sort_keys=True))
    return L


def main(argv=None, cbs_fetch=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary-out", required=True)
    ap.add_argument("--table-json-out")
    ap.add_argument("--table-csv-out")
    ap.add_argument("--workbook", help="read this local World Bank workbook instead of downloading it")
    args = ap.parse_args(argv)
    out = Path(args.summary_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        s, rows = run(args.workbook, cbs_fetch)
    except (fx.DataIntegrityError, fx.FxError, ns.NlgSourceError, ss.SecondSourceError, wbv.ValidationError, ck.Hist05Error) as exc:
        out.write_text(json.dumps({"status": "FAILED", "label": LABEL, "error": str(exc)[:400]}, indent=2) + "\n")
        print("DEFECT", str(exc)[:400])
        return 1
    meta = {"status": s["status"], "missing_sources": s["missing_sources"], "flags": s["flags"], "constants": s["constants"],
            "formula": {"eur_route": "grams = house_price_eur x 31.1034768 / gold_eur_equiv_per_oz",
                        "nlg_route": "grams = (house_price_eur x 2.20371) x 31.1034768 / gold_nlg_per_oz"}}
    write_table(rows, meta, args.table_json_out, args.table_csv_out)
    out.write_text(json.dumps(s, indent=2, sort_keys=True, default=str) + "\n")
    print("\n".join(report_lines(s)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
