"""HIST-07 research collector (CI only, read-only, nothing committed, nothing approved).

Acquires through the hardened tools.hist_02_acquire.fetch path (https allowlist per registered URL, size limit,
sha256), parses with Decimal, and runs the comparison analyses of docs/research/HIST_07_GOLD_NLG.md using the pure
functions of tools.hist_07_gold_constructions. Unreachable sources are recorded (missing_sources) and the
dependent analyses are skipped; they are never replaced by other data. Real defects (a structurally invalid World
Bank sheet, wrong units) exit 1. The artifact holds aggregates, hashes and a derived monthly table only.
"""
import argparse
import csv
import io
import json
import re
import statistics
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
from urllib.parse import urlsplit

from tools import hist_02_acquire as acq
from tools import hist_03_second_source as ss
from tools import hist_03_worldbank_validate as wbv
from tools import hist_04_fx as fx
from tools import hist_04_gold_nlg as gn
from tools import hist_04_nlg_sources as ns
from tools import hist_07_gold_constructions as hc

Q = hc.Quote
H10 = ns.H10
EXTRA = {
    "h07-fed-dat96-eu": (H10 + "dat96_eu.txt", "txt"),
    "h07-fed-dat00-eu": (H10 + "dat00_eu.txt", "txt"),
    "h07-imf-nld": ("https://api.imf.org/external/sdmx/2.1/data/IMF.STA,ER/NLD.XDC_USD.PA_RT.M?startPeriod=1955-01&endPeriod=2002-12&format=sdmx-csv", "xml"),
    "h07-boe-xumagpd": (ss.BOE_CSV.replace("01/Jan/1975", "01/Jan/1960").replace("31/Dec/1999", "31/Dec/2001"), "csv"),
    "h07-datahub-gold-monthly": ("https://raw.githubusercontent.com/datasets/gold-prices/main/data/monthly.csv", "csv"),
    "h07-bbk-wt5511": ("https://api.statistiken.bundesbank.de/rest/data/BBK01/WT5511?format=csv&lang=en", "csv"),
    "h07-wb-page": ("https://www.worldbank.org/en/research/commodity-markets", "html"),
    "h07-cbs-catalog-gold": ("https://opendata.cbs.nl/ODataCatalog/Tables?$format=json&$filter=substringof('goud',Title)", "json"),
}
acq.SOURCES.update(EXTRA)
WB_ID = "world-bank-gold-history"
WB_FILE = "CMO-Historical-Data-Monthly.xlsx"
NVM_NLG = {1985: Decimal("130000"), 1990: Decimal("159000"), 1995: Decimal("223000"), 1999: Decimal("329000")}  # as quoted in HIST_05_NVM_AND_LONG_RUN.md (ESB table, secondary)
CAVEAT = "research only; nothing approved; rights UNVERIFIED; no raw third-party bytes in artifacts"


def pc(v, q="1E-4"):
    return None if v is None else format((v * 100).quantize(Decimal(q)), "f")


def fixture_house():
    p = Path(__file__).resolve().parent.parent / "data" / "fixtures" / "cbs-1995-1999-i1.json"
    raw = p.read_bytes()
    d = json.loads(raw, parse_float=Decimal, parse_int=Decimal)
    out = {}
    for r in d["data"]:
        if r["series"] != "nl_house_avg_eur":
            continue
        if r["date"] in out:
            raise hc.ConstructionError("FIXTURE_DUPLICATE")
        out[r["date"]] = hc.parse_decimal(r["value"])
    import hashlib
    return out, hashlib.sha256(raw).hexdigest()


# ------------------------------------------------------------------ parsers (full ranges)
def monthly_mean(points):
    sums, cnt = {}, Counter()
    for d, v in points.items():
        k = f"{d.year:04d}-{d.month:02d}"
        sums[k] = sums.get(k, Decimal(0)) + v
        cnt[k] += 1
    with localcontext() as c:
        c.prec = 34
        return {k: sums[k] / cnt[k] for k in sorted(sums)}, dict(cnt)


def parse_fed_ne(raw, sid):
    parsed, dirn = gn.parse_fed_file(raw, sid)
    return parsed["points"], parsed["missing_markers"]


