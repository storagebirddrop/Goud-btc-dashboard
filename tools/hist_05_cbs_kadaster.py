"""HIST-05 research-only: Dutch house-price history before 2000 (CBS StatLine, Kadaster). Nothing approved.

What this probes (all from GitHub Actions; the dev sandbox cannot reach external hosts):
  * the CBS legacy OData catalogue (title keyword searches) and, for relevant tables, TableInfos,
    DataProperties and TypedDataSet; plus the OData v4 route for the two tables of the repo fixture;
  * CBS and Kadaster pages (terms, methodology, links to historical series).
Each candidate gets a status: OBTAINED (fetched and parsed in CI), REFERENCE_ONLY (only a link or mention
in an obtained page, nothing retrieved), UNREACHABLE (fetch failed; HTTP code or error class recorded).

Rules: Decimal parsing; missing values stay None and are counted, never filled; duplicate period codes and
non-numeric/invalid values are hard errors (exit 1); unreachable or non-matching sources are findings (exit 0,
listed in missing_sources). No interpolation, no synthetic monthly values, no back-calculation of price levels
from an index, no linking or splicing of series. Comparisons are descriptive statistics on shared periods.
Acquisition reuses tools.hist_02_acquire.fetch (exact-URL allowlist, 15 MB limit, sha256); raw bytes stay in
memory; the output holds aggregates, short quotes, and sha256 of fetched bodies only.
"""
import argparse
import hashlib
import json
import re
import statistics
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import build_opener

from tools import hist_02_acquire
from tools.hist_03_worldbank_validate import canonical_sha256

ODATA3 = "https://opendata.cbs.nl/ODataApi/OData/"
ODATA4 = "https://datasets.cbs.nl/odata/v1/CBS/"
CATALOG = "https://opendata.cbs.nl/ODataCatalog/Tables?$format=json&$filter="
FIXTURE_PATH = Path(__file__).resolve().parents[1] / "data" / "fixtures" / "cbs-1995-1999-i1.json"

# Tables named by the task; their existence/content is established only by the CI fetch.
FIXED_TABLES = ["85773NED", "83906NED", "83913NED", "81884NED", "82101NED"]
V4_TABLES = ["85773NED", "83906NED"]
CATALOG_KEYWORDS = ["woning", "koopwoning", "verkoopprijs", "prijsindex", "woningprijs", "huizenprijs",
                    "historisch", "eeuw", "dwelling", "house"]
HOUSING_TITLE = re.compile(r"woning|woon|huis|koop|verkoop|onroerend|vastgoed|eigen|hypotheek|dwelling|house|housing|real estate|purchase", re.I)
MAX_DISCOVERED = 12
TABLE_ID_RE = re.compile(r"[0-9A-Za-z]{4,10}")

# id -> (url, format, group); groups: page, catalog, table
PAGES = {
    "cbs-copyright-nl": ("https://www.cbs.nl/nl-nl/over-ons/website/copyright", "html", "page"),
    "cbs-copyright-en": ("https://www.cbs.nl/en-gb/about-us/website/copyright", "html", "page"),
    "cbs-open-data-nl": ("https://www.cbs.nl/nl-nl/onze-diensten/open-data", "html", "page"),
    "cbs-85773ned-page": ("https://www.cbs.nl/nl-nl/cijfers/detail/85773NED", "html", "page"),
    "cbs-method-prijsindex-bkw": ("https://www.cbs.nl/nl-nl/onze-diensten/methoden/onderzoeksomschrijvingen/korte-onderzoeksbeschrijvingen/prijsindex-bestaande-koopwoningen", "html", "page"),
    "kadaster-home": ("https://www.kadaster.nl/", "html", "page"),
    "kadaster-open-data": ("https://www.kadaster.nl/over-ons/open-data", "html", "page"),
    "kadaster-vastgoedcijfers": ("https://www.kadaster.nl/zakelijk/vastgoedinformatie/vastgoedcijfers", "html", "page"),
    "kadaster-woningmarkt-cijfers": ("https://www.kadaster.nl/zakelijk/vastgoedinformatie/kadaster-cijfers", "html", "page"),
}
CANDIDATES = dict(PAGES)
for _kw in CATALOG_KEYWORDS:
    CANDIDATES[f"catalog-{_kw}"] = (CATALOG + f"substringof(%27{_kw}%27,Title)", "json", "catalog")
