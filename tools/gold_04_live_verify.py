"""GOLD-04: read-only verification of the PUBLIC production site (HTTP layer).

Fetches the live index, the served JS bundle and /data/monthly.json and compares them with the
repository (committed JSON, release record, CBS csv). It writes nothing to the repository, sends
no credentials and only issues GET requests. Exit code 0 only when every check passes.

Checks (each printed as PASS/FAIL with the measured value):
  * monthly.json: 320 months 2000-01..2026-08, gold_index and gold_grams_per_house filled,
    gold_eur_oz null, CBS fields equal build(csv), sha256 == release-record artifact sha256
    == APPROVED_PUBLIC_JSON_SHA256, bytes identical to the committed file.
  * bundle: asset name equals the locally built asset name (deployment belongs to this source),
    source/method/June-2025 strings present, source URLs present.
  * response headers recorded as evidence (date, etag, last-modified, cf-ray, cache-control).
"""
import argparse
import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from etl.gold_publication_candidate import APPROVED_PUBLIC_JSON_SHA256  # noqa: E402
from etl.static_export import build  # noqa: E402

GOLD = ("gold_index", "gold_grams_per_house")
REQUIRED_BUNDLE_STRINGS = (
    "Peildatum bronstand", "World Bank", "ECB", "85773NED", "eigen", "juni 2025",
    "https://www.worldbank.org/", "https://data.ecb.europa.eu/", "https://opendata.cbs.nl/",
)
results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail != "" else ""))


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "gold-04-live-verify/1 (read-only)",
                                               "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.status, dict(resp.headers.items()), resp.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="https://goud-btc-dashboard.pages.dev/")
    ap.add_argument("--local-dist", default=None, help="locally built frontend/dist to compare asset names")
    args = ap.parse_args()
    base = args.base

    status, headers, index = get(base)
    check("index HTTP 200", status == 200, status)
    for h in ("date", "etag", "last-modified", "cache-control", "cf-ray", "server"):
        print(f"HEADER {h}: {headers.get(h) or headers.get(h.title())}")
    html = index.decode("utf-8", "replace")
    assets = re.findall(r'(?:src|href)="(/assets/[^"]+)"', html)
    check("index references hashed assets", bool(assets), assets)

    status, headers, raw = get(urljoin(base, "data/monthly.json"))
    check("monthly.json HTTP 200", status == 200, status)
    print(f"HEADER monthly.json content-type: {headers.get('content-type') or headers.get('Content-Type')}, "
          f"etag: {headers.get('etag') or headers.get('ETag')}, last-modified: {headers.get('last-modified')}")
    sha = hashlib.sha256(raw).hexdigest()
    record = json.loads((ROOT / "data/gold-release-record.json").read_text(encoding="utf-8"))
    check("live sha256 == release record", sha == record["artifact"]["sha256"], sha)
    check("live sha256 == code pin APPROVED_PUBLIC_JSON_SHA256", sha == APPROVED_PUBLIC_JSON_SHA256)
    check("release record AUTHORIZED", record["release_authorization"]["status"] == "AUTHORIZED",
          f"{record['release_authorization']['authorized_by']} {record['release_authorization']['authorized_at']}")
    committed = (ROOT / "frontend/public/data/monthly.json").read_bytes()
    check("live bytes == committed bytes", raw == committed, f"{len(raw)} bytes")

    rows = json.loads(raw.decode("utf-8"))["data"]
    check("320 months", len(rows) == 320, len(rows))
    check("range 2000-01..2026-08", rows[0]["period"] == "2000-01" and rows[-1]["period"] == "2026-08")
    periods = [r["period"] for r in rows]
    check("no duplicates, strictly increasing", periods == sorted(set(periods)))
    for k in GOLD:
        vals = [r[k] for r in rows]
        filled = [v for v in vals if isinstance(v, (int, float))]
        check(f"{k} filled in all rows, finite positive", len(filled) == len(vals) and all(v > 0 for v in filled),
              f"filled {len(filled)}/{len(vals)}" + (f", min {min(filled):.4f} max {max(filled):.4f}" if filled else ""))
    check("gold_eur_oz null in all rows", all(r["gold_eur_oz"] is None for r in rows))
    check("gold_index 2000-01 == 100", rows[0]["gold_index"] == 100)
    expected = build(ROOT / "data/cbs-housing.csv")["data"]
    same = all({k: v for k, v in a.items() if k not in GOLD} == {k: v for k, v in b.items() if k not in GOLD}
               for a, b in zip(rows, expected)) and len(rows) == len(expected)
    check("CBS fields (house_eur, hpi, hpi_index, period) == build(committed csv)", same)
    check("no sat/btc fields in JSON", not any(re.search(r"sat|btc|bitcoin", k, re.I) for k in rows[0]), list(rows[0]))

    bundle_text = ""
    for path in assets:
        if path.endswith(".js"):
            st, _, body = get(urljoin(base, path))
            check(f"asset {path} HTTP 200", st == 200, len(body))
            bundle_text += body.decode("utf-8", "replace")
    for needle in REQUIRED_BUNDLE_STRINGS:
        check(f"bundle contains {needle!r}", needle in bundle_text)
    # Diagnostic (not a pass/fail check): which earlier releases does the live bundle contain?
    for label, needle in (("DASH-02 UI (#83) 'Toon als tabel'", "Toon als tabel"),
                          ("DASH-01/02 category 'Alternatieve waardering'", "Alternatieve waardering"),
                          ("GOLD-03 source block 'Peildatum bronstand'", "Peildatum bronstand")):
        print(f"DIAGNOSTIC live bundle has {label}: {needle in bundle_text}")
    print(f"DIAGNOSTIC live JSON bytes {len(raw)}, sha256 {sha}")
    if args.local_dist:
        local = sorted(p.name for p in (Path(args.local_dist) / "assets").iterdir())
        live = sorted(Path(a).name for a in assets)
        check("live asset file names == freshly built asset names (same source)",
              all(n in local for n in live), f"live {live} local {local}")

    ok = all(results)
    print(f"\nRESULT: {'ALL CHECKS PASSED' if ok else 'FAILURES PRESENT'} ({sum(results)}/{len(results)})")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
