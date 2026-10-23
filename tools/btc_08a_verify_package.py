"""BTC-08A: independent restore + verification of a BTC-07E-A vintage package, for the OWNER's durable copy (private; price-free output).

It only chains the EXISTING tools in a fresh directory and compares hashes; it adds no method, no source and no release logic:
  1. the SHA-256 of the package file must equal the external anchor (the anchor is recorded OUTSIDE the storage location);
  2. optional `--calc-commit`: the package was packed at that commit and `calculation_git_commit` is hash-bound into the candidate preview, so the
     calculation code (etl/, the four BTC tools, the pins) must be byte-identical to that commit; the commit is then used for the rebuild;
  3. `tools.btc_07b_package restore` (all internal manifest hashes, replay IDENTICAL);
  4. the candidate is rebuilt from the restored snapshot with `tools.btc_06c_candidate` and its hashes are compared with the expected values;
  5. an OFFLINE replay of the restored snapshot inside an empty network namespace; isolation is proven by a failing connect probe.
Output: one JSON document with hashes, counts and booleans only (no price, no BTC/satoshi value). Exit 0 only when every check holds.

Usage: python -m tools.btc_08a_verify_package --package P.tar --expect-sha256 ANCHOR --dest NEW_DIR [--calc-commit SHA40]
         [--expect-candidate-sha256 H] [--expect-sidecar-sha256 H] [--expect-snapshot-id ID] [--expect-derived-sha256 H]"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CALC_PATHS = ["etl", "tools/btc_04e_cm_replay.py", "tools/btc_06c_candidate.py", "tools/btc_07b_package.py", "tools/btc_public_report.py", "data/fixtures/btc04e"]
CBS, LEGACY = "data/cbs-housing.csv", "frontend/public/data/monthly.json"


def sha(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def run(cmd, env=None):
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, env=env)
    return p.returncode, p.stdout + p.stderr


def isolation_prefix():
    """An argv prefix that runs a command in an EMPTY network namespace, proven by a failing connect; None when unavailable."""
    probe = [sys.executable, "-c", "import socket;socket.create_connection(('1.1.1.1',53),2)"]
    me, path = getpass.getuser(), os.environ.get("PATH", "")
    for prefix in (["unshare", "-rn"], ["sudo", "-n", "unshare", "-n", "--", "sudo", "-n", "-u", me, "env", f"PATH={path}"]):
        try:
            ok = run(prefix + ["true"])[0] == 0
            blocked = ok and run(prefix + probe)[0] != 0
        except OSError:
            continue
        if ok and blocked:
            return prefix
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="BTC-08A independent restore of a vintage package (price-free)")
    ap.add_argument("--package", required=True)
    ap.add_argument("--expect-sha256", required=True, help="external anchor of the package file")
    ap.add_argument("--dest", required=True, help="new, empty directory OUTSIDE the repository")
    ap.add_argument("--calc-commit")
    ap.add_argument("--expect-candidate-sha256")
    ap.add_argument("--expect-sidecar-sha256")
    ap.add_argument("--expect-snapshot-id")
    ap.add_argument("--expect-derived-sha256")
    a = ap.parse_args(argv)
    dest = Path(a.dest).resolve()
    if ROOT in (dest, *dest.parents):
        raise SystemExit("the destination must be outside the repository")
    if dest.exists() and any(dest.iterdir()):
        raise SystemExit("the destination must be new or empty")
    R: dict = {"schema": "btc08a-verify/1", "checks": {}}
    ck = R["checks"]
    ck["package_sha256_equals_anchor"] = (R.setdefault("package_sha256", sha(a.package))) == a.expect_sha256.lower()
    if not ck["package_sha256_equals_anchor"]:
        print(json.dumps(R, indent=1, sort_keys=True))
        return 2
    env = dict(os.environ)
    if a.calc_commit:
        if not re.fullmatch(r"[0-9a-f]{40}", a.calc_commit):
            raise SystemExit("--calc-commit must be a 40-hex commit")
        have = run(["git", "cat-file", "-e", f"{a.calc_commit}^{{commit}}"])[0] == 0
        same = have and run(["git", "diff", "--quiet", a.calc_commit, "HEAD", "--"] + CALC_PATHS)[0] == 0
        ck["calculation_code_identical_to_calc_commit"] = bool(same)
        R["calc_commit"], R["commit_available_locally"] = a.calc_commit, have
        if not same:
            print(json.dumps(R, indent=1, sort_keys=True))
            return 3
        env["GITHUB_SHA"] = a.calc_commit
    dest.mkdir(parents=True, exist_ok=True)
    rc, out = run([sys.executable, "-m", "tools.btc_07b_package", "restore", "--package", a.package, "--expect-sha256", a.expect_sha256, "--dest", str(dest / "restore")], env)
    m = re.search(r"EVIDENCE (\{.*\})", out)
    ev = json.loads(m.group(1)) if m else {}
    ck["restore_verified"] = rc == 0 and ev.get("status") == "RESTORE_VERIFIED_LOCAL" and bool(ev.get("compared")) and all(ev["compared"].values())
    ck["restore_replay_identical"] = ev.get("replay") == "IDENTICAL"
    R["restore"] = {"status": ev.get("status"), "snapshot_manifest_sha256": (ev.get("hashes") or {}).get("snapshot_manifest_sha256"), "raw_source_bytes": ev.get("raw_source_bytes")}
    if not ck["restore_verified"]:
        print(json.dumps(R, indent=1, sort_keys=True))
        return 4
    rc, out = run([sys.executable, "-m", "tools.btc_06c_candidate", "--snapshot", str(dest / "restore/snapshot"), "--cbs-csv", CBS, "--legacy-json", LEGACY,
                   "--out-dir", str(dest / "candidate"), "--verify-release-path"], env)
    m = re.search(r"SUMMARY candidate (\{.*\})", out)
    s = json.loads(m.group(1)) if m else {}
    cand, side = sha(dest / "candidate/candidate.json") if (dest / "candidate/candidate.json").exists() else None, sha(dest / "candidate/candidate_values.json") if (dest / "candidate/candidate_values.json").exists() else None
    R["candidate"] = {"snapshot_id": s.get("snapshot_id"), "candidate_sha256": cand, "sidecar_sha256": side, "derived_values_sha256": s.get("derived_values_sha256"), "candidate_value_months": s.get("candidate_value_months"),
                      "published_months": s.get("published_months"), "replay": s.get("replay"), "legacy_sha256": s.get("legacy_sha256")}
    ck["candidate_rebuilt_replay_identical"] = rc == 0 and s.get("replay") == "IDENTICAL" and s.get("published_months") == 0
    ck["rebuilt_equals_packed_candidate_and_sidecar"] = cand == (ev.get("hashes") or {}).get("candidate_sha256", cand) and side == (ev.get("hashes") or {}).get("sidecar_sha256")
    for key, want, got in (("candidate", a.expect_candidate_sha256, cand), ("sidecar", a.expect_sidecar_sha256, side), ("snapshot_id", a.expect_snapshot_id, s.get("snapshot_id")), ("derived", a.expect_derived_sha256, s.get("derived_values_sha256"))):
        if want:
            ck[f"expected_{key}_matches"] = got == want
    prefix = isolation_prefix()
    R["network_isolation"] = "EMPTY_NETWORK_NAMESPACE_PROVEN" if prefix else "NOT_ISOLATED"
    rc, out = run((prefix or []) + [sys.executable, "-m", "tools.btc_04e_cm_replay", "--replay-snapshot", str(dest / "restore/snapshot"), "--cbs-csv", str(dest / "restore/inputs/cbs-housing.csv")], env)
    m = re.search(r"REPLAY (\{.*\})", out)
    rp = json.loads(m.group(1)) if m else {}
    R["offline_replay"] = {"status": rp.get("status"), "derived_values_sha256": rp.get("derived_values_sha256")}
    ck["offline_replay_identical"] = rc == 0 and rp.get("status") == "IDENTICAL" and rp.get("derived_values_sha256") == s.get("derived_values_sha256")
    ck["offline_replay_network_isolated"] = prefix is not None
    R["all_checks_pass"] = all(ck.values())
    print(json.dumps(R, indent=1, sort_keys=True))
    return 0 if R["all_checks_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
