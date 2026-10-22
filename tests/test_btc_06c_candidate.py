"""BTC-06C: private btc-monthly/1 candidate, contract validator, legacy projection and closed release gates.

Synthetic Coin Metrics/ECB data prove code, not data. The CBS csv and the legacy monthly.json are the real committed files (read only).
"""
import argparse
import hashlib
import json
import re
import subprocess
from datetime import date, timedelta
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path

import pytest

from etl import btc_contract as bc
from etl import hist_model  # noqa: F401  (import check only; production files must not import it)
from tools import btc_04e_cm_replay as b4
from tools import btc_06c_candidate as cand

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "data/cbs-housing.csv"
LEGACY = ROOT / "frontend/public/data/monthly.json"
STAMP = "2026-10-22T10:00:00+00:00"


def days(first, last):
    d, end = date.fromisoformat(first), date.fromisoformat(last)
    while d <= end:
        yield d.isoformat()
        d += timedelta(days=1)


def price(day):
    d = date.fromisoformat(day)
    return Decimal(20) + Decimal((d.year - 2010) * 37 + d.month * 5) + Decimal(d.day * 7 % 11) / Decimal(3)


def fx(day):
    return Decimal("1.1") + Decimal(date.fromisoformat(day).day % 7) / Decimal(50)


def cm_daily(first="2010-07-18", last="2026-09-30"):
    return {d: price(d) for d in days(first, last)}


def ecb_daily(first="1999-01-04", last="2026-09-30"):
    hol = set()
    for y in range(int(first[:4]), int(last[:4]) + 1):
        hol |= {h.isoformat() for h in b4.target_holidays(y)}
    return {d: fx(d) for d in days(first, last) if date.fromisoformat(d).weekday() < 5 and d not in hol}


def raw_pages(daily, per_page=2500):
    keys = sorted(daily)
    return [json.dumps({"data": [{"asset": "btc", "time": f"{d}T00:00:00.000000000Z", "PriceUSD": str(daily[d])} for d in keys[i:i + per_page]]}).encode()
            for i in range(0, len(keys), per_page)]


def make_snapshot(path, cm=None, ecb=None, cbs_sha=None):
    cm = cm_daily() if cm is None else cm
    ecb = ecb_daily() if ecb is None else ecb
    pages = raw_pages(cm)
    house = b4.hb.cbs_2000_series(CSV)
    built = b4.build_from_daily(cm, ecb, house, STAMP)
    hashes = [hashlib.sha256(p).hexdigest() for p in pages]
    acq = {"source": b4.PROVIDER, "metric": "PriceUSD", "url": b4.BASE_URL, "query": b4.query("2010-07-18", max(cm)), "retrieved_at_utc": STAMP,
           "pages": len(pages), "page_sha256": hashes, "response_sha256": hashlib.sha256("".join(hashes).encode()).hexdigest(),
           "first": min(cm), "last": max(cm), "n": len(cm), "provider_gaps": [], "daily": cm}
    man = b4.manifest(acq, "e" * 64, ecb, b4.derived_values_sha256(built), b4.source_windows({"cm_priceusd_daily": cm, "ecb_usd_per_eur_daily": ecb}), "deadbeef")
    sha = hashlib.sha256(CSV.read_bytes()).hexdigest() if cbs_sha is None else cbs_sha
    b4.export_snapshot(path, cm_daily=cm, ecb_daily=ecb, man=man, raw_pages=pages, derived_cutoff=b4.RESEARCH_CUTOFF, cbs_input_sha256=sha)
    return path


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    base = tmp_path_factory.mktemp("btc06c")
    snap = make_snapshot(base / "snap")
    candidate, exact, summary = cand.build_candidate(snap, CSV, LEGACY)
    return {"base": base, "snap": snap, "candidate": candidate, "exact": exact, "summary": summary, "cm": cm_daily(), "ecb": ecb_daily()}


def rows(world):
    return {r["period"]: r for r in world["candidate"]["data"]}


def legacy_bytes():
    return LEGACY.read_bytes()


# ---------------------------------------------------------------- shape, statuses, quality
def test_candidate_has_the_documented_structure(world):
    c = world["candidate"]
    assert set(c) == {"data", "btc"} and len(c["data"]) == 320
    assert all(list(r) == bc.LEGACY_FIELDS + bc.BTC_FIELDS for r in c["data"])
    root = c["btc"]
    assert root["contract"] == "btc-monthly/1" and root["method_id"] == "CM_PRICEUSD_MONTHMEAN_C1_V1" and root["status"] == "PRIVATE_CANDIDATE"
    assert root["publication_authorized"] is False and root["release_gate"] == "CLOSED" and root["early_history_numeric"] is False
    assert world["summary"]["replay"] == "IDENTICAL" and world["summary"]["raw_source_bytes"] == "RETAINED_AND_VERIFIED"


