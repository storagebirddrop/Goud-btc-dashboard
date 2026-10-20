"""HIST-05 research-only: ORIGINAL definition of the CBS/Kadaster average purchase price (85773NED, 83906NED,
81884NED) plus republication-rights texts. Nothing is approved; nothing is published; no public file is touched.

Every fact gets one of three statuses:
  OFFICIAL_CONFIRMED  a sentence in a retrieved official text (CBS/Kadaster/BIS page, TableInfos/DataProperties
                      metadata, method PDF) matches; the short quote and its source id are kept;
  DERIVED             computed by this tool from retrieved numbers (labelled; never a definition);
  NOT_RETRIEVED       nothing matching was retrieved (unreachable source, empty or missing field).
Rights evidence levels: OFFICIAL_TEXT_READ or NOT_RETRIEVED (SECONDARY_ONLY is assigned by hand in the report).

Rules: Decimal parsing; missing fields stay NOT_RETRIEVED, never guessed; a retrieved-but-malformed metadata body
raises Hist05DefError (fail closed: the source is reported as FORMAT_NOT_USABLE and counted as NOT_RETRIEVED);
duplicate periods / invalid numerics in the three core data tables are real defects (exit 1). Unreachable
sources only appear in missing_sources (exit 0). No interpolation, no back-calculation of levels from an index,
no NLG conversion is APPLIED to any series (numbers are only reported). Acquisition reuses
tools.hist_02_acquire.fetch (exact-URL allowlist, 15 MB, sha256); raw bytes stay in memory; the summary holds
metadata, short quotes, aggregates and sha256 only.
"""
import argparse
import json
import re
import statistics
import sys
from collections import Counter
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener
from decimal import Decimal
from pathlib import Path

from tools import hist_02_acquire
from tools.hist_05_cbs_kadaster import (Hist05Error, classify_measure, compare_series, fetch_status, level_continuity,
                                        load_fixture, load_json, parse_props, parse_typed, periods_between,
                                        pick_price_measure, strip_tags)
from tools.hist_05_other_sources import pdf_context, pdf_to_text

ODATA3 = "https://opendata.cbs.nl/ODataApi/OData/"
ODATA4 = "https://datasets.cbs.nl/odata/v1/CBS/"
CATALOG = "https://opendata.cbs.nl/ODataCatalog/Tables?$format=json&$filter="
CORE = ["85773NED", "83906NED", "81884NED"]
OLDER = ["71533NED", "80330NED", "83625NED", "83910NED", "83913NED", "81885NED", "84997NED"]
DEFAULT_PRICE_KEY_WORDS = ("gemiddelde", "verkoopprijs")
NLG_PER_EUR = Decimal("2.20371")
CATALOG_TITLE_KEYWORDS = ["koopwoningen", "Koopwoningen", "verkoopprijzen", "Verkoopprijzen", "gemiddelde", "Gemiddelde",
                          "Woningen", "woningen", "gulden", "Gulden"]
DISCOVERY_RE = re.compile(r"koopwoning|verkoopprijs|woningprijs|huizenprijs|koopsom|woningen", re.I)
MAX_DISCOVERED = 10

