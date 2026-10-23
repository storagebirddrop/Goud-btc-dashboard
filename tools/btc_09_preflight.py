"""BTC-09: final private-input release preflight, historical-vs-regenerated candidate comparison and independent value recomputation.

PRIVATE tool for an authorized private environment (the runner of the manual BTC-09 workflow). Reads a verified vintage snapshot and the real
candidate; writes NOTHING public and no price: the report holds hashes, counts, booleans and changed JSON KEY PATHS only. It registers no release
record and changes no pin: the only approval it ever builds is a SYNTHETIC in-memory one, used to exercise `release_preflight` and its negative cases.

Checks (each fails closed; exit 0 only when all hold):
  1. regenerate the candidate from the snapshot under the CURRENT calculation code (offline; optionally inside an empty network namespace);
  2. compare it with the historical candidate: every BTC/satoshi value, private state, status and quality must be identical; preview differences are
     allowed only on explained key paths (calculation commit, source attribution wording);
  3. recompute every candidate value independently (plain Decimal from the daily files and the CBS CSV, no etl code) and compare;
  4. month/quality scope of the standard profile (contiguous interval, class counts, no Q3, 2011-06 withheld);
  5. `release_preflight` with a synthetic approval on the REAL private inputs plus a negative battery (every case must be refused).

Usage: python -m tools.btc_09_preflight --snapshot DIR --cbs-csv CSV --legacy-json JSON --historical-dir DIR --out-dir NEW_DIR --report FILE [--isolated]
"""
from __future__ import annotations

import argparse
import calendar
import json
import os
import subprocess
import sys
from decimal import Decimal, localcontext
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etl import btc_contract as bc  # noqa: E402
from tools import btc_06c_candidate as cand  # noqa: E402

PROFILE_FIRST, PROFILE_LAST, PROFILE_COUNT = "2014-02", "2026-08", 151
PROFILE_CLASSES = {"Q2": 27, "Q1_CANDIDATE": 124}
# Preview paths (list indices collapsed to []) whose bytes may legitimately differ between the historical and the regenerated candidate:
# the hash-bound calculation commit and the corrected source attribution wording (BTC-08B). Anything else is an unexplained change.
EXPLAINED_PATHS = {"btc.provenance.calculation_git_commit", "btc.sources[].attribution"}
REL_TOL = Decimal("1e-25")


class PreflightError(Exception):
    pass


# ------------------------------------------------------------------ comparison (values never leave this function)
def key_paths_diff(a, b, path="") -> set:
    """Key paths (indices collapsed) at which two JSON documents differ. Values are never returned."""
    if type(a) is not type(b):
        return {path or "<root>"}
    if isinstance(a, dict):
        out = set()
        for k in sorted(set(a) | set(b)):
            sub = f"{path}.{k}" if path else k
            if k not in a or k not in b:
                out.add(sub)
            else:
                out |= key_paths_diff(a[k], b[k], sub)
        return out
    if isinstance(a, list):
        if len(a) != len(b):
            return {path + "[]#length"}
        out = set()
        for x, y in zip(a, b):
            out |= key_paths_diff(x, y, path + "[]")
        return out
    return set() if a == b else {path or "<root>"}


def compare_candidates(hist_preview, hist_sidecar, new_preview, new_sidecar) -> dict:
    hm, nm = hist_sidecar["months"], new_sidecar["months"]
    same_months = sorted(hm) == sorted(nm)
    value_diffs = sum(1 for m in set(hm) & set(nm) if hm[m] != nm[m])
    rows_h = {r["period"]: r for r in hist_preview["data"]}
    rows_n = {r["period"]: r for r in new_preview["data"]}
    meta_diffs = sum(1 for p in set(rows_h) | set(rows_n) if rows_h.get(p) != rows_n.get(p))
    paths = key_paths_diff(hist_preview, new_preview)
    unexplained = sorted(p for p in paths if not any(p == e or p.startswith(e + ".") for e in EXPLAINED_PATHS))
    return {"same_month_set": same_months, "months": len(nm), "value_differences": value_diffs, "preview_row_differences": meta_diffs,
            "contract_equal": hist_sidecar.get("contract") == new_sidecar.get("contract"),
            "preview_diff_paths": sorted(paths), "unexplained_preview_paths": unexplained,
            "identical_economics": same_months and value_diffs == 0 and meta_diffs == 0 and not unexplained}