def test_quality_periods_first_value_month_and_null_semantics(world):
    r = rows(world)
    assert r["2000-01"]["btc_meta"] == {"status": "MISSING", "quality": None, "missing_reason": "NOT_APPLICABLE", "exception": None}
    assert r["2010-08"]["btc_meta"] == {"status": "MISSING", "quality": "Q3", "missing_reason": "NOT_PUBLISHED", "exception": None}
    assert r["2014-01"]["btc_per_house"] is None and r["2014-01"]["btc_meta"]["quality"] == "Q3"
    assert r["2014-02"]["btc_meta"] == {"status": "CANDIDATE", "quality": "Q2", "missing_reason": None, "exception": None}
    assert r["2016-04"]["btc_meta"]["quality"] == "Q2" and r["2016-05"]["btc_meta"]["quality"] == "Q1_CANDIDATE"
    assert r["2026-08"]["btc_meta"]["quality"] == "Q1_CANDIDATE" and r["2026-08"]["btc_per_house"] > 0
    cands = [p for p, x in r.items() if x["btc_meta"]["status"] == "CANDIDATE"]
    assert cands[0] == "2014-02" and cands[-1] == "2026-08" and len(cands) == 151
    assert all(r[p]["btc_per_house"] is None and r[p]["sat_per_house"] is None for p in r if p < "2014-02")


def test_june_2011_is_always_hold_null_and_never_a_candidate(world):
    june = rows(world)["2011-06"]
    assert june["btc_per_house"] is None and june["sat_per_house"] is None
    assert june["btc_meta"] == {"status": "HOLD", "quality": "Q3", "missing_reason": "NOT_PUBLISHED", "exception": "HOLD_2011_06"}
    forged = json.loads(json.dumps(world["candidate"]))
    row = next(x for x in forged["data"] if x["period"] == "2011-06")
    row["btc_per_house"], row["sat_per_house"] = 1.0, 1e8
    with pytest.raises(bc.BtcContractError):
        bc.validate_candidate(forged, legacy_bytes())
    row["btc_per_house"] = row["sat_per_house"] = None
    row["btc_meta"] = {"status": "MISSING", "quality": "Q3", "missing_reason": "NOT_PUBLISHED", "exception": None}
    with pytest.raises(bc.BtcContractError):
        bc.validate_candidate(forged, legacy_bytes())  # the HOLD flag cannot be dropped


def test_early_history_is_not_numeric_even_if_a_candidate_claims_it(world):
    forged = json.loads(json.dumps(world["candidate"]))
    row = next(x for x in forged["data"] if x["period"] == "2013-05")
    row["btc_per_house"], row["sat_per_house"] = 5.0, 5e8
    row["btc_meta"] = {"status": "CANDIDATE", "quality": "Q3", "missing_reason": None, "exception": None}
    with pytest.raises(bc.BtcContractError, match="before 2014-02"):
        bc.validate_candidate(forged, legacy_bytes())


def test_contract_constants_cannot_drift_from_the_research_method():
    assert bc.METHOD_ID == b4.METHOD_ID and bc.HOLD_MONTHS == {m: v for m, v in b4.EXCEPTIONS.items()}
    assert bc.FIRST_SUPPORTED_MONTH == b4.FIRST_SUPPORTED_MONTH
    months = [f"{y}-{m:02d}" for y in range(2010, 2027) for m in range(1, 13)]
    for m in months:
        if m >= "2010-08":
            assert bc.quality_of(m) == b4.quality_of_month(m), m
        else:
            assert bc.quality_of(m) is None
    assert bc.QUALITIES == ("Q3", "Q2", "Q1_CANDIDATE")


# ---------------------------------------------------------------- economics
def exact_month(world, month):
    n = b4.H.days_in_month(month)
    p = sum(Fraction(world["cm"][f"{month}-{i:02d}"]) for i in range(1, n + 1)) / n
    f_vals = [Fraction(v) for d, v in world["ecb"].items() if d[:7] == month]
    return p, sum(f_vals) / len(f_vals), f_vals


