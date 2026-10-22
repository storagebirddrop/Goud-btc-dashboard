"""BTC-06C: PRIVATE production-candidate adapter for btc-monthly/1. Research side; NOTHING IS PUBLISHED.

Builds the candidate (legacy rows + btc_per_house, sat_per_house, btc_meta + root block `btc`) from a verified BTC-05D vintage snapshot, the
committed CBS csv and the approved legacy payload. It reuses the BTC-04E calculation (CM_PRICEUSD_MONTHMEAN_C1_V1) and the BTC-05D
snapshot/replay; there is no second pipeline and no network access. Mandatory checks: snapshot integrity and offline replay IDENTICAL, the
CBS csv hash recorded in the snapshot, the pinned legacy payload hash and agreement of the legacy CBS column with the csv. The candidate
and its exact-value sidecar are written to an explicit NEW directory and are never uploaded or committed.
"""
import argparse
import csv
import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from etl import btc_contract as bc  # noqa: E402
from tools import btc_04e_cm_replay as b4  # noqa: E402

SOURCES = ["coinmetrics_community_priceusd", "ecb_exr_d_usd_eur", "cbs_85773NED"]


class CandidateError(b4.Btc04eError):
    """A mandatory production-candidate check failed: no candidate is produced."""


def _sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def candidate_months(built: dict, first_value_month=bc.FIRST_VALUE_MONTH) -> dict:
    """{month: (btc, sats) Decimals} that may enter the private candidate: a value, from the first value month on, and eligibility that
    is not HOLD. Releasing anything is a separate matter: no month is ever marked RELEASE_ELIGIBLE here."""
    btc = {p.period: p.value for p in built["cbs_btc_per_house_cm_c1"].points}
    sats = {p.period: p.value for p in built["cbs_sats_per_house_cm_c1"].points}
    return {m: (btc[m], sats[m]) for m in sorted(btc) if btc[m] is not None and m >= first_value_month
            and b4.month_eligibility(m) == "RESEARCH_ONLY"}


def _meta(month, selected, built_btc):
    """btc_meta for a month: CANDIDATE with its quality, HOLD for the absolute exception, else MISSING with an explicit reason."""
    q = bc.quality_of(month)
    if month in bc.HOLD_MONTHS:
        return {"status": "HOLD", "quality": q, "missing_reason": "NOT_PUBLISHED", "exception": bc.HOLD_MONTHS[month]}
    if month in selected:
        return {"status": "CANDIDATE", "quality": q, "missing_reason": None, "exception": None}
    if month < bc.FIRST_SUPPORTED_MONTH:
        reason = "NOT_APPLICABLE"
    elif month < bc.FIRST_VALUE_MONTH:
        reason = "NOT_PUBLISHED"  # early history exists for research only and is not numeric in this contract version
    else:
        reason = "INCOMPLETE_PERIOD" if built_btc.get(month) is None else "FAILED_VALIDATION"
    return {"status": "MISSING", "quality": q, "missing_reason": reason, "exception": None}


