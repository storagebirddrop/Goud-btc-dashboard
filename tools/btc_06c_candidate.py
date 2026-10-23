"""BTC-06C: PRIVATE production-candidate adapter for btc-monthly/1. Research side; NOTHING IS PUBLISHED.

Builds the PREVIEW payload (legacy rows + btc_per_house, sat_per_house, btc_meta + root block `btc`, every BTC value null and withheld) and a
private values sidecar from a verified BTC-05D vintage snapshot, the committed CBS csv and the approved legacy payload. It reuses the BTC-04E
calculation (CM_PRICEUSD_MONTHMEAN_C1_V1) and the BTC-05D snapshot/replay: no second pipeline, no network. Mandatory checks: snapshot
integrity with RETAINED CM bytes, offline replay IDENTICAL, the CBS csv hash recorded in the snapshot, the pinned legacy payload hash and
agreement of the legacy CBS column with the csv. Candidate values and PRIVATE candidate states live only in the sidecar and never in the public
`btc_meta.status` enum. Output goes to an explicit NEW directory and is never uploaded or committed.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from etl import btc_contract as bc  # noqa: E402
from tools import btc_04e_cm_replay as b4  # noqa: E402
from tools import btc_public_report as pr  # noqa: E402

SOURCES = [
    {"id": "coinmetrics_community_priceusd", "metric": "btc.PriceUSD.1d", "url": "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics",
     "license_url": "https://creativecommons.org/licenses/by-nc/4.0/", "attribution": "Coin Metrics Community, PriceUSD (dagelijkse USD-referentieprijs, CC BY-NC 4.0). Gewijzigd: rekenkundig gemiddelde per volledige UTC-kalendermaand, gedeeld door het maandgemiddelde van de ECB-koers; eigen berekening, geen publicatie van of onderschrijving door Coin Metrics"},
    {"id": "ecb_exr_d_usd", "metric": "EXR.D.USD.EUR.SP00.A", "url": "https://data.ecb.europa.eu/data/datasets/EXR/EXR.D.USD.EUR.SP00.A",
     "license_url": "https://www.ecb.europa.eu/services/using-our-site/disclaimer/html/index.en.html",
     "attribution": "Europese Centrale Bank, euro foreign exchange reference rate USD/EUR (EXR.D.USD.EUR.SP00.A); bron: ECB. Gewijzigd: rekenkundig gemiddelde van de geldige dagkoersen per kalendermaand; eigen berekening, geen officiële ECB-publicatie"},
    {"id": "cbs_85773NED_csv", "metric": "nl_house_avg_eur", "url": "https://opendata.cbs.nl/CBS/nl/dataset/85773NED/table",
     "license_url": "https://creativecommons.org/licenses/by/4.0/", "attribution": "CBS StatLine 85773NED, gemiddelde verkoopprijs bestaande koopwoningen (CC BY 4.0). Gebruikt als teller; BTC- en satoshi-per-woning zijn eigen berekeningen, geen CBS-publicatie"},
]
SIDECAR_CONTRACT = "btc-monthly/1-private-values"


class CandidateError(b4.Btc04eError):
    """A mandatory production-candidate check failed: no candidate is produced."""


def _sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git_commit() -> str:
    commit = os.environ.get("GITHUB_SHA") or subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", commit or ""):
        raise CandidateError("the calculation git commit cannot be established as a 40-hex commit")
    return commit


def candidate_months(built: dict, first_value_month=bc.DEFAULT_FROM) -> dict:
    """{month: (btc, sats) Decimals} eligible for the PRIVATE candidate values: a value, from the default start on and not HOLD. Eligibility
    here is never RELEASE_ELIGIBLE: releasing needs an exact owner record."""
    btc = {p.period: p.value for p in built["cbs_btc_per_house_cm_c1"].points}
    sats = {p.period: p.value for p in built["cbs_sats_per_house_cm_c1"].points}
    return {m: (btc[m], sats[m]) for m in sorted(btc) if btc[m] is not None and m >= first_value_month
            and b4.month_eligibility(m) == "RESEARCH_ONLY"}


def public_state(month: str, has_value: bool) -> tuple:
    """(status, missing_reason) of a PREVIEW month by the contract's priority: June HOLD, before support, outside the standard profile,
    release gate (publication not authorized), then concrete input problems."""
    if month in bc.HOLD_MONTHS:
        return "WITHHELD", bc.HOLD_MONTHS[month]
    if month < bc.SUPPORTED_FROM:
        return "MISSING", "BEFORE_SUPPORTED_MONTH"
    if month < bc.DEFAULT_FROM:
        return "WITHHELD", "NOT_AUTHORIZED_PERIOD"
    if has_value:
        return "WITHHELD", "PUBLICATION_NOT_AUTHORIZED"
    return "MISSING", "INCOMPLETE_PERIOD"


def build_candidate(snapshot_dir, cbs_csv, legacy_json) -> tuple:
    """-> (preview payload, private sidecar, value-free summary). Raises CandidateError / SnapshotError / BtcContractError."""
    snap = b4.load_snapshot(snapshot_dir)  # fail closed: hashes, versions, raw bytes vs normalized values
    if snap["raw_retention"] != "RETAINED":
        raise CandidateError("a production candidate needs the original Coin Metrics bytes (CM raw retention RETAINED and verified)")
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
    man = snap["man"]
    built = b4.build_from_daily(snap["cm_daily"], snap["ecb_daily"], house, man["coinmetrics"]["retrieved_at_utc"])
    selected = candidate_months(built)
    rows, values = [], {}
    for lrow in legacy["data"]:
        m = lrow["period"]
        status, reason = public_state(m, m in selected)
        row = {k: lrow[k] for k in bc.LEGACY_FIELDS}
        row["btc_per_house"] = row["sat_per_house"] = None  # preview: nothing is published, whatever the candidate values are
        row["btc_meta"] = {"quality": bc.quality_of(m), "status": status, "missing_reason": reason, "flags": bc.flags_for(m)}
        rows.append(row)
        if m in selected:
            values[m] = {"btc_per_house": format(selected[m][0], "f"), "sat_per_house": format(selected[m][1], "f"), "private_state": "CANDIDATE_VALUE"}
    root = {"contract_version": bc.CONTRACT, "method_id": man["method_id"], "parser_version": man["parser_version"],
            "quality_version": man["quality_version"], "exception_policy_version": man["exception_policy_version"], "units": dict(bc.UNITS),
            "coverage": {"supported_from": bc.SUPPORTED_FROM, "default_from": bc.DEFAULT_FROM, "authorized_from": None, "authorized_through": None,
                         "early_history_authorized": False},
            "release": {"id": None, "decision_ref": None, "publication_authorized": False},
            "provenance": {"snapshot_format": b4.SNAPSHOT_FORMAT, "snapshot_id": snap["snapshot_id"],
                           "snapshot_manifest_sha256": _sha(Path(snapshot_dir) / b4.SNAPSHOT_MANIFEST), "calculation_git_commit": git_commit(),
                           "cbs_input_sha256": cbs_sha, "cm_daily_sha256": man["coinmetrics"]["canonical_daily_sha256"],
                           "ecb_daily_sha256": man["ecb"]["canonical_daily_sha256"], "source_windows": man["source_windows"],
                           "derived_values_sha256": man["derived_values_sha256"], "derived_cutoff": snap["derived_cutoff"],
                           "cm_raw_retention": snap["raw_retention"], "ecb_raw_retention": "NOT_RETAINED",
                           "vintage_reference_utc": man["coinmetrics"]["retrieved_at_utc"], "time_basis": "CM_ACQUISITION_REFERENCE"},
            "sources": [dict(s) for s in SOURCES],
            "rights": {"assessment": "CONDITIONAL", "review_ref": None, "scope": "NON_COMMERCIAL", "conflicting_contract_check": "UNVERIFIED"}}
    preview = {"data": rows, "btc": root}
    sidecar = {"contract": SIDECAR_CONTRACT, "months": values,
               "qa": {"snapshot_id": snap["snapshot_id"], "candidate_months": len(values), "note": "private candidate values; never part of a public payload"}}
    summary = bc.validate_payload(preview, legacy_bytes)
    summary.update({"snapshot_id": snap["snapshot_id"], "replay": replay["status"], "raw_source_bytes": replay["raw_source_bytes"],
                    "derived_values_sha256": man["derived_values_sha256"], "candidate_value_months": len(values),
                    "sidecar_sha256": bc.sha256(bc.serialize(sidecar))})
    return preview, sidecar, summary


def verify_release_path(preview: dict, sidecar: dict) -> dict:
    """In-memory proof that the closed release path works on THIS candidate: compose, build the record template, approve it with a
    SYNTHETIC in-memory approval (never registered), pass the gate, and check that the default gate and tampered records still deny.
    Nothing here authorizes anything; the registry stays empty."""
    auth = {"release_id": "SYNTHETIC-VERIFICATION-ONLY", "decision_ref": "SYNTHETIC-VERIFICATION-ONLY", "months": sorted(sidecar["months"]),
            "rights_review_ref": "SYNTHETIC-VERIFICATION-ONLY", "conflicting_contract_check": "VERIFIED", **bc.private_hashes(preview, sidecar)}
    composite = bc.compose_release(preview, sidecar, auth)
    blob = bc.serialize(composite)
    record = bc.record_template(composite, auth)
    record.update(owner_approval="APPROVED", approved_by="synthetic-in-memory-check", approved_on="n/a")
    passed = bc.composite_release_gate(blob, records=[record]) is record
    denied = {}
    for label, call in (("default_registry", lambda: bc.composite_release_gate(blob)),
                        ("tampered_hash", lambda: bc.composite_release_gate(blob, records=[dict(record, composite_sha256="0" * 64)])),
                        ("fewer_months", lambda: bc.composite_release_gate(blob, records=[dict(record, authorized_months=record["authorized_months"][1:])])),
                        ("pending_approval", lambda: bc.composite_release_gate(blob, records=[dict(record, owner_approval="PENDING")])),
                        ("other_quality_scope", lambda: bc.composite_release_gate(blob, records=[dict(record, authorized_qualities=["Q2"])])),
                        ("other_snapshot", lambda: bc.composite_release_gate(blob, records=[dict(record, snapshot_id="btc04e-" + "0" * 16)])),
                        ("owner_fields_pending", lambda: bc.composite_release_gate(blob, records=[dict(record, private_sidecar_sha256=bc.PENDING)]))):
        try:
            call()
            denied[label] = False
        except bc.ReleaseDenied:
            denied[label] = True
    if not passed or not all(denied.values()) or bc.ARTIFACT_RECORDS != ():
        raise CandidateError(f"release path verification failed: passed={passed} denied={denied}")
    pub = [r["period"] for r in composite["data"] if r["btc_meta"]["status"] == "PUBLISHED"]
    return {"status": "NOT_AUTHORIZED_IN_MEMORY_VERIFICATION_ONLY", "composite_sha256": bc.sha256(blob), "published_months": len(pub),
            "first": pub[0], "last": pub[-1], "btc_selection_sha256": record["btc_selection_sha256"],
            "legacy_projection_sha256": record["legacy_projection_sha256"], "denied": denied, "registry_records": len(bc.ARTIFACT_RECORDS)}


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


def write_private(directory, preview: dict, sidecar: dict) -> dict:
    """Exclusive creation in an explicit new/empty directory; never overwrites."""
    d = Path(directory)
    if d.exists() and (not d.is_dir() or any(d.iterdir())):
        raise CandidateError(f"{d} exists and is not an empty directory")
    d.mkdir(parents=True, exist_ok=True)
    out = {}
    for name, payload in (("candidate.json", preview), ("candidate_values.json", sidecar)):
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
    ap.add_argument("--verify-release-path", action="store_true", help="in-memory proof of the closed release path with a SYNTHETIC approval")
    a = ap.parse_args(argv)
    try:
        if a.compare_snapshot:
            res = revision_checks(a.snapshot, a.compare_snapshot, a.cbs_csv)
            pr.assert_value_free(res)
            print("SUMMARY revision_checks", json.dumps(res, sort_keys=True))
            return 0 if res["status"] == "CLEAN" else 1
        preview, sidecar, summary = build_candidate(a.snapshot, a.cbs_csv, a.legacy_json)
        if a.verify_release_path:
            summary["release_path"] = verify_release_path(preview, sidecar)
        if a.out_dir:
            summary["written"] = write_private(a.out_dir, preview, sidecar)
    except (b4.Btc04eError, bc.BtcContractError, OSError, ValueError) as exc:
        print("DEFECT", type(exc).__name__, pr.safe_text(exc, 300))
        return 1
    try:
        pr.assert_value_free(summary)  # public log: refuse (and print nothing) if the summary carries anything numeric-looking
    except pr.PublicReportError as exc:
        print("DEFECT", type(exc).__name__, pr.safe_text(exc, 200))
        return 1
    print("SUMMARY candidate", json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
