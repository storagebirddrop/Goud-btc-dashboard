"""HIST-06 research tool: Dutch house-price history (NVM/Vastgoedmarkt vs CBS/Kadaster), RESEARCH ONLY.

Nothing here publishes, links or splices series. The pure functions (parsing, unit guards, overlap
statistics, break detection) are unit tested offline; the CLI `probe` fetches third-party documents in
GitHub Actions only (via tools.hist_02_acquire.fetch: https allowlist, size cap, redirect policy, sha256),
keeps raw bytes in memory, and writes aggregates, hashes and small derived tables.

Hard rules enforced in code: ascending unique periods; no annual->monthly conversion; no interpolation or
fill; sha256 pins verified; values of different unit / statistic / frequency are never compared.
"""
import argparse
import csv
import hashlib
import json
import math
import re
import statistics
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

NLG_PER_EUR = Decimal("2.20371")  # irrevocable conversion rate (redenomination, not purchasing power)


class HousingError(ValueError):
    """Integrity / parser defect: fail closed."""


class UnorderedPeriods(HousingError):
    pass


class DuplicatePeriod(HousingError):
    pass


class HashMismatch(HousingError):
    pass


class UnitMismatch(HousingError):
    pass


class ForbiddenConversion(HousingError):
    pass


# ------------------------------------------------------------------ series container and guards
@dataclass(frozen=True)
class Series:
    name: str
    unit: str        # NLG | EUR | kEUR | EUR_FROM_NLG | EUR_REAL_<year> | INDEX_<base>
    statistic: str   # mean | median | index | mean_of_monthly_means
    freq: str        # A | M
    values: tuple    # ((period, Decimal), ...) strictly ascending, unique


def make_series(name, unit, statistic, freq, pairs):
    periods = [p for p, _ in pairs]
    check_periods(periods, freq)
    vals = []
    for p, v in pairs:
        d = v if isinstance(v, Decimal) else to_decimal(v)
        if not d.is_finite() or d <= 0:
            raise HousingError(f"NON_POSITIVE_OR_NON_FINITE {p}")
        vals.append((p, d))
    return Series(name, unit, statistic, freq, tuple(vals))


def to_decimal(text):
    s = str(text).strip().replace(" ", "").replace(" ", "")
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", s):      # Dutch thousands separator
        s = s.replace(".", "")
    elif re.fullmatch(r"\d{1,3}(,\d{3})+", s):
        s = s.replace(",", "")
    else:
        s = s.replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation as exc:
        raise HousingError(f"INVALID_NUMBER {text!r}") from exc


def _ordinal(period, freq):
    if freq == "A":
        if not re.fullmatch(r"\d{4}", period):
            raise HousingError(f"BAD_PERIOD {period!r}")
        return int(period)
    m = re.fullmatch(r"(\d{4})-(\d{2})", period)
    if freq != "M" or not m or not 1 <= int(m.group(2)) <= 12:
        raise HousingError(f"BAD_PERIOD {period!r}")
    return int(m.group(1)) * 12 + int(m.group(2)) - 1


def check_periods(periods, freq, contiguous=False):
    ords = [_ordinal(p, freq) for p in periods]
    for a, b in zip(ords, ords[1:]):
        if a == b:
            raise DuplicatePeriod(f"DUPLICATE_PERIOD {periods[ords.index(a)]}")
        if b < a:
            raise UnorderedPeriods("UNORDERED_PERIODS")
        if contiguous and b != a + 1:
            raise HousingError("GAP_IN_PERIODS (no fill allowed)")
    return ords


def as_dict(s):
    return dict(s.values)


def assert_comparable(a, b):
    for attr in ("unit", "statistic", "freq"):
        if getattr(a, attr) != getattr(b, attr):
            raise UnitMismatch(f"{attr.upper()}_MISMATCH {getattr(a, attr)} vs {getattr(b, attr)}")


def rescale(s, factor, new_unit):
    """Explicit unit scaling (e.g. kEUR -> EUR). Only kEUR->EUR with factor 1000 is allowed."""
    if not (s.unit == "kEUR" and new_unit == "EUR" and factor == Decimal(1000)):
        raise UnitMismatch("ONLY_KEUR_TO_EUR_x1000_ALLOWED")
    return Series(s.name, "EUR", s.statistic, s.freq, tuple((p, v * factor) for p, v in s.values))


def nlg_to_eur(s):
    """Redenomination at the fixed rate; the result is a DERIVED nominal series (unit EUR_FROM_NLG), never 'original'."""
    if s.unit != "NLG":
        raise UnitMismatch("NLG_REQUIRED")
    return Series(s.name, "EUR_FROM_NLG", s.statistic, s.freq, tuple((p, v / NLG_PER_EUR) for p, v in s.values))


