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
MAX_QUOTES = 8
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
    "ice-iba-about": ("https://www.ice.com/iba/about", "html", "iba"),
    "ice-iba-fee-schedule-2026": ("https://www.ice.com/publicdocs/IBA_MLA_Licensing_Data_Fee_Schedule_2026.pdf", "pdf", "iba"),
    "lbma-prices-data": ("https://www.lbma.org.uk/prices-and-data/precious-metal-prices", "html", "lbma"),
    "lbma-gold-price": ("https://www.lbma.org.uk/prices-and-data/lbma-gold-price", "html", "lbma"),
    "lbma-terms": ("https://www.lbma.org.uk/terms-and-conditions", "html", "lbma"),
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
    "wb": {"default_licence": r"Creative Commons Attribution 4\.0|CC BY 4\.0", "labelled_otherwise": r"labell?ed otherwise|specifically labell?ed|unless otherwise",
           "third_party": r"third[- ]part(y|ies)", "attribution": r"attribut", "modification": r"modif|adapt|derivative",
           "endorsement": r"endors", "gold_source": r"\bgold\b.{0,80}(LBMA|London|fixing|spot)|(LBMA|London|fixing).{0,80}\bgold\b"},
    "iba": {"derived": r"derived", "redistribution": r"redistribut", "licence": r"licen[cs]", "historical": r"histor",
            "lbma_gold_price": r"LBMA Gold Price", "third_party": r"third[- ]part(y|ies)"},
    "lbma": {"historic": r"histor", "licence": r"licen[cs]", "portal": r"members?[' ]*(area|portal)|portal", "iba": r"\bIBA\b|ICE Benchmark",
             "derived": r"derived", "redistribution": r"redistribut|republish"},
    "ecb": {"reuse": r"re-?us|reproduc", "source": r"acknowledg|credit|source", "information_only": r"information purposes",
            "commercial": r"commercial", "third_party": r"third[- ]part(y|ies)", "alteration": r"alter|modif|distort|own calculation"},
    "cbs": {"reproduction": r"reproduc|verveelvoudig|overnemen", "source": r"bronvermelding|source", "licence": r"CC[ -]?BY|Creative Commons|licen[cs]"},
}
WORKBOOK_TOPICS = {"gold": r"\bgold\b", "provider": r"LBMA|London|Reuters|\bICE\b|\bIBA\b|Platts|Metal Bulletin|fixing|spot",
                   "rights": r"licen[cs]|copyright|terms of use|attribut|third[- ]part|permission|reproduc|redistribut|cite|citation|source"}
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


def short_quote(text, pattern):
    """First match of `pattern` -> verbatim window of <= MAX_QUOTE_WORDS words, aligned to a sentence start when possible.
    None when there is no match (NOT_RETRIEVED)."""
    m = re.search(pattern, text, re.I | re.S)
    if not m:
        return None
    before = len(text[:m.start()].split())
    words = text.split()
    start = max(0, before - 4)
    for j in range(before - 1, max(-1, before - 11), -1):
        if j >= 0 and re.search(r"[.!?:;]$", words[j]):
            start = j + 1
            break
    window = words[start:start + MAX_QUOTE_WORDS]
    if before >= start + MAX_QUOTE_WORDS:  # match fell outside the window: re-centre on the match
        window = words[before:before + MAX_QUOTE_WORDS]
    return enforce_quote_limit(" ".join(window))


def quotes_for(text, topics):
    out = []
    for topic, pat in topics.items():
        q = short_quote(text, pat)
        out.append({"topic": topic, "quote": q if q else "NOT_RETRIEVED"})
    found = [q for q in out if q["quote"] != "NOT_RETRIEVED"]
    return out if len(found) <= MAX_QUOTES else _cap(out)


def _cap(quotes):
    kept, n = [], 0
    for q in quotes:
        if q["quote"] == "NOT_RETRIEVED":
            kept.append(q)
        elif n < MAX_QUOTES:
            kept.append(q)
            n += 1
        else:
            kept.append({"topic": q["topic"], "quote": "OMITTED_QUOTE_CAP"})
    return kept


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
    return re.sub(r"\s+", " ", p.stdout.decode("utf-8", "replace")).strip() if p.returncode == 0 and p.stdout else None


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
            head = [r for r in rows[:12] if re.search(r"gold", r, re.I)]
            # only the header cell(s) naming gold, shortened; never the price rows
            out["data_sheet_gold_header"] = [enforce_quote_limit(" ".join(h.split()[:MAX_QUOTE_WORDS])) for h in head[:2]] or "NOT_RETRIEVED"
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
