"""EQ-01 research-only probe: S&P 500 / AEX feasibility against Dutch house prices.

Nothing here is a decision, a source authorization or a publication. Raw third-party bytes stay
in memory (fetch via tools.hist_02_acquire.fetch: exact-URL allowlist, no redirect, 15 MB cap,
sha256); the summary holds aggregates, hashes and <=25-word quotes only. Missing data stays
absent: no interpolation, forward fill, backfill, annual->monthly conversion or splicing.

Two layers:
 1. Pure helpers (index rebasing, common baseline, overlap range, relative performance,
    EUR conversion, frequency handling, valuation-ratio guard). All Decimal.
 2. Probes (candidate sources -> coverage, first/last, gaps, hash) and official-terms quotes.
"""
import argparse
import hashlib
import io
import json
import math
import os
import re
import shutil
import signal
import statistics
import subprocess
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener
from decimal import Decimal, InvalidOperation, getcontext
from pathlib import Path

getcontext().prec = 34

RETURN_TYPES = ("price", "total_gross", "total_net", "housing_avg_price", "housing_hpi", "fx")
FREQUENCIES = ("daily", "monthly", "annual")
BASES = ("close", "month_end", "month_avg", "annual", "n/a")
PERIOD_RE = {"daily": re.compile(r"^\d{4}-\d{2}-\d{2}$"), "monthly": re.compile(r"^\d{4}-\d{2}$"),
             "annual": re.compile(r"^\d{4}$")}
HUNDRED = Decimal(100)


class EquityMethodError(ValueError):
    """Methodological violation; fails closed."""


@dataclass(frozen=True)
class Series:
    name: str
    kind: str                # 'equity' | 'housing' | 'fx'
    return_type: str         # RETURN_TYPES
    currency: str            # e.g. USD, EUR, NLG
    frequency: str
    basis: str               # BASES
    points: tuple            # ((period, Decimal), ...) strictly ascending
    index_base: object = None  # period at which the value is 100, else None


def make_series(name, kind, return_type, currency, frequency, basis, points, index_base=None):
    if kind not in ("equity", "housing", "fx"):
        raise EquityMethodError("UNKNOWN_KIND")
    if return_type not in RETURN_TYPES:
        raise EquityMethodError("UNKNOWN_RETURN_TYPE")
    if frequency not in FREQUENCIES:
        raise EquityMethodError("UNKNOWN_FREQUENCY")
    if basis not in BASES:
        raise EquityMethodError("UNKNOWN_BASIS")
    out, prev = [], None
    for period, value in points:
        if not PERIOD_RE[frequency].match(str(period)):
            raise EquityMethodError(f"PERIOD_FORMAT_MISMATCH {period} for {frequency}")
        if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
            raise EquityMethodError(f"NON_POSITIVE_OR_NON_FINITE {period}")
        if prev is not None:
            if period == prev:
                raise EquityMethodError(f"DUPLICATE_PERIOD {period}")
            if period < prev:
                raise EquityMethodError(f"UNORDERED_PERIOD {period}")
        prev = period
        out.append((period, value))
    return Series(name, kind, return_type, currency, frequency, basis, tuple(out), index_base)


def _as_dict(s):
    return dict(s.points)


def series_sha256(s):
    """Deterministic hash over (frequency, basis, period, value) with normalised Decimal text."""
    h = hashlib.sha256()
    h.update(f"{s.frequency}|{s.basis}|{s.return_type}|{s.currency}\n".encode())
    for p, v in s.points:
        h.update(f"{p},{format(v.normalize(), 'f')}\n".encode())
    return h.hexdigest()


# ---- frequency handling -------------------------------------------------------------------

def annual_to_monthly(*_args, **_kwargs):
    """Manufacturing monthly values from annual ones is forbidden (METHODOLOGY v2.4)."""
    raise EquityMethodError("ANNUAL_TO_MONTHLY_FORBIDDEN")