def parse_fed_euro(raw, century, sid):
    parsed = ns.parse_dated_text(raw, century=century)
    head = " ".join(parsed["header"]).upper()
    vals = list(parsed["points"].values())
    if "EURO" not in head or not vals or not all(Decimal("0.5") <= v <= Decimal("2.0") for v in vals):
        raise hc.ConstructionError(f"{sid}: NOT_USD_PER_EURO_SERIES header={head[:120]!r}")
    return {d: v for d, v in parsed["points"].items() if d >= date(1999, 1, 1)}, parsed["header"][:3]


def norm(cell):
    return (cell or "").split(":")[0].strip()


def parse_bis(raw):
    text = raw.decode("utf-8-sig", "replace")
    rdr = csv.DictReader(io.StringIO(text))
    rows = list(rdr)
    if not rows:
        raise hc.ConstructionError("BIS_EMPTY")
    keymap = {norm(k).upper() if ":" in (k or "") else (k or "").strip().upper(): k for k in rdr.fieldnames}
    need = ("FREQ", "TIME_PERIOD", "OBS_VALUE")
    if any(n not in keymap for n in need):
        raise hc.ConstructionError("BIS_COLUMNS " + json.dumps(list(keymap)[:14]))
    combos, out = Counter(), {}
    for r in rows:
        fr = norm(r[keymap["FREQ"]])
        col = norm(r[keymap["COLLECTION"]]) if "COLLECTION" in keymap else ""
        cur = norm(r[keymap["CURRENCY"]]) if "CURRENCY" in keymap else ""
        combos[(fr, col, cur)] += 1
        if fr == "M" and col in ("A", ""):
            k = r[keymap["TIME_PERIOD"]].strip()[:7]
            if k in out:
                raise hc.ConstructionError("BIS_DUPLICATE_MONTH " + k)
            v = (r[keymap["OBS_VALUE"]] or "").strip()
            if v:
                out[k] = hc.parse_decimal(v)
    return out, {f"{a}|{b}|{c}": n for (a, b, c), n in combos.items()}


def parse_imf(raw):
    root = ET.fromstring(raw)
    series, out = 0, {}
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if tag == "Series":
            series += 1
        if tag == "Obs" and "TIME_PERIOD" in el.attrib and "OBS_VALUE" in el.attrib:
            k = el.attrib["TIME_PERIOD"][:7]
            if k in out:
                raise hc.ConstructionError("IMF_DUPLICATE_MONTH " + k)
            if el.attrib["OBS_VALUE"].strip():
                out[k] = hc.parse_decimal(el.attrib["OBS_VALUE"].strip())
    return out, series


def parse_cbs(props_raw, data_raw):
    props = json.loads(props_raw.decode("utf-8-sig"), parse_float=Decimal, parse_int=Decimal)["value"]
    data = json.loads(data_raw.decode("utf-8-sig"), parse_float=Decimal, parse_int=Decimal)
    cands = [p for p in props if p.get("Type", "Topic") == "Topic" and re.search(r"amerikaanse dollar|us dollar", str(p.get("Title", "")), re.I)]
    if len(cands) != 1:
        raise hc.ConstructionError("CBS_AMBIGUOUS_PROPERTY")
    key, out = cands[0]["Key"], {}
    for row in data["value"]:
        m = re.fullmatch(r"(\d{4})MM(\d{2})", str(row.get("Perioden", "")))
        v = row.get(key)
        if m and isinstance(v, Decimal):
            k = f"{m.group(1)}-{m.group(2)}"
            if k in out:
                raise hc.ConstructionError("CBS_DUPLICATE_MONTH")
            out[k] = hc.parse_decimal(v)
    return out, str(cands[0].get("Unit"))[:20]