# id -> (url, format, group)
PAGES = {
    "cbs-85773-page": ("https://www.cbs.nl/nl-nl/cijfers/detail/85773NED", "html", "cbs_def"),
    "cbs-83906-page": ("https://www.cbs.nl/nl-nl/cijfers/detail/83906NED", "html", "cbs_def"),
    "cbs-81884-page": ("https://www.cbs.nl/nl-nl/cijfers/detail/81884NED", "html", "cbs_def"),
    "cbs-83625-page": ("https://www.cbs.nl/nl-nl/cijfers/detail/83625NED", "html", "cbs_def"),
    "cbs-faq-woningprijzen": ("https://www.cbs.nl/nl-nl/faq/specifiek/welke-cijfers-heeft-het-cbs-over-woningprijzen-", "html", "cbs_def"),
    "cbs-method-pbk-2015": ("https://www.cbs.nl/nl-nl/onze-diensten/methoden/onderzoeksomschrijvingen/korte-onderzoeksbeschrijvingen/prijsindex-bestaande-koopwoningen--pbk---2015-100", "html", "cbs_def"),
    "cbs-method-pbk-2010": ("https://www.cbs.nl/nl-nl/onze-diensten/methoden/onderzoeksomschrijvingen/korte-onderzoeksbeschrijvingen/prijsindex-bestaande-koopwoningen--pbk---2010-100", "html", "cbs_def"),
    "cbs-method-regio": ("https://www.cbs.nl/nl-nl/onze-diensten/methoden/onderzoeksomschrijvingen/korte-onderzoeksbeschrijvingen/prijzen-bestaande-koopwoningen-per-regio", "html", "cbs_def"),
    "cbs-background-2005": ("https://www.cbs.nl/nl-nl/achtergrond/2005/47/prijzen-koopwoningen", "html", "cbs_def"),
    "cbs-method-pdf-2018": ("https://www.cbs.nl/-/media/_pdf/2018/08/methodebeschrijving-prijsindex-bestaande-koopwoningen.pdf", "pdf", "cbs_def"),
    "cbs-method-pdf-2024": ("https://www.cbs.nl/-/media/cbs/onze-diensten/methoden/onderzoek/pdf/2024/methodebeschrijving-prijsindex-bestaande-koopwoningen-nl-4-1.pdf", "pdf", "cbs_def"),
    "cbs-method-pdf-2008": ("https://www.cbs.nl/-/media/imported/documents/2008/04/methodebeschrijving-prijsindex-bestaande-koopwoningen.pdf", "pdf", "cbs_def"),
    "overheid-45084": ("https://data.overheid.nl/dataset/45084-bestaande-koopwoningen--verkoopprijzen-prijsindex-2020-100", "html", "cbs_def"),
    "kadaster-vastgoedcijfers": ("https://www.kadaster.nl/zakelijk/vastgoedinformatie/vastgoedcijfers", "html", "kadaster_def"),
    "kadaster-vastgoeddashboard": ("https://www.kadaster.nl/zakelijk/vastgoedinformatie/vastgoedcijfers/vastgoeddashboard", "html", "kadaster_def"),
    "kadaster-gemiddelde-koopsom": ("https://www.kadaster.nl/zakelijk/producten/vastgoed/gemiddelde-koopsom", "html", "kadaster_def"),
    "kadaster-koopsom-woningtype": ("https://www.kadaster.nl/zakelijk/vastgoedinformatie/vastgoedcijfers/vastgoeddashboard/koopsom/gemiddelde-koopsom-per-woningtype", "html", "kadaster_def"),
    "cbs-copyright-nl": ("https://www.cbs.nl/nl-nl/over-ons/website/copyright", "html", "rights_cbs"),
    "cbs-copyright-en": ("https://www.cbs.nl/en-gb/about-us/website/copyright", "html", "rights_cbs"),
    "cbs-open-data": ("https://www.cbs.nl/nl-nl/onze-diensten/open-data", "html", "rights_cbs"),
    "kadaster-who": ("https://www.kadaster.nl/over-ons/wet-en-regelgeving/wet-hergebruik-van-overheidsinformatie", "html", "rights_kadaster"),
    "kadaster-kaart-open-data": ("https://www.kadaster.nl/-/als-u-de-kadastrale-kaart-als-open-data-opvraagt-wat-mag-u-er-dan-mee-c2-a0", "html", "rights_kadaster"),
    "kadaster-open-data-privacy": ("https://www.kadaster.nl/-/het-kadaster-verstrekt-ook-open-data-zitten-hier-persoonsgegevens-in-", "html", "rights_kadaster"),
    "kadaster-bag-voorwaarden": ("https://www.kadaster.nl/-/welke-voorwaarden-gelden-er-voor-het-gebruik-van-bag-data-7c-algemeen", "html", "rights_kadaster"),
    "kadaster-leveringsvoorwaarden": ("https://www.kadaster.nl/algemene-leveringsvoorwaarden", "html", "rights_kadaster"),
    "bis-terms-statistics": ("https://www.bis.org/terms_statistics.htm", "html", "rights_bis"),
    "bis-permitted-use-statistics": ("https://www.bis.org/about/legal/permitted-use-statistics", "html", "rights_bis"),
    "bis-data-help-legal": ("https://data.bis.org/help/legal", "html", "rights_bis"),
    "bis-terms-conditions": ("https://www.bis.org/about/terms-conditions", "html", "rights_bis"),
    "bis-permission-requests": ("https://www.bis.org/about/legal/permission-request", "html", "rights_bis"),
}
CANDIDATES = dict(PAGES)
for _t in CORE + OLDER:
    CANDIDATES[f"def3-{_t}-info"] = (f"{ODATA3}{_t}/TableInfos", "json", "meta")
    CANDIDATES[f"def3-{_t}-props"] = (f"{ODATA3}{_t}/DataProperties", "json", "meta")
    CANDIDATES[f"def-cat-{_t}"] = (CATALOG + f"Identifier%20eq%20%27{_t}%27", "json", "catalog_id")
for _t in CORE:
    CANDIDATES[f"def3-{_t}-data"] = (f"{ODATA3}{_t}/TypedDataSet", "json", "data")
    CANDIDATES[f"def3-{_t}-perioden"] = (f"{ODATA3}{_t}/Perioden", "json", "perioden")
for _t in CORE[:2]:
    CANDIDATES[f"def4-{_t}-properties"] = (f"{ODATA4}{_t}/Properties", "json", "meta4")
    CANDIDATES[f"def4-{_t}-perioden"] = (f"{ODATA4}{_t}/PeriodenCodes", "json", "perioden4")
for _k in CATALOG_TITLE_KEYWORDS:
    CANDIDATES[f"def-catalog-{_k}"] = (CATALOG + f"substringof(%27{_k}%27,Title)", "json", "catalog")
hist_02_acquire.SOURCES.update({k: (v[0], v[1]) for k, v in CANDIDATES.items()})


class Hist05DefError(ValueError):
    """Real parser/integrity defect or malformed retrieved metadata (fail closed). Never raised for unreachability."""


# ---------------------------------------------------------------- metadata parsers
INFO_FIELDS = ("Title", "ShortTitle", "ShortDescription", "Description", "Summary", "Period", "Frequency", "Modified",
               "ReleaseDate", "Updated", "Source", "Language", "Status", "MetaDataModified", "DefaultPresentation")
LONG_FIELDS = {"ShortDescription": 1500, "Description": 9000, "Summary": 700}


def _field(row, name):
    """Text value of a field or None (NOT_RETRIEVED). A non-scalar value is malformed (fail closed)."""
    v = row.get(name)
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    if isinstance(v, (dict, list, bool)):
        raise Hist05DefError(f"INVALID_FIELD_TYPE {name}")
    return str(v).strip()


def parse_table_info(doc):
    """TableInfos (v3: {"value":[{...}]}) or v4 Properties (one object) -> {"fields": {name: {status, value}}, "retrieved": n}."""
    if not isinstance(doc, dict):
        raise Hist05DefError("NOT_AN_OBJECT")
    if isinstance(doc.get("value"), list):
        if not doc["value"] or not isinstance(doc["value"][0], dict):
            raise Hist05DefError("EMPTY_TABLEINFOS")
        row = doc["value"][0]
    elif "Title" in doc or "Identifier" in doc:
        row = doc
    else:
        raise Hist05DefError("MISSING_VALUE_ARRAY")
    fields = {}
    for name in INFO_FIELDS:
        val = _field(row, name)
        fields[name] = ({"status": "NOT_RETRIEVED", "value": None} if val is None
                        else {"status": "OFFICIAL_CONFIRMED", "value": val[:LONG_FIELDS.get(name, 200)]})
    return {"fields": fields, "retrieved": sum(1 for f in fields.values() if f["value"] is not None)}


