"""HIST-04 research-only FX handling for gold-per-house in NLG/EUR (CANDIDATE, not approved).

Quote directions (every quote is 'quoted-currency units per 1 base unit'):
  Fed G.5 NLG    : NLG per 1 USD   (foreign currency per USD)           -> 'NLG_PER_USD'
  ECB EXR USD    : USD per 1 EUR   (foreign currency per EUR)           -> 'USD_PER_EUR'
  Fixed conversion (Council Reg. (EC) 2866/98): 1 EUR = 2.20371 NLG     -> 'NLG_PER_EUR'
Chain (Decimal only): gold NLG/oz = gold USD/oz * NLG_PER_USD ; gold EUR/oz = gold USD/oz / USD_PER_EUR ;
NLG->EUR = NLG / 2.20371 (labelled derivation only). Implied USD_PER_EUR from G.5 = 2.20371 / NLG_PER_USD.
Monthly aggregation: arithmetic mean OF THE QUOTED DIRECTION first, convert/invert AFTER averaging. The
Jensen gap mean(1/x) vs 1/mean(x) is measured, never silently mixed. No interpolation, no forward-fill of
weekends/holidays, missing (ND / absent) stays absent. Acquisition reuses tools.hist_02_acquire.fetch;
output is aggregates/metadata only; raw bytes stay in memory. No publication, no repository data writes.
"""
import argparse
import csv
import io
import json
import re
import sys
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path

from tools import hist_02_acquire

NLG_PER_EUR = Decimal("2.20371")  # Council Regulation (EC) No 2866/98, Art. 1 (verify against EUR-Lex in the doc)
DIRECTIONS = {"fed_g5_nlg": "NLG_PER_USD", "ecb_exr_usd": "USD_PER_EUR", "fixed_eur_nlg": "NLG_PER_EUR"}
PRECISION = 34
FED_MISSING = {"ND", "NC", "", "NA", "."}
VALUE_RE = re.compile(r"\d+(\.\d+)?")
FED_BASE = "https://www.federalreserve.gov/datadownload/"
ECB_BASE = "https://data-api.ecb.europa.eu/service/data/EXR/"
ECB_DAILY, ECB_MONTHLY = "ecb-exr-d-usd", "ecb-exr-m-usd"
FED_ZIP = "fed-g5-xml-zip"
DISCOVERY_PAGES = {  # Choose/Build.aspx?rel=G5 answered HTTP 400 in CI run 39437923033; kept out
    "fed-g5-release": ("https://www.federalreserve.gov/releases/g5/default.htm", "html"),
    "fed-g5-current": ("https://www.federalreserve.gov/releases/g5/current/default.htm", "html"),
    "fed-g5a-current": ("https://www.federalreserve.gov/releases/g5a/current/default.htm", "html"),
}
STATIC_SOURCES = {
    ECB_DAILY: (ECB_BASE + "D.USD.EUR.SP00.A?format=csvdata", "csv"),
    ECB_MONTHLY: (ECB_BASE + "M.USD.EUR.SP00.A?format=csvdata", "csv"),
    FED_ZIP: ("https://www.federalreserve.gov/releases/g5/data/FRB_g5_xml.zip", "zip"),
    **DISCOVERY_PAGES,
}
hist_02_acquire.SOURCES.update(STATIC_SOURCES)


class FxError(ValueError):
    pass


def to_decimal(text):
    t = text.strip()
    if not VALUE_RE.fullmatch(t):
        raise FxError("INVALID_VALUE")
    try:
        v = Decimal(t)
    except InvalidOperation as exc:
        raise FxError("INVALID_VALUE") from exc
    if not v.is_finite() or v <= 0:
        raise FxError("NON_POSITIVE_VALUE")
    return v


def period_key(text, freq):
    """Strict period: 'YYYY-MM-DD' (D), 'YYYY-MM' (M) or 'YYYY' (A); no guessing."""
    t = text.strip()
    pat = {"D": r"\d{4}-\d{2}-\d{2}", "M": r"\d{4}-\d{2}", "A": r"\d{4}"}[freq]
    if not re.fullmatch(pat, t):
        raise FxError("UNPARSEABLE_PERIOD")
    return t


