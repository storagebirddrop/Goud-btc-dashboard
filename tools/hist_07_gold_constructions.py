"""HIST-07 research only: pure Decimal functions for the competing pre-2000 gold constructions.

Constructions (labels are part of the data model, never implied):
  C1  gold_nlg_oz          = USD/oz (monthly, World Bank)  x  NLG per USD (monthly mean, market rate)   [observed NLG]
  C3  eur_equivalent_oz    = C1 / 2.20371 (Council Reg. (EC) 2866/98)  [REDENOMINATED nominal equivalent,
                             NOT an observed contemporaneous euro market price]
  C4  gold_eur_oz          = USD/oz / (USD per EUR, monthly mean, ECB)  [OBSERVED euro price, ADR-004 method;
                             exists only from 1999-01]
  C2  direct guilder gold prices are not computed here (no credible machine-readable series found; see report).

Unit algebra: every number that enters a formula is a Quote(value, num, den, tag). Multiplication needs
matching units, so NLG-vs-EUR confusion and USD/oz-vs-USD/g mixing raise UnitError. The fixed rate is applied
by redenominate() exactly once: a REDENOMINATED quote cannot be redenominated again and an EUR quote cannot be
redenominated at all.

Missing data stays missing: functions return (result, missing_months) and never interpolate, forward-fill or
substitute. Inputs must be strictly ascending, unique, positive and finite. Nothing here touches etl/ or data/.
CLI is fail closed (exit 1 on any defect, exit 2 on a sha256 mismatch).
"""
import argparse
import hashlib
import json
import re
import sys
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path

PREC = 34
NLG_PER_EUR = Decimal("2.20371")
GRAMS_PER_OZ = Decimal("31.1034768")
PERIOD_RE = re.compile(r"\d{4}-(0[1-9]|1[0-2])")
TAGS = ("OBSERVED", "DERIVED", "REDENOMINATED")
LABELS = {
    "C1": "gold in NLG: USD/oz x market NLG per USD (observed guilder pricing basis, no euro)",
    "C3": "nominal redenominated EUR equivalent = C1 / 2.20371 (NOT an observed euro market price)",
    "C4": "observed EUR price: USD/oz / ECB monthly-mean USD per EUR (ADR-004 method, from 1999-01)",
}
OUTPUT_DIGITS = 10


class ConstructionError(ValueError):
    """Data or input defect (fail closed)."""


class UnitError(ConstructionError):
    """Unit, currency or redenomination misuse."""


class Quote:
    """value in `num` per `den`; tag records provenance (OBSERVED, DERIVED, REDENOMINATED)."""
    __slots__ = ("value", "num", "den", "tag")

    def __init__(self, value, num, den, tag="OBSERVED"):
        if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
            raise ConstructionError("QUOTE_VALUE_NOT_POSITIVE_FINITE_DECIMAL")
        if tag not in TAGS:
            raise ConstructionError("UNKNOWN_TAG")
        self.value, self.num, self.den, self.tag = value, num, den, tag

    def __repr__(self):
        return f"Quote({self.value} {self.num}/{self.den} {self.tag})"


def mul(a, b, tag="DERIVED"):
    """(X per Y) x (Y per Z) = X per Z."""
    if not isinstance(a, Quote) or not isinstance(b, Quote):
        raise UnitError("UNTYPED_OPERAND")
    if a.den != b.num:
        raise UnitError(f"UNIT_MISMATCH {a.num}/{a.den} x {b.num}/{b.den}")
    with localcontext() as ctx:
        ctx.prec = PREC
        return Quote(a.value * b.value, a.num, b.den, tag)


def div(a, b, tag="DERIVED"):
    """(X per Z) / (X per Y) = Y per Z."""
    if not isinstance(a, Quote) or not isinstance(b, Quote):
        raise UnitError("UNTYPED_OPERAND")
    if a.num != b.num:
        raise UnitError(f"UNIT_MISMATCH {a.num}/{a.den} / {b.num}/{b.den}")
    with localcontext() as ctx:
        ctx.prec = PREC
        return Quote(a.value / b.value, b.den, a.den, tag)


def redenominate(q):
    """NLG -> EUR at the fixed rate, exactly once, result tagged REDENOMINATED."""
    if not isinstance(q, Quote):
        raise UnitError("UNTYPED_OPERAND")
    if q.num != "NLG":
        raise UnitError(f"REDENOMINATION_NEEDS_NLG_GOT_{q.num}")
    if q.tag == "REDENOMINATED":
        raise UnitError("ALREADY_REDENOMINATED")
    with localcontext() as ctx:
        ctx.prec = PREC
        return Quote(q.value / NLG_PER_EUR, "EUR", q.den, "REDENOMINATED")


def nlg_per_usd_from_usd_per_eur(q):
    """Fixed-rate cross for the euro era only: NLG per USD = 2.20371 / (USD per EUR). DERIVED."""
    if not isinstance(q, Quote) or (q.num, q.den) != ("USD", "EUR"):
        raise UnitError("NEEDS_USD_PER_EUR")
    with localcontext() as ctx:
        ctx.prec = PREC
        return Quote(NLG_PER_EUR / q.value, "NLG", "USD", "DERIVED")