def parse_unit(unit):
    """Unit string -> {status, currency, scale, kind}. Empty/missing => NOT_RETRIEVED; unknown text => UNRECOGNISED (never guessed)."""
    if unit is None or not str(unit).strip():
        return {"status": "NOT_RETRIEVED", "currency": None, "scale": None, "kind": None}
    u = str(unit).strip().lower()
    cur = "NLG" if re.search(r"gulden|nlg|\bfl\b", u) else "EUR" if re.search(r"euro|\beur\b|€", u) else None
    scale = "million" if re.search(r"\bmln\b|miljoen|million", u) else "thousand" if re.search(r"\bx ?1 ?000\b|duizend|thousand", u) else "unit"
    if re.search(r"\d{4}\s*=\s*100", u):
        kind = "INDEX"
    elif "%" in u or "procent" in u:
        kind = "PERCENT"
    elif cur:
        kind = "MONEY"
    elif re.search(r"aantal|number", u):
        kind = "COUNT"
    else:
        return {"status": "UNRECOGNISED", "currency": None, "scale": None, "kind": None, "text": u[:40]}
    return {"status": "OFFICIAL_CONFIRMED", "currency": cur, "scale": scale, "kind": kind}


def parse_property_details(doc):
    """DataProperties -> per Topic {Key, Title, Description, Unit(+parsed), Decimals} with NOT_RETRIEVED for missing items."""
    rows = doc.get("value") if isinstance(doc, dict) else None
    if not isinstance(rows, list):
        raise Hist05DefError("MISSING_VALUE_ARRAY")
    out = {}
    for p in rows:
        if not isinstance(p, dict):
            raise Hist05DefError("PROPERTY_NOT_OBJECT")
        typ, key = str(p.get("Type", "")), p.get("Key")
        if not isinstance(key, str) or "Topic" not in typ or "Group" in typ:
            continue
        desc, unit, dec = _field(p, "Description"), _field(p, "Unit"), p.get("Decimals")
        if isinstance(dec, (dict, list, bool)):
            raise Hist05DefError("INVALID_FIELD_TYPE Decimals")
        out[key] = {"title": (_field(p, "Title") or "")[:140],
                    "description": {"status": "NOT_RETRIEVED" if desc is None else "OFFICIAL_CONFIRMED", "value": desc[:900] if desc else None},
                    "unit": unit, "unit_parsed": parse_unit(unit),
                    "decimals": None if dec is None else str(dec),
                    "classified": classify_measure(p.get("Title"), p.get("Unit"))}
    if not out:
        raise Hist05DefError("NO_TOPICS")
    return out


def parse_perioden_status(doc):
    """Perioden code list (v3: Key/Title/Description/Status; v4 may differ) -> status counters. No Status field => NOT_RETRIEVED."""
    rows = doc.get("value") if isinstance(doc, dict) else None
    if not isinstance(rows, list):
        raise Hist05DefError("MISSING_VALUE_ARRAY")
    keys = Counter()
    statuses = Counter()
    nonfinal = []
    for r in rows:
        if not isinstance(r, dict):
            raise Hist05DefError("PERIOD_ROW_NOT_OBJECT")
        keys.update(["rows"])
        st = r.get("Status")
        if st is None or (isinstance(st, str) and not st.strip()):
            statuses.update(["NOT_RETRIEVED"])
            continue
        if isinstance(st, (dict, list, bool)):
            raise Hist05DefError("INVALID_FIELD_TYPE Status")
        statuses.update([str(st)])
        if str(st).strip().lower() not in ("definitief", "final"):
            nonfinal.append(str(r.get("Key") or r.get("Identifier") or "")[:12])
    return {"rows": keys["rows"], "status_counts": dict(statuses), "non_final_periods_head": nonfinal[:12], "non_final_count": len(nonfinal),
            "status_field": "NOT_RETRIEVED" if set(statuses) <= {"NOT_RETRIEVED"} else "OFFICIAL_CONFIRMED"}


# ---------------------------------------------------------------- text facts
FACT_SPECS = {
    "existing_dwellings_scope": r"bestaande koop ?woningen|existing (owner[- ]occupied )?(dwellings|homes|houses)",
    "transaction_prices_not_asking": r"transactieprijz|verkooptransacties|notaristransacties|verkoopprijzen? .{0,60}(Kadaster|notari)|sales? prices?|transaction prices?",
    "asking_price_mention": r"vraagprijs|asking price",
    "source_kadaster": r"Kadaster|Land Registry|cadastre",
    "spar_method": r"\bSPAR\b|Sale Price Appraisal Ratio",
    "woz_mix_adjustment": r"WOZ",
    "average_is_plain_mean": r"som van de (transactie|verkoop)prijzen|gemiddelde koopsom is|gemiddelde van alle|zonder correctie|average of all",
    "average_not_price_development": r"gemiddelde verkoopprijs .{0,100}(geen indicator|niet)|geen indicator|not an indicator",
    "national_coverage": r"geheel Nederland|heel Nederland|Nederlandse grond|alle woningen in Nederland|landelijk|nationwide|whole of the Netherlands",
    "scope_exclusions": r"nieuwbouw|woonwagen|woonboot|niet-zelfstandige|new[- ]?build|particulier",
    "guilder_or_conversion": r"gulden|guilder|\bNLG\b|\bfl\.?\s?\d|omgerekend|omrekening|conversie|conversion|converted|2[,.]20371",
    "revision_policy": r"revisie|herzien|gecorrigeerd|voorlopig|definitief|eerste publicatie|revis(ed|ion)",
    "series_start_1995": r"1995",
}
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