def decode(raw):
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise FxError("NOT_UTF8") from exc


def parse_fed_g5(raw, freq):
    """Fed DDP CSV (layout=seriescolumn): metadata rows, then 'Time Period,<series>' and data rows.

    Returns {'meta', 'points': {period: Decimal}, 'nd': int}. Fail closed on missing header, column count,
    duplicate period (also for ND rows), bad number. ND/NC/blank are counted and stay absent.
    """
    rows = [r for r in csv.reader(io.StringIO(decode(raw))) if r and any(c.strip() for c in r)]
    meta, idx = {}, None
    for i, r in enumerate(rows):
        if r[0].strip().lower() == "time period":
            idx = i
            break
        if len(r) >= 2:
            meta[r[0].strip().rstrip(":")] = r[1].strip()
    if idx is None:
        raise FxError("NO_TIME_PERIOD_HEADER")
    header = rows[idx]
    if len(header) != 2:
        raise FxError("UNEXPECTED_COLUMN_COUNT")
    points, seen, nd = {}, set(), 0
    for r in rows[idx + 1:]:
        if len(r) != 2:
            raise FxError("UNEXPECTED_COLUMN_COUNT")
        k = period_key(r[0], freq)
        if k in seen:
            raise FxError("DUPLICATE_PERIOD")
        seen.add(k)
        if r[1].strip() in FED_MISSING:
            nd += 1
            continue
        points[k] = to_decimal(r[1])
    if not points:
        raise FxError("NO_OBSERVATIONS")
    return {"meta": {"series_column": header[1].strip(), **meta}, "points": points, "nd": nd}


def assert_fed_nlg_direction(meta):
    """Fail closed unless metadata says NLG per US$ with multiplier 1."""
    blob = " ".join(str(v) for v in meta.values()).lower()
    if meta.get("Multiplier", "1").strip() != "1":
        raise FxError("MULTIPLIER_NOT_ONE")
    if "nlg" not in blob and "guilder" not in blob:
        raise FxError("NOT_NLG_SERIES")
    if not re.search(r"per_us|per us|/us\$|guilder/us", blob):
        raise FxError("DIRECTION_NOT_PER_USD")


def parse_ecb_csv(raw, freq, currency="USD", denom="EUR"):
    """ECB data API csvdata. Needs TIME_PERIOD and OBS_VALUE; checks CURRENCY/CURRENCY_DENOM when present."""
    rdr = csv.DictReader(io.StringIO(decode(raw)))
    if not rdr.fieldnames or "TIME_PERIOD" not in rdr.fieldnames or "OBS_VALUE" not in rdr.fieldnames:
        raise FxError("MISSING_ECB_COLUMNS")
    points, missing, meta = {}, 0, {}
    seen = set()
    for row in rdr:
        if row.get("CURRENCY") not in (None, currency) or row.get("CURRENCY_DENOM") not in (None, denom):
            raise FxError("ECB_CURRENCY_MISMATCH")
        for c in ("KEY", "FREQ", "UNIT", "UNIT_MULT", "CURRENCY", "CURRENCY_DENOM", "EXR_TYPE", "EXR_SUFFIX"):
            if c in row:
                meta.setdefault(c, row[c])
        k = period_key(row["TIME_PERIOD"], freq)
        if k in seen:
            raise FxError("DUPLICATE_PERIOD")
        seen.add(k)
        if (row["OBS_VALUE"] or "").strip() in {"", "NaN"}:
            missing += 1
            continue
        points[k] = to_decimal(row["OBS_VALUE"])
    if not points:
        raise FxError("NO_OBSERVATIONS")
    return {"points": points, "missing": missing, "meta": meta}


# ---- conversion chain (Decimal) -------------------------------------------------------------
def gold_nlg_per_oz(usd_per_oz, nlg_per_usd):
    with localcontext() as c:
        c.prec = PRECISION
        return usd_per_oz * nlg_per_usd


def gold_eur_per_oz(usd_per_oz, usd_per_eur):
    with localcontext() as c:
        c.prec = PRECISION
        return usd_per_oz / usd_per_eur


