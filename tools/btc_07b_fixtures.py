"""BTC-07B P3: SYNTHETIC fixtures for the local browser acceptance (B01-B11). Fictional prices, real CBS/legacy rows, nothing is a market value.

The default and early fixtures are produced by the real contract code (`compose_release`) from a synthetic vintage, so the UI is exercised on
payloads the backend contract accepts. The `exact` fixture is hand-made (H = 300000, P = 60000, F = 1.2 -> 6 BTC / 600000000 sat) and only
serves the number-format proof; it is never valid for a release. Output goes to an explicit new directory OUTSIDE the repository."""
from __future__ import annotations

import gzip
import hashlib
import json
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from etl import btc_contract as bc  # noqa: E402
from tools import btc_04e_cm_replay as b4  # noqa: E402
from tools import btc_06c_candidate as cand  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "data/cbs-housing.csv"
LEGACY = ROOT / "frontend/public/data/monthly.json"
STAMP = "2026-10-22T10:00:00+00:00"


def _days(first, last):
    d, end = date.fromisoformat(first), date.fromisoformat(last)
    while d <= end:
        yield d.isoformat()
        d += timedelta(days=1)


def _price(day):
    d = date.fromisoformat(day)
    return Decimal(20) + Decimal((d.year - 2010) * 37 + d.month * 5) + Decimal(d.day * 7 % 11) / Decimal(3)


def _fx(day):
    return Decimal("1.1") + Decimal(date.fromisoformat(day).day % 7) / Decimal(50)


def synthetic_candidate(work: Path):
    cm = {d: _price(d) for d in _days("2010-07-18", "2026-09-30")}
    hol = set()
    for y in range(1999, 2027):
        hol |= {h.isoformat() for h in b4.target_holidays(y)}
    ecb = {d: _fx(d) for d in _days("1999-01-04", "2026-09-30") if date.fromisoformat(d).weekday() < 5 and d not in hol}
    keys = sorted(cm)
    pages = [json.dumps({"data": [{"asset": "btc", "time": f"{d}T00:00:00.000000000Z", "PriceUSD": str(cm[d])} for d in keys[i:i + 2500]]}).encode()
             for i in range(0, len(keys), 2500)]
    house = b4.hb.cbs_2000_series(CSV)
    built = b4.build_from_daily(cm, ecb, house, STAMP)
    hashes = [hashlib.sha256(p).hexdigest() for p in pages]
    acq = {"source": b4.PROVIDER, "metric": "PriceUSD", "url": b4.BASE_URL, "query": b4.query("2010-07-18", max(cm)), "retrieved_at_utc": STAMP,
           "pages": len(pages), "page_sha256": hashes, "response_sha256": hashlib.sha256("".join(hashes).encode()).hexdigest(),
           "first": min(cm), "last": max(cm), "n": len(cm), "provider_gaps": [], "daily": cm}
    man = b4.manifest(acq, "e" * 64, ecb, b4.derived_values_sha256(built), b4.source_windows({"cm_priceusd_daily": cm, "ecb_usd_per_eur_daily": ecb}), "deadbeef")
    snap = work / "synthetic-snapshot"
    b4.export_snapshot(snap, cm_daily=cm, ecb_daily=ecb, man=man, raw_pages=pages, derived_cutoff=b4.RESEARCH_CUTOFF,
                       cbs_input_sha256=hashlib.sha256(CSV.read_bytes()).hexdigest())
    return cand.build_candidate(snap, CSV, LEGACY) + (built,)


def _auth(months, early=False):
    return {"release_id": "SYNTHETIC-BROWSER-FIXTURE", "decision_ref": "SYNTHETIC-NOT-A-DECISION", "months": months,
            "rights_review_ref": "SYNTHETIC", "conflicting_contract_check": "VERIFIED", "early_history_authorized": early}


def _put(out: Path, name: str, payload=None, blob: bytes = None) -> str:
    blob = bc.serialize(payload) if blob is None else blob
    (out / f"{name}.json").write_bytes(blob)
    return hashlib.sha256(blob).hexdigest()


def load_real_candidate(candidate_dir) -> tuple:
    """BTC-07E-B: the PRIVATE real candidate written by tools/btc_06c_candidate.py (preview + private sidecar). Read only; nothing is written back."""
    d = Path(candidate_dir)
    return json.loads((d / "candidate.json").read_text(encoding="utf-8")), json.loads((d / "candidate_values.json").read_text(encoding="utf-8"))