# ------------------------------------------------------------------ independent recomputation (no etl code)
def _read_daily(path) -> dict:
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        day, _, val = line.partition(":")
        out[day] = Decimal(val) if val.strip() else None
    return out


def _house(csv_path) -> dict:
    out = {}
    for line in Path(csv_path).read_text(encoding="utf-8").splitlines()[1:]:
        d, s, v = line.split(",")
        if s == "nl_house_avg_eur":
            out[d] = Decimal(v)
    return out


def _month_mean(daily: dict, month: str, *, complete: bool):
    y, m = int(month[:4]), int(month[5:])
    n = calendar.monthrange(y, m)[1]
    vals = [daily.get(f"{month}-{d:02d}") for d in range(1, n + 1)]
    if complete and any(v is None for v in vals):
        return None
    got = [v for v in vals if v is not None]
    return sum(got) / len(got) if got else None


def independent_recompute(snapshot_dir, cbs_csv, sidecar) -> dict:
    cm, ecb, house = _read_daily(Path(snapshot_dir) / "cm_priceusd_daily.txt"), _read_daily(Path(snapshot_dir) / "ecb_usd_per_eur_daily.txt"), _house(cbs_csv)
    checked = bad = 0
    worst = Decimal(0)
    with localcontext() as ctx:
        ctx.prec = 80
        for month, entry in sorted(sidecar["months"].items()):
            if entry.get("private_state") != "CANDIDATE_VALUE":
                continue
            p, f, h = _month_mean(cm, month, complete=True), _month_mean(ecb, month, complete=False), house.get(month)
            checked += 1
            if p is None or f is None or h is None or p <= 0:
                bad += 1
                continue
            btc = h * f / p
            rel = abs(btc - Decimal(entry["btc_per_house"])) / btc
            rel_sat = abs(btc * 100000000 - Decimal(entry["sat_per_house"])) / (btc * 100000000)
            worst = max(worst, rel, rel_sat)
            if rel > REL_TOL or rel_sat > REL_TOL:
                bad += 1
    return {"months_checked": checked, "mismatches": bad, "max_relative_difference_below_1e-25": worst <= REL_TOL, "ok": checked > 0 and bad == 0}


# ------------------------------------------------------------------ scope and release preflight
def scope_report(composite, expect) -> dict:
    rows = {r["period"]: r for r in composite["data"]}
    pub = {p: r["btc_meta"]["quality"] for p, r in rows.items() if r["btc_meta"]["status"] == "PUBLISHED"}
    months = sorted(pub)
    first, last, count = expect
    counts = {}
    for q in pub.values():
        counts[q] = counts.get(q, 0) + 1
    def nxt(m):
        y, mo = int(m[:4]), int(m[5:])
        return f"{y + (mo == 12):04d}-{(mo % 12) + 1:02d}"
    contiguous = bool(months) and all(nxt(a) == b for a, b in zip(months, months[1:]))
    hold = rows.get("2011-06")
    return {"published_months": len(months), "first": months[0] if months else None, "last": months[-1] if months else None, "contiguous": contiguous,
            "quality_counts": counts, "no_q3": "Q3" not in counts, "june_2011_withheld": hold is None or hold["btc_meta"]["status"] != "PUBLISHED",
            "ok": bool(months) and months[0] == first and months[-1] == last and len(months) == count and contiguous and "Q3" not in counts
                  and (hold is None or hold["btc_meta"]["status"] != "PUBLISHED")}


