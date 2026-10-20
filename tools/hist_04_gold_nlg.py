"""HIST-04 research candidate - not approved: monthly gold in NLG (1975-01..1998-12) and EUR (1999).

Owner-approved RESEARCH CANDIDATE method (not final, not publication-approved):
  1975-01..1998-12  FX   = Federal Reserve H.10 daily noon buying rates New York, NLG per USD
                           (dat89_ne.txt + dat96_ne.txt); monthly FX = arithmetic mean of the available
                           daily observations of the calendar month ('ND' stays missing, no filling).
                    gold = World Bank monthly USD/oz x monthly mean NLG/USD            (Decimal)
                    hist_eur_equivalent_oz = gold_nlg_oz / 2.20371 (Council Reg. (EC) 2866/98):
                    a historical EUR-equivalent, NOT a contemporaneous traded euro price.
  1999-01..1999-12  FX   = ECB monthly EXR M.USD.EUR.SP00.A (USD per EUR); gold_eur_oz = USD/oz / USD per EUR.
                    The 2000+ production pipeline (etl/gold_monthly.py) is neither used nor touched.

Reuse (no second ETL stack): acquisition tools.hist_04_fx.acquire -> tools.hist_02_acquire.fetch
(https allowlist, size limit, sha256); World Bank workbook via tools.hist_03_worldbank_validate
(load_workbook / --workbook, validate, KNOWN_* hashes with hist-03 semantics: a hash difference is
FLAGGED as a source revision for human review, structural defects are hard); Fed parser and IMF
parser from tools.hist_04_nlg_sources; ECB parser and Decimal formulas from tools.hist_04_fx;
BoE monthly/daily parsers and outlier constants from tools.hist_03_second_source / hist_04_gold_outliers.

Exit semantics: unreachable sources (timeout, DNS, HTTP 4xx/5xx, empty) -> status PARTIAL/INCOMPLETE with
explicit missing_sources, exit 0. Real defects (wrong quote direction, duplicate dates, invalid values,
structural World Bank failure, integrity/allowlist violations) -> exit 1. A green run is not methodological
approval. Output is a derived research table for the CI artifact only; nothing is written to the repository.
"""
import argparse
import csv
import io
import json
import math
import sys
from collections import Counter
from datetime import date
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path

from tools import hist_02_acquire
from tools import hist_03_second_source as ss
from tools import hist_03_worldbank_validate as wbv
from tools import hist_04_fx as fx
from tools import hist_04_gold_outliers as go
from tools import hist_04_nlg_sources as ns
from tools.hist_02_coverage import month_range

LABEL = "research candidate - not approved"
PUBLICATION = "research candidate - not approved; not approved for publication"
PREC = 34
NLG_START, NLG_END = "1975-01", "1998-12"
EUR_START, EUR_END = "1999-01", "1999-12"
EXPECTED_NLG_MONTHS = 288
FEW_OBS = 15  # months with fewer observations are labelled INCOMPLETE_FEW_OBS (same cut as hist_04_nlg_sources)
NLG_PER_EUR = fx.NLG_PER_EUR
OUTLIER_FLAG = "UNVERIFIED_OUTLIER"
WB_ID = "world-bank-gold-history"
FED_IDS = ("fed-h10-dat89-ne-txt", "fed-h10-dat96-ne-txt")
ECB_M, ECB_D = fx.ECB_MONTHLY, fx.ECB_DAILY
IMF_ID = "imf-api-er-nld"
BOE_M = "boe-gold-usd-monthly-average"
BOE_D = go.register_daily("XUDLGPD")
CORE_IDS = (WB_ID,) + FED_IDS + (ECB_M,)
OPTIONAL_IDS = (ECB_D, IMF_ID, BOE_M, BOE_D)
BOE_D_CODE = "XUDLGPD"

FIELD_NOTES = {
    "usd_oz": "World Bank Pink Sheet monthly gold, USD per troy ounce (whole USD in the pre-2000 part)",
    "fx_nlg_per_usd": "arithmetic mean of available Fed H.10 daily noon buying rates NY of the month (NLG per USD)",
    "fx_obs_count": "number of daily observations used; fx_nd_count = days with marker ND (missing, never filled)",
    "gold_nlg_oz": "usd_oz x fx_nlg_per_usd (Decimal, 34 digits); null when either input is missing",
    "hist_eur_equivalent_oz": ("historical EUR-equivalent = gold_nlg_oz / 2.20371, NOT a contemporaneous "
                               "traded euro price; null when gold_nlg_oz is null"),
    "fx_usd_per_eur": "ECB monthly average EXR M.USD.EUR.SP00.A, 1999 only (USD per EUR)",
    "gold_eur_oz": "usd_oz / fx_usd_per_eur, 1999 only",
    "sens_pom_vs_mop_rel": ("methodology sensitivity, not a correction: (product of means - mean of products) / mean of "
                            "products on days with both BoE XUDLGPD and Fed values"),
}

