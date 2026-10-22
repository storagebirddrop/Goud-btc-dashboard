"""BTC-07B P1: minimal executable protocol to retain and restore ONE private vintage package (btc04e-snapshot/2 + the exact CBS input).

No new storage service and no network: `pack` writes a deterministic tar OUTSIDE the repository, `restore` verifies it against an
EXTERNAL anchor hash (the tar sha256 that Project Control keeps elsewhere), extracts into a new empty directory with hardened member
checks, verifies the file manifest, replays offline with sockets blocked and compares source, CBS, derived, candidate and sidecar
hashes with the provenance recorded at pack time. Evidence output is price-free (hashes, counts, statuses).

Passing this protocol locally proves the CODE works on the tested directory. It does not prove durable owner storage: that gate stays OPEN
until the owner designates a private location and a restore from that location has actually been executed."""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import socket
import sys
import tarfile
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from etl import btc_contract as bc  # noqa: E402
from tools import btc_04e_cm_replay as b4  # noqa: E402
from tools import btc_06c_candidate as cand  # noqa: E402
from tools import btc_public_report as pr  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FORMAT = "btc07b-package/1"
SUMS = "SHA256SUMS"
PROVENANCE = "evidence/provenance.json"
INPUTS = {"inputs/cbs-housing.csv": "cbs", "legacy/monthly.json": "legacy"}


class PackageError(b4.Btc04eError):
    pass


def sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def file_sha(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def provenance(snapshot_dir, cbs_csv, legacy_json) -> dict:
    """Price-free identity of the vintage and of everything derived from it (recomputed on restore and compared)."""
    snap = b4.load_snapshot(snapshot_dir)
    preview, sidecar, summary = cand.build_candidate(snapshot_dir, cbs_csv, legacy_json)
    return {"format": FORMAT, "snapshot_id": snap["snapshot_id"], "snapshot_manifest_sha256": file_sha(Path(snapshot_dir) / b4.SNAPSHOT_MANIFEST),
            "cm_daily_sha256": snap["man"]["coinmetrics"]["canonical_daily_sha256"], "ecb_daily_sha256": snap["man"]["ecb"]["canonical_daily_sha256"],
            "cbs_input_sha256": file_sha(cbs_csv), "legacy_sha256": file_sha(legacy_json), "derived_values_sha256": snap["man"]["derived_values_sha256"],
            "candidate_sha256": sha(bc.serialize(preview)), "sidecar_sha256": sha(bc.serialize(sidecar)), "raw_retention": snap["raw_retention"],
            "candidate_value_months": summary["candidate_value_months"]}


def _files(snapshot_dir, cbs_csv, legacy_json) -> dict:
    base = Path(snapshot_dir)
    out = {f"snapshot/{p.relative_to(base).as_posix()}": p for p in sorted(base.rglob("*")) if p.is_file()}
    out["inputs/cbs-housing.csv"], out["legacy/monthly.json"] = Path(cbs_csv), Path(legacy_json)
    return out


def _add(tar, name, blob):
    info = tarfile.TarInfo(name)
    info.size, info.mtime, info.mode, info.uid, info.gid, info.uname, info.gname = len(blob), 0, 0o600, 0, 0, "", ""
    tar.addfile(info, io.BytesIO(blob))


def pack(snapshot_dir, cbs_csv, legacy_json, out_tar) -> dict:
    out = Path(out_tar).resolve()
    if ROOT in (out, *out.parents):
        raise PackageError("the package must be written OUTSIDE the repository (no private package in a public tree)")
    prov = provenance(snapshot_dir, cbs_csv, legacy_json)
    files = _files(snapshot_dir, cbs_csv, legacy_json)
    blobs = {name: p.read_bytes() for name, p in files.items()}
    prov_blob = (json.dumps(prov, indent=1, sort_keys=True) + "\n").encode()
    blobs[PROVENANCE] = prov_blob
    sums = "".join(f"{sha(b)}  {name}\n" for name, b in sorted(blobs.items())).encode()  # the list does not hash itself
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "xb") as fh, tarfile.open(fileobj=fh, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for name in sorted(blobs):
            _add(tar, name, blobs[name])
        _add(tar, SUMS, sums)
    return {"package": str(out), "package_sha256": file_sha(out), "files": len(blobs) + 1, "bytes": out.stat().st_size, "provenance": prov}


@contextlib.contextmanager
def network_blocked():
    """Offline proof: any attempt to open a socket during replay raises."""
    real = socket.socket

    class Blocked(real):
        def connect(self, *a, **k):
            raise OSError("network access is blocked during the restore replay")

        def connect_ex(self, *a, **k):
            raise OSError("network access is blocked during the restore replay")
    socket.socket = Blocked
    try:
        yield
    finally:
        socket.socket = real


def _safe_extract(tar, dest: Path):
    for m in tar.getmembers():
        p = PurePosixPath(m.name)
        if not m.isreg() or p.is_absolute() or ".." in p.parts or not p.parts or m.name.startswith("./") or m.size > 200_000_000:
            raise PackageError(f"unsafe or unsupported archive member {m.name[:60]!r}")
        target = dest.joinpath(*p.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "xb") as fh:
            fh.write(tar.extractfile(m).read())


def restore(package, expected_sha256, dest) -> dict:
    """Verify the external anchor, extract into a NEW empty directory, verify the manifest, replay offline, compare hashes. Raises on any failure."""
    if not (isinstance(expected_sha256, str) and len(expected_sha256) == 64):
        raise PackageError("the external anchor hash (sha256 of the package) is required")
    got = file_sha(package)
    if got != expected_sha256:
        raise PackageError("PACKAGE_HASH_MISMATCH: the package differs from the externally recorded anchor; nothing was extracted")
    d = Path(dest)
    if d.exists() and (not d.is_dir() or any(d.iterdir())):
        raise PackageError("the restore directory must be new or empty")
    d.mkdir(parents=True, exist_ok=True)
    with tarfile.open(package, "r:") as tar:
        _safe_extract(tar, d)
    listed = {}
    for line in (d / SUMS).read_text().splitlines():
        digest, _, name = line.partition("  ")
        listed[name] = digest
    present = sorted(str(p.relative_to(d)) for p in d.rglob("*") if p.is_file() and p.name != SUMS)
    if present != sorted(listed):
        raise PackageError("MANIFEST_MISMATCH: extracted files and SHA256SUMS differ")
    for name, digest in listed.items():
        if file_sha(d / name) != digest:
            raise PackageError(f"MANIFEST_MISMATCH: {name} differs from SHA256SUMS")
    recorded = json.loads((d / PROVENANCE).read_text())
    with network_blocked():  # offline replay: nothing may reach a provider
        snap_dir, cbs, legacy = d / "snapshot", d / "inputs/cbs-housing.csv", d / "legacy/monthly.json"
        house = b4.hb.cbs_2000_series(cbs)
        replay = b4.replay(snap_dir, house, file_sha(cbs))
        again = provenance(snap_dir, cbs, legacy)
    checks = {k: (again.get(k) == v) for k, v in recorded.items()}
    ok = replay["status"] == "IDENTICAL" and all(checks.values()) and replay["raw_source_bytes"] == "RETAINED_AND_VERIFIED"
    evidence = {"status": "RESTORE_VERIFIED_LOCAL" if ok else "RESTORE_FAILED", "package_sha256": got, "replay": replay["status"],
                "raw_source_bytes": replay["raw_source_bytes"], "compared": {k: bool(v) for k, v in sorted(checks.items())},
                "hashes": {k: recorded[k] for k in ("snapshot_manifest_sha256", "cm_daily_sha256", "ecb_daily_sha256", "cbs_input_sha256",
                                                      "derived_values_sha256", "candidate_sha256", "sidecar_sha256")},
                "durable_storage": "OPEN", "scope": "LOCAL_DIRECTORY_ONLY: no owner storage location was tested"}
    if not ok:
        raise PackageError("RESTORE_FAILED: " + pr.safe_text(json.dumps(evidence["compared"], sort_keys=True), 300))
    return evidence


def main(argv=None):
    ap = argparse.ArgumentParser(description="BTC-07B private vintage package: pack / restore (offline, price-free evidence)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pack")
    p.add_argument("--snapshot", required=True)
    p.add_argument("--cbs-csv", required=True)
    p.add_argument("--legacy-json", required=True)
    p.add_argument("--out", required=True, help="new tar file OUTSIDE the repository")
    r = sub.add_parser("restore")
    r.add_argument("--package", required=True)
    r.add_argument("--expect-sha256", required=True, help="external anchor: sha256 of the package recorded outside the storage location")
    r.add_argument("--dest", required=True, help="new empty directory")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "pack":
            res = pack(a.snapshot, a.cbs_csv, a.legacy_json, a.out)
            res = {k: v for k, v in res.items() if k != "package"} | {"anchor_to_record_with_pc": res["package_sha256"]}
        else:
            res = restore(a.package, a.expect_sha256, a.dest)
        pr.assert_value_free(res)
    except (b4.Btc04eError, bc.BtcContractError, pr.PublicReportError, OSError, ValueError, tarfile.TarError) as exc:
        print("DEFECT", type(exc).__name__, pr.safe_text(exc, 300))
        return 1
    print("EVIDENCE", json.dumps(res, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