def release_preflight_battery(preview, sidecar, legacy_bytes, months) -> dict:
    pv, sc = bc.serialize(preview), bc.serialize(sidecar)
    auth = {"release_id": "BTC09-SYNTHETIC-NOT-A-RELEASE", "decision_ref": "BTC09-SYNTHETIC-NOT-A-RELEASE", "months": months,
            "rights_review_ref": "BTC09-SYNTHETIC-NOT-A-RELEASE", "conflicting_contract_check": "VERIFIED", **bc.private_hashes(preview, sidecar)}
    composite = bc.compose_release(preview, sidecar, auth)
    blob = bc.serialize(composite)
    record = bc.record_template(composite, auth)
    record.update(owner_approval="APPROVED", approved_by="btc09-synthetic-in-memory", approved_on="n/a")

    def refused(fn):
        try:
            fn()
        except (bc.BtcContractError, bc.ReleaseDenied):  # ReleaseDenied is a BtcContractError; both listed for clarity
            return True
        return False

    positive = bc.release_preflight(blob, record, pv, sc, legacy_bytes) is record
    forged = json.loads(blob)
    row = next(r for r in forged["data"] if r["btc_meta"]["status"] == "PUBLISHED")
    row["btc_per_house"] = row["btc_per_house"] * 1.01
    row["sat_per_house"] = row["sat_per_house"] * 1.01
    forged_blob = bc.serialize(forged)
    forged_rec = dict(bc.record_template(forged, auth), owner_approval="APPROVED", approved_by="x", approved_on="n/a")
    quals = sorted(set(bc.quality_by_month(composite).values()))
    one_class = {q: q for q in quals}
    cases = {
        "pending_template": lambda: bc.release_preflight(blob, dict(record, private_sidecar_sha256=bc.PENDING), pv, sc, legacy_bytes),
        "owner_not_approved": lambda: bc.release_preflight(blob, dict(record, owner_approval="PENDING"), pv, sc, legacy_bytes),
        "extra_field": lambda: bc.release_preflight(blob, dict(record, extra="x"), pv, sc, legacy_bytes),
        "missing_field": lambda: bc.release_preflight(blob, {k: v for k, v in record.items() if k != "rollback_ref"}, pv, sc, legacy_bytes),
        "fewer_months": lambda: bc.release_preflight(blob, dict(record, authorized_months=record["authorized_months"][1:]), pv, sc, legacy_bytes),
        "wrong_quality_scope": lambda: bc.release_preflight(blob, dict(record, authorized_qualities=quals[:1]), pv, sc, legacy_bytes),
        "wrong_month_quality_mapping": lambda: bc.release_preflight(blob, dict(record, quality_by_month_sha256="0" * 64), pv, sc, legacy_bytes),
        "other_snapshot": lambda: bc.release_preflight(blob, dict(record, snapshot_id="btc04e-" + "0" * 16), pv, sc, legacy_bytes),
        "other_calculation_commit": lambda: bc.release_preflight(blob, dict(record, calculation_git_commit="0" * 40), pv, sc, legacy_bytes),
        "other_private_candidate": lambda: bc.release_preflight(blob, record, pv + b" ", sc, legacy_bytes),
        "other_private_sidecar": lambda: bc.release_preflight(blob, record, pv, sc + b" ", legacy_bytes),
        "wrong_rollback_bytes": lambda: bc.release_preflight(blob, record, pv, sc, legacy_bytes + b" "),
        "mutated_hash_consistent_payload": lambda: bc.release_preflight(forged_blob, forged_rec, pv, sc, legacy_bytes),
        "payload_not_canonical": lambda: bc.release_preflight(blob + b"\n", record, pv, sc, legacy_bytes),
    }
    del one_class
    results = {name: refused(fn) for name, fn in cases.items()}
    gate_alone_blind = False
    try:
        gate_alone_blind = bc.composite_release_gate(forged_blob, records=[forged_rec]) is forged_rec
    except bc.BtcContractError:
        gate_alone_blind = False
    reproduced = bc.reproduce_composite(record, pv, sc) == blob
    return {"positive_path": positive, "reproduce_byte_identical": reproduced, "rollback_target_ok": bc.rollback_target_ok(record, legacy_bytes),
            "negative_cases": results, "all_negative_refused": all(results.values()), "gate_alone_cannot_see_forged_payload": gate_alone_blind,
            "composite_sha256": bc.sha256(blob), "record_keys_exact": set(record) == bc.RECORD_KEYS, "registry_empty": bc.ARTIFACT_RECORDS == (),
            "ok": positive and reproduced and all(results.values())}


# ------------------------------------------------------------------ driver
def _load(directory):
    d = Path(directory)
    return json.loads((d / "candidate.json").read_bytes()), json.loads((d / "candidate_values.json").read_bytes())