CSV_FIELDS = ["period", "regime", "usd_oz", "fx_nlg_per_usd", "fx_usd_per_eur", "fx_obs_count", "fx_nd_count",
              "gold_nlg_oz", "hist_eur_equivalent_oz", "gold_eur_oz", "quality_label", "outlier_flag",
              "outlier_boe_monthly_usd", "outlier_wb_minus_boe_usd", "outlier_wb_minus_boe_pct_of_boe",
              "sens_n_common_days", "sens_pom_vs_mop_rel", "usd_oz_source_url", "usd_oz_source_sha256",
              "fx_source_url", "fx_source_sha256", "rights_status", "publication_status"]


# ----------------------------------------------------------------------------- Decimal helpers
def _s(v):
    return None if v is None else format(v, "f")


def mean_dec(values):
    with localcontext() as c:
        c.prec = PREC
        return sum(values, Decimal(0)) / len(values)


def pct6(v):
    """Relative value as percent text (6 decimals)."""
    return None if v is None else str((v * 100).quantize(Decimal("0.000001")))


def sci(v):
    return None if v is None else f"{v:.4E}"


def pctile(sorted_vals, p):
    if not sorted_vals:
        return None
    return sorted_vals[max(0, math.ceil(p / 100 * len(sorted_vals)) - 1)]


