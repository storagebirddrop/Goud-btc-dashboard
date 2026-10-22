"""BTC-07B P1: executable snapshot retention / restore protocol on synthetic Coin Metrics + ECB data and the real CBS csv.

LOCAL directories only. These tests prove the code path (pack, external anchor, hardened extraction, manifest, offline replay, hash comparison).
They do NOT prove durable owner storage: no owner location exists, so that operational gate stays OPEN."""
import io
import json
import socket
import tarfile
from pathlib import Path

import pytest

from tools import btc_07b_package as P
import test_btc_06c_candidate as t6

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def pkg(tmp_path_factory):
    base = tmp_path_factory.mktemp("btc07b_p1")
    snap = t6.make_snapshot(base / "snap")
    res = P.pack(snap, t6.CSV, t6.LEGACY, base / "store" / "vintage.tar")
    return {"base": base, "snap": snap, "res": res, "tar": Path(res["package"]), "anchor": res["package_sha256"]}


def rewrite(src_tar, dst_tar, edit):
    """Rebuild a package with an edit (and a consistent SHA256SUMS unless the edit says otherwise)."""
    with tarfile.open(src_tar) as tar:
        members = {m.name: tar.extractfile(m).read() for m in tar.getmembers()}
    members = edit(members)
    with tarfile.open(dst_tar, "w") as out:
        for name, blob in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(blob)
            out.addfile(info, io.BytesIO(blob))
    return dst_tar


def resum(members):
    members = dict(members)
    members.pop(P.SUMS, None)
    members[P.SUMS] = "".join(f"{P.sha(b)}  {n}\n" for n, b in sorted(members.items())).encode()
    return members


def test_round_trip_restores_and_compares_every_hash_offline(pkg, tmp_path):
    ev = P.restore(pkg["tar"], pkg["anchor"], tmp_path / "restored")
    assert ev["status"] == "RESTORE_VERIFIED_LOCAL" and ev["replay"] == "IDENTICAL" and ev["raw_source_bytes"] == "RETAINED_AND_VERIFIED"
    assert all(ev["compared"].values()) and {"candidate_sha256", "sidecar_sha256", "derived_values_sha256", "cbs_input_sha256"} <= set(ev["compared"])
    assert ev["durable_storage"] == "OPEN" and "LOCAL" in ev["scope"]
    assert (tmp_path / "restored/snapshot").is_dir() and (tmp_path / "restored" / P.SUMS).is_file()


def test_the_package_is_deterministic_and_lists_every_file_with_a_hash(pkg):
    with tarfile.open(pkg["tar"]) as tar:
        names = tar.getnames()
        sums = tar.extractfile(P.SUMS).read().decode()
    assert names == sorted(n for n in names if n != P.SUMS) + [P.SUMS]
    assert all(f"  {n}\n" in sums for n in names if n != P.SUMS) and P.SUMS not in sums
    again = P.pack(pkg["snap"], t6.CSV, t6.LEGACY, pkg["base"] / "store2" / "again.tar")
    assert again["package_sha256"] == pkg["anchor"], "same inputs must give the same package bytes"


def test_a_wrong_or_missing_external_anchor_extracts_nothing(pkg, tmp_path):
    dest = tmp_path / "never"
    with pytest.raises(P.PackageError, match="PACKAGE_HASH_MISMATCH"):
        P.restore(pkg["tar"], "0" * 64, dest)
    assert not dest.exists()
    with pytest.raises(P.PackageError):
        P.restore(pkg["tar"], "", dest)


def test_a_flipped_byte_in_the_stored_package_is_caught_by_the_anchor(pkg, tmp_path):
    bad = tmp_path / "bad.tar"
    blob = bytearray(pkg["tar"].read_bytes())
    blob[2048] ^= 1
    bad.write_bytes(bytes(blob))
    with pytest.raises(P.PackageError, match="PACKAGE_HASH_MISMATCH"):
        P.restore(bad, pkg["anchor"], tmp_path / "r")


def test_a_repacked_archive_with_a_changed_file_fails_even_with_its_own_anchor(pkg, tmp_path):
    def edit(m):
        m = dict(m)
        name = next(n for n in m if n.endswith("cm_daily.json") or "daily" in n and n.startswith("snapshot/") and "raw" not in n)
        m[name] = m[name].replace(b"1", b"2", 3)
        return resum(m)
    tar = rewrite(pkg["tar"], tmp_path / "forged.tar", edit)
    with pytest.raises(b4_errors()):
        P.restore(tar, P.file_sha(tar), tmp_path / "r")  # anchor matches the forged file, the snapshot verification does not


