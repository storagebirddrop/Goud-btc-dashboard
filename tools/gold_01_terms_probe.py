"""GOLD-01 rights workstream, research only: probe OFFICIAL terms pages and the World Bank Pink Sheet workbook notes.

Nothing here is legal advice, nothing is approved, no public file or ADR is touched. The probe records METADATA ONLY
per source: exact URL, HTTP status, sha256, byte count, evidence level and short verbatim quotes (<= 25 words each,
at most MAX_QUOTES per source). Whole third-party pages or sheets are never stored; raw bytes stay in memory.

Evidence levels: OFFICIAL_TEXT_READ (official bytes retrieved and parsed here) or NOT_RETRIEVED. SECONDARY_ONLY is only
assigned by hand in the report. Fail closed: unreachable sources (DNS/TLS/timeout/HTTP status/redirect off the exact URL)
land in `missing_sources` and the exit code stays 0; a retrieved body of the wrong kind (content mismatch), too large,
empty or a quote above the word limit is a real defect (GoldTermsError, exit 1).
Acquisition reuses tools.hist_02_acquire.fetch (exact-URL allowlist, 15 MB cap, sha256).
"""
import argparse
import io
import json
import re
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from tools import hist_02_acquire

RETRIEVAL_DATE = "2026-10-20"
MAX_QUOTE_WORDS = 25
MAX_QUOTES = 30
QUOTES_PER_TOPIC = 2
SPREAD = 300
MAX_PAGE_BYTES = 6_000_000
WORKBOOK_ID = "world-bank-gold-history"
DATA_SHEET = "Monthly Prices"
NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}

# id -> (url, format, group). Exact URLs only (hist_02_acquire allowlist); a redirect is reported, never followed.
PAGES = {
    "wb-dataset-terms": ("https://www.worldbank.org/ext/en/legal/terms-conditions/datasets", "html", "wb"),
    "wb-summary-terms": ("https://data.worldbank.org/summary-terms-of-use", "html", "wb"),
    "wb-commodity-markets": ("https://www.worldbank.org/en/research/commodity-markets", "html", "wb"),
    "wb-permissions": ("https://www.worldbank.org/en/about/legal/permissions", "html", "wb"),
    "wb-pink-sheet-2025-06": ("https://thedocs.worldbank.org/en/doc/18675f1d1639c7a34d463f59263ba0a2-0050012025/related/CMO-Pink-Sheet-June-2025.pdf", "pdf", "wb"),
    "ice-iba-lbma": ("https://www.ice.com/iba/lbma-precious-metals", "html", "iba"),
    "ecb-fx-framework": ("https://www.ecb.europa.eu/stats/pdf/exchange/Frameworkfortheeuroforeignexchangereferencerates.en.pdf", "pdf", "ecb"),
    "ice-iba-about":("https://www.ice.com/iba/about", "html", "iba"),
    "ice-iba-fee-schedule-2026": ("https://www.ice.com/publicdocs/IBA_MLA_Licensing_Data_Fee_Schedule_2026.pdf", "pdf", "iba"),
    "lbma-prices-data": ("https://www.lbma.org.uk/prices-and-data/lbma-precious-metal-prices", "html", "lbma"),
    "lbma-tables-moving": ("https://www.lbma.org.uk/articles/lbma-benchmark-prices-data-tables-are-moving", "html", "lbma"),
    "lbma-gold-price": ("https://www.lbma.org.uk/prices-and-data/lbma-gold-price", "html", "lbma"),
    "ecb-usage-policy": ("https://www.ecb.europa.eu/stats/ecb_statistics/governance_and_quality_framework/html/usage_policy.en.html", "html", "ecb"),
    "ecb-disclaimer": ("https://www.ecb.europa.eu/services/using-our-site/disclaimer/html/index.en.html", "html", "ecb"),
    "ecb-eurofxref": ("https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html", "html", "ecb"),
    "ecb-exr-dataset": ("https://data.ecb.europa.eu/data/datasets/EXR/EXR.D.USD.EUR.SP00.A", "html", "ecb"),
    "cbs-copyright-en": ("https://www.cbs.nl/en-gb/about-us/website/copyright", "html", "cbs"),
    "cbs-copyright-nl": ("https://www.cbs.nl/nl-nl/over-ons/website/copyright", "html", "cbs"),
    "cbs-85773-page": ("https://www.cbs.nl/nl-nl/cijfers/detail/85773NED", "html", "cbs"),
}
hist_02_acquire.SOURCES.update({k: (v[0], v[1]) for k, v in PAGES.items()})
ALL_IDS = [WORKBOOK_ID] + list(PAGES)

