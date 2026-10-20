"""HIST-02 research-only HTTPS acquisition: raw bytes remain ephemeral.
No fallback, no repository writes, no production data or methodology changes.
"""
import argparse
import hashlib
import json
import os
import socket
import ssl
import time
from urllib.error import HTTPError, URLError
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

MAX_BYTES = 15_000_000
TIMEOUT_SECONDS = 30
SOURCES = {
    "world-bank-gold-history": ("https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/related/CMO-Historical-Data-Monthly.xlsx", "xlsx"),
    "fred-exneus-history": ("https://fred.stlouisfed.org/graph/fredgraph.csv?id=EXNEUS", "csv"),
}


class AcquisitionError(ValueError):
    pass


def validate_url(source, url):
    if source not in SOURCES:
        raise AcquisitionError("UNAPPROVED_SOURCE")
    expected = urlsplit(SOURCES[source][0])
    actual = urlsplit(url)
    if (actual.scheme != "https" or actual.hostname != expected.hostname or
            actual.path != expected.path or actual.query != expected.query or
            actual.port is not None or actual.username or actual.password or actual.fragment):
        raise AcquisitionError("UNAUTHORIZED_ENDPOINT_OR_REDIRECT")


class RestrictedRedirect(HTTPRedirectHandler):
    def __init__(self, source):
        self.source = source

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(self.source, newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _network_error(exc):
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return "NETWORK_TIMEOUT"
    if isinstance(exc, ssl.SSLError):
        return "TLS_ERROR"
    if isinstance(exc, socket.gaierror):
        return "DNS_ERROR"
    if isinstance(exc, HTTPError):
        return "HTTP_STATUS_ERROR"
    if isinstance(exc, URLError) and isinstance(exc.reason, BaseException):
        return _network_error(exc.reason)
    return "NETWORK_ERROR"


def diagnose(source, *, resolver=None, connector=None):
    """Independent bounded DNS/TLS probes, no HTTP response body or fallback."""
    if source not in SOURCES:
        raise AcquisitionError("UNAPPROVED_SOURCE")
    url = SOURCES[source][0]
    validate_url(source, url)
    host = urlsplit(url).hostname
    result = {"source_id": source, "url": url, "dns": "NOT_VERIFIED", "tls": "NOT_VERIFIED"}
    try:
        (resolver or socket.getaddrinfo)(host, 443, type=socket.SOCK_STREAM)
        result["dns"] = "PASS"
    except OSError as exc:
        result["dns"] = _network_error(exc)
        return result
    try:
        with (connector or socket.create_connection)((host, 443), timeout=5) as sock:
            with ssl.create_default_context().wrap_socket(sock, server_hostname=host):
                result["tls"] = "PASS"
    except OSError as exc:
        result["tls"] = _network_error(exc)
    return result


def fetch(source, *, opener=None):
    if source not in SOURCES:
        raise AcquisitionError("UNAPPROVED_SOURCE")
    url, kind = SOURCES[source]
    validate_url(source, url)
    opener = opener or build_opener(RestrictedRedirect(source)).open
    phase = "response_headers"
    started = time.monotonic()
    try:
        response_context = opener(Request(url, headers={"User-Agent": "Goud-btc-dashboard/HIST-02 research"}), timeout=TIMEOUT_SECONDS)
    except (OSError, URLError, TimeoutError) as exc:
        raise AcquisitionError(f"{_network_error(exc)} source={source} phase={phase} elapsed_seconds={time.monotonic()-started:.2f}") from exc
    with response_context as response:
        if hasattr(response, "geturl"):
            validate_url(source, response.geturl())
        if response.status != 200:
            raise AcquisitionError("UNEXPECTED_HTTP_STATUS")
        length = response.headers.get("Content-Length")
        if length is not None:
            if not length.isascii() or not length.isdecimal():
                raise AcquisitionError("INVALID_CONTENT_LENGTH")
            if int(length) > MAX_BYTES:
                raise AcquisitionError("SOURCE_TOO_LARGE")
        try:
            raw = response.read(MAX_BYTES + 1)
        except (OSError, URLError, TimeoutError) as exc:
            raise AcquisitionError(f"{_network_error(exc)} source={source} phase=response_body elapsed_seconds={time.monotonic()-started:.2f}") from exc
        if len(raw) > MAX_BYTES:
            raise AcquisitionError("SOURCE_TOO_LARGE")
        if not raw:
            raise AcquisitionError("EMPTY_SOURCE")
        return raw, {"source_id": source, "url": url, "sha256": hashlib.sha256(raw).hexdigest(),
                     "bytes": len(raw), "http_status": 200, "format": kind,
                     "rights_status": "UNVERIFIED", "retention_status": "EPHEMERAL_ONLY",
                     "publication_authorized": False}


def run(directory):
    out = Path(directory).resolve()
    if os.environ.get("GITHUB_WORKSPACE") and (out == Path(os.environ["GITHUB_WORKSPACE"]).resolve() or
        out.is_relative_to(Path(os.environ["GITHUB_WORKSPACE"]).resolve())):
        raise AcquisitionError("REPOSITORY_WRITE_PROHIBITED")
    out.mkdir(parents=True, exist_ok=True)
    manifest = {"status": "BLOCKED_PENDING_SOURCE_SCHEMA_AND_RIGHTS_REVIEW", "sources": []}
    failures = []
    for source in SOURCES:
        diagnostic = diagnose(source)
        print(json.dumps({"diagnostic": diagnostic}, sort_keys=True), flush=True)
        try:
            raw, record = fetch(source)
        except AcquisitionError as exc:
            failures.append({"source_id": source, "error": str(exc)})
            print(json.dumps({"acquisition_failure": failures[-1]}, sort_keys=True), flush=True)
            continue
        filename = out / (source + "." + record["format"])
        with filename.open("xb") as f:
            f.write(raw)
        if hashlib.sha256(filename.read_bytes()).hexdigest() != record["sha256"]:
            raise AcquisitionError("READBACK_HASH_MISMATCH")
        record["readback_hash_match"] = True
        manifest["sources"].append(record)
        print(json.dumps({"acquired": record}, sort_keys=True), flush=True)
    manifest["failures"] = failures
    manifest["status"] = "ACQUISITION_INCOMPLETE" if failures else "ACQUIRED_PENDING_SOURCE_SCHEMA_AND_RIGHTS_REVIEW"
    (out / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    if failures:
        raise AcquisitionError("ACQUISITION_INCOMPLETE")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ephemeral-directory", required=True)
    args = parser.parse_args()
    run(args.ephemeral_directory)
