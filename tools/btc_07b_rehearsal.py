"""BTC-07B P4: LOCAL release / rollback rehearsal in an isolated directory. Nothing here can touch the repository's public data.

Sandbox layout (all inside --work-dir, which must be outside the repository):
  public/data/monthly.json   the sandbox 'live' file, initially the exact approved legacy bytes
  backup/monthly.legacy.json the retained legacy bytes (the rollback target)
  staging/                   exported candidates
The rehearsal proves: an invalid candidate leaves the live file unchanged; a SYNTHETIC valid composite exists only in the sandbox; switching back
restores the exact legacy bytes (hash, gold/CBS projection); the release gate stays closed by default (no registered record, ever)."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from etl import btc_contract as bc  # noqa: E402
from etl import btc_release as br  # noqa: E402
from etl import data_quality as dq  # noqa: E402
from tools import btc_07b_fixtures as fx  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "data/cbs-housing.csv"


class RehearsalError(ValueError):
    pass


def sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sandbox(work_dir) -> dict:
    root = Path(work_dir).resolve()
    if ROOT in (root, *root.parents):
        raise RehearsalError("the rehearsal sandbox must be outside the repository")
    if root.exists() and any(root.iterdir()):
        raise RehearsalError("the sandbox directory must be new or empty")
    live = root / "public/data/monthly.json"
    backup = root / "backup/monthly.legacy.json"
    for p in (live, backup, root / "staging/x"):
        p.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(br.DEFAULT_PUBLIC, live)
    shutil.copyfile(br.DEFAULT_PUBLIC, backup)
    if sha(live) != bc.LEGACY_PUBLIC_SHA256:
        raise RehearsalError("the repository legacy file is not the approved payload")
    return {"root": root, "live": live, "backup": backup, "staging": root / "staging"}


def activate(staged, live, *, replace=os.replace):
    """Atomic switch inside the sandbox: write next to the target, then replace. A failure leaves the live file untouched and no temp file."""
    live = Path(live)
    fd, tmp = tempfile.mkstemp(dir=live.parent, prefix=".switch-")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(Path(staged).read_bytes())
        replace(tmp, live)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def rollback(backup, live, *, replace=os.replace):
    activate(backup, live, replace=replace)
    if sha(live) != bc.LEGACY_PUBLIC_SHA256:
        raise RehearsalError("rollback did not restore the approved legacy bytes")


def validate_live(live, *, records=None):
    """Production validator on the sandbox file. `records` only for the in-process synthetic record; the default registry stays empty."""
    live = Path(live)
    if records is None:
        return dq.validate_production_state(CSV, live)[0]
    return br.validate_composite_state(CSV, live, records=records)


def rehearse(work_dir) -> dict:
    sb = sandbox(work_dir)
    live, backup = sb["live"], sb["backup"]
    base = {"legacy_sha256": sha(live), "csv_sha256": sha(CSV), "registry_records": len(bc.ARTIFACT_RECORDS)}
    steps = []

    preview, sidecar, _, _ = fx.synthetic_candidate(sb["root"])
    months = [m for m in sorted(sidecar["months"]) if m >= "2014-02"]
    auth = {"release_id": "SYNTHETIC-REHEARSAL", "decision_ref": "SYNTHETIC-NOT-A-DECISION", "months": months, "rights_review_ref": "SYNTHETIC",
            "conflicting_contract_check": "VERIFIED"}
    composite = bc.compose_release(preview, sidecar, auth)
    blob = bc.serialize(composite)
    record = bc.record_template(composite, auth)
    record.update(owner_approval="APPROVED", approved_by="synthetic-rehearsal", approved_on="n/a")

    # 1. invalid candidates: tampered legacy field, tampered BTC selection, missing record. Live file must not change.
    before = sha(live)
    invalid = {}
    tampered = json.loads(blob.decode())
    tampered["data"][50]["house_eur"] += 1
    invalid["legacy_field_changed"] = bc.serialize(tampered)
    tampered = json.loads(blob.decode())
    tampered["data"][-1]["btc_per_house"] = tampered["data"][-1]["btc_per_house"] * 2
    invalid["btc_value_changed_after_approval"] = bc.serialize(tampered)
    invalid["no_record_by_default"] = blob
    outcome = {}
    for name, bad in invalid.items():
        src = sb["staging"] / f"{name}.json"
        src.write_bytes(bad)
        try:
            br.export_composite(src, sb["staging"] / f"out-{name}.json", legacy_path=live, records=None if name == "no_record_by_default" else [record])
            outcome[name] = "ACCEPTED (unexpected)"
        except bc.BtcContractError:
            outcome[name] = "REFUSED"
    steps.append({"step": "invalid candidates", "outcomes": outcome, "live_unchanged": sha(live) == before and before == base["legacy_sha256"],
                  "no_output_written": not list(sb["staging"].glob("out-*"))})

    # 2. synthetic valid composite: exported and switched ONLY in the sandbox, validated with the in-process synthetic record
    src = sb["staging"] / "composite.json"
    src.write_bytes(blob)
    res = br.export_composite(src, sb["staging"] / "out-composite.json", legacy_path=live, records=[record])
    activate(sb["staging"] / "out-composite.json", live)
    count = validate_live(live, records=[record])
    try:
        validate_live(live)  # default registry: closed
        closed = False
    except bc.ReleaseDenied:
        closed = True
    steps.append({"step": "synthetic composite active in sandbox", "composite_sha256": res["composite_sha256"], "months_validated": count,
                  "default_registry_denies_it": closed, "live_is_composite": sha(live) == res["composite_sha256"]})

    # 3. failure injection during the switch: live stays the composite, no temp file
    def boom(*a, **k):
        raise OSError("injected failure")
    kept = sha(live)
    try:
        activate(backup, live, replace=boom)
        injected = "no failure (unexpected)"
    except OSError:
        injected = "FAILED_AS_INJECTED"
    steps.append({"step": "failure during switch", "result": injected, "live_unchanged": sha(live) == kept,
                  "temp_files_left": sorted(p.name for p in live.parent.iterdir() if p.name.startswith(".switch-"))})

    # 4. rollback to the retained legacy bytes
    rollback(backup, live)
    back = validate_live(live)
    proj_ok = bc.sha256(bc.legacy_projection_bytes(json.loads(blob.decode()))) == sha(live)
    steps.append({"step": "rollback to legacy", "live_sha256": sha(live), "equals_approved_legacy": sha(live) == bc.LEGACY_PUBLIC_SHA256,
                  "default_validator_months": back, "composite_projection_equals_legacy": proj_ok})

    final = {"repo_legacy_sha256": sha(br.DEFAULT_PUBLIC), "repo_csv_sha256": sha(CSV), "registry_records": len(bc.ARTIFACT_RECORDS)}
    ok = (steps[0]["live_unchanged"] and steps[0]["no_output_written"] and all(v == "REFUSED" for v in outcome.values()) and steps[1]["default_registry_denies_it"]
          and steps[1]["live_is_composite"] and steps[2]["live_unchanged"] and not steps[2]["temp_files_left"] and steps[3]["equals_approved_legacy"]
          and proj_ok and final["repo_legacy_sha256"] == base["legacy_sha256"] and final["repo_csv_sha256"] == base["csv_sha256"] and final["registry_records"] == 0)
    return {"status": "REHEARSAL_PASSED_LOCAL_SYNTHETIC" if ok else "REHEARSAL_FAILED", "scope": "SANDBOX_ONLY: no Cloudflare deployment, no public rollback", "base": base,
            "steps": steps, "final": final}


def main(argv=None):
    ap = argparse.ArgumentParser(description="BTC-07B local release/rollback rehearsal (sandbox, synthetic)")
    ap.add_argument("--work-dir", required=True, help="new directory outside the repository")
    a = ap.parse_args(argv)
    try:
        res = rehearse(a.work_dir)
    except (RehearsalError, bc.BtcContractError, OSError, ValueError) as exc:
        print("DEFECT", type(exc).__name__, str(exc)[:200])
        return 1
    print(json.dumps(res, indent=1, sort_keys=True))
    return 0 if res["status"].startswith("REHEARSAL_PASSED") else 1


if __name__ == "__main__":
    sys.exit(main())
