"""HIST-05 research-only: NVM and other reproducible Dutch house-price sources, 1975-1999 and toward 1900.

For every candidate the run records HTTP result, sha256, and what was ACTUALLY OBTAINED (parsed strictly
with Decimal) versus only REFERENCED. Labels: OBTAINED (machine-readable Netherlands observations parsed),
REFERENCE_ONLY (a page / file was fetched or a source is only named, but no usable observations were
parsed), UNREACHABLE (fetch failed). Measure type is classified: price LEVEL vs INDEX (with base period)
vs growth RATE; an index is never turned into a price level.

Rules: no interpolation, no synthetic monthly prices, no back-calculation of levels from an index, no
linking of different series, no publication, no repository data writes. Missing markers stay missing.
Duplicate periods and invalid numerics in machine formats (SDMX-CSV, XLSX) are hard errors
(HousingSourceError => exit 1); unreachable sources only appear in ``missing_sources`` (exit 0, PARTIAL).
Heuristic text extraction (PDF table) that does not match is reported as FORMAT_UNPARSED, not a defect.

Acquisition reuses tools.hist_02_acquire.fetch (exact-URL allowlist, 15 MB limit, sha256). Raw bytes stay
in memory; the output holds aggregates, anchors and short licence/definition quotes only. Comparison with
the existing CBS series (read from a CLI-supplied baseline CSV) is a growth-rate / ratio diagnostic on
shared periods ONLY; nothing is spliced or normalised.
"""
import argparse
import csv
import io
import json
import re
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation
from pathlib import Path

from tools import hist_02_acquire
from tools.hist_04_nlg_sources import page_facts, probe_status, strip_tags, dataflow_names

OECD = "https://sdmx.oecd.org/public/rest/data/OECD.ECO.MPD,DSD_AN_HOUSE_PRICES@DF_HOUSE_PRICES,1.0/"
BIS_API = "https://stats.bis.org/api/v2/data/dataflow/BIS/"
# id -> (url, format, group, kind). kind: data (machine-readable) | page (documentation / licence text).
CANDIDATES = {
    # (a) NVM and Dutch compilations
    "nvm-marktinformatie": ("https://www.nvm.nl/wonen/marktinformatie-wonen/", "html", "nvm", "page"),
    "nvm-copyright": ("https://www.nvm.nl/special-pages/copyright/", "html", "nvm", "page"),
    "nvm-home": ("https://www.nvm.nl/", "html", "nvm", "page"),
    "vastgoedmarkt-kerncijfers-pdf": ("https://vmn-vastgoedmarkt.imgix.net/uploads/2024/07/kerncijfers-vastgoedmarkt-1974-2024.pdf", "pdf", "compilation", "pdf_table"),
    "esb-copyright": ("https://esb.nu/copyright-statement/", "html", "compilation", "page"),
    "esb-nvm-median": ("https://esb.nu/vast-aanbod-flexibele-vraag/", "html", "compilation", "page"),
    # (b) BIS residential property prices
    "bis-spp-q-nl": (BIS_API + "WS_SPP/1.0/Q.NL?format=csv", "csv", "bis", "sdmx_csv"),
    "bis-spp-all-nl": (BIS_API + "WS_SPP/1.0/*.NL?format=csv", "csv", "bis", "sdmx_csv"),
    "bis-spp-bulk-zip": ("https://www.bis.org/statistics/full_webstats_spp_dataflow_csv.zip", "zip", "bis", "sdmx_zip"),
    "bis-spp-bulk-flat-zip": ("https://data.bis.org/static/bulk/WS_SPP_csv_flat.zip", "zip", "bis", "sdmx_zip"),
    "bis-long-pp-q-nl": (BIS_API + "WS_LONG_PP/1.0/Q.NL?format=csv", "csv", "bis", "sdmx_csv"),
    "bis-spp-structure": ("https://stats.bis.org/api/v2/structure/dataflow/BIS/WS_SPP/1.0", "xml", "bis", "page"),
    "bis-pp-page": ("https://www.bis.org/statistics/pp.htm", "html", "bis", "page"),
    "bis-pp-selected-page": ("https://www.bis.org/statistics/pp_selected.htm", "html", "bis", "page"),
    "bis-pp-long-page": ("https://www.bis.org/statistics/pp_long.htm", "html", "bis", "page"),
    "bis-terms": ("https://www.bis.org/about/terms-conditions", "html", "bis", "page"),
    "bis-data-legal": ("https://data.bis.org/legal", "html", "bis", "page"),
    "bis-legal": ("https://data.bis.org/help/legal", "html", "bis", "page"),
    "bis-pp-selected-documentation-pdf": ("https://www.bis.org/pages/statistics/pp-documentation.pdf", "pdf", "bis", "pdf_text"),
    "bis-pp-sources-pdf": ("https://www.bis.org/pages/statistics/pp-sources.pdf", "pdf", "bis", "pdf_text"),
    "bis-data-portal-rpp": ("https://data.bis.org/topics/RPP", "html", "bis", "page"),
    # (c) OECD
    "oecd-hp-nld": (OECD + "NLD.....?format=csv", "csv", "oecd", "sdmx_csv"),
    "oecd-hp-all": (OECD + "all?format=csv", "csv", "oecd", "sdmx_csv"),
    "oecd-dataflows": ("https://sdmx.oecd.org/public/rest/dataflow/all", "xml", "oecd", "dataflow_list"),
    "oecd-terms": ("https://www.oecd.org/en/about/terms-conditions.html", "html", "oecd", "page"),
    # (d) long-run academic / institutional
    "dallas-houseprice-page": ("https://www.dallasfed.org/research/international/houseprice", "html", "dallas", "page"),
    "dallas-hp2604-xlsx": ("https://www.dallasfed.org/~/media/documents/research/international/houseprice/hp2604.xlsx", "xlsx", "dallas", "xlsx"),
    "dallas-hp2604-xlsx-dash": ("https://www.dallasfed.org/-/media/documents/research/international/houseprice/hp2604.xlsx", "xlsx", "dallas", "xlsx"),
    "dallas-hp2604-xlsx-dash-caps": ("https://www.dallasfed.org/-/media/Documents/research/international/houseprice/hp2604.xlsx", "xlsx", "dallas", "xlsx"),
    "jst-macrohistory-page": ("https://www.macrohistory.net/database/", "html", "jst", "page"),
    "jst-licence-terms": ("https://www.macrohistory.net/database/licence-terms/", "html", "jst", "page"),
    "jst-r6-xlsx": ("https://www.macrohistory.net/app/download/9834512569/JSTdatasetR6.xlsx?t=1763503850", "xlsx", "jst", "xlsx_panel"),
    "jst-r6-documentation-pdf": ("https://www.macrohistory.net/app/download/9834516169/JST_documentationR6.pdf?t=1676279836", "pdf", "jst", "pdf_text"),
    "jst-r6-xlsx-cdn": ("https://sfff5b3ac9317c4be.jimcontent.com/download/version/1763503850/module/9834512569/name/JSTdatasetR6.xlsx", "xlsx", "jst", "xlsx_panel"),
    "jst-r6-documentation-pdf-cdn": ("https://sfff5b3ac9317c4be.jimcontent.com/download/version/1676279836/module/9834516169/name/JST_documentationR6.pdf", "pdf", "jst", "pdf_text"),
    "jst-macrohistory-home": ("https://www.macrohistory.net/", "html", "jst", "page"),
    "imf-ghw-page": ("https://www.imf.org/en/Topics/Global-Housing-Watch", "html", "imf", "page"),
    "eurostat-hpi-q-nl": ("https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/PRC_HPI_Q/Q.TOTAL.I15_Q.NL?format=SDMX-CSV", "csv", "eurostat", "sdmx_csv"),
    # (e) Dutch open-data catalogue
    "overheid-ckan-woningprijzen": ("https://data.overheid.nl/data/api/3/action/package_search?q=woningprijzen&rows=10", "json", "overheid", "ckan"),
    "overheid-ckan-koopwoningen": ("https://data.overheid.nl/data/api/3/action/package_search?q=koopwoningen&rows=10", "json", "overheid", "ckan"),
}
hist_02_acquire.SOURCES.update({k: (v[0], v[1]) for k, v in CANDIDATES.items()})

