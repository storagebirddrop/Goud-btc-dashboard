"""HIST-10 research only: Dutch housing prices in grams of gold from 1975 (NVM median, CBS mean), on ARCH-02.

Nothing here is a decision, a methodology or a publication. Raw third-party bytes are read in memory in GitHub
Actions (tools.hist_08_gold_validate.load -> tools.hist_02_acquire.fetch) and never stored; the artifact holds
aggregates and a derived half-year table only. Offline tests use synthetic inputs and prove code, not data.

Series (separate, never spliced): World Bank gold USD/oz monthly; Fed NLG-per-USD daily; ECB USD-per-EUR daily;
local-currency gold (NLG 1975-1998, observed EUR 1999-, retrospective EUR as a labelled third series);
NVM median and CBS mean housing in grams of gold. NVM and CBS stay different statistics.
"""
import argparse
import csv
import hashlib
import json
import signal
import sys
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from etl import hist_model as hm  # noqa: E402
from tools import hist_08_bundle as hb  # noqa: E402
from tools import hist_09_bundle as h9  # noqa: E402

RETRIEVED = "2026-10-22T00:00:00+00:00"  # day of the research run; the run date is recorded, not the publisher's date
RATE = Fraction(220371, 100000)
G_PER_OZ = Fraction(311034768, 10 ** 7)
MIN_DAY_COVERAGE = Decimal("0.5")  # share of calendar days required for a monthly FX mean (explicit, recorded)
NLG_ERA = ("1975-01", "1998-12")
EUR_ERA_FIRST = "1999-01"
LEVELS = (("1975-01", "1978-12", "GOLD_LEVEL_B"), ("1979-01", "1998-12", "GOLD_LEVEL_A"),
          ("1999-01", "1999-12", "GOLD_LEVEL_E"), ("2000-01", "2099-12", "GOLD_ADR004_PERIOD"))
CAVEAT = "research only; nothing approved; rights UNVERIFIED; no raw third-party bytes in artifacts"


class Hist10Error(hm.ModelError):
    """Input or consistency defect: fail closed."""


def level_flag(month: str) -> str:
    for first, last, flag in LEVELS:
        if first <= month <= last:
            return flag
    raise Hist10Error(f"{month}: before the research start 1975-01")


# ------------------------------------------------------------------ source adapters (verified, provenance-carrying)
def gold_usd_series(wb: dict, raw_sha: str, *, first="1975-01") -> hm.Series:
    """World Bank monthly gold, USD per troy ounce, from `first`. Quality flags follow HIST-08 (PROPOSED thresholds)."""
    values = {m: v for m, v in sorted(wb.items()) if m >= first}
    if not values:
        raise Hist10Error("no World Bank gold observations from the research start")
    rows = tuple(hm.Observation("gold_usd_monthly", m, v, "USD", "USD_per_troy_oz", "wb_pink_sheet_gold_monthly",
                                "world_bank_commodity_markets", raw_sha, RETRIEVED, f"sha:{raw_sha[:12]}", "CONFIRMED",
                                ("WB_WHOLE_USD", level_flag(m))) for m, v in values.items())
    s = hm.Series("gold_usd_monthly", "source", "gold", "monthly", "USD", "USD_per_troy_oz", "wb_pink_sheet_gold_monthly",
                  "spot_price", "nominal", None, (), rows)
    hm.validate_series(s)
    return s


def fx_daily_series(series_id, daily: dict, *, currency, unit, source_id, raw_sha, definition) -> hm.Series:
    """Daily FX quote {date: Decimal}; the quotation direction is part of `unit` (e.g. NLG_per_USD)."""
    if not daily:
        raise Hist10Error(f"{series_id}: no observations")
    rows = tuple(hm.Observation(series_id, d.isoformat(), v, currency, unit, definition, source_id, raw_sha, RETRIEVED,
                                f"sha:{raw_sha[:12]}", "CONFIRMED", ()) for d, v in sorted(daily.items()))
    s = hm.Series(series_id, "source", "fx", "daily", currency, unit, definition, "fx_rate", "nominal", None, (), rows)
    hm.validate_series(s)
    return s