# topic -> regex; first match per topic yields at most one <= 25-word quote.
TOPICS = {
    "wb": {"default_licence": r"Creative Commons Attribution 4\.0", "labelled_otherwise": r"labell?ed otherwise",
           "third_party_consent": r"consent of the original|original data provider|provided by third parties|third[- ]party (data|content|material)",
           "attribution_format": r"Dataset name|Data source \(if|attribution should|When you download or use",
           "changes": r"indicate (if )?changes|changes were made|you (modify|adapt)|derivative",
           "endorsement": r"endors", "no_warranty": r"infring|warrant|as is\b",
           "third_party_tail": r"(?<=without the consent of the original data provider, )\S",
           "free_to": r"free to copy, distribute, adapt",
           "data_sources_note": r"Prospects Group|data (is|are) (sourced|obtained|compiled)|sources? (of|for) (the )?(data|prices)",
           "contact": r"pubrights|permissions@|data@worldbank",
           "pdf_rights": r"licen[cs]e|copyright|permission|Creative Commons|terms of use|redistribut",
           "terms_pointer": r"Terms of Use|terms and conditions|copyright",
           "gold_source": r"\bgold\b.{0,120}(LBMA|London|fixing|spot)|(LBMA|London|fixing).{0,120}\bgold\b"},
    "iba": {"derived": r"derived (benchmark|indices|index)", "derived_definition": r"derived benchmark(s)? (is|are|means|licen[cs]e)|Derived Benchmark Licen[cs]e",
            "lbma_user_scope": r"(?<=Schedule J\) )\S", "lbma_user_scope_tail": r"(?<=new or historical LBMA Gold Price, LBMA )\S",
            "derived_index_licence": r"Derived Index Licen[cs]e", "derived_index_tail": r"(?<=Derived Index Licence\. )\S", "derived_index_any": r"derived index", "derived_lbma": r"LBMA.{0,100}derived|derived.{0,100}LBMA",
            "derived_scope": r"derived .{0,60}(index|indices|benchmark).{0,80}(LBMA|based on|calculated|created)", "redistribution": r"redistribut", "usage_licence": r"usage licen[cs]e|licen[cs]e from IBA|available under licen[cs]e",
            "historical_access": r"historical (access|data)", "lbma_gold_price": r"LBMA Gold Price",
            "reserves_rights": r"reserves all rights|all rights", "non_commercial": r"non-commercial|educational|internal use|personal use",
            "contact": r"IBA-Licensing|contact us"},
    "lbma": {"historic_tables": r"histor", "licence": r"licen[cs]e", "portal": r"members?[' ]*(area|portal)|portal|self-certif", "iba": r"\bIBA\b|ICE Benchmark",
             "derived": r"derived", "redistribution": r"redistribut|republish", "non_commercial": r"non-commercial|educational"},
    "ecb": {"free_reuse": r"free reuse regarding|policy of free", "source_condition": r"Source: ECB|source is (acknowledged|cited|mentioned|stated)|acknowledg",
            "additional_rules": r"(?<=additional rules apply: )\S", "disclaimer_conditions": r"(?<=following conditions: )\S", "accuracy": r"accurate",
            "source_example": r"\(e\.g\. .{0,3}Source", "conditions": r"provided that|on condition that|as long as|subject to", "reproduction": r"reproduc", "dataset_modification": r"Modification of original data",
            "not_modified": r"not (been )?(modified|altered)|are not modified|distort", "information_only": r"information purposes",
            "commercial": r"commercial", "third_party": r"third[- ]part(y|ies) (data|content|material)|originator",
            "user_modification": r"modified by the user|calculation of growth rates|stated explicitly",
            "copyright": r"copyright|©|licen[cs]e"},
    "cbs": {"reproduction": r"reproduc|verveelvoudig|overnemen", "source": r"bronvermelding|sourced from CBS|state that the data", "licence": r"CC[ -]?BY|Creative Commons",
            "exception": r"covered by copyright|not permitted|niet toegestaan"},
}
WORKBOOK_TOPICS = {"gold_row_tail2": r"(?<=London Bullion Market; )\S", "gold_row_tail": r"(?<=London afternoon fixing, average of daily rates \| )\S", "gold_definition": r"\bgold\b", "gold_provider": r"\bgold\b.{0,200}(LBMA|London|Reuters|\bICE\b|\bIBA\b|Platts|Metal Bulletin|fixing|spot)",
                   "rights": r"licen[cs]e|copyright|terms of use|attribut|third[- ]part|permission|reproduc|redistribut|citation|creative commons|CC BY",
                   "source_line": r"Source:|Notes?:"}