def sentences(text):
    return [s.strip() for s in SENT_SPLIT.split(text or "") if 25 <= len(s.strip()) <= 700]


def extract_facts(corpus, specs=None, max_quotes=14):
    """corpus: {source_id: plain text}. Returns {fact: {status, quotes:[{source, quote}], sources_with_text}}.
    OFFICIAL_CONFIRMED means a matching sentence was READ in a retrieved text (not that the claim is true in general);
    nothing matched => NOT_RETRIEVED."""
    out = {}
    for fact, rx in (specs or FACT_SPECS).items():
        pat = re.compile(rx, re.I)
        quotes = []
        for sid in sorted(corpus):
            for s in sentences(corpus[sid]):
                if pat.search(s) and len(quotes) < max_quotes and all(q["quote"] != s[:260] for q in quotes):
                    quotes.append({"source": sid, "quote": s[:260]})
                    break  # at most one quote per source, so the quotes cover different sources
        out[fact] = {"status": "OFFICIAL_CONFIRMED" if quotes else "NOT_RETRIEVED", "quotes": quotes, "sources_with_text": len(corpus)}
    return out


def focus_sentences(text, regex, limit=14, maxlen=320):
    """Distinct sentences of one text that match REGEX (document order), shortened; used to read definition sections."""
    pat, out = re.compile(regex, re.I), []
    for s in sentences(text):
        if pat.search(s) and s[:maxlen] not in out:
            out.append(s[:maxlen])
        if len(out) >= limit:
            break
    return out


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def probe_redirect(sid, opener=None):
    """For an allowlisted URL that failed with UNAUTHORIZED_ENDPOINT_OR_REDIRECT: GET without following and report only
    status and the Location header (no body read; nothing fetched from the target). The target is a hint for a later,
    explicitly registered exact URL; it is never followed here."""
    url = hist_02_acquire.SOURCES[sid][0]
    hist_02_acquire.validate_url(sid, url)
    opener = opener or build_opener(_NoRedirect).open
    try:
        resp = opener(Request(url, headers={"User-Agent": "Goud-btc-dashboard/HIST-05 research"}), timeout=20)
    except HTTPError as exc:
        return {"http": exc.code, "location": (exc.headers.get("Location") or "")[:200] if exc.headers else None}
    except (OSError, URLError) as exc:
        return {"http": None, "error": type(exc).__name__}
    with resp:
        return {"http": getattr(resp, "status", None), "location": None}


def window_around(text, anchor, before=1500, after=1200):
    """Text window around the first occurrence of ANCHOR ('' when absent => NOT_RETRIEVED)."""
    i = (text or "").find(anchor)
    return text[max(0, i - before): i + len(anchor) + after] if i >= 0 else ""


def window_after(text, anchor, n=1800, occurrence=0):
    """Text window after the chosen occurrence (default: last) of ANCHOR; '' when the anchor is absent (NOT_RETRIEVED)."""
    idx = [mm.start() for mm in re.finditer(re.escape(anchor), text or "")]
    return text[idx[occurrence]: idx[occurrence] + n] if idx else ""


DESC_FOCUS = (r"verkoopprijs|revisie|herzien|definitief|voorlopig|eerste publicatie|gecorrigeerd|bronnen|methode|Kadaster|euro|gulden|NLG|"
              r"omgerekend|1995|gewicht|WOZ|SPAR|particulier|koopsom|nieuwbouw|vraagprijs")
METHOD_FOCUS = r"vanaf|sinds|gewicht|herzien|revisie|WIK|Repeat|SPAR|2005|2008|2013|gulden|euro|Kadaster|1995"
KADASTER_FOCUS = r"koopsom|PBK|prijsindex|NVM|kwaliteit|correctie|gemiddelde|notari|registr|verschil"
RIGHTS_SPEC = re.compile(r"toegestaan|permitted|permissible|free|vrij|unrestricted|CC[ -]?BY|CC0|Public Domain|licen[cs]e?|bronvermelding|"
                         r"naamsvermelding|cite|credit|must|verplicht|obliged|not permitted|prohibit|written permission|toestemming|"
                         r"commercial|hergebruik|re-?use|reproduc", re.I)


def rights_quotes(text, limit=5):
    cand = [s for s in sentences(text) if RIGHTS_SPEC.search(s)]
    cand.sort(key=lambda s: 0 if re.search(r"permitted|toegestaan|must|verplicht|obliged|not permitted|prohibit|permission|toestemming|CC[ -]?BY|CC0|Public Domain", s, re.I) else 1)
    return [s[:280] for s in cand[:limit]]


def rights_level(text):
    if not text:
        return "NOT_RETRIEVED"
    return "OFFICIAL_TEXT_READ" if rights_quotes(text, 1) else "NOT_RETRIEVED"


# ---------------------------------------------------------------- numeric analyses (DERIVED)
def month_range(series, first, last):
    labels = periods_between("M", first, last)
    return {k: series[k] for k in labels if series.get(k) is not None}


def mom_changes(series):
    """Month-on-month % change on consecutive observed months (consecutive only; gaps are not bridged)."""
    labs = sorted(k for k, v in series.items() if v is not None)
    out = {}
    for p, c in zip(labs, labs[1:]):
        if periods_between("M", p, c) == [p, c]:
            out[c] = (series[c] / series[p] - 1) * 100
    return out