def deflate(nominal, cpi, base_year):
    """Real series = nominal * CPI[base]/CPI[year]. Needs EVERY year of the nominal series in the CPI; missing -> error."""
    if nominal.freq != "A" or cpi.freq != "A" or not cpi.unit.startswith("INDEX"):
        raise UnitMismatch("ANNUAL_NOMINAL_AND_ANNUAL_INDEX_REQUIRED")
    if nominal.unit.startswith("EUR_REAL") or nominal.unit.startswith("INDEX"):
        raise UnitMismatch("NOMINAL_LEVEL_REQUIRED")
    c = as_dict(cpi)
    if str(base_year) not in c:
        raise HousingError("BASE_YEAR_MISSING_IN_CPI")
    out = []
    for p, v in nominal.values:
        if p not in c:
            raise HousingError(f"CPI_MISSING {p} (no fill allowed)")
        out.append((p, v * c[str(base_year)] / c[p]))
    return Series(nominal.name + "_real", f"{nominal.unit}_REAL_{base_year}", nominal.statistic, "A", tuple(out))


def annual_to_monthly(*_a, **_k):
    raise ForbiddenConversion("ANNUAL_TO_MONTHLY_FORBIDDEN")


def interpolate(*_a, **_k):
    raise ForbiddenConversion("INTERPOLATION_FORBIDDEN")


def annual_mean_of_complete_years(monthly):
    """Arithmetic mean of 12 monthly values for years with all 12 months; incomplete years are omitted (not filled).
    Labelled mean_of_monthly_means: NOT the count-weighted annual mean CBS publishes."""
    if monthly.freq != "M":
        raise UnitMismatch("MONTHLY_REQUIRED")
    by = {}
    for p, v in monthly.values:
        by.setdefault(p[:4], []).append(v)
    pairs = [(y, sum(vs) / 12) for y, vs in sorted(by.items()) if len(vs) == 12]
    return Series(monthly.name + "_annual", monthly.unit, "mean_of_monthly_means", "A", tuple(pairs))


def verify_sha256(raw, expected):
    got = hashlib.sha256(raw).hexdigest()
    if got != expected.lower():
        raise HashMismatch(f"SHA256_MISMATCH expected={expected[:12]} got={got[:12]}")
    return got


# ------------------------------------------------------------------ table parsing (text from pdftotext / OCR)
YEAR_ROW = re.compile(r"^\s*((?:19|20)\d\d)\b[\s:|.\-]*(.*)$")
NUM_TOKEN = re.compile(r"(?<![\d.,])\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?(?![\d])")


def parse_year_rows(text, y_min=1900, y_max=2100):
    """Blocks of consecutive lines that start with a year. Returns list of blocks; each block is a list of (year, [Decimal...]).
    Within a block years must be strictly ascending and unique (else UnorderedPeriods / DuplicatePeriod).
    Lines with a year but no number are ignored (not filled)."""
    blocks, cur = [], []
    for line in text.splitlines():
        m = YEAR_ROW.match(line)
        nums = []
        if m:
            y = int(m.group(1))
            if y_min <= y <= y_max:
                for tok in NUM_TOKEN.findall(m.group(2)):
                    try:
                        nums.append(to_decimal(tok))
                    except HousingError:
                        pass
                if nums:
                    cur.append((y, nums))
                    continue
        if cur and line.strip():
            blocks.append(cur)
            cur = []
    if cur:
        blocks.append(cur)
    for b in blocks:
        ys = [y for y, _ in b]
        for a, c in zip(ys, ys[1:]):
            if a == c:
                raise DuplicatePeriod(f"DUPLICATE_YEAR {a}")
            if c < a:
                raise UnorderedPeriods(f"UNORDERED_YEARS {a}>{c}")
    return blocks


def pick_value_column(block, col=0):
    """First numeric column of a block as {year: Decimal}; rows lacking that column are dropped and counted by the caller."""
    return {y: nums[col] for y, nums in block if len(nums) > col}


def contiguity(years):
    ys = sorted(years)
    return {"first": ys[0], "last": ys[-1], "n": len(ys), "gaps": [y for y in range(ys[0], ys[-1] + 1) if y not in set(ys)]} if ys else {"n": 0}


# ------------------------------------------------------------------ overlap statistics
def overlap_rows(a, b):
    """Per common period: a, b, abs diff (a-b), pct diff relative to b, ratio a/b. Series must be comparable (after explicit rescale)."""
    assert_comparable(a, b)
    da, db = as_dict(a), as_dict(b)
    return [{"period": p, "a": da[p], "b": db[p], "abs_diff": da[p] - db[p],
             "pct_diff_of_b": (da[p] - db[p]) / db[p] * 100, "ratio": da[p] / db[p]} for p in sorted(set(da) & set(db))]