def parse_datahub(raw):
    rdr = csv.DictReader(io.StringIO(raw.decode("utf-8-sig", "replace")))
    out = {}
    cols = rdr.fieldnames or []
    dk = next((c for c in cols if c.lower() == "date"), None)
    pk = next((c for c in cols if c.lower() == "price"), None)
    if not dk or not pk:
        raise hc.ConstructionError("DATAHUB_COLUMNS " + json.dumps(cols[:6]))
    for r in rdr:
        k = r[dk].strip()[:7]
        v = (r[pk] or "").strip()
        if not v:
            continue
        if k in out:
            raise hc.ConstructionError("DATAHUB_DUPLICATE_MONTH " + k)
        d = Decimal(v)
        if not d.is_finite() or d <= 0:
            raise hc.ConstructionError("DATAHUB_NONPOSITIVE")
        out[k] = d
    return out, cols


def parse_bbk(raw):
    text = raw.decode("utf-8-sig", "replace")
    pts = {}
    for ln in text.splitlines():
        m = re.match(r'\s*"?(\d{4}-\d{2}(?:-\d{2})?)"?\s*[;,]\s*"?([0-9]+(?:\.[0-9]+)?)"?', ln)
        if m:
            pts[m.group(1)] = Decimal(m.group(2))
    return pts, [ln[:120] for ln in text.splitlines()[:4]]