def build_fixtures(out_dir, real_candidate_dir=None, real_composite=None) -> dict:
    """Without `real_candidate_dir` everything is SYNTHETIC (BTC-07B). With it, ONLY the default payload (and the fixtures derived from it: incomplete,
    unpinned claim, exact) is composed from the real private candidate with a TEST authorization that exists only in the temporary test build;
    the early/Q3 fixture stays synthetic because the standard candidate carries no Q3 values."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    preview, sidecar, _, built = synthetic_candidate(out)
    if real_candidate_dir is not None:
        r_preview, r_sidecar = load_real_candidate(real_candidate_dir)
        r_months = sorted(r_sidecar["months"])
        default = bc.compose_release(r_preview, r_sidecar, _auth([m for m in r_months if m >= "2014-02"]))
        if real_composite is not None:  # BTC-10: test the EXACT proposed release bytes instead of a freshly composed test payload
            default = json.loads(real_composite.decode("utf-8"))
            if bc.serialize(default) != real_composite:
                raise ValueError("the supplied composite is not in canonical serialization")
    else:
        all_months = sorted(sidecar["months"])
        default = bc.compose_release(preview, sidecar, _auth([m for m in all_months if m >= "2014-02"]))
    # separately authorised FICTIONAL early history (Q3): the standard sidecar never carries it, so the values are added here for the UI proof only
    early_sidecar = json.loads(json.dumps(sidecar))
    for m, (btc_v, sat_v) in cand.candidate_months(built, "2010-08").items():
        early_sidecar["months"].setdefault(m, {"btc_per_house": format(btc_v, "f"), "sat_per_house": format(sat_v, "f"), "private_state": "CANDIDATE_VALUE"})
    early = bc.compose_release(preview, early_sidecar, _auth(sorted(early_sidecar["months"]), early=True))
    shas, pinned = {}, []

    shas["real_default"] = _put(out, "real_default", default)
    shas["real_early"] = _put(out, "real_early", early)
    pinned += ["real_default", "real_early"]

    # B06: one month of the default coverage with incomplete source data (a null, never a zero)
    incomplete = json.loads(json.dumps(default))
    for r in incomplete["data"]:
        if r["period"] == "2015-07":
            r["btc_per_house"] = r["sat_per_house"] = None
            r["btc_meta"].update(status="MISSING", missing_reason="INCOMPLETE_PERIOD")
    shas["incomplete"] = _put(out, "incomplete", incomplete)
    pinned.append("incomplete")

    # B02: hand-made exact numbers, 3 months, not tied to the legacy payload
    legacy_rows = json.loads(LEGACY.read_text())["data"]
    exact = json.loads(json.dumps(default))
    exact["data"] = [dict(r, house_eur=300000.0) for r in exact["data"] if "2014-02" <= r["period"] <= "2014-04"]
    vals = {"2014-02": (6, 600000000), "2014-03": (6.12345678, 612345678), "2014-04": (5.5, 550000000)}
    for r in exact["data"]:
        r["btc_per_house"], r["sat_per_house"] = vals[r["period"]]
    exact["btc"]["coverage"].update(authorized_from="2014-02", authorized_through="2014-04")
    shas["exact"] = _put(out, "exact", exact)
    pinned.append("exact")

    # B10: pinned bytes whose root block is wrong, or rows without metadata (pin alone must not be enough)
    bad_root = json.loads(json.dumps(default))
    bad_root["btc"]["contract_version"] = "btc-monthly/0"
    shas["pinned_bad_root"] = _put(out, "pinned_bad_root", bad_root)
    no_meta = json.loads(json.dumps(default))
    for r in no_meta["data"]:
        r.pop("btc_meta", None)
    shas["pinned_no_meta"] = _put(out, "pinned_no_meta", no_meta)
    pinned += ["pinned_bad_root", "pinned_no_meta"]

    # NOT pinned: a JSON that claims authorization, and legacy rows carrying unauthorized numbers
    shas["unpinned_authorized_claim"] = _put(out, "unpinned_authorized_claim", blob=bc.serialize(default) + b"\n")
    poison = {"data": [dict(r, sat_per_house=123456789, btc_per_house=1.2345, btc_eur=61000, publication_authorized=True) for r in legacy_rows]}
    shas["poisoned_legacy"] = _put(out, "poisoned_legacy", poison)
    shas["legacy"] = _put(out, "legacy", blob=LEGACY.read_bytes())
    assert shas["legacy"] == bc.LEGACY_PUBLIC_SHA256
    index = {"shas": shas, "pinned": sorted(shas[n] for n in pinned),
             "real_mode": real_candidate_dir is not None,
             "note": "REAL default payload from the private candidate (TEST authorization, temporary build only); other fixtures synthetic; not a release"
             if real_candidate_dir is not None else "SYNTHETIC fixtures; fictional prices; not a release"}
    (out / "index.json").write_text(json.dumps(index, indent=1, sort_keys=True) + "\n")
    return index


if __name__ == "__main__":
    print(json.dumps(build_fixtures(sys.argv[1]), indent=1, sort_keys=True))
