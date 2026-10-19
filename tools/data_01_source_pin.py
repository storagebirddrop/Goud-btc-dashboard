"""DATA-01B: isolated, read-only source byte pinning and offline replay.

No production ETL import, pricing calculation, public output or automatic fallback.
Raw bytes exist only in caller memory / explicitly supplied isolated directory.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError

HEX = re.compile(r"^[0-9a-f]{64}$")
VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,127}$")
ALLOWED = {
    "world-bank-gold": ("thedocs.worldbank.org", "/en/doc/", "xlsx"),
    "ecb-usd-per-eur": ("data-api.ecb.europa.eu", "/service/data/EXR/D.USD.EUR.SP00.A", "csv"),
    "coinmetrics-btc-research": ("community-api.coinmetrics.io", "/v4/timeseries/asset-metrics", "json"),
}
METADATA = ("content-type", "etag", "last-modified")
MAX_SOURCE_BYTES = 15_000_000


class _RestrictedRedirect(HTTPRedirectHandler):
    def __init__(self, source_id):
        self.source_id = source_id

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Revalidate every redirect hop, not only the initial URL.
        _validate_location(self.source_id, newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _validate_location(source_id, url):
    u = urlsplit(url)
    host, prefix, _ = ALLOWED[source_id]
    if (u.scheme != "https" or u.hostname != host or u.port is not None or
            u.username is not None or u.password is not None or
            not u.path.startswith(prefix) or u.fragment):
        raise PinError("UNAUTHORIZED_REDIRECT")


def _content_length(headers):
    value = next((v for k, v in headers.items() if k.lower() == "content-length"), None)
    if value is None:
        return None
    if not isinstance(value, str) or not value.isascii() or not value.isdecimal():
        raise PinError("INVALID_CONTENT_LENGTH")
    return int(value)



class PinError(ValueError):
    """Fail closed on incomplete, changed or unauthorized source evidence."""


def sha256(raw: bytes) -> str:
    if not isinstance(raw, bytes):
        raise PinError("MISSING_SOURCE_BYTES")
    return hashlib.sha256(raw).hexdigest()


def canonical(obj) -> bytes:
    return (json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                       allow_nan=False) + "\n").encode("utf-8")


def _config(source_id, source_version, url, params, parser_version, transform_version,
            rights_status):
    if source_id not in ALLOWED:
        raise PinError("UNEXPECTED_SOURCE_ID")
    if not isinstance(source_version, str) or not VERSION.fullmatch(source_version):
        raise PinError("INVALID_SOURCE_VERSION")
    if not all(isinstance(x, str) and VERSION.fullmatch(x) for x in (parser_version, transform_version)):
        raise PinError("INVALID_TRANSFORM_VERSION")
    if rights_status not in ("UNVERIFIED", "RESTRICTED", "APPROVED"):
        raise PinError("INVALID_RIGHTS_STATUS")
    if not isinstance(params, dict) or any(not isinstance(k, str) or not k or not isinstance(v, str) or not v
                                           for k, v in params.items()):
        raise PinError("INVALID_REQUEST_PARAMETERS")
    if not isinstance(url, str):
        raise PinError("INVALID_SOURCE_URL")
    u = urlsplit(url)
    host, prefix, _ = ALLOWED[source_id]
    if (u.scheme != "https" or u.hostname != host or u.port is not None or
            u.username is not None or u.password is not None or
            not u.path.startswith(prefix) or u.query or u.fragment):
        raise PinError("UNEXPECTED_SOURCE_URL")
    return dict(source_id=source_id, source_version=source_version, endpoint=url,
                request_parameters=dict(sorted(params.items())),
                parser_version=parser_version, transform_version=transform_version,
                rights_status=rights_status)


def _schema_check(raw, kind):
    # Format gate only; economic source parsing stays in existing adapters.
    if kind == "xlsx":
        import io
        import zipfile
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                if not {"xl/workbook.xml", "[Content_Types].xml"}.issubset(archive.namelist()):
                    raise PinError("INVALID_SOURCE_SCHEMA")
                if archive.testzip() is not None:
                    raise PinError("INVALID_SOURCE_SCHEMA")
        except (ValueError, zipfile.BadZipFile, OSError) as exc:
            raise PinError("INVALID_SOURCE_SCHEMA") from exc
    elif kind == "csv":
        if b"TIME_PERIOD" not in raw.splitlines()[0] or b"OBS_VALUE" not in raw.splitlines()[0]:
            raise PinError("INVALID_SOURCE_SCHEMA")
    elif kind == "json":
        try:
            value = json.loads(raw)
        except (UnicodeError, ValueError) as exc:
            raise PinError("INVALID_SOURCE_SCHEMA") from exc
        if not isinstance(value, dict) or not isinstance(value.get("data"), list):
            raise PinError("INVALID_SOURCE_SCHEMA")


def pin(raw: bytes, *, source_id: str, source_version: str, url: str,
        params: dict, parser_version: str, transform_version: str,
        rights_status: str = "UNVERIFIED", http_status: int = 200,
        response_headers: dict | None = None, retrieved_at_utc: str,
        storage_reference: str = "EPHEMERAL_RUNNER_ONLY",
        retention_status: str = "NOT_DURABLE"):
    identity = _config(source_id, source_version, url, params, parser_version,
                       transform_version, rights_status)
    if not isinstance(raw, bytes) or not raw:
        raise PinError("EMPTY_OR_MISSING_SOURCE_BYTES")
    if http_status != 200 or isinstance(http_status, bool):
        raise PinError("UNEXPECTED_HTTP_STATUS")
    if not isinstance(response_headers, dict) or any(not isinstance(k, str) or not isinstance(v, str)
                                                     for k, v in response_headers.items()):
        raise PinError("INVALID_HTTP_METADATA")
    if not isinstance(retrieved_at_utc, str):
        raise PinError("INVALID_RETRIEVAL_TIMESTAMP")
    try:
        dt = datetime.fromisoformat(retrieved_at_utc.replace("Z", "+00:00"))
        if dt.tzinfo is None or dt.utcoffset().total_seconds() != 0:
            raise ValueError
    except (ValueError, AttributeError):
        raise PinError("INVALID_RETRIEVAL_TIMESTAMP") from None
    if storage_reference != "EPHEMERAL_RUNNER_ONLY" or retention_status != "NOT_DURABLE":
        raise PinError("UNVERIFIED_DURABLE_STORAGE_CLAIM")
    digest = sha256(raw)  # ALWAYS before schema validation / downstream parsing.
    identity.update(source_sha256=digest, byte_size=len(raw))
    identity["source_identity_sha256"] = sha256(canonical(identity))
    _, _, kind = ALLOWED[source_id]
    _schema_check(raw, kind)
    operations = dict(retrieved_at_utc=retrieved_at_utc, http_status=http_status,
                      response_headers={k.lower(): v for k, v in response_headers.items()
                                        if k.lower() in METADATA},
                      storage_reference=storage_reference, retention_status=retention_status,
                      hash_validation="PASS", schema_validation="PASS",
                      replay_bytes_durable=False, publication_authorized=False)
    return {"schema": "DATA-01B-source-manifest-v1", "identity": identity,
            "operations": operations}


def acquire(*, opener=None, timeout=30, **kwargs):
    """Explicit one-time fetch. Never used by replay; no retry/fallback."""
    if "raw" in kwargs or "http_status" in kwargs or "response_headers" in kwargs:
        raise PinError("INVALID_ACQUISITION_ARGUMENTS")
    if "retrieved_at_utc" in kwargs:
        raise PinError("RETRIEVAL_TIME_SET_BY_ACQUISITION")
    cfg = _config(kwargs["source_id"], kwargs["source_version"], kwargs["url"],
                  kwargs["params"], kwargs["parser_version"], kwargs["transform_version"],
                  kwargs.get("rights_status", "UNVERIFIED"))
    url = cfg["endpoint"]
    if cfg["request_parameters"]:
        url += "?" + urlencode(cfg["request_parameters"])
    req = Request(url, headers={"User-Agent": "goud-btc-dashboard/data-01b research"})
    if opener is None:
        opener = build_opener(_RestrictedRedirect(cfg["source_id"])).open
    try:
        with opener(req, timeout=timeout) as response:
            if hasattr(response, "geturl"):
                _validate_location(cfg["source_id"], response.geturl())
            status = response.status
            headers = dict(response.headers.items())
            length = _content_length(headers)
            if length is not None and length > MAX_SOURCE_BYTES:
                raise PinError("SOURCE_TOO_LARGE")
            raw = response.read(MAX_SOURCE_BYTES + 1)
            if len(raw) > MAX_SOURCE_BYTES:
                raise PinError("SOURCE_TOO_LARGE")
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise PinError("SOURCE_ACQUISITION_FAILED") from exc
    manifest = pin(raw, http_status=status, response_headers=headers,
                   retrieved_at_utc=datetime.now(timezone.utc).isoformat(), **kwargs)
    return raw, manifest


def replay(raw: bytes, manifest: dict, *, expected_source_id: str | None = None,
           expected_source_version: str | None = None):
    """Pure offline replay. No network or source parser imports."""
    if not isinstance(manifest, dict) or set(manifest) != {"schema", "identity", "operations"}:
        raise PinError("INVALID_MANIFEST")
    if manifest["schema"] != "DATA-01B-source-manifest-v1":
        raise PinError("INVALID_MANIFEST_VERSION")
    identity, op = manifest["identity"], manifest["operations"]
    if not isinstance(identity, dict) or not isinstance(op, dict):
        raise PinError("INVALID_MANIFEST")
    required = {"source_id", "source_version", "endpoint", "request_parameters",
                "parser_version", "transform_version", "rights_status",
                "source_sha256", "byte_size", "source_identity_sha256"}
    if set(identity) != required:
        raise PinError("INVALID_MANIFEST")
    if expected_source_id is not None and identity["source_id"] != expected_source_id:
        raise PinError("UNEXPECTED_SOURCE_ID")
    if expected_source_version is not None and identity["source_version"] != expected_source_version:
        raise PinError("UNEXPECTED_SOURCE_VERSION")
    _config(identity["source_id"], identity["source_version"], identity["endpoint"],
            identity["request_parameters"], identity["parser_version"],
            identity["transform_version"], identity["rights_status"])
    if not isinstance(raw, bytes) or not raw:
        raise PinError("MISSING_REPLAY_BYTES")
    if not isinstance(identity["source_sha256"], str) or not HEX.fullmatch(identity["source_sha256"]):
        raise PinError("INVALID_MANIFEST_HASH")
    if sha256(raw) != identity["source_sha256"] or len(raw) != identity["byte_size"]:
        raise PinError("SOURCE_HASH_MISMATCH")
    unsigned = {k: v for k, v in identity.items() if k != "source_identity_sha256"}
    if sha256(canonical(unsigned)) != identity["source_identity_sha256"]:
        raise PinError("SOURCE_IDENTITY_MISMATCH")
    if op.get("hash_validation") != "PASS" or op.get("schema_validation") != "PASS" or op.get("publication_authorized") is not False:
        raise PinError("INVALID_VALIDATION_STATUS")
    _schema_check(raw, ALLOWED[identity["source_id"]][2])
    return {"status": "PASS", "source_id": identity["source_id"],
            "source_version": identity["source_version"],
            "source_sha256": identity["source_sha256"],
            "byte_size": identity["byte_size"],
            "source_identity_sha256": identity["source_identity_sha256"]}


def write_metadata_only(manifest: dict, output: Path, *, repository_root: Path):
    """Write only JSON metadata; no raw source bytes and no protected public paths."""
    output, root = Path(output).resolve(), Path(repository_root).resolve()
    if output == root or output.is_relative_to(root):
        raise PinError("REPOSITORY_WRITE_PROHIBITED")
    if output.exists():
        raise PinError("NO_OVERWRITE")
    if not isinstance(manifest, dict) or manifest.get("schema") != "DATA-01B-source-manifest-v1":
        raise PinError("INVALID_MANIFEST")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical(manifest))