UNREACHABLE_PREFIXES = ("NETWORK_", "TLS_ERROR", "DNS_ERROR", "HTTP_STATUS_ERROR", "UNEXPECTED_HTTP_STATUS")


class GoldTermsError(ValueError):
    """Real defect (content mismatch, size, quote above limit, malformed workbook). Never raised for unreachability."""


# ---------------------------------------------------------------- text helpers
def strip_tags(html):
    t = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&quot;", '"'), ("&#39;", "'"), ("&rsquo;", "'"), ("&lsquo;", "'"), ("&ldquo;", '"'), ("&rdquo;", '"')):
        t = t.replace(a, b)
    return re.sub(r"\s+", " ", t).strip()


def enforce_quote_limit(quote):
    if len(quote.split()) > MAX_QUOTE_WORDS:
        raise GoldTermsError("QUOTE_TOO_LONG")
    return quote


def _window(text, pos):
    before = len(text[:pos].split())
    words = text.split()
    start = max(0, before - 12)
    for j in range(before - 1, max(-1, before - 13), -1):
        if j >= 0 and re.search(r"[.!?:;]$", words[j]):
            start = j + 1
            break
    if before >= start + MAX_QUOTE_WORDS:  # match fell outside the window: re-centre on the match
        start = before
    return enforce_quote_limit(" ".join(words[start:start + MAX_QUOTE_WORDS]))


def short_quote(text, pattern, nth=0):
    """nth match of `pattern` (matches closer than SPREAD chars to the previous kept one are skipped) -> verbatim window of
    <= MAX_QUOTE_WORDS words aligned to a sentence start when possible. None when there is no such match (NOT_RETRIEVED)."""
    last, kept = -10**9, 0
    for m in re.finditer(pattern, text, re.I | re.S):
        if m.start() - last < SPREAD:
            continue
        if kept == nth:
            return _window(text, m.start())
        kept, last = kept + 1, m.start()
    return None


def quotes_for(text, topics):
    out, n = [], 0
    for topic, pat in topics.items():
        for nth in range(QUOTES_PER_TOPIC):
            q = short_quote(text, pat, nth)
            if q is None:
                if nth == 0:
                    out.append({"topic": topic, "quote": "NOT_RETRIEVED"})
                break
            if n >= MAX_QUOTES:
                out.append({"topic": topic, "quote": "OMITTED_QUOTE_CAP"})
                break
            out.append({"topic": topic, "quote": q})
            n += 1
    return out