def monthly_from_daily(s, basis):
    """Aggregate EXISTING daily observations of one calendar month. Months without any daily
    observation stay absent (no fill). basis: 'month_end' (last observed day) or 'month_avg'
    (arithmetic mean of observed days)."""
    if s.frequency != "daily":
        raise EquityMethodError("MONTHLY_FROM_DAILY_REQUIRES_DAILY")
    if basis not in ("month_end", "month_avg"):
        raise EquityMethodError("UNKNOWN_MONTHLY_BASIS")
    months = defaultdict(list)
    for p, v in s.points:
        months[p[:7]].append(v)
    pts = []
    for m in sorted(months):
        vals = months[m]
        pts.append((m, vals[-1] if basis == "month_end" else sum(vals) / Decimal(len(vals))))
    return make_series(s.name, s.kind, s.return_type, s.currency, "monthly", basis, pts, None)


def month_index(period):
    y, m = int(period[:4]), int(period[5:7])
    return y * 12 + (m - 1)


def monthly_gaps(periods):
    """Number of calendar months strictly inside [first,last] without an observation."""
    if not periods:
        return 0
    mset = {month_index(p[:7]) for p in periods}
    return (max(mset) - min(mset) + 1) - len(mset)


# ---- rebasing, baseline, overlap ----------------------------------------------------------

def rebase(s, base_period):
    """Index to 100 at base_period. The base observation must exist exactly (no nearest-date)."""
    if s.index_base is not None:
        raise EquityMethodError("ALREADY_REBASED")
    d = _as_dict(s)
    if base_period not in d:
        raise EquityMethodError(f"BASE_PERIOD_MISSING {base_period}")
    b = d[base_period]
    pts = [(p, HUNDRED * v / b) for p, v in s.points]
    return make_series(s.name, s.kind, s.return_type, s.currency, s.frequency, s.basis, pts, base_period)


def _same_frequency(series):
    if len({x.frequency for x in series}) != 1:
        raise EquityMethodError("FREQUENCY_MISMATCH")


def common_baseline(series_list):
    """Earliest period at which ALL series have an observation. Raises if none exists."""
    if len(series_list) < 2:
        raise EquityMethodError("NEED_TWO_SERIES")
    _same_frequency(series_list)
    common = set(_as_dict(series_list[0]))
    for s in series_list[1:]:
        common &= set(_as_dict(s))
    if not common:
        raise EquityMethodError("NO_COMMON_OBSERVATION")
    return min(common)


def overlap_range(a, b):
    """(first, last) of the period-range intersection; raises when the ranges are disjoint."""
    _same_frequency([a, b])
    if not a.points or not b.points:
        raise EquityMethodError("EMPTY_SERIES")
    lo = max(a.points[0][0], b.points[0][0])
    hi = min(a.points[-1][0], b.points[-1][0])
    if lo > hi:
        raise EquityMethodError("NON_OVERLAPPING_RANGES")
    return lo, hi


def assert_comparable(a, b):
    """Return types are never interchangeable: price vs total return, gross vs net, avg price vs HPI."""
    if a.kind == "equity" and b.kind == "equity":
        if a.return_type != b.return_type:
            raise EquityMethodError(f"RETURN_TYPE_MIXING {a.return_type} vs {b.return_type}")
        if a.currency != b.currency:
            raise EquityMethodError(f"CURRENCY_MIXING {a.currency} vs {b.currency}")
    if a.kind == "housing" and b.kind == "housing" and a.return_type != b.return_type:
        raise EquityMethodError("HOUSING_DEFINITION_MIXING")
    if "fx" in (a.kind, b.kind):
        raise EquityMethodError("FX_SERIES_NOT_COMPARABLE")


def relative_performance(a_idx, b_idx):
    """relative[t] = 100 * a_idx[t] / b_idx[t] on periods present in BOTH series (others absent,
    never filled). Both series must be rebased to the SAME base period."""
    if a_idx.index_base is None or b_idx.index_base is None:
        raise EquityMethodError("NOT_REBASED")
    if a_idx.index_base != b_idx.index_base:
        raise EquityMethodError(f"DIFFERENT_BASE_DATES {a_idx.index_base} vs {b_idx.index_base}")
    _same_frequency([a_idx, b_idx])
    assert_comparable(a_idx, b_idx)
    overlap_range(a_idx, b_idx)  # raises if disjoint
    da, db = _as_dict(a_idx), _as_dict(b_idx)
    common = sorted(set(da) & set(db))
    if a_idx.index_base not in common:
        raise EquityMethodError("BASE_NOT_IN_COMMON_OBSERVATIONS")
    pts = [(p, HUNDRED * da[p] / db[p]) for p in common]
    return make_series(f"{a_idx.name}/{b_idx.name}", "equity", "price" if a_idx.return_type == "price" else a_idx.return_type,
                       "ratio", a_idx.frequency, "n/a", pts, a_idx.index_base)