def nlg_to_eur(nlg):  # labelled derivation: fixed rate 2.20371
    with localcontext() as c:
        c.prec = PRECISION
        return nlg / NLG_PER_EUR


def implied_usd_per_eur(nlg_per_usd):
    """USD per EUR implied by G.5 and the fixed rate: (NLG/EUR) / (NLG/USD)."""
    with localcontext() as c:
        c.prec = PRECISION
        return NLG_PER_EUR / nlg_per_usd


# ---- monthly aggregation of the QUOTED direction ---------------------------------------------
def monthly_stats(daily):
    """{day: Decimal} -> {YYYY-MM: {n, mean, mean_of_reciprocals, reciprocal_of_mean, jensen_gap_rel}}.

    mean = arithmetic mean of quoted values (invert AFTER averaging); both inversion routes are reported.
    jensen_gap_rel = (mean(1/x) - 1/mean(x)) / (1/mean(x)), always >= 0.
    """
    groups = {}
    for k, v in daily.items():
        groups.setdefault(k[:7], []).append(v)
    out = {}
    with localcontext() as c:
        c.prec = PRECISION
        for m in sorted(groups):
            vals = groups[m]
            n = len(vals)
            mean = sum(vals, Decimal(0)) / n
            mean_inv = sum((Decimal(1) / v for v in vals), Decimal(0)) / n
            inv_mean = Decimal(1) / mean
            out[m] = {"n": n, "mean": mean, "mean_of_reciprocals": mean_inv, "reciprocal_of_mean": inv_mean,
                      "jensen_gap_rel": (mean_inv - inv_mean) / inv_mean}
    return out


def jensen_summary(stats):
    gaps = [s["jensen_gap_rel"] for s in stats.values()]
    if not gaps:
        return {"months": 0}
    worst = max(stats, key=lambda m: stats[m]["jensen_gap_rel"])
    return {"months": len(gaps), "max_gap_rel": f"{max(gaps):.3E}", "max_gap_month": worst,
            "mean_gap_rel": f"{sum(gaps, Decimal(0)) / len(gaps):.3E}", "min_gap_rel": f"{min(gaps):.3E}",
            "months_gap_ge_1e-5": sum(1 for g in gaps if g >= Decimal("1e-5")),
            "all_non_negative": all(g >= 0 for g in gaps)}


def month_list(first, last):
    y, m = map(int, first.split("-"))
    ey, em = map(int, last.split("-"))
    out = []
    while (y, m) <= (ey, em):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def coverage(monthly_keys):
    keys = sorted(monthly_keys)
    if not keys:
        return {"present": 0}
    have = set(keys)
    exp = month_list(keys[0], keys[-1])
    missing = [m for m in exp if m not in have]
    return {"first": keys[0], "last": keys[-1], "expected_between": len(exp), "present": len(keys),
            "missing_count": len(missing), "missing_months": missing[:60]}


