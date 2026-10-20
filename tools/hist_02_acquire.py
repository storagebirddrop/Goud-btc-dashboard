"""HIST-02 research-only HTTPS acquisition: raw bytes remain ephemeral.
No fallback, no repository writes, no production data or methodology changes.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

MAX_BYTES = 15_000_000
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


def fetch(source, *, opener=None):
    url, kind = SOURCES[source]
    validate_url(source, url)
    opener = opener or build_opener(RestrictedRedirect(source)).open
    with opener(Request(url, headers={"User-Agent": "Goud-btc-dashboard/HIST-02 research"}), timeout=30) as response:
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
        raw = response.read(MAX_BYTES + 1)
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
    for source in SOURCES:
        raw, record = fetch(source)
        filename = out / (source + "." + record["format"])
        with filename.open("xb") as f:
            f.write(raw)
        if hashlib.sha256(filename.read_bytes()).hexdigest() != record["sha256"]:
            raise AcquisitionError("READBACK_HASH_MISMATCH")
        record["readback_hash_match"] = True
        manifest["sources"].append(record)
    (out / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ephemeral-directory", required=True)
    args = parser.parse_args()
    run(args.ephemeral_directory)
