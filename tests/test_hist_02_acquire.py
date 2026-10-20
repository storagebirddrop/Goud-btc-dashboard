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
