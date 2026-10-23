"""BTC-10 / D07: PRIVATE preparation of the exact Bitcoin release artifact (candidate, public composite bytes, unapproved `btc-release-record/2` template).

Runs only in an authorized private environment (the manual BTC-10 workflow on a runner, or the owner's machine). The composite bytes and the candidate contain real
prices and are written ONLY to `--private-dir`; the manifest and the record template written for review are price-free (hashes, counts, booleans, ids).
It registers nothing, pins nothing, deploys nothing; the only approval it builds is a SYNTHETIC in-memory one for `release_preflight`.

Steps (each fails closed; exit 0 only when all hold):
  1. calculation identity: the calculation code of HEAD equals the frozen commit C (`git diff C HEAD` over CALC_PATHS is empty) and C is used as `calculation_git_commit`;
  2. rebuild the candidate from the restored snapshot; compare with the historical candidate (values, states, qualities identical; explained preview paths only);
  3. independent Decimal recomputation of every value; scope 2014-02..2026-08, 151 months, Q2 27, Q1_CANDIDATE 124, no Q3, 2011-06 withheld;
  4. second candidate build in a SEPARATE process must be byte-identical;
  5. compose the public composite for the PROPOSED release identity, regenerate it independently from the private inputs, build the unapproved record template;
  6. `release_preflight` with a synthetic in-memory approval + the 14-case negative battery on the proposed identity.

Usage: python -m tools.btc_10_d07 --snapshot DIR --cbs-csv CSV --legacy-json JSON --historical-dir DIR --private-dir NEW_DIR --calc-commit C40
         --manifest-out FILE --template-out FILE [--release-id ID --decision-ref REF --rights-ref REF] [--isolated]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etl import btc_contract as bc  # noqa: E402
from tools import btc_06c_candidate as cand  # noqa: E402
from tools import btc_09_preflight as pf  # noqa: E402
from tools.btc_08a_verify_package import CALC_PATHS  # noqa: E402

# PROPOSED identifiers (not owner-approved): the owner may replace them; every change alters the composite SHA-256 and requires re-running this tool.
PROPOSED_IDS = {"release_id": "BTC-REL-2026-10-001", "decision_ref": "PC-BTC10-D07-2026-10-001", "rights_review_ref": "PC-BTC09-A1+PC-BTC07D-CM10"}
SYNTHETIC_APPROVER = "SYNTHETIC-D07-PREFLIGHT-NOT-AN-OWNER"


class D07Error(Exception):
    pass


def calc_identity(calc_commit: str, repo: Path = ROOT) -> dict:
    """The calculation code (CALC_PATHS) of the working tree/HEAD must be byte-identical to the frozen commit C."""
    if not (len(calc_commit) == 40 and all(c in "0123456789abcdef" for c in calc_commit)):
        raise D07Error("calc commit must be a full 40-hex SHA")
    def git(*a):
        return subprocess.run(["git", *a], cwd=repo, capture_output=True, text=True)
    if git("cat-file", "-e", f"{calc_commit}^{{commit}}").returncode != 0:
        raise D07Error("calculation commit is not available in this checkout (fetch it)")
    same = git("diff", "--quiet", calc_commit, "HEAD", "--", *CALC_PATHS).returncode == 0
    dirty = bool(git("status", "--porcelain", "--", *CALC_PATHS).stdout.strip())
    return {"calculation_commit": calc_commit, "head": git("rev-parse", "HEAD").stdout.strip(), "calc_paths_identical_to_C": same, "calc_paths_clean": not dirty,
            "ok": same and not dirty}


def prepare(snapshot, cbs_csv, legacy_json, historical_dir, private_dir, calc_commit, ids=None, repo: Path = ROOT, check_identity=True) -> tuple:
    """Returns (manifest, record_template). Private bytes are written under `private_dir` only."""
    ids = ids or PROPOSED_IDS
    ident = calc_identity(calc_commit, repo) if check_identity else {"calculation_commit": calc_commit, "ok": True, "skipped": True}
    if not ident["ok"]:
        raise D07Error("calculation code differs from the frozen calculation commit")
    legacy_bytes = Path(legacy_json).read_bytes()
    private = Path(private_dir)
    old = os.environ.get("GITHUB_SHA")
    os.environ["GITHUB_SHA"] = calc_commit  # the candidate binds `calculation_git_commit` from GITHUB_SHA
    try:
        preview, sidecar, summary = cand.build_candidate(snapshot, cbs_csv, legacy_json)
        written = cand.write_private(private / "candidate", preview, sidecar)
        second = subprocess.run([sys.executable, "-m", "tools.btc_06c_candidate", "--snapshot", str(snapshot), "--cbs-csv", str(cbs_csv), "--legacy-json", str(legacy_json),
                                 "--out-dir", str(private / "candidate_again")], cwd=repo, capture_output=True, text=True, env=dict(os.environ, GITHUB_SHA=calc_commit))
    finally:
        if old is None:
            os.environ.pop("GITHUB_SHA", None)
        else:
            os.environ["GITHUB_SHA"] = old
    if second.returncode != 0:
        raise D07Error("second candidate build failed")
    again = {n: bc.sha256((private / "candidate_again" / n).read_bytes()) for n in ("candidate.json", "candidate_values.json")}
    hist_preview, hist_sidecar = pf._load(historical_dir)
    comparison = pf.compare_candidates(hist_preview, hist_sidecar, preview, sidecar)
    recompute = pf.independent_recompute(snapshot, cbs_csv, sidecar)
    months = [m for m in sorted(sidecar["months"]) if m >= pf.PROFILE_FIRST]
    auth = {**ids, "months": months, "conflicting_contract_check": "VERIFIED", **bc.private_hashes(preview, sidecar)}
    composite = bc.compose_release(preview, sidecar, auth)
    blob = bc.serialize(composite)
    (private / "monthly.composite.json").write_bytes(blob)  # PRIVATE: real prices
    scope = pf.scope_report(composite, (pf.PROFILE_FIRST, pf.PROFILE_LAST, pf.PROFILE_COUNT))
    scope["class_counts_match"] = scope["quality_counts"] == pf.PROFILE_CLASSES
    scope["ok"] = scope["ok"] and scope["class_counts_match"]
    template = bc.record_template(composite, auth)
    pv, sc = bc.serialize(preview), bc.serialize(sidecar)
    regenerated = bc.reproduce_composite(template, pv, sc) == blob
    approved = dict(template, owner_approval="APPROVED", approved_by=SYNTHETIC_APPROVER, approved_on="SYNTHETIC-NOT-A-DATE")  # in memory only, never persisted
    preflight_ok = bc.release_preflight(blob, approved, pv, sc, legacy_bytes) is approved
    battery = pf.release_preflight_battery(preview, sidecar, legacy_bytes, months, ids=ids)
    template_unapproved = template["owner_approval"] == "PENDING" and template["approved_by"] == "" and template["approved_on"] == "" and set(template) == bc.RECORD_KEYS
    manifest = {
        "schema": "btc10-d07-manifest/1", "status": "NOT AUTHORIZED FOR PUBLICATION", "record_status": "PENDING", "note": "no price, no BTC/satoshi value; hashes, counts, ids, booleans",
        "proposed_identity": dict(ids, state="PROPOSED, not owner-approved"),
        "source": {"snapshot_id": template["snapshot_id"], "snapshot_manifest_sha256": template["snapshot_manifest_sha256"], "provenance_sha256": template["provenance_sha256"],
                   "cbs_input_sha256": template["cbs_input_sha256"]},
        "calculation": {"commit": calc_commit, "identity": ident, "method_id": template["method_id"], "quality_version": template["quality_version"],
                        "exception_policy_version": template["exception_policy_version"]},
        "hashes": {"candidate_preview_sha256": written["candidate.json"], "private_sidecar_sha256": written["candidate_values.json"], "public_composite_sha256": bc.sha256(blob),
                   "btc_selection_sha256": template["btc_selection_sha256"], "legacy_projection_sha256": template["legacy_projection_sha256"],
                   "quality_by_month_sha256": template["quality_by_month_sha256"], "historical_candidate_sha256": bc.sha256(bc.serialize(hist_preview)),
                   "historical_sidecar_sha256": bc.sha256(bc.serialize(hist_sidecar))},
        "separate_process_rebuild_identical": again == {"candidate.json": written["candidate.json"], "candidate_values.json": written["candidate_values.json"]},
        "comparison_with_historical": comparison, "independent_recompute": recompute, "scope": scope, "composite_regenerated_byte_identical": regenerated,
        "synthetic_preflight_positive": preflight_ok, "negative_battery": battery, "template_unapproved_and_complete": template_unapproved, "replay": summary.get("replay"),
        "registry_empty": bc.ARTIFACT_RECORDS == (), "composite_bytes_location": "PRIVATE working storage only (not in the repository, not in public artifacts)"}
    manifest["ok"] = (ident["ok"] and manifest["separate_process_rebuild_identical"] and comparison["identical_economics"] and recompute["ok"] and scope["ok"] and regenerated
                      and preflight_ok and battery["ok"] and template_unapproved and summary.get("replay") == "IDENTICAL" and manifest["registry_empty"]
                      and written["candidate_values.json"] == bc.sha256(bc.serialize(hist_sidecar)))
    return manifest, template


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="BTC-10 / D07 private release artifact preparation (price-free manifest)")
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--cbs-csv", required=True)
    ap.add_argument("--legacy-json", required=True)
    ap.add_argument("--historical-dir", required=True)
    ap.add_argument("--private-dir", required=True, help="new empty directory OUTSIDE the repository for the private bytes")
    ap.add_argument("--calc-commit", required=True)
    ap.add_argument("--manifest-out", required=True)
    ap.add_argument("--template-out", required=True)
    ap.add_argument("--release-id", default=PROPOSED_IDS["release_id"])
    ap.add_argument("--decision-ref", default=PROPOSED_IDS["decision_ref"])
    ap.add_argument("--rights-ref", default=PROPOSED_IDS["rights_review_ref"])
    ap.add_argument("--isolated", action="store_true", help="re-execute inside an empty network namespace (fail if unavailable)")
    ap.add_argument("--in-isolation", action="store_true", help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    private = Path(a.private_dir).resolve()
    if ROOT in (private, *private.parents):
        raise SystemExit("the private directory must be outside the repository")
    if private.exists() and any(private.iterdir()):
        raise SystemExit("the private directory must be new or empty")
    if a.isolated and not a.in_isolation:
        from tools.btc_08a_verify_package import isolation_prefix
        prefix = isolation_prefix()
        if prefix is None:
            print("NETWORK ISOLATION UNAVAILABLE", file=sys.stderr)
            return 3
        os.execvp(prefix[0], prefix + [sys.executable, "-m", "tools.btc_10_d07", *(argv if argv is not None else sys.argv[1:]), "--in-isolation"])
    private.mkdir(parents=True, exist_ok=True)
    ids = {"release_id": a.release_id, "decision_ref": a.decision_ref, "rights_review_ref": a.rights_ref}
    manifest, template = prepare(a.snapshot, a.cbs_csv, a.legacy_json, a.historical_dir, private, a.calc_commit, ids)
    manifest["network_isolated"] = bool(a.in_isolation)
    Path(a.manifest_out).write_text(json.dumps(manifest, indent=1, sort_keys=True), encoding="utf-8")
    Path(a.template_out).write_text(json.dumps(template, indent=1, sort_keys=True), encoding="utf-8")
    h = manifest["hashes"]
    print("SUMMARY btc10", json.dumps({"ok": manifest["ok"], "candidate": h["candidate_preview_sha256"], "sidecar": h["private_sidecar_sha256"], "composite": h["public_composite_sha256"]}))
    return 0 if manifest["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