for _t in FIXED_TABLES:
    CANDIDATES[f"cbs3-{_t}-info"] = (f"{ODATA3}{_t}/TableInfos", "json", "table")
    CANDIDATES[f"cbs3-{_t}-props"] = (f"{ODATA3}{_t}/DataProperties", "json", "table")
    CANDIDATES[f"cbs3-{_t}-data"] = (f"{ODATA3}{_t}/TypedDataSet", "json", "table")
for _t in V4_TABLES:
    CANDIDATES[f"cbs4-{_t}-measures"] = (f"{ODATA4}{_t}/MeasureCodes", "json", "table4")
    CANDIDATES[f"cbs4-{_t}-dims"] = (f"{ODATA4}{_t}/Dimensions", "json", "table4")
    CANDIDATES[f"cbs4-{_t}-obs"] = (f"{ODATA4}{_t}/Observations", "json", "table4")
hist_02_acquire.SOURCES.update({k: (v[0], v[1]) for k, v in CANDIDATES.items()})


class Hist05Error(ValueError):
    """Real parser/integrity defect (fail closed); never raised for mere unreachability."""


# ---------------------------------------------------------------- acquisition
def register_table(tid):
    """Register the three exact legacy-OData URLs of a catalogue-discovered table id (validated)."""
    if not TABLE_ID_RE.fullmatch(tid or ""):
        raise Hist05Error("INVALID_TABLE_ID")
    for suffix, name in (("TableInfos", "info"), ("DataProperties", "props"), ("TypedDataSet", "data")):
        sid = f"cbs3-{tid}-{name}"
        CANDIDATES[sid] = (f"{ODATA3}{tid}/{suffix}", "json", "table")
        hist_02_acquire.SOURCES[sid] = (CANDIDATES[sid][0], "json")


def fetch_status(sid, opener=None):
    """Fetch one candidate via hist_02_acquire.fetch. Returns (raw|None, entry) with explicit status and HTTP code."""
    entry = {"source_id": sid, "url": hist_02_acquire.SOURCES[sid][0]}
    seen = {}
    if opener is None:
        base = build_opener(hist_02_acquire.RestrictedRedirect(sid)).open

        def opener(req, timeout=None):
            try:
                return base(req, timeout=timeout)
            except HTTPError as exc:
                seen["code"] = exc.code
                raise
    try:
        raw, rec = hist_02_acquire.fetch(sid, opener=opener)
    except hist_02_acquire.AcquisitionError as exc:
        entry.update(status="UNREACHABLE", error=str(exc)[:160], http_status=seen.get("code"))
        return None, entry
    entry.update(status="FETCHED", http_status=rec["http_status"], bytes=rec["bytes"], sha256=rec["sha256"])
    return raw, entry


# ---------------------------------------------------------------- periods and values
PERIOD_RE = re.compile(r"(\d{4})(MM|KW|JJ)(\d{2})")


def parse_period(code):
    """CBS period code -> (frequency, label) or None. '1995MM01' -> ('M','1995-01'), '1995KW02' -> ('Q','1995-Q2'),
    '1995JJ00' or '1995' -> ('A','1995'). Anything else (half years, weeks, 'X0' totals) -> None (counted, not guessed)."""
    c = str(code).strip()
    if re.fullmatch(r"\d{4}", c):
        return "A", c
    m = PERIOD_RE.fullmatch(c)
    if not m:
        return None
    y, kind, n = m.group(1), m.group(2), int(m.group(3))
    if kind == "MM" and 1 <= n <= 12:
        return "M", f"{y}-{n:02d}"
    if kind == "KW" and 1 <= n <= 4:
        return "Q", f"{y}-Q{n}"
    if kind == "JJ" and n == 0:
        return "A", y
    return None


def periods_between(freq, first, last):
    """Complete expected label sequence between first and last (inclusive)."""
    if freq == "A":
        return [str(y) for y in range(int(first), int(last) + 1)]
    if freq == "M":
        (y0, m0), (y1, m1) = map(lambda s: (int(s[:4]), int(s[5:7])), (first, last))
        return [f"{y0 + (m0 - 1 + i) // 12}-{(m0 - 1 + i) % 12 + 1:02d}" for i in range((y1 - y0) * 12 + m1 - m0 + 1)]
    (y0, q0), (y1, q1) = map(lambda s: (int(s[:4]), int(s[-1])), (first, last))
    return [f"{y0 + (q0 - 1 + i) // 4}-Q{(q0 - 1 + i) % 4 + 1}" for i in range((y1 - y0) * 4 + q1 - q0 + 1)]