def window(s: hm.Series, first: str, last: str, series_id: str) -> hm.Series:
    """Subset of a SOURCE series' periods (same provenance, no new values): a labelled era, never a splice."""
    if s.layer != "source":
        raise Hist10Error("window applies to source series only")
    rows = tuple(replace_obs(o, series_id) for o in s.observations if first <= o.period <= last)
    if not rows:
        raise Hist10Error(f"{series_id}: empty window {first}..{last}")
    out = hm.Series(series_id, "source", s.asset_class, s.frequency, s.currency, s.unit, s.definition_id, s.kind,
                    s.basis, s.index_base, (), rows)
    hm.validate_series(out)
    return out


def replace_obs(o: hm.Observation, series_id: str) -> hm.Observation:
    return hm.Observation(series_id, o.period, o.value, o.currency, o.unit, o.definition_id, o.source_id, o.raw_sha256,
                          o.retrieved_at, o.vintage, o.quality, o.flags)


# ------------------------------------------------------------------ model construction
def build_gold(gold_usd: hm.Series, fed_daily: hm.Series, ecb_daily: hm.Series) -> dict:
    """All gold and FX series; local-currency gold per era, plus half-year aggregations under every rule."""
    out = {"gold_usd_monthly": gold_usd, "fed_nlg_per_usd_daily": fed_daily, "ecb_usd_per_eur_daily": ecb_daily}
    out["fed_nlg_per_usd_monthly"] = hm.monthly_mean(fed_daily, min_coverage=MIN_DAY_COVERAGE, series_id="fed_nlg_per_usd_monthly")
    out["ecb_usd_per_eur_monthly"] = hm.monthly_mean(ecb_daily, min_coverage=MIN_DAY_COVERAGE, series_id="ecb_usd_per_eur_monthly")
    last = gold_usd.observations[-1].period
    out["gold_usd_nlg_era"] = window(gold_usd, *NLG_ERA, "gold_usd_nlg_era")
    out["gold_usd_eur_era"] = window(gold_usd, EUR_ERA_FIRST, last, "gold_usd_eur_era")
    out["gold_nlg_monthly"] = hm.convert_currency_by_quote(out["gold_usd_nlg_era"], out["fed_nlg_per_usd_monthly"],
                                                           to_currency="NLG", series_id="gold_nlg_monthly")
    out["gold_eur_monthly"] = hm.convert_currency(out["gold_usd_eur_era"], out["ecb_usd_per_eur_monthly"],
                                                  to_currency="EUR", series_id="gold_eur_monthly")
    out["gold_eur_retro_monthly"] = hm.redenominate_nlg_to_eur(out["gold_nlg_monthly"], series_id="gold_eur_retro_monthly")
    for rule in hm.HALF_RULES:
        out[f"gold_nlg_half_{rule}"] = hm.half_year_aggregate(out["gold_nlg_monthly"], rule=rule, series_id=f"gold_nlg_half_{rule}")
        out[f"gold_eur_half_{rule}"] = hm.half_year_aggregate(out["gold_eur_monthly"], rule=rule, series_id=f"gold_eur_half_{rule}")
        out[f"gold_eur_retro_half_{rule}"] = hm.half_year_aggregate(out["gold_eur_retro_monthly"], rule=rule,
                                                                    series_id=f"gold_eur_retro_half_{rule}")
    # ratio of half-year means (product of means): mean(USD gold) x mean(monthly FX) per half-year
    gu_nlg = hm.half_year_aggregate(out["gold_usd_nlg_era"], rule="mean", series_id="gold_usd_nlg_era_half_mean")
    fx_nlg = hm.half_year_aggregate(out["fed_nlg_per_usd_monthly"], rule="mean", series_id="fed_nlg_per_usd_half_mean")
    out["gold_nlg_half_ratio_of_means"] = hm.convert_currency_by_quote(gu_nlg, fx_nlg, to_currency="NLG",
                                                                       series_id="gold_nlg_half_ratio_of_means")
    gu_eur = hm.half_year_aggregate(out["gold_usd_eur_era"], rule="mean", series_id="gold_usd_eur_era_half_mean")
    fx_eur = hm.half_year_aggregate(out["ecb_usd_per_eur_monthly"], rule="mean", series_id="ecb_usd_per_eur_half_mean")
    out["gold_eur_half_ratio_of_means"] = hm.convert_currency(gu_eur, fx_eur, to_currency="EUR",
                                                              series_id="gold_eur_half_ratio_of_means")
    out.update({"gold_usd_nlg_era_half_mean": gu_nlg, "fed_nlg_per_usd_half_mean": fx_nlg,
                "gold_usd_eur_era_half_mean": gu_eur, "ecb_usd_per_eur_half_mean": fx_eur})
    return out