# ------------------------------------------------------------------ helpers
def sheet_names(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        wb = ET.fromstring(z.read("xl/workbook.xml"))
    return [s.attrib["name"] for s in wb.findall(".//x:sheets/x:sheet", wbv.NS)]


def gold_text_rows(raw, names):
    out = {}
    for n in names:
        if n == wbv.SHEET:
            continue
        try:
            rows = wbv.read_rows(raw, sheet=n)
        except Exception as exc:  # reported, not fatal
            out[n] = {"error": type(exc).__name__}
            continue
        hits = []
        for r in rows:
            cells = [str(v).strip() for v in r.values() if str(v).strip()]
            if any(re.search(r"gold|pink|updated|break|fixing|spot", c, re.I) for c in cells):
                hits.append(" | ".join(cells)[:420])
        out[n] = {"rows": len(rows), "gold_related_rows": hits[:6]}
    return out


def dev_dict(a, b, months):
    """(a - b) / b on months present in both (Decimal series); no filling."""
    out = {}
    for m in months:
        if m in a and m in b:
            with localcontext() as c:
                c.prec = 34
                out[m] = (a[m] - b[m]) / b[m]
    return out


def stat(a, b, months):
    return hc.deviation_stats(dev_dict(a, b, months))


def cov(series, start, end):
    ms = hc.month_range(start, end)
    have = [m for m in ms if m in series]
    miss = [m for m in ms if m not in series]
    return {"expected": len(ms), "present": len(have), "first": have[0] if have else None, "last": have[-1] if have else None,
            "missing": len(miss), "missing_sample": miss[:6] + (["..."] + miss[-3:] if len(miss) > 9 else miss[6:9])}


def decade_stats(series, preds):
    out = {}
    for name, (a, b) in preds.items():
        vs = [v for m, v in series.items() if a <= m <= b]
        if vs:
            out[name] = {"n": len(vs), "min": str(min(vs)), "max": str(max(vs)),
                         "non_integer": sum(1 for v in vs if v != v.to_integral_value()),
                         "median": str(statistics.median(vs))}
    return out


def longest_equal_run(series, a, b):
    best, cur, prev, where = 0, 0, None, None
    for m in sorted(series):
        if not a <= m <= b:
            continue
        if series[m] == prev:
            cur += 1
        else:
            cur, prev = 1, series[m]
        if cur > best:
            best, where = cur, m
    return {"longest_run_months": best, "ends": where}


def c3_for(usd, nlg, months):
    c1q, miss = hc.c1(usd, nlg, months)
    return c1q, hc.c3(c1q), miss


# ------------------------------------------------------------------ main collection
def collect(workbook=None):
    S = {"status": "RUNNING", "caveat": CAVEAT, "sources": {}, "missing_sources": [], "flags": [], "defects": [], "not_performed": []}
    raws = {}

    def get(sid, local=None):
        try:
            if local:
                raw, rec = wbv.load_workbook(local)
            elif sid == WB_ID:
                raw, rec = wbv.load_workbook(None)
            else:
                raw, rec = acq.fetch(sid)
        except acq.AcquisitionError as exc:
            S["missing_sources"].append({"source_id": sid, "reason": str(exc)[:140]})
            return None
        S["sources"][sid] = {"url": rec["url"], "sha256": rec["sha256"], "bytes": rec["bytes"]}
        raws[sid] = raw
        return raw

    def safe(label, fn):
        try:
            return fn()
        except (hc.ConstructionError, ns.NlgSourceError, fx.FxError, ss.SecondSourceError, ET.ParseError, KeyError, ValueError, InvalidOperation, wbv.ValidationError) as exc:
            S["defects"].append({"where": label, "error": f"{type(exc).__name__}: {str(exc)[:220]}"})
            return None

    # --- World Bank (pinned workbook; structure hard, hash flagged)
    wb_raw = get(WB_ID, workbook)
    wb, wbp = {}, None
    if wb_raw:
        rec = S["sources"][WB_ID]
        rec["matches_known_workbook_sha256"] = rec["sha256"] == wbv.KNOWN_WORKBOOK_SHA256
        if not rec["matches_known_workbook_sha256"]:
            S["flags"].append("WB_WORKBOOK_SHA256_DIFFERS_FROM_PINNED")
        wbp = wbv.parse(wb_raw, "1960-01", "2099-12")
        wb = wbp["series"]
        if wbp["duplicates"] or wbp["invalid"] or wbp["bad_dates"] or not wb:
            raise hc.ConstructionError("WB_STRUCTURE " + json.dumps({k: wbp[k] for k in ("duplicates", "invalid", "bad_dates")})[:300])
        first, last = min(wb), max(wb)
        names = sheet_names(wb_raw)
        S["worldbank"] = {
            "sheet_names": names, "gold_column": wbp["gold_column"], "header": wbp["header_text"], "unit_rows": wbp["unit_texts"],
            "first": first, "last": last, "count": len(wb), "coverage_first_to_last": cov(wb, first, last),
            "pinned_range_1975_1999_canonical_sha256": wbv.canonical_sha256(wb, hc.month_range("1975-01", "1999-12")) if all(m in wb for m in hc.month_range("1975-01", "1999-12")) else None,
            "known_canonical_sha256": wbv.KNOWN_CANONICAL_SERIES_SHA256,
            "decades": decade_stats(wb, {"1960-67": ("1960-01", "1967-12"), "1968-74": ("1968-01", "1974-12"), "1975-79": ("1975-01", "1979-12"),
                                          "1980-89": ("1980-01", "1989-12"), "1990-99": ("1990-01", "1999-12"), "2000-09": ("2000-01", "2009-12"),
                                          "2010-26": ("2010-01", "2099-12")}),
            "run_1960_1967": longest_equal_run(wb, "1960-01", "1967-12"),
            "run_1968_1974": longest_equal_run(wb, "1968-01", "1974-12"),
            "values_1960_01": str(wb.get("1960-01")), "values_1967_12": str(wb.get("1967-12")), "values_1968_02_to_05": {m: str(wb.get(m)) for m in ("1968-02", "1968-03", "1968-04", "1968-05")},
            "values_1971_07_to_1971_09": {m: str(wb.get(m)) for m in ("1971-07", "1971-08", "1971-09")},
            "values_1974_12_1975_01": {m: str(wb.get(m)) for m in ("1974-12", "1975-01")},
            "values_2025_05_06": {m: str(wb.get(m)) for m in ("2025-05", "2025-06", "2025-07")},
            "definition_text": gold_text_rows(wb_raw, names),
        }
    # newer vintage probe
    page = get("h07-wb-page")
    S["wb_vintage_probe"] = {"page_fetched": bool(page)}
    if page:
        hrefs = sorted({h for h in re.findall(r'href="([^"]+)"', page.decode("utf-8", "replace")) if WB_FILE in h})
        S["wb_vintage_probe"]["xlsx_hrefs_found"] = [h[:200] for h in hrefs[:5]]
        pinned = acq.SOURCES[WB_ID][0]
        newer = [h for h in hrefs if h != pinned and urlsplit(h).hostname == "thedocs.worldbank.org" and urlsplit(h).path.endswith(WB_FILE)]
        S["wb_vintage_probe"]["differs_from_pinned"] = bool(newer)
        if newer:
            acq.SOURCES["h07-wb-new"] = (newer[0], "xlsx")
            nraw = get("h07-wb-new")
            if nraw:
                np_ = wbv.parse(nraw, "1960-01", "2099-12")["series"]
                common = [m for m in wb if m in np_]
                diff = [m for m in common if wb[m] != np_[m]]
                S["wb_vintage_probe"]["new_vs_pinned"] = {"new_last": max(np_), "common": len(common), "differing_months": len(diff),
                                                           "differing_sample": diff[:8], "differing_pre2000": sum(1 for m in diff if m < "2000-01")}

    # --- gold cross sources
    boe, dh, bbk = {}, {}, {}
    raw = get("h07-boe-xumagpd")
    if raw:
        pts = safe("boe", lambda: ss.parse_points(raw, ss.BOE_SERIES)[0])
        boe = ss.monthly_from_points(pts, "1960-01", "2001-12") if pts else {}
    raw = get("h07-datahub-gold-monthly")
    if raw:
        r = safe("datahub", lambda: parse_datahub(raw))
        if r:
            dh = r[0]
            S["datahub"] = {"columns": r[1][:4], "first": min(dh), "last": max(dh), "count": len(dh)}
    raw = get("h07-bbk-wt5511")
    if raw:
        r = safe("bbk", lambda: parse_bbk(raw))
        if r:
            S["bundesbank_wt5511"] = {"points": len(r[0]), "first": min(r[0]) if r[0] else None, "last": max(r[0]) if r[0] else None, "head": r[1]}
            days = {k: v for k, v in r[0].items() if len(k) == 10}
            if days:
                bbk = monthly_mean({date.fromisoformat(k): v for k, v in days.items()})[0]
            else:
                bbk = {k: v for k, v in r[0].items() if len(k) == 7}
    gold = {}
    if boe:
        S["boe_xumagpd"] = {"first": min(boe), "last": max(boe), "count": len(boe)}
    if wb:
        for name, other in (("boe", boe), ("datahub", dh), ("bundesbank_wt5511", bbk)):
            if other:
                per = {"1960-67": ("1960-01", "1967-12"), "1968-74": ("1968-01", "1974-12"), "1975-78": ("1975-01", "1978-12"),
                       "1979-89": ("1979-01", "1989-12"), "1990-98": ("1990-01", "1998-12"), "1999-2001": ("1999-01", "2001-12")}
                gold[name] = {k: stat(wb, other, hc.month_range(a, b)) for k, (a, b) in per.items()}
                gold[name]["exactly_equal_months_1975_1998"] = sum(1 for m in hc.month_range("1975-01", "1998-12") if m in wb and m in other and wb[m] == other[m])
                gold[name]["common_months_1975_1998"] = sum(1 for m in hc.month_range("1975-01", "1998-12") if m in wb and m in other)
        S["gold_wb_vs_other"] = gold
    raw = get("fred-exneus-history")  # known to time out; one more attempt, recorded either way

    # --- FX monthly NLG per USD
    fed_pts = {}
    for sid in gn.FED_IDS:
        raw = get(sid)
        if raw:
            r = safe(sid, lambda: parse_fed_ne(raw, sid))
            if r:
                fed_pts.update(r[0])
    fed_m, fed_n = monthly_mean(fed_pts) if fed_pts else ({}, {})
    fed_m = {k: v for k, v in fed_m.items() if k <= "1998-12"}
    bis_m = imf_m = cbs_m = {}
    raw = get("bis-api-m-nl")
    if raw:
        r = safe("bis", lambda: parse_bis(raw))
        if r:
            bis_eur, combos = r
            bis_m = {k: hc.nlg_per_usd_from_eur_per_usd(Q(v, "EUR", "USD")).value for k, v in bis_eur.items()}
            S["bis"] = {"combos": combos, "first": min(bis_eur), "last": max(bis_eur), "count": len(bis_eur)}
    raw = get("h07-imf-nld")
    if raw:
        r = safe("imf", lambda: parse_imf(raw))
        if r:
            imf_m = r[0]
            S["imf"] = {"series_count": r[1], "first": min(imf_m) if imf_m else None, "last": max(imf_m) if imf_m else None, "count": len(imf_m)}
    pr, dr = get("cbs-7139shfo-props"), get("cbs-7139shfo-data")
    if pr and dr:
        r = safe("cbs7139", lambda: parse_cbs(pr, dr))
        if r:
            cbs_m = r[0]
            S["cbs_7139"] = {"unit": r[1], "first": min(cbs_m), "last": max(cbs_m), "count": len(cbs_m)}
    fx_series = {"fed": fed_m, "bis": bis_m, "imf": imf_m, "cbs": cbs_m}
    S["fx_coverage_1960_1998"] = {k: cov({m: v for m, v in s.items()}, "1960-01", "1998-12") for k, s in fx_series.items() if s}
    if fed_m:
        S["fed_obs_per_month"] = {"min": min(fed_n[m] for m in fed_m), "max": max(fed_n[m] for m in fed_m), "median": statistics.median(fed_n[m] for m in fed_m), "first": min(fed_m)}
    # parity check pre-1971 from BIS
    if bis_m:
        pre = Counter(format(v.quantize(Decimal("0.0001")), "f") for m, v in bis_m.items() if "1960-01" <= m <= "1970-12")
        S["bis_nlg_per_usd_1960_1970_distinct_4dp"] = dict(pre.most_common(8))
    fxcmp = {}
    for a in ("bis", "imf", "cbs"):
        if fx_series[a] and fed_m:
            fxcmp[f"{a}_vs_fed_1971_1998"] = stat(fx_series[a], fed_m, hc.month_range("1971-01", "1998-12"))
    for a in ("imf", "cbs"):
        if fx_series[a] and bis_m:
            fxcmp[f"{a}_vs_bis_1960_1970"] = stat(fx_series[a], bis_m, hc.month_range("1960-01", "1970-12"))
    S["fx_pairwise"] = fxcmp

    # --- euro-era FX for the overlap
    ecb_raw = get(fx.ECB_MONTHLY)
    ecb_m = gn.parse_ecb_monthly(ecb_raw) if ecb_raw else {}
    fed_eu = {}
    for sid, cen in (("h07-fed-dat96-eu", 1900), ("h07-fed-dat00-eu", 2000)):
        raw = get(sid)
        if raw:
            r = safe(sid, lambda: parse_fed_euro(raw, cen, sid))
            if r:
                fed_eu.update(r[0])
                S["sources"][sid]["header"] = r[1]
    fed_eu_m, fed_eu_n = monthly_mean(fed_eu) if fed_eu else ({}, {})
    if fed_eu_m:
        S["fed_euro"] = {"first": min(fed_eu_m), "last": max(fed_eu_m), "months": len(fed_eu_m), "min_obs": min(fed_eu_n.values())}

    # --- overlap C3 vs C4
    ovm = hc.month_range("1999-01", "2001-12")
    ov = {}
    if wb and ecb_m:
        c4q, c4miss = hc.c4(wb, ecb_m, ovm)
        ov["c4_missing"] = c4miss
        variants = {}
        if fed_eu_m:
            variants["fed_noon_euro_implied"] = {m: hc.nlg_per_usd_from_usd_per_eur(Q(v, "USD", "EUR")).value for m, v in fed_eu_m.items()}
        for k, s in (("imf", imf_m), ("cbs", cbs_m)):
            if s:
                variants[k] = {m: v for m, v in s.items() if m >= "1999-01"}
        if bis_m:
            variants["bis"] = {m: v for m, v in bis_m.items() if m >= "1999-01"}
        for name, nlg in variants.items():
            _, c3q, miss = c3_for(wb, nlg, ovm)
            devs, dmiss = hc.overlap_compare(c3q, c4q, ovm)
            by_year = {}
            for y in ("1999", "2000", "2001"):
                by_year[y] = hc.deviation_stats({m: d for m, d in devs.items() if m.startswith(y)}).get("mean_signed_pct")
            ov[name] = {"c3_missing": miss, "stats": hc.deviation_stats(devs), "mean_signed_pct_by_year": by_year}
        S["overlap_1999_2001"] = ov
        if fed_eu_m:
            long = hc.month_range("1999-01", min(max(fed_eu_m), max(ecb_m)))
            d_ = dev_dict({m: v for m, v in ecb_m.items()}, fed_eu_m, long)  # (ECB - Fed)/Fed in USD per EUR; C3(Fed)/C4 - 1 = ECB/Fed - 1
            byy = {}
            for m, v in d_.items():
                byy.setdefault(m[:4], {})[m] = v
            S["fed_vs_ecb_long"] = {"all_months": hc.deviation_stats(d_), "by_year_median_abs_pct": {y: hc.deviation_stats(v)["median_abs_pct"] for y, v in sorted(byy.items())},
                                      "note": "(ECB - Fed)/Fed in USD per EUR equals C3(Fed-implied)/C4 - 1 for the same USD gold"}
    else:
        S["not_performed"].append("overlap: needs World Bank and ECB monthly")

    # --- constructions 1960-01..1998-12 by FX source
    months_pre = hc.month_range("1960-01", "1998-12")
    constr, table = {}, {"usd_wb": {m: wb[m] for m in hc.month_range("1960-01", "1999-12") if m in wb}}
    for name, s in fx_series.items():
        if s and wb:
            c1q, c3q, miss = c3_for(wb, s, months_pre)
            constr[name] = (c1q, c3q)
            S.setdefault("construction_coverage_1960_1998", {})[name] = {"present": len(c1q), "first": min(c1q) if c1q else None, "last": max(c1q) if c1q else None,
                                                                         "missing": len(miss), "missing_sample": miss[:8]}
            table[f"nlg_per_usd_{name}"] = s
            table[f"c1_nlg_{name}"] = c1q
            table[f"c3_eur_equiv_{name}"] = c3q
    if wb and ecb_m:
        c4all, _ = hc.c4(wb, ecb_m, hc.month_range("1999-01", "1999-12"))
        table["c4_eur_observed"] = c4all
    if boe:
        table["usd_boe"] = boe
    # --- grams per home 1995-1999 (CBS fixture)
    house, fx_hash = fixture_house()
    S["fixture_sha256"] = fx_hash
    gm = {}
    if wb and ecb_m and constr:
        ms = hc.month_range("1995-01", "1999-12")
        hq = {m: Q(house[m], "EUR", "home") for m in ms}
        routes = {}
        for name, (c1q, c3q) in constr.items():
            r = {}
            for m in ms:
                if m < "1999-01":
                    if m in c3q:
                        r[m] = hc.grams_per_home_eur(hq[m], c3q[m])
                else:
                    if m in c4all:
                        r[m] = hc.grams_per_home_eur(hq[m], c4all[m])  # 1999: observed C4 (all routes equal)
            routes[f"C3_{name}_then_C4_1999"] = r
        if boe:
            c1b, _ = hc.c1(boe, fed_m, hc.month_range("1995-01", "1998-12"))
            routes["C3_fed_with_BoE_gold_USD"] = {m: hc.grams_per_home_eur(hq[m], hc.redenominate(c1b[m])) for m in c1b}
        if fed_eu_m:
            cf = {m: hc.redenominate(hc.mul(hc.nlg_per_usd_from_usd_per_eur(Q(fed_eu_m[m], "USD", "EUR")), Q(wb[m], "USD", "oz"))) for m in hc.month_range("1999-01", "1999-12") if m in fed_eu_m and m in wb}
            routes["C3_fed_1995_1998_plus_fedeuro_C3_1999"] = {**{m: v for m, v in routes.get("C3_fed_then_C4_1999", {}).items() if m < "1999-01"},
                                                              **{m: hc.grams_per_home_eur(hq[m], cf[m]) for m in cf}}
        base = routes.get("C3_fed_then_C4_1999", {})
        out = {}
        for name, r in routes.items():
            yr = {}
            for y in range(1995, 2000):
                v = [r[m] for m in ms if m.startswith(str(y)) and m in r]
                yr[str(y)] = {"n": len(v), "mean_g": format((sum(v) / len(v)).quantize(Decimal("0.01")), "f") if v else None}
            dv = {m: (r[m] - base[m]) / base[m] for m in r if m in base}
            out[name] = {"years": yr, "vs_base_C3_fed": hc.deviation_stats(dv) if name != "C3_fed_then_C4_1999" else "base"}
        S["grams_per_home_1995_1999"] = out
        # NVM selected years (median NLG, secondary quote), annual option A
        nvm = {}
        for y, nlg_price in NVM_NLG.items():
            row = {}
            hn = Q(nlg_price, "NLG", "home")
            he = hc.redenominate(hn)
            for name, (c1q, c3q) in constr.items():
                if y <= 1998:
                    a1 = hc.annual_mean(c1q, y)
                    a3 = hc.annual_mean(c3q, y)
                    if a1 and a3:
                        gn_ = hc.grams_per_home_nlg(hn, a1)
                        ge_ = hc.grams_per_home_eur(he, hc.Quote(a3.value, "EUR", "oz", "REDENOMINATED"))
                        row[name] = {"grams_nlg_route": format(gn_.quantize(Decimal("0.01")), "f"), "grams_eur_route": format(ge_.quantize(Decimal("0.01")), "f"),
                                     "annual_gold_nlg_oz": format(a1.value.quantize(Decimal("0.0001")), "f")}
                    else:
                        row[name] = None
            if y == 1999:
                a4 = hc.annual_mean(c4all, 1999)
                row["C4_observed_ecb"] = {"grams_eur_route": format(hc.grams_per_home_eur(he, a4).quantize(Decimal("0.01")), "f")} if a4 else None
            nvm[str(y)] = row
        S["nvm_selected_years_grams"] = nvm
    else:
        S["not_performed"].append("grams per home: needs World Bank, ECB and at least one FX source")

    # --- direct guilder gold (C2) probe
    raw = get("h07-cbs-catalog-gold")
    if raw:
        try:
            doc = json.loads(raw.decode("utf-8-sig"))
            S["c2_cbs_catalog_gold_titles"] = [str(x.get("Title"))[:90] + " | " + str(x.get("ShortTitle"))[:30] for x in doc.get("value", [])][:12]
        except ValueError:
            S["c2_cbs_catalog_gold_titles"] = "UNPARSEABLE"
    # --- canonical hash of the derived table
    cols = {k: v for k, v in table.items()}
    rows = hc.canonical_rows({k: ({m: x for m, x in v.items()}) for k, v in cols.items()})
    S["table"] = {"rows": len(rows), "columns": sorted(cols), "canonical_sha256": hc.canonical_sha256(rows)}
    core_missing = [m["source_id"] for m in S["missing_sources"] if m["source_id"] in (WB_ID, "ecb-exr-m-usd") or m["source_id"] in gn.FED_IDS]
    S["status"] = "INCOMPLETE" if core_missing else ("PARTIAL" if S["missing_sources"] or S["defects"] else "COMPLETE_RESEARCH")
    return S, rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary-out", required=True)
    ap.add_argument("--table-csv-out")
    ap.add_argument("--workbook")
    a = ap.parse_args(argv)
    out = Path(a.summary_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        S, rows = collect(a.workbook)
    except (hc.ConstructionError, wbv.ValidationError, fx.FxError, ns.NlgSourceError) as exc:
        out.write_text(json.dumps({"status": "FAILED", "error": str(exc)[:400]}, indent=1) + "\n")
        print("DEFECT", str(exc)[:400])
        return 1
    out.write_text(json.dumps(S, indent=1, sort_keys=True, default=str) + "\n")
    if a.table_csv_out and rows:
        cols = ["period"] + sorted({k for r in rows for k in r if k != "period"})
        with open(a.table_csv_out, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
    for key in sorted(S):
        if key in ("sources", "caveat"):
            continue
        print("REPORT", key, json.dumps(S[key], sort_keys=True, default=str)[:3500])
    print("REPORT sources", json.dumps({k: {"sha256": v["sha256"], "bytes": v["bytes"]} for k, v in S["sources"].items()}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