def to_value(v, where):
    """JSON value -> Decimal or None. None/'' = missing (kept missing). Strings/booleans/NaN: hard error."""
    if v is None or v == "":
        return None
    if isinstance(v, bool) or isinstance(v, str):
        raise Hist05Error(f"INVALID_NUMERIC {where}")
    try:
        d = v if isinstance(v, Decimal) else Decimal(str(v))
    except InvalidOperation as exc:
        raise Hist05Error(f"INVALID_NUMERIC {where}") from exc
    if not d.is_finite():
        raise Hist05Error(f"INVALID_NUMERIC {where}")
    return d


def load_json(raw):
    try:
        doc = json.loads(raw.decode("utf-8-sig"), parse_float=Decimal, parse_int=Decimal)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Hist05Error("NOT_JSON") from exc
    return doc


def value_list(doc):
    if not isinstance(doc, dict) or not isinstance(doc.get("value"), list):
        raise Hist05Error("MISSING_VALUE_ARRAY")
    return doc["value"]


# ---------------------------------------------------------------- measures
def classify_measure(title, unit):
    """Return {kind, currency, base} from title/unit text. kind in PRICE_LEVEL, INDEX, CHANGE_PCT, COUNT, OTHER."""
    t, u = str(title or "").lower(), str(unit or "").lower()
    both = t + " | " + u
    base = re.search(r"(\d{4}\s*=\s*100)", both)
    if base or re.search(r"\bindex\b|indexcijfer", both):
        kind = "INDEX"
    elif "%" in u or "procent" in u or "mutatie" in t or "verandering" in t:
        kind = "CHANGE_PCT"
    elif re.search(r"euro|gulden|nlg|eur\b|€", u):
        kind = "PRICE_LEVEL"
    elif re.search(r"aantal|number", both) or u in ("aantal", "number"):
        kind = "COUNT"
    else:
        kind = "OTHER"
    cur = "EUR" if re.search(r"euro|eur\b|€", u) else "NLG" if re.search(r"gulden|nlg", u) else None
    return {"kind": kind, "currency": cur, "base": re.sub(r"\s", "", base.group(1)) if base else None}


def parse_props(doc):
    """DataProperties -> {'topics': {key: {title, unit, ...classification}}, 'period_key', 'dimensions': [keys]}."""
    topics, dims, period_key = {}, [], None
    for p in value_list(doc):
        typ, key = str(p.get("Type", "")), p.get("Key")
        if not isinstance(key, str):
            continue
        if "Topic" in typ and "Group" not in typ:
            topics[key] = {"title": str(p.get("Title", ""))[:140], "unit": str(p.get("Unit") or "")[:40]}
            topics[key].update(classify_measure(p.get("Title"), p.get("Unit")))
        elif "TimeDimension" in typ:
            period_key = key
        elif "Dimension" in typ:  # Dimension, GeoDimension
            dims.append(key)
    return {"topics": topics, "period_key": period_key, "dimensions": dims}


# ---------------------------------------------------------------- data tables
def parse_typed(doc, props):
    """Legacy TypedDataSet -> {(measure_key, dims_tuple): {freq: {label: Decimal|None}}}; hard errors on duplicates/invalid."""
    pkey = props["period_key"]
    if not pkey or not props["topics"]:
        raise Hist05Error("NO_PERIOD_OR_TOPICS")
    series, unsupported = {}, {}
    seen = set()
    for row in value_list(doc):
        pc = parse_period(row.get(pkey, ""))
        if pc is None:
            unsupported[str(row.get(pkey, ""))[:12]] = unsupported.get(str(row.get(pkey, ""))[:12], 0) + 1
            continue
        dims = tuple(str(row.get(d, "")).strip() for d in props["dimensions"])
        if (dims, pc) in seen:
            raise Hist05Error(f"DUPLICATE_PERIOD {pc[1]} {dims}")
        seen.add((dims, pc))
        for key in props["topics"]:
            if key not in row:
                continue
            val = to_value(row[key], f"{key}@{pc[1]}")
            series.setdefault((key, dims), {}).setdefault(pc[0], {})[pc[1]] = val
    return series, unsupported