def nlg_per_usd_from_eur_per_usd(q):
    """BIS-style EUR per USD (pre-1999 values are NLG-per-USD / 2.20371) -> NLG per USD. DERIVED."""
    if not isinstance(q, Quote) or (q.num, q.den) != ("EUR", "USD"):
        raise UnitError("NEEDS_EUR_PER_USD")
    with localcontext() as ctx:
        ctx.prec = PREC
        return Quote(q.value * NLG_PER_EUR, "NLG", "USD", "DERIVED")


# ------------------------------------------------------------------ series
def parse_decimal(text):
    if isinstance(text, Decimal):
        d = text
    else:
        if not isinstance(text, str) or not re.fullmatch(r"\d+(\.\d+)?", text):
            raise ConstructionError("NONCANONICAL_NUMBER")
        try:
            d = Decimal(text)
        except InvalidOperation as exc:
            raise ConstructionError("NONCANONICAL_NUMBER") from exc
    if not d.is_finite() or d <= 0:
        raise ConstructionError("NONPOSITIVE_OR_NONFINITE")
    return d


def load_series(pairs):
    """pairs: iterable of (period, value) strictly ascending without duplicates -> dict."""
    out, last = {}, None
    for period, value in pairs:
        if not isinstance(period, str) or not PERIOD_RE.fullmatch(period):
            raise ConstructionError("BAD_PERIOD")
        if period in out:
            raise ConstructionError("DUPLICATE_PERIOD " + period)
        if last is not None and period < last:
            raise ConstructionError("NOT_ASCENDING " + period)
        out[period] = parse_decimal(value)
        last = period
    return out


def month_range(start, end):
    for p in (start, end):
        if not PERIOD_RE.fullmatch(p):
            raise ConstructionError("BAD_PERIOD")
    if start > end:
        raise ConstructionError("RANGE_REVERSED")
    y, m = map(int, start.split("-"))
    ey, em = map(int, end.split("-"))
    out = []
    while (y, m) <= (ey, em):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _typed(series, num, den, tag="OBSERVED"):
    return {p: Quote(v, num, den, tag) for p, v in series.items()}


def c1(usd_oz, nlg_per_usd, months):
    """C1 in NLG/oz. Returns ({month: Quote NLG/oz}, missing_months). A month lacking either input is missing."""
    g, f = _typed(usd_oz, "USD", "oz"), _typed(nlg_per_usd, "NLG", "USD")
    out, missing = {}, []
    for m in months:
        if m in g and m in f:
            out[m] = mul(f[m], g[m])
        else:
            missing.append(m)
    return out, missing


def c3(c1_quotes):
    """C3 = C1 / 2.20371 applied once per month; REDENOMINATED EUR/oz."""
    return {m: redenominate(q) for m, q in c1_quotes.items()}


def c4(usd_oz, usd_per_eur, months):
    """C4 observed EUR/oz = USD/oz / (USD per EUR). Only meaningful from 1999-01 (euro existed)."""
    if any(m < "1999-01" for m in months):
        raise ConstructionError("C4_BEFORE_EURO_EXISTED")
    g, f = _typed(usd_oz, "USD", "oz"), _typed(usd_per_eur, "USD", "EUR")
    out, missing = {}, []
    for m in months:
        if m in g and m in f:
            out[m] = div(g[m], f[m], "OBSERVED")
        else:
            missing.append(m)
    return out, missing


# ------------------------------------------------------------------ comparison
def rel_dev(a, b):
    """(a - b) / b for two quotes with equal units (Decimal)."""
    if (a.num, a.den) != (b.num, b.den):
        raise UnitError("COMPARE_UNIT_MISMATCH")
    with localcontext() as ctx:
        ctx.prec = PREC
        return (a.value - b.value) / b.value