def compare_mom(a, b, first="1995-02", last="1999-12"):
    """Max/mean absolute difference (percentage points) of month-on-month changes on shared months. Different index bases cancel out."""
    ma, mb = mom_changes(a), mom_changes(b)
    common = [k for k in periods_between("M", first, last) if k in ma and k in mb]
    if not common:
        return {"common_months": 0}
    d = [abs(ma[k] - mb[k]) for k in common]
    q = Decimal("0.0001")
    return {"common_months": len(common), "max_abs_diff_pp": str(max(d).quantize(q)),
            "mean_abs_diff_pp": str((sum(d) / len(d)).quantize(q)), "label": "DERIVED"}


def mom_stats(series, first, last):
    m = mom_changes(series)
    vals = [abs(m[k]) for k in periods_between("M", first, last) if k in m]
    if not vals:
        return {"months": 0}
    q = Decimal("0.001")
    return {"months": len(vals), "mean_abs_mom_pct": str((sum(vals) / len(vals)).quantize(q)),
            "median_abs_mom_pct": str(Decimal(str(statistics.median(vals))).quantize(q)), "max_abs_mom_pct": str(max(vals).quantize(q))}


def guilder_numbers(series, rate=NLG_PER_EUR, steps=(1, 10, 100, 1000), tol=Decimal("1.1")):
    """DERIVED, NOT CONCLUSIVE: x * 2.20371 and how close it is to multiples of 1/10/100/1000 guilders.
    A euro value rounded to whole euros moves the guilder equivalent by up to +-1.1 NLG, so only coarse steps carry any
    information, and an average of many transactions has no reason to be a round guilder amount. Numbers only."""
    vals = [v for v in series.values() if v is not None]
    if not vals:
        return {"observations": 0}
    out = {"observations": len(vals), "rate": str(rate), "tolerance_nlg": str(tol), "label": "DERIVED_NOT_CONCLUSIVE", "by_step": {}}
    for step in steps:
        hits = 0
        for v in vals:
            nlg = v * rate
            rem = nlg % step
            if min(rem, step - rem) <= tol:
                hits += 1
        out["by_step"][str(step)] = {"within_tolerance": hits, "expected_by_chance": str((Decimal(len(vals)) * min(Decimal(1), 2 * tol / Decimal(step))).quantize(Decimal("0.1")))}
    return out


def analyse_core(tid, props_doc, data_doc):
    """Price level, index and sales-count measures of one core table: Decimal series per measure (national, monthly)."""
    props = parse_props(props_doc)
    series, unsupported = parse_typed(data_doc, props)
    price = pick_price_measure(props["topics"], DEFAULT_PRICE_KEY_WORDS) or pick_price_measure(props["topics"], ("verkoopprijs",))
    index = [k for k, t in props["topics"].items() if t["kind"] == "INDEX"]

    def mon(key):
        combos = [fm.get("M") for (k, _), fm in series.items() if k == key and fm.get("M")]
        return combos[0] if len(combos) == 1 else None
    count = [k for k, t in props["topics"].items() if t["kind"] == "COUNT" and "verkocht" in t["title"].lower()]
    annual = [fm.get("A") for (k, _), fm in series.items() if k == price and fm.get("A")] if price else []
    return {"price_key": price, "index_keys": index, "price": mon(price) if price else None,
            "index": {k: mon(k) for k in index}, "count": mon(count[0]) if len(count) == 1 else None,
            "price_annual": annual[0] if len(annual) == 1 else None, "unsupported": len(unsupported)}


def weighted_annual_check(core, years=range(1995, 2000)):
    """DERIVED: count-weighted mean of the 12 monthly average prices of a year versus the published annual average (and the
    sum of monthly counts versus the published annual count is NOT available here). Tests whether the annual level is a plain
    mean over transactions (weights = counts), without mix adjustment. Any month missing => that year is skipped, not filled."""
    out = {}
    for t, c in sorted(core.items()):
        if not (c.get("price") and c.get("count") and c.get("price_annual")):
            continue
        rows = {}
        for y in years:
            labs = periods_between("M", f"{y}-01", f"{y}-12")
            if any(c["price"].get(k) is None or c["count"].get(k) is None for k in labs):
                continue
            n = sum(c["count"][k] for k in labs)
            w = sum(c["price"][k] * c["count"][k] for k in labs) / n if n else None
            pub = c["price_annual"].get(str(y))
            if w is None or pub is None:
                continue
            rows[str(y)] = {"weighted_monthly_mean": str(w.quantize(Decimal("0.01"))), "published_annual": str(pub), "diff": str((w - pub).quantize(Decimal("0.01"))),
                            "sum_monthly_counts": str(n), "label": "DERIVED"}
        out[t] = rows
    return out


PDF_YEAR_ROW = re.compile(r"^\s*((?:19|20)\d\d)\s+([\d.]{5,9})\s+([\d.]{5,9})\s*$", re.M)


def pdf_year_rows(text, limit=40):
    """Rows 'year  count  average-price' of a method-PDF table (layout text). Only exact three-column rows are kept."""
    return [{"year": y, "col_a": a, "col_b": b} for y, a, b in PDF_YEAR_ROW.findall(text or "")][:limit]


def revision_comparison(core, fixture):
    """Fixture vs tables on 1995-01..1999-12, tables against each other (levels exact; index via month-on-month)."""
    rng = ("1995-01", "1999-12")
    out = {}
    fx = month_range(fixture, *rng)
    prices = {t: month_range(c["price"], *rng) for t, c in core.items() if c.get("price")}
    for t, p in sorted(prices.items()):
        out[f"fixture_vs_{t}_price"] = compare_series(fx, p)
        out[f"{t}_price_months_1995_1999"] = len(p)
    ids = sorted(prices)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            out[f"{a}_vs_{b}_price"] = compare_series(prices[a], prices[b])
    idx = {t: next(iter(c["index"].values()), None) for t, c in core.items() if c.get("index")}
    idx = {t: v for t, v in idx.items() if v}
    ids = sorted(idx)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            out[f"{a}_vs_{b}_index_mom"] = compare_mom(idx[a], idx[b])
    return out