def relative_to_housing(equity, housing, base_period=None):
    """Convenience: rebase both at a common baseline (default: earliest common observation)."""
    if equity.kind != "equity" or housing.kind != "housing":
        raise EquityMethodError("KIND_MISMATCH")
    base = base_period or common_baseline([equity, housing])
    return relative_performance(rebase(equity, base), rebase(housing, base))


# ---- currency -----------------------------------------------------------------------------

def to_eur(usd_series, usd_per_eur):
    """Equity (USD) -> EUR investor view: value_usd / USD_per_EUR at the SAME period and SAME basis.
    Periods without an FX observation stay absent (no carry-forward)."""
    if usd_series.currency != "USD" or usd_per_eur.currency != "USD_PER_EUR":
        raise EquityMethodError("CURRENCY_DIRECTION_MISMATCH")
    if usd_series.frequency != usd_per_eur.frequency:
        raise EquityMethodError("FREQUENCY_MISMATCH")
    if usd_series.basis != usd_per_eur.basis:
        raise EquityMethodError(f"BASIS_MISMATCH {usd_series.basis} vs {usd_per_eur.basis}")
    fx = _as_dict(usd_per_eur)
    pts = [(p, v / fx[p]) for p, v in usd_series.points if p in fx]
    return make_series(usd_series.name + "_eur", usd_series.kind, usd_series.return_type, "EUR",
                       usd_series.frequency, usd_series.basis, pts, None)


def chain(a, b):
    """Splicing two series (e.g. price-return history + total-return history) is never allowed."""
    raise EquityMethodError("SPLICE_NOT_ALLOWED")


# ---- valuation ratio (concept B) ----------------------------------------------------------

def houses_per_unit(house_price_eur, unit_price_eur, unit_kind, proxy_name=None):
    """Number of purchasable units per average house. Index points are NOT purchasable units."""
    if unit_kind == "index_points":
        raise EquityMethodError("INDEX_POINTS_ARE_NOT_PURCHASABLE_UNITS")
    if unit_kind != "investable_proxy" or not proxy_name:
        raise EquityMethodError("INVESTABLE_PROXY_REQUIRED")
    if unit_price_eur <= 0 or house_price_eur <= 0:
        raise EquityMethodError("NON_POSITIVE_PRICE")
    return house_price_eur / unit_price_eur


# ---- parsers (bytes -> list[(date, Decimal)]), absent markers are counted ------------------

class SourceFormatError(ValueError):
    pass


def _dec(text):
    try:
        v = Decimal(text.strip())
    except (InvalidOperation, AttributeError):
        return None
    return v if v.is_finite() else None


def parse_csv_close(raw, date_col, value_col, delimiter=","):
    """Generic header-based CSV (Stooq: Date,Close; FRED: observation_date/DATE,<id>)."""
    text = raw.decode("utf-8-sig", errors="replace")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        raise SourceFormatError("EMPTY")
    header = [h.strip() for h in lines[0].split(delimiter)]
    lowered = [h.lower() for h in header]
    dc = [i for i, h in enumerate(lowered) if h in date_col]
    vc = [i for i, h in enumerate(lowered) if h in value_col]
    if not dc or not vc:
        raise SourceFormatError("HEADER_NOT_RECOGNISED:" + ",".join(header)[:60])
    pts, missing = [], 0
    for ln in lines[1:]:
        cells = ln.split(delimiter)
        if len(cells) <= max(dc[0], vc[0]):
            missing += 1
            continue
        v = _dec(cells[vc[0]])
        if v is None or v <= 0:
            missing += 1
            continue
        pts.append((cells[dc[0]].strip(), v))
    return pts, missing