def count_stats(stats):
    ns = sorted(s["n"] for s in stats.values())
    if not ns:
        return {}
    return {"min": ns[0], "median": ns[len(ns) // 2], "max": ns[-1], "months_below_15": sum(1 for n in ns if n < 15)}


def provider_vs_own(provider_monthly, own_stats):
    """Provider-published monthly average vs our mean of the provider's daily values (same direction)."""
    common = sorted(set(provider_monthly) & set(own_stats))
    if not common:
        return {"common_months": 0}
    devs = [(abs(provider_monthly[m] - own_stats[m]["mean"]) / own_stats[m]["mean"], m) for m in common]
    worst = max(devs)
    return {"common_months": len(common), "max_rel_dev": f"{worst[0]:.3E}", "max_dev_month": worst[1],
            "months_dev_gt_1e-4": sum(1 for d, _ in devs if d > Decimal("1e-4"))}


def transition_report(fed_daily, ecb_daily):
    """1998-12 / 1999-01 handover plus daily overlap check (G.5-implied vs ECB USD_PER_EUR)."""
    f_last = max(fed_daily) if fed_daily else None
    e_first = min(ecb_daily) if ecb_daily else None
    overlap = sorted(set(fed_daily) & set(ecb_daily))
    res = {"fed_last_day": f_last, "ecb_first_day": e_first, "overlap_days": len(overlap)}
    if overlap:
        devs = [abs(implied_usd_per_eur(fed_daily[d]) - ecb_daily[d]) / ecb_daily[d] for d in overlap]
        res["overlap_max_rel_dev"] = f"{max(devs):.3E}"
        res["overlap_first"], res["overlap_last"] = overlap[0], overlap[-1]
    if f_last:
        res["fed_last_nlg_per_usd"] = str(fed_daily[f_last])
        res["fed_last_implied_usd_per_eur"] = str(implied_usd_per_eur(fed_daily[f_last]))
    if e_first:
        res["ecb_first_usd_per_eur"] = str(ecb_daily[e_first])
    return res


def chain_example(usd_oz, nlg_per_usd, usd_per_eur):
    nlg = gold_nlg_per_oz(usd_oz, nlg_per_usd)
    return {"usd_oz": str(usd_oz), "nlg_per_usd": str(nlg_per_usd), "gold_nlg_oz": str(nlg),
            "gold_nlg_oz_to_eur_derived": str(nlg_to_eur(nlg)),
            "usd_per_eur": str(usd_per_eur), "gold_eur_oz": str(gold_eur_per_oz(usd_oz, usd_per_eur))}


# ---- discovery of Fed DDP series hashes (the DDP addresses a series by an opaque 32-hex id) ---
HASH_RE = re.compile(r"series=([0-9a-f]{32})", re.I)


def discover_series(html_text, width=160):
    """Return [(hash, context)] for hashes whose nearby text mentions the Netherlands/guilder."""
    out = []
    for m in HASH_RE.finditer(html_text):
        ctx = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html_text[max(0, m.start() - 10): m.end() + width]))
        if re.search(r"netherlands|guilder|RXI_N\.[BMA]\.NL", ctx, re.I):
            out.append((m.group(1), ctx.strip()))
    return out


HREF_RE = re.compile(r"""href\s*=\s*["']([^"'#]+)""", re.I)
LINK_FILTER = re.compile(r"datadownload|/g5|g5a|\.csv|\.xml|\.txt|\.zip|histor|archive", re.I)


def extract_links(html_text, limit=80):
    """Distinct hrefs on a documentation page that look like data/archive links (diagnostic only)."""
    out = []
    for h in HREF_RE.findall(html_text):
        if LINK_FILTER.search(h) and h not in out:
            out.append(h[:200])
    return out[:limit]


def probe_status(url):
    """Diagnostic only: first-response status/Location/content-type, no redirect followed, no body read."""
    from urllib.error import HTTPError
    from urllib.parse import urlsplit
    from urllib.request import HTTPRedirectHandler, Request, build_opener

    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    try:
        r = build_opener(NoRedirect).open(Request(url, headers={"User-Agent": "Goud-btc-dashboard/HIST-04 probe"}), timeout=30)
        return {"status": r.status, "content_type": r.headers.get("Content-Type"), "length": r.headers.get("Content-Length")}
    except HTTPError as exc:
        loc = exc.headers.get("Location")
        parts = urlsplit(loc) if loc else None
        return {"status": exc.code, "location_host": parts.hostname if parts else None,
                "location_path": parts.path if parts else None, "server": exc.headers.get("Server")}
    except OSError as exc:
        return {"error_class": type(exc).__name__}


PROBE_URLS = [  # statuses from run 39438156672: DDP Choose/Build/Download/Output rel=G5 -> 400; FRED probes timed out
    "https://www.federalreserve.gov/releases/g5/data/FRB_g5_xml.zip",
    "https://www.federalreserve.gov/releases/g5a/",
    "https://www.federalreserve.gov/datadownload/Choose.aspx?rel=H10",
]