def break_statistics(core):
    out = {}
    for t, c in sorted(core.items()):
        if c.get("price"):
            out[f"{t}_price_boundary_1999-12_2000-01"] = level_continuity(c["price"])
            out[f"{t}_price_abs_mom_1995_1999"] = mom_stats(c["price"], "1995-02", "1999-12")
            out[f"{t}_price_abs_mom_2000_2004"] = mom_stats(c["price"], "2000-02", "2004-12")
        idx = next(iter((c.get("index") or {}).values()), None)
        if idx:
            out[f"{t}_index_boundary_1999-12_2000-01"] = level_continuity(idx)
            out[f"{t}_index_abs_mom_1995_1999"] = mom_stats(idx, "1995-02", "1999-12")
            out[f"{t}_index_abs_mom_2000_2004"] = mom_stats(idx, "2000-02", "2004-12")
    return out


# ---------------------------------------------------------------- catalogue rows
def catalog_info_rows(doc):
    rows = doc.get("value") if isinstance(doc, dict) else None
    if not isinstance(rows, list):
        raise Hist05DefError("MISSING_VALUE_ARRAY")
    out = []
    for r in rows:
        if not isinstance(r, dict) or not isinstance(r.get("Identifier"), str):
            continue
        out.append({"id": r["Identifier"].strip(), "title": str(r.get("Title") or "")[:160],
                    "period": str(r.get("Period") or "")[:60], "frequency": str(r.get("Frequency") or "")[:30],
                    "modified": str(r.get("Modified") or "")[:25], "release_date": str(r.get("ReleaseDate") or r.get("Updated") or "NOT_RETRIEVED")[:25],
                    "status": str(r.get("Status") or "NOT_RETRIEVED")[:30]})
    return out


# ---------------------------------------------------------------- orchestration
def fetch_json(sid, results, missing):
    raw, entry = fetch_status(sid)
    results.append(entry)
    print(json.dumps({sid: {k: entry.get(k) for k in ("status", "http_status", "bytes")}}, sort_keys=True), flush=True)
    if raw is None:
        missing.append(sid)
    return raw


