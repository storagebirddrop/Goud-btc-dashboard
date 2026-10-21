"""HIST-08 research only: independent validation of the HIST-07 gold constructions (C1, C3, C4).

Nothing here is a decision, a methodology or a publication. The tool reads public sources through the hardened
tools.hist_02_acquire.fetch path (CI only), keeps raw bytes in memory, and writes aggregates plus a small derived
overlap table (36 rows) only. It never touches data/, etl/ outputs or frontend/.

Independence: the statistics below (aggregation rules, percentiles, overlap deviations, rounding bounds, sensitivity)
are NEW exact-arithmetic code on fractions.Fraction. They do not call the functions under check
(hist_07_gold_constructions.c1/c3/c4/overlap_compare/deviation_stats, hist_07_collect.collect). Those are called only
afterwards on the same inputs to compare results (`overlap_agreement`). File parsing (Fed text, BIS/IMF/CBS formats,
the World Bank workbook) reuses the existing parsers; parser faults are therefore NOT independently covered, which the
report states.

Missing data stays missing: a source that cannot be fetched is listed in missing_sources and the dependent sections
are skipped (not_performed); nothing is interpolated, forward-filled or replaced by another source.
"""
import argparse
import csv
import hashlib
import json
import re
import signal
import sys
from collections import Counter
from datetime import date
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

from tools import hist_02_acquire as acq
from tools import hist_03_worldbank_validate as wbv
from tools import hist_04_fx as fx
from tools import hist_04_gold_nlg as gn
from tools import hist_03_second_source as ss
from tools import hist_04_nlg_sources as ns
from tools import hist_07_collect as c7
from tools import hist_07_gold_constructions as hc

RATE = Fraction(220371, 100000)  # NLG per EUR, Council Regulation (EC) 2866/98
G_PER_OZ = Fraction(311034768, 10 ** 7)
CAVEAT = "research only; nothing approved; rights UNVERIFIED; no raw third-party bytes in artifacts"
PERIODS = {"1960-67": ("1960-01", "1967-12"), "1968-74": ("1968-01", "1974-12"), "1975-78": ("1975-01", "1978-12"),
           "1979-89": ("1979-01", "1989-12"), "1990-98": ("1990-01", "1998-12"), "1999-2001": ("1999-01", "2001-12"),
           "2002-2026": ("2002-01", "2099-12")}
# Numbers reported in docs/research/HIST_07_GOLD_NLG.md section 3 (percent), used only to test reproduction.
REPORTED_HIST07 = {
    "fed_euro_noon": {"median_abs_pct": "0.0582", "mean_signed_pct": "0.0324", "p95_abs_pct": "0.3035", "max_abs_pct": "0.3074"},
    "bis": {"median_abs_pct": "0.0110", "mean_signed_pct": "0.0162", "p95_abs_pct": "0.0410", "max_abs_pct": "0.0442"},
    "cbs": {"median_abs_pct": "0.1180", "mean_signed_pct": "-0.0207", "p95_abs_pct": "0.4223", "max_abs_pct": "0.5338"},
    "fed_long_1999_2011": {"months": 149, "median_abs_pct": "0.0509", "mean_signed_pct": "-0.0144", "p95_abs_pct": "0.2404", "max_abs_pct": "0.4591"},
}
PERIOD_RE = re.compile(r"\d{4}-(0[1-9]|1[0-2])")


class ValidationDefect(ValueError):
    """Input or logic defect (fail closed)."""


# ------------------------------------------------------------------ exact helpers (new code)
def fr(x):
    """Positive finite exact Fraction from Decimal/int/str/Fraction. Floats are rejected."""
    if isinstance(x, (float, bool)):
        raise ValidationDefect("FLOAT_OR_BOOL_INPUT")
    try:
        f = x if isinstance(x, Fraction) else Fraction(x)
    except (ValueError, TypeError, ZeroDivisionError, OverflowError) as exc:  # NaN, Infinity, garbage text
        raise ValidationDefect("NONFINITE_OR_UNPARSEABLE_INPUT") from exc
    if f <= 0:
        raise ValidationDefect("NONPOSITIVE_INPUT")
    return f


def dec_str(f, places=6):
    """Fraction -> fixed-point string, round half to even (exact)."""
    n = round(Fraction(f) * 10 ** places)
    return format(Decimal(n).scaleb(-places), "f")


def pct_str(f, places=6):
    return dec_str(Fraction(f) * 100, places)


def month_key(d):
    return f"{d.year:04d}-{d.month:02d}"