MAX_UNZIPPED = 150_000_000
NL_VALUE_RE = re.compile(r"(^NLG$)|netherlands|guilder|\.NL\b", re.I)


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def parse_fed_xml_zip(raw):
    """Inspect the Fed G.5 XML package (FRB_g5_xml.zip): structure summary plus Netherlands/NLG series observations.

    Generic over element names: an element carrying TIME_PERIOD and OBS_VALUE attributes is an observation of the
    nearest ancestor that has attributes. Observations are collected only for series whose attributes look like
    NLG/Netherlands. ND (non-numeric OBS_VALUE) stays absent and is counted. Fail closed on DOCTYPE/ENTITY,
    oversized archives, duplicate periods, bad numbers.
    """
    import zipfile
    from xml.etree import ElementTree as ET
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as exc:
        raise FxError("NOT_A_ZIP") from exc
    infos = zf.infolist()
    if sum(i.file_size for i in infos) > MAX_UNZIPPED:
        raise FxError("ZIP_TOO_LARGE_UNCOMPRESSED")
    res = {"members": [{"name": i.filename, "bytes": i.file_size} for i in infos][:20], "tags": {}, "attr_names": {},
           "series_total": 0, "attribute_values": {}, "nl_series": []}
    for info in infos:
        if not info.filename.lower().endswith(".xml"):
            continue
        data = zf.read(info)
        if b"<!ENTITY" in data or b"<!DOCTYPE" in data:
            raise FxError("XML_DTD_REJECTED")
        stack = []
        for ev, el in ET.iterparse(io.BytesIO(data), events=("start", "end")):
            name = _local(el.tag)
            if ev == "start":
                res["tags"][name] = res["tags"].get(name, 0) + 1
                attrs = {_local(k): v for k, v in el.attrib.items()}
                for k in attrs:
                    res["attr_names"].setdefault(name, set()).add(k)
                if "TIME_PERIOD" in attrs and "OBS_VALUE" in attrs:
                    parent = next((f for f in reversed(stack) if f["attrs"]), None)
                    if parent is not None and parent["nl"]:
                        k = attrs["TIME_PERIOD"].strip()
                        if k in parent["seen"]:
                            raise FxError("DUPLICATE_PERIOD")
                        parent["seen"].add(k)
                        v = attrs["OBS_VALUE"].strip()
                        if v in FED_MISSING:
                            parent["nd"] += 1
                            parent["nd_values"].add(v[:12])
                        else:
                            parent["points"][k] = to_decimal(v)  # raises on anything not a positive decimal
                    stack.append({"attrs": {}, "nl": False})
                    continue
                nl = any(NL_VALUE_RE.search(str(v)) for v in attrs.values())
                if attrs and "TIME_PERIOD" not in attrs:
                    res["series_total"] += 1
                    for key in ("CURRENCY", "UNIT", "FREQ", "SERIES_NAME", "UNIT_MULT", "DATA_TYPE"):
                        if key in attrs and key != "SERIES_NAME":
                            res["attribute_values"].setdefault(key, set()).add(attrs[key])
                frame = {"attrs": attrs, "nl": nl, "points": {}, "seen": set(), "nd": 0, "nd_values": set()}
                stack.append(frame)
                if nl:
                    res["nl_series"].append(frame)
            else:
                stack.pop()
                el.clear()
    res["attr_names"] = {k: sorted(v) for k, v in res["attr_names"].items()}
    res["attribute_values"] = {k: sorted(v)[:40] for k, v in res["attribute_values"].items()}
    nl = []
    for f in res["nl_series"]:
        if f["points"] or f["nd"]:
            nl.append({"attrs": f["attrs"], "observations": len(f["points"]), "nd": f["nd"], "nd_values": sorted(f["nd_values"]),
                       "first": min(f["points"]) if f["points"] else None, "last": max(f["points"]) if f["points"] else None,
                       "points": f["points"]})
    res["nl_series"] = nl
    return res


def status_snippets(html_text, limit=6, width=260):
    """Documentation sentences about discontinuation/history/euro (page text only, not data)."""
    text = re.sub(r"\s+", " ", re.sub(r"<(script|style)[^>]*>.*?</\1>|<[^>]+>", " ", html_text, flags=re.S | re.I))
    out = []
    for sent in re.split(r"(?<=[.!?])\s+", text):
        if re.search(r"discontinu|no longer|euro\b|guilder|netherlands|historical", sent, re.I) and len(sent) >= 20:
            out.append(sent[:width])
        if len(out) >= limit:
            break
    return out