def test_usd_per_eur_direction_and_ratio_of_monthly_means(world):
    house = {r["period"]: Fraction(Decimal(str(r["house_eur"]))) for r in world["candidate"]["data"]}
    for month in ("2014-02", "2016-05", "2020-02", "2026-08"):
        p, f, f_vals = exact_month(world, month)
        btc_eur = p / f  # USD per BTC divided by USD per EUR = EUR per BTC
        want = house[month] / btc_eur
        got = Fraction(Decimal(world["exact"][month]["btc_per_house"]))
        assert abs(got / want - 1) < Fraction(1, 10 ** 28), month
        wrong_direction = house[month] / (p * f)  # multiplying instead of dividing
        assert abs(got / wrong_direction - 1) > Fraction(1, 100)
        n = b4.H.days_in_month(month)
        mean_of_ratios = sum(Fraction(world["cm"][f"{month}-{i:02d}"]) / f_vals[min(i - 1, len(f_vals) - 1)] for i in range(1, n + 1)) / n
        assert mean_of_ratios != btc_eur  # the two constructions are different numbers; the contract uses the ratio of monthly means
        assert abs(Fraction(Decimal(world["exact"][month]["btc_per_house"])) / (house[month] / mean_of_ratios) - 1) > Fraction(1, 10 ** 6)


def test_exact_sidecar_matches_json_numbers_and_sats_are_exactly_btc_times_1e8(world):
    bc.check_exact(world["candidate"], world["exact"])
    for month, e in world["exact"].items():
        assert Fraction(Decimal(e["sat_per_house"])) == Fraction(Decimal(e["btc_per_house"])) * 10 ** 8
        assert rows(world)[month]["btc_per_house"] == float(Decimal(e["btc_per_house"]))
    with localcontext() as ctx:
        ctx.prec = 8  # ambient context must not change the stored exact values
        bc.check_exact(world["candidate"], world["exact"])


def test_json_serialization_loss_is_bounded_and_detected(world):
    worst = max(abs(Fraction(rows(world)[m]["btc_per_house"]) / Fraction(Decimal(e["btc_per_house"])) - 1) for m, e in world["exact"].items())
    assert worst < Fraction(1, 2 ** 52)  # one double conversion at most
    tampered = json.loads(json.dumps(world["candidate"]))
    row = next(x for x in tampered["data"] if x["period"] == "2020-02")
    row["btc_per_house"] = row["btc_per_house"] * (1 + 1e-9)
    row["sat_per_house"] = row["btc_per_house"] * 1e8
    with pytest.raises(bc.BtcContractError):
        bc.check_exact(tampered, world["exact"])
    assert bc.serialize(world["candidate"]).count(b"NaN") == 0


def test_missing_or_incomplete_inputs_stay_null_without_fill(tmp_path):
    cm = cm_daily()
    del cm["2015-06-15"]  # one missing UTC day
    ecb = ecb_daily()
    del ecb["2018-03-14"]  # an unexpected missing ECB business day (a Wednesday, not a TARGET holiday)
    c, _, _ = cand.build_candidate(make_snapshot(tmp_path / "s", cm=cm, ecb=ecb), CSV, LEGACY)
    r = {x["period"]: x for x in c["data"]}
    for month in ("2015-06", "2018-03"):
        assert r[month]["btc_per_house"] is None and r[month]["btc_meta"]["status"] == "MISSING"
        assert r[month]["btc_meta"]["missing_reason"] == "INCOMPLETE_PERIOD"
    assert r["2015-05"]["btc_meta"]["status"] == "CANDIDATE" and r["2015-07"]["btc_meta"]["status"] == "CANDIDATE"  # neighbours untouched
    assert r["2018-02"]["btc_meta"]["status"] == "CANDIDATE" and r["2018-04"]["btc_meta"]["status"] == "CANDIDATE"


# ---------------------------------------------------------------- legacy / gold-CBS protection
def test_legacy_projection_is_byte_identical_to_the_approved_payload(world):
    assert bc.legacy_projection_bytes(world["candidate"]) == legacy_bytes()
    assert bc.sha256(legacy_bytes()) == bc.LEGACY_PUBLIC_SHA256 == "1afb0bf924cb284a7f818fbe99084fd042f594c6e46b6498c9c399373f91d8cd"
    assert bc.validate_legacy_projection(world["candidate"], legacy_bytes()) == bc.LEGACY_PUBLIC_SHA256
    assert world["candidate"]["btc"]["legacy_sha256"] == bc.LEGACY_PUBLIC_SHA256