def safe_json(raw, sid, findings):
    try:
        return load_json(raw)
    except Hist05Error as exc:
        findings.append({"source": sid, "finding": "FORMAT_NOT_USABLE", "reason": str(exc)})
        return None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary-out", required=True)
    args = ap.parse_args(argv)
    results, missing, defects, findings = [], [], [], []
    corpus, rights_text, metadata, units, perioden, catalog_ids = {}, {}, {}, {}, {}, {}
    props_raw = {}
    # 1. pages and PDFs
    for sid, (url, fmt, group) in sorted(PAGES.items()):
        raw, entry = fetch_status(sid)
        print(json.dumps({sid: {k: entry.get(k) for k in ("status", "http_status", "bytes")}}, sort_keys=True), flush=True)
        if raw is None:
            missing.append(sid)
            if str(entry.get("error", "")).startswith("UNAUTHORIZED_ENDPOINT_OR_REDIRECT"):
                entry["redirect_probe"] = probe_redirect(sid)
            results.append(entry)
            continue
        if fmt == "pdf":
            text, diag = pdf_to_text(raw)
            entry["pdf"] = diag
            if text is None:
                findings.append({"source": sid, "finding": "PDF_TEXT_NOT_EXTRACTED"})
        else:
            text = strip_tags(raw.decode("utf-8", "replace"))
        entry["text_chars"] = len(text or "")
        if group.startswith("rights_"):
            rights_text[sid] = text or ""
            entry["window_terms"] = window_after(text, "Terms of permitted use of BIS statistics", 2600) if sid.startswith("bis-") else ""
            entry["rights_evidence"] = rights_level(text)
            entry["rights_quotes"] = rights_quotes(text)
        else:
            corpus[sid] = text or ""
            if group == "kadaster_def":
                entry["rights_quotes"] = rights_quotes(text)
        results.append(entry)
    # 2. table metadata, property details, Perioden status
    for tid in CORE + OLDER:
        for kind in ("info", "props"):
            sid = f"def3-{tid}-{kind}"
            raw = fetch_json(sid, results, missing)
            if raw is None:
                continue
            if kind == "props":
                props_raw[tid] = raw
            doc = safe_json(raw, sid, findings)
            if doc is None:
                continue
            try:
                if kind == "info":
                    metadata[tid] = parse_table_info(doc)
                    corpus[sid] = " . ".join(f"{k}: {v['value']}" for k, v in metadata[tid]["fields"].items() if v["value"])
                else:
                    units[tid] = parse_property_details(doc)
                    corpus[sid] = " . ".join(f"{k}: {v['title']}. {v['description']['value'] or ''}" for k, v in units[tid].items())
            except Hist05DefError as exc:
                findings.append({"source": sid, "finding": "MALFORMED_METADATA", "reason": str(exc)})
        raw = fetch_json(f"def-cat-{tid}", results, missing)
        if raw is not None:
            doc = safe_json(raw, f"def-cat-{tid}", findings)
            try:
                rows = catalog_info_rows(doc) if doc is not None else []
            except Hist05DefError as exc:
                rows, _ = [], findings.append({"source": f"def-cat-{tid}", "finding": "MALFORMED_METADATA", "reason": str(exc)})
            if rows:
                catalog_ids[tid] = rows[0]
    for tid in CORE[:2]:
        raw = fetch_json(f"def4-{tid}-properties", results, missing)
        doc = safe_json(raw, f"def4-{tid}-properties", findings) if raw else None
        if doc is not None:
            try:
                metadata[tid + "_v4"] = parse_table_info(doc)
                corpus[f"def4-{tid}-properties"] = " . ".join(f"{k}: {v['value']}" for k, v in metadata[tid + "_v4"]["fields"].items() if v["value"])
            except Hist05DefError as exc:
                findings.append({"source": f"def4-{tid}-properties", "finding": "MALFORMED_METADATA", "reason": str(exc)})
    for tid in CORE:
        raw = fetch_json(f"def3-{tid}-perioden", results, missing)
        doc = safe_json(raw, f"def3-{tid}-perioden", findings) if raw else None
        if doc is not None:
            try:
                perioden[tid] = parse_perioden_status(doc)
            except Hist05DefError as exc:
                findings.append({"source": f"def3-{tid}-perioden", "finding": "MALFORMED_METADATA", "reason": str(exc)})
    # 3. catalogue title searches -> older/other 'gemiddelde verkoopprijs' tables
    discovered = {}
    for kw in CATALOG_TITLE_KEYWORDS:
        raw = fetch_json(f"def-catalog-{kw}", results, missing)
        doc = safe_json(raw, f"def-catalog-{kw}", findings) if raw else None
        try:
            for r in (catalog_info_rows(doc) if doc is not None else []):
                discovered[r["id"]] = r
        except Hist05DefError as exc:
            findings.append({"source": f"def-catalog-{kw}", "finding": "MALFORMED_METADATA", "reason": str(exc)})
    catalogue_hits = sorted((r for r in discovered.values() if DISCOVERY_RE.search(r["title"])), key=lambda r: r["id"])
    extra = [r for r in catalogue_hits if r["id"] not in CORE + OLDER and re.fullmatch(r"[0-9A-Za-z]{4,10}", r["id"])][:MAX_DISCOVERED]
    for r in extra:
        for kind, suffix in (("info", "TableInfos"), ("props", "DataProperties")):
            sid = f"def3-{r['id']}-{kind}"
            CANDIDATES[sid] = (f"{ODATA3}{r['id']}/{suffix}", "json", "meta")
            hist_02_acquire.SOURCES[sid] = (CANDIDATES[sid][0], "json")
            raw = fetch_json(sid, results, missing)
            doc = safe_json(raw, sid, findings) if raw else None
            try:
                if doc is not None and kind == "info":
                    metadata[r["id"]] = parse_table_info(doc)
                    corpus[sid] = " . ".join(f"{k}: {v['value']}" for k, v in metadata[r["id"]]["fields"].items() if v["value"])
                elif doc is not None:
                    units[r["id"]] = parse_property_details(doc)
                    corpus[sid] = " . ".join(f"{k}: {v['title']}. {v['description']['value'] or ''}" for k, v in units[r["id"]].items())
            except Hist05DefError as exc:
                findings.append({"source": sid, "finding": "MALFORMED_METADATA", "reason": str(exc)})
    # 4. core data: fixture / table comparison (integrity errors are real defects)
    core = {}
    for tid in CORE:
        raw = fetch_json(f"def3-{tid}-data", results, missing)
        pr = props_raw.get(tid)
        if raw is None or pr is None:
            continue
        try:
            core[tid] = analyse_core(tid, load_json(pr), load_json(raw))
        except Hist05Error as exc:
            if str(exc) in ("NOT_JSON", "MISSING_VALUE_ARRAY", "NO_PERIOD_OR_TOPICS"):
                findings.append({"source": f"def3-{tid}-data", "finding": "FORMAT_NOT_USABLE", "reason": str(exc)})
            else:
                defects.append(f"{tid}:{str(exc)[:80]}")
    try:
        fixture = load_fixture()
    except (OSError, ValueError, KeyError) as exc:
        fixture = {}
        defects.append(f"fixture:{type(exc).__name__}")
    revisions = revision_comparison(core, fixture) if not defects else {}
    breaks = break_statistics(core) if not defects else {}
    nlg = {t: guilder_numbers(month_range(c["price"], "1995-01", "1998-12")) for t, c in sorted(core.items()) if c.get("price")}
    nlg["fixture_1995_1998"] = guilder_numbers(month_range(fixture, "1995-01", "1998-12"))
    facts = extract_facts(corpus)
    pdf_windows = {}
    for sid in ("cbs-method-pdf-2008", "cbs-method-pdf-2018", "cbs-method-pdf-2024"):
        txt = corpus.get(sid, "")
        pdf_windows[sid] = {"around_table_1993_1994": window_around(txt, "81.037", 1800, 1500),
                            "average_price_contexts": pdf_context(txt, r"gemiddelde verkoopprijs|verkoopprijs", r"gemiddeld|euro|gulden", 350, 4)}
    pdf_tables = {sid: pdf_year_rows(corpus.get(sid, "")) for sid in ("cbs-method-pdf-2008", "cbs-method-pdf-2018", "cbs-method-pdf-2024")}
    description_excerpts = {t: focus_sentences(m["fields"]["Description"]["value"], DESC_FOCUS, 16) for t, m in sorted(metadata.items())
                            if t in CORE or t.replace("_v4", "") in CORE}
    method_history = {sid: focus_sentences(corpus.get(sid, ""), METHOD_FOCUS, 14) for sid in ("cbs-method-pbk-2010", "cbs-method-pbk-2015", "cbs-method-regio", "cbs-background-2005", "cbs-faq-woningprijzen", "cbs-method-pdf-2008", "cbs-method-pdf-2018", "cbs-method-pdf-2024")}
    kadaster_excerpts = {sid: focus_sentences(corpus.get(sid, ""), KADASTER_FOCUS, 30) for sid in sorted(PAGES) if PAGES[sid][2] == "kadaster_def"}
    summary = {"status": "DONE", "nothing_approved": True, "publication_authorized": False, "rights_status": "UNVERIFIED",
               "facts": facts, "table_metadata": metadata, "description_excerpts": description_excerpts,
               "method_history": method_history, "kadaster_excerpts": kadaster_excerpts,
               "rights_windows": {r["source_id"]: r["window_terms"] for r in results if r.get("window_terms")},
               "kadaster_page_rights_quotes": {r["source_id"]: r["rights_quotes"] for r in results if PAGES.get(r["source_id"], ("", "", ""))[2] == "kadaster_def"},
               "measure_details": {t: {k: v for k, v in m.items()} for t, m in units.items() if t in CORE or t in OLDER or t in [r["id"] for r in extra]},
               "perioden_status": perioden, "catalog_entries_of_known_tables": catalog_ids,
               "catalog_title_hits": catalogue_hits[:60], "catalog_extra_fetched": [r["id"] for r in extra],
               "price_keys": {t: c["price_key"] for t, c in core.items()}, "index_keys": {t: c["index_keys"] for t, c in core.items()},
               "revision_comparison": revisions, "weighted_annual_check": weighted_annual_check(core) if not defects else {}, "pdf_tables": pdf_tables, "pdf_windows": pdf_windows, "break_statistics": breaks, "guilder_numbers_derived": nlg,
               "rights": {sid: {"level": rights_level(t), "quotes": rights_quotes(t)} for sid, t in sorted(rights_text.items())},
               "results": results, "findings": findings, "missing_sources": sorted(set(missing)), "defects": defects}
    out = Path(args.summary_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: summary[k] for k in ("status", "missing_sources", "defects", "findings")}, sort_keys=True, default=str)[:3000])
    for line in report_lines(summary):
        print(line)
    return 1 if defects else 0