def build_housing_grams(gold: dict, nvm_nlg: hm.Series, cbs_price: hm.Series, cbs_count: hm.Series,
                        cbs_fixture: hm.Series, cbs_csv: hm.Series, rule: str = "mean") -> dict:
    """NVM and CBS in grams of gold, each statistic and each currency era in its own series (no splice)."""
    out = {}
    nvm_eur = hm.redenominate_nlg_to_eur(nvm_nlg, series_id="nvm_median_eur_halfyear")
    out["nvm_median_eur_halfyear"] = nvm_eur
    out["nvm_grams_nlg_era"] = hm.grams_per_house(nvm_nlg, gold[f"gold_nlg_half_{rule}"], series_id="nvm_grams_nlg_era")
    out["nvm_grams_eur_era"] = hm.grams_per_house(nvm_eur, gold[f"gold_eur_half_{rule}"], series_id="nvm_grams_eur_era")
    out["nvm_grams_eur_retro"] = hm.grams_per_house(nvm_eur, gold[f"gold_eur_retro_half_{rule}"], series_id="nvm_grams_eur_retro")
    cbs_half = hm.weighted_half_year_mean(cbs_price, cbs_count, series_id="cbs_avg_price_eur_halfyear")
    out["cbs_avg_price_eur_halfyear"] = cbs_half
    out["cbs_grams_eur_retro_halfyear"] = hm.grams_per_house(cbs_half, gold[f"gold_eur_retro_half_{rule}"],
                                                              series_id="cbs_grams_eur_retro_halfyear")
    out["cbs_grams_eur_halfyear"] = hm.grams_per_house(cbs_half, gold[f"gold_eur_half_{rule}"], series_id="cbs_grams_eur_halfyear")
    out["cbs_grams_1995_1998_retro_monthly"] = hm.grams_per_house(cbs_fixture, gold["gold_eur_retro_monthly"],
                                                                  series_id="cbs_grams_1995_1998_retro_monthly")
    out["cbs_grams_1999_monthly"] = hm.grams_per_house(cbs_fixture, gold["gold_eur_monthly"], series_id="cbs_grams_1999_monthly")
    out["cbs_grams_2000_onward_monthly"] = hm.grams_per_house(cbs_csv, gold["gold_eur_monthly"],
                                                              series_id="cbs_grams_2000_onward_monthly")
    return out


def lineage_closure(allseries: dict, members) -> list:
    """Series plus every ancestor (validate_bundle requires the full lineage inside the bundle)."""
    by_hash = {hm.series_sha256(s): s for s in allseries.values()}
    need, stack = {}, list(members)
    while stack:
        s = stack.pop()
        if s.series_id in need:
            continue
        need[s.series_id] = s
        for _, digest in s.inputs:
            if digest not in by_hash:
                raise Hist10Error(f"{s.series_id}: ancestor with hash {digest[:12]} is not among the built series")
            stack.append(by_hash[digest])
    order = {sid: i for i, sid in enumerate(allseries)}
    return sorted(need.values(), key=lambda s: order.get(s.series_id, 10**6))


def all_series(gold: dict, houses: dict, *sources: hm.Series) -> dict:
    """Every built series plus the housing source series that feed the derived ones (needed for lineage)."""
    out = {**gold, **houses}
    for s in sources:
        out[s.series_id] = s
    return out