def build_candidate(snapshot_dir, cbs_csv, legacy_json) -> tuple:
    """-> (candidate dict, exact sidecar dict, value-free summary). Raises CandidateError / SnapshotError / BtcContractError."""
    snap = b4.load_snapshot(snapshot_dir)  # fail closed: hashes, versions, raw bytes vs normalized values
    cbs_sha = _sha(cbs_csv)
    if snap["cbs_input_sha256"] is None:
        raise CandidateError("snapshot carries no CBS input hash: CBS provenance cannot be verified")
    if snap["cbs_input_sha256"] != cbs_sha:
        raise CandidateError("CBS_INPUT_DIFFERS: the CBS csv is not the one this vintage was calculated with; a revised CBS needs a new review")
    legacy_bytes = Path(legacy_json).read_bytes()
    if bc.sha256(legacy_bytes) != bc.LEGACY_PUBLIC_SHA256:
        raise CandidateError("the legacy payload is not the pinned approved gold/CBS payload")
    legacy = json.loads(legacy_bytes)
    house = b4.hb.cbs_2000_series(cbs_csv)
    hv = {o.period: float(Decimal(str(o.value))) for o in house.observations}
    for row in legacy["data"]:
        if hv.get(row["period"]) != row["house_eur"]:
            raise CandidateError(f"{row['period']}: legacy house_eur differs from the CBS csv the vintage was calculated with")
    replay = b4.replay(snapshot_dir, house, cbs_sha)
    if replay["status"] != "IDENTICAL":
        raise CandidateError(f"offline replay of the vintage is {replay['status']}, not IDENTICAL")
    built = b4.build_from_daily(snap["cm_daily"], snap["ecb_daily"], house, snap["man"]["coinmetrics"]["retrieved_at_utc"])
    selected = candidate_months(built)
    built_btc = {p.period: p.value for p in built["cbs_btc_per_house_cm_c1"].points}
    rows, exact = [], {}
    for lrow in legacy["data"]:
        m = lrow["period"]
        row = {k: lrow[k] for k in bc.LEGACY_FIELDS}
        if m in selected:
            btc, sats = selected[m]
            exact[m] = {"btc_per_house": format(btc, "f"), "sat_per_house": format(sats, "f")}
            row["btc_per_house"], row["sat_per_house"] = float(btc), float(sats)
        else:
            row["btc_per_house"] = row["sat_per_house"] = None
        row["btc_meta"] = _meta(m, selected, built_btc)
        rows.append(row)
    man = snap["man"]
    root = {"contract": bc.CONTRACT, "status": "PRIVATE_CANDIDATE", "method_id": man["method_id"], "parser_version": man["parser_version"],
            "exception_policy_version": man["exception_policy_version"], "quality_version": man["quality_version"],
            "snapshot_id": snap["snapshot_id"], "derived_values_sha256": man["derived_values_sha256"], "source_windows": man["source_windows"],
            "cbs_input_sha256": cbs_sha, "legacy_sha256": bc.sha256(legacy_bytes), "first_value_month": bc.FIRST_VALUE_MONTH,
            "early_history_numeric": False, "publication_authorized": False, "release_gate": "CLOSED", "sources": SOURCES}
    candidate = {"data": rows, "btc": root}
    summary = bc.validate_candidate(candidate, legacy_bytes, exact)
    summary.update({"snapshot_id": snap["snapshot_id"], "replay": replay["status"], "raw_source_bytes": replay["raw_source_bytes"],
                    "derived_values_sha256": man["derived_values_sha256"], "exact_sha256": bc.sha256(bc.serialize(exact))})
    return candidate, exact, summary


def revision_checks(baseline_dir, new_dir, cbs_csv) -> dict:
    """Targeted historical revision control between two vintages: CM and ECB day by day (days only), CBS by input hash.
    Any revision or missing historical value means the candidate must not be rebuilt silently: a new review is required."""
    old, new = b4.load_snapshot(baseline_dir), b4.load_snapshot(new_dir)
    out = {"cm": b4.revision_report(old["cm_daily"], new["cm_daily"]), "ecb": b4.revision_report(old["ecb_daily"], new["ecb_daily"]),
           "cbs": "UNCHANGED" if old["cbs_input_sha256"] == _sha(cbs_csv) == new["cbs_input_sha256"] else "CBS_REVISED_OR_UNVERIFIED"}
    bad = [k for k in ("cm", "ecb") if out[k]["status"] in ("HISTORICAL_REVISION", "MISSING_HISTORICAL")] + (["cbs"] if out["cbs"] != "UNCHANGED" else [])
    out["status"] = "REVIEW_REQUIRED" if bad else "CLEAN"
    out["revised_sources"] = bad
    return out


def write_private(directory, candidate: dict, exact: dict) -> dict:
    """Exclusive creation in an explicit new/empty directory; never overwrites."""
    d = Path(directory)
    if d.exists() and (not d.is_dir() or any(d.iterdir())):
        raise CandidateError(f"{d} exists and is not an empty directory")
    d.mkdir(parents=True, exist_ok=True)
    out = {}
    for name, payload in (("candidate.json", candidate), ("exact_values.json", exact)):
        blob = bc.serialize(payload)
        with open(d / name, "xb") as fh:
            fh.write(blob)
        out[name] = bc.sha256(blob)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="BTC-06C private production candidate (no publication)")
    ap.add_argument("--snapshot", required=True, help="verified BTC-05D vintage snapshot directory")
    ap.add_argument("--cbs-csv", required=True)
    ap.add_argument("--legacy-json", required=True, help="the approved legacy payload (read only)")
    ap.add_argument("--out-dir", help="explicit new directory for the private candidate; omit to only validate")
    ap.add_argument("--compare-snapshot", help="newer vintage: run the historical revision controls against --snapshot")
    a = ap.parse_args(argv)
    try:
        if a.compare_snapshot:
            res = revision_checks(a.snapshot, a.compare_snapshot, a.cbs_csv)
            print("SUMMARY revision_checks", json.dumps(res, sort_keys=True))
            return 0 if res["status"] == "CLEAN" else 1
        candidate, exact, summary = build_candidate(a.snapshot, a.cbs_csv, a.legacy_json)
        if a.out_dir:
            summary["written"] = write_private(a.out_dir, candidate, exact)
    except (b4.Btc04eError, bc.BtcContractError, OSError, ValueError) as exc:
        print("DEFECT", type(exc).__name__, str(exc)[:300])
        return 1
    print("SUMMARY candidate", json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