def _pct_rank(sorted_vals, p):
    return sorted_vals[max(0, -(-p * len(sorted_vals) // 100) - 1)]


def deviation_stats(devs):
    """devs: {month: Decimal relative deviation}. Aggregates in percent, as strings."""
    if not devs:
        return {"months": 0}
    with localcontext() as ctx:
        ctx.prec = PREC
        absd = sorted(abs(v) for v in devs.values())
        sgn = sorted(devs.values())
        n = len(absd)
        pc = lambda v: format((v * 100).quantize(Decimal("1E-6")), "f")
        worst = sorted(devs.items(), key=lambda kv: (-abs(kv[1]), kv[0]))[:3]
        return {"months": n, "mean_signed_pct": pc(sum(sgn) / n), "median_signed_pct": pc(sgn[(n - 1) // 2]),
                "median_abs_pct": pc(_pct_rank(absd, 50)), "p95_abs_pct": pc(_pct_rank(absd, 95)),
                "max_abs_pct": pc(absd[-1]), "worst": [[m, pc(v)] for m, v in worst]}


def overlap_compare(c3_quotes, c4_quotes, months):
    """Month-by-month C3 vs C4 on months present in both; others reported missing, never filled."""
    devs, missing = {}, []
    for m in months:
        if m in c3_quotes and m in c4_quotes:
            a, b = c3_quotes[m], c4_quotes[m]
            if a.tag != "REDENOMINATED" or b.tag != "OBSERVED" or a.num != "EUR" or b.num != "EUR":
                raise UnitError("OVERLAP_NEEDS_REDENOMINATED_C3_AND_OBSERVED_C4")
            devs[m] = rel_dev(a, b)
        else:
            missing.append(m)
    return devs, missing


# ------------------------------------------------------------------ grams per home
def grams_per_home_eur(house_eur, gold_eur_oz):
    """house EUR per home x 31.1034768 g/oz / gold EUR per oz -> grams per home."""
    if (house_eur.num, house_eur.den) != ("EUR", "home") or (gold_eur_oz.num, gold_eur_oz.den) != ("EUR", "oz"):
        raise UnitError("GRAMS_EUR_ROUTE_NEEDS_EUR_HOME_AND_EUR_OZ")
    with localcontext() as ctx:
        ctx.prec = PREC
        return house_eur.value * GRAMS_PER_OZ / gold_eur_oz.value


def grams_per_home_nlg(house_nlg, gold_nlg_oz):
    if (house_nlg.num, house_nlg.den) != ("NLG", "home") or (gold_nlg_oz.num, gold_nlg_oz.den) != ("NLG", "oz"):
        raise UnitError("GRAMS_NLG_ROUTE_NEEDS_NLG_HOME_AND_NLG_OZ")
    with localcontext() as ctx:
        ctx.prec = PREC
        return house_nlg.value * GRAMS_PER_OZ / gold_nlg_oz.value


def annual_mean(monthly_quotes, year):
    """Arithmetic mean of the 12 monthly quotes of `year`; None unless all 12 months are present (no partial years)."""
    ms = [f"{year:04d}-{i:02d}" for i in range(1, 13)]
    if any(m not in monthly_quotes for m in ms):
        return None
    first = monthly_quotes[ms[0]]
    if any((monthly_quotes[m].num, monthly_quotes[m].den, monthly_quotes[m].tag) != (first.num, first.den, first.tag) for m in ms):
        raise UnitError("MIXED_UNITS_OR_TAGS_IN_YEAR")
    with localcontext() as ctx:
        ctx.prec = PREC
        return Quote(sum(monthly_quotes[m].value for m in ms) / 12, first.num, first.den, "DERIVED")


# ------------------------------------------------------------------ canonical output
def _fmt(d):
    with localcontext() as ctx:
        ctx.prec = PREC
        return format(d.quantize(Decimal(1).scaleb(-OUTPUT_DIGITS)), "f")


def canonical_rows(columns):
    """columns: {name: {month: Quote|Decimal}} -> sorted list of rows with fixed-digit strings (missing = null)."""
    months = sorted({m for col in columns.values() for m in col})
    rows = []
    for m in months:
        row = {"period": m}
        for name in sorted(columns):
            v = columns[name].get(m)
            row[name] = None if v is None else _fmt(v.value if isinstance(v, Quote) else v)
        rows.append(row)
    return rows


def canonical_sha256(rows):
    text = json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode()).hexdigest()


# ------------------------------------------------------------------ CLI
def compute_from_inputs(inputs):
    """inputs: {"start","end","usd_oz":{p:str},"nlg_per_usd":{p:str},"usd_per_eur":{p:str}} (all optional but usd_oz)."""
    months = month_range(inputs["start"], inputs["end"])
    usd = load_series(sorted(inputs["usd_oz"].items()))
    nlg = load_series(sorted(inputs.get("nlg_per_usd", {}).items()))
    eur = load_series(sorted(inputs.get("usd_per_eur", {}).items()))
    pre = [m for m in months if m < "1999-01"]
    post = [m for m in months if m >= "1999-01"]
    cols, missing = {"usd_oz": usd}, {}
    c1q, missing["c1"] = c1(usd, nlg, pre)
    c3q = c3(c1q)
    cols["c1_gold_nlg_oz"], cols["c3_eur_equivalent_oz"] = c1q, c3q
    if post:
        c4q, missing["c4"] = c4(usd, eur, post)
        cols["c4_gold_eur_oz"] = c4q
    cols["usd_oz"] = {m: v for m, v in usd.items() if m in months}
    rows = canonical_rows(cols)
    return {"labels": LABELS, "rows": rows, "missing": missing, "sha256": canonical_sha256(rows)}


def main(argv=None):
    ap = argparse.ArgumentParser(description="HIST-07 research-only gold constructions (fail closed)")
    ap.add_argument("--inputs", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--expect-sha256")
    a = ap.parse_args(argv)
    try:
        inputs = json.loads(Path(a.inputs).read_text())
        result = compute_from_inputs(inputs)
    except (ConstructionError, KeyError, OSError, ValueError) as exc:
        print("DEFECT", str(exc)[:300])
        return 1
    Path(a.out).write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    print("SHA256", result["sha256"], "rows", len(result["rows"]), "missing", {k: len(v) for k, v in result["missing"].items()})
    if a.expect_sha256 and a.expect_sha256 != result["sha256"]:
        print("HASH_MISMATCH expected", a.expect_sha256)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
