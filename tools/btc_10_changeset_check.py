"""BTC-10 / D07: deterministic release-change-set check, three-commit model C -> B -> R.

  C  frozen calculation commit: the candidate and the release record bind `calculation_git_commit = C`; it is never rebased to B or R.
  B  integrated technical baseline on main (BTC-10 tooling, workflow, tests and docs merged): its calculation code must be byte-identical to C, and its production
     state must still be the closed legacy state (registry `()`, pin list `[]`, public payload = pinned legacy payload).
  R  future production release commit, a descendant of B.

Checks (all fail closed):
  1. C, B and R resolve to commits; C is an ancestor of B and B an ancestor of R.
  2. C -> B: the calculation paths (CALC_PATHS from the BTC-08A contract) are byte-identical.
  3. The release record binds C (not B, not R) and is approved, non-synthetic, with the exact key set.
  4. B -> R may differ ONLY in:
       * `etl/btc_contract.py`: the value of `ARTIFACT_RECORDS` (AST comparison of the rest of the module); `()` at B, exactly the one approved record at R;
       * `frontend/src/btc.ts`: the list literal of `BTC_APPROVED_COMPOSITE_SHA256`; `[]` at B, exactly `[record.composite_sha256]` at R;
       * `frontend/public/data/monthly.json`: SHA-256 equals `record.public_payload_sha256`, legacy projection equals the pinned legacy payload, and
         `composite_release_gate` opens for these exact bytes; the record's rollback target equals the SHA-256 of B's public payload;
       * files under `docs/` and `tests/`.
     Anything else (workflows, tools, other frontend files, other calculation files) is rejected.

Usage: python -m tools.btc_10_changeset_check --repo . --calc-commit C --baseline-commit B --release-commit R --record RECORD.json
Exit 0 only when every check holds. Output: booleans, counts and hashes only."""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etl import btc_contract as bc  # noqa: E402
from tools.btc_08a_verify_package import CALC_PATHS  # noqa: E402

CONTRACT, PINS, PUBLIC = "etl/btc_contract.py", "frontend/src/btc.ts", "frontend/public/data/monthly.json"
FREE_PREFIXES = ("docs/", "tests/")
PIN_RE = re.compile(r"(export const BTC_APPROVED_COMPOSITE_SHA256:readonly string\[\]=)\[([^\]]*)\];")
PIN_ITEM_RE = re.compile(r"^\s*(?:(['\"])([0-9a-f]{64})\1\s*(?:,\s*|$))*$")


class ChangesetError(Exception):
    pass


def _git(repo, *args, raw=False):
    p = subprocess.run(["git", *args], cwd=repo, capture_output=True)
    if p.returncode != 0:
        raise ChangesetError(f"git {' '.join(args[:2])} failed: {p.stderr.decode()[:200]}")
    return p.stdout if raw else p.stdout.decode()


def _show(repo, commit, path):
    return _git(repo, "show", f"{commit}:{path}", raw=True)


def _under(path, prefixes):
    return any(path == p or path.startswith(p.rstrip("/") + "/") for p in prefixes)


def registry_of(source: str):
    """(normalized AST dump with ARTIFACT_RECORDS neutralized, literal value of ARTIFACT_RECORDS)."""
    tree = ast.parse(source)
    hits = [n for n in tree.body if (isinstance(n, ast.AnnAssign) and getattr(n.target, "id", None) == "ARTIFACT_RECORDS")
            or (isinstance(n, ast.Assign) and any(getattr(t, "id", None) == "ARTIFACT_RECORDS" for t in n.targets))]
    if len(hits) != 1:
        raise ChangesetError("etl/btc_contract.py must define ARTIFACT_RECORDS exactly once at module level")
    node = hits[0]
    value = ast.literal_eval(node.value)
    node.value = ast.Constant(None)
    return ast.dump(tree), value


def pins_of(source: str):
    """(source text with the pin list neutralized, list of pins; raises on any non-hash content)."""
    found = PIN_RE.findall(source)
    if len(found) != 1:
        raise ChangesetError("frontend/src/btc.ts must define BTC_APPROVED_COMPOSITE_SHA256 exactly once")
    inner = found[0][1]
    if not PIN_ITEM_RE.match(inner):
        raise ChangesetError("the pin list contains something other than 64-hex strings")
    return PIN_RE.sub(r"\1[];", source), re.findall(r"[0-9a-f]{64}", inner)


def _is_ancestor(repo, older, newer) -> bool:
    return subprocess.run(["git", "merge-base", "--is-ancestor", older, newer], cwd=repo, capture_output=True).returncode == 0