# Named but never fetched here: explicit REFERENCE_ONLY entries. Statements marked [K] are own knowledge, unverified.
REFERENCES = {
    "knoll-schularick-steger-no-price-like-home": "Knoll, Schularick, Steger, AER 2017, annual house price indices 1870-2012 for 14 advanced economies; whether the Netherlands is included and from which year is [K] UNVERIFIED here. Data distributed via macrohistory.net.",
    "eichholtz-herengracht": "Eichholtz (1997) Herengracht index 1628-1973, repeat sales of Amsterdam canal houses; local, not national [K] UNVERIFIED here; data file not located.",
    "dutch-long-run-national-accounts": "Smits/Horlings/van Zanden and CBS 'Tweehonderd jaar statistiek' long-run series; house price content [K] UNVERIFIED, not located.",
    "dnb-cpb-publications": "DNB / CPB publications may contain house price series; no machine-readable file located.",
    "ecb-rpp": "ECB residential property price statistics (RPP); start period expected well after 1990 [K], not fetched.",
}

PDF_SENTENCE_RE = r"house price|housing price|hpnom|hpreal|residential property|Netherlands|Dutch|Kadaster|NVM"
PDF_FOCUS = {
    "bis-pp-selected-documentation-pdf": {"anchor": r"NL Netherlands Compilation", "near": r".", "width": 900, "limit": 1},
    "bis-pp-sources-pdf": {"anchor": r"NL Netherlands|Netherlands", "near": r".", "width": 250, "limit": 3},
    "jst-r6-documentation-pdf-cdn": {"anchor": r"Netherlands", "near": r"house price|Herengracht|Eichholtz|Knoll|housing", "width": 600, "limit": 8},
}
PERIOD_RE = re.compile(r"(\d{4})(?:-?Q([1-4])|-(\d{2}))?")
TIME_COLS = {"TIME_PERIOD", "Time period", "TIME PERIOD", "DATE"}
OBS_COLS = {"OBS_VALUE", "Observation value", "Observation Value", "VALUE_OBS"}
OBS_ATTR_COLS = {"OBS_STATUS", "OBS_CONF", "OBS_PRE_BREAK", "COMMENT_OBS", "OBS_COMMENT", "OBS_FLAG",
                 "Observation Status", "Observation confidentiality", "Observation pre-break value", "Observation comment",
                 "LAST UPDATE", "STRUCTURE", "STRUCTURE_ID", "STRUCTURE_NAME", "ACTION", "DATAFLOW"}
AREA_COLS = {"REF_AREA", "Reference area", "COUNTRY", "Country", "geo", "REF_AREA_LABEL"}
MISSING = {"", ".", "NA", "N/A", "NaN", "nan", "-", "ND", "NULL"}
NUM_RE = re.compile(r"-?\d+(\.\d+)?([eE][+-]?\d+)?")
BASE_RES = [re.compile(r"(?i)\b((?:19|20)\d\d)\s*=\s*100\b"),
            re.compile(r"(?i)\b(?:base|reference)[^0-9]{0,20}((?:19|20)\d\d)"),
            re.compile(r"(?i)index[^0-9]{0,12}((?:19|20)\d\d)(?:\s*=\s*100)?")]
LICENCE_KEYWORDS = (r"licen[cs]e|copyright|reproduc|redistribut|re-?use|terms of use|creative commons|CC[ -]?BY|non-?commercial|"
                    r"attribution|auteursrecht|overnemen|toestemming|bronvermelding|public domain|permission|cite|citation")
DEFINITION_KEYWORDS = r"transaction|asking|existing dwellings|new dwellings|average price|median|mediaan|index|nominal|real|quarterly|annual|netherlands|nederland|woning|verkoopprijs|1970|1975|1900"


class HousingSourceError(ValueError):
    """Real parser / integrity defect (fail closed); never raised for mere unreachability."""


# ------------------------------------------------------------------ periods, values
def parse_period(text):
    """-> (freq, year, sub, ordinal). A: 1975; Q: 1975-Q1 / 1975Q1 / 1975:Q1; M: 1975-01. Anything else is a hard error."""
    t = text.strip().replace(":", "-")
    m = PERIOD_RE.fullmatch(t)
    if not m:
        raise HousingSourceError("INVALID_PERIOD " + text[:20])
    y = int(m.group(1))
    if m.group(2):
        q = int(m.group(2))
        return "Q", y, q, y * 4 + q - 1
    if m.group(3):
        mo = int(m.group(3))
        if not 1 <= mo <= 12:
            raise HousingSourceError("INVALID_PERIOD " + text[:20])
        return "M", y, mo, y * 12 + mo - 1
    return "A", y, 1, y


def to_decimal(text):
    t = text.strip()
    if not NUM_RE.fullmatch(t):
        raise HousingSourceError("INVALID_VALUE")
    try:
        v = Decimal(t)
    except InvalidOperation as exc:
        raise HousingSourceError("INVALID_VALUE") from exc
    if not v.is_finite():
        raise HousingSourceError("INVALID_VALUE")
    return v