def test_any_change_to_a_legacy_field_is_rejected(world):
    for field, value in (("gold_index", 100.5), ("house_eur", 1.0), ("hpi", 1.0)):
        forged = json.loads(json.dumps(world["candidate"]))
        forged["data"][5][field] = value
        with pytest.raises(bc.BtcContractError):
            bc.validate_candidate(forged, legacy_bytes())
    forged = json.loads(json.dumps(world["candidate"]))
    del forged["data"][-1]
    with pytest.raises(bc.BtcContractError):
        bc.validate_candidate(forged, legacy_bytes())
    with pytest.raises(bc.BtcContractError):  # a different legacy payload than the pinned one
        bc.validate_candidate(world["candidate"], legacy_bytes().replace(b"100.0", b"100.1", 1))


def test_public_json_exporter_and_hashes_are_untouched():
    assert hashlib.sha256(LEGACY.read_bytes()).hexdigest() == bc.LEGACY_PUBLIC_SHA256
    assert hashlib.sha256(CSV.read_bytes()).hexdigest() == "ad98bba942b0bc0c43ff142c7972c3e2742f53088398edb3ccde4ff422bbd8f6"
    from etl.static_export import build
    for row in build(CSV)["data"]:
        assert list(row) == bc.LEGACY_FIELDS
    text = LEGACY.read_text(encoding="utf-8").lower()
    assert "btc" not in text and "sat_per_house" not in text
    tracked = subprocess.run(["git", "ls-files", "frontend/public"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    assert tracked == ["frontend/public/data/monthly.json"]


# ---------------------------------------------------------------- mandatory provenance checks
def test_wrong_cbs_csv_or_missing_cbs_hash_is_refused(tmp_path):
    other = tmp_path / "cbs.csv"
    other.write_bytes(CSV.read_bytes() + b"\n")  # same rows, different bytes -> different hash
    snap = make_snapshot(tmp_path / "s")
    with pytest.raises(cand.CandidateError, match="CBS_INPUT_DIFFERS"):
        cand.build_candidate(snap, other, LEGACY)
    nohash = make_snapshot(tmp_path / "t", cbs_sha="")
    # an empty recorded hash can never equal the file hash
    with pytest.raises(cand.CandidateError):
        cand.build_candidate(nohash, CSV, LEGACY)


def test_snapshot_without_a_recorded_cbs_hash_is_refused(world, tmp_path):
    snap = tmp_path / "x"
    loaded = b4.load_snapshot(world["snap"])
    b4.export_snapshot(snap, cm_daily=loaded["cm_daily"], ecb_daily=loaded["ecb_daily"], man=loaded["man"], raw_pages=loaded["raw_pages"],
                       cut_before=loaded["cut_before"], derived_cutoff=loaded["derived_cutoff"], cbs_input_sha256=None)
    with pytest.raises(cand.CandidateError, match="no CBS input hash"):
        cand.build_candidate(snap, CSV, LEGACY)


def test_corrupt_snapshot_unpinned_legacy_and_non_identical_replay_are_refused(world, tmp_path, monkeypatch):
    bad = tmp_path / "bad"
    make_snapshot(bad)
    (bad / "ecb_usd_per_eur_daily.txt").write_text("1999-01-04:1\n")
    with pytest.raises(b4.SnapshotError):
        cand.build_candidate(bad, CSV, LEGACY)
    other_legacy = tmp_path / "monthly.json"
    other_legacy.write_bytes(legacy_bytes().replace(b"100.0", b"100.1", 1))
    with pytest.raises(cand.CandidateError, match="pinned"):
        cand.build_candidate(world["snap"], CSV, other_legacy)
    monkeypatch.setattr(b4, "replay", lambda *a, **k: {"status": "DIFFERENT", "raw_source_bytes": "RETAINED_AND_VERIFIED"})
    with pytest.raises(cand.CandidateError, match="not IDENTICAL"):
        cand.build_candidate(world["snap"], CSV, LEGACY)


def test_revision_controls_for_cm_ecb_and_cbs(world, tmp_path):
    clean = make_snapshot(tmp_path / "same")
    res = cand.revision_checks(world["snap"], clean, CSV)
    assert res["status"] == "CLEAN" and res["cm"]["status"] == "UNCHANGED_HISTORY" and res["cbs"] == "UNCHANGED"
    cm = cm_daily()
    cm["2012-03-03"] += Decimal("0.01")
    res = cand.revision_checks(world["snap"], make_snapshot(tmp_path / "cm", cm=cm), CSV)
    assert res["status"] == "REVIEW_REQUIRED" and res["revised_sources"] == ["cm"] and res["cm"]["revised_days"] == ["2012-03-03"]
    ecb = ecb_daily()
    ecb["2012-03-05"] += Decimal("0.01")
    res = cand.revision_checks(world["snap"], make_snapshot(tmp_path / "ecb", ecb=ecb), CSV)
    assert res["revised_sources"] == ["ecb"]
    grown = make_snapshot(tmp_path / "grown", cm=cm_daily(last="2026-10-15"))
    assert cand.revision_checks(world["snap"], grown, CSV)["status"] == "CLEAN"  # new observations are not revisions
    other = tmp_path / "cbs.csv"
    other.write_bytes(CSV.read_bytes() + b"\n")
    assert cand.revision_checks(world["snap"], clean, other)["revised_sources"] == ["cbs"]


def test_revision_cli_exit_codes(world, tmp_path, capsys):
    same = make_snapshot(tmp_path / "same")
    assert cand.main(["--snapshot", str(world["snap"]), "--compare-snapshot", str(same), "--cbs-csv", str(CSV), "--legacy-json", str(LEGACY)]) == 0
    cm = cm_daily()
    cm["2012-03-03"] += Decimal("0.01")
    revised = make_snapshot(tmp_path / "rev", cm=cm)
    assert cand.main(["--snapshot", str(world["snap"]), "--compare-snapshot", str(revised), "--cbs-csv", str(CSV), "--legacy-json", str(LEGACY)]) == 1
    assert "REVIEW_REQUIRED" in capsys.readouterr().out


# ---------------------------------------------------------------- closed gates
def test_publication_authorized_flag_never_grants_authority(world):
    forged = json.loads(json.dumps(world["candidate"]))
    forged["btc"]["publication_authorized"] = True
    with pytest.raises(bc.BtcContractError, match="never authorizes"):
        bc.validate_candidate(forged, legacy_bytes())
    with pytest.raises(bc.BtcContractError):
        bc.composite_release_gate(bc.serialize(forged))


def test_composite_release_is_denied_without_an_exact_owner_record(world):
    blob = bc.serialize(world["candidate"])
    assert bc.ARTIFACT_RECORDS == () and b4.RELEASE_APPROVALS == frozenset()
    with pytest.raises(bc.ReleaseDenied):
        bc.composite_release_gate(blob)
    good = {"owner_approval": "APPROVED", "composite_sha256": bc.sha256(blob), "legacy_projection_sha256": bc.LEGACY_PUBLIC_SHA256,
            "approved_by": "owner", "approved_on": "2026-01-01"}
    assert bc.composite_release_gate(blob, records=[good]) == good
    for bad in ({**good, "owner_approval": "PROPOSED"}, {**good, "composite_sha256": "0" * 64}, {**good, "legacy_projection_sha256": "1" * 64},
                {**good, "approved_by": ""}, {k: v for k, v in good.items() if k != "approved_on"}, "APPROVED", None):
        with pytest.raises(bc.ReleaseDenied):
            bc.composite_release_gate(blob, records=[bad])
    other_bytes = bc.serialize(dict(world["candidate"], btc=dict(world["candidate"]["btc"], snapshot_id="other")))
    with pytest.raises(bc.ReleaseDenied):  # a record for other bytes does not release these bytes
        bc.composite_release_gate(other_bytes, records=[good])


def test_candidate_shape_violations_are_rejected(world):
    def forge(edit):
        c = json.loads(json.dumps(world["candidate"]))
        edit(c)
        with pytest.raises(bc.BtcContractError):
            bc.validate_candidate(c, legacy_bytes())
    forge(lambda c: c.update(extra=1))
    forge(lambda c: c["data"][100].update(btc_extra=1))
    forge(lambda c: c["data"].reverse())
    forge(lambda c: c["btc"].pop("snapshot_id"))
    forge(lambda c: c["btc"].update(release_gate="OPEN"))
    forge(lambda c: c["btc"].update(early_history_numeric=True))
    forge(lambda c: c["btc"].update(method_id="OTHER"))
    forge(lambda c: c["btc"].update(legacy_sha256="0" * 64))
    forge(lambda c: c["data"][300]["btc_meta"].update(status="WRONG"))
    forge(lambda c: c["data"][300]["btc_meta"].pop("quality"))
    forge(lambda c: c["data"][300].update(btc_per_house="1.5"))
    forge(lambda c: c["data"][300].update(btc_per_house=float("inf")))
    forge(lambda c: c["data"][300].update(btc_per_house=True))
    forge(lambda c: c["data"][300].update(btc_per_house=-1.0))
    forge(lambda c: c["data"][300].update(sat_per_house=c["data"][300]["sat_per_house"] * 1.001))
    forge(lambda c: c["data"][300]["btc_meta"].update(quality="Q3"))
    forge(lambda c: c["data"][5]["btc_meta"].update(missing_reason=None))
    forge(lambda c: c["data"][5]["btc_meta"].update(missing_reason="MADE_UP"))
    forge(lambda c: c["data"][5].update(btc_per_house=1.0))


# ---------------------------------------------------------------- private output, no raw data, CLI
def test_candidate_is_written_privately_without_overwrite_and_without_raw_prices(world, tmp_path, capsys):
    out = tmp_path / "private"
    assert cand.main(["--snapshot", str(world["snap"]), "--cbs-csv", str(CSV), "--legacy-json", str(LEGACY), "--out-dir", str(out)]) == 0
    printed = capsys.readouterr().out
    assert sorted(p.name for p in out.iterdir()) == ["candidate.json", "exact_values.json"]
    assert (out / "candidate.json").read_bytes() == bc.serialize(world["candidate"])
    daily_values = {str(v) for v in list(world["cm"].values())[:400] if len(str(v)) >= 12}  # long decimals cannot collide by accident
    assert daily_values
    blob = (out / "candidate.json").read_text() + printed
    assert not any(v in blob for v in daily_values), "raw Coin Metrics prices must not appear in the candidate or the printed summary"
    assert "SUMMARY candidate" in printed and "btc_per_house" not in printed
    assert cand.main(["--snapshot", str(world["snap"]), "--cbs-csv", str(CSV), "--legacy-json", str(LEGACY), "--out-dir", str(out)]) == 1
    assert (out / "candidate.json").read_bytes() == bc.serialize(world["candidate"])  # untouched


def test_no_private_artifact_is_tracked_or_uploaded():
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines()
    assert not [f for f in tracked if f.endswith(("candidate.json", "exact_values.json", "snapshot_manifest.json"))]
    wf = (ROOT / ".github/workflows/btc-04e-cm-replay.yml").read_text()
    assert wf.count("upload-artifact") == 1 and "path: ${{ runner.temp }}/btc-04e/" in wf
    assert "--out-dir \"$RUNNER_TEMP/btc-06c-private\"" in wf
    uploaded = wf.split("uses: actions/upload-artifact@v4")[1].split("- name:")[0]
    assert "btc-06c-private" not in uploaded and "btc-04e-private-snapshot" not in uploaded
    assert "continue-on-error" not in wf


def test_production_files_do_not_import_the_research_model_or_tools():
    text = (ROOT / "etl/btc_contract.py").read_text(encoding="utf-8")
    assert "hist_model" not in text and "from tools" not in text and "import tools" not in text
    assert not re.search(r"frontend/public|cbs-housing\.csv|monthly\.json", (ROOT / "tools/btc_06c_candidate.py").read_text(encoding="utf-8"))
    assert "btc_06c" not in (ROOT / "etl/static_export.py").read_text(encoding="utf-8")


def test_governance_records_the_decisions_without_inventing_a_release():
    decisions = (ROOT / "docs/governance/DECISIONS.md").read_text(encoding="utf-8")
    section = decisions[decisions.index("## ADR-012 / BTC-06"):]
    for needle in ("PC-BTC06-6 is uitsluitend voorwaardelijk", "niet in de repository aanwezig", "RELEASE_APPROVALS", "publication_authorized=true",
                   "CM_PRICEUSD_MONTHMEAN_C1_V1", "niet** als publicatie"):
        assert needle in section, needle
    assert not re.search(r"(?i)rechten\w* (zijn )?(vrijgegeven|gewaarborgd|goedgekeurd)|release(besluit)? (is )?genomen", section)
    contract = (ROOT / "docs/governance/DATA_CONTRACT.md").read_text(encoding="utf-8")
    assert "btc-monthly/1" in contract and bc.LEGACY_PUBLIC_SHA256 in contract and "geen** BTC-veld" in contract
    table = decisions[:decisions.index("## Open beslisvragen")]
    for adr in ("ADR-004", "ADR-007", "ADR-008", "ADR-009"):
        assert any(adr in row and "PROPOSED" in row for row in table.splitlines() if row.startswith("|")), adr
