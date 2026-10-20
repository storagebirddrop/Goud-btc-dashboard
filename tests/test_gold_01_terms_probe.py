"""GOLD-01 terms probe: offline tests with SYNTHETIC fixtures (prove parser/fail-closed code only, no legal facts)."""
import io
import json
import zipfile

import pytest

from tools import gold_01_terms_probe as m
from tools import hist_02_acquire as acq

HTML = ("<html><head><title>t</title><style>x{}</style></head><body><script>var a=1;</script>"
        "<p>Intro. Unless specifically labeled otherwise, these datasets are provided under CC BY 4.0 licence. "
        "Third party data may need consent of the provider.</p></body></html>")


def _fetch_for(raw, status=200):
    def f(source):
        return raw, {"source_id": source, "url": acq.SOURCES[source][0], "sha256": "0" * 64, "bytes": len(raw), "http_status": status}
    return f


def _raising(msg):
    def f(source):
        raise acq.AcquisitionError(msg)
    return f


def _xlsx(sheets):
    """sheets: {name: [[cell strings]]} inline-string workbook."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        wb = "".join(f'<sheet name="{n}" sheetId="{i}" r:id="rId{i}"/>' for i, n in enumerate(sheets, 1))
        z.writestr("xl/workbook.xml", f'<workbook xmlns="{m.NS["x"]}" xmlns:r="{m.NS["r"]}"><sheets>{wb}</sheets></workbook>')
        rel = "".join(f'<Relationship Id="rId{i}" Target="worksheets/s{i}.xml"/>' for i in range(1, len(sheets) + 1))
        z.writestr("xl/_rels/workbook.xml.rels", f"<Relationships>{rel}</Relationships>")
        for i, rows in enumerate(sheets.values(), 1):
            body = "".join("<row>" + "".join(f'<c r="A1" t="inlineStr"><is><t>{c}</t></is></c>' for c in r) + "</row>" for r in rows)
            z.writestr(f"xl/worksheets/s{i}.xml", f'<worksheet xmlns="{m.NS["x"]}"><sheetData>{body}</sheetData></worksheet>')
    return buf.getvalue()


def test_registered_exact_https_urls():
    assert m.WORKBOOK_ID in acq.SOURCES
    for sid, (url, _, group) in m.PAGES.items():
        assert url.startswith("https://") and acq.SOURCES[sid][0] == url and group in m.TOPICS
        acq.validate_url(sid, url)
    with pytest.raises(acq.AcquisitionError):
        acq.validate_url("wb-dataset-terms", "https://example.org/x")


def test_strip_tags_removes_script_and_style():
    t = m.strip_tags(HTML)
    assert "var a" not in t and "x{}" not in t and "CC BY 4.0" in t


def test_quote_is_verbatim_and_within_limit():
    long_text = "Alpha. " + " ".join(f"w{i}" for i in range(80)) + " licence " + " ".join(f"z{i}" for i in range(80))
    q = m.short_quote(long_text, r"licence")
    assert q and len(q.split()) <= m.MAX_QUOTE_WORDS and "licence" in q and q in long_text


def test_quote_missing_is_none_and_not_retrieved():
    assert m.short_quote("nothing here", r"CC BY") is None
    assert m.quotes_for("nothing here", {"a": r"CC BY"}) == [{"topic": "a", "quote": "NOT_RETRIEVED"}]


def test_quote_limit_enforced():
    with pytest.raises(m.GoldTermsError, match="QUOTE_TOO_LONG"):
        m.enforce_quote_limit(" ".join(["w"] * 26))
    assert m.enforce_quote_limit(" ".join(["w"] * 25))


def test_every_quote_from_page_is_short():
    rec, missing = m.probe_one("wb-dataset-terms", _fetch_for(HTML.encode()))
    assert missing is None and rec["evidence_level"] == "OFFICIAL_TEXT_READ"
    got = {q["topic"]: q["quote"] for q in rec["quotes"]}
    assert "CC BY 4.0" in got["default_licence"] and got["endorsement"] == "NOT_RETRIEVED"
    assert all(len(q["quote"].split()) <= m.MAX_QUOTE_WORDS for q in rec["quotes"])
    assert "var a" not in json.dumps(rec)


def test_quote_cap_per_source():
    topics = {f"t{i}": r"word" for i in range(12)}
    qs = m.quotes_for("a word here", topics)
    assert sum(1 for q in qs if q["quote"] not in ("NOT_RETRIEVED", "OMITTED_QUOTE_CAP")) == m.MAX_QUOTES


@pytest.mark.parametrize("msg", ["DNS_ERROR source=x phase=response_headers elapsed_seconds=0.1", "NETWORK_TIMEOUT source=x", "UNEXPECTED_HTTP_STATUS",
                                 "HTTP_STATUS_ERROR source=x", "TLS_ERROR source=x"])
def test_unreachable_is_missing_not_error(msg):
    summary = m.run_probe(["wb-dataset-terms", "ecb-usage-policy"], fetcher=_raising(msg))
    assert summary["sources"] == [] and [x["source_id"] for x in summary["missing_sources"]] == ["wb-dataset-terms", "ecb-usage-policy"]
    assert summary["status"] == "RESEARCH_ONLY_NOTHING_APPROVED" and summary["legal_advice"] is False


def test_redirect_off_exact_url_is_missing_with_location():
    loc = lambda url: {"status": 301, "location": "https://example.org/next"}
    s = m.run_probe(["wb-dataset-terms"], fetcher=_raising("UNAUTHORIZED_ENDPOINT_OR_REDIRECT"), locator=loc)
    assert s["missing_sources"][0]["reason"] == "REDIRECT_OFF_EXACT_URL" and s["missing_sources"][0]["redirect"]["status"] == 301


@pytest.mark.parametrize("msg", ["SOURCE_TOO_LARGE", "EMPTY_SOURCE", "INVALID_CONTENT_LENGTH", "UNAPPROVED_SOURCE"])
def test_size_or_integrity_errors_are_hard(msg):
    with pytest.raises(m.GoldTermsError):
        m.run_probe(["wb-dataset-terms"], fetcher=_raising(msg))


@pytest.mark.parametrize("sid,raw", [("wb-dataset-terms", b"%PDF-1.7 data"), ("wb-dataset-terms", b"PK\x03\x04zip"), ("wb-dataset-terms", b"plain text no markup"),
                                      ("ice-iba-fee-schedule-2026", b"<html><body>x</body></html>"), (m.WORKBOOK_ID, b"<html><body>x</body></html>")])
def test_unexpected_content_type_is_hard(sid, raw):
    with pytest.raises(m.GoldTermsError, match="UNEXPECTED_CONTENT_TYPE"):
        m.probe_one(sid, _fetch_for(raw))


def test_oversize_page_is_hard():
    with pytest.raises(m.GoldTermsError, match="PAGE_TOO_LARGE"):
        m.check_content("html", b"<html>" + b"a" * (m.MAX_PAGE_BYTES + 1))


def test_empty_body_is_hard():
    with pytest.raises(m.GoldTermsError, match="EMPTY_SOURCE"):
        m.check_content("html", b"")


def test_corrupt_workbook_is_hard():
    with pytest.raises(m.GoldTermsError, match="WORKBOOK_NOT_PARSEABLE"):
        m.analyse_workbook(b"PK\x03\x04garbage")


def test_workbook_notes_found_and_price_rows_not_stored():
    raw = _xlsx({"Monthly Prices": [["Gold ($/troy oz)"], ["1960M01", "35.27"]],
                 "Description": [["Gold (UK), 99.5% fine, London afternoon fixing, prices in USD per troy oz."],
                                 ["Permission is required to redistribute. Source: LBMA."]]})
    out = m.analyse_workbook(raw)
    assert out["sheet_names"] == ["Monthly Prices", "Description"] and out["data_sheet_present"]
    q = {x["topic"]: x["quote"] for x in out["notes_sheets"][0]["quotes"]}
    assert "London" in q["provider"] and "Permission" in q["rights"]
    blob = json.dumps(out)
    assert "35.27" not in blob and "1960M01" not in blob


def test_workbook_without_notes_sheet_reports_empty_list():
    assert m.analyse_workbook(_xlsx({"Monthly Prices": [["Gold"]]}))["notes_sheets"] == []


def test_main_exit_codes(tmp_path, monkeypatch):
    out = tmp_path / "s.json"
    monkeypatch.setattr(acq, "fetch", _raising("DNS_ERROR source=x"))
    assert m.main(["--summary-out", str(out), "--source", "wb-dataset-terms"]) == 0
    assert json.loads(out.read_text())["missing_sources"][0]["reason"] == "DNS_ERROR"
    out2 = tmp_path / "t.json"
    monkeypatch.setattr(acq, "fetch", _raising("SOURCE_TOO_LARGE"))
    assert m.main(["--summary-out", str(out2), "--source", "wb-dataset-terms"]) == 1
    assert not out2.exists()