EUROSTAT_BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
EUROSTAT_PROBES = {
    "eurostat-usd-m": EUROSTAT_BASE + "ert_bil_eur_m?format=JSON&lang=EN&currency=USD&statinfo=AVG&unit=NAC",
    "eurostat-nlg-m": EUROSTAT_BASE + "ert_bil_eur_m?format=JSON&lang=EN&currency=NLG&statinfo=AVG&unit=NAC",
}
hist_02_acquire.SOURCES.update({k: (v, "json") for k, v in EUROSTAT_PROBES.items()})
EXTRA_PAGES = {"fed-ddp-g5a": (FED_BASE + "Choose.aspx?rel=G5A", "html"),
               "fed-h10-zip": ("https://www.federalreserve.gov/releases/h10/data/FRB_h10_xml.zip", "zip")}
hist_02_acquire.SOURCES.update(EXTRA_PAGES)


def jsonstat_summary(raw):
    """Eurostat JSON-stat: time range and non-null count (structure only, no values kept)."""
    d = json.loads(decode(raw))
    idx = d.get("dimension", {}).get("time", {}).get("category", {}).get("index", {})
    keys = sorted(idx) if isinstance(idx, dict) else sorted(idx or [])
    vals = d.get("value", {})
    n = len(vals) if hasattr(vals, "__len__") else None
    return {"time_first": keys[0] if keys else None, "time_last": keys[-1] if keys else None,
            "time_points": len(keys), "values": n, "error": d.get("error")}


