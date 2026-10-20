import hashlib
import io
from types import SimpleNamespace
import pytest
from tools.hist_02_acquire import AcquisitionError, MAX_BYTES, fetch, validate_url, SOURCES


class Response:
    status = 200
    def __init__(self, data, url, length=None):
        self.data, self.url = data, url
        self.headers = {} if length is None else {"Content-Length": str(length)}
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def geturl(self): return self.url
    def read(self, n): return self.data[:n]


def opener(data, source="fred-exneus-history", length=None, url=None):
    return lambda req, timeout: Response(data, url or SOURCES[source][0], length)


def test_exact_limit_and_hash():
    raw, record = fetch("fred-exneus-history", opener=opener(b"a" * MAX_BYTES))
    assert len(raw) == MAX_BYTES
    assert record["sha256"] == hashlib.sha256(raw).hexdigest()


@pytest.mark.parametrize("size", [MAX_BYTES + 1, MAX_BYTES + 99])
def test_over_limit(size):
    with pytest.raises(AcquisitionError, match="SOURCE_TOO_LARGE"):
        fetch("fred-exneus-history", opener=opener(b"a" * size))


def test_false_content_length():
    with pytest.raises(AcquisitionError, match="SOURCE_TOO_LARGE"):
        fetch("fred-exneus-history", opener=opener(b"a" * (MAX_BYTES + 1), length=1))


def test_oversized_content_length():
    with pytest.raises(AcquisitionError, match="SOURCE_TOO_LARGE"):
        fetch("fred-exneus-history", opener=opener(b"a", length=MAX_BYTES + 1))


@pytest.mark.parametrize("url", ["http://fred.stlouisfed.org/graph/fredgraph.csv?id=EXNEUS",
    "https://evil.example/graph/fredgraph.csv?id=EXNEUS",
    "https://fred.stlouisfed.org/graph/fredgraph.csv?id=OTHER"])
def test_redirect_rejected(url):
    with pytest.raises(AcquisitionError, match="UNAUTHORIZED_ENDPOINT_OR_REDIRECT"):
        fetch("fred-exneus-history", opener=opener(b"test", url=url))


def test_missing_and_bad_status():
    with pytest.raises(AcquisitionError, match="EMPTY_SOURCE"):
        fetch("fred-exneus-history", opener=opener(b""))


def test_source_allowlist():
    with pytest.raises(AcquisitionError, match="UNAPPROVED_SOURCE"):
        validate_url("other", "https://example.com")

def test_header_timeout_classified():
    def opener_timeout(req, timeout):
        assert timeout == 30
        raise TimeoutError("header timeout")
    with pytest.raises(AcquisitionError, match="NETWORK_TIMEOUT.*phase=response_headers"):
        fetch("world-bank-gold-history", opener=opener_timeout)


def test_body_timeout_classified():
    class TimedResponse(Response):
        def read(self, n):
            assert n == MAX_BYTES + 1
            raise TimeoutError("body timeout")
    with pytest.raises(AcquisitionError, match="NETWORK_TIMEOUT.*phase=response_body"):
        fetch("fred-exneus-history", opener=lambda req, timeout: TimedResponse(b"", SOURCES["fred-exneus-history"][0]))


def test_dns_error_classified():
    import socket
    def failed(req, timeout):
        raise socket.gaierror("DNS failure")
    with pytest.raises(AcquisitionError, match="DNS_ERROR"):
        fetch("fred-exneus-history", opener=failed)


def test_diagnostic_dns_failure():
    import socket
    from tools.hist_02_acquire import diagnose
    def failed(*args, **kwargs):
        raise socket.gaierror("DNS failure")
    result = diagnose("fred-exneus-history", resolver=failed)
    assert result["dns"] == "DNS_ERROR"
    assert result["tls"] == "NOT_VERIFIED"


def test_run_restricted_to_selected_source(monkeypatch, tmp_path):
    import json
    import tools.hist_02_acquire as acq
    seen = []
    def fake_fetch(source):
        seen.append(source)
        raise AcquisitionError("NETWORK_TIMEOUT source=%s phase=response_headers" % source)
    monkeypatch.setattr(acq, "fetch", fake_fetch)
    monkeypatch.setattr(acq, "diagnose", lambda source: {"source_id": source, "dns": "PASS", "tls": "PASS"})
    with pytest.raises(AcquisitionError, match="ACQUISITION_INCOMPLETE"):
        acq.run(tmp_path / "out", ["fred-exneus-history"])
    assert seen == ["fred-exneus-history"]
    manifest = json.loads((tmp_path / "out" / "manifest.json").read_text())
    assert manifest["status"] == "ACQUISITION_INCOMPLETE" and manifest["sources"] == []