def parse_yahoo_chart(raw):
    try:
        doc = json.loads(raw)
        res = doc["chart"]["result"][0]
    except (ValueError, KeyError, TypeError, IndexError) as exc:
        raise SourceFormatError("YAHOO_JSON_UNEXPECTED") from exc
    ts = res.get("timestamp") or []
    closes = res["indicators"]["quote"][0].get("close") or []
    if len(ts) != len(closes):
        raise SourceFormatError("YAHOO_LENGTH_MISMATCH")
    import datetime as dt
    pts, missing = [], 0
    for t, c in zip(ts, closes):
        if c is None or not isinstance(c, (int, float)) or not math.isfinite(c) or c <= 0:
            missing += 1
            continue
        pts.append((dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d"), Decimal(repr(c))))
    meta = {k: res.get("meta", {}).get(k) for k in ("currency", "instrumentType", "exchangeName", "exchangeTimezoneName")}
    return pts, missing, meta


def parse_shiller_rows(rows):
    """rows: iterable of (date_float, price). Shiller dates are YYYY.MM (1871.1 = October)."""
    pts, missing = [], 0
    for d, price in rows:
        if not isinstance(d, (int, float)) or not isinstance(price, (int, float)) or price <= 0:
            missing += 1
            continue
        y = int(d)
        m = int(round((d - y) * 100))
        if not 1 <= m <= 12:
            raise SourceFormatError(f"SHILLER_BAD_MONTH {d}")
        pts.append((f"{y:04d}-{m:02d}", Decimal(repr(price))))
    return pts, missing


# ---- coverage summary ---------------------------------------------------------------------

def dedupe_check(points):
    seen, prev = set(), None
    dup = unordered = 0
    for p, _ in points:
        if p in seen:
            dup += 1
        if prev is not None and p < prev:
            unordered += 1
        seen.add(p)
        prev = p
    return dup, unordered


def coverage_summary(points, frequency):
    dup, unordered = dedupe_check(points)
    s = {"observations": len(points), "duplicates": dup, "unordered": unordered}
    if not points:
        return s
    ps = [p for p, _ in points]
    s.update({"first": min(ps), "last": max(ps), "monthly_gaps_inside_range": monthly_gaps(ps)})
    per_month = defaultdict(int)
    for p in ps:
        per_month[p[:7]] += 1
    if frequency == "daily":
        counts = sorted(per_month.values())
        s["obs_per_month_min_median_max"] = [counts[0], int(statistics.median(counts)), counts[-1]]
        s["months_with_data"] = len(per_month)
    if dup == 0 and unordered == 0:
        pts = [(p, v) for p, v in points]
        s["sha256"] = series_sha256(make_series("x", "equity", "price", "n/a", frequency, "close" if frequency == "daily" else "month_avg", pts))
    return s


def housing_months(csv_path):
    """Read the committed CBS CSV (public repo data) -> {series: {YYYY-MM: Decimal}}."""
    out = defaultdict(dict)
    for ln in Path(csv_path).read_text().splitlines()[1:]:
        d, ser, val = ln.split(",")
        out[ser][d[:7]] = Decimal(val)
    return out


def derived_vs_housing(daily_pts, housing_pts):
    """Monthly month_end / month_avg of a daily series vs CBS housing: overlap + relative-perf hash.
    Aggregates only."""
    res = {}
    daily = make_series("eq", "equity", "price", "idx", "daily", "close", daily_pts)
    house = make_series("hpi", "housing", "housing_hpi", "idx", "monthly", "n/a", sorted(housing_pts.items()))
    for basis in ("month_end", "month_avg"):
        m = monthly_from_daily(daily, basis)
        try:
            lo, hi = overlap_range(m, house)
            rel = relative_to_housing(m, house)
            vals = [v for _, v in rel.points]
            res[basis] = {"overlap": [lo, hi], "baseline": rel.index_base, "n": len(rel.points),
                          "relative_min": format(min(vals).quantize(Decimal("0.01")), "f"),
                          "relative_max": format(max(vals).quantize(Decimal("0.01")), "f"),
                          "sha256": series_sha256(rel), "monthly_sha256": series_sha256(m)}
        except EquityMethodError as exc:
            res[basis] = {"error": str(exc)}
    return res


# ---- candidate sources --------------------------------------------------------------------
Y0, Y1 = "-1325635200", "1790000000"  # 1927-12-30 .. 2026-09-26+ (Yahoo accepts negative period1)


def _yahoo(sym):
    return f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1={Y0}&period2={Y1}&interval=1d&events=history"


# id -> (url, kind, group, label)
DATA_CANDIDATES = {
    "shiller-ie-data": ("https://www.econ.yale.edu/~shiller/data/ie_data.xls", "xls", "shiller", "S&P Composite monthly, Shiller"),
    "fred-sp500": ("https://fred.stlouisfed.org/graph/fredgraph.csv?id=SP500", "csv", "fred", "FRED SP500 daily close, USD, price return"),
    "stooq-spx-d": ("https://stooq.com/q/d/l/?s=%5Espx&i=d", "csv", "stooq", "Stooq ^SPX daily"),
    "stooq-aex-d": ("https://stooq.com/q/d/l/?s=%5Eaex&i=d", "csv", "stooq", "Stooq ^AEX daily"),
    "yahoo-gspc-d": (_yahoo("%5EGSPC"), "json", "yahoo", "Yahoo ^GSPC daily, price return"),
    "yahoo-spxtr-d": (_yahoo("%5ESPXTR"), "json", "yahoo", "Yahoo ^SPXTR daily, total return"),
    "yahoo-sp500tr-d": (_yahoo("%5ESP500TR"), "json", "yahoo", "Yahoo ^SP500TR daily, total return"),
    "yahoo-sp500ntr-d": (_yahoo("%5ESP500NTR"), "json", "yahoo", "Yahoo ^SP500NTR daily, net total return"),
    "yahoo-aexgr-d": (_yahoo("%5EAEXGR"), "json", "yahoo", "Yahoo ^AEXGR daily (probe: may not exist)"),
    "yahoo-aex-d": (_yahoo("%5EAEX"), "json", "yahoo", "Yahoo ^AEX daily, price return"),
}
# Official documents: (url, kind, keyword list)
DOC_CANDIDATES = {
    "spdji-sp500-through-history": ("https://www.spglobal.com/spdji/en/documents/campaigns/sp-500-through-history-202301.pdf", "pdf",
                                    ["1957", "1926", "90 stocks", "back-test", "base", "1941"]),
    "spdji-us-methodology-page": ("https://www.spglobal.com/spdji/en/methodology/article/sp-us-indices-methodology/", "html",
                                  ["float", "base value", "1941", "total return", "back-test"]),
    "spdji-sp500-page": ("https://www.spglobal.com/spdji/en/indices/equity/sp-500/", "html",
                         ["launch", "back-test", "total return", "net total return", "1957"]),
    "fred-sp500-notes-page": ("https://fred.stlouisfed.org/series/SP500", "html",
                              ["10 years", "copyright", "prior written permission", "S&P Dow Jones Indices"]),
    "euronext-aex-factsheet": ("https://live.euronext.com/sites/default/files/documentation/index-fact-sheets/AEX_Index_Factsheet.pdf", "pdf",
                               ["1983", "base", "gross return", "net return", "introduced", "return", "launch", "currency"]),
    "euronext-aex-composition-history": ("https://www.euronext.com/sites/default/files/aex_index_history_evolution_of_the_composition_from_1983.pdf", "pdf",
                                         ["1983", "100", "base", "guilder", "euro"]),
    "euronext-index-data-use": ("https://live.euronext.com/en/products/indices/data-use", "html",
                                ["informational", "reserves all rights", "licen", "redistribut", "unauthori"]),
    "shiller-home": ("https://shillerdata.com/", "html", ["ie_data", "Data", "monthly", "average", "S&P"]),
    "spdji-terms-of-use": ("https://www.spglobal.com/spdji/en/terms-of-use/", "html",
                           ["personal", "non-commercial", "redistribute", "copyright", "Index Data"]),
}


def register(hist_02_acquire):
    for sid, (url, kind, *_rest) in list(DATA_CANDIDATES.items()) + list(DOC_CANDIDATES.items()):
        hist_02_acquire.SOURCES[sid] = (url, kind)


# ---- official text quotes (<=25 words) ----------------------------------------------------

def html_to_text(raw):
    t = raw.decode("utf-8", errors="replace")
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", t)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t)


def pdf_to_text(raw):
    exe = shutil.which("pdftotext")
    if not exe:
        raise SourceFormatError("PDFTOTEXT_MISSING")
    with tempfile.TemporaryDirectory() as d:  # ephemeral, outside the repository
        src = Path(d) / "in.pdf"
        src.write_bytes(raw)
        proc = subprocess.run([exe, "-layout", str(src), "-"], capture_output=True, timeout=60)
    return re.sub(r"\s+", " ", proc.stdout.decode("utf-8", errors="replace"))


def quotes(text, keywords, per_keyword=2, max_words=25):
    sentences = re.split(r"(?<=[.;:])\s+", text)
    out = {}
    for kw in keywords:
        hits = []
        for s in sentences:
            if kw.lower() in s.lower():
                words = s.split()
                idx = next((i for i, w in enumerate(words) if kw.lower() in w.lower()), 0)
                lo = max(0, min(idx - 8, len(words) - max_words))
                hits.append(" ".join(words[lo:lo + max_words]))
                if len(hits) >= per_keyword:
                    break
        out[kw] = hits
    return out


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def locate(url):
    """Status and Location of the first response WITHOUT following it (allowlisted exact URLs only)."""
    try:
        build_opener(_NoRedirect()).open(Request(url, headers={"User-Agent": "Goud-btc-dashboard/EQ-01 research"}), timeout=20).close()
        return {"status": 200}
    except HTTPError as exc:
        return {"status": exc.code, "location": (exc.headers.get("Location") or "")[:240] or None}
    except (OSError, URLError) as exc:
        return {"status": None, "error": type(exc).__name__}


# ---- probe runner -------------------------------------------------------------------------

def shiller_points(raw):
    try:
        import xlrd  # optional dependency, installed in the workflow only
    except ImportError as exc:
        raise SourceFormatError("XLRD_MISSING") from exc
    book = xlrd.open_workbook(file_contents=raw)
    sheet = book.sheet_by_name("Data")
    rows, notes = [], []
    for r in range(sheet.nrows):
        a, b = sheet.cell_value(r, 0), sheet.cell_value(r, 1)
        if isinstance(a, float) and isinstance(b, float) and 1800 < a < 2100:
            rows.append((a, b))
        else:
            for c in range(min(sheet.ncols, 4)):
                v = sheet.cell_value(r, c)
                if isinstance(v, str) and "average" in v.lower():
                    notes.append(" ".join(v.split()[:25]))
    pts, missing = parse_shiller_rows(rows)
    return pts, missing, {"sheets": book.sheet_names(), "average_notes": notes[:3]}


def probe_data(sid, fetcher, housing, locator=None):
    url, kind, group, label = DATA_CANDIDATES[sid]
    rec = {"id": sid, "url": url, "label": label}
    try:
        raw, meta = fetcher(sid)
    except Exception as exc:  # unreachable is a finding, not a defect
        rec["status"] = "UNAVAILABLE"
        rec["error"] = str(exc)[:200]
        if locator and not str(exc).startswith("NETWORK_TIMEOUT"):
            rec["locate"] = locator(url)
        return rec
    rec.update({"status": "FETCHED", "bytes": meta["bytes"], "sha256": meta["sha256"]})
    try:
        if group == "yahoo":
            pts, missing, ymeta = parse_yahoo_chart(raw)
            rec["yahoo_meta"] = ymeta
        elif group == "fred":
            pts, missing = parse_csv_close(raw, ("date", "observation_date"), ("sp500",))
        elif group == "stooq":
            pts, missing = parse_csv_close(raw, ("date", "data"), ("close", "zamkniecie"))
        else:
            pts, missing, extra = shiller_points(raw)
            rec["shiller_meta"] = extra
    except (SourceFormatError, KeyError, ValueError) as exc:
        rec["status"] = "FETCHED_NOT_PARSEABLE"
        rec["error"] = str(exc)[:160]
        rec["html_head"] = " ".join(html_to_text(raw).split()[:40]) if raw[:15].lower().startswith(b"<!doctype html") else None
        rec["head_is_text"] = raw[:40].decode("utf-8", errors="replace").replace("\n", " ")[:40] if group in ("stooq", "fred") else None
        return rec
    freq = "monthly" if group == "shiller" else "daily"
    rec["frequency"] = freq
    rec["missing_markers"] = missing
    try:
        rec["coverage"] = coverage_summary(pts, freq)
        hp = housing.get("nl_hpi", {})
        if freq == "daily" and not rec["coverage"]["duplicates"] and not rec["coverage"]["unordered"]:
            rec["vs_cbs_hpi"] = derived_vs_housing(pts, hp)
    except ValueError as exc:  # malformed dates etc.: a finding about the source
        rec["status"] = "FETCHED_NOT_PARSEABLE"
        rec["error"] = str(exc)[:160]
    return rec


def probe_doc(sid, fetcher, locator=None):
    url, kind, kws = DOC_CANDIDATES[sid]
    rec = {"id": sid, "url": url}
    try:
        raw, meta = fetcher(sid)
    except Exception as exc:
        rec["status"] = "UNAVAILABLE"
        rec["error"] = str(exc)[:200]
        if locator and not str(exc).startswith("NETWORK_TIMEOUT"):
            rec["locate"] = locator(url)
        return rec
    rec.update({"status": "OFFICIAL_TEXT_READ", "bytes": meta["bytes"], "sha256": meta["sha256"]})
    try:
        text = pdf_to_text(raw) if kind == "pdf" else html_to_text(raw)
    except SourceFormatError as exc:
        rec["status"] = "FETCHED_NO_TEXT"
        rec["error"] = str(exc)
        return rec
    rec["quotes"] = quotes(text, kws)
    rec["head"] = " ".join(text.split()[:50])
    rec["text_chars"] = len(text)
    return rec


HARD_TIMEOUT_SECONDS = 45


def with_deadline(fetcher, seconds=HARD_TIMEOUT_SECONDS):
    """Wall-clock guard per source (a trickling server must not stall the whole probe)."""
    def _alarm(_signum, _frame):
        raise TimeoutError("HARD_DEADLINE_EXCEEDED")

    def wrapped(sid):
        old = signal.signal(signal.SIGALRM, _alarm)
        signal.alarm(seconds)
        try:
            return fetcher(sid)
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old)
    return wrapped


def run(summary_out, housing_csv, fetcher=None):
    from tools import hist_02_acquire
    register(hist_02_acquire)
    fetcher = with_deadline(fetcher or hist_02_acquire.fetch)
    housing = housing_months(housing_csv) if Path(housing_csv).exists() else {}
    summary = {"status": "RESEARCH_ONLY_NOT_A_DECISION", "data": [], "docs": []}
    for sid in DATA_CANDIDATES:
        summary["data"].append(probe_data(sid, fetcher, housing, locate))
        print(json.dumps({"data": summary["data"][-1]["id"], "status": summary["data"][-1]["status"]}), flush=True)
    for sid in DOC_CANDIDATES:
        summary["docs"].append(probe_doc(sid, fetcher, locate))
        print(json.dumps({"doc": summary["docs"][-1]["id"], "status": summary["docs"][-1]["status"]}), flush=True)
    hp = housing.get("nl_hpi", {})
    ap = housing.get("nl_house_avg_eur", {})
    summary["housing_cbs_repo"] = {"hpi": [min(hp), max(hp), len(hp)] if hp else None,
                                   "avg_price": [min(ap), max(ap), len(ap)] if ap else None}
    summary["missing_sources"] = [r["id"] for r in summary["data"] + summary["docs"] if r["status"] in ("UNAVAILABLE",)]
    text = json.dumps(summary, sort_keys=True, indent=2) + "\n"
    out = Path(summary_out)
    ws = os.environ.get("GITHUB_WORKSPACE")
    if ws and out.resolve().is_relative_to(Path(ws).resolve()):
        raise RuntimeError("REPOSITORY_WRITE_PROHIBITED")
    out.write_text(text)
    print("summary_sha256", hashlib.sha256(text.encode()).hexdigest())
    return summary


if __name__ == "__main__":
    ap_ = argparse.ArgumentParser()
    ap_.add_argument("--summary-out", required=True)
    ap_.add_argument("--housing-csv", default="data/cbs-housing.csv")
    a = ap_.parse_args()
    run(a.summary_out, a.housing_csv)
    sys.exit(0)
