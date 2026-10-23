"""BTC-09: static-distribution and rollback-state verification (price-free; reads files only).

  dist      scan a production build directory: no private candidate/sidecar/snapshot/raw-source file or marker, the shipped /data/monthly.json is
            byte-identical to the committed public file and to the pinned legacy payload, no Bitcoin keys, and no 64-hex literal that could be a
            release pin (the frontend pin list must compile to an empty list).
  state     verify a public state (JSON file + frontend source): the "legacy gold/CBS, no Bitcoin" state a rollback must restore.

Usage: python -m tools.btc_09_distribution_check dist --dist frontend/dist [--public frontend/public/data/monthly.json]
       python -m tools.btc_09_distribution_check state --json PATH [--btc-ts frontend/src/btc.ts]
Exit 0 only when every check holds. Output: booleans, counts and hashes only."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etl import btc_contract as bc  # noqa: E402

FORBIDDEN_NAMES = re.compile(r"(candidate|sidecar|snapshot|cm_priceusd|ecb_usd_per_eur|btc-real|vintage|\.tar$|\.tar\.gz$|\.zip$|private)", re.I)
FORBIDDEN_MARKERS = [b"CANDIDATE_VALUE", b"NO_CANDIDATE_VALUE", b"candidate_values", b"private_sidecar", b"btc04e-snapshot", b"cm_priceusd_daily"]
DAILY_LINE = re.compile(rb"\d{4}-\d{2}-\d{2}:\d+\.\d{6,}")
HEX64 = re.compile(rb"[\"'`][0-9a-f]{64}[\"'`]")
PINS_EMPTY = re.compile(r"export const BTC_APPROVED_COMPOSITE_SHA256:readonly string\[\]=\[\];")


def pins_empty(btc_ts: Path) -> bool:
    return bool(PINS_EMPTY.search(Path(btc_ts).read_text(encoding="utf-8")))


def check_state(json_path: Path, btc_ts: Path) -> dict:
    blob = Path(json_path).read_bytes()
    try:
        doc = json.loads(blob)
    except ValueError:
        doc = None
    rows = doc.get("data") if isinstance(doc, dict) else None
    no_btc_keys = isinstance(rows, list) and "btc" not in doc and not any(isinstance(r, dict) and any(k.startswith(("btc", "sat_")) for k in r) for r in rows)
    out = {"sha256": bc.sha256(blob), "equals_pinned_legacy_payload": bc.sha256(blob) == bc.LEGACY_PUBLIC_SHA256, "no_bitcoin_keys": bool(no_btc_keys),
           "frontend_pin_list_empty": pins_empty(btc_ts), "registry_empty": bc.ARTIFACT_RECORDS == ()}
    out["ok"] = all(out[k] for k in ("equals_pinned_legacy_payload", "no_bitcoin_keys", "frontend_pin_list_empty", "registry_empty"))
    return out


def check_dist(dist: Path, public: Path) -> dict:
    dist = Path(dist)
    files = [p for p in dist.rglob("*") if p.is_file()]
    bad_names = sorted(str(p.relative_to(dist)) for p in files if FORBIDDEN_NAMES.search(p.name))
    bad_markers = sorted({f"{m.decode()}@{p.relative_to(dist)}" for p in files for m in FORBIDDEN_MARKERS if m in p.read_bytes()})
    daily = sorted(str(p.relative_to(dist)) for p in files if DAILY_LINE.search(p.read_bytes()))
    shipped = dist / "data/monthly.json"
    identical = shipped.is_file() and shipped.read_bytes() == Path(public).read_bytes()
    js = [p for p in files if p.suffix in (".js", ".mjs", ".html")]
    hex_literals = sorted({m.group(0)[1:-1].decode() for p in js for m in HEX64.finditer(p.read_bytes())})
    state = check_state(shipped, ROOT / "frontend/src/btc.ts") if shipped.is_file() else {"ok": False}
    out = {"files": len(files), "forbidden_file_names": bad_names, "forbidden_markers": bad_markers, "raw_daily_series_lines_in": daily,
           "shipped_json_identical_to_committed": identical, "shipped_state": state, "sha256_literals_in_bundle": len(hex_literals),
           "no_unexpected_release_pin": len(hex_literals) == 0}
    out["ok"] = not bad_names and not bad_markers and not daily and identical and state.get("ok", False) and out["no_unexpected_release_pin"]
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="BTC-09 static distribution / rollback-state check (price-free)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dist")
    d.add_argument("--dist", required=True)
    d.add_argument("--public", default=str(ROOT / "frontend/public/data/monthly.json"))
    s = sub.add_parser("state")
    s.add_argument("--json", required=True)
    s.add_argument("--btc-ts", default=str(ROOT / "frontend/src/btc.ts"))
    a = ap.parse_args(argv)
    res = check_dist(Path(a.dist), Path(a.public)) if a.cmd == "dist" else check_state(Path(a.json), Path(a.btc_ts))
    print(json.dumps(res, indent=1, sort_keys=True))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