def months_between(a, b):
    if not (PERIOD_RE.fullmatch(a) and PERIOD_RE.fullmatch(b)) or a > b:
        raise ValidationDefect("BAD_MONTH_RANGE")
    y, m = map(int, a.split("-"))
    ey, em = map(int, b.split("-"))
    out = []
    while (y, m) <= (ey, em):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def median_exact(vals):
    s = sorted(vals)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def nearest_rank(sorted_vals, p):
    """Nearest-rank percentile (the definition used by HIST-07): the ceil(p*n/100)-th smallest value."""
    n = len(sorted_vals)
    return sorted_vals[max(1, -(-p * n // 100)) - 1]


def linear_pct(sorted_vals, p):
    """Linear interpolation between closest ranks (numpy default); shown to expose definition sensitivity."""
    n = len(sorted_vals)
    pos = Fraction(p, 100) * (n - 1)
    lo = int(pos)
    hi = min(lo + 1, n - 1)
    return sorted_vals[lo] + (pos - lo) * (sorted_vals[hi] - sorted_vals[lo])


def dev_stats(devs):
    """devs {month: Fraction relative deviation} -> aggregates in percent (strings)."""
    if not devs:
        return {"months": 0}
    n = len(devs)
    absd = sorted(abs(v) for v in devs.values())
    sgn = sorted(devs.values())
    worst = sorted(devs.items(), key=lambda kv: (-abs(kv[1]), kv[0]))[:3]
    return {"months": n, "mean_signed_pct": pct_str(sum(sgn) / n), "median_signed_pct": pct_str(median_exact(sgn)),
            "median_abs_pct": pct_str(nearest_rank(absd, 50)), "median_abs_pct_linear": pct_str(linear_pct(absd, 50)),
            "p95_abs_pct": pct_str(nearest_rank(absd, 95)), "p95_abs_pct_linear": pct_str(linear_pct(absd, 95)),
            "max_abs_pct": pct_str(absd[-1]), "worst": [[m, pct_str(v)] for m, v in worst]}


def rel(a, b):
    return (fr(a) - fr(b)) / fr(b)


def devs_between(a, b, months):
    """(a - b) / b on months present in both; no filling."""
    return {m: rel(a[m], b[m]) for m in months if m in a and m in b}


# ------------------------------------------------------------------ aggregation
RULES = ("mean", "last", "first", "median")


def aggregate(points, rule="mean", min_obs=1):
    """Daily {date: number} -> ({month: Fraction}, {month: n_obs}); months with fewer than min_obs are dropped."""
    groups = {}
    for d in sorted(points):
        groups.setdefault(month_key(d), []).append(fr(points[d]))
    out, counts = {}, {}
    for k, v in groups.items():
        if len(v) < min_obs:
            continue
        if rule == "mean":
            out[k] = sum(v) / len(v)
        elif rule == "last":
            out[k] = v[-1]
        elif rule == "first":
            out[k] = v[0]
        elif rule == "median":
            out[k] = median_exact(v)
        else:
            raise ValidationDefect("UNKNOWN_RULE " + rule)
        counts[k] = len(v)
    return out, counts


# ------------------------------------------------------------------ direction and units
def assert_direction(header_text, values, expect="NLG_PER_USD"):
    """Direction from header text AND value range. Conflict, unknown or != expect raises."""
    t = (header_text or "").upper()
    txt_nlg_per_usd = bool(re.search(r"GUILDERS?\s*/\s*(U\.?S\.?\s*\$|US\$|USD)", t))
    txt_usd_per_nlg = bool(re.search(r"(U\.?S\.?\s*\$|US\$|USD)\s*/\s*GUILDERS?", t))
    if not values:
        raise ValidationDefect("NO_VALUES")
    med = median_exact([fr(v) for v in values])
    by_value = "NLG_PER_USD" if 1 <= med <= 6 else ("USD_PER_NLG" if Fraction(15, 100) <= med <= 1 else None)
    by_text = "NLG_PER_USD" if txt_nlg_per_usd and not txt_usd_per_nlg else ("USD_PER_NLG" if txt_usd_per_nlg and not txt_nlg_per_usd else None)
    if by_text and by_value and by_text != by_value:
        raise ValidationDefect("DIRECTION_TEXT_VS_VALUE_CONFLICT")
    got = by_text or by_value
    if got is None:
        raise ValidationDefect("DIRECTION_UNDETERMINED")
    if got != expect:
        raise ValidationDefect(f"DIRECTION_{got}_NOT_{expect}")
    return {"direction": got, "by_text": by_text, "by_value": by_value, "median_value": dec_str(med, 4)}


def continuity_direction_test(fed_monthly, ecb_monthly, fed_months, ecb_months):
    """Empirical direction check across the euro changeover: implied USD per EUR from the Fed series in the last
    months of 1998 (2.20371 / NLG per USD) must be close to the ECB level of the first months of 1999; the inverted
    reading (2.20371 x value) must not be."""
    f = [fed_monthly[m] for m in fed_months if m in fed_monthly]
    e = [ecb_monthly[m] for m in ecb_months if m in ecb_monthly]
    if not f or not e:
        return None
    fe, ee = sum(f) / len(f), sum(e) / len(e)
    correct = RATE / fe  # NLG per USD reading
    inverted = RATE * fe  # USD per NLG reading
    return {"fed_months": len(f), "ecb_months": len(e), "implied_usd_per_eur_if_nlg_per_usd": dec_str(correct, 5),
            "implied_usd_per_eur_if_usd_per_nlg": dec_str(inverted, 5), "ecb_usd_per_eur": dec_str(ee, 5),
            "dev_pct_if_nlg_per_usd": pct_str(correct / ee - 1, 4), "dev_pct_if_usd_per_nlg": pct_str(inverted / ee - 1, 4),
            "direction_confirmed": abs(correct / ee - 1) < Fraction(5, 100) and abs(inverted / ee - 1) > Fraction(30, 100)}


def c1_f(usd_oz, nlg_per_usd):
    return fr(usd_oz) * fr(nlg_per_usd)


def c3_f(c1_nlg_oz):
    return fr(c1_nlg_oz) / RATE


def c4_f(usd_oz, usd_per_eur):
    return fr(usd_oz) / fr(usd_per_eur)


def nlg_per_usd_from_usd_per_eur(x):
    return RATE / fr(x)


def grams_per_home(house, gold_per_oz):
    """house and gold in the SAME currency -> grams of gold per home."""
    return fr(house) * G_PER_OZ / fr(gold_per_oz)


# ------------------------------------------------------------------ overlap recompute
def overlap_devs(usd_oz, alt_usd_per_eur, ecb_usd_per_eur, months):
    """C3 built from an alternative euro-era FX (via the fixed cross NLG per USD = 2.20371 / x) against C4 built from the ECB.
    Full formulas, then asserted equal to the closed form ecb/alt - 1 (exact). Returns (devs, missing)."""
    devs, missing = {}, []
    for m in months:
        if m in usd_oz and m in alt_usd_per_eur and m in ecb_usd_per_eur:
            nlg = nlg_per_usd_from_usd_per_eur(alt_usd_per_eur[m])
            d = c3_f(c1_f(usd_oz[m], nlg)) / c4_f(usd_oz[m], ecb_usd_per_eur[m]) - 1
            if d != fr(ecb_usd_per_eur[m]) / fr(alt_usd_per_eur[m]) - 1:
                raise ValidationDefect("CLOSED_FORM_MISMATCH " + m)
            devs[m] = d
        else:
            missing.append(m)
    return devs, missing


def overlap_devs_from_nlg(usd_oz, alt_nlg_per_usd, ecb_usd_per_eur, months):
    """Same test when the alternative source is quoted directly in NLG per USD (BIS-derived, CBS)."""
    devs, missing = {}, []
    for m in months:
        if m in usd_oz and m in alt_nlg_per_usd and m in ecb_usd_per_eur:
            devs[m] = c3_f(c1_f(usd_oz[m], alt_nlg_per_usd[m])) / c4_f(usd_oz[m], ecb_usd_per_eur[m]) - 1
        else:
            missing.append(m)
    return devs, missing


def compare_with_hist07(usd_dec, nlg_dec, ecb_dec, months, mine_devs):
    """Run the HIST-07 functions on the same inputs and compare with the independent result."""
    c4q, _ = hc.c4(usd_dec, ecb_dec, months)
    c1q, _ = hc.c1(usd_dec, nlg_dec, months)
    devs, _ = hc.overlap_compare(hc.c3(c1q), c4q, months)
    st = hc.deviation_stats(devs)
    mine = dev_stats(mine_devs)
    keys = ("mean_signed_pct", "median_abs_pct", "p95_abs_pct", "max_abs_pct")
    diffs = {k: [mine.get(k), st.get(k)] for k in keys if mine.get(k) is not None and st.get(k) is not None
             and Decimal(mine[k]) != Decimal(st[k])}
    month_diff = max((abs(mine_devs[m] - Fraction(devs[m])) for m in devs if m in mine_devs), default=Fraction(0))
    same_months = sorted(devs) == sorted(mine_devs)
    return {"months_hist07": st.get("months", 0), "months_mine": mine.get("months", 0), "same_month_set": same_months,
            "stat_differences": diffs, "max_abs_month_dev_difference": f"{float(month_diff):.3e}",
            "agree": same_months and not diffs and month_diff < Fraction(1, 10 ** 25)}


def reproduces_reported(mine, reported):
    out = {}
    for k, v in reported.items():
        if k == "months":
            out[k] = mine.get("months") == v
        else:
            got = mine.get(k)
            out[k] = got is not None and abs(Decimal(got) - Decimal(v)) <= Decimal("0.00006")
    return out


# ------------------------------------------------------------------ World Bank precision, regime, rounding
def wb_precision(wb):
    out = {}
    for name, (a, b) in PERIODS.items():
        vs = [(m, v) for m, v in sorted(wb.items()) if a <= m <= b]
        if not vs:
            continue
        vals = [fr(v) for _, v in vs]
        non_int = sum(1 for _, v in vs if v != v.to_integral_value())
        out[name] = {"n": len(vs), "non_integer": non_int, "min": dec_str(min(vals), 4), "median": dec_str(median_exact(vals), 4),
                     "max": dec_str(max(vals), 4), "bound_pct_at_min": pct_str(Fraction(1, 2) / min(vals), 4),
                     "bound_pct_at_median": pct_str(Fraction(1, 2) / median_exact(vals), 4),
                     "expected_mean_abs_error_pct_if_uniform": pct_str(sum(Fraction(1, 4) / v for v in vals) / len(vals), 4)}
    return out


def rounding_vs_reference(wb, ref, months):
    """Is the whole-dollar World Bank value consistent with a rounded copy of a decimal reference series?"""
    com = [m for m in months if m in wb and m in ref]
    if not com:
        return {"months": 0}
    d = {m: fr(wb[m]) - fr(ref[m]) for m in com}
    ab = sorted(abs(v) for v in d.values())
    rounded_equal = sum(1 for m in com if fr(wb[m]) == (fr(ref[m]) + Fraction(1, 2)) // 1)
    worst = max(com, key=lambda m: (abs(d[m]), m))
    return {"months": len(com), "within_half_usd": sum(1 for v in ab if v <= Fraction(1, 2)), "within_one_usd": sum(1 for v in ab if v <= 1),
            "gt_one_usd": sum(1 for v in ab if v > 1), "wb_equals_round_half_up_of_ref": rounded_equal,
            "mean_signed_usd": dec_str(sum(d.values()) / len(com), 4), "median_abs_usd": dec_str(nearest_rank(ab, 50), 4),
            "p95_abs_usd": dec_str(nearest_rank(ab, 95), 4), "max_abs_usd": dec_str(ab[-1], 4), "max_month": worst}


def regime_scan(series, a, b):
    ms = [m for m in sorted(series) if a <= m <= b]
    if not ms:
        return {"months": 0}
    best, cur, prev, ends, first_change = 0, 0, None, None, None
    for m in ms:
        if series[m] == prev:
            cur += 1
        else:
            cur, prev = 1, series[m]
            if first_change is None and m != ms[0]:
                first_change = m
        if cur > best:
            best, ends = cur, m
    return {"months": len(ms), "first_value": str(series[ms[0]]), "first_change_month": first_change, "longest_equal_run": best,
            "longest_run_ends": ends, "distinct_values": len({series[m] for m in ms}),
            "months_equal_first_value": sum(1 for m in ms if series[m] == series[ms[0]])}


def top_steps(series, a, b, n=5):
    ms = [m for m in sorted(series) if a <= m <= b]
    st = [(ms[i], fr(series[ms[i]]) / fr(series[ms[i - 1]]) - 1) for i in range(1, len(ms))]
    st.sort(key=lambda kv: (-abs(kv[1]), kv[0]))
    return [[m, pct_str(v, 3)] for m, v in st[:n]]


def decimals_distribution(values, top=4):
    c = Counter(max(0, -v.as_tuple().exponent) for v in values if isinstance(v, Decimal))
    return dict(c.most_common(top))


def closeness(a_nlg, b_nlg, months):
    """Fingerprint: how many months two NLG-per-USD series agree within 5e-5, 1e-4, 1e-3 (absolute)."""
    com = [m for m in months if m in a_nlg and m in b_nlg]
    ds = [abs(fr(a_nlg[m]) - fr(b_nlg[m])) for m in com]
    return {"months": len(com), "le_0_00005": sum(1 for d in ds if d <= Fraction(5, 10 ** 5)), "le_0_0001": sum(1 for d in ds if d <= Fraction(1, 10 ** 4)),
            "le_0_001": sum(1 for d in ds if d <= Fraction(1, 10 ** 3))}


# ------------------------------------------------------------------ sensitivity
def aggregation_sensitivity(daily, months_by_period):
    """Relative change of the monthly FX (hence of C1 and, inversely, of grams per home) when the monthly value is the
    last/first/median daily observation instead of the mean. Gold is the same on both sides, so it cancels."""
    base, _ = aggregate(daily, "mean")
    out = {}
    for rule in RULES[1:]:
        alt, _ = aggregate(daily, rule)
        out[rule] = {name: dev_stats(devs_between(alt, base, ms)) for name, ms in months_by_period.items()}
    return out


def product_of_means_effect(gold_daily, fx_daily, months):
    """A = mean(gold) x mean(fx) vs B = mean(gold x fx) on common days of each month."""
    byday = {d: (fr(gold_daily[d]), fr(fx_daily[d])) for d in gold_daily if d in fx_daily}
    groups = {}
    for d, gv in byday.items():
        groups.setdefault(month_key(d), []).append(gv)
    devs = {}
    for m in months:
        v = groups.get(m)
        if v:
            n = len(v)
            a = (sum(x for x, _ in v) / n) * (sum(y for _, y in v) / n)
            b = sum(x * y for x, y in v) / n
            devs[m] = a / b - 1
    return dev_stats(devs)


def fixed_rate_sensitivity(c1_nlg_oz, house_nlg, delta=Fraction(1, 100)):
    """Effect of a mis-stated conversion rate R' = R(1+delta) on C3 and on grams per home (exact)."""
    out = {}
    r2 = RATE * (1 + delta)
    c3_ok, c3_bad = fr(c1_nlg_oz) / RATE, fr(c1_nlg_oz) / r2
    out["c3_level_change_pct"] = pct_str(c3_bad / c3_ok - 1, 6)
    g_ok = grams_per_home(fr(house_nlg) / RATE, c3_ok)
    g_both = grams_per_home(fr(house_nlg) / r2, c3_bad)  # house and gold converted at the same R'
    g_fixed_house = grams_per_home(fr(house_nlg) / RATE, c3_bad)  # house already in EUR (official R), gold at R'
    out["grams_change_pct_same_rate_for_both"] = pct_str(g_both / g_ok - 1, 6)
    out["grams_change_pct_house_fixed_gold_at_wrong_rate"] = pct_str(g_fixed_house / g_ok - 1, 6)
    return out


def grams_variants(house_eur, usd_oz, fed_daily, ecb_m_dec, bis_a, years):
    """Annual mean of monthly grams per home 1995..1999 under alternative FX/gold assumptions (EUR route)."""
    ms_all = months_between(f"{years[0]}-01", f"{years[-1]}-12")
    ecb = {m: fr(v) for m, v in ecb_m_dec.items()}
    fx_rules = {r: aggregate(fed_daily, r)[0] for r in RULES}

    def gold_c3(m, nlg, usd_shift=Fraction(0), rate=RATE):
        if m < "1999-01":
            return (fr(usd_oz[m]) + usd_shift) * nlg[m] / rate if m in nlg and m in usd_oz else None
        return c4_f(fr(usd_oz[m]) + usd_shift, ecb[m]) if m in usd_oz and m in ecb else None

    variants = {"base_fed_mean": dict(nlg=fx_rules["mean"]), "fed_last_of_month": dict(nlg=fx_rules["last"]),
                "fed_first_of_month": dict(nlg=fx_rules["first"]), "fed_median": dict(nlg=fx_rules["median"]),
                "wb_minus_half_usd": dict(nlg=fx_rules["mean"], usd_shift=Fraction(-1, 2)),
                "wb_plus_half_usd": dict(nlg=fx_rules["mean"], usd_shift=Fraction(1, 2)),
                "rate_plus_1pct_house_eur_fixed": dict(nlg=fx_rules["mean"], rate=RATE * Fraction(101, 100))}
    if bis_a:
        variants["bis_average_derived"] = dict(nlg={m: fr(v) * RATE for m, v in bis_a.items()})
    series = {}
    for name, kw in variants.items():
        g = {}
        for m in ms_all:
            gold = gold_c3(m, **kw)
            if gold is not None and m in house_eur:
                g[m] = grams_per_home(house_eur[m], gold)
        series[name] = g
    base = series["base_fed_mean"]
    out = {}
    for name, g in series.items():
        yr = {}
        for y in years:
            v = [g[m] for m in months_between(f"{y}-01", f"{y}-12") if m in g]
            yr[str(y)] = dec_str(sum(v) / len(v), 2) if len(v) == 12 else None
        base_yr = {}
        for y in years:
            v = [base[m] for m in months_between(f"{y}-01", f"{y}-12") if m in base]
            base_yr[y] = sum(v) / len(v) if len(v) == 12 else None
        ann = {}
        for y in years:
            v = [g[m] for m in months_between(f"{y}-01", f"{y}-12") if m in g]
            if len(v) == 12 and base_yr[y]:
                ann[y] = abs(sum(v) / 12 / base_yr[y] - 1)
        mdev = {m: g[m] / base[m] - 1 for m in g if m in base}
        out[name] = {"annual_mean_grams": yr, "max_abs_annual_dev_pct": pct_str(max(ann.values()), 4) if ann else None,
                     "monthly_vs_base": dev_stats(mdev) if name != "base_fed_mean" else "base"}
    return out


# ------------------------------------------------------------------ source loading (reuses existing parsers)
class WatchdogTimeout(Exception):
    pass


def _alarm(signum, frame):
    raise WatchdogTimeout()


def parse_bis_collections(raw):
    """BIS WS_XRU M.NL: {collection: {month: Decimal EUR per USD}} for collections A (average) and E (end of period)."""
    import io
    rdr = csv.DictReader(io.StringIO(raw.decode("utf-8-sig", "replace")))
    rows = list(rdr)

    def norm(cell):
        return (cell or "").split(":")[0].strip()

    keymap = {(norm(k).upper() if ":" in (k or "") else (k or "").strip().upper()): k for k in (rdr.fieldnames or [])}
    for need in ("FREQ", "TIME_PERIOD", "OBS_VALUE"):
        if need not in keymap:
            raise ValidationDefect("BIS_COLUMNS_MISSING " + need)
    out, combos = {}, Counter()
    for r in rows:
        fr_, col = norm(r[keymap["FREQ"]]), (norm(r[keymap["COLLECTION"]]) if "COLLECTION" in keymap else "")
        unit = norm(r[keymap["UNIT_MEASURE"]]) if "UNIT_MEASURE" in keymap else ""
        combos[(fr_, col, unit)] += 1
        if fr_ != "M" or col not in ("A", "E"):
            continue
        k = r[keymap["TIME_PERIOD"]].strip()[:7]
        v = (r[keymap["OBS_VALUE"]] or "").strip()
        if not v:
            continue
        if k in out.setdefault(col, {}):
            raise ValidationDefect("BIS_DUPLICATE_MONTH " + col + k)
        out[col][k] = hc.parse_decimal(v)
    return out, {f"{a}|{b}|{c}": n for (a, b, c), n in combos.items()}


def load(fetch_fn, workbook=None):
    """Fetch and parse every source. Returns (data, status) where data holds Decimal series and daily dicts."""
    S = {"sources": {}, "missing_sources": [], "defects": [], "flags": []}
    D = {}

    def get(sid, local=None):
        print("STEP fetch", sid, flush=True)
        signal.alarm(100)
        try:
            if sid == c7.WB_ID:
                raw, rec = wbv.load_workbook(local)
            else:
                raw, rec = fetch_fn(sid)
        except acq.AcquisitionError as exc:
            S["missing_sources"].append({"source_id": sid, "reason": str(exc)[:140]})
            return None
        except WatchdogTimeout:
            S["missing_sources"].append({"source_id": sid, "reason": "WATCHDOG_100S"})
            return None
        finally:
            signal.alarm(0)
        S["sources"][sid] = {"sha256": rec["sha256"], "bytes": rec["bytes"]}
        return raw

    def safe(label, fn):
        try:
            return fn()
        except Exception as exc:  # reported as a defect of that source, never silently dropped
            S["defects"].append({"where": label, "error": f"{type(exc).__name__}: {str(exc)[:200]}"})
            return None

    raw = get(c7.WB_ID, workbook)
    if raw:
        S["sources"][c7.WB_ID]["matches_known_workbook_sha256"] = S["sources"][c7.WB_ID]["sha256"] == wbv.KNOWN_WORKBOOK_SHA256
        p = wbv.parse(raw, "1960-01", "2099-12")
        if p["duplicates"] or p["invalid"] or p["bad_dates"] or not p["series"]:
            raise ValidationDefect("WB_STRUCTURE")
        D["wb"], D["wb_meta"] = p["series"], {"gold_column": p["gold_column"], "header": p["header_text"], "unit_rows": p["unit_texts"]}
    raw = get("boe-gold-usd-monthly-average")
    if raw:
        pts = safe("boe_monthly", lambda: ss.parse_points(raw, ss.BOE_SERIES)[0])
        if pts:
            D["boe_m"] = ss.monthly_from_points(pts, "1960-01", "1999-12")
    raw = get(gn.BOE_D)
    if raw:
        D["boe_d"] = safe("boe_daily", lambda: gn.parse_boe_daily(raw))
    fed_pts, fed_header, fed_nd = {}, [], 0
    for sid in gn.FED_IDS:
        raw = get(sid)
        if raw:
            parsed = safe(sid, lambda: ns.parse_dated_text(raw, century=1900))
            if parsed:
                for d, v in parsed["points"].items():
                    if d in fed_pts:
                        S["defects"].append({"where": sid, "error": "DUPLICATE_DATE_ACROSS_FILES " + d.isoformat()})
                    fed_pts[d] = v
                fed_header += parsed["header"]
                fed_nd += parsed["missing_markers"]
    if fed_pts:
        D["fed_daily"], D["fed_header"], D["fed_nd"] = fed_pts, " ".join(fed_header), fed_nd
    eu = {}
    for sid, cen in (("h07-fed-dat96-eu", 1900), ("h07-fed-dat00-eu", 2000)):
        raw = get(sid)
        if raw:
            r = safe(sid, lambda: c7.parse_fed_euro(raw, cen, sid))
            if r:
                eu.update(r[0])
    if eu:
        D["fed_eu_daily"] = eu
    raw = get("bis-api-m-nl")
    if raw:
        r = safe("bis", lambda: parse_bis_collections(raw))
        if r:
            D["bis"], S["bis_combos"] = r
    raw = get("h07-imf-nld")
    if raw:
        r = safe("imf", lambda: c7.parse_imf(raw))
        if r:
            D["imf"] = r[0]
    pr, dr = get("cbs-7139shfo-props"), get("cbs-7139shfo-data")
    if pr and dr:
        r = safe("cbs7139", lambda: c7.parse_cbs(pr, dr))
        if r:
            D["cbs"] = r[0]
    raw = get(fx.ECB_MONTHLY)
    if raw:
        D["ecb_m"] = safe("ecb_monthly", lambda: gn.parse_ecb_monthly(raw))
    raw = get(fx.ECB_DAILY)
    if raw:
        D["ecb_d"] = safe("ecb_daily", lambda: gn.parse_ecb_daily(raw))
        D["prod"] = safe("prod_adr004", lambda: production_adr004(raw, D.get("wb")))
    r = safe("fixture_house", lambda: c7.fixture_house())
    if r:
        D["house"], S["fixture_sha256"] = r
    return D, S


def production_adr004(ecb_daily_raw, wb):
    """Run the production ADR-004 functions (etl.gold_monthly) on the same ECB daily bytes."""
    from etl import gold_monthly as gm
    fx_m, counts, ndays = gm.parse_ecb(ecb_daily_raw)
    gold = {m: v for m, v in (wb or {}).items() if m >= "2000-01"}
    homes = {m: Decimal(1) for m in gold}
    rows = gm.compute(gold, fx_m, homes, counts) if gold and "2000-01" in fx_m else []
    return {"fx_monthly": fx_m, "counts": counts, "days": ndays, "gold_eur": {r["month"]: Decimal(r["gold_eur_oz"]) for r in rows}}


# ------------------------------------------------------------------ analysis (pure over parsed data)
def analyze(D, S=None):
    S = S if S is not None else {"defects": [], "missing_sources": []}
    R = {"caveat": CAVEAT, "checks": [], "not_performed": []}

    def check(name, ok, detail=None):
        R["checks"].append({"name": name, "pass": bool(ok), "detail": detail})
        if not ok:
            S.setdefault("defects", []).append({"where": "check:" + name, "error": "CHECK_FAILED " + json.dumps(detail, default=str)[:160]})

    def need(section, *keys):
        miss = [k for k in keys if not D.get(k)]
        if miss:
            R["not_performed"].append(f"{section}: missing {','.join(miss)}")
        return not miss

    def section(name, fn):
        try:
            fn()
        except Exception as exc:  # a failing section is recorded as a defect, never hidden; the others still run
            S.setdefault("defects", []).append({"where": name, "error": f"{type(exc).__name__}: {str(exc)[:200]}"})

    wb = D.get("wb", {})
    fed_daily = D.get("fed_daily", {})
    fed_m, fed_n = aggregate(fed_daily, "mean") if fed_daily else ({}, {})
    fed_m_pre = {m: v for m, v in fed_m.items() if m <= "1998-12"}
    ecb_m = {m: fr(v) for m, v in D.get("ecb_m", {}).items()}
    usd = {m: fr(v) for m, v in wb.items()}
    RK = lambda a, b: months_between(a, b)

    # ---- unit consistency and constants
    def units():
        u = {"rate_equals_hist07_constant": RATE == Fraction(hc.NLG_PER_EUR), "grams_equals_hist07_constant": G_PER_OZ == Fraction(hc.GRAMS_PER_OZ)}
        check("constants_match_hist07", u["rate_equals_hist07_constant"] and u["grams_equals_hist07_constant"], u)
        if wb:
            unit_rows = " ".join(D.get("wb_meta", {}).get("unit_rows", [])).lower()
            u["wb_unit_text_mentions_troy_oz"] = "troy" in unit_rows
            check("wb_unit_is_usd_per_troy_oz", "troy" in unit_rows and "$" in unit_rows, unit_rows[:60])
        if fed_m_pre and wb:
            ratios = [c1_f(usd[m], fed_m_pre[m]) / usd[m] for m in fed_m_pre if m in usd]
            u["c1_over_usd_ratio_min_max"] = [dec_str(min(ratios), 4), dec_str(max(ratios), 4)]
            check("c1_nlg_per_usd_range_plausible", Fraction(14, 10) <= min(ratios) and max(ratios) <= Fraction(36, 10), u["c1_over_usd_ratio_min_max"])
            c3r = [c3_f(c1_f(usd[m], fed_m_pre[m])) / usd[m] for m in fed_m_pre if m in usd]
            u["c3_over_usd_ratio_min_max"] = [dec_str(min(c3r), 4), dec_str(max(c3r), 4)]
        if wb and ecb_m:
            ms = [m for m in RK("1999-01", "2001-12") if m in usd and m in ecb_m]
            ident = [c3_f(c1_f(usd[m], nlg_per_usd_from_usd_per_eur(ecb_m[m]))) - c4_f(usd[m], ecb_m[m]) for m in ms]
            u["euro_era_identity_c3_of_fixed_cross_equals_c4_exactly"] = bool(ms) and all(x == 0 for x in ident)
            u["euro_era_identity_months"] = len(ms)
            check("euro_era_fixed_cross_identity_exact", u["euro_era_identity_c3_of_fixed_cross_equals_c4_exactly"], len(ms))
        R["unit_consistency"] = u

    section("unit_consistency", units)

    # ---- direction
    def direction():
        d = {}
        if fed_daily:
            d["fed_header_and_values"] = assert_direction(D.get("fed_header", ""), list(fed_daily.values()))
            check("fed_direction_text_and_value", d["fed_header_and_values"]["by_text"] == "NLG_PER_USD", d["fed_header_and_values"])
            d["fed_header_sha256"] = hashlib.sha256(D.get("fed_header", "").encode()).hexdigest()
            d["fed_header_mentions"] = {k: bool(re.search(p, D.get("fed_header", ""), re.I)) for k, p in
                                        {"guilder": r"guilder", "us_dollar_sign": r"US\$|U\.S\.", "noon": r"noon", "buying": r"buying", "new_york": r"new york", "certified": r"certif", "customs": r"custom"}.items()}
        if fed_m and ecb_m:
            r = continuity_direction_test(fed_m, ecb_m, RK("1998-07", "1998-12"), RK("1999-01", "1999-06"))
            d["continuity_1998H2_vs_1999H1"] = r
            check("fed_direction_by_euro_continuity", r and r["direction_confirmed"], r)
        if fed_m_pre:
            cmp_ = {}
            window = RK("1971-01", "1998-12")
            for name, s in (("bis_a_times_rate", {m: fr(v) * RATE for m, v in D.get("bis", {}).get("A", {}).items()}),
                            ("imf", D.get("imf", {})), ("cbs", D.get("cbs", {}))):
                if s:
                    ratio = [fr(s[m]) / fed_m_pre[m] for m in window if m in s and m in fed_m_pre]
                    if ratio:
                        med = median_exact(ratio)
                        cmp_[name] = {"months": len(ratio), "median_ratio_to_fed": dec_str(med, 5), "same_direction": Fraction(95, 100) < med < Fraction(105, 100)}
                        check("direction_consistent_" + name, cmp_[name]["same_direction"], cmp_[name])
            d["other_sources_vs_fed_median_ratio"] = cmp_
        R["fx_direction"] = d

    section("fx_direction", direction)

    # ---- provenance and reliability of the FX series
    def provenance():
        p = {}
        if fed_daily:
            nd_by_year = Counter()
            p["fed"] = {"daily_obs": len(fed_daily), "first": min(fed_daily).isoformat(), "last": max(fed_daily).isoformat(),
                        "nd_markers": D.get("fed_nd"), "decimals": decimals_distribution(list(fed_daily.values())),
                        "obs_per_month_min_median_max": [min(fed_n.values()), str(median_exact(list(fed_n.values()))), max(fed_n.values())],
                        "months_lt15_obs_1971_1998": sum(1 for m, n in fed_n.items() if m <= "1998-12" and n < 15)}
            days = sorted(fed_daily)
            jumps = sorted(((fr(fed_daily[days[i]]) / fr(fed_daily[days[i - 1]]) - 1, days[i]) for i in range(1, len(days))), key=lambda t: -abs(t[0]))
            p["fed"]["largest_daily_moves_pct"] = [[d.isoformat(), pct_str(v, 3)] for v, d in jumps[:5]]
            p["fed"]["daily_moves_gt_3pct"] = sum(1 for v, _ in jumps if abs(v) > Fraction(3, 100))
            gaps = max(((days[i] - days[i - 1]).days, days[i].isoformat()) for i in range(1, len(days)))
            p["fed"]["longest_gap_days_ends"] = list(gaps)
            del nd_by_year
        bis = D.get("bis", {})
        if bis:
            p["bis"] = {c: {"months": len(s), "first": min(s), "last": max(s), "decimals": decimals_distribution(list(s.values()))} for c, s in bis.items()}
            a = {m: fr(v) * RATE for m, v in bis.get("A", {}).items()}
            p["bis_combos"] = (S or {}).get("bis_combos")
            win = RK("1960-01", "1998-12")
            if D.get("imf"):
                p["bis_a_vs_imf_closeness_1960_1998"] = closeness(a, D["imf"], win)
            if fed_m_pre:
                p["bis_a_vs_fed_closeness_1971_1998"] = closeness(a, fed_m_pre, RK("1971-01", "1998-12"))
            if D.get("cbs"):
                p["bis_a_vs_cbs_closeness_1965_1998"] = closeness(a, D["cbs"], RK("1965-01", "1998-12"))
            if ecb_m and a:
                recip = {m: 1 / ecb_m[m] for m in RK("1999-01", "2026-12") if m in ecb_m}
                devs = devs_between({m: fr(v) for m, v in bis.get("A", {}).items()}, recip, RK("1999-01", "2026-12"))
                p["bis_a_vs_reciprocal_ecb_1999_on"] = dev_stats(devs)
        for name, key in (("imf", "imf"), ("cbs", "cbs")):
            if D.get(key):
                p[name] = {"months": len(D[key]), "first": min(D[key]), "last": max(D[key]), "decimals": decimals_distribution(list(D[key].values()))}
        pair = {}
        if fed_m_pre:
            w71, w60 = RK("1971-01", "1998-12"), RK("1960-01", "1970-12")
            bis_a = {m: fr(v) * RATE for m, v in bis.get("A", {}).items()}
            for name, s in (("bis_derived", bis_a), ("cbs", D.get("cbs", {})), ("imf", D.get("imf", {}))):
                if s:
                    pair[f"{name}_vs_fed_1971_1998"] = dev_stats(devs_between({m: fr(v) for m, v in s.items()}, fed_m_pre, w71))
            if bis_a:
                for name in ("cbs", "imf"):
                    if D.get(name):
                        pair[f"{name}_vs_bis_derived_1960_1970"] = dev_stats(devs_between({m: fr(v) for m, v in D[name].items()}, bis_a, w60))
        p["pairwise"] = pair
        R["fx_provenance"] = p

    section("fx_provenance", provenance)

    # ---- World Bank precision, rounding, regime
    def wb_section():
        if not need("worldbank", "wb"):
            return
        w = {"coverage": {"first": min(wb), "last": max(wb), "count": len(wb), "expected": len(RK(min(wb), max(wb)))},
             "precision_by_period": wb_precision(wb),
             "non_integer_total": sum(1 for v in wb.values() if v != v.to_integral_value()),
             "regime_1960_1967": regime_scan(wb, "1960-01", "1967-12"), "regime_1968_1974": regime_scan(wb, "1968-01", "1974-12"),
             "regime_1975_1978": regime_scan(wb, "1975-01", "1978-12"),
             "values_1971_07_to_09": {m: str(wb.get(m)) for m in ("1971-07", "1971-08", "1971-09", "1971-12", "1972-01", "1973-02", "1973-03")},
             "values_1974_12_1975_01": {m: str(wb.get(m)) for m in ("1974-12", "1975-01")},
             "months_equal_35_total": sum(1 for v in wb.values() if v == 35), "last_month_equal_35": max((m for m, v in wb.items() if v == 35), default=None)}
        check("wb_complete_range", w["coverage"]["count"] == w["coverage"]["expected"], w["coverage"])
        if D.get("boe_m"):
            w["wb_vs_boe_rounding_consistency"] = {k: rounding_vs_reference(wb, D["boe_m"], RK(a, b)) for k, (a, b) in
                                                    {"1979-89": ("1979-01", "1989-12"), "1990-98": ("1990-01", "1998-12"), "1999": ("1999-01", "1999-12")}.items()}
            if fed_m_pre:
                boe_f = {m: fr(v) for m, v in D["boe_m"].items()}
                w["c1_effect_wb_vs_boe_gold_same_fx_1979_1998"] = dev_stats({m: (usd[m] * fed_m_pre[m]) / (boe_f[m] * fed_m_pre[m]) - 1 for m in RK("1979-01", "1998-12") if m in usd and m in fed_m_pre and m in boe_f})
        if fed_m_pre:
            ms = [m for m in RK("1975-01", "1998-12") if m in usd and m in fed_m_pre]
            w["c1_rounding_worst_case_pct_1975_1998"] = dev_stats({m: Fraction(1, 2) / usd[m] for m in ms})
            w["c1_rounding_worst_case_pct_1979_1998"] = dev_stats({m: Fraction(1, 2) / usd[m] for m in ms if m >= "1979-01"})
        R["worldbank"] = w

    section("worldbank", wb_section)

    # ---- early regimes of the FX series
    def fx_regimes():
        bis_a = {m: fr(v) * RATE for m, v in D.get("bis", {}).get("A", {}).items()}
        f = {}
        if bis_a:
            f["bis_derived_top_monthly_steps_1960_1972"] = top_steps(bis_a, "1960-01", "1972-12")
            f["bis_derived_distinct_4dp_1960_1970_top3"] = dict(Counter(dec_str(v, 4) for m, v in bis_a.items() if "1960-01" <= m <= "1970-12").most_common(3))
        if fed_m:
            f["fed_top_monthly_steps_1971_1975"] = top_steps(fed_m, "1971-01", "1975-12")
        R["fx_regimes"] = f

    section("fx_regimes", fx_regimes)

    # ---- aggregation sensitivity (alternative FX month aggregation)
    def agg():
        if not need("aggregation_sensitivity", "fed_daily"):
            return
        mp = {"1971-1974": RK("1971-01", "1974-12"), "1975-1998": RK("1975-01", "1998-12")}
        a = {"c1_and_inverse_grams_per_home_vs_mean": aggregation_sensitivity(fed_daily, mp)}
        bis = D.get("bis", {})
        if bis.get("A") and bis.get("E"):
            a["bis_end_of_period_vs_average"] = dev_stats(devs_between(bis["E"], bis["A"], RK("1960-01", "1998-12")))
            fl = aggregate(fed_daily, "last")[0]
            a["fed_last_vs_bis_end_of_period_derived_1971_1998"] = dev_stats(devs_between(fl, {m: fr(v) * RATE for m, v in bis["E"].items()}, RK("1971-01", "1998-12")))
        if D.get("boe_d"):
            a["mean_of_products_vs_product_of_means_boe_x_fed_1979_1998"] = product_of_means_effect(D["boe_d"], fed_daily, RK("1979-01", "1998-12"))
        if D.get("ecb_d"):
            ecb_last, _ = aggregate(D["ecb_d"], "last")
            ecb_mean, _ = aggregate(D["ecb_d"], "mean")
            a["ecb_end_of_month_vs_mean_c4_effect"] = {k: dev_stats({m: ecb_mean[m] / ecb_last[m] - 1 for m in RK(x, y) if m in ecb_last and m in ecb_mean})
                                                       for k, (x, y) in {"1999-2001": ("1999-01", "2001-12"), "2002-2026": ("2002-01", "2026-12")}.items()}
        R["aggregation_sensitivity"] = a

    section("aggregation_sensitivity", agg)

    # ---- overlap recompute
    def overlap():
        if not need("overlap", "wb", "ecb_m"):
            return
        ov, ovm = {}, RK("1999-01", "2001-12")
        variants = {}
        if D.get("fed_eu_daily"):
            fe, _ = aggregate(D["fed_eu_daily"], "mean", min_obs=15)
            _, fe_all_n = aggregate(D["fed_eu_daily"], "mean")
            ov["fed_euro_months_dropped_lt15_obs"] = {m: n for m, n in fe_all_n.items() if n < 15}
            dm, dn = c7.monthly_mean(D["fed_eu_daily"])  # the input preparation HIST-07 used, for the comparison run only
            hc_nlg = {m: hc.nlg_per_usd_from_usd_per_eur(hc.Quote(v, "USD", "EUR")).value for m, v in dm.items() if dn[m] >= 15}
            variants["fed_euro_noon"] = ("eur", fe, hc_nlg)
            fl, _ = aggregate(D["fed_eu_daily"], "last", min_obs=15)
            variants["fed_euro_noon_last_of_month"] = ("eur", fl, None)
        if D.get("bis", {}).get("A"):
            variants["bis"] = ("nlg", {m: fr(v) * RATE for m, v in D["bis"]["A"].items()},
                               {m: hc.nlg_per_usd_from_eur_per_usd(hc.Quote(v, "EUR", "USD")).value for m, v in D["bis"]["A"].items()})
        if D.get("cbs"):
            variants["cbs"] = ("nlg", {m: fr(v) for m, v in D["cbs"].items()}, dict(D["cbs"]))
        if D.get("imf"):
            variants["imf"] = ("nlg", {m: fr(v) for m, v in D["imf"].items() if m >= "1999-01"}, None)
        for name, (kind, ser, dec_for_hc) in variants.items():
            devs, missing = (overlap_devs(usd, ser, ecb_m, ovm) if kind == "eur" else overlap_devs_from_nlg(usd, ser, ecb_m, ovm))
            st = dev_stats(devs)
            entry = {"stats": st, "missing_months": len(missing)}
            by_year = {y: dev_stats({m: d for m, d in devs.items() if m.startswith(y)}).get("mean_signed_pct") for y in ("1999", "2000", "2001")}
            entry["mean_signed_pct_by_year"] = by_year
            if name in REPORTED_HIST07:
                entry["reproduces_hist07_reported"] = reproduces_reported(st, REPORTED_HIST07[name])
            if dec_for_hc is not None and devs:
                entry["agreement_with_hist07_code"] = compare_with_hist07(D["wb"], dec_for_hc, D["ecb_m"], ovm, devs)
                check("overlap_agreement_" + name, entry["agreement_with_hist07_code"]["agree"], entry["agreement_with_hist07_code"])
            ov[name] = entry
            if name == "fed_euro_noon":
                ov["_monthly_rows"] = [{"period": m, "fed_euro_noon_usd_per_eur": dec_str(ser[m], 6), "ecb_usd_per_eur": dec_str(ecb_m[m], 6), "c3_over_c4_minus_1_pct": pct_str(devs[m], 6)} for m in sorted(devs)]
        if D.get("fed_eu_daily"):
            fe, _ = aggregate(D["fed_eu_daily"], "mean", min_obs=15)
            long_ms = [m for m in RK("1999-01", "2099-12") if m in fe and m in ecb_m] if fe else []
            ldev = {m: ecb_m[m] / fe[m] - 1 for m in long_ms}
            ov["fed_long_run"] = {"stats": dev_stats(ldev), "first": min(ldev, default=None), "last": max(ldev, default=None)}
            ov["fed_long_run"]["by_year_median_abs_pct"] = {y: dev_stats({m: d for m, d in ldev.items() if m.startswith(y)}).get("median_abs_pct") for y in sorted({m[:4] for m in ldev})}
            cut = {m: d for m, d in ldev.items() if m <= "2011-05"}
            ov["fed_long_run_1999_2011_05"] = {"stats": dev_stats(cut), "reproduces_hist07_reported": reproduces_reported(dev_stats(cut), REPORTED_HIST07["fed_long_1999_2011"])}
            # alternative aggregation for the euro era: Fed end-of-month versus ECB mean, and Fed mean versus ECB end-of-month
            fl, _ = aggregate(D["fed_eu_daily"], "last", min_obs=15)
            ov["fed_last_vs_ecb_mean_1999_2001"] = dev_stats({m: ecb_m[m] / fl[m] - 1 for m in ovm if m in fl and m in ecb_m})
            if D.get("ecb_d"):
                el, _ = aggregate(D["ecb_d"], "last")
                ov["fed_last_vs_ecb_last_1999_2001"] = dev_stats({m: el[m] / fl[m] - 1 for m in ovm if m in fl and m in el})
                ov["fed_mean_vs_ecb_last_1999_2001"] = dev_stats({m: el[m] / fe[m] - 1 for m in ovm if m in fe and m in el})
        R["overlap_1999_2001"] = ov

    section("overlap", overlap)

    # ---- ADR-004 production logic against the independent calculation
    def adr004():
        if not need("adr004", "wb", "ecb_d", "prod"):
            return
        mean_m, cnt = aggregate(D["ecb_d"], "mean")
        pm = {m: fr(v) for m, v in D["prod"]["fx_monthly"].items()}
        a = {"production_fx_months": len(pm), "my_fx_months": len(mean_m),
             "production_fx_vs_exact_mean_of_daily": dev_stats(devs_between(pm, mean_m, [m for m in sorted(pm)]))}
        mine_c4 = {m: c4_f(usd[m], mean_m[m]) for m in sorted(D["prod"]["gold_eur"]) if m in usd and m in mean_m}
        prod_c4 = {m: fr(v) for m, v in D["prod"]["gold_eur"].items()}
        a["production_c4_vs_exact"] = dev_stats(devs_between(prod_c4, mine_c4, sorted(prod_c4)))
        a["production_c4_months"] = len(prod_c4)
        if ecb_m:
            a["ecb_daily_mean_vs_provider_monthly_1999_on"] = dev_stats(devs_between(mean_m, ecb_m, RK("1999-01", "2099-12")))
            a["c4_with_provider_monthly_vs_daily_mean_1999_2001"] = dev_stats({m: (usd[m] / ecb_m[m]) / (usd[m] / mean_m[m]) - 1 for m in RK("1999-01", "2001-12") if m in usd and m in mean_m and m in ecb_m})
        mx = max((abs(fr(v) / mine_c4[m] - 1) for m, v in prod_c4.items() if m in mine_c4), default=Fraction(0))
        check("production_c4_equals_independent_c4", mx < Fraction(1, 10 ** 20), f"{float(mx):.2e}")
        R["adr004_production_vs_independent"] = a

    section("adr004", adr004)

    # ---- grams per home and the fixed rate
    def grams():
        if not need("grams_per_home", "wb", "ecb_m", "fed_daily", "house"):
            return
        years = [1995, 1996, 1997, 1998, 1999]
        R["grams_per_home_1995_1999"] = grams_variants({m: fr(v) for m, v in D["house"].items()}, wb, fed_daily, D["ecb_m"], D.get("bis", {}).get("A"), years)
        m = "1998-06"
        if m in usd and m in fed_m:
            R["fixed_rate_sensitivity_example_1998_06"] = {"delta_rate_pct": "1", **fixed_rate_sensitivity(c1_f(usd[m], fed_m[m]), Fraction(250000))}

    section("grams_per_home", grams)

    # ---- boundary step 1998-12 -> 1999-01
    def boundary():
        if fed_m and ecb_m and "1998-12" in fed_m and "1999-01" in ecb_m:
            imp = RATE / fed_m["1998-12"]
            R["changeover_step"] = {"implied_usd_per_eur_1998_12_from_fed_mean": dec_str(imp, 6), "ecb_usd_per_eur_1999_01": dec_str(ecb_m["1999-01"], 6),
                                    "change_pct": pct_str(ecb_m["1999-01"] / imp - 1, 4), "wb_usd_1998_12_1999_01": [str(wb.get("1998-12")), str(wb.get("1999-01"))]}

    section("boundary", boundary)
    return R


# ------------------------------------------------------------------ CLI
def run(fetch_fn=None, workbook=None):
    signal.signal(signal.SIGALRM, _alarm)
    fetch_fn = fetch_fn or acq.fetch
    D, S = load(fetch_fn, workbook)
    S.setdefault("defects", [])
    R = analyze(D, S)
    rows = R.get("overlap_1999_2001", {}).pop("_monthly_rows", [])
    R.update({"sources": S["sources"], "missing_sources": S["missing_sources"], "defects": S["defects"], "flags": S["flags"],
              "fixture_sha256": S.get("fixture_sha256")})
    core = {c7.WB_ID, fx.ECB_MONTHLY} | set(gn.FED_IDS)
    if any(m["source_id"] in core for m in S["missing_sources"]):
        R["status"] = "INCOMPLETE"
    elif S["defects"]:
        R["status"] = "DEFECTS"
    else:
        R["status"] = "PARTIAL" if S["missing_sources"] or R["not_performed"] else "COMPLETE_RESEARCH"
    R["checks_failed"] = [c["name"] for c in R["checks"] if not c["pass"]]
    return R, rows


def main(argv=None):
    ap = argparse.ArgumentParser(description="HIST-08 gold construction validation (research only)")
    ap.add_argument("--summary-out")
    ap.add_argument("--overlap-csv-out")
    ap.add_argument("--workbook")
    ap.add_argument("--print-summary")
    ap.add_argument("--keys", default="")
    a = ap.parse_args(argv)
    if a.print_summary:
        S = json.loads(Path(a.print_summary).read_text())
        for key in [k for k in a.keys.split(",") if k]:
            print("SUMMARY", key, json.dumps(S.get(key), sort_keys=True, default=str)[:3800])
        return 0
    if not a.summary_out:
        ap.error("--summary-out is required")
    out = Path(a.summary_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        R, rows = run(workbook=a.workbook)
    except (ValidationDefect, wbv.ValidationError, hc.ConstructionError) as exc:
        out.write_text(json.dumps({"status": "FAILED", "error": str(exc)[:400]}, indent=1) + "\n")
        print("DEFECT", str(exc)[:400])
        return 1
    out.write_text(json.dumps(R, indent=1, sort_keys=True, default=str) + "\n")
    if a.overlap_csv_out and rows:
        with open(a.overlap_csv_out, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    print("STATUS", R["status"], "checks_failed", R["checks_failed"], "defects", len(R["defects"]), "missing_sources", [m["source_id"] for m in R["missing_sources"]])
    return 1 if R["status"] in ("DEFECTS",) else 0


if __name__ == "__main__":
    sys.exit(main())