def parse_observations_v4(rows, period_key="Perioden"):
    """OData v4 Observations -> {(measure_id, ()): {freq: {label: Decimal|None}}}; duplicates are hard errors."""
    series, unsupported, seen = {}, {}, set()
    for r in rows:
        pc = parse_period(r.get(period_key, ""))
        if pc is None:
            unsupported[str(r.get(period_key, ""))[:12]] = unsupported.get(str(r.get(period_key, ""))[:12], 0) + 1
            continue
        measure = r.get("Measure")
        if not isinstance(measure, str):
            raise Hist05Error("MISSING_MEASURE")
        if (measure, pc) in seen:
            raise Hist05Error(f"DUPLICATE_PERIOD {pc[1]} {measure}")
        seen.add((measure, pc))
        series.setdefault((measure, ()), {}).setdefault(pc[0], {})[pc[1]] = to_value(r.get("Value"), f"{measure}@{pc[1]}")
    return series, unsupported


def series_facts(freq_map, kind):
    """Per-frequency coverage facts; rules: observed = non-missing; gaps = absent or null periods between first and last."""
    out = {}
    for freq, pts in sorted(freq_map.items()):
        obs = {k: v for k, v in pts.items() if v is not None}
        if not obs:
            out[freq] = {"observations": 0, "null_values": len(pts)}
            continue
        labels = sorted(obs)
        expected = periods_between(freq, labels[0], labels[-1])
        gaps = [p for p in expected if p not in obs]
        vals = [obs[k] for k in labels]
        if kind in ("PRICE_LEVEL", "INDEX") and any(v <= 0 for v in vals):
            raise Hist05Error("NON_POSITIVE_LEVEL_OR_INDEX")
        out[freq] = {"observations": len(obs), "null_values": len(pts) - len(obs), "first": labels[0], "last": labels[-1],
                     "gap_count": len(gaps), "gaps_head": gaps[:8], "first_value": str(obs[labels[0]]), "last_value": str(obs[labels[-1]]),
                     "min": str(min(vals)), "max": str(max(vals))}
        if freq == "M" and not gaps:
            out[freq]["canonical_sha256"] = canonical_sha256(obs, labels)
    return out


def table_summary(series, unsupported, topics):
    """Aggregate per measure; with dimensions keep the 4 combos with most observations (rest counted)."""
    by_measure = {}
    for (key, dims), fm in series.items():
        by_measure.setdefault(key, []).append((dims, fm))
    out = {}
    for key, combos in sorted(by_measure.items()):
        meta = topics.get(key, {})
        combos.sort(key=lambda c: -sum(len(p) for p in c[1].values()))
        kept = []
        for dims, fm in combos[:4]:
            kept.append({"dimensions": list(dims), "frequencies": series_facts(fm, meta.get("kind"))})
        out[key] = {"title": meta.get("title"), "unit": meta.get("unit"), "kind": meta.get("kind"), "currency": meta.get("currency"),
                    "base": meta.get("base"), "dimension_combinations": len(combos), "shown": kept}
    return {"measures": out, "unsupported_period_codes": dict(sorted(unsupported.items())[:6])}


def single_series(series, key, freq):
    """The series of one measure/frequency if there is exactly one dimension combination, else None."""
    combos = [fm for (k, _), fm in series.items() if k == key and freq in fm]
    return combos[0][freq] if len(combos) == 1 else None


def pick_price_measure(topics, require_words=("verkoopprijs",)):
    hits = [k for k, t in topics.items() if t["kind"] == "PRICE_LEVEL" and all(w in t["title"].lower() for w in require_words)]
    return hits[0] if len(hits) == 1 else None