def bundles(allseries: dict) -> dict:
    g = allseries
    spec = {
        "A_gold_original": ["gold_usd_monthly"],
        "B_gold_local": ["gold_nlg_monthly", "gold_eur_monthly", "gold_eur_retro_monthly"] +
                        [f"gold_{c}_half_{r}" for c in ("nlg", "eur", "eur_retro") for r in hm.HALF_RULES] +
                        ["gold_nlg_half_ratio_of_means", "gold_eur_half_ratio_of_means"],
        "C_nvm_grams": ["nvm_grams_nlg_era", "nvm_grams_eur_era", "nvm_grams_eur_retro"],
        "D_cbs_grams": ["cbs_grams_eur_retro_halfyear", "cbs_grams_eur_halfyear", "cbs_grams_1995_1998_retro_monthly",
                        "cbs_grams_1999_monthly", "cbs_grams_2000_onward_monthly"],
    }
    return {name: lineage_closure(g, [g[i] for i in ids if i in g]) for name, ids in spec.items()}


def write_bundles(bundle_map: dict, out) -> dict:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    digests = {}
    for name, series in bundle_map.items():
        raw = hb.bundle_bytes(hb.build_bundle(series))
        path = out / f"hist10_{name}.json"
        path.write_bytes(raw)
        digests[path.name] = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "series": len(series),
                              "ids": [s.series_id for s in series if s.layer != "source"]}
    return digests


# ------------------------------------------------------------------ pure helpers used by analysis and tests
def fr(x) -> Fraction:
    return Fraction(x) if not isinstance(x, Fraction) else x


def month_of(d) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def half_of(month: str) -> str:
    return f"{month[:4]}-H{1 if int(month[5:7]) <= 6 else 2}"


def half_months(half: str) -> list:
    first = 1 if half.endswith("H1") else 7
    return [f"{half[:4]}-{m:02d}" for m in range(first, first + 6)]