def report_lines(summary):
    """Compact aggregates-only rendering for CI logs."""
    out = []
    for f, v in sorted(summary["facts"].items()):
        out.append(f"FACT {f} {v['status']}")
        out += [f"  Q [{q['source']}] {q['quote'][:240]}" for q in v["quotes"]]
    for t, m in sorted(summary["table_metadata"].items()):
        fl = m["fields"]
        out.append(f"INFO {t} " + " | ".join(f"{k}={(fl[k]['value'] or 'NOT_RETRIEVED')[:110]}" for k in ("Title", "Period", "Frequency", "Modified", "ReleaseDate", "Source", "Status")))
        for k in ("ShortDescription", "Summary"):
            if fl[k]["value"]:
                out.append(f"  {k}: {fl[k]['value'][:1500]}")
    for t, m in sorted(summary["measure_details"].items()):
        for k, v in m.items():
            out.append(f"MEAS {t} {k}|{v['title'][:50]}|unit={v['unit']}|{v['unit_parsed']['status']}:{v['unit_parsed']['currency']}/{v['unit_parsed']['kind']}|dec={v['decimals']}|desc={(v['description']['value'] or 'NOT_RETRIEVED')[:700]}")
    for t, lst in sorted(summary["description_excerpts"].items()):
        out += [f"DESC {t} {q}" for q in lst]
    for sid, lst in sorted(summary["method_history"].items()):
        out += [f"METH {sid} {q}" for q in lst]
    for sid, lst in sorted(summary["kadaster_excerpts"].items()):
        out += [f"KAD {sid} {q}" for q in lst]
    for sid, lst in sorted(summary["kadaster_page_rights_quotes"].items()):
        out += [f"KADRIGHTS {sid} {q[:300]}" for q in lst[:4]]
    for sid, w in sorted(summary["rights_windows"].items()):
        out.append(f"BISWINDOW {sid} {w}")
    out.append("PERIODEN " + json.dumps(summary["perioden_status"], sort_keys=True, separators=(",", ":")))
    out.append("CATALOG " + json.dumps(summary["catalog_entries_of_known_tables"], sort_keys=True, separators=(",", ":"))[:2500])
    for r in summary["catalog_title_hits"]:
        out.append(f"HIT {r['id']}|{r['period']}|{r['frequency']}|{r['modified']}|{r['title'][:100]}")
    for sid, w in sorted(summary["pdf_windows"].items()):
        out.append(f"PDFWIN {sid} TABLE {w['around_table_1993_1994']}")
        out += [f"PDFWIN {sid} CTX {c}" for c in w["average_price_contexts"]]
    for key in ("weighted_annual_check", "pdf_tables", "revision_comparison", "break_statistics", "guilder_numbers_derived", "price_keys", "index_keys"):
        out.append(f"{key.upper()} " + json.dumps(summary[key], sort_keys=True, separators=(",", ":")))
    for sid, r in sorted(summary["rights"].items()):
        out.append(f"RIGHTS {sid} {r['level']}")
        out += [f"  Q {q}" for q in r["quotes"][:6]]
    for r in summary["results"]:
        out.append(f"SRC {r['source_id']} {r['status']} http={r.get('http_status')} bytes={r.get('bytes')} sha={(r.get('sha256') or '')[:16]} err={str(r.get('error') or '')[:90]} redirect={json.dumps(r.get('redirect_probe'), sort_keys=True) if r.get('redirect_probe') else ''} pdf={json.dumps(r.get('pdf'), sort_keys=True) if r.get('pdf') else ''}")
    out.append("FINDINGS " + json.dumps(summary["findings"], sort_keys=True, default=str)[:2000])
    out.append("MISSING " + json.dumps(summary["missing_sources"]))
    out.append("DEFECTS " + json.dumps(summary["defects"]))
    return out


if __name__ == "__main__":
    sys.exit(main())
