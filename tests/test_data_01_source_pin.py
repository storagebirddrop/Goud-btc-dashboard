import io
import json
import zipfile
from email.message import Message
from pathlib import Path
from unittest.mock import patch
import pytest
from tools.data_01_source_pin import PinError, pin, replay, acquire, sha256, canonical, write_metadata_only

WB = "https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/related/CMO-Historical-Data-Monthly.xlsx"
ECB = "https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A"
BTC = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
CONFIGS = [
    ("world-bank-gold", WB, b""),
    ("ecb-usd-per-eur", ECB, b"TIME_PERIOD,OBS_VALUE\\n2026-09-01,1.1\\n"),
    ("coinmetrics-btc-research", BTC, b'{"data":[{"asset":"btc"}]}'),
]

def wb_bytes():
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        z.writestr("xl/workbook.xml", "<workbook/>")
        z.writestr("[Content_Types].xml", "<Types/>")
    return out.getvalue()

def make(source_id="ecb-usd-per-eur", url=ECB, raw=None, **overrides):
    if raw is None:
        raw = b"TIME_PERIOD,OBS_VALUE\n2026-09-01,1.1\n"
    cfg = dict(source_id=source_id, source_version="v1", url=url, params={"format":"csvdata"},
               parser_version="parser-v1", transform_version="commit-abc",
               rights_status="UNVERIFIED", http_status=200, response_headers={"ETag":"fixture"},
               retrieved_at_utc="2026-10-19T21:00:00Z")
    cfg.update(overrides)
    return pin(raw, **cfg)

@pytest.mark.parametrize("source_id,url,raw", CONFIGS)
def test_offline_replay_three_sources(source_id,url,raw):
    if source_id == "world-bank-gold":
        raw = wb_bytes()
    manifest = make(source_id,url,raw)
    with patch("urllib.request.urlopen", side_effect=AssertionError("network fallback")):
        assert replay(raw,manifest,expected_source_id=source_id,expected_source_version="v1")["status"] == "PASS"
    assert manifest["identity"]["source_sha256"] == sha256(raw)
    assert manifest["identity"]["byte_size"] == len(raw)

def test_identity_is_stable_across_operational_timestamps():
    a = make(retrieved_at_utc="2026-10-19T21:00:00Z")
    b = make(retrieved_at_utc="2026-10-20T21:00:00Z")
    assert a["identity"] == b["identity"]
    assert canonical(a) == canonical(a)
    assert canonical(a) != canonical(b)

@pytest.mark.parametrize("changes,code", [
    ({"raw":b""},"EMPTY_OR_MISSING_SOURCE_BYTES"),
    ({"http_status":429},"UNEXPECTED_HTTP_STATUS"),
    ({"source_id":"evil"},"UNEXPECTED_SOURCE_ID"),
    ({"source_version":"bad version"},"INVALID_SOURCE_VERSION"),
    ({"url":"http://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A"},"UNEXPECTED_SOURCE_URL"),
    ({"response_headers":None},"INVALID_HTTP_METADATA"),
    ({"retrieved_at_utc":"2026-10-19"},"INVALID_RETRIEVAL_TIMESTAMP"),
    ({"storage_reference":"public-github"},"UNVERIFIED_DURABLE_STORAGE_CLAIM"),
    ({"rights_status":"GRANTED_BY_ASSUMPTION"},"INVALID_RIGHTS_STATUS"),
])
def test_pin_negative(changes,code):
    with pytest.raises(PinError,match=code):
        make(**changes)