# ---------------------------------------------------------------- content validation
def check_content(kind, raw):
    """Wrong kind of body or oversize page => GoldTermsError (a real defect, not unreachability)."""
    if not raw:
        raise GoldTermsError("EMPTY_SOURCE")
    if kind == "html":
        if len(raw) > MAX_PAGE_BYTES:
            raise GoldTermsError("PAGE_TOO_LARGE")
        head = raw[:4000].decode("utf-8", "replace").lower()
        if raw[:4] in (b"%PDF", b"PK\x03\x04") or "<" not in head or not re.search(r"<(!doctype|html|head|body|div|p|title)", head):
            raise GoldTermsError("UNEXPECTED_CONTENT_TYPE html")
    elif kind == "pdf":
        if raw[:5] != b"%PDF-":
            raise GoldTermsError("UNEXPECTED_CONTENT_TYPE pdf")
    elif kind == "xlsx":
        if raw[:4] != b"PK\x03\x04":
            raise GoldTermsError("UNEXPECTED_CONTENT_TYPE xlsx")
    else:
        raise GoldTermsError("UNKNOWN_KIND")


def pdf_to_text(raw):
    try:
        p = subprocess.run(["pdftotext", "-layout", "-", "-"], input=raw, capture_output=True, timeout=60, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if p.returncode != 0 or not p.stdout:
        return None
    return re.sub(r"\s+", " ", re.sub(r"[.…]{4,}", " ", p.stdout.decode("utf-8", "replace"))).strip()


# ---------------------------------------------------------------- workbook (all sheets, notes only)
def _shared(z):
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    root = ET.fromstring(z.read("xl/sharedStrings.xml"))
    return ["".join(t.text or "" for t in si.findall(".//x:t", NS)) for si in root.findall("x:si", NS)]


def workbook_sheets(raw):
    """-> list of (name, [row texts]) for EVERY sheet; text cells only (numbers kept as text, capped by caller)."""
    try:
        z = zipfile.ZipFile(io.BytesIO(raw))
        shared = _shared(z)
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        targets = {x.attrib["Id"]: x.attrib["Target"] for x in rels}
        out = []
        for s in wb.findall(".//x:sheets/x:sheet", NS):
            tgt = targets[s.attrib["{" + NS["r"] + "}id"]].lstrip("/")
            root = ET.fromstring(z.read(tgt if tgt.startswith("xl/") else "xl/" + tgt))
            rows = []
            for row in root.findall(".//x:sheetData/x:row", NS):
                cells = []
                for c in row.findall("x:c", NS):
                    v, inl = c.find("x:v", NS), c.find("x:is", NS)
                    val = (v.text or "") if v is not None else ("".join(t.text or "" for t in inl.findall(".//x:t", NS)) if inl is not None else "")
                    if c.attrib.get("t") == "s" and val:
                        val = shared[int(val)]
                    if val.strip():
                        cells.append(val.strip())
                if cells:
                    rows.append(" | ".join(cells))
            out.append((s.attrib["name"], rows))
        return out
    except (zipfile.BadZipFile, KeyError, ET.ParseError, ValueError, IndexError) as exc:
        raise GoldTermsError(f"WORKBOOK_NOT_PARSEABLE {type(exc).__name__}") from exc


def analyse_workbook(raw):
    sheets = workbook_sheets(raw)
    names = [n for n, _ in sheets]
    out = {"sheet_names": names, "data_sheet_present": DATA_SHEET in names, "notes_sheets": []}
    for name, rows in sheets:
        if name == DATA_SHEET:
            cells = [c for r in rows[:12] for c in r.split(" | ")]
            # header cells only (never the price rows): cells naming gold, and whether a troy-oz unit appears in the header block
            out["data_sheet_gold_header"] = [enforce_quote_limit(" ".join(c.split()[:MAX_QUOTE_WORDS])) for c in cells if re.match(r"gold", c, re.I)][:3] or "NOT_RETRIEVED"
            out["data_sheet_troy_oz_unit_in_header"] = any(re.search(r"troy\s*oz", c, re.I) for c in cells)
            out["data_sheet_footer_quotes"] = quotes_for(re.sub(r"\s+", " ", " ".join(r for r in rows[-15:] if re.search(r"[A-Za-z]{5}", r))), {"footer": r"Source|Note|World Bank|licen[cs]e"})
            continue
        text = re.sub(r"\s+", " ", " ".join(rows))
        out["notes_sheets"].append({"sheet": name, "rows": len(rows), "text_chars": len(text), "quotes": quotes_for(text, WORKBOOK_TOPICS)})
    return out


# ---------------------------------------------------------------- redirect locator (metadata only)
class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def locate(url):
    """Status and Location of the first response WITHOUT following it. Only called for allowlisted exact URLs."""
    try:
        build_opener(_NoRedirect()).open(Request(url, headers={"User-Agent": "Goud-btc-dashboard/GOLD-01 research"}), timeout=20).close()
        return {"status": 200}
    except HTTPError as exc:
        return {"status": exc.code, "location": exc.headers.get("Location")}
    except (OSError, URLError):
        return {"status": None}


# ---------------------------------------------------------------- probe
def probe_one(source, fetcher, locator=None):
    """-> (record or None, missing or None). Unreachable => missing (exit 0); defects raise."""
    kind = hist_02_acquire.SOURCES[source][1]
    group = PAGES[source][2] if source in PAGES else "wb"
    try:
        raw, rec = fetcher(source)
    except hist_02_acquire.AcquisitionError as exc:
        msg = str(exc)
        if msg.startswith("UNAUTHORIZED_ENDPOINT_OR_REDIRECT"):
            info = (locator or (lambda u: {}))(hist_02_acquire.SOURCES[source][0])
            return None, {"source_id": source, "reason": "REDIRECT_OFF_EXACT_URL", "redirect": info}
        if msg.startswith(UNREACHABLE_PREFIXES):
            return None, {"source_id": source, "reason": msg.split(" ")[0]}
        raise GoldTermsError(msg) from exc
    check_content(kind, raw)
    record = {"source_id": source, "url": rec["url"], "http_status": rec["http_status"], "sha256": rec["sha256"], "bytes": rec["bytes"],
              "format": kind, "retrieval_date": RETRIEVAL_DATE}
    if kind == "xlsx":
        record["workbook"] = analyse_workbook(raw)
        record["evidence_level"] = "OFFICIAL_TEXT_READ"
        return record, None
    text = strip_tags(raw.decode("utf-8", "replace")) if kind == "html" else pdf_to_text(raw)
    if not text:
        return None, {"source_id": source, "reason": "NO_TEXT_EXTRACTED"}
    record["text_chars"] = len(text)
    record["quotes"] = quotes_for(text, TOPICS[group])
    record["evidence_level"] = "OFFICIAL_TEXT_READ"
    return record, None


def run_probe(sources=None, fetcher=None, locator=locate):
    fetcher = fetcher or hist_02_acquire.fetch
    summary = {"status": "RESEARCH_ONLY_NOTHING_APPROVED", "legal_advice": False, "retrieval_date": RETRIEVAL_DATE,
               "run_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "sources": [], "missing_sources": []}
    for source in (sources or ALL_IDS):
        rec, missing = probe_one(source, fetcher, locator)
        if rec:
            summary["sources"].append(rec)
        else:
            summary["missing_sources"].append(missing)
        print(json.dumps({"source": source, "retrieved": bool(rec), "missing": missing}, sort_keys=True), flush=True)
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary-out", required=True)
    ap.add_argument("--source", action="append", choices=ALL_IDS)
    args = ap.parse_args(argv)
    try:
        summary = run_probe(args.source)
    except GoldTermsError as exc:
        print("GOLD_TERMS_PROBE_DEFECT " + str(exc), file=sys.stderr)
        return 1
    Path(args.summary_out).write_text(json.dumps(summary, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"retrieved": len(summary["sources"]), "missing": len(summary["missing_sources"])}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