def ordinal_to_period(freq, ordinal):
    if freq == "A":
        return str(ordinal)
    if freq == "Q":
        return f"{ordinal // 4}-Q{ordinal % 4 + 1}"
    return f"{ordinal // 12}-{ordinal % 12 + 1:02d}"


def year_ranges(years):
    out, ys = [], sorted(set(years))
    for y in ys:
        if out and y == out[-1][1] + 1:
            out[-1][1] = y
        else:
            out.append([y, y])
    return [f"{a}-{b}" if a != b else str(a) for a, b in out]


# ------------------------------------------------------------------ classification
def detect_base(attrs):
    """Base period of an index from attribute text ('2010=100', 'Index, 2015 = 100', BASE_PER) or None."""
    mu = re.fullmatch(r"I(\d{2})_[QA]", _code(attrs, "UNIT") or "")
    if mu:
        return "20" + mu.group(1)
    bp = _code(attrs, "BASE_PER")
    if bp and re.fullmatch(r"(19|20)\d\d", bp):
        return bp
    blob = " | ".join(str(v) for v in attrs.values())
    for rx in BASE_RES:
        m = rx.search(blob)
        if m:
            return m.group(1)
    return None


def _code(attrs, name):
    for k, v in attrs.items():
        if k.split(":")[0].strip().upper() == name:
            return str(v).split(":")[0].strip().upper()
    return None


def classify_unit(attrs):
    um = _code(attrs, "UNIT_MEASURE")
    if _code(attrs, "VARIABLE") in {"HPNOM", "HPREAL"}:
        return "INDEX"  # inferred from the JST variable name only; confirmed or refuted by the documentation text in the same run
    if um in {"628", "IX"} or (um or "").startswith("IX"):
        return "INDEX"
    if re.fullmatch(r"I\d{2}_[QA]", (_code(attrs, "UNIT") or "")):
        return "INDEX"
    if um in {"771"} or (um or "").startswith(("PC", "PT")):
        return "RATE"
    blob = " ".join(str(v) for v in attrs.values())
    low = blob.lower()
    if re.search(r"year-on-year|percentage change|growth|% change|per cent change|annual change|rate of change", low):
        return "RATE"
    if re.search(r"\bindex\b|=\s*100|\bidx\b|index,", low) or detect_base(attrs):
        return "INDEX"
    if re.search(r"\b(nlg|eur|euro|guilder|gulden|usd)\b|\bnational currency\b", low):
        return "LEVEL"
    return "UNDETERMINED"


def classify_real_nominal(attrs):
    val, meas = _code(attrs, "VALUE"), _code(attrs, "MEASURE")
    var = _code(attrs, "VARIABLE")
    if var in {"HPNOM", "HPREAL"}:
        return "NOMINAL" if var == "HPNOM" else "REAL"
    if val in {"N", "R"}:
        return "NOMINAL" if val == "N" else "REAL"
    if meas == "RHP":
        return "REAL"
    if meas == "HPI":
        return "NOMINAL"
    low = " ".join(str(v) for v in attrs.values()).lower()
    if re.search(r"\breal\b|deflat|\brhp\b|constant price", low):
        return "REAL"
    if re.search(r"\bnominal\b|\bcurrent price", low):
        return "NOMINAL"
    return "UNSPECIFIED"


KEEP_ATTRS = re.compile(r"(?i)^(FREQ|Frequency|VALUE|Value|UNIT_MEASURE|Unit of measure|UNIT|MEASURE|Measure|TITLE|TITLE_TS|Series|"
                        r"BASE_PER|DECIMALS|UNIT_MULT|SOURCE_REF|SOURCE|COVERAGE|PRICE_BASE|ADJUSTMENT|TRANSFORMATION|PURCHASE|purchase|unit|"
                        r"COLLECTION|Collection|DWELLING|sheet|country)")


def compact_attrs(attrs):
    return {k.split(":")[0][:30]: v[:110] for k, v in attrs.items() if KEEP_ATTRS.match(k.split(":")[0]) and v}