def test_replay_negative_and_no_network_fallback():
    raw = b"TIME_PERIOD,OBS_VALUE\n2026-09-01,1.1\n"
    m = make(raw=raw)
    cases = [
        (None,m,"MISSING_REPLAY_BYTES"),
        (raw+b"changed",m,"SOURCE_HASH_MISMATCH"),
        (raw,{**m,"identity":{**m["identity"],"source_version":"v2"}},"SOURCE_IDENTITY_MISMATCH"),
        (raw,{**m,"identity":{**m["identity"],"source_sha256":"0"*64}},"SOURCE_HASH_MISMATCH"),
        (raw,{**m,"operations":{**m["operations"],"publication_authorized":True}},"INVALID_VALIDATION_STATUS"),
        (raw,{**m,"schema":"other"},"INVALID_MANIFEST_VERSION"),
    ]
    with patch("urllib.request.urlopen",side_effect=AssertionError("network fallback")):
        for content, manifest, error in cases:
            with pytest.raises(PinError,match=error):
                replay(content,manifest)

def test_version_mismatch():
    with pytest.raises(PinError,match="UNEXPECTED_SOURCE_VERSION"):
        replay(b"TIME_PERIOD,OBS_VALUE\n2026-09-01,1.1\n",make(),expected_source_version="v2")

def test_invalid_schema_and_metadata():
    with pytest.raises(PinError,match="INVALID_SOURCE_SCHEMA"):
        make(raw=b"garbage")
    with pytest.raises(PinError,match="INVALID_REQUEST_PARAMETERS"):
        make(params={"format":None})

def test_no_public_write(tmp_path):
    m = make()
    with pytest.raises(PinError,match="REPOSITORY_WRITE_PROHIBITED"):
        write_metadata_only(m,tmp_path/"repo"/"frontend/public/data/monthly.json",repository_root=tmp_path/"repo")
    output = tmp_path/"isolated"/"manifest.json"
    write_metadata_only(m,output,repository_root=tmp_path/"repo")
    assert json.loads(output.read_text()) == m
    with pytest.raises(PinError,match="NO_OVERWRITE"):
        write_metadata_only(m,output,repository_root=tmp_path/"repo")

def test_acquire_single_fetch_and_replay_offline():
    raw = b"TIME_PERIOD,OBS_VALUE\n2026-09-01,1.1\n"
    class Response:
        status=200
        headers={"Content-Type":"text/csv"}
        def __enter__(self):return self
        def __exit__(self,*a):return False
        def read(self, size=-1):return raw if size < 0 else raw[:size]
    calls=[]
    def opener(req,timeout):
        calls.append(req.full_url)
        return Response()
    args=dict(source_id="ecb-usd-per-eur",source_version="v1",url=ECB,params={"format":"csvdata"},
              parser_version="parser-v1",transform_version="commit-abc")
    data,m=acquire(opener=opener,**args)
    assert len(calls)==1
    assert replay(data,m)["status"]=="PASS"

from tools.data_01_source_pin import MAX_SOURCE_BYTES, _RestrictedRedirect
from urllib.request import Request

def _mock_acquire(raw, headers=None, final_url=ECB):
    class Response:
        status=200
        def __init__(self):self.headers=headers or {}
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def geturl(self):return final_url
        def read(self,limit):
            assert limit==MAX_SOURCE_BYTES+1
            return raw[:limit]
    return acquire(opener=lambda req,timeout:Response(),
                   source_id="ecb-usd-per-eur",source_version="v1",url=ECB,
                   params={"format":"csvdata"},parser_version="parser-v1",
                   transform_version="commit-abc")

@pytest.mark.parametrize("size,ok",[(15_000_000,True),(15_000_001,False)])
def test_download_boundary(size,ok):
    raw=b"TIME_PERIOD,OBS_VALUE\n"+b" "*(size-22)
    if ok:
        data,manifest=_mock_acquire(raw)
        assert len(data)==size
        assert replay(data,manifest)["status"]=="PASS"
    else:
        with pytest.raises(PinError,match="SOURCE_TOO_LARGE"):
            _mock_acquire(raw)