def b4_errors():
    from tools import btc_04e_cm_replay as b4
    return b4.Btc04eError


def test_a_manifest_that_does_not_match_the_files_is_refused(pkg, tmp_path):
    def edit(m):
        m = dict(m)
        m["snapshot/extra.bin"] = b"unlisted"
        return m  # SHA256SUMS not updated
    tar = rewrite(pkg["tar"], tmp_path / "extra.tar", edit)
    with pytest.raises(P.PackageError, match="MANIFEST_MISMATCH"):
        P.restore(tar, P.file_sha(tar), tmp_path / "r")

    def swapped(m):
        m = dict(m)
        m["legacy/monthly.json"] = m["legacy/monthly.json"] + b" "
        return m
    tar2 = rewrite(pkg["tar"], tmp_path / "swap.tar", swapped)
    with pytest.raises(P.PackageError, match="MANIFEST_MISMATCH"):
        P.restore(tar2, P.file_sha(tar2), tmp_path / "r2")


def test_a_different_cbs_input_is_never_identical(pkg, tmp_path):
    def edit(m):
        m = dict(m)
        m["inputs/cbs-housing.csv"] = m["inputs/cbs-housing.csv"].replace(b"\n", b"\n", 1) + b"\n"
        return resum(m)
    tar = rewrite(pkg["tar"], tmp_path / "cbs.tar", edit)
    with pytest.raises(b4_errors()):
        P.restore(tar, P.file_sha(tar), tmp_path / "r")


@pytest.mark.parametrize("name", ["../escape.txt", "/abs.txt", "snapshot/../../x"])
def test_unsafe_member_names_are_refused(pkg, tmp_path, name):
    tar = rewrite(pkg["tar"], tmp_path / "unsafe.tar", lambda m: {**m, name: b"x"})
    with pytest.raises(P.PackageError, match="unsafe"):
        P.restore(tar, P.file_sha(tar), tmp_path / "r")
    assert not (tmp_path / "escape.txt").exists()


def test_links_are_refused(pkg, tmp_path):
    out = tmp_path / "link.tar"
    with tarfile.open(pkg["tar"]) as src, tarfile.open(out, "w") as dst:
        for m in src.getmembers():
            dst.addfile(m, src.extractfile(m))
        link = tarfile.TarInfo("snapshot/link")
        link.type, link.linkname = tarfile.SYMTYPE, "/etc/passwd"
        dst.addfile(link)
    with pytest.raises(P.PackageError, match="unsafe"):
        P.restore(out, P.file_sha(out), tmp_path / "r")


def test_restore_needs_a_new_or_empty_directory(pkg, tmp_path):
    (tmp_path / "used").mkdir()
    (tmp_path / "used" / "f").write_text("x")
    with pytest.raises(P.PackageError, match="new or empty"):
        P.restore(pkg["tar"], pkg["anchor"], tmp_path / "used")


def test_pack_refuses_to_write_inside_the_repository_or_over_an_existing_file(pkg, tmp_path):
    with pytest.raises(P.PackageError, match="OUTSIDE"):
        P.pack(pkg["snap"], t6.CSV, t6.LEGACY, ROOT / "frontend/public/data/vintage.tar")
    assert not (ROOT / "frontend/public/data/vintage.tar").exists()
    with pytest.raises(FileExistsError):
        P.pack(pkg["snap"], t6.CSV, t6.LEGACY, pkg["tar"])


def test_the_replay_runs_with_the_network_blocked():
    with P.network_blocked():
        s = socket.socket()
        with pytest.raises(OSError, match="blocked"):
            s.connect(("127.0.0.1", 9))
    s2 = socket.socket()  # restored afterwards
    s2.close()
    assert socket.socket is not None


def test_evidence_is_price_free_and_cli_round_trip(pkg, tmp_path, capsys):
    base = ["restore", "--package", str(pkg["tar"]), "--expect-sha256", pkg["anchor"], "--dest", str(tmp_path / "cli")]
    assert P.main(base) == 0
    out = capsys.readouterr().out
    doc = json.loads(out.split("EVIDENCE ", 1)[1])
    assert doc["status"] == "RESTORE_VERIFIED_LOCAL"
    import re
    assert not re.search(r"\d\.\d", out)
    assert P.main(["restore", "--package", str(pkg["tar"]), "--expect-sha256", "f" * 64, "--dest", str(tmp_path / "cli2")]) == 1
    assert "PACKAGE_HASH_MISMATCH" in capsys.readouterr().out