# ---------------------------------------------------------------- comparison (descriptive; never a splice)
def compare_series(a, b):
    """Descriptive statistics on shared non-missing periods of two {label: Decimal|None} maps."""
    common = sorted(k for k in set(a) & set(b) if a[k] is not None and b[k] is not None)
    if not common:
        return {"common_periods": 0}
    diffs = [a[k] - b[k] for k in common]
    ratios = sorted(a[k] / b[k] for k in common)
    worst = max(common, key=lambda k: abs(a[k] - b[k]))
    return {"common_periods": len(common), "first": common[0], "last": common[-1],
            "exact_equal": sum(1 for d in diffs if d == 0), "max_abs_diff": str(max(abs(d) for d in diffs)),
            "max_abs_diff_period": worst, "median_ratio_a_over_b": str(ratios[len(ratios) // 2].quantize(Decimal("0.000001"))),
            "mean_abs_diff": str((sum(abs(d) for d in diffs) / len(diffs)).quantize(Decimal("0.0001")))}


def level_continuity(monthly, before="1999-12", after="2000-01", window=12):
    """Descriptive month-on-month change at the 1999/2000 boundary vs the typical |mom| change in the prior year."""
    if monthly.get(before) is None or monthly.get(after) is None:
        return {"status": "NOT_AVAILABLE"}
    mom = {}
    labs = sorted(k for k, v in monthly.items() if v is not None)
    for p, c in zip(labs, labs[1:]):
        if c <= after and periods_between("M", p, c) == [p, c]:
            mom[c] = (monthly[c] / monthly[p] - 1) * 100
    prior = [abs(v) for k, v in mom.items() if k < after][-window:]
    jump = mom.get(after)
    q = Decimal("0.001")
    return {"status": "COMPUTED", "boundary_change_pct": str(jump.quantize(q)) if jump is not None else None,
            "median_abs_mom_pct_prior_window": str(Decimal(str(statistics.median(prior))).quantize(q)) if prior else None,
            "window_months": len(prior), "note": "descriptive only; same table, no splice"}


def load_fixture(path=FIXTURE_PATH):
    doc = json.loads(Path(path).read_text(encoding="utf-8"), parse_float=Decimal, parse_int=Decimal)
    series = {}
    for r in doc["data"]:
        if r["series"] == "nl_house_avg_eur":
            series[r["date"]] = Decimal(str(r["value"]))
    return series


# ---------------------------------------------------------------- pages and rights
def strip_tags(html):
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    return re.sub(r"\s+", " ", re.sub(r"(?s)<[^>]+>", " ", t)).strip()


RIGHTS_RE = re.compile(r"CC[ -]?BY|Creative Commons|CC0|bronvermelding|source|licen[cs]|open data|hergebruik|re-use|reuse", re.I)
LINK_RE = re.compile(r"kadaster|prijs|woning|woningmarkt|koopwoning|historisch|reeks|tijdreeks|eeuw|jaarboek|statline|opendata|odata", re.I)


def page_facts(raw, max_quotes=6, max_links=25):
    text = raw.decode("utf-8", "replace")
    title = re.search(r"(?is)<title[^>]*>(.*?)</title>", text)
    plain = strip_tags(text)
    quotes = []
    for s in re.split(r"(?<=[.!?])\s+", plain):
        if RIGHTS_RE.search(s) and 30 <= len(s) <= 400 and len(quotes) < max_quotes:
            quotes.append(s[:300])
    links = []
    for h in re.findall(r"""(?i)href\s*=\s*["']([^"'#\s]+)""", text):
        if LINK_RE.search(h) and h not in links:
            links.append(h[:170])
    return {"html_title": strip_tags(title.group(1))[:120] if title else None, "text_chars": len(plain), "rights_quotes": quotes,
            "matching_links": links[:max_links], "matching_link_count": len(links)}


def rights_level(entry):
    if entry.get("status") != "FETCHED":
        return "NOT_RETRIEVED"
    return "OFFICIAL_TEXT_READ" if entry.get("page", {}).get("rights_quotes") else "NOT_RETRIEVED"


# ---------------------------------------------------------------- catalogue
def catalog_rows(doc):
    out = []
    for r in value_list(doc):
        ident = r.get("Identifier")
        if not isinstance(ident, str) or not TABLE_ID_RE.fullmatch(ident.strip()):
            continue
        period = str(r.get("Period") or "")
        years = [int(y) for y in re.findall(r"\b(1[5-9]\d{2}|20\d{2})\b", period)]
        out.append({"id": ident.strip(), "title": str(r.get("Title") or "")[:160], "period": period[:60],
                    "frequency": str(r.get("Frequency") or "")[:30], "language": str(r.get("Language") or "")[:5],
                    "modified": str(r.get("Modified") or "")[:25], "start_year": min(years) if years else None,
                    "end_year": max(years) if years else None})
    return out


def pick_discovered(rows, exclude, limit=MAX_DISCOVERED):
    """Housing-related tables with a start year before 2000 that are not already fixed candidates (oldest first)."""
    seen, picked = set(exclude), []
    for r in sorted(rows, key=lambda r: (r["start_year"] or 9999, r["id"])):
        if r["id"] in seen or r["start_year"] is None or r["start_year"] >= 2000 or not HOUSING_TITLE.search(r["title"]):
            continue
        seen.add(r["id"])
        picked.append(r)
        if len(picked) >= limit:
            break
    return picked


# ---------------------------------------------------------------- orchestration
def analyse_table(tid, raws):
    """Parse info/props/data of one legacy-OData table from the raw dict {name: bytes}; returns (summary, parsed)."""
    res = {"table_id": tid}
    if "info" in raws:
        info = value_list(load_json(raws["info"]))
        if info:
            res["info"] = {k: str(info[0].get(k))[:200] for k in ("Title", "Period", "Frequency", "Modified", "Language", "Source", "Summary") if info[0].get(k) is not None}
    if "props" not in raws or "data" not in raws:
        res["status"] = "PARTIAL_" + ",".join(sorted(raws)) if raws else "NOTHING_OBTAINED"
        return res, None
    props = parse_props(load_json(raws["props"]))
    doc = load_json(raws["data"])
    series, unsupported = parse_typed(doc, props)
    res["status"] = "OBTAINED"
    res["odata_next_link_present"] = isinstance(doc, dict) and any("nextLink" in k for k in doc)
    res["dimensions"] = props["dimensions"]
    res["summary"] = table_summary(series, unsupported, props["topics"])
    return res, (series, props)


def run_tables(tids, results, defects, missing, parsed_store):
    for tid in tids:
        raws = {}
        for name in ("info", "props", "data"):
            sid = f"cbs3-{tid}-{name}"
            raw, entry = fetch_status(sid)
            results.append(entry)
            print(json.dumps({sid: {k: entry.get(k) for k in ("status", "http_status", "bytes", "error")}}, sort_keys=True), flush=True)
            if raw is None:
                missing.append(sid)
            else:
                raws[name] = raw
        try:
            res, parsed = analyse_table(tid, raws)
        except Hist05Error as exc:
            msg = str(exc)
            if msg in ("NOT_JSON", "MISSING_VALUE_ARRAY", "NO_PERIOD_OR_TOPICS"):  # wrong shape/endpoint: finding
                res, parsed = {"table_id": tid, "status": "FORMAT_NOT_USABLE", "reason": msg}, None
            else:  # duplicates, invalid numerics, non-positive levels: real integrity defects
                res, parsed = {"table_id": tid, "status": "DEFECT", "defect": msg[:200]}, None
                defects.append(f"{tid}:{msg[:80]}")
        results.append({"table_analysis": res})
        if parsed:
            parsed_store[tid] = parsed


def comparisons(parsed_store, v4_store, fixture):
    out = {}
    primary = {}
    for tid, (series, props) in parsed_store.items():
        key = pick_price_measure(props["topics"], ("verkoopprijs",))
        if key and single_series(series, key, "M"):
            primary[tid] = (key, single_series(series, key, "M"))
    out["price_measure_keys"] = {t: k for t, (k, _) in primary.items()}
    for tid, (key, mon) in sorted(primary.items()):
        out[f"fixture_1995_1999_vs_{tid}"] = compare_series(fixture, mon)
        out[f"{tid}_boundary_1999_12_to_2000_01"] = level_continuity(mon)
    ids = sorted(primary)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            out[f"{a}_vs_{b}"] = compare_series(primary[a][1], primary[b][1])
    for tid, mon in v4_store.items():
        if tid in primary:
            out[f"v3_vs_v4_{tid}"] = compare_series(primary[tid][1], mon)
    out["fixture_months"] = len(fixture)
    return out


def run_v4(tid, results, missing, defects, v4_store, props3=None):
    raws = {}
    for name in ("measures", "dims", "obs"):
        sid = f"cbs4-{tid}-{name}"
        raw, entry = fetch_status(sid)
        results.append(entry)
        print(json.dumps({sid: {k: entry.get(k) for k in ("status", "http_status", "bytes", "error")}}, sort_keys=True), flush=True)
        if raw is None:
            missing.append(sid)
        else:
            raws[name] = raw
    if set(raws) != {"measures", "dims", "obs"}:
        return
    try:
        measures = value_list(load_json(raws["measures"]))
        dims = value_list(load_json(raws["dims"]))
        pk = next((d.get("Identifier") for d in dims if "period" in str(d.get("Identifier", "")).lower()), "Perioden")
        obs_doc = load_json(raws["obs"])
        series, unsupported = parse_observations_v4(value_list(obs_doc), pk)
    except Hist05Error as exc:
        if str(exc) in ("NOT_JSON", "MISSING_VALUE_ARRAY"):
            results.append({"table_analysis": {"table_id": tid, "route": "v4", "status": "FORMAT_NOT_USABLE", "reason": str(exc)}})
        else:
            defects.append(f"v4:{tid}:{str(exc)[:80]}")
            results.append({"table_analysis": {"table_id": tid, "route": "v4", "status": "DEFECT", "defect": str(exc)[:200]}})
        return
    titles = {m.get("Identifier"): str(m.get("Title", "")) for m in measures}
    topics = {k: {"title": titles.get(k, "")[:140], "unit": str(next((m.get("Unit") for m in measures if m.get("Identifier") == k), "") or "")[:40],
                  **classify_measure(titles.get(k), next((m.get("Unit") for m in measures if m.get("Identifier") == k), ""))} for k, _ in series}
    results.append({"table_analysis": {"table_id": tid, "route": "v4", "status": "OBTAINED", "odata_next_link_present": "@odata.nextLink" in obs_doc,
                                       "summary": table_summary(series, unsupported, topics)}})
    key = pick_price_measure(topics)
    if key and single_series(series, key, "M"):
        v4_store[tid] = single_series(series, key, "M")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary-out", required=True)
    args = ap.parse_args(argv)
    results, missing, defects, parsed_store, v4_store = [], [], [], {}, {}
    catalog_found = {}
    for sid, (url, fmt, group) in sorted(CANDIDATES.items()):
        if group not in ("page", "catalog"):
            continue
        raw, entry = fetch_status(sid)
        print(json.dumps({sid: {k: entry.get(k) for k in ("status", "http_status", "bytes", "error")}}, sort_keys=True), flush=True)
        if raw is None:
            missing.append(sid)
        elif group == "page":
            entry["page"] = page_facts(raw)
            entry["rights_evidence"] = rights_level(entry)
        else:
            try:
                rows = catalog_rows(load_json(raw))
                entry["catalog_rows"] = len(rows)
                for r in rows:
                    catalog_found[r["id"]] = r
            except Hist05Error as exc:
                entry["format_unparsed"] = str(exc)
        results.append(entry)
    pre2000 = sorted((r for r in catalog_found.values() if r["start_year"] is not None and r["start_year"] < 2000 and HOUSING_TITLE.search(r["title"])),
                     key=lambda r: (r["start_year"], r["id"]))
    discovered = pick_discovered(list(catalog_found.values()), FIXED_TABLES)
    for r in discovered:
        register_table(r["id"])
    run_tables(FIXED_TABLES + [r["id"] for r in discovered], results, defects, missing, parsed_store)
    for tid in V4_TABLES:
        run_v4(tid, results, missing, defects, v4_store)
    try:
        fixture = load_fixture()
    except (OSError, ValueError, KeyError) as exc:
        fixture = {}
        defects.append(f"fixture:{type(exc).__name__}")
    cmp_ = comparisons(parsed_store, v4_store, fixture) if not defects else {}
    summary = {"status": "DONE", "nothing_approved": True, "rights_status": "UNVERIFIED", "publication_authorized": False,
               "source_approved": False, "catalog_distinct_tables": len(catalog_found),
               "catalog_housing_tables_start_before_2000": pre2000[:60], "discovered_fetched": [r["id"] for r in discovered],
               "results": results, "comparisons": cmp_, "missing_sources": sorted(missing), "defects": defects}
    out = Path(args.summary_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: summary[k] for k in ("status", "catalog_distinct_tables", "discovered_fetched", "missing_sources", "defects")}, sort_keys=True))
    return 1 if defects else 0


if __name__ == "__main__":
    sys.exit(main())