def _q(x, places="0.01"):
    return str(Decimal(x).quantize(Decimal(places)))


def summarize_rows(rows):
    if not rows:
        return {"n": 0}
    pct = [r["pct_diff_of_b"] for r in rows]
    ratios = [float(r["ratio"]) for r in rows]
    return {"n": len(rows), "first": rows[0]["period"], "last": rows[-1]["period"],
            "mean_pct_diff": _q(sum(pct) / len(pct)), "median_pct_diff": _q(sorted(pct)[len(pct) // 2]),
            "min_pct_diff": _q(min(pct)), "max_pct_diff": _q(max(pct)),
            "mean_abs_diff": _q(sum(abs(r["abs_diff"]) for r in rows) / len(rows)),
            "ratio_stdev": f"{statistics.pstdev(ratios):.4f}" if len(ratios) > 1 else None}


def growth(s):
    """YoY percent for annual series; only for adjacent years that both exist (a gap yields no value, never a bridge)."""
    if s.freq != "A":
        raise UnitMismatch("ANNUAL_REQUIRED")
    d = as_dict(s)
    return {int(p): (v / d[str(int(p) - 1)] - 1) * 100 for p, v in d.items() if str(int(p) - 1) in d}


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx, syy = sum((x - mx) ** 2 for x in xs), sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / math.sqrt(sxx * syy)


def growth_differences(a, b):
    """Growth of two comparable annual series on common years. diff = growth_a - growth_b in percentage points."""
    if a.freq != b.freq or a.freq != "A":
        raise UnitMismatch("ANNUAL_BOTH_REQUIRED")  # growth is unit free; frequency must agree
    ga, gb = growth(a), growth(b)
    yrs = sorted(set(ga) & set(gb))
    diffs = {y: ga[y] - gb[y] for y in yrs}
    if not yrs:
        return {"n": 0}
    ab = sorted(abs(d) for d in diffs.values())
    worst = max(yrs, key=lambda y: abs(diffs[y]))
    r = pearson([float(ga[y]) for y in yrs], [float(gb[y]) for y in yrs])
    return {"n": len(yrs), "first": yrs[0], "last": yrs[-1], "mean_abs_diff_pp": _q(sum(ab) / len(ab)),
            "median_abs_diff_pp": _q(ab[len(ab) // 2]), "max_abs_diff_pp": _q(ab[-1]), "max_diff_year": worst,
            "mean_growth_a": _q(sum(ga[y] for y in yrs) / len(yrs)), "mean_growth_b": _q(sum(gb[y] for y in yrs) / len(yrs)),
            "same_sign": sum(1 for y in yrs if (ga[y] >= 0) == (gb[y] >= 0)),
            "pearson_r": f"{r:.3f}" if r is not None else None, "diffs": {str(y): _q(diffs[y]) for y in yrs}}


def cumulative_drift(rows):
    """Relative level change of a/b between first and last common period (ratio_last/ratio_first - 1, percent)."""
    if len(rows) < 2:
        return None
    return _q((rows[-1]["ratio"] / rows[0]["ratio"] - 1) * 100)


def ratio_break_scan(rows, min_seg=4):
    """Structural-break INDICATOR on log(a/b): best single mean-shift split by Welch t-statistic. Deterministic; an indicator only,
    not a test with a p-value (serial correlation is ignored). Returns None with fewer than 2*min_seg points."""
    xs = [math.log(float(r["ratio"])) for r in rows]
    n = len(xs)
    if n < 2 * min_seg:
        return None
    best = None
    for k in range(min_seg, n - min_seg + 1):
        l, r = xs[:k], xs[k:]
        vl, vr = statistics.variance(l), statistics.variance(r)
        se = math.sqrt(vl / len(l) + vr / len(r))
        t = abs(statistics.fmean(r) - statistics.fmean(l)) / se if se > 0 else float("inf")
        if best is None or t > best[0]:
            best = (t, k)
    t, k = best
    return {"split_before_period": rows[k]["period"], "t_abs": f"{t:.2f}" if math.isfinite(t) else "inf",
            "ratio_mean_before": f"{math.exp(statistics.fmean(xs[:k])):.4f}", "ratio_mean_after": f"{math.exp(statistics.fmean(xs[k:])):.4f}",
            "n_before": k, "n_after": n - k}


def growth_outliers(diffs, k=3.0):
    """Years whose growth difference deviates > k robust sigmas (median/MAD) from the median difference."""
    vals = {y: float(Decimal(v)) for y, v in diffs.items()}
    if len(vals) < 5:
        return []
    med = statistics.median(vals.values())
    mad = statistics.median(abs(v - med) for v in vals.values())
    scale = max(1.4826 * mad, 0.5)  # floor 0.5 pp so a zero MAD does not flag everything
    return sorted(y for y, v in vals.items() if abs(v - med) / scale > k)


def mix_effect(avg, index):
    """Average-price growth minus constant-quality index growth (pp), per year: composition (transaction-mix) effect on the CBS side."""
    ga, gi = growth(avg), growth(index)
    yrs = sorted(set(ga) & set(gi))
    d = [ga[y] - gi[y] for y in yrs]
    if not d:
        return {"n": 0}
    return {"n": len(d), "first": yrs[0], "last": yrs[-1], "mean_pp": _q(sum(d) / len(d)),
            "mean_abs_pp": _q(sum(abs(x) for x in d) / len(d)), "max_abs_pp": _q(max(abs(x) for x in d)),
            "years_gt_2pp": [y for y, x in zip(yrs, d) if abs(x) > 2]}


# ------------------------------------------------------------------ labelled illustration from quoted secondary values
# Quoted, NOT verified against a primary table: ESB 1999 article (NVM Wonen MEDIAN, NLG, existing dwellings; HIST-05) and the
# Vastgoedmarkt table values reported in HIST-01/02 (mean, kEUR, rounded to 1,000). Illustration only, never a series.
ESB_NVM_MEDIAN_NLG = {"1985": 130000, "1990": 159000, "1995": 223000, "1999": 329000}
VM_QUOTED_KEUR = {"1975": 47, "1995": 105}


def illustrative_secondary(cbs_annual):
    """Compare the quoted values with the CBS published annual mean (EUR) on common years. Different statistics / populations:
    each line is a descriptive ratio, not a validation."""
    cbs = as_dict(cbs_annual)
    out = {}
    esb = nlg_to_eur(make_series("esb_nvm_median", "NLG", "median", "A", [(y, Decimal(v)) for y, v in ESB_NVM_MEDIAN_NLG.items()]))
    for y, eur in esb.values:
        if y in cbs:
            out["esb_nvm_median_" + y] = {"nvm_median_nlg": str(ESB_NVM_MEDIAN_NLG[y]), "nvm_median_eur_derived": _q(eur, "1"), "cbs_mean_eur": str(cbs[y]),
                                          "pct_vs_cbs": _q((eur / cbs[y] - 1) * 100), "note": "median vs mean, NVM members vs Kadaster, kosten koper unknown"}
    vm = rescale(make_series("vm", "kEUR", "mean", "A", [(y, Decimal(v)) for y, v in VM_QUOTED_KEUR.items()]), Decimal(1000), "EUR")
    for y, v in vm.values:
        if y in cbs:
            out["vm_quoted_" + y] = {"vm_eur": str(v), "cbs_mean_eur": str(cbs[y]), "abs_diff": str(v - cbs[y]), "pct_vs_cbs": _q((v / cbs[y] - 1) * 100),
                                     "note": "rounded to EUR 1,000 (+-0.5k = +-0.5%); retro-EUR; 'per ultimo' unresolved"}
    return out


# ------------------------------------------------------------------ CBS inputs
def load_cbs_series(path):
    """Committed CSV (date,series,value) -> {series: Series (monthly, EUR or INDEX_2000)}; validates order/dups."""
    raw = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            raw.setdefault(r["series"], []).append((r["date"], r["value"]))
    out = {}
    for k, pairs in raw.items():
        unit = "EUR" if k == "nl_house_avg_eur" else "INDEX_CBS"
        out[k] = make_series("cbs_" + k, unit, "mean" if unit == "EUR" else "index", "M", pairs)
    return out


def cbs_annual_from_typed(rows):
    """CBS OData TypedDataSet rows -> (avg_price Series, index Series, counts dict) for annual rows ('YYYYJJ00')."""
    avg, idx, cnt = [], [], {}
    for r in rows:
        m = re.fullmatch(r"(\d{4})JJ00", str(r.get("Perioden", "")).strip())
        if not m:
            continue
        y = m.group(1)
        for k, v in r.items():
            if v is None:
                continue
            if k.startswith("GemiddeldeVerkoopprijs"):
                avg.append((y, v))
            elif k.startswith("PrijsindexVerkoopprijzen"):
                idx.append((y, v))
            elif k.startswith("AantalVerkochteWoningen"):
                cnt[y] = Decimal(str(v))
    avg.sort()
    idx.sort()
    return (make_series("cbs_avg_annual_published", "EUR", "mean", "A", [(p, Decimal(str(v))) for p, v in avg]),
            make_series("cbs_index_annual_published", "INDEX_CBS", "index", "A", [(p, Decimal(str(v))) for p, v in idx]) if idx else None,
            cnt)


# ------------------------------------------------------------------ probe (network; GitHub Actions only)
VM = "https://vmn-vastgoedmarkt.imgix.net/uploads/2024/07/kerncijfers-vastgoedmarkt-1974-2024.pdf"
ODATA3 = "https://opendata.cbs.nl/ODataApi/OData/"
CATALOG = "https://opendata.cbs.nl/ODataCatalog/Tables?$format=json&$filter="


def build_sources():
    s = {}
    for suffix in ["", "?fm=pdf"] + [f"?page={n}" for n in range(1, 13)] + [f"?page={n}&w=2400" for n in range(1, 13)]:
        s["vm" + re.sub(r"\W+", "-", suffix)] = (VM + suffix, "bin")
    s.update({
        "esb-1981-nbm": ("https://esb.nu/wp-content/uploads/2022/11/editie_pdfs_1981_0233_tcm445-252946.pdf", "pdf"),
        "cbs-longread-2": ("https://www.cbs.nl/nl-nl/longread/de-nederlandse-economie/2022/achtergrond-bij-de-huizenprijsstijgingen-vanaf-2013/2-de-ontwikkeling-van-de-huizenprijzen", "html"),
        "cbs-longread-refs": ("https://www.cbs.nl/nl-nl/longread/de-nederlandse-economie/2022/achtergrond-bij-de-huizenprijsstijgingen-vanaf-2013/verwijzingen", "html"),
        "cpb-2020-note": ("https://www.cpb.nl/sites/default/files/omnidownload/CPB-Notitie-mrt2020-Beweging-op-de-woningmarkt-prijzen-en-volumes.pdf", "pdf"),
        "kss-dallas-wp": ("https://www.dallasfed.org/-/media/Documents/research/international/wpapers/2014/0208.pdf", "pdf"),
        "cpb-2020-note-www": ("https://www.cpb.nl/sites/default/files/omnidownload/CPB-Notitie-mrt2020-Beweging-op-de-woningmarkt-prijzen-en-volumes.pdf", "pdf"),
        "cpb-2020-pub": ("https://www.cpb.nl/beweging-op-de-woningmarkt-prijzen-en-volumes", "html"),
        "cbs-reeks-prijzen": ("https://www.cbs.nl/nl-nl/reeksen/tijd/prijzen-koopwoningen", "html"),
        "zeepbel-80s": ("https://www.huizenmarkt-zeepbel.nl/het-instorten-van-de-huizenprijzen-huizenmarkt-begin-jaren-80/", "html"),
        "hypotheker-1970": ("https://www.hypotheker.nl/blog/wat-kostte-een-huis-in-1970-huizen-werden-19-keer-zo-duur-in-de-laatste-50-jaar/", "html"),
        "cbs-85773-data": (ODATA3 + "85773NED/TypedDataSet", "json"),
        "cbs-cat-consumenten": (CATALOG + "substringof('Consumentenprijzen',Title)", "json"),
        "cbs-cat-prijsindexcijfers": (CATALOG + "substringof('Consumentenprijsindex',Title)", "json"),
    })
    for t in ("71905NED", "70936NED", "83131NED"):
        s["cbs-info-" + t] = (f"{ODATA3}{t}/TableInfos", "json")
    return s


def _run(cmd, data, timeout=120):
    p = subprocess.run(cmd, input=data, capture_output=True, timeout=timeout, check=False)
    return p.returncode, p.stdout, p.stderr


def pdf_text(raw):
    rc, out, _ = _run(["pdftotext", "-layout", "-", "-"], raw)
    return out.decode("utf-8", "replace") if rc == 0 and out else None


def ocr_png(raw, psm):
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "p.png"
        f.write_bytes(raw)
        rc, out, err = _run(["tesseract", str(f), "-", "--psm", str(psm), "-l", "nld+eng"], None, 180)
        return out.decode("utf-8", "replace") if rc == 0 else None


def strip_tags(t):
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", t)
    t = re.sub(r"<[^>]+>", " ", t)
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&#160;", " "), ("&lt;", "<"), ("&gt;", ">")):
        t = t.replace(a, b)
    return re.sub(r"\s+", " ", t).strip()


def contexts(text, pattern, width=170, limit=8):
    out, last = [], -10**9
    for m in re.finditer(pattern, text, re.I):
        if m.start() - last < width:
            continue
        out.append(re.sub(r"\s+", " ", text[max(0, m.start() - width): m.end() + width]))
        last = m.start()
        if len(out) >= limit:
            break
    return out


def magic(raw):
    return "PDF" if raw.startswith(b"%PDF") else "PNG" if raw.startswith(b"\x89PNG") else "JPEG" if raw[:2] == b"\xff\xd8" else "HTML" if raw.lstrip()[:1] == b"<" else "OTHER"


def probe(cbs_csv, pins=None):
    from tools import hist_02_acquire as acq
    srcs = build_sources()
    acq.SOURCES.update(srcs)
    res = {"status": "RESEARCH_ONLY_NOT_APPROVED", "fetch": {}, "defects": [], "vm": {}, "text": {}, "cbs": {}}
    raws = {}
    from concurrent.futures import ThreadPoolExecutor

    def one(sid):
        try:
            return sid, acq.fetch(sid), None
        except acq.AcquisitionError as exc:
            return sid, None, str(exc)[:80]

    with ThreadPoolExecutor(max_workers=8) as ex:
        for sid, got, err in ex.map(one, list(srcs)):
            if err:
                res["fetch"][sid] = {"status": "NOT_RETRIEVED", "error": err}
                print(f"PROGRESS {sid} NOT_RETRIEVED {err}", flush=True)
                continue
            raw, rec = got
            if pins and sid in pins:
                try:
                    verify_sha256(raw, pins[sid])
                except HashMismatch as exc:
                    res["defects"].append({"source": sid, "error": str(exc)})
            raws[sid] = raw
            res["fetch"][sid] = {"status": "FETCHED", "bytes": rec["bytes"], "sha256": rec["sha256"], "kind": magic(raw)}
            print(f"PROGRESS {sid} FETCHED {rec['bytes']} {magic(raw)}", flush=True)

    # --- A. Vastgoedmarkt / NVM table (PDF text if a PDF is served, otherwise OCR of the page images; OCR = derived, unverified)
    for sid, raw in raws.items():
        if not sid.startswith("vm"):
            continue
        kind = magic(raw)
        print(f"PROGRESS processing {sid} {kind}", flush=True)
        texts = {}
        if kind == "PDF":
            t = pdf_text(raw)
            if t:
                texts["pdftotext"] = t
        elif kind == "PNG":
            for psm in (6, 4):
                t = ocr_png(raw, psm)
                if t:
                    texts[f"ocr_psm{psm}"] = t
        entry = {"kind": kind, "methods": {}}
        for m, t in texts.items():
            try:
                blocks = parse_year_rows(t, 1970, 2030)
            except HousingError as exc:
                entry["methods"][m] = {"defect_like": str(exc), "chars": len(t)}
                continue
            big = [b for b in blocks if len(b) >= 8]
            entry["methods"][m] = {"chars": len(t), "blocks_ge8": [{"n": len(b), "first": b[0][0], "last": b[-1][0],
                                                                    "ncols": sorted({len(n) for _, n in b})} for b in big],
                                   "keywords": contexts(t, r"per ultimo|Bron:|NVM|NBM|gemiddelde verkoopprijs|bestaande", 120, 4)}
            if big:
                best = max(big, key=len)
                entry["methods"][m]["table"] = {str(y): [str(x) for x in nums] for y, nums in best}
        res["vm"][sid] = entry

    # --- B. text documents: contexts only
    focus = {"esb-1981-nbm": (pdf_text, r"gemiddeld\w* (koop|verkoop|prijs)|NBM|f ?\d{2,3}\.\d{3}|prijs per woning", 12),
             "cpb-2020-note": (pdf_text, r"NVM|Kadaster|bron|1970|lange reeks|gemiddelde verkoopprijs", 10),
             "kss-dallas-wp": (pdf_text, r"Netherlands|Dutch|Herengracht|Eichholtz", 14),
             "cpb-2020-note-www": (pdf_text, r"NVM|Kadaster|bron|1970|lange reeks|gemiddelde verkoopprijs", 10)}
    for sid, (fn, pat, lim) in focus.items():
        if sid in raws:
            t = fn(raws[sid]) or ""
            res["text"][sid] = {"chars": len(t), "contexts": contexts(t, pat, 200, lim)}
            if sid == "esb-1981-nbm" and t:
                res["text"][sid]["captions"] = [re.sub(r"\s+", " ", c) for c in re.findall(r"Tabel \d+\.[^\n]{0,110}", t)][:20]
                try:
                    bl = parse_year_rows(t, 1970, 1985)
                    res["text"][sid]["blocks"] = [{"n": len(b), "first": b[0][0], "last": b[-1][0], "row0": [str(x) for x in b[0][1][:7]]} for b in bl][:25]
                except HousingError as exc:
                    res["text"][sid]["year_rows_defect"] = str(exc)
            if sid == "kss-dallas-wp" and t:
                i = t.rfind("B.10 The Netherlands")
                tail = t[int(len(t) * 0.55):]
                m = re.search(r"B\.10 The Netherlands\s+[A-Z]", tail) or re.search(r"Land Registry|Kadaster|NVM|NBM", tail)
                res["text"][sid]["b10"] = re.sub(r"\s+", " ", tail[max(0, m.start() - 200): m.start() + 4200]) if m else None
                res["text"][sid]["nl_table"] = contexts(t, r"The Netherlands 1870", 700, 1)
            if sid == "esb-1981-nbm" and t:
                res["text"][sid]["tables"] = {n: re.sub(r"\s+", " ", t[m.start(): m.start() + 1500]) for n in ("1", "2", "5") for m in [re.search(r"Tabel %s\. " % n, t)] if m}
    for sid, pat in {"cbs-longread-2": r"gulden|1978|CPB|NVM|Kadaster|bron:|Bron", "cbs-longread-refs": r"CPB|2020|NVM",
                     "cbs-reeks-prijzen": r"1970|1975|1995|gemiddeld|reeks", "zeepbel-80s": r"NVM|bron|NBM|halfjaar|Kadaster|CBS",
                     "hypotheker-1970": r"bron|NVM|CBS|Kadaster|1970|1975", "cpb-2020-pub": r"NVM|Kadaster|bron|pdf|1970"}.items():
        if sid in raws:
            t = strip_tags(raws[sid].decode("utf-8", "replace"))
            res["text"][sid] = {"chars": len(t), "contexts": contexts(t, pat, 150, 8)}

    # --- C. CBS annual published average (OData) and overlap inputs
    cbs = load_cbs_series(cbs_csv)
    res["cbs"]["committed_csv"] = {k: {"first": s.values[0][0], "last": s.values[-1][0], "n": len(s.values)} for k, s in cbs.items()}
    if "cbs-85773-data" in raws:
        rows = json.loads(raws["cbs-85773-data"].decode("utf-8")).get("value", [])
        avg, idx, cnt = cbs_annual_from_typed(rows)
        res["cbs"]["annual_published"] = {"first": avg.values[0][0], "last": avg.values[-1][0], "n": len(avg.values),
                                          "values": {p: str(v) for p, v in avg.values}, "counts": {k: str(v) for k, v in sorted(cnt.items())}}
        res["_avg"], res["_idx"] = avg, idx
    for sid in ("cbs-cat-consumenten", "cbs-cat-prijsindexcijfers"):
        if sid in raws:
            try:
                rows = json.loads(raws[sid].decode("utf-8")).get("value", [])
                res["cbs"][sid] = [{k: r.get(k) for k in ("Identifier", "Title", "Period", "Modified")} for r in rows[:25]]
            except ValueError:
                res["cbs"][sid] = "UNPARSED"
    for sid in [s for s in raws if s.startswith("cbs-info-")]:
        try:
            v = json.loads(raws[sid].decode("utf-8"))["value"][0]
            res["cbs"][sid] = {k: str(v.get(k))[:120] for k in ("Title", "Period", "Frequency", "ShortDescription")}
        except (ValueError, KeyError, IndexError):
            res["cbs"][sid] = "UNPARSED"

    # --- D. NVM (OCR/pdf table) vs CBS overlap, only when a table with >= 20 rows was recovered and agrees with anchors
    nvm_tables = {}
    for sid, e in res["vm"].items():
        for m, d in e["methods"].items():
            if "table" in d and len(d["table"]) >= 20:
                nvm_tables[f"{sid}/{m}"] = d["table"]
    res["vm_candidate_tables"] = sorted(nvm_tables)
    if nvm_tables and "_avg" in res:
        res["overlap"] = {}
        for key, tab in nvm_tables.items():
            try:
                pairs = [(str(y), nums[0]) for y, nums in sorted((int(y), [Decimal(x) for x in n]) for y, n in tab.items()) if nums]
                nvm = make_series("nvm_vm_" + key, "kEUR", "mean", "A", pairs)
                nvm_eur = rescale(nvm, Decimal(1000), "EUR")
                rows = overlap_rows(nvm_eur, res["_avg"])
                gd = growth_differences(nvm_eur, res["_avg"])
                res["overlap"][key] = {"summary": summarize_rows(rows), "drift_pct": cumulative_drift(rows), "break": ratio_break_scan(rows),
                                       "growth": {k: v for k, v in gd.items() if k != "diffs"}, "outlier_years": growth_outliers(gd.get("diffs", {})),
                                       "rows": [{"y": r["period"], "nvm": _q(r["a"], "1"), "cbs": _q(r["b"], "1"), "pct": _q(r["pct_diff_of_b"])} for r in rows]}
                if "_idx" in res and res["_idx"]:
                    res["overlap"][key]["nvm_growth_vs_cbs_hpi"] = {k: v for k, v in growth_differences(
                        Series(nvm.name, "INDEX_CBS", "index", "A", nvm.values), res["_idx"]).items() if k != "diffs"}
            except HousingError as exc:
                res["overlap"][key] = {"defect": str(exc)}
                res["defects"].append({"source": key, "error": str(exc)})
    # CBS-side mix effect, 2000-2025 (monthly committed CSV -> annual mean, labelled)
    a_m = annual_mean_of_complete_years(cbs["nl_house_avg_eur"])
    i_m = annual_mean_of_complete_years(cbs["nl_hpi"])
    res["cbs"]["mix_effect_avg_vs_hpi_committed"] = mix_effect(a_m, i_m)
    if "_avg" in res and res.get("_idx"):
        res["cbs"]["mix_effect_avg_vs_hpi_published_annual"] = mix_effect(res["_avg"], res["_idx"])
    if "_avg" in res:
        res["illustration"] = illustrative_secondary(res["_avg"])
    res.pop("_avg", None)
    res.pop("_idx", None)
    return res


def digest(doc, section="all"):
    """Compact, sectioned text view; the CI log tail is small, so the workflow prints one section at a time."""
    L = [f"status={doc['status']} defects={len(doc['defects'])} section={section}"]
    want = lambda n: section in ("all", n)  # noqa: E731
    if want("fetch"):
        groups = {}
        for sid, f in doc["fetch"].items():
            if f["status"] == "FETCHED" and sid.startswith("vm"):
                groups.setdefault((f["sha256"][:12], f["kind"], f["bytes"]), []).append(sid)
            else:
                L.append(f"FETCH {sid}: {f['status']} {f.get('kind','')} {f.get('bytes','')} {f.get('sha256','')[:12]} {f.get('error','')}")
        for (sh, kind, n), sids in groups.items():
            L.append(f"VMFETCH {sh} {kind} {n}B x{len(sids)}: {','.join(x[3:] or 'base' for x in sids)[:150]}")
    if want("vm"):
        seen = set()
        for sid, e in doc["vm"].items():
            for m, d in e["methods"].items():
                sig = (d.get("chars"), json.dumps(d.get("blocks_ge8")), d.get("defect_like"))
                if sig in seen:
                    continue
                seen.add(sig)
                L.append(f"VM {sid} {m}: chars={d.get('chars')} blocks={d.get('blocks_ge8')} {d.get('defect_like','')}")
                for k in d.get("keywords", [])[:3]:
                    L.append("  KW " + k[:200])
                if "table" in d:
                    L.append("  VMTABLE " + json.dumps(d["table"], sort_keys=True)[:1800])
    for sid, d in doc["text"].items():
        if want("text") or want(sid):
            L.append(f"TEXT {sid} chars={d['chars']}")
            for c in d["contexts"]:
                L.append("  CTX " + c[:300])
            for k in ("captions", "tables", "nl_table", "b10"):
                if d.get(k):
                    L.append(f"  {k} " + json.dumps(d[k])[:2400])
    if want("cbs"):
        L.append("CBS " + json.dumps(doc["cbs"], sort_keys=True)[:4500])
    if want("cbs") and "illustration" in doc:
        L.append("ILLUSTRATION " + json.dumps(doc["illustration"], sort_keys=True)[:3000])
    if want("overlap") and "overlap" in doc:
        L.append("OVERLAP " + json.dumps(doc["overlap"], sort_keys=True)[:7000])
    return "\n".join(L)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("probe")
    a.add_argument("--cbs-csv", required=True)
    a.add_argument("--summary-out", required=True)
    a.add_argument("--pins", help="JSON {source_id: sha256}; a mismatch fails the run")
    d = sub.add_parser("digest")
    d.add_argument("path")
    d.add_argument("--section", default="all")
    args = p.parse_args(argv)
    if args.cmd == "digest":
        print(digest(json.loads(Path(args.path).read_text()), args.section))
        return 0
    pins = json.loads(Path(args.pins).read_text()) if args.pins else None
    try:
        doc = probe(args.cbs_csv, pins)
    except HousingError as exc:
        print(f"FAIL_CLOSED {exc}", file=sys.stderr)
        return 1
    Path(args.summary_out).write_text(json.dumps(doc, sort_keys=True, indent=1, default=str) + "\n")
    print(f"summary written; defects={len(doc['defects'])}")
    return 1 if doc["defects"] else 0


if __name__ == "__main__":
    sys.exit(main())