def fed_url(series_hash):
    return (FED_BASE + "Output.aspx?rel=G5&series=" + series_hash +
            "&lastobs=&from=&to=&filetype=csv&label=include&layout=seriescolumn")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary-out", required=True)
    args = ap.parse_args(argv)
    out = Path(args.summary_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    s = {"status": "RUNNING", "candidate_not_approved": True, "needs_owner_decision": True, "directions": DIRECTIONS,
         "nlg_per_eur": str(NLG_PER_EUR), "rights_status": "UNVERIFIED", "publication_authorized": False,
         "discovery": {}, "fed": {}, "ecb": {}, "failures": []}

    def fail(sid, exc):
        s["failures"].append({"source_id": sid, "error": f"{type(exc).__name__}: {str(exc)[:300]}"})

    ecb_d = ecb_m = None
    for sid, freq in ((ECB_DAILY, "D"), (ECB_MONTHLY, "M")):
        try:
            raw, rec = hist_02_acquire.fetch(sid)
            p = parse_ecb_csv(raw, freq)
            s["ecb"][sid] = {"sha256": rec["sha256"], "bytes": rec["bytes"], "observations": len(p["points"]),
                             "missing_markers": p["missing"], "meta": p["meta"],
                             "first": min(p["points"]), "last": max(p["points"])}
            if freq == "D":
                ecb_d = p["points"]
            else:
                ecb_m = p["points"]
        except (hist_02_acquire.AcquisitionError, FxError) as exc:
            fail(sid, exc)

    s["probes"] = {u: probe_status(u) for u in PROBE_URLS}
    hashes = []
    for sid in DISCOVERY_PAGES:
        try:
            raw, rec = hist_02_acquire.fetch(sid)
            text = raw.decode("utf-8", "replace")
            found = discover_series(text)
            s["discovery"][sid] = {"sha256": rec["sha256"], "bytes": rec["bytes"], "links": extract_links(text),
                                   "all_series_hashes": len(set(HASH_RE.findall(text))),
                                   "netherlands_hits": [{"hash": h, "context": c} for h, c in found][:12]}
            hashes += [h for h, _ in found]
        except hist_02_acquire.AcquisitionError as exc:
            fail(sid, exc)

    s["alt_probes"] = {}
    for sid in list(EUROSTAT_PROBES) + list(EXTRA_PAGES):
        try:
            raw, rec = hist_02_acquire.fetch(sid)
            entry = {"sha256": rec["sha256"], "bytes": rec["bytes"]}
            if sid in EUROSTAT_PROBES:
                entry.update(jsonstat_summary(raw))
            entry["status_snippets"] = status_snippets(raw.decode("utf-8", "replace")) if sid == "fed-ddp-g5a" else None
            s["alt_probes"][sid] = entry
        except Exception as exc:  # diagnostics only
            s["alt_probes"][sid] = {"error": f"{type(exc).__name__}: {str(exc)[:200]}",
                                    "probe": probe_status(hist_02_acquire.SOURCES[sid][0])}
    for sid in DISCOVERY_PAGES:
        try:
            raw, _ = hist_02_acquire.fetch(sid)
            s["discovery"][sid]["status_snippets"] = status_snippets(raw.decode("utf-8", "replace"))
        except Exception:
            pass
    fed = {}
    try:
        raw, rec = hist_02_acquire.fetch(FED_ZIP)
        z = parse_fed_xml_zip(raw)
        s["fed_xml_zip"] = {"sha256": rec["sha256"], "bytes": rec["bytes"], "members": z["members"], "tags": z["tags"],
                            "attr_names": z["attr_names"], "attributed_elements": z["series_total"],
                            "attribute_values": z["attribute_values"],
                            "nl_series": [{k: v for k, v in n.items() if k != "points"} for n in z["nl_series"]]}
        for n in z["nl_series"]:
            freq = {"D": "D", "B": "D", "M": "M", "A": "A"}.get(str(n["attrs"].get("FREQ", ""))[:1].upper())
            if freq is None:
                continue
            fed.setdefault(freq, {"meta": n["attrs"], "points": n["points"], "nd": n["nd"], "rec": rec})
    except (hist_02_acquire.AcquisitionError, FxError, Exception) as exc:  # diagnostics must not abort the run
        fail(FED_ZIP, exc)
    for h in dict.fromkeys(hashes):
        sid = "fed-g5-" + h[:8]
        hist_02_acquire.SOURCES[sid] = (fed_url(h), "csv")
        try:
            raw, rec = hist_02_acquire.fetch(sid)
        except hist_02_acquire.AcquisitionError as exc:
            fail(sid, exc)
            continue
        for freq in ("D", "M", "A"):
            try:
                p = parse_fed_g5(raw, freq)
            except FxError:
                continue
            p["rec"] = rec
            fed.setdefault(freq, p)
            break
    for freq, p in fed.items():
        try:
            assert_fed_nlg_direction(p["meta"])
            dir_ok = True
        except FxError as exc:
            dir_ok = str(exc)
        s["fed"][freq] = {"sha256": p["rec"]["sha256"], "bytes": p["rec"]["bytes"], "meta": p["meta"],
                          "direction_check": dir_ok, "observations": len(p["points"]), "nd_markers": p["nd"],
                          "first": min(p["points"]), "last": max(p["points"])}
    fed_d = fed.get("D", {}).get("points")
    if fed_d:
        fs = monthly_stats(fed_d)
        s["fed_daily_analysis"] = {"months": coverage(fs), "obs_per_month": count_stats(fs),
                                   "jensen_nlg_per_usd": jensen_summary(fs),
                                   "provider_monthly_vs_own": provider_vs_own(fed["M"]["points"], fs) if "M" in fed else "NO_MONTHLY_SERIES"}
    if ecb_d:
        es = monthly_stats(ecb_d)
        s["ecb_daily_analysis"] = {"months": coverage(es), "obs_per_month": count_stats(es),
                                   "jensen_usd_per_eur": jensen_summary(es),
                                   "provider_monthly_vs_own": provider_vs_own(ecb_m, es) if ecb_m else "NO_MONTHLY_SERIES"}
        if ecb_m:
            s["ecb_monthly_series_coverage"] = coverage(ecb_m)
    if fed_d and ecb_d:
        s["transition"] = transition_report(fed_d, ecb_d)
        s["chain_example_synthetic_gold"] = chain_example(Decimal("400.00"), fed_d[max(fed_d)], ecb_d[min(ecb_d)])
    s["status"] = "OK" if (ecb_d and fed_d) else "PARTIAL"
    out.write_text(json.dumps(s, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps(s, indent=2, sort_keys=True, default=str))
    return 0 if s["status"] == "OK" else 2


if __name__ == "__main__":
    sys.exit(main())