# ------------------------------------------------------------------ series summary
def summarize_series(attrs, points, missing):
    """points {period_text: Decimal}. Returns (summary, {ordinal: Decimal}, freq). Mixed frequency is a defect."""
    if not points:
        return None, {}, None
    parsed = {}
    freqs = set()
    for p, v in points.items():
        f, y, s, o = parse_period(p)
        freqs.add(f)
        parsed[o] = v
    if len(freqs) != 1:
        raise HousingSourceError("MIXED_FREQUENCY_IN_SERIES")
    freq = freqs.pop()
    ords = sorted(parsed)
    step = {"A": 1, "Q": 1, "M": 1}[freq]
    gaps = [o for o in range(ords[0], ords[-1] + 1, step) if o not in parsed]
    years = [o if freq == "A" else o // 4 if freq == "Q" else o // 12 for o in ords]
    pre2000 = [y for y in years if y <= 1999]
    n_pre = sum(1 for y in years if y <= 1999)
    comp = compact_attrs(attrs)
    summary = {
        "attrs": comp, "frequency": freq, "first": ordinal_to_period(freq, ords[0]), "last": ordinal_to_period(freq, ords[-1]),
        "n_obs": len(ords), "missing_markers": missing, "gap_count": len(gaps),
        "gaps_first5": [ordinal_to_period(freq, g) for g in gaps[:5]],
        "unit_class": classify_unit(attrs), "base_period": detect_base(attrs), "real_or_nominal": classify_real_nominal(attrs),
        "first_value": str(parsed[ords[0]]), "last_value": str(parsed[ords[-1]]),
        "n_obs_1975_1999": sum(1 for y in years if 1975 <= y <= 1999),
        "n_obs_up_to_1999": n_pre, "years_up_to_1999": year_ranges(pre2000)[:12],
    }
    return summary, parsed, freq


# ------------------------------------------------------------------ SDMX-CSV
def _norm(h):
    return h.split(":")[0].strip()


def _is_nl(vals):
    for v in vals:
        head = v.split(":")[0].strip()
        if head in {"NL", "NLD"} or "netherlands" in v.lower():
            return True
    return False


def scan_sdmx_csv(rows, max_series=40):
    """rows: csv.reader iterable. Long (TIME_PERIOD/OBS_VALUE) or wide (period columns) layout; keeps Netherlands only.
    Returns {"layout","rows_scanned","nl_series_count","nl_series","_parsed"}."""
    it = iter(rows)
    header = next((r for r in it if r and any(c.strip() for c in r)), None)
    if header is None:
        raise HousingSourceError("EMPTY_CSV")
    header = [c.strip() for c in header]
    norm = [_norm(c) for c in header]
    tcol = next((i for i, c in enumerate(norm) if c in TIME_COLS), None)
    ocol = next((i for i, c in enumerate(norm) if c in OBS_COLS), None)
    wide = [i for i, c in enumerate(norm) if PERIOD_RE.fullmatch(c) and len(c) >= 4]
    if tcol is not None and ocol is not None:
        layout = "long"
    elif len(wide) >= 10:
        layout = "wide"
    else:
        raise HousingSourceError("CSV_LAYOUT_UNRECOGNISED " + json.dumps(header[:8]))
    skip = set(wide) | {tcol, ocol}
    attr_idx = [i for i in range(len(header)) if i not in skip and norm[i] not in OBS_ATTR_COLS and norm[i] not in TIME_COLS | OBS_COLS]
    area_idx = [i for i in attr_idx if norm[i] in AREA_COLS]
    series, total = {}, 0
    for r in it:
        if not r:
            continue
        total += 1
        if area_idx and not _is_nl([r[i] for i in area_idx if i < len(r)]):
            continue
        attrs = tuple((header[i], r[i].strip() if i < len(r) else "") for i in attr_idx)
        s = series.setdefault(attrs, {"_missing": 0})
        pairs = [(r[tcol].strip(), r[ocol].strip())] if layout == "long" else [(norm[i], r[i].strip()) for i in wide if i < len(r)]
        for p, v in pairs:
            if v in MISSING:
                s["_missing"] += 1
                continue
            if p in s:
                raise HousingSourceError("DUPLICATE_PERIOD_IN_SERIES")
            s[p] = to_decimal(v)
    out, parsed_store = [], {}
    for attrs, s in series.items():
        miss = s.pop("_missing")
        summ, parsed, freq = summarize_series(dict(attrs), s, miss)
        if summ:
            out.append(summ)
            parsed_store[len(out) - 1] = (parsed, freq, dict(attrs))
    return {"layout": layout, "rows_scanned": total, "header": header[:14], "area_filter_columns": [header[i] for i in area_idx],
            "nl_series_count": len(out), "nl_series": out[:max_series], "_parsed": parsed_store}


def scan_csv_bytes(raw):
    return scan_sdmx_csv(csv.reader(io.StringIO(raw.decode("utf-8-sig", "replace"))))


def scan_zip_bytes(raw, max_member=400_000_000):
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as exc:
        raise HousingSourceError("BAD_ZIP") from exc
    members = [i for i in zf.infolist() if i.filename.lower().endswith(".csv")]
    if not members:
        raise HousingSourceError("NO_CSV_IN_ZIP " + json.dumps([i.filename[:60] for i in zf.infolist()][:5]))
    big = max(members, key=lambda i: i.file_size)
    if big.file_size > max_member:
        raise HousingSourceError("ZIP_MEMBER_TOO_LARGE")
    with zf.open(big) as fh:
        res = scan_sdmx_csv(csv.reader(io.TextIOWrapper(fh, encoding="utf-8-sig", errors="replace", newline="")))
    res["zip_member"] = big.filename[:80]
    res["zip_members"] = len(members)
    return res


# ------------------------------------------------------------------ XLSX (Dallas Fed layout, generic)
def _col_index(ref):
    letters = re.match(r"[A-Z]+", ref).group()
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1


def read_xlsx_sheets(raw, max_rows=3000, max_cols=400):
    """-> {sheet_name: [[cell str, ...], ...]}; shared strings resolved; no formulas evaluated."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as exc:
        raise HousingSourceError("BAD_XLSX_ZIP") from exc
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
          "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
    try:
        shared = []
        if "xl/sharedStrings.xml" in zf.namelist():
            for si in ET.fromstring(zf.read("xl/sharedStrings.xml")).findall("m:si", ns):
                shared.append("".join(t.text or "" for t in si.iter("{%s}t" % ns["m"])))
        wb = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = {r.attrib["Id"]: r.attrib["Target"] for r in ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))}
        sheets = {}
        for sh in wb.find("m:sheets", ns):
            target = rels[sh.attrib["{%s}id" % ns["r"]]].lstrip("/")
            path = target if target.startswith("xl/") else "xl/" + target
            rows = []
            for row in ET.fromstring(zf.read(path)).iter("{%s}row" % ns["m"]):
                cells = {}
                for c in row.findall("m:c", ns):
                    idx = _col_index(c.attrib["r"])
                    if idx >= max_cols:
                        continue
                    v = c.find("m:v", ns)
                    t = c.attrib.get("t")
                    if t == "s" and v is not None:
                        cells[idx] = shared[int(v.text)]
                    elif t == "inlineStr":
                        cells[idx] = "".join(x.text or "" for x in c.iter("{%s}t" % ns["m"]))
                    elif v is not None and v.text is not None:
                        cells[idx] = v.text
                rows.append([cells.get(i, "") for i in range(max(cells) + 1)] if cells else [])
                if len(rows) >= max_rows:
                    break
            sheets[sh.attrib["name"]] = rows
        return sheets
    except (KeyError, ET.ParseError, ValueError, IndexError) as exc:
        raise HousingSourceError("XLSX_STRUCTURE_ERROR " + type(exc).__name__) from exc


def scan_xlsx_country(raw, country="Netherlands"):
    """Find, per sheet, a header cell equal to the country; read period labels from the first column."""
    sheets = read_xlsx_sheets(raw)
    out, parsed_store = [], {}
    for name, rows in sheets.items():
        hdr = next(((ri, r.index(country)) for ri, r in enumerate(rows[:15]) if country in r), None)
        if hdr is None:
            continue
        ri, ci = hdr
        notes = [c.strip()[:140] for r in rows[:ri] for c in r[:2] if c.strip()][:4]
        points, missing = {}, 0
        for r in rows[ri + 1:]:
            if not r or not r[0].strip():
                continue
            label = r[0].strip()
            m = re.fullmatch(r"(\d{4})\s*[:\-]?\s*Q([1-4])", label)
            if not m:
                continue  # footnotes / non-period rows
            period = f"{m.group(1)}-Q{m.group(2)}"
            v = r[ci].strip() if ci < len(r) else ""
            if v in MISSING:
                missing += 1
                continue
            if period in points:
                raise HousingSourceError("DUPLICATE_PERIOD_IN_SERIES")
            points[period] = to_decimal(v)
        attrs = {"sheet": name, "country": country}
        summ, parsed, freq = summarize_series(attrs, points, missing)
        if summ:
            summ["sheet_notes"] = notes
            out.append(summ)
            parsed_store[len(out) - 1] = (parsed, freq, attrs)
    return {"layout": "xlsx", "sheet_names": list(sheets)[:12], "nl_series_count": len(out), "nl_series": out, "_parsed": parsed_store}


def scan_xlsx_panel(raw, country="Netherlands", var_prefix="hp"):
    """Long-run panel layout (JST): header row has 'country' and 'year'; keep variables starting with var_prefix for one country.
    Annual series; blanks stay missing; duplicate years / non-numeric cells are hard errors."""
    sheets = read_xlsx_sheets(raw, max_rows=20000, max_cols=400)
    out, parsed_store = [], {}
    for name, rows in sheets.items():
        hdr = next((ri for ri, r in enumerate(rows[:10]) if "country" in [c.strip().lower() for c in r] and "year" in [c.strip().lower() for c in r]), None)
        if hdr is None:
            continue
        head = [c.strip() for c in rows[hdr]]
        ci, yi = head.index(next(c for c in head if c.lower() == "country")), head.index(next(c for c in head if c.lower() == "year"))
        cols = [i for i, c in enumerate(head) if c.lower().startswith(var_prefix) and i not in (ci, yi)]
        data = {i: ({}, [0]) for i in cols}
        countries = set()
        for r in rows[hdr + 1:]:
            if len(r) <= max(ci, yi) or not r[ci].strip():
                continue
            countries.add(r[ci].strip())
            if r[ci].strip() != country:
                continue
            ym = re.fullmatch(r"(\d{4})(?:\.0+)?", r[yi].strip())
            if not ym:
                raise HousingSourceError("INVALID_PERIOD " + r[yi][:20])
            for i in cols:
                v = r[i].strip() if i < len(r) else ""
                pts, miss = data[i]
                if v in MISSING:
                    miss[0] += 1
                    continue
                if ym.group(1) in pts:
                    raise HousingSourceError("DUPLICATE_PERIOD_IN_SERIES")
                pts[ym.group(1)] = to_decimal(v)
        for i in cols:
            pts, miss = data[i]
            summ, parsed, freq = summarize_series({"sheet": name, "country": country, "variable": head[i]}, pts, miss[0])
            if summ:
                summ["variable"] = head[i]
                out.append(summ)
                parsed_store[len(out) - 1] = (parsed, freq, {"variable": head[i]})
        if out:
            return {"layout": "xlsx_panel", "sheet_names": list(sheets)[:12], "countries_in_sheet": len(countries), "variables_scanned": [head[i] for i in cols],
                    "nl_series_count": len(out), "nl_series": out, "_parsed": parsed_store}
    return {"layout": "xlsx_panel", "sheet_names": list(sheets)[:12], "nl_series_count": 0, "nl_series": [], "_parsed": {}}


# ------------------------------------------------------------------ PDF table (Vastgoedmarkt)
VM_HEADING = r"Gemiddelde\s+verkoopprijs\s+bestaande\s+woningen"


def pdf_to_text(raw):
    """-> (text or None, diagnostics). Pure in-memory: bytes via stdin, text via stdout."""
    diag = {"magic": raw[:5].decode("latin-1")}
    try:
        p = subprocess.run(["pdftotext", "-layout", "-", "-"], input=raw, capture_output=True, timeout=60, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        diag["error"] = type(exc).__name__
        return None, diag
    diag.update({"returncode": p.returncode, "stdout_bytes": len(p.stdout), "stderr": p.stderr.decode("utf-8", "replace")[:160]})
    return (p.stdout.decode("utf-8", "replace") if p.returncode == 0 and p.stdout else None), diag


def pdf_context(plain, anchor=r"Netherlands|Dutch", near=r"house price|Herengracht|residential|dwelling|housing", width=220, limit=6):
    """Short contexts around ANCHOR that also mention NEAR; used to read definitions / sources out of documentation PDFs."""
    out, last = [], -10**9
    for m in re.finditer(anchor, plain):
        if m.start() - last < width:
            continue
        ctx = plain[max(0, m.start() - width): m.end() + width]
        if re.search(near, ctx, re.I):
            out.append(ctx)
            last = m.start()
        if len(out) >= limit:
            break
    return out


def parse_median_table(plain):
    """ESB article table 'Prijsontwikkeling bestaande koopwoning YYYY - YYYY (mediaan) (bron: NVM Wonen)': years in a 'Jaar' row, then
    rows 'label n.nnn n.nnn ...'. Heuristic text extraction: a mismatch gives status FORMAT_UNPARSED (not a defect)."""
    m = re.search(r"Prijsontwikkeling bestaande koopwoning[^()]{0,40}\(mediaan\)(?:\s*\(bron:\s*([^)]{1,40})\))?(.{0,1200})", plain)
    if not m:
        return {"status": "HEADING_NOT_FOUND"}
    tail = m.group(2)
    ym = re.search(r"Jaar((?:\s+(?:19|20)\d\d){2,8})", tail)
    if not ym:
        return {"status": "FORMAT_UNPARSED", "reason": "no year row"}
    years = [int(y) for y in ym.group(1).split()]
    n = len(years)
    rows, rejected = {}, []
    for lab, nums in re.findall(r"([A-Z][A-Za-z\- ]{3,30}?)\s+((?:\d{1,3}\.\d{3}(?=\s|$)\s*){%d})" % n, tail[ym.end():]):
        vals = [Decimal(x.replace(".", "")) for x in nums.split()]
        ordered = [v for _, v in sorted(zip(years, vals))]
        if ordered != sorted(ordered):  # plausibility flag only: prices rose in every printed interval; a scrambled row is rejected, never repaired
            rejected.append({"label": lab.strip(), "reason": "NOT_MONOTONE_LIKELY_COLUMN_MISALIGNMENT"})
            continue
        rows.setdefault(lab.strip(), dict(zip(years, vals)))
    if not rows:
        return {"status": "FORMAT_UNPARSED", "reason": "no complete rows", "years": years}
    return {"status": "PARSED", "source_note": (m.group(1) or "").strip(), "years": years, "rows": {k: {str(y): str(v) for y, v in r.items()} for k, r in rows.items()},
            "rejected_rows": rejected,
            "unit_note": "NLG per dwelling as printed (article table); statistic = median; selected years only"}


def parse_year_value_table(text, heading=VM_HEADING, window=7000):
    """Heuristic: after the heading, collect '<year> <value>' pairs until a year repeats. Not strict machine
    parsing: any mismatch yields status FORMAT_UNPARSED with diagnostics, not a defect."""
    m = re.search(heading, text, re.I)
    if not m:
        return {"status": "HEADING_NOT_FOUND"}
    seg = text[m.start(): m.end() + window]
    pairs, seen = [], set()
    for y, v in re.findall(r"(?<!\d)((?:19|20)\d\d)[ \t]+(\d{1,3}(?:[.,]\d{1,2})?)(?![\d.,]*\d)", seg):
        if y in seen:
            break
        seen.add(y)
        pairs.append((int(y), v))
    years = [y for y, _ in pairs]
    if len(pairs) < 10 or years != sorted(years):
        return {"status": "FORMAT_UNPARSED", "pairs_found": len(pairs),
                "heading_context": re.sub(r"\s+", " ", seg[:200])}
    vals = {y: Decimal(v.replace(",", ".")) for y, v in pairs}
    return {"status": "PARSED", "values": vals, "heading": re.sub(r"\s+", " ", seg[:160])}


def summarize_year_table(vals):
    ys = sorted(vals)
    gaps = [y for y in range(ys[0], ys[-1] + 1) if y not in vals]
    anchors = {str(y): str(vals[y]) for y in (1975, 1980, 1985, 1990, 1995, 1999, 2000, 2010, 2023) if y in vals}
    return {"frequency": "A", "first": str(ys[0]), "last": str(ys[-1]), "n_obs": len(ys), "gap_count": len(gaps), "gaps_first5": gaps[:5],
            "years_up_to_1999": year_ranges([y for y in ys if y <= 1999]), "n_obs_1975_1999": sum(1 for y in ys if 1975 <= y <= 1999),
            "anchors": anchors, "unit_class": "LEVEL", "unit_note": "value as printed; table heading says x1000 EUR (per source heading)"}


# ------------------------------------------------------------------ CBS comparison diagnostics
def load_cbs(path):
    """-> {series: {YYYY-MM: Decimal}} from a CSV with columns date,series,value."""
    out = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            out.setdefault(r["series"], {})[r["date"]] = Decimal(r["value"])
    return out


def annual_from_cbs(monthly, mode):
    years = {}
    for k, v in monthly.items():
        years.setdefault(int(k[:4]), {})[int(k[5:7])] = v
    out = {}
    for y, ms in years.items():
        if mode == "mean" and len(ms) == 12:
            out[y] = sum(ms.values()) / 12
        elif mode == "december" and 12 in ms:
            out[y] = ms[12]
    return out


def annualize(parsed, freq):
    """{ordinal: value} -> {year: value}. A as-is; Q/M only complete years: arithmetic mean (labelled derivation)."""
    if freq == "A":
        return dict(parsed)
    per, n = (4, 4) if freq == "Q" else (12, 12)
    buckets = {}
    for o, v in parsed.items():
        buckets.setdefault(o // per, []).append(v)
    return {y: sum(vs) / n for y, vs in buckets.items() if len(vs) == n}


def yoy(annual):
    return {y: (annual[y] / annual[y - 1] - 1) * 100 for y in annual if y - 1 in annual and annual[y - 1] != 0}


def pearson(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sxx * syy).sqrt()


def compare_growth(a, b, label_a, label_b, min_years=3):
    """Year-on-year growth (percent) of two ANNUAL dicts on shared years. Diagnostic only; nothing is linked."""
    ga, gb = yoy(a), yoy(b)
    common = sorted(set(ga) & set(gb))
    if len(common) < min_years:
        return {"compared": f"{label_a} vs {label_b}", "common_growth_years": len(common), "status": "TOO_FEW_COMMON_YEARS"}
    d = [abs(ga[y] - gb[y]) for y in common]
    r = pearson([ga[y] for y in common], [gb[y] for y in common])
    q = Decimal("0.01")
    return {"compared": f"{label_a} vs {label_b}", "common_growth_years": len(common), "first_year": common[0], "last_year": common[-1],
            "mean_abs_diff_pp": str((sum(d) / len(d)).quantize(q)), "max_abs_diff_pp": str(max(d).quantize(q)),
            "same_sign_years": sum(1 for y in common if (ga[y] >= 0) == (gb[y] >= 0)),
            "pearson_r": str(r.quantize(Decimal("0.001"))) if r is not None else None,
            "mean_growth_pp_a": str((sum(ga[y] for y in common) / len(common)).quantize(q)),
            "mean_growth_pp_b": str((sum(gb[y] for y in common) / len(common)).quantize(q))}


def level_ratio(a, b):
    common = sorted(set(a) & set(b))
    if not common:
        return {"common_years": 0}
    ratios = sorted(a[y] / b[y] for y in common)
    q = Decimal("0.001")
    return {"common_years": len(common), "first_year": common[0], "last_year": common[-1],
            "median_ratio": str(ratios[len(ratios) // 2].quantize(q)), "min_ratio": str(ratios[0].quantize(q)), "max_ratio": str(ratios[-1].quantize(q))}


def overlap_with_cbs(key, summ, parsed, freq, cbs):
    """Compare one obtained series with CBS from 2000-01 on. INDEX -> nl_hpi; LEVEL -> nl_house_avg_eur. REAL / RATE / unknown skipped."""
    cls = summ["unit_class"]
    if cls not in ("INDEX", "LEVEL"):
        return {"series": key, "status": "NOT_COMPARED_UNIT_" + cls}
    if summ["real_or_nominal"] == "REAL":
        return {"series": key, "status": "NOT_COMPARED_REAL_SERIES"}
    ann = annualize(parsed, freq)
    ann = {y: v for y, v in ann.items() if y >= 2000}
    out = {"series": key, "status": "COMPARED", "nominal_confirmed": summ["real_or_nominal"] == "NOMINAL", "annualization": "mean of complete years" if freq != "A" else "as published"}
    if cls == "INDEX":
        out["vs_cbs_hpi_annual_mean"] = compare_growth(ann, annual_from_cbs(cbs["nl_hpi"], "mean"), key, "cbs nl_hpi annual mean")
    else:
        out["vs_cbs_avg_annual_mean"] = compare_growth(ann, annual_from_cbs(cbs["nl_house_avg_eur"], "mean"), key, "cbs avg annual mean")
        out["vs_cbs_avg_december"] = compare_growth(ann, annual_from_cbs(cbs["nl_house_avg_eur"], "december"), key, "cbs avg december")
    return out


# ------------------------------------------------------------------ probes
STRONG_LICENCE = r"permitted|not permitted|may not|prohibit|forbid|non-?commercial|commercial|redistribut|toegestaan|zonder .{0,30}toestemming|attribution|CC[ -]?BY"


def licence_quotes(raw, limit=4):
    """Sentences about reuse; sentences with an explicit permission/prohibition term come first."""
    plain = strip_tags(raw.decode("utf-8", "replace"))
    cand = [x for x in re.split(r"(?<=[.!?])\s+", plain) if 30 <= len(x) <= 600 and re.search(LICENCE_KEYWORDS, x, re.I)]
    cand.sort(key=lambda x: 0 if re.search(STRONG_LICENCE, x, re.I) else 1)
    return [x[:280] for x in cand[:limit]]


def ckan_facts(raw):
    try:
        doc = json.loads(raw.decode("utf-8", "replace"))
    except ValueError:
        return {"status": "NOT_JSON"}
    res = doc.get("result") if isinstance(doc, dict) else None
    if not isinstance(res, dict):
        return {"status": "UNEXPECTED_SHAPE"}
    return {"status": "OK", "count": res.get("count"),
            "titles": [str(r.get("title"))[:90] for r in (res.get("results") or [])[:10] if isinstance(r, dict)]}


def run_candidate(sid, results, store, cbs):
    url, fmt, group, kind = CANDIDATES[sid]
    entry = {"source_id": sid, "url": url, "group": group, "kind": kind}
    try:
        raw, rec = hist_02_acquire.fetch(sid)
    except hist_02_acquire.AcquisitionError as exc:
        entry.update({"fetch": "FAILED", "label": "UNREACHABLE", "error": str(exc)[:200], "probe": probe_status(url), "rights_evidence": "NOT_RETRIEVED"})
        results.append(entry)
        return
    entry.update({"fetch": "HTTP_200", "bytes": rec["bytes"], "sha256": rec["sha256"], "label": "REFERENCE_ONLY"})
    if kind == "page":
        entry["page"] = page_facts(raw, DEFINITION_KEYWORDS, r"xlsx|csv|zip|download|data|hp\d{4}|houseprice|\.pdf|licen|terms|copyright")
        plain = strip_tags(raw.decode("utf-8", "replace"))
        entry["nvm_sentences"] = [x[:300] for x in re.split(r"(?<=[.!?])\s+", plain) if "NVM" in x and re.search(r"mediaan|gemiddeld|prijs|gulden|transactie|vraagprijs|verkoop", x, re.I)][:5] if group in ("compilation", "nvm") else []
        q = licence_quotes(raw)
        entry["licence_quotes"] = q
        if sid == "esb-nvm-median":
            mt = parse_median_table(plain)
            entry["median_table"] = mt
            if mt["status"] == "PARSED":
                entry["label"] = "OBTAINED"
        entry["rights_evidence"] = "OFFICIAL_TEXT_READ" if q else "NOT_RETRIEVED"
    elif kind == "ckan":
        entry["ckan"] = ckan_facts(raw)
    elif kind == "dataflow_list":
        entry["dataflows_matching"] = dataflow_names(raw, r"house|dwelling|property|residential|price", 25)
    elif kind == "pdf_text":
        text, diag = pdf_to_text(raw)
        focus = PDF_FOCUS.get(sid, {})
        if text is None:
            entry["text"] = {"status": "PDFTOTEXT_UNAVAILABLE_OR_FAILED", "diag": diag}
        else:
            plain = re.sub(r"\s+", " ", text)
            sents = [x[:300] for x in re.split(r"(?<=[.!?])\s+", plain) if re.search(PDF_SENTENCE_RE, x, re.I)]
            entry["text"] = {"status": "OK", "chars": len(plain), "contexts": pdf_context(plain, **focus), "matching_sentences": sents[:4]}
    elif kind == "pdf_table":
        text, diag = pdf_to_text(raw)
        if text is None:
            entry["table"] = {"status": "NOT_A_PDF_RESPONSE" if not raw.startswith(b"%PDF") else "PDFTOTEXT_FAILED", "diag": diag}
        else:
            entry["pdf_text_chars"] = len(text)
            tab = parse_year_value_table(text)
            if tab["status"] == "PARSED":
                vals = tab.pop("values")
                entry["table"] = {"status": "PARSED", "heading": tab["heading"], "summary": summarize_year_table(vals)}
                entry["label"] = "OBTAINED"
                store[sid] = ({y: v for y, v in vals.items()}, "A", {"unit_class": "LEVEL", "real_or_nominal": "UNSPECIFIED"})
                if cbs:
                    scale = {y: v * 1000 for y, v in vals.items()}  # heading says x1000 EUR: labelled unit conversion
                    ov = {"series": sid, "status": "COMPARED", "unit_conversion": "x1000 per source heading"}
                    ov["vs_cbs_avg_annual_mean"] = compare_growth({y: v for y, v in scale.items() if y >= 2000}, annual_from_cbs(cbs["nl_house_avg_eur"], "mean"), sid, "cbs avg annual mean")
                    ov["vs_cbs_avg_december"] = compare_growth({y: v for y, v in scale.items() if y >= 2000}, annual_from_cbs(cbs["nl_house_avg_eur"], "december"), sid, "cbs avg december")
                    ov["level_ratio_vs_cbs_annual_mean"] = level_ratio({y: v for y, v in scale.items() if y >= 2000}, annual_from_cbs(cbs["nl_house_avg_eur"], "mean"))
                    ov["level_ratio_vs_cbs_december"] = level_ratio({y: v for y, v in scale.items() if y >= 2000}, annual_from_cbs(cbs["nl_house_avg_eur"], "december"))
                    entry["overlap_vs_cbs"] = [ov]
            else:
                if tab["status"] == "HEADING_NOT_FOUND":
                    tab["lines_with_1975"] = [re.sub(r"\s+", " ", ln)[:90] for ln in text.splitlines() if "1975" in ln][:4]
                    tab["lines_with_verkoopprijs"] = [re.sub(r"\s+", " ", ln)[:90] for ln in text.splitlines() if re.search("verkoopprijs", ln, re.I)][:4]
                entry["table"] = tab
        entry["rights_evidence"] = "NOT_RETRIEVED"
    else:  # sdmx_csv / sdmx_zip / xlsx: strict machine parsing, defects propagate
        if kind == "sdmx_csv":
            scan = scan_csv_bytes(raw) if raw.lstrip()[:1] != b"<" else None
            if scan is None:
                entry["format_unparsed"] = "XML_OR_HTML_BODY " + re.sub(r"\s+", " ", raw[:160].decode("utf-8", "replace"))
        elif kind == "sdmx_zip":
            scan = scan_zip_bytes(raw)
        elif kind == "xlsx_panel":
            scan = scan_xlsx_panel(raw)
        else:
            scan = scan_xlsx_country(raw)
        if scan:
            parsed_store = scan.pop("_parsed")
            entry["scan"] = scan
            if scan["nl_series_count"]:
                entry["label"] = "OBTAINED"
            if cbs:
                entry["overlap_vs_cbs"] = []
                for i, (parsed, freq, attrs) in parsed_store.items():
                    summ = scan["nl_series"][i] if i < len(scan["nl_series"]) else None
                    if summ:
                        entry["overlap_vs_cbs"].append(overlap_with_cbs(f"{sid}#{i}", summ, parsed, freq, cbs))
            for i, v in parsed_store.items():
                store[f"{sid}#{i}"] = v
        entry["rights_evidence"] = "NOT_RETRIEVED"
    results.append(entry)


def coverage_matrix(results):
    """Per obtained series: years up to 1999 and measure class (level vs index), for the 1900-1999 matrix."""
    rows = []
    for r in results:
        if r.get("label") != "OBTAINED":
            continue
        mt = r.get("median_table")
        if mt and mt.get("status") == "PARSED":
            for lab, vals in mt["rows"].items():
                ys = sorted(int(y) for y in vals)
                rows.append({"source_id": r["source_id"], "series": lab, "unit_class": "LEVEL", "frequency": "A (selected years)", "first": str(ys[0]), "last": str(ys[-1]),
                             "years_up_to_1999": [str(y) for y in ys if y <= 1999], "real_or_nominal": "UNSPECIFIED"})
            continue
        if r["kind"] == "pdf_table":
            s = r["table"]["summary"]
            rows.append({"source_id": r["source_id"], "series": "table", "unit_class": s["unit_class"], "frequency": s["frequency"],
                         "first": s["first"], "last": s["last"], "years_up_to_1999": s["years_up_to_1999"], "real_or_nominal": "UNSPECIFIED"})
            continue
        for i, s in enumerate(r.get("scan", {}).get("nl_series", [])):
            rows.append({"source_id": r["source_id"], "series": i, "unit_class": s["unit_class"], "base_period": s["base_period"],
                         "frequency": s["frequency"], "first": s["first"], "last": s["last"], "n_obs_1975_1999": s["n_obs_1975_1999"],
                         "years_up_to_1999": s["years_up_to_1999"], "real_or_nominal": s["real_or_nominal"]})
    return rows


def digest(doc):
    """Compact one-line-per-fact view of a summary (aggregates only), for CI logs."""
    lines = [f"STATUS {doc['status']} missing={doc['missing_sources']} defects={doc['defects']}"]
    for r in doc["results"]:
        head = {k: r.get(k) for k in ("source_id", "fetch", "label", "bytes", "sha256", "rights_evidence", "defect")}
        err = r.get("error")
        if err:
            head["error"] = err[:60]
            head["probe"] = {k: v for k, v in (r.get("probe") or {}).items() if k in ("status", "location_host", "location_path")}
        lines.append("SRC " + json.dumps(head, sort_keys=True, separators=(",", ":")))
        for q in r.get("nvm_sentences", [])[:5]:
            lines.append("  NVMSENT " + q[:300])
        for q in r.get("licence_quotes", [])[:3]:
            lines.append("  QUOTE " + q[:260])
        pg = r.get("page")
        if pg:
            lines.append("  PAGE " + json.dumps({"title": pg.get("title"), "links": pg.get("links", [])[:12]}, separators=(",", ":"))[:700])
        for c in (r.get("text") or {}).get("contexts", []):
            lines.append("  CTX " + c[:1300])
        for k in ("ckan", "median_table", "table", "text", "dataflows_matching", "format_unparsed", "pdf_text_chars"):
            if k in r:
                lines.append(f"  {k.upper()} " + json.dumps(r[k], sort_keys=True, separators=(",", ":"))[:900])
        sc = r.get("scan")
        if sc:
            lines.append("  SCAN " + json.dumps({k: sc.get(k) for k in ("layout", "rows_scanned", "nl_series_count", "sheet_names", "zip_member", "variables_scanned")}, separators=(",", ":"))[:500])
            for i, s_ in enumerate(sc["nl_series"]):
                keys = ("frequency", "first", "last", "n_obs", "missing_markers", "gap_count", "unit_class", "base_period", "real_or_nominal", "first_value", "last_value", "n_obs_1975_1999", "years_up_to_1999")
                lines.append(f"  S{i} " + json.dumps({"attrs": s_["attrs"], **{k: s_[k] for k in keys}}, sort_keys=True, separators=(",", ":"))[:800])
        for ov in r.get("overlap_vs_cbs", []):
            if ov.get("status") == "COMPARED":
                lines.append("  OVERLAP " + json.dumps(ov, sort_keys=True, separators=(",", ":"))[:1200])
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--digest", help="print a compact digest of an existing summary JSON and exit")
    ap.add_argument("--summary-out")
    ap.add_argument("--cbs-csv", help="read-only CBS baseline CSV (date,series,value) for overlap diagnostics")
    ap.add_argument("--only", action="append", choices=sorted(CANDIDATES))
    args = ap.parse_args(argv)
    if args.digest:
        print("\n".join(digest(json.loads(Path(args.digest).read_text()))))
        return 0
    if not args.summary_out:
        ap.error("--summary-out is required")
    cbs = load_cbs(args.cbs_csv) if args.cbs_csv else None
    results, store, defects = [], {}, []
    for sid in (args.only or list(CANDIDATES)):
        try:
            run_candidate(sid, results, store, cbs)
        except HousingSourceError as exc:
            defects.append({"source_id": sid, "defect": str(exc)[:300]})
            results.append({"source_id": sid, "fetch": "HTTP_200", "label": "DEFECT", "defect": str(exc)[:300]})
        print(json.dumps({sid: {k: results[-1].get(k) for k in ("fetch", "label", "bytes", "sha256", "defect", "error")}}, sort_keys=True), flush=True)
    missing = [r["source_id"] for r in results if r.get("label") == "UNREACHABLE"]
    summary = {"status": "PARTIAL" if missing else "COMPLETE", "missing_sources": missing, "publication_authorized": False, "source_approved": False,
               "rights_status": "UNVERIFIED", "results": results, "references_only": REFERENCES,
               "coverage_matrix": coverage_matrix(results), "defects": defects,
               "cbs_baseline_used": bool(cbs)}
    out = Path(args.summary_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: summary[k] for k in ("status", "missing_sources", "defects")}, sort_keys=True))
    return 1 if defects else 0


if __name__ == "__main__":
    sys.exit(main())