def dist_stats(rels, worst=5):
    """rels: {month: Decimal relative difference}. Absolute-value distribution, signed median, worst months."""
    if not rels:
        return {"months": 0}
    absr = sorted(abs(v) for v in rels.values())
    ranked = sorted(rels.items(), key=lambda kv: abs(kv[1]), reverse=True)
    return {"months": len(rels), "median_abs_pct": pct6(pctile(absr, 50)), "mean_abs_pct": pct6(mean_dec(absr)),
            "p90_abs_pct": pct6(pctile(absr, 90)), "p95_abs_pct": pct6(pctile(absr, 95)),
            "p99_abs_pct": pct6(pctile(absr, 99)), "max_abs_pct": pct6(absr[-1]),
            "median_signed_pct": pct6(sorted(rels.values())[(len(rels) - 1) // 2]),
            "worst_months": [{"month": m, "signed_pct": pct6(v)} for m, v in ranked[:worst]],
            "months_abs_gt_0_1pct": sum(1 for v in absr if v > Decimal("0.001")),
            "months_abs_gt_0_5pct": sum(1 for v in absr if v > Decimal("0.005"))}


def month_of(d):
    return f"{d.year:04d}-{d.month:02d}"


# ----------------------------------------------------------------------------- Fed H.10
def parse_fed_file(raw, source_id):
    """One H.10 history file. Direction must be asserted from the header text (GUILDERS/US$) AND values."""
    try:
        parsed = ns.parse_dated_text(raw, century=1900)
        d = ns.detect_direction(" ".join(parsed["header"]), list(parsed["points"].values()))
    except ns.NlgSourceError as exc:
        raise fx.DataIntegrityError(f"{source_id}: {exc}") from exc
    if d["direction"] != "NLG_PER_USD" or d["evidence"] != "TEXT_AND_VALUE_RANGE":
        raise fx.DataIntegrityError(f"{source_id}: FED_DIRECTION_NOT_ASSERTED_FROM_HEADER {json.dumps(d)}")
    return parsed, d


def merge_fed(parsed_by_source):
    """Union of daily observations and ND days over files; a date in two files (or both value and ND) is a defect."""
    points, nd, origin = {}, set(), {}
    for sid, parsed in parsed_by_source.items():
        for d, v in parsed["points"].items():
            if d in points or d in nd:
                raise fx.DataIntegrityError(f"{sid}: DUPLICATE_DATE_ACROSS_FILES {d.isoformat()}")
            points[d], origin[d] = v, sid
        for d in parsed["missing_dates"]:
            if d in points or d in nd:
                raise fx.DataIntegrityError(f"{sid}: DUPLICATE_DATE_ACROSS_FILES {d.isoformat()}")
            nd.add(d)
            origin[d] = sid
    return points, nd, origin


def monthly_fx(points, nd, origin, months):
    """{month: {mean, n, nd, files}}; a month without observations has mean None (never filled)."""
    groups, ndc, files = {}, Counter(month_of(d) for d in nd), {}
    for d, v in points.items():
        groups.setdefault(month_of(d), []).append(v)
        files.setdefault(month_of(d), set()).add(origin[d])
    return {m: {"mean": mean_dec(groups[m]) if m in groups else None, "n": len(groups.get(m, ())),
                "nd": ndc.get(m, 0), "files": sorted(files.get(m, ()))} for m in months}


# ----------------------------------------------------------------------------- formulas (reuse hist_04_fx)
def gold_nlg(usd_oz, nlg_per_usd):
    if usd_oz is None or nlg_per_usd is None:
        return None
    return fx.gold_nlg_per_oz(usd_oz, nlg_per_usd)


def hist_eur_equivalent(gold_nlg_oz):
    return None if gold_nlg_oz is None else fx.nlg_to_eur(gold_nlg_oz)


def gold_eur(usd_oz, usd_per_eur):
    if usd_oz is None or usd_per_eur is None:
        return None
    return fx.gold_eur_per_oz(usd_oz, usd_per_eur)


def quality_label(usd_oz, fx_value, n_obs, regime):
    issues = []
    if usd_oz is None:
        issues.append("NO_USD_OZ")
    if fx_value is None:
        issues.append("NO_FX_OBSERVATIONS")
    elif regime == "NLG_FED_H10_MEAN" and n_obs < FEW_OBS:
        issues.append("INCOMPLETE_FEW_OBS")
    return "+".join(issues) if issues else "OK"


# ----------------------------------------------------------------------------- ECB
def parse_ecb_monthly(raw):
    try:
        p = fx.parse_ecb_csv(raw, "M")
    except fx.FxError as exc:
        raise fx.DataIntegrityError(f"{ECB_M}: {exc}") from exc
    meta = p["meta"]
    if meta.get("CURRENCY") != "USD" or meta.get("CURRENCY_DENOM") != "EUR":
        raise fx.DataIntegrityError(f"{ECB_M}: QUOTE_DIRECTION_NOT_ASSERTED_USD_PER_EUR {json.dumps(meta, sort_keys=True)}")
    if any(not Decimal("0.5") <= v <= Decimal("2.0") for v in p["points"].values()):
        raise fx.DataIntegrityError(f"{ECB_M}: USD_PER_EUR_OUT_OF_PLAUSIBLE_RANGE")
    return p["points"]


def parse_ecb_daily(raw):
    try:
        p = fx.parse_ecb_csv(raw, "D")
    except fx.FxError as exc:
        raise fx.DataIntegrityError(f"{ECB_D}: {exc}") from exc
    return {date.fromisoformat(k): v for k, v in p["points"].items()}


def parse_imf(raw):
    """Single NLD monthly series or None (+reason). Exploratory source: ambiguity is reported, not fatal."""
    try:
        scan = ns.scan_sdmx_xml(raw) if raw.lstrip()[:1] == b"<" else ns.scan_csv_bytes(raw)
    except ns.NlgSourceError as exc:
        raise fx.DataIntegrityError(f"{IMF_ID}: {exc}") from exc
    mons = scan["_monthlies"]
    if len(mons) != 1:
        return None, f"IMF_SERIES_COUNT_{len(mons)}"
    (monthly, _), = mons.values()
    return monthly, None


def parse_boe_monthly(raw):
    try:
        pts, _ = ss.parse_points(raw, ss.BOE_SERIES)
        return ss.monthly_from_points(pts)
    except ss.SecondSourceError as exc:
        raise fx.DataIntegrityError(f"{BOE_M}: {exc}") from exc


def parse_boe_daily(raw):
    try:
        pts, _ = ss.parse_points(raw, BOE_D_CODE)
    except ss.SecondSourceError as exc:
        raise fx.DataIntegrityError(f"{BOE_D}: {exc}") from exc
    return pts


# ----------------------------------------------------------------------------- analyses
def fed_vs_imf(fed_m, imf_m, months):
    """Per-month |IMF - Fed| / Fed on common months. Independence of the sources is NOT assumed."""
    rels = {}
    for m in months:
        f = fed_m.get(m, {}).get("mean")
        i = imf_m.get(m)
        if f is not None and i is not None:
            with localcontext() as c:
                c.prec = PREC
                rels[m] = (i - f) / f
    unit_ratio = None
    if rels:
        ratios = sorted(imf_m[m] / fed_m[m]["mean"] for m in rels)
        unit_ratio = ratios[len(ratios) // 2]
    out = dist_stats(rels)
    out.update({"definition": "(IMF XDC_USD PA_RT monthly - Fed mean of daily noon rates) / Fed; signed value shown for worst months",
                "median_ratio_imf_to_fed": _s(unit_ratio.quantize(Decimal("0.00001"))) if unit_ratio else None,
                "independence": "NOT ASSUMED: shared origin of IMF and Fed is not excluded (both deviate in 1991-03 per earlier run)"})
    if unit_ratio is not None and abs(unit_ratio - 1) > Decimal("0.03"):
        out["unit_check"] = "MISMATCH_COMPARISON_NOT_RELIABLE"
    elif unit_ratio is not None:
        out["unit_check"] = "NLG_PER_USD_BY_COMPARISON"
    return out


def product_sensitivity(boe_daily, fed_points, wb, fed_m, months):
    """Product of monthly means vs mean of daily products on common days (BoE XUDLGPD x Fed).

    A = mean(gold over common days) x mean(fx over common days); B = mean(gold_d x fx_d).
    pom_vs_mop = (A - B) / B is a methodology sensitivity, NOT a correction.
    pipeline_vs_mop = (WB monthly x Fed monthly mean - B) / B additionally contains the WB-vs-BoE definition gap.
    """
    per, pom, pipe = {}, {}, {}
    by_month = {}
    for d in set(boe_daily) & set(fed_points):
        by_month.setdefault(month_of(d), []).append(d)
    for m in months:
        days = sorted(by_month.get(m, ()))
        if not days:
            continue
        with localcontext() as c:
            c.prec = PREC
            a = mean_dec([boe_daily[d] for d in days]) * mean_dec([fed_points[d] for d in days])
            b = mean_dec([boe_daily[d] * fed_points[d] for d in days])
            pom[m] = (a - b) / b
            per[m] = {"n_common_days": len(days), "rel": pom[m]}
            f, w = fed_m.get(m, {}).get("mean"), wb.get(m)
            if f is not None and w is not None:
                pipe[m] = (w * f - b) / b
    ncs = sorted(v["n_common_days"] for v in per.values())
    return per, {"months": len(pom), "common_days_per_month_min_median_max": [ncs[0], ncs[len(ncs) // 2], ncs[-1]] if ncs else None,
                 "product_of_means_vs_mean_of_products": dist_stats(pom),
                 "wb_pipeline_vs_mean_of_products": dist_stats(pipe),
                 "note": "methodology sensitivity only; no value is corrected; Jensen-type covariance of gold and FX within the month"}


def transition_monthly(rows):
    r98, r99 = rows.get("1998-12"), rows.get("1999-01")
    need = {"usd_1998_12": r98 and r98["_usd"], "gold_nlg_1998_12": r98 and r98["_gold_nlg"], "fx_nlg_1998_12": r98 and r98["_fx_nlg"],
            "usd_1999_01": r99 and r99["_usd"], "gold_eur_1999_01": r99 and r99["_gold_eur"], "fx_usd_per_eur_1999_01": r99 and r99["_fx_eur"]}
    missing = [k for k, v in need.items() if v is None]
    if missing:
        return {"status": "NOT_COMPUTABLE", "missing_inputs": missing}
    with localcontext() as c:
        c.prec = PREC
        eq98 = need["gold_nlg_1998_12"] / NLG_PER_EUR
        implied98 = fx.implied_usd_per_eur(need["fx_nlg_1998_12"])
        eur_chg = need["gold_eur_1999_01"] / eq98 - 1
        usd_chg = need["usd_1999_01"] / need["usd_1998_12"] - 1
        fx_chg = need["fx_usd_per_eur_1999_01"] / implied98 - 1
        residual = abs((1 + eur_chg) - (1 + usd_chg) / (1 + fx_chg))
        ln_eur, ln_usd, ln_fx = (1 + eur_chg).ln(), (1 + usd_chg).ln(), (1 + fx_chg).ln()
    return {"status": "COMPUTED",
            "hist_eur_equivalent_oz_1998_12": _s(eq98.quantize(Decimal("0.0001"))),
            "gold_eur_oz_1999_01": _s(need["gold_eur_1999_01"].quantize(Decimal("0.0001"))),
            "eur_equivalent_change_pct": pct6(eur_chg),
            "wb_usd_oz_1998_12": _s(need["usd_1998_12"]), "wb_usd_oz_1999_01": _s(need["usd_1999_01"]),
            "wb_usd_change_pct": pct6(usd_chg),
            "implied_usd_per_eur_1998_12": _s(implied98.quantize(Decimal("0.00000001"))),
            "ecb_monthly_usd_per_eur_1999_01": _s(need["fx_usd_per_eur_1999_01"]),
            "usd_per_eur_change_pct": pct6(fx_chg),
            "identity": "(1+eur_change) = (1+usd_change)/(1+usd_per_eur_change); residual " + sci(residual),
            "log_decomposition": {"ln_eur_equivalent_change": _s(ln_eur.quantize(Decimal("0.000001"))),
                                  "ln_usd_change": _s(ln_usd.quantize(Decimal("0.000001"))),
                                  "minus_ln_usd_per_eur_change": _s((-ln_fx).quantize(Decimal("0.000001")))},
            "reading": ("numbers only: the EUR-equivalent change equals the USD gold change adjusted for the change of the "
                        "implied USD/EUR rate; the definitions (Fed daily-mean NY noon vs ECB monthly average) differ, "
                        "so a share of the move can be definitional; it is not quantified here")}


def _rel_changes(seq):
    out = []
    for (_, a), (_, b) in zip(seq, seq[1:]):
        with localcontext() as c:
            c.prec = PREC
            out.append(abs(b / a - 1))
    return sorted(out)


def transition_daily(fed_points, ecb_daily, last_n=250, first_n=60):
    """Boundary 1998-12-31 -> 1999-01-04 on implied USD/EUR = 2.20371 / (NLG per USD) vs ECB daily USD per EUR."""
    fed_days = sorted(d for d in fed_points if d <= date(1998, 12, 31))
    if not fed_days or not ecb_daily:
        return {"status": "NOT_COMPUTABLE", "fed_days": len(fed_days), "ecb_days": len(ecb_daily or ())}
    f_last, e_first = fed_days[-1], min(ecb_daily)
    implied = {d: fx.implied_usd_per_eur(fed_points[d]) for d in fed_days}
    with localcontext() as c:
        c.prec = PREC
        jump = ecb_daily[e_first] / implied[f_last] - 1
    fed_tail = _rel_changes([(d, implied[d]) for d in fed_days[-last_n:]])
    ecb_days = sorted(d for d in ecb_daily if d >= e_first)[:first_n]
    ecb_head = _rel_changes([(d, ecb_daily[d]) for d in ecb_days])
    overlap = sorted(set(fed_points) & set(ecb_daily))
    res = {"status": "COMPUTED", "fed_last_day": f_last.isoformat(), "fed_last_nlg_per_usd": _s(fed_points[f_last]),
           "fed_last_implied_usd_per_eur": _s(implied[f_last].quantize(Decimal("0.00000001"))),
           "ecb_first_day": e_first.isoformat(), "ecb_first_usd_per_eur": _s(ecb_daily[e_first]),
           "calendar_days_between": (e_first - f_last).days, "boundary_change_pct": pct6(jump),
           "overlap_days": len(overlap),
           "baseline_daily_abs_change_pct": {
               "fed_implied_last_%d_obs" % last_n: {"median": pct6(pctile(fed_tail, 50)), "p95": pct6(pctile(fed_tail, 95)), "max": pct6(fed_tail[-1] if fed_tail else None)},
               "ecb_first_%d_obs" % first_n: {"median": pct6(pctile(ecb_head, 50)), "p95": pct6(pctile(ecb_head, 95)), "max": pct6(ecb_head[-1] if ecb_head else None)}},
           "boundary_abs_vs_fed_baseline_median_x": (_s((abs(jump) / pctile(fed_tail, 50)).quantize(Decimal("0.01")))
                                                     if fed_tail and pctile(fed_tail, 50) else None),
           "reading": ("a boundary change inside the range of ordinary day-to-day moves is market movement; the gap spans "
                       "non-trading days and the two series have different sources; no cause is claimed")}
    if overlap:
        devs = sorted(abs(ecb_daily[d] / implied[d] - 1) for d in overlap)
        res["overlap_max_abs_pct"] = pct6(devs[-1])
    return res


def definitional_breaks():
    return [
        "FX source: Fed H.10 noon buying rates New York for cable transfers (NLG per USD) until 1998-12, ECB reference rates (USD per EUR) from 1999-01",
        "FX aggregation: arithmetic mean of available daily observations (1975-1998) vs ECB provider monthly average (1999); ECB monthly equals the mean of ECB daily values (earlier run, max deviation 5.3E-14)",
        "Quote direction: NLG per USD (multiply) before 1999, USD per EUR (divide) from 1999; the historical EUR-equivalent divides NLG by the fixed 2.20371",
        "Gold: single World Bank Pink Sheet series across the boundary (no break in the gold source); whole-USD rounding before 2000",
        "Currency: NLG until 1998-12 versus euro from 1999-01; the 1975-1998 EUR-equivalent is a fixed-rate conversion, not a traded euro price",
    ]


def outlier_details(wb, boe_m, boe_daily):
    out = {}
    for m in go.OUTLIER_MONTHS:
        w, b = wb.get(m), (boe_m or {}).get(m)
        cmp_ = go.compare(w, b)
        d = {"wb_usd_oz": _s(w), "boe_monthly_usd": _s(b) if b is not None else None,
             "wb_minus_boe_usd": cmp_["diff"] if cmp_ else None,
             "wb_minus_boe_pct_of_boe": cmp_["pct_of_other"] if cmp_ else None}
        v = go.daily_variants(boe_daily, m) if boe_daily else None
        if v:
            d["boe_daily_min"], d["boe_daily_max"], d["boe_daily_days"] = _s(v["min"]), _s(v["max"]), v["n_days"]
        out[m] = d
    return out


# ----------------------------------------------------------------------------- table
def build_rows(wb, fed_m, ecb_m, outliers, sens, sources):
    rows = {}
    for m in month_range(NLG_START, EUR_END):
        usd = wb.get(m)
        if m <= NLG_END:
            f = fed_m.get(m, {"mean": None, "n": 0, "nd": 0, "files": []})
            g = gold_nlg(usd, f["mean"])
            fx_value, regime = f["mean"], "NLG_FED_H10_MEAN"
            row = {"period": m, "regime": regime, "usd_oz": _s(usd), "fx_nlg_per_usd": _s(f["mean"]), "fx_usd_per_eur": None,
                   "fx_obs_count": f["n"], "fx_nd_count": f["nd"], "gold_nlg_oz": _s(g),
                   "hist_eur_equivalent_oz": _s(hist_eur_equivalent(g)), "gold_eur_oz": None,
                   "_usd": usd, "_fx_nlg": f["mean"], "_fx_eur": None, "_gold_nlg": g, "_gold_eur": None}
            fx_ids = f["files"]
            n_obs = f["n"]
        else:
            e = ecb_m.get(m)
            ge = gold_eur(usd, e)
            fx_value, regime, n_obs = e, "EUR_ECB_MONTHLY", None
            row = {"period": m, "regime": regime, "usd_oz": _s(usd), "fx_nlg_per_usd": None, "fx_usd_per_eur": _s(e),
                   "fx_obs_count": None, "fx_nd_count": None, "gold_nlg_oz": None, "hist_eur_equivalent_oz": None,
                   "gold_eur_oz": _s(ge), "_usd": usd, "_fx_nlg": None, "_fx_eur": e, "_gold_nlg": None, "_gold_eur": ge}
            fx_ids = [ECB_M] if e is not None else []
        row["quality_label"] = quality_label(usd, fx_value, n_obs, regime)
        row["outlier_flag"] = OUTLIER_FLAG if m in go.OUTLIER_MONTHS else None
        o = outliers.get(m) if m in go.OUTLIER_MONTHS else None
        row["outlier_boe_monthly_usd"] = o and o["boe_monthly_usd"]
        row["outlier_wb_minus_boe_usd"] = o and o["wb_minus_boe_usd"]
        row["outlier_wb_minus_boe_pct_of_boe"] = o and o["wb_minus_boe_pct_of_boe"]
        sv = (sens or {}).get(m)
        row["sens_n_common_days"] = sv["n_common_days"] if sv else None
        row["sens_pom_vs_mop_rel"] = _s(sv["rel"]) if sv else None
        wbs, fxs = sources.get(WB_ID), [sources[i] for i in fx_ids if i in sources]
        row["usd_oz_source_url"] = wbs["url"] if wbs and usd is not None else None
        row["usd_oz_source_sha256"] = wbs["sha256"] if wbs and usd is not None else None
        row["fx_source_url"] = ";".join(x["url"] for x in fxs) or None
        row["fx_source_sha256"] = ";".join(x["sha256"] for x in fxs) or None
        row["rights_status"], row["publication_status"] = "UNVERIFIED", PUBLICATION
        rows[m] = row
    return rows


def public_row(row):
    return {k: v for k, v in row.items() if not k.startswith("_")}


def write_table(rows, meta, json_path, csv_path):
    clean = [public_row(r) for r in rows.values()]
    doc = {"label": LABEL, "publication_status": PUBLICATION, "rights_status": "UNVERIFIED", "field_notes": FIELD_NOTES, **meta,
           "rows": clean}
    if json_path:
        Path(json_path).parent.mkdir(parents=True, exist_ok=True)
        Path(json_path).write_text(json.dumps(doc, indent=1, sort_keys=False) + "\n")
    if csv_path:
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=CSV_FIELDS, lineterminator="\n")
        w.writeheader()
        for r in clean:
            w.writerow({k: ("" if r.get(k) is None else r[k]) for k in CSV_FIELDS})
        Path(csv_path).parent.mkdir(parents=True, exist_ok=True)
        Path(csv_path).write_text(buf.getvalue())


# ----------------------------------------------------------------------------- checks
def independent_recompute(rows, wb, fed_points, ecb_m):
    """Exact Fraction arithmetic from raw inputs; compares every non-null output (does not reuse mean_dec / fx formulas)."""
    groups = {}
    for d, v in fed_points.items():
        groups.setdefault(month_of(d), []).append(Fraction(v))
    worst, checked = Fraction(0), 0
    for m, r in rows.items():
        pairs = []
        if r["_gold_nlg"] is not None:
            fmean = sum(groups[m]) / len(groups[m])
            usd = Fraction(wb[m])
            g = usd * fmean
            pairs += [(Fraction(r["_gold_nlg"]), g), (Fraction(r["hist_eur_equivalent_oz"]), g / Fraction(220371, 100000))]
        if r["_gold_eur"] is not None:
            pairs.append((Fraction(r["_gold_eur"]), Fraction(wb[m]) / Fraction(ecb_m[m])))
        for got, exp in pairs:
            checked += 1
            worst = max(worst, abs(got - exp) / exp)
    return {"values_checked": checked, "max_rel_deviation": f"{Decimal(worst.numerator) / Decimal(worst.denominator):.3E}", "pass": worst < Fraction(1, 10 ** 30)}


def coverage_report(rows, fed_m, expected=EXPECTED_NLG_MONTHS):
    nlg = [r for r in rows.values() if r["regime"] == "NLG_FED_H10_MEAN"]
    eur = [r for r in rows.values() if r["regime"] == "EUR_ECB_MONTHLY"]
    counts = sorted(r["fx_obs_count"] for r in nlg)
    labels = Counter(r["quality_label"] for r in rows.values())
    return {"nlg_months_expected": expected, "nlg_months_in_table": len(nlg), "nlg_months_exactly_288": len(nlg) == expected,
            "nlg_months_with_usd_oz": sum(1 for r in nlg if r["_usd"] is not None),
            "nlg_months_with_fx": sum(1 for r in nlg if r["_fx_nlg"] is not None),
            "nlg_months_with_gold_nlg": sum(1 for r in nlg if r["_gold_nlg"] is not None),
            "nlg_months_null_gold_nlg": sum(1 for r in nlg if r["_gold_nlg"] is None),
            "nlg_months_with_hist_eur_equivalent": sum(1 for r in nlg if r["hist_eur_equivalent_oz"] is not None),
            "eur_months_expected": len(month_range(EUR_START, EUR_END)), "eur_months_with_gold_eur": sum(1 for r in eur if r["_gold_eur"] is not None),
            "fx_obs_per_month_min_median_max": [counts[0], counts[len(counts) // 2], counts[-1]] if counts else None,
            "months_below_%d_obs" % FEW_OBS: sum(1 for c in counts if c < FEW_OBS),
            "months_zero_obs": sum(1 for c in counts if c == 0),
            "nd_days_total": sum(r["fx_nd_count"] for r in nlg), "quality_labels": dict(sorted(labels.items())),
            "outlier_months_flagged": [m for m, r in rows.items() if r["outlier_flag"]]}


def wb_precision(wb_parsed, wb):
    fp = wbv.fingerprint(wb_parsed)
    vals = [wb[m] for m in month_range(NLG_START, EUR_END) if m in wb]
    bounds = sorted(Decimal("0.5") / v for v in vals)
    return {"non_integer_count_in_range": fp["non_integer_count_in_range"], "months": len(vals),
            "max_rel_rounding_bound_pct": pct6(bounds[-1]) if bounds else None,
            "median_rel_rounding_bound_pct": pct6(pctile(bounds, 50)),
            "note": "values are whole USD per oz where integer; an integer value carries a rounding uncertainty of up to 0.5 USD (the stated bound), "
                    "unknown for non-integer months; the bound is not propagated into the table"}


# ----------------------------------------------------------------------------- orchestration
def collect(workbook=None, acquire=fx.acquire):
    """Fetch, parse and analyse. Returns (summary, rows). Raises fx.DataIntegrityError on real defects."""
    s = {"status": "RUNNING", "label": LABEL, "publication_status": PUBLICATION, "rights_status": "UNVERIFIED",
         "publication_authorized": False, "source_approved": False, "method": "see module docstring", "sources": {},
         "missing_sources": [], "flags": [], "analyses_not_performed": [], "checks": {}}
    raws = {}

    def get(sid, local=None):
        try:
            if local is not None:
                raw, rec = wbv.load_workbook(local)
            elif sid == WB_ID:
                raw, rec = wbv.load_workbook(None)
            else:
                raw, rec = acquire(sid)
        except hist_02_acquire.AcquisitionError as exc:
            err = fx.classify_acquisition_error(sid, exc)
            if isinstance(err, fx.SourceUnavailable):
                s["missing_sources"].append({"source_id": sid, "reason": err.reason_class, "detail": err.detail[:160]})
                return None
            raise err from exc
        except fx.SourceUnavailable as exc:
            s["missing_sources"].append({"source_id": sid, "reason": exc.reason_class, "detail": exc.detail[:160]})
            return None
        s["sources"][sid] = {"url": rec["url"], "sha256": rec["sha256"], "bytes": rec["bytes"],
                             "origin": rec.get("origin", "fetch"), "rights_status": "UNVERIFIED"}
        raws[sid] = raw
        return rec

    # World Bank (hist-03 semantics: structure hard, hashes flagged)
    wb, wb_parsed = {}, None
    rec = get(WB_ID, workbook)
    if rec:
        try:
            summary = wbv.validate(raws[WB_ID])
            wb_parsed = wbv.parse(raws[WB_ID])
        except wbv.ValidationError as exc:
            raise fx.DataIntegrityError(f"{WB_ID}: {exc}") from exc
        if summary["status"] != "VALIDATED":
            raise fx.DataIntegrityError(f"{WB_ID}: VALIDATION_FAILED {summary['problems']}")
        wb = wb_parsed["series"]
        s["sources"][WB_ID]["matches_known_workbook_sha256"] = rec["matches_known_workbook_sha256"]
        s["sources"][WB_ID]["canonical_series_sha256"] = summary["canonical_series_sha256"]
        s["sources"][WB_ID]["matches_known_canonical_series_sha256"] = (
            summary["canonical_series_sha256"] == wbv.KNOWN_CANONICAL_SERIES_SHA256)
        if not rec["matches_known_workbook_sha256"]:
            s["flags"].append("WB_WORKBOOK_SHA256_DIFFERS_FROM_KNOWN: source revision, human review required (hist-03 semantics)")
        if not s["sources"][WB_ID]["matches_known_canonical_series_sha256"]:
            s["flags"].append("WB_CANONICAL_SERIES_SHA256_DIFFERS_FROM_KNOWN: source revision, human review required")
        s["wb_precision"] = wb_precision(wb_parsed, wb)

    # Fed H.10
    parsed_fed, fed_dirs = {}, {}
    for sid in FED_IDS:
        if get(sid):
            parsed_fed[sid], fed_dirs[sid] = parse_fed_file(raws[sid], sid)
            s["sources"][sid]["points"] = len(parsed_fed[sid]["points"])
            s["sources"][sid]["nd_markers"] = parsed_fed[sid]["missing_markers"]
            s["sources"][sid]["direction"] = fed_dirs[sid]
            s["sources"][sid]["header_head"] = parsed_fed[sid]["header"][:4]
    fed_points, fed_nd, fed_origin = merge_fed(parsed_fed)
    nlg_months = month_range(NLG_START, NLG_END)
    fed_m = monthly_fx(fed_points, fed_nd, fed_origin, nlg_months)
    s["checks"]["fed_directions"] = {k: v["direction"] for k, v in fed_dirs.items()}
    s["checks"]["nlg_expected_months"] = len(nlg_months)

    # ECB monthly (1999)
    ecb_m = {}
    if get(ECB_M):
        ecb_m = parse_ecb_monthly(raws[ECB_M])
        s["sources"][ECB_M]["observations"] = len(ecb_m)

    # optional sources
    ecb_d = {}
    if get(ECB_D):
        ecb_d = parse_ecb_daily(raws[ECB_D])
    imf_m, imf_reason = {}, None
    if get(IMF_ID):
        imf_m, imf_reason = parse_imf(raws[IMF_ID])
        imf_m = imf_m or {}
    boe_m = {}
    if get(BOE_M):
        boe_m = parse_boe_monthly(raws[BOE_M])
    boe_d = {}
    if get(BOE_D):
        boe_d = parse_boe_daily(raws[BOE_D])

    # analyses
    outliers = outlier_details(wb, boe_m or None, boe_d or None)
    sens_rows, sens = ({}, None)
    if boe_d and fed_points:
        sens_rows, sens = product_sensitivity(boe_d, fed_points, wb, fed_m, nlg_months)
        s["product_of_means_vs_mean_of_products"] = sens
    else:
        s["analyses_not_performed"].append({"analysis": "product_of_means_vs_mean_of_products", "reason": "needs BoE XUDLGPD daily and Fed daily"})
    rows = build_rows(wb, fed_m, ecb_m, outliers, sens_rows, s["sources"])
    s["coverage"] = coverage_report(rows, fed_m)
    s["outlier_months"] = outliers
    if imf_m and fed_points:
        s["fed_vs_imf"] = fed_vs_imf(fed_m, imf_m, nlg_months)
    else:
        s["analyses_not_performed"].append({"analysis": "fed_vs_imf", "reason": imf_reason or "IMF or Fed monthly series not obtained"})
    s["transition"] = {"definitional_breaks": definitional_breaks(), "monthly_1998_12_to_1999_01": transition_monthly(rows)}
    if fed_points and ecb_d:
        s["transition"]["daily_boundary"] = transition_daily(fed_points, ecb_d)
    else:
        s["analyses_not_performed"].append({"analysis": "transition_daily_boundary", "reason": "needs Fed daily and ECB daily"})
    if wb and fed_points:
        s["checks"]["independent_recompute"] = independent_recompute(rows, wb, fed_points, ecb_m)
        if not s["checks"]["independent_recompute"]["pass"]:
            raise fx.DataIntegrityError("FORMULA_RECOMPUTE_MISMATCH")
    core_missing = [m["source_id"] for m in s["missing_sources"] if m["source_id"] in CORE_IDS]
    s["status"] = "INCOMPLETE" if core_missing else ("PARTIAL" if s["missing_sources"] else "COMPLETE_RESEARCH_CANDIDATE")
    return s, rows


def report_lines(s):
    c, t = s.get("coverage", {}), s.get("transition", {})
    L = ["REPORT status=%s label=%r missing=%s flags=%s" % (s["status"], LABEL, [m["source_id"] for m in s["missing_sources"]], s["flags"])]
    L.append("REPORT sources=" + json.dumps({k: {"sha256": v["sha256"], "bytes": v["bytes"]} for k, v in s["sources"].items()}, sort_keys=True))
    L.append("REPORT coverage=" + json.dumps(c, sort_keys=True))
    L.append("REPORT checks=" + json.dumps(s["checks"], sort_keys=True))
    L.append("REPORT wb_precision=" + json.dumps(s.get("wb_precision"), sort_keys=True))
    L.append("REPORT transition_monthly=" + json.dumps(t.get("monthly_1998_12_to_1999_01"), sort_keys=True))
    L.append("REPORT transition_daily=" + json.dumps(t.get("daily_boundary"), sort_keys=True))
    L.append("REPORT fed_vs_imf=" + json.dumps(s.get("fed_vs_imf"), sort_keys=True))
    L.append("REPORT product_vs_mean=" + json.dumps(s.get("product_of_means_vs_mean_of_products"), sort_keys=True))
    L.append("REPORT outliers=" + json.dumps(s.get("outlier_months"), sort_keys=True))
    L.append("REPORT not_performed=" + json.dumps(s["analyses_not_performed"]))
    return L


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary-out", required=True)
    ap.add_argument("--table-json-out")
    ap.add_argument("--table-csv-out")
    ap.add_argument("--workbook", help="read this local World Bank workbook instead of downloading it")
    args = ap.parse_args(argv)
    out = Path(args.summary_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        s, rows = collect(args.workbook)
    except (fx.DataIntegrityError, fx.FxError, ns.NlgSourceError, ss.SecondSourceError, wbv.ValidationError) as exc:
        out.write_text(json.dumps({"status": "FAILED", "label": LABEL, "error": str(exc)[:400]}, indent=2) + "\n")
        print("DEFECT", str(exc)[:400])
        return 1
    meta = {"status": s["status"], "sources": s["sources"], "missing_sources": s["missing_sources"], "flags": s["flags"],
            "formula": {"nlg": "gold_nlg_oz = usd_oz * mean(daily NLG per USD)", "eur_equivalent": "hist_eur_equivalent_oz = gold_nlg_oz / 2.20371",
                        "eur_1999": "gold_eur_oz = usd_oz / ECB monthly USD per EUR"}}
    write_table(rows, meta, args.table_json_out, args.table_csv_out)
    out.write_text(json.dumps(s, indent=2, sort_keys=True, default=str) + "\n")
    print("\n".join(report_lines(s)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