def run(snapshot, cbs_csv, legacy_json, historical_dir, out_dir, expect=(PROFILE_FIRST, PROFILE_LAST, PROFILE_COUNT), expect_classes=None) -> dict:
    legacy_bytes = Path(legacy_json).read_bytes()
    preview, sidecar, summary = cand.build_candidate(snapshot, cbs_csv, legacy_json)
    written = cand.write_private(out_dir, preview, sidecar)
    hist_preview, hist_sidecar = _load(historical_dir)
    rep = {"schema": "btc09-preflight/1", "note": "no price, no BTC/satoshi value; hashes, counts, booleans and key paths only",
           "snapshot_id": summary.get("snapshot_id"), "replay": summary.get("replay"), "calculation_git_commit": preview["btc"]["provenance"]["calculation_git_commit"],
           "candidate_sha256": written["candidate.json"], "sidecar_sha256": written["candidate_values.json"],
           "historical_candidate_sha256": bc.sha256(bc.serialize(hist_preview)), "historical_sidecar_sha256": bc.sha256(bc.serialize(hist_sidecar))}
    rep["comparison"] = compare_candidates(hist_preview, hist_sidecar, preview, sidecar)
    rep["independent_recompute"] = independent_recompute(snapshot, cbs_csv, sidecar)
    months = [m for m in sorted(sidecar["months"]) if m >= expect[0]]
    auth_probe = {"release_id": "BTC09-SYNTHETIC-NOT-A-RELEASE", "decision_ref": "BTC09-SYNTHETIC-NOT-A-RELEASE", "months": months, "rights_review_ref": "BTC09-SYNTHETIC-NOT-A-RELEASE",
                  "conflicting_contract_check": "VERIFIED", **bc.private_hashes(preview, sidecar)}
    composite = bc.compose_release(preview, sidecar, auth_probe)
    rep["scope"] = scope_report(composite, expect)
    if expect_classes is not None:
        rep["scope"]["class_counts_match"] = rep["scope"]["quality_counts"] == expect_classes
        rep["scope"]["ok"] = rep["scope"]["ok"] and rep["scope"]["class_counts_match"]
    rep["release_preflight"] = release_preflight_battery(preview, sidecar, legacy_bytes, months)
    rep["ok"] = rep["replay"] == "IDENTICAL" and rep["comparison"]["identical_economics"] and rep["independent_recompute"]["ok"] and rep["scope"]["ok"] \
        and rep["release_preflight"]["ok"]
    return rep


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="BTC-09 private final release preflight (price-free report)")
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--cbs-csv", required=True)
    ap.add_argument("--legacy-json", required=True)
    ap.add_argument("--historical-dir", required=True, help="the historical candidate directory (candidate.json, candidate_values.json)")
    ap.add_argument("--out-dir", required=True, help="new empty directory for the regenerated private candidate")
    ap.add_argument("--report", required=True)
    ap.add_argument("--isolated", action="store_true", help="re-execute inside an empty network namespace (fail if unavailable)")
    ap.add_argument("--in-isolation", action="store_true", help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    if a.isolated and not a.in_isolation:
        from tools.btc_08a_verify_package import isolation_prefix
        prefix = isolation_prefix()
        if prefix is None:
            print("NETWORK ISOLATION UNAVAILABLE", file=sys.stderr)
            return 3
        args = [x for x in (argv if argv is not None else sys.argv[1:])]
        os.execvp(prefix[0], prefix + [sys.executable, "-m", "tools.btc_09_preflight", *args, "--in-isolation"])
    rep = run(a.snapshot, a.cbs_csv, a.legacy_json, a.historical_dir, a.out_dir, expect_classes=PROFILE_CLASSES)
    rep["network_isolated"] = bool(a.in_isolation)
    Path(a.report).write_text(json.dumps(rep, indent=1, sort_keys=True), encoding="utf-8")
    print("SUMMARY btc09", json.dumps({k: rep[k] for k in ("ok", "snapshot_id", "replay", "candidate_sha256", "sidecar_sha256", "calculation_git_commit", "network_isolated")}))
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