def monthly_rule(daily: dict, rule: str, min_share=Fraction(1, 2)) -> dict:
    """{date: number} -> {month: Fraction} with rule mean/last/first/median; months below min_share of calendar days dropped."""
    from calendar import monthrange
    groups = {}
    for d in sorted(daily):
        groups.setdefault(month_of(d), []).append(fr(daily[d]))
    out = {}
    for m, v in groups.items():
        if Fraction(len(v), monthrange(int(m[:4]), int(m[5:7]))[1]) < min_share:
            continue
        s = sorted(v)
        out[m] = {"mean": sum(v) / len(v), "last": v[-1], "first": v[0],
                  "median": s[len(s) // 2] if len(s) % 2 else (s[len(s) // 2 - 1] + s[len(s) // 2]) / 2}[rule]
    return out


def grams(house_local, gold_local_per_oz) -> Fraction:
    """house and gold in the SAME currency -> grams of gold per house."""
    return fr(house_local) * G_PER_OZ / fr(gold_local_per_oz)


def half_gold_methods(wb: dict, fed_daily: dict, ecb_daily: dict, half: str) -> dict:
    """Gold local price per troy ounce for one half-year under each aggregation alternative (exact Fractions).

    Currency era follows the half-year: NLG up to 1998-H2, observed EUR from 1999-H1. A method is None when its
    inputs are incomplete (never partial).
    """
    ms = half_months(half)
    nlg = half <= "1998-H2"
    daily = fed_daily if nlg else ecb_daily
    mean_m = monthly_rule(daily, "mean")
    last_m = monthly_rule(daily, "last")
    first_m = monthly_rule(daily, "first")
    if any(m not in wb or m not in mean_m for m in ms):
        return {k: None for k in ("M1_mean_of_monthly_local", "M2_ratio_of_half_means", "M2d_daily_weighted_fx",
                                  "M3_end_of_half", "M4_start_of_half", "M6_fx_last_of_month", "M7_fx_first_of_month")}

    def conv(usd, fx):
        return fr(usd) * fx if nlg else fr(usd) / fx

    usd_mean = sum(fr(wb[m]) for m in ms) / 6
    days = [fr(v) for d, v in sorted(daily.items()) if half_of(month_of(d)) == half]
    local_mean_m = [conv(wb[m], mean_m[m]) for m in ms]
    res = {"M1_mean_of_monthly_local": sum(local_mean_m) / 6,
           "M2_ratio_of_half_means": conv(usd_mean, sum(mean_m[m] for m in ms) / 6),
           "M2d_daily_weighted_fx": conv(usd_mean, sum(days) / len(days)),
           "M3_end_of_half": local_mean_m[-1], "M4_start_of_half": local_mean_m[0]}
    res["M6_fx_last_of_month"] = sum(conv(wb[m], last_m[m]) for m in ms if m in last_m) / 6 if all(m in last_m for m in ms) else None
    res["M7_fx_first_of_month"] = sum(conv(wb[m], first_m[m]) for m in ms if m in first_m) / 6 if all(m in first_m for m in ms) else None
    return res


def dev_summary(devs: dict) -> dict:
    """{period: Fraction relative deviation} -> max / mean / median absolute deviation in percent (4 places)."""
    if not devs:
        return {"n": 0}
    a = sorted(abs(v) for v in devs.values())
    pct = lambda f: f"{float(f * 100):.4f}"  # noqa: E731
    top = max(devs, key=lambda k: abs(devs[k]))
    return {"n": len(devs), "max_abs_pct": pct(a[-1]), "max_at": top, "mean_abs_pct": pct(sum(a) / len(a)),
            "median_abs_pct": pct(a[len(a) // 2]), "mean_signed_pct": pct(sum(devs.values()) / len(devs))}


def era_of(half: str) -> str:
    return "1975-1978" if half <= "1978-H2" else "1979-1998" if half <= "1998-H2" else "1999-2000"


# ------------------------------------------------------------------ real-data run (CI only)
def run(args):  # noqa: C901
    from tools import hist_02_acquire as acq
    from tools import hist_07_collect as c7
    from tools import hist_04_fx as fx
    from tools import hist_04_gold_nlg as gn
    from tools import hist_08_gold_validate as gv

    signal.signal(signal.SIGALRM, gv._alarm)
    D, S = gv.load(acq.fetch, args.workbook)
    R = {"caveat": CAVEAT, "missing_sources": S["missing_sources"], "defects": S["defects"], "flags": S["flags"]}
    need = ("wb", "fed_daily", "ecb_d")
    if any(k not in D for k in need):
        R["status"] = "INCOMPLETE"
        R["missing"] = [k for k in need if k not in D]
        return R
    wb_sha = S["sources"][c7.WB_ID]["sha256"]
    fed_sha = hashlib.sha256("".join(sorted(S["sources"][i]["sha256"] for i in gn.FED_IDS if i in S["sources"])).encode()).hexdigest()
    ecb_sha = S["sources"][fx.ECB_DAILY]["sha256"]
    R["source_hashes"] = {"world_bank_workbook": wb_sha, "fed_files_combined": fed_sha, "ecb_daily": ecb_sha,
                          "cbs_zip": h9.CBS_ZIP_SHA256, "nvm_csv": h9.NVM_CSV_SHA256}
    gold_usd = gold_usd_series(D["wb"], wb_sha)
    fed = fx_daily_series("fed_nlg_per_usd_daily", D["fed_daily"], currency="NLG", unit="NLG_per_USD",
                          source_id="fed_h10", raw_sha=fed_sha, definition="fed_h10_nlg_per_usd_daily")
    ecb = fx_daily_series("ecb_usd_per_eur_daily", D["ecb_d"], currency="USD", unit="USD_per_EUR",
                          source_id="ecb_exr_d_usd", raw_sha=ecb_sha, definition="ecb_ref_usd_per_eur_daily")
    gold = build_gold(gold_usd, fed, ecb)
    inputs = Path(args.inputs)
    h9.verify_package(inputs)
    nvm = h9.nvm_nlg_series(h9.read_nvm_csv(inputs), h9.NVM_CSV_SHA256)
    cbs = h9.cbs_series(h9.read_cbs_zip(inputs))
    fixture, csv_series = hb.cbs_1995_1999_series(), hb.cbs_2000_series(args.cbs_csv)
    houses = build_housing_grams(gold, nvm, cbs["price"], cbs["count"], fixture, csv_series)
    allseries = all_series(gold, houses, nvm, *cbs.values(), fixture, csv_series)
    bm = bundles(allseries)
    digests = write_bundles(bm, args.bundles_out) if args.bundles_out else {n: {"sha256": hashlib.sha256(hb.bundle_bytes(hb.build_bundle(s))).hexdigest(), "series": len(s)} for n, s in bm.items()}
    R["bundles"] = digests
    R["bundle_validation"] = {n: len(hm.validate_bundle(json.loads(hb.bundle_bytes(hb.build_bundle(s))))) for n, s in bm.items()}
    R["coverage"] = coverage_matrix(gold, houses, nvm, cbs)
    R["independent"] = independent_check(D, nvm, cbs, houses, fixture, csv_series)
    R["aggregation"] = aggregation_impact(D, nvm, cbs)
    R["transition"] = transition(D, houses, gold)
    R["retro_vs_nlg_exact"] = retro_vs_nlg(houses)
    R["monthly_mean_vs_provider"] = ecb_model_vs_provider(gold, D)
    if args.production_json:
        R["production_comparison"] = compare_production(houses["cbs_grams_2000_onward_monthly"], args.production_json)
    R["status"] = "COMPLETE_RESEARCH" if not S["missing_sources"] and not S["defects"] else "PARTIAL"
    if args.csv_out:
        write_derived_table(houses, args.csv_out)
    return R


def coverage_matrix(gold, houses, nvm, cbs) -> dict:
    out = {}
    for name in ("gold_usd_monthly", "fed_nlg_per_usd_daily", "ecb_usd_per_eur_daily", "fed_nlg_per_usd_monthly",
                 "ecb_usd_per_eur_monthly", "gold_nlg_monthly", "gold_eur_monthly", "gold_eur_retro_monthly"):
        s = gold[name]
        rows = [r for r in (s.observations if s.layer == "source" else s.points) if r.value is not None]
        nulls = [r.period for r in (s.points if s.layer != "source" else ()) if r.value is None]
        out[name] = {"first": rows[0].period, "last": rows[-1].period, "n": len(rows), "null_periods": nulls[:6], "n_null": len(nulls)}
    for name, s in list(houses.items()) + [("nvm_median_nlg_halfyear", nvm)] + [(k, v) for k, v in cbs.items()]:
        rows = [r for r in (s.observations if s.layer == "source" else s.points) if r.value is not None]
        nulls = [r.period for r in (s.points if s.layer != "source" else ()) if r.value is None]
        out[name] = {"first": rows[0].period, "last": rows[-1].period, "n": len(rows), "n_null": len(nulls)}
    return out


def _nvm_local(nvm: hm.Series, half: str):
    v = {o.period: o.value for o in nvm.observations}
    return fr(v[half]) if half in v else None


def independent_check(D, nvm, cbs, houses, fixture, csv_series) -> dict:
    """Exact Fraction recomputation (from the raw dicts) of representative half-years against the bundle values."""
    out = {}
    cbs_half = {p.period: p.value for p in houses["cbs_avg_price_eur_halfyear"].points}
    nvm_g = {**{p.period: p.value for p in houses["nvm_grams_nlg_era"].points}, **{p.period: p.value for p in houses["nvm_grams_eur_era"].points}}
    cbs_g = {**{p.period: p.value for p in houses["cbs_grams_eur_retro_halfyear"].points}, **{p.period: p.value for p in houses["cbs_grams_eur_halfyear"].points}}
    for half in ("1975-H1", "1980-H2", "1995-H1", "1998-H2", "1999-H1", "2000-H2"):
        m = half_gold_methods(D["wb"], D["fed_daily"], D["ecb_d"], half)["M1_mean_of_monthly_local"]
        entry = {}
        if m is not None:
            nl = _nvm_local(nvm, half)
            house = nl if half <= "1998-H2" else nl / RATE
            exact = grams(house, m)
            entry["nvm_exact"] = f"{float(exact):.6f}"
            entry["nvm_model"] = f"{float(nvm_g[half]):.6f}" if half in nvm_g else None
            entry["nvm_rel_diff"] = f"{float(abs(Fraction(nvm_g[half]) / exact - 1)):.3e}" if half in nvm_g else None
            if half in cbs_half and cbs_half[half] is not None:
                gold_eur = m / RATE if half <= "1998-H2" else m
                exact_c = grams(Fraction(cbs_half[half]), gold_eur)
                entry["cbs_exact_given_model_half_mean"] = f"{float(exact_c):.6f}"
                entry["cbs_model"] = f"{float(cbs_g[half]):.6f}"
                entry["cbs_rel_diff"] = f"{float(abs(Fraction(cbs_g[half]) / exact_c - 1)):.3e}"
        out[half] = entry
    return out


SHORT = {"M2_ratio_of_half_means": "M2", "M2d_daily_weighted_fx": "M2d", "M3_end_of_half": "M3", "M4_start_of_half": "M4",
         "M6_fx_last_of_month": "M6", "M7_fx_first_of_month": "M7"}


def aggregation_impact(D, nvm, cbs) -> dict:
    """NVM grams per half-year under each aggregation alternative vs M1; plus CBS transaction-weighted gold (M5)."""
    methods = ("M2_ratio_of_half_means", "M2d_daily_weighted_fx", "M3_end_of_half", "M4_start_of_half", "M6_fx_last_of_month",
               "M7_fx_first_of_month")
    halves = [f"{y}-H{h}" for y in range(1975, 2001) for h in (1, 2)]
    per = {m: {} for m in methods}
    by_era = {m: {} for m in methods}
    sample = {}
    for half in halves:
        gm = half_gold_methods(D["wb"], D["fed_daily"], D["ecb_d"], half)
        base = gm["M1_mean_of_monthly_local"]
        if base is None:
            continue
        nl = _nvm_local(nvm, half)
        house = nl if half <= "1998-H2" else nl / RATE
        g1 = grams(house, base)
        if half in ("1975-H1", "1980-H2", "1990-H1", "1995-H1", "1998-H2", "1999-H1", "2000-H2"):
            sample[half] = {"M1": f"{float(g1):.2f}", **{SHORT[k]: (f"{float(grams(house, v)):.2f}" if v else None)
                                                          for k, v in gm.items() if k != "M1_mean_of_monthly_local"}}
        for m in methods:
            if gm[m] is not None:
                dev = grams(house, gm[m]) / g1 - 1
                per[m][half] = dev
                by_era[m].setdefault(era_of(half), {})[half] = dev
    out = {"all_periods": {m: dev_summary(per[m]) for m in methods},
           "by_era": {m: {e: dev_summary(v) for e, v in sorted(by_era[m].items())} for m in methods}, "grams_sample": sample}
    # M5: CBS half-year mean with transaction-weighted gold vs M1 (1995-H1..2000-H2)
    counts = h9_counts(cbs)
    price = {o.period: Fraction(o.value) for o in cbs["price"].observations}
    dev5 = {}
    for half in halves:
        if half < "1995-H1":
            continue
        ms = half_months(half)
        nlg = half <= "1998-H2"
        mean_m = monthly_rule(D["fed_daily"] if nlg else D["ecb_d"], "mean")
        if any(m not in D["wb"] or m not in mean_m for m in ms):
            continue
        loc = [fr(D["wb"][m]) * mean_m[m] / RATE if nlg else fr(D["wb"][m]) / mean_m[m] for m in ms]
        total = sum(counts[m] for m in ms)
        cbs_h = sum(price[m] * counts[m] for m in ms) / total
        g1 = grams(cbs_h, sum(loc) / 6)
        g5 = grams(cbs_h, sum(l * counts[m] for l, m in zip(loc, ms)) / total)
        dev5[half] = g5 / g1 - 1
    out["M5_transaction_weighted_gold_vs_M1_cbs"] = dev_summary(dev5)
    return out


def h9_counts(cbs) -> dict:
    return {o.period: Fraction(o.value) for o in cbs["count"].observations}


def transition(D, houses, gold) -> dict:
    """The 1998/1999 currency transition: steps in gold, NVM grams and CBS grams across the boundary."""
    def step(a, b):
        return f"{float((Fraction(b) / Fraction(a) - 1) * 100):.4f}" if a and b else None
    nvm = {**{p.period: p.value for p in houses["nvm_grams_nlg_era"].points}, **{p.period: p.value for p in houses["nvm_grams_eur_era"].points}}
    m_retro = {p.period: p.value for p in gold["gold_eur_retro_monthly"].points}
    m_eur = {p.period: p.value for p in gold["gold_eur_monthly"].points}
    cbs_r = {p.period: p.value for p in houses["cbs_grams_1995_1998_retro_monthly"].points}
    cbs_1999 = {p.period: p.value for p in houses["cbs_grams_1999_monthly"].points}
    return {"gold_eur_1998-12_retro_to_1999-01_observed_pct": step(m_retro.get("1998-12"), m_eur.get("1999-01")),
            "nvm_grams_1998-H2_to_1999-H1_pct": step(nvm.get("1998-H2"), nvm.get("1999-H1")),
            "cbs_grams_1998-12_retro_to_1999-01_pct": step(cbs_r.get("1998-12"), cbs_1999.get("1999-01"))}


def retro_vs_nlg(houses) -> dict:
    a = {p.period: p.value for p in houses["nvm_grams_nlg_era"].points if p.value is not None}
    b = {p.period: p.value for p in houses["nvm_grams_eur_retro"].points if p.value is not None and p.period in a}
    worst = max((abs(Fraction(a[p]) / Fraction(b[p]) - 1) for p in b), default=None)
    return {"periods_compared": len(b), "max_rel_diff": f"{float(worst):.3e}" if worst is not None else None}


def ecb_model_vs_provider(gold, D) -> dict:
    """Model monthly mean of ECB daily vs the provider monthly series (HIST-08: equal by definition)."""
    if "ecb_m" not in D:
        return {"status": "NOT_AVAILABLE"}
    model = {p.period: Fraction(p.value) for p in gold["ecb_usd_per_eur_monthly"].points if p.value is not None}
    prov = {m: Fraction(v) for m, v in D["ecb_m"].items() if m in model}
    worst = max((abs(model[m] / prov[m] - 1) for m in prov), default=None)
    return {"months": len(prov), "max_rel_diff": f"{float(worst):.3e}" if worst is not None else None}


def compare_production(series: hm.Series, path) -> dict:
    rows = json.loads(Path(path).read_text(encoding="utf-8"))["data"]
    prod = {r["period"]: r["gold_grams_per_house"] for r in rows if r.get("gold_grams_per_house") is not None}
    mine = {p.period: Fraction(p.value) for p in series.points if p.value is not None}
    devs = {m: abs(mine[m] / Fraction(prod[m]) - 1) for m in mine if m in prod}
    worst = max(devs, key=devs.get) if devs else None
    return {"months_compared": len(devs), "months_only_in_research": len(set(mine) - set(prod)),
            "max_rel_diff": f"{float(devs[worst]):.3e}" if worst else None, "max_at": worst}


def write_derived_table(houses, path):
    """Derived half-year grams only (no raw third-party values)."""
    rows = []
    for name in ("nvm_grams_nlg_era", "nvm_grams_eur_era", "cbs_grams_eur_retro_halfyear", "cbs_grams_eur_halfyear"):
        for p in houses[name].points:
            rows.append({"series": name, "period": p.period, "grams_of_gold": "" if p.value is None else f"{p.value:.6f}",
                         "quality": p.quality})
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["series", "period", "grams_of_gold", "quality"])
        w.writeheader()
        w.writerows(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description="HIST-10 housing in grams of gold (research only)")
    ap.add_argument("--inputs", help="pinned HIST-09 inputs directory")
    ap.add_argument("--cbs-csv", help="committed CBS csv (read only)")
    ap.add_argument("--production-json", help="public monthly json (read only), for a consistency comparison")
    ap.add_argument("--workbook")
    ap.add_argument("--summary-out")
    ap.add_argument("--csv-out")
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
    except (hm.ModelError, Hist10Error) as exc:
        out.write_text(json.dumps({"status": "FAILED", "error": f"{type(exc).__name__}: {str(exc)[:400]}"}, indent=1) + "\n")
        print("DEFECT", type(exc).__name__, str(exc)[:400])
        return 1
    out.write_text(json.dumps(R, indent=1, sort_keys=True, default=str) + "\n")
    print("STATUS", R["status"], "missing", [m["source_id"] for m in R["missing_sources"]], "defects", len(R["defects"]))
    return 0 if R["status"] != "FAILED" else 1


if __name__ == "__main__":
    sys.exit(main())