@pytest.mark.parametrize("length,actual,error",[
    (None,50,None),("1",50,None),("15000001",50,"SOURCE_TOO_LARGE"),
    ("50",15_000_001,"SOURCE_TOO_LARGE"),("not-a-number",50,"INVALID_CONTENT_LENGTH")
])
def test_content_length_untrusted(length,actual,error):
    raw=b"TIME_PERIOD,OBS_VALUE\n"+b" "*(actual-22)
    headers={} if length is None else {"Content-Length":length}
    if error:
        with pytest.raises(PinError,match=error):
            _mock_acquire(raw,headers)
    else:
        data,_=_mock_acquire(raw,headers)
        assert len(data)==actual

@pytest.mark.parametrize("destination",[
    "https://unapproved.example/resource",
    "http://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A",
])
def test_redirect_blocked(destination):
    with pytest.raises(PinError,match="UNAUTHORIZED_REDIRECT"):
        _RestrictedRedirect("ecb-usd-per-eur").redirect_request(
            Request(ECB),None,302,"Found",{},destination)

def test_final_url_checked_before_read():
    with pytest.raises(PinError,match="UNAUTHORIZED_REDIRECT"):
        _mock_acquire(b"TIME_PERIOD,OBS_VALUE\n",final_url="https://unapproved.example/")

def test_bounded_acquisition_and_redirect_rejection():
    from tools.data_01_source_pin import MAX_SOURCE_BYTES, _RestrictedRedirect
    from urllib.request import Request
    from unittest.mock import patch
    from tools.data_01_source_pin import _validate_location
    args=dict(source_id="ecb-usd-per-eur",source_version="v1",url=ECB,
              params={"format":"csvdata"},parser_version="parser-v1",transform_version="commit-abc")
    class Response:
        status=200
        def __init__(self,raw,headers=None,url=ECB):
            self.raw=raw
            self.headers=headers or {}
            self.url=url
            self.read_sizes=[]
        def __enter__(self):return self
        def __exit__(self,*a):return False
        def geturl(self):return self.url
        def read(self,size=-1):
            self.read_sizes.append(size)
            return self.raw[:size]
    # Valid full-size ECB fixture: syntactically valid CSV, padded within a quoted field.
    prefix=b"TIME_PERIOD,OBS_VALUE,COMMENT\\n2026-09-01,1.1,"
    raw=prefix+b'"'+b"x"*(MAX_SOURCE_BYTES-len(prefix)-3)+b'"\\n'
    assert len(raw)==MAX_SOURCE_BYTES
    response=Response(raw,{"Content-Length":str(MAX_SOURCE_BYTES)})
    got,manifest=acquire(opener=lambda req,timeout:response,**args)
    assert len(got)==MAX_SOURCE_BYTES
    assert response.read_sizes==[MAX_SOURCE_BYTES+1]
    assert manifest["identity"]["byte_size"]==MAX_SOURCE_BYTES
    assert replay(got,manifest)["status"]=="PASS"
    for headers in ({},{"Content-Length":"2"}):
        response=Response(raw+b"!",headers)
        with pytest.raises(PinError,match="SOURCE_TOO_LARGE"):
            acquire(opener=lambda req,timeout:response,**args)
        assert response.read_sizes==[MAX_SOURCE_BYTES+1]
    response=Response(raw,{"Content-Length":str(MAX_SOURCE_BYTES+1)})
    with pytest.raises(PinError,match="SOURCE_TOO_LARGE"):
        acquire(opener=lambda req,timeout:response,**args)
    assert response.read_sizes==[]
    for target in ("https://attacker.example/steal",
                   "http://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A"):
        with pytest.raises(PinError,match="UNAUTHORIZED_REDIRECT"):
            _RestrictedRedirect("ecb-usd-per-eur").redirect_request(
                Request(ECB),None,302,"Found",{},target)
        response=Response(b"TIME_PERIOD,OBS_VALUE\\n2026-09-01,1.1\\n",url=target)
        with pytest.raises(PinError,match="UNAUTHORIZED_REDIRECT"):
            acquire(opener=lambda req,timeout:response,**args)
        assert response.read_sizes==[]