def check(repo, calc_commit: str, baseline_commit: str, release_commit: str, record: dict) -> dict:
    repo = Path(repo)
    c = _git(repo, "rev-parse", f"{calc_commit}^{{commit}}").strip()
    b = _git(repo, "rev-parse", f"{baseline_commit}^{{commit}}").strip()
    r = _git(repo, "rev-parse", f"{release_commit}^{{commit}}").strip()
    problems = []
    out = {"calculation_commit_C": c, "baseline_commit_B": b, "release_commit_R": r}
    # 1. ancestry
    out["ancestry_C_B_R"] = _is_ancestor(repo, c, b) and _is_ancestor(repo, b, r) and b != r
    if not out["ancestry_C_B_R"]:
        problems.append("ancestry")
    # 2. C -> B: calculation code byte-identical (the whole CALC_PATHS, including the registry constant)
    cb_changed = [x for x in _git(repo, "diff", "--name-only", c, b).splitlines() if x]
    calc_cb = sorted(p for p in cb_changed if _under(p, CALC_PATHS))
    out["calc_code_identical_C_to_B"] = not calc_cb
    out["calc_changes_C_to_B"] = calc_cb
    if calc_cb:
        problems.append("calculation_code_changed_C_to_B")
    out["technical_files_changed_C_to_B"] = len(cb_changed) - len(calc_cb)
    # 3. record binds C, approved, not synthetic, exact key set
    rec_ok = (isinstance(record, dict) and set(record) == bc.RECORD_KEYS and record.get("owner_approval") == "APPROVED" and bool(str(record.get("approved_by", "")).strip())
              and bool(str(record.get("approved_on", "")).strip()) and "SYNTHETIC" not in json.dumps(record).upper())
    out["record_approved_not_synthetic_exact_keys"] = bool(rec_ok)
    out["record_binds_C"] = isinstance(record, dict) and record.get("calculation_git_commit") == c
    if not rec_ok:
        problems.append("record")
    if not out["record_binds_C"]:
        problems.append("record_calculation_commit")
    # B production state must be the closed legacy state
    try:
        b_norm, b_val = registry_of(_show(repo, b, CONTRACT).decode())
        b_ts, b_pins = pins_of(_show(repo, b, PINS).decode())
        b_public = _show(repo, b, PUBLIC)
        out["baseline_closed_legacy_state"] = b_val == () and b_pins == [] and bc.sha256(b_public) == bc.LEGACY_PUBLIC_SHA256
    except (ChangesetError, ValueError, SyntaxError) as e:
        out["baseline_closed_legacy_state"] = False
        out["baseline_error"] = str(e)[:120]
        b_norm = b_ts = b_public = None
    if not out["baseline_closed_legacy_state"]:
        problems.append("baseline_state")
    # 4. B -> R
    changed = [x for x in _git(repo, "diff", "--name-only", b, r).splitlines() if x]
    release_files = {CONTRACT, PINS, PUBLIC}
    unauthorized = sorted(p for p in changed if p not in release_files and not _under(p, FREE_PREFIXES))
    calc_changed = sorted(p for p in changed if p != CONTRACT and _under(p, CALC_PATHS))
    out.update(changed_files_B_to_R=len(changed), unauthorized_paths=unauthorized, calculation_code_changed_B_to_R=calc_changed)
    if unauthorized:
        problems.append("unauthorized_paths")
    if calc_changed:
        problems.append("calculation_code_changed")
    try:
        r_norm, r_val = registry_of(_show(repo, r, CONTRACT).decode())
        out["contract_rest_identical"] = b_norm is not None and b_norm == r_norm
        out["registry_exactly_the_record"] = isinstance(r_val, tuple) and len(r_val) == 1 and r_val[0] == record
    except (ChangesetError, ValueError, SyntaxError) as e:
        out.update(contract_rest_identical=False, registry_exactly_the_record=False, contract_error=str(e)[:120])
    try:
        r_ts, r_pins = pins_of(_show(repo, r, PINS).decode())
        out["pins_rest_identical"] = b_ts is not None and b_ts == r_ts
        out["pins_exactly_the_composite"] = r_pins == [record.get("composite_sha256")] if isinstance(record, dict) else False
    except ChangesetError as e:
        out.update(pins_rest_identical=False, pins_exactly_the_composite=False, pins_error=str(e)[:120])
    for k in ("contract_rest_identical", "registry_exactly_the_record", "pins_rest_identical", "pins_exactly_the_composite"):
        if not out[k]:
            problems.append(k)
    # public payload and rollback target
    blob = _show(repo, r, PUBLIC)
    out["public_payload_sha256"] = bc.sha256(blob)
    out["public_equals_record"] = isinstance(record, dict) and out["public_payload_sha256"] == record.get("public_payload_sha256") == record.get("composite_sha256")
    try:
        doc = json.loads(blob)
        out["legacy_projection_is_pinned_legacy"] = bc.sha256(bc.legacy_projection_bytes(doc)) == bc.LEGACY_PUBLIC_SHA256
        bc.composite_release_gate(blob, records=[record])
        out["gate_opens_for_these_bytes"] = True
    except (ValueError, bc.BtcContractError, KeyError, TypeError, AttributeError):
        out.setdefault("legacy_projection_is_pinned_legacy", False)
        out["gate_opens_for_these_bytes"] = False
    ref = record.get("rollback_ref") if isinstance(record, dict) else None
    out["rollback_target_is_B_public_payload"] = (isinstance(ref, dict) and b_public is not None and ref == {"previous_public_sha256": bc.sha256(b_public), "state": bc.ROLLBACK_STATE}
                                                  and bc.rollback_target_ok(record, b_public))
    for k in ("public_equals_record", "legacy_projection_is_pinned_legacy", "gate_opens_for_these_bytes", "rollback_target_is_B_public_payload"):
        if not out[k]:
            problems.append(k)
    out["problems"] = sorted(set(problems))
    out["ok"] = not out["problems"]
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="BTC-10 release change-set check (three-commit model C -> B -> R)")
    ap.add_argument("--repo", default=str(ROOT))
    ap.add_argument("--calc-commit", required=True)
    ap.add_argument("--baseline-commit", required=True, help="B: the integrated technical baseline on main (never defaulted)")
    ap.add_argument("--release-commit", required=True)
    ap.add_argument("--record", required=True, help="the approved btc-release-record/2 JSON (price-free)")
    a = ap.parse_args(argv)
    res = check(a.repo, a.calc_commit, a.baseline_commit, a.release_commit, json.loads(Path(a.record).read_text(encoding="utf-8")))
    print(json.dumps(res, indent=1, sort_keys=True))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
