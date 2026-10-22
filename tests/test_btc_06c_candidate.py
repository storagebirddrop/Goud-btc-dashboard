"""BTC-06C: btc-monthly/1 preview payload, contract validator, legacy projection and closed release gates, reconciled with the accepted
BTC-06 documents. Synthetic Coin Metrics/ECB data prove code, not data; the CBS csv and the legacy monthly.json are the real committed files.

Acceptance mapping (BTC-06 data contract draft section 10): 1,2,3,4 economics; 5,6,7 are covered in test_btc_04e_cm_replay.py (UTC months,
leap years, ECB calendar, null propagation) and here for the candidate; 8 versions; 9 quality; 10 June 2011; 12 closed gates; 13 legacy projection;
14 payload shapes; 15 revisions; 17 exact record; 18 precision; 19 offline replay with CBS pin; 20 selection hash; 22 no private data in public artifacts;
24 HOLD regression. NOT EXECUTED here: 11, 16, 21 (browser end-to-end), 23 (release/rollback after separate permission).
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
from tools import btc_04e_cm_replay as b4
from tools import btc_06c_candidate as cand
from tools import hist_09_bundle as h9

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "data/cbs-housing.csv"
LEGACY = ROOT / "frontend/public/data/monthly.json"
STAMP = "2026-10-22T10:00:00+00:00"
AUTH_FIELDS = ["btc_per_house", "sat_per_house"]


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


def make_snapshot(path, cm=None, ecb=None, cbs_sha=None, with_raw=True):
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
    b4.export_snapshot(path, cm_daily=cm, ecb_daily=ecb, man=man, raw_pages=pages if with_raw else None, derived_cutoff=b4.RESEARCH_CUTOFF, cbs_input_sha256=sha)
    return path


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    base = tmp_path_factory.mktemp("btc06c")
    snap = make_snapshot(base / "snap")
    preview, sidecar, summary = cand.build_candidate(snap, CSV, LEGACY)
    return {"base": base, "snap": snap, "preview": preview, "sidecar": sidecar, "summary": summary, "cm": cm_daily(), "ecb": ecb_daily()}


def legacy_bytes():
    return LEGACY.read_bytes()


def rows(payload):
    return {r["period"]: r for r in payload["data"]}


def authorization(world, months=None, **over):
    base = {"release_id": "SYN-RELEASE-1", "decision_ref": "SYN-DECISION-1", "months": sorted(world["sidecar"]["months"]) if months is None else months,
            "rights_review_ref": "SYN-RIGHTS-1", "conflicting_contract_check": "VERIFIED"}
    base.update(over)
    return base


def approved_record(composite, auth, **over):
    rec = bc.record_template(composite, auth)
    rec.update(owner_approval="APPROVED", approved_by="synthetic-test-owner", approved_on="2026-01-01")
    rec.update(over)
    return rec


@pytest.fixture(scope="module")
def release(world):
    auth = authorization(world)
    composite = bc.compose_release(world["preview"], world["sidecar"], auth)
    return {"auth": auth, "composite": composite, "blob": bc.serialize(composite), "record": approved_record(composite, auth)}


def forged(payload, edit):
    c = json.loads(json.dumps(payload))
    edit(c)
    return c


# ---------------------------------------------------------------- vocabulary: private candidate state vs public enum
def test_preview_uses_only_the_public_status_enum_and_private_states_stay_private(world):
    p = world["preview"]
    assert {r["btc_meta"]["status"] for r in p["data"]} <= {"PUBLISHED", "WITHHELD", "MISSING"}
    assert {r["btc_meta"]["status"] for r in p["data"]} == {"WITHHELD", "MISSING"}  # nothing is published in a preview
    text = bc.serialize(p).decode()
    for private in ("CANDIDATE_VALUE", "NO_CANDIDATE_VALUE", '"CANDIDATE"', '"HOLD"'):
        assert private not in text
    assert all(m["private_state"] in bc.PRIVATE_STATES for m in world["sidecar"]["months"].values())
    assert not set(bc.PRIVATE_STATES) & set(bc.STATUSES)
    assert all(r["btc_per_house"] is None and r["sat_per_house"] is None for r in p["data"])


def test_private_states_cannot_be_used_as_public_status(world):
    for bad in ("CANDIDATE", "HOLD", "CANDIDATE_VALUE", "published", ""):
        c = forged(world["preview"], lambda x: x["data"][300]["btc_meta"].update(status=bad))
        with pytest.raises(bc.BtcContractError):
            bc.validate_payload(c, legacy_bytes())


def test_status_and_reason_must_belong_together(world):
    c = world["preview"]
    idx = next(i for i, r in enumerate(c["data"]) if r["period"] == "2020-01")
    for status, reason in (("MISSING", "PUBLICATION_NOT_AUTHORIZED"), ("WITHHELD", "INCOMPLETE_PERIOD"), ("WITHHELD", None), ("MISSING", None),
                           ("WITHHELD", "MADE_UP")):
        bad = forged(c, lambda x: x["data"][idx]["btc_meta"].update(status=status, missing_reason=reason))
        with pytest.raises(bc.BtcContractError):
            bc.validate_payload(bad, legacy_bytes())
    assert bc.REASON_STATUS["RESEARCH_ONLY_HOLD"] == "WITHHELD" and bc.REASON_STATUS["BEFORE_SUPPORTED_MONTH"] == "MISSING"
    assert set(bc.REASON_PRIORITY) == set(bc.REASON_STATUS)


def test_priority_reasons_per_period_in_the_preview(world):
    r = rows(world["preview"])
    expect = {"2000-01": (None, "MISSING", "BEFORE_SUPPORTED_MONTH"), "2010-07": (None, "MISSING", "BEFORE_SUPPORTED_MONTH"),
              "2010-08": ("Q3", "WITHHELD", "NOT_AUTHORIZED_PERIOD"), "2011-06": ("Q3", "WITHHELD", "RESEARCH_ONLY_HOLD"),
              "2014-01": ("Q3", "WITHHELD", "NOT_AUTHORIZED_PERIOD"), "2014-02": ("Q2", "WITHHELD", "PUBLICATION_NOT_AUTHORIZED"),
              "2016-04": ("Q2", "WITHHELD", "PUBLICATION_NOT_AUTHORIZED"), "2016-05": ("Q1_CANDIDATE", "WITHHELD", "PUBLICATION_NOT_AUTHORIZED"),
              "2026-08": ("Q1_CANDIDATE", "WITHHELD", "PUBLICATION_NOT_AUTHORIZED")}
    for month, (q, status, reason) in expect.items():
        m = r[month]["btc_meta"]
        assert (m["quality"], m["status"], m["missing_reason"]) == (q, status, reason), month
        assert list(m) == ["quality", "status", "missing_reason", "flags"]
    assert world["summary"]["reason_counts"] == {"BEFORE_SUPPORTED_MONTH": 127, "NOT_AUTHORIZED_PERIOD": 41, "RESEARCH_ONLY_HOLD": 1,
                                                 "PUBLICATION_NOT_AUTHORIZED": 151}


def test_flags_are_registered_review_notes_only(world):
    r = rows(world["preview"])
    assert r["2012-03"]["btc_meta"]["flags"] == ["EARLY_HISTORY_LIMITED_PROVENANCE"] and r["2000-01"]["btc_meta"]["flags"] == []
    assert r["2015-05"]["btc_meta"]["flags"] == ["REVIEW_2015_05"] and r["2015-08"]["btc_meta"]["flags"] == ["REVIEW_2015_08"]
    assert r["2017-12"]["btc_meta"]["flags"] == ["REVIEW_2017_12"] and r["2020-01"]["btc_meta"]["flags"] == []
    for edit in (lambda x: x["data"][300]["btc_meta"].update(flags=["MADE_UP"]), lambda x: x["data"][300]["btc_meta"].update(flags=["REVIEW_2017_12"]),
                 lambda x: x["data"][300]["btc_meta"].update(flags="REVIEW_2017_12"), lambda x: x["data"][300]["btc_meta"].pop("flags"),
                 lambda x: x["data"][150]["btc_meta"].update(flags=[]), lambda x: x["data"][300]["btc_meta"].update(exception=None)):
        with pytest.raises(bc.BtcContractError):
            bc.validate_payload(forged(world["preview"], edit), legacy_bytes())


# ---------------------------------------------------------------- June 2011
def test_june_2011_is_research_only_hold_with_two_nulls_in_every_state(world, release):
    for payload in (world["preview"], release["composite"]):
        june = rows(payload)["2011-06"]
        assert june["btc_per_house"] is None and june["sat_per_house"] is None
        assert june["btc_meta"] == {"quality": "Q3", "status": "WITHHELD", "missing_reason": "RESEARCH_ONLY_HOLD",
                                    "flags": ["EARLY_HISTORY_LIMITED_PROVENANCE"]}
    assert "2011-06" not in world["sidecar"]["months"]  # no candidate value is even carried


def test_june_2011_cannot_be_published_relabelled_or_authorized(world, release):
    def publish_june(c):
        row = next(x for x in c["data"] if x["period"] == "2011-06")
        row["btc_per_house"], row["sat_per_house"], row["btc_meta"]["status"], row["btc_meta"]["missing_reason"] = 1.0, 1e8, "PUBLISHED", None
    with pytest.raises(bc.BtcContractError):
        bc.validate_payload(forged(release["composite"], publish_june), legacy_bytes())
    for status, reason in (("WITHHELD", "NOT_AUTHORIZED_PERIOD"), ("MISSING", "INCOMPLETE_PERIOD"), ("WITHHELD", "PUBLICATION_NOT_AUTHORIZED")):
        c = forged(world["preview"], lambda x: next(r for r in x["data"] if r["period"] == "2011-06")["btc_meta"].update(status=status, missing_reason=reason))
        with pytest.raises(bc.BtcContractError):
            bc.validate_payload(c, legacy_bytes())
    wide = dict(world["sidecar"], months={**world["sidecar"]["months"], "2011-06": {"btc_per_house": "1", "sat_per_house": "100000000", "private_state": "CANDIDATE_VALUE"}})
    with pytest.raises(bc.BtcContractError):
        bc.compose_release(world["preview"], wide, authorization(world, months=sorted(wide["months"])))  # a too-wide allowlist cannot include June
    early = authorization(world, months=["2011-05", "2011-06", "2011-07"], early_history_authorized=True)
    with pytest.raises(bc.BtcContractError):
        bc.compose_release(world["preview"], wide, early)


def test_no_early_numeric_history_without_its_own_authorization(world):
    early = dict(world["sidecar"], months={**world["sidecar"]["months"], "2013-05": {"btc_per_house": "5", "sat_per_house": "500000000", "private_state": "CANDIDATE_VALUE"}})
    with pytest.raises(bc.BtcContractError):
        bc.compose_release(world["preview"], early, authorization(world, months=["2013-05", "2014-02"]))
    # even an early-authorizing record cannot publish June, and the exceptions list in a record must contain it
    assert min(world["sidecar"]["months"]) == "2014-02"


# ---------------------------------------------------------------- root metadata and provenance
def test_root_block_has_the_agreed_keys_and_honest_provenance(world):
    root = world["preview"]["btc"]
    assert list(root) == bc.ROOT_KEYS and root["contract_version"] == "btc-monthly/1" and root["method_id"] == "CM_PRICEUSD_MONTHMEAN_C1_V1"
    assert root["units"] == {"btc_per_house": "BTC/home", "sat_per_house": "satoshi/home"}
    assert root["coverage"] == {"supported_from": "2010-08", "default_from": "2014-02", "authorized_from": None, "authorized_through": None,
                                "early_history_authorized": False}
    assert root["release"] == {"id": None, "decision_ref": None, "publication_authorized": False}
    assert root["rights"] == {"assessment": "CONDITIONAL", "review_ref": None, "scope": "NON_COMMERCIAL", "conflicting_contract_check": "UNVERIFIED"}
    prov = root["provenance"]
    assert list(prov) == bc.PROVENANCE_KEYS and prov["snapshot_format"] == "btc04e-snapshot/2"
    assert prov["snapshot_manifest_sha256"] == hashlib.sha256((world["snap"] / "snapshot_manifest.json").read_bytes()).hexdigest()
    assert prov["cbs_input_sha256"] == hashlib.sha256(CSV.read_bytes()).hexdigest()
    assert (prov["cm_raw_retention"], prov["ecb_raw_retention"], prov["time_basis"]) == ("RETAINED", "NOT_RETAINED", "CM_ACQUISITION_REFERENCE")
    assert re.fullmatch(r"[0-9a-f]{40}", prov["calculation_git_commit"]) and prov["derived_cutoff"] == "2026-08"
    assert prov["source_windows"]["cm_priceusd_daily"]["n"] > 5000 and prov["vintage_reference_utc"] == STAMP
    assert [s["id"] for s in root["sources"]] == bc.SOURCE_IDS and all(s["license_url"].startswith("https://") for s in root["sources"])


def test_placeholders_and_dishonest_provenance_are_refused(world):
    for edit in (lambda c: c["btc"]["provenance"].update(snapshot_manifest_sha256="<actual-64-hex>"), lambda c: c["btc"]["provenance"].update(calculation_git_commit="<actual-40-hex>"),
                 lambda c: c["btc"]["provenance"].update(ecb_raw_retention="RETAINED"), lambda c: c["btc"]["provenance"].update(cm_raw_retention="NOT_RETAINED"),
                 lambda c: c["btc"]["provenance"].update(cbs_input_sha256=None), lambda c: c["btc"]["provenance"].pop("derived_cutoff"),
                 lambda c: c["btc"].update(contract_version="btc-monthly/2"), lambda c: c["btc"].update(method_id="OTHER"),
                 lambda c: c["btc"].pop("rights"), lambda c: c["btc"].update(extra=1), lambda c: c["btc"]["sources"].pop(),
                 lambda c: c["btc"]["rights"].update(scope="COMMERCIAL"), lambda c: c.update(extra=1),
                 lambda c: c["btc"]["release"].update(publication_authorized="yes")):
        with pytest.raises(bc.BtcContractError):
            bc.validate_payload(forged(world["preview"], edit), legacy_bytes())


def test_a_preview_carries_no_release_authority_fields(world):
    for edit in (lambda c: c["btc"]["release"].update(id="X"), lambda c: c["btc"]["coverage"].update(authorized_from="2014-02"),
                 lambda c: c["btc"]["rights"].update(review_ref="R"), lambda c: c["btc"]["rights"].update(conflicting_contract_check="VERIFIED"),
                 lambda c: c["btc"]["coverage"].update(early_history_authorized=True)):
        with pytest.raises(bc.BtcContractError):
            bc.validate_payload(forged(world["preview"], edit), legacy_bytes())


def test_wrong_cbs_csv_missing_cbs_hash_and_non_retained_raw_are_refused(tmp_path):
    other = tmp_path / "cbs.csv"
    other.write_bytes(CSV.read_bytes() + b"\n")  # same rows, different bytes -> different hash
    snap = make_snapshot(tmp_path / "s")
    with pytest.raises(cand.CandidateError, match="CBS_INPUT_DIFFERS"):
        cand.build_candidate(snap, other, LEGACY)
    with pytest.raises(cand.CandidateError):
        cand.build_candidate(make_snapshot(tmp_path / "t", cbs_sha=""), CSV, LEGACY)
    b4.export_snapshot(tmp_path / "x", cm_daily=cm_daily(), ecb_daily=ecb_daily(), man=b4.load_snapshot(snap)["man"], raw_pages=None,
                       derived_cutoff=b4.RESEARCH_CUTOFF, cbs_input_sha256=hashlib.sha256(CSV.read_bytes()).hexdigest())
    with pytest.raises(cand.CandidateError, match="RETAINED"):
        cand.build_candidate(tmp_path / "x", CSV, LEGACY)
    loaded = b4.load_snapshot(snap)
    b4.export_snapshot(tmp_path / "y", cm_daily=loaded["cm_daily"], ecb_daily=loaded["ecb_daily"], man=loaded["man"], raw_pages=loaded["raw_pages"],
                       cut_before=loaded["cut_before"], derived_cutoff=loaded["derived_cutoff"], cbs_input_sha256=None)
    with pytest.raises(cand.CandidateError, match="no CBS input hash"):
        cand.build_candidate(tmp_path / "y", CSV, LEGACY)


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


def test_versions_must_match_the_running_code(world, monkeypatch):
    monkeypatch.setattr(b4, "PARSER_VERSION", "cm-priceusd-parser/2")
    with pytest.raises(b4.SnapshotError) as e:
        cand.build_candidate(world["snap"], CSV, LEGACY)
    assert e.value.code == "METHOD_CHANGED"


# ---------------------------------------------------------------- economics (acceptance 1-4)
def test_synthetic_example_from_the_contract_6_btc_and_600m_sat():
    cm = {d: Decimal(60000) for d in days("2015-03-01", "2015-03-31")}
    ecb = {d: Decimal("1.2") for d in days("2015-03-01", "2015-03-31") if date.fromisoformat(d).weekday() < 5}
    house = b4.hb.source_series("h", "housing", {"2015-03": "300000"}, frequency="monthly", currency="EUR", unit="EUR", kind="average_price",
                                definition_id=h9.CBS_DEFINITION, source_id="syn", raw_sha256="a" * 64, retrieved_at=STAMP, vintage="v",
                                quality_of=lambda p: "CONFIRMED")
    built = b4.build_from_daily(cm, ecb, house, STAMP)
    btc = {p.period: p.value for p in built["cbs_btc_per_house_cm_c1"].points}["2015-03"]
    sat = {p.period: p.value for p in built["cbs_sats_per_house_cm_c1"].points}["2015-03"]
    assert Fraction(btc) == 6 and Fraction(sat) == 600000000
    with localcontext() as ctx:
        ctx.prec = 6
        assert Fraction(sat) == Fraction(btc) * 10 ** 8  # exactness does not depend on the ambient context


def test_ratio_of_monthly_means_differs_from_mean_of_daily_ratios_and_direction_is_division():
    feb = list(days("2015-02-01", "2015-02-28"))
    cm = {d: Decimal(100 if d <= "2015-02-14" else 200) for d in feb}
    ecb = {d: Decimal(1 if d <= "2015-02-14" else 4) for d in feb if date.fromisoformat(d).weekday() < 5}
    house = b4.hb.source_series("h", "housing", {"2015-02": "300000"}, frequency="monthly", currency="EUR", unit="EUR", kind="average_price",
                                definition_id=h9.CBS_DEFINITION, source_id="syn", raw_sha256="a" * 64, retrieved_at=STAMP, vintage="v",
                                quality_of=lambda p: "CONFIRMED")
    built = b4.build_from_daily(cm, ecb, house, STAMP)
    got = Fraction({p.period: p.value for p in built["cm_btc_eur_equivalent_c1"].points}["2015-02"])
    p_mean = sum(Fraction(v) for v in cm.values()) / 28
    f_mean = sum(Fraction(v) for v in ecb.values()) / len(ecb)
    assert got == p_mean / f_mean  # ratio of monthly means, USD per BTC divided by USD per EUR
    daily_ratio = sum(Fraction(cm[d]) / Fraction(ecb[d]) for d in ecb) / len(ecb)
    assert got != daily_ratio and abs(got / daily_ratio - 1) > Fraction(1, 10)
    assert got != p_mean * f_mean  # multiplying by the USD-per-EUR rate would be the wrong direction


def test_sidecar_values_match_an_independent_exact_recalculation(world):
    house = {r["period"]: Fraction(Decimal(str(r["house_eur"]))) for r in world["preview"]["data"]}
    for month in ("2014-02", "2016-05", "2020-02", "2026-08"):
        n = b4.H.days_in_month(month)
        p = sum(Fraction(world["cm"][f"{month}-{i:02d}"]) for i in range(1, n + 1)) / n
        f_vals = [Fraction(v) for d, v in world["ecb"].items() if d[:7] == month]
        want = house[month] / (p / (sum(f_vals) / len(f_vals)))
        got = Fraction(Decimal(world["sidecar"]["months"][month]["btc_per_house"]))
        assert abs(got / want - 1) < Fraction(1, 10 ** 28), month
        assert Fraction(Decimal(world["sidecar"]["months"][month]["sat_per_house"])) == got * 10 ** 8


def test_missing_or_incomplete_inputs_stay_null_without_fill(tmp_path):
    cm = cm_daily()
    del cm["2015-06-15"]
    ecb = ecb_daily()
    del ecb["2018-03-14"]  # an unexpected missing ECB business day (a Wednesday, not a TARGET holiday)
    preview, sidecar, _ = cand.build_candidate(make_snapshot(tmp_path / "s", cm=cm, ecb=ecb), CSV, LEGACY)
    r = rows(preview)
    for month in ("2015-06", "2018-03"):
        assert month not in sidecar["months"]
        assert (r[month]["btc_meta"]["status"], r[month]["btc_meta"]["missing_reason"]) == ("MISSING", "INCOMPLETE_PERIOD")
    assert "2015-05" in sidecar["months"] and "2015-07" in sidecar["months"] and "2018-02" in sidecar["months"] and "2018-04" in sidecar["months"]
    composite = bc.compose_release(preview, sidecar, authorization({"sidecar": sidecar}))
    assert rows(composite)["2015-06"]["btc_meta"]["status"] == "MISSING" and rows(composite)["2015-06"]["btc_per_house"] is None


# ---------------------------------------------------------------- precision (acceptance 18)
def test_composite_values_equal_one_float_conversion_of_the_canonical_decimals(world, release):
    bc.check_precision(release["composite"], world["sidecar"])
    reread = bc.reparse_decimal(release["blob"])
    for row in reread["data"]:
        if row["btc_meta"]["status"] == "PUBLISHED":
            e = world["sidecar"]["months"][row["period"]]
            assert abs(row["btc_per_house"] - Decimal(e["btc_per_house"])) * 10 ** 8 < Decimal("0.25")
            assert abs(row["sat_per_house"] - Decimal(e["sat_per_house"])) < Decimal("0.25")
            assert abs(row["btc_per_house"] * 10 ** 8 - row["sat_per_house"]) < Decimal("0.5") and row["sat_per_house"] < 2 ** 53
    with localcontext() as ctx:
        ctx.prec = 8
        bc.check_precision(release["composite"], world["sidecar"])


def test_representation_loss_beyond_the_agreed_bounds_is_rejected(world, release):
    month = "2020-02"
    for field, factor in (("btc_per_house", 1 + 1e-9), ("sat_per_house", 1 + 1e-9)):
        bad = forged(release["composite"], lambda c: next(r for r in c["data"] if r["period"] == month).update({field: rows(release["composite"])[month][field] * factor}))
        with pytest.raises(bc.BtcContractError):
            bc.check_precision(bad, world["sidecar"])
    small = forged(release["composite"], lambda c: next(r for r in c["data"] if r["period"] == month).update(
        sat_per_house=rows(release["composite"])[month]["sat_per_house"] + 0.6))
    with pytest.raises(bc.BtcContractError):  # BTC x 1e8 and SAT differ by 0.5 satoshi or more
        bc.validate_payload(small, bc.legacy_projection_bytes(small))
    big = forged(release["composite"], lambda c: next(r for r in c["data"] if r["period"] == month).update(sat_per_house=float(2 ** 53), btc_per_house=float(2 ** 53) / 1e8))
    with pytest.raises(bc.BtcContractError):
        bc.validate_payload(big, bc.legacy_projection_bytes(big))
    wrong_exact = dict(world["sidecar"], months={**world["sidecar"]["months"], month: {**world["sidecar"]["months"][month], "sat_per_house": "1"}})
    with pytest.raises(bc.BtcContractError):
        bc.check_precision(release["composite"], wrong_exact)


@pytest.mark.parametrize("bad", ["1.5", float("inf"), float("nan"), True, False, -1.0, 0, 0.0, None])
def test_published_values_must_be_finite_positive_numbers(release, bad):
    month = "2020-02"
    c = forged(release["composite"], lambda x: next(r for r in x["data"] if r["period"] == month).update(btc_per_house=bad))
    with pytest.raises((bc.BtcContractError, ValueError)):
        bc.validate_payload(c, bc.legacy_projection_bytes(c))


# ---------------------------------------------------------------- legacy projection (acceptance 13, 24)
def test_legacy_projection_is_byte_identical_for_preview_and_composite(world, release):
    for payload in (world["preview"], release["composite"]):
        assert bc.legacy_projection_bytes(payload) == legacy_bytes()
        assert bc.validate_legacy_projection(payload, legacy_bytes()) == bc.LEGACY_PUBLIC_SHA256
    assert bc.sha256(legacy_bytes()) == bc.LEGACY_PUBLIC_SHA256 == "1afb0bf924cb284a7f818fbe99084fd042f594c6e46b6498c9c399373f91d8cd"
    parsed = json.loads(legacy_bytes())
    assert len(parsed["data"]) == 320 and all(r["gold_eur_oz"] is None for r in parsed["data"])


def test_any_change_to_a_legacy_field_or_the_legacy_payload_is_rejected(world):
    for field, value in (("gold_index", 100.5), ("house_eur", 1.0), ("hpi", 1.0), ("gold_grams_per_house", 1.0), ("hpi_index", 1.0)):
        c = forged(world["preview"], lambda x: x["data"][5].update({field: value}))
        with pytest.raises(bc.BtcContractError):
            bc.validate_payload(c, legacy_bytes())
    c = forged(world["preview"], lambda x: x["data"].pop())
    with pytest.raises(bc.BtcContractError):
        bc.validate_payload(c, legacy_bytes())
    with pytest.raises(bc.BtcContractError):
        bc.validate_payload(world["preview"], legacy_bytes().replace(b"100.0", b"100.1", 1))


def test_public_json_exporter_and_hashes_are_untouched():
    assert hashlib.sha256(LEGACY.read_bytes()).hexdigest() == bc.LEGACY_PUBLIC_SHA256
    assert hashlib.sha256(CSV.read_bytes()).hexdigest() == "ad98bba942b0bc0c43ff142c7972c3e2742f53088398edb3ccde4ff422bbd8f6"
    from etl.static_export import build
    for row in build(CSV)["data"]:
        assert list(row) == bc.LEGACY_FIELDS
    text = LEGACY.read_text(encoding="utf-8").lower()
    assert "btc" not in text and "sat_per_house" not in text and "btc_meta" not in text
    tracked = subprocess.run(["git", "ls-files", "frontend/public"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    assert tracked == ["frontend/public/data/monthly.json"]
    assert bc.ARTIFACT_RECORDS == () and b4.RELEASE_APPROVALS == frozenset()


# ---------------------------------------------------------------- closed release gate (acceptance 12, 17, 20)
def test_activation_needs_an_exact_owner_record_and_default_is_closed(release):
    with pytest.raises(bc.ReleaseDenied):
        bc.composite_release_gate(release["blob"])
    assert bc.composite_release_gate(release["blob"], records=[release["record"]]) == release["record"]
    assert bc.validate_payload(release["composite"], bc.legacy_projection_bytes(release["composite"]))["mode"] == "ACTIVE"


@pytest.mark.parametrize("edit", [
    {"owner_approval": "PENDING"}, {"owner_approval": "approved"}, {"status": "PROPOSED"}, {"approved_by": ""}, {"approved_on": ""}, {"record_id": ""},
    {"composite_sha256": "0" * 64}, {"btc_selection_sha256": "0" * 64}, {"legacy_projection_sha256": "1" * 64}, {"snapshot_manifest_sha256": "2" * 64},
    {"cbs_input_sha256": "3" * 64}, {"method_id": "OTHER"}, {"quality_version": "CM_Q_V2"}, {"exception_policy_version": "CM_EXC_V2"},
    {"authorized_fields": ["btc_per_house"]}, {"authorized_fields": ["btc_per_house", "sat_per_house", "gold_index"]}, {"exceptions": []},
    {"early_history_authorized": True}, {"release_id": "OTHER"}, {"decision_ref": "OTHER"}, {"review_refs": {"rights": "OTHER", "contract_check": "VERIFIED"}},
    {"review_refs": {"rights": "SYN-RIGHTS-1", "contract_check": "UNVERIFIED"}}, {"review_refs": {}},
])
def test_any_record_mismatch_denies_the_release(release, edit):
    with pytest.raises(bc.ReleaseDenied):
        bc.composite_release_gate(release["blob"], records=[{**release["record"], **edit}])


def test_authorized_months_must_equal_the_published_months_exactly(release):
    months = release["record"]["authorized_months"]
    for wrong in (months[1:], months[:-1], months + ["2026-09"], list(reversed(months)), months + months[:1]):
        with pytest.raises(bc.ReleaseDenied):
            bc.composite_release_gate(release["blob"], records=[{**release["record"], "authorized_months": wrong}])
    assert "2011-06" not in months


def test_a_record_for_other_bytes_or_a_partial_record_never_releases(world, release):
    other_auth = authorization(world, months=release["auth"]["months"][:-1])
    other = bc.compose_release(world["preview"], world["sidecar"], other_auth)
    with pytest.raises(bc.ReleaseDenied):
        bc.composite_release_gate(bc.serialize(other), records=[release["record"]])
    with pytest.raises(bc.ReleaseDenied):
        bc.composite_release_gate(release["blob"], records=[{k: v for k, v in release["record"].items() if k != "approved_on"}])
    with pytest.raises(bc.ReleaseDenied):
        bc.composite_release_gate(release["blob"], records=["APPROVED", None, 3])


def test_numeric_hash_alone_cannot_hide_changed_hold_or_quality_metadata(release):
    base = bc.btc_selection_sha256(release["composite"])
    for edit in (lambda c: next(r for r in c["data"] if r["period"] == "2020-02")["btc_meta"].update(quality="Q2"),
                 lambda c: next(r for r in c["data"] if r["period"] == "2011-06")["btc_meta"].update(missing_reason="NOT_AUTHORIZED_PERIOD", status="WITHHELD"),
                 lambda c: next(r for r in c["data"] if r["period"] == "2017-12")["btc_meta"].update(flags=[])):
        assert bc.btc_selection_sha256(forged(release["composite"], edit)) != base
    assert bc.btc_selection_sha256(release["composite"]) == release["record"]["btc_selection_sha256"]


def test_publication_authorized_flag_never_grants_authority(world, release):
    flipped = forged(world["preview"], lambda c: c["btc"]["release"].update(publication_authorized=True))
    with pytest.raises(bc.BtcContractError):
        bc.validate_payload(flipped, legacy_bytes())  # an active claim needs the whole active metadata and published months
    claimed = forged(release["composite"], lambda c: c["btc"]["release"].update(id="OTHER"))
    with pytest.raises(bc.ReleaseDenied):
        bc.composite_release_gate(bc.serialize(claimed), records=[release["record"]])
    preview_bytes = bc.serialize(world["preview"])
    with pytest.raises(bc.ReleaseDenied):
        bc.composite_release_gate(preview_bytes, records=[release["record"]])  # a preview cannot be released
    with pytest.raises(bc.BtcContractError):
        bc.composite_release_gate(release["blob"] + b" ", records=[release["record"]])  # not canonical bytes


def test_active_payload_publishes_only_authorized_months_with_their_quality(release):
    r = rows(release["composite"])
    pub = [p for p, x in r.items() if x["btc_meta"]["status"] == "PUBLISHED"]
    assert pub[0] == "2014-02" and pub[-1] == "2026-08" and len(pub) == 151 and "2011-06" not in pub
    assert r["2014-02"]["btc_meta"]["quality"] == "Q2" and r["2016-05"]["btc_meta"]["quality"] == "Q1_CANDIDATE"
    assert r["2012-03"]["btc_meta"]["missing_reason"] == "NOT_AUTHORIZED_PERIOD" and r["2012-03"]["btc_per_house"] is None
    root = release["composite"]["btc"]
    assert root["coverage"]["authorized_from"] == "2014-02" and root["coverage"]["authorized_through"] == "2026-08"
    assert root["release"] == {"id": "SYN-RELEASE-1", "decision_ref": "SYN-DECISION-1", "publication_authorized": True}


def test_compose_refuses_unknown_months_and_non_candidates(world):
    with pytest.raises(bc.BtcContractError):
        bc.compose_release(world["preview"], world["sidecar"], authorization(world, months=["2030-01"]))
    with pytest.raises(bc.BtcContractError):
        bc.compose_release(world["preview"], world["sidecar"], authorization(world, months=["2014-02", "2014-02"]))
    with pytest.raises(bc.BtcContractError):
        bc.compose_release(world["preview"], world["sidecar"], authorization(world, months=[]))
    with pytest.raises(bc.BtcContractError):
        bc.compose_release(world["preview"], world["sidecar"], authorization(world, months=["2014-01"]))  # not a candidate month


def test_verify_release_path_proves_the_closed_gate_in_memory(world):
    res = cand.verify_release_path(world["preview"], world["sidecar"])
    assert res["status"] == "NOT_AUTHORIZED_IN_MEMORY_VERIFICATION_ONLY" and res["published_months"] == 151 and res["registry_records"] == 0
    assert all(res["denied"].values()) and set(res["denied"]) == {"default_registry", "tampered_hash", "fewer_months", "pending_approval"}
    assert bc.ARTIFACT_RECORDS == ()


# ---------------------------------------------------------------- revisions (acceptance 15) and offline replay (19)
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
    assert cand.revision_checks(world["snap"], make_snapshot(tmp_path / "ecb", ecb=ecb), CSV)["revised_sources"] == ["ecb"]
    grown = make_snapshot(tmp_path / "grown", cm=cm_daily(last="2026-10-15"))
    assert cand.revision_checks(world["snap"], grown, CSV)["status"] == "CLEAN"  # new observations are not revisions
    other = tmp_path / "cbs.csv"
    other.write_bytes(CSV.read_bytes() + b"\n")
    assert cand.revision_checks(world["snap"], clean, other)["revised_sources"] == ["cbs"]


def test_revision_cli_exit_codes(world, tmp_path, capsys):
    same = make_snapshot(tmp_path / "same")
    base = ["--snapshot", str(world["snap"]), "--cbs-csv", str(CSV), "--legacy-json", str(LEGACY)]
    assert cand.main(base + ["--compare-snapshot", str(same)]) == 0
    cm = cm_daily()
    cm["2012-03-03"] += Decimal("0.01")
    assert cand.main(base + ["--compare-snapshot", str(make_snapshot(tmp_path / "rev", cm=cm))]) == 1
    assert "REVIEW_REQUIRED" in capsys.readouterr().out


def test_build_is_offline_and_deterministic(world, tmp_path, monkeypatch):
    import socket

    def no_network(*a, **k):
        raise AssertionError("network access")
    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(b4, "fetch_priceusd", no_network)
    again, side, _ = cand.build_candidate(world["snap"], CSV, LEGACY)
    assert bc.serialize(again) == bc.serialize(world["preview"]) and bc.serialize(side) == bc.serialize(world["sidecar"])


# ---------------------------------------------------------------- private output, no public artifacts (acceptance 22)
def test_private_output_without_overwrite_and_without_raw_prices(world, tmp_path, capsys):
    out = tmp_path / "private"
    base = ["--snapshot", str(world["snap"]), "--cbs-csv", str(CSV), "--legacy-json", str(LEGACY)]
    assert cand.main(base + ["--out-dir", str(out), "--verify-release-path"]) == 0
    printed = capsys.readouterr().out
    assert sorted(p.name for p in out.iterdir()) == ["candidate.json", "candidate_values.json"]
    assert (out / "candidate.json").read_bytes() == bc.serialize(world["preview"])
    long_prices = {str(v) for v in list(world["cm"].values())[:400] if len(str(v)) >= 12}
    assert long_prices
    blob = (out / "candidate.json").read_text() + printed
    assert not any(v in blob for v in long_prices), "raw Coin Metrics prices must not appear in the candidate or the printed summary"
    sidecar_text = (out / "candidate_values.json").read_text()
    assert "private_state" in sidecar_text and "private_state" not in (out / "candidate.json").read_text()
    assert "SUMMARY candidate" in printed and "NOT_AUTHORIZED_IN_MEMORY_VERIFICATION_ONLY" in printed and '"btc_per_house"' not in printed
    assert cand.main(base + ["--out-dir", str(out)]) == 1
    assert (out / "candidate.json").read_bytes() == bc.serialize(world["preview"])


def test_no_private_artifact_is_tracked_or_uploaded():
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines()
    assert not [f for f in tracked if f.endswith(("candidate.json", "candidate_values.json", "snapshot_manifest.json"))]
    wf = (ROOT / ".github/workflows/btc-04e-cm-replay.yml").read_text()
    assert wf.count("upload-artifact") == 1 and "path: ${{ runner.temp }}/btc-04e/" in wf
    assert "--out-dir \"$RUNNER_TEMP/btc-06c-private\"" in wf and "--verify-release-path" in wf
    uploaded = wf.split("uses: actions/upload-artifact@v4")[1].split("- name:")[0]
    assert "btc-06c-private" not in uploaded and "btc-04e-private-snapshot" not in uploaded
    assert "continue-on-error" not in wf


def test_production_files_do_not_import_the_research_model_or_tools():
    text = (ROOT / "etl/btc_contract.py").read_text(encoding="utf-8")
    assert "hist_model" not in text and "from tools" not in text and "import tools" not in text
    assert not re.search(r"frontend/public|cbs-housing\.csv|monthly\.json", (ROOT / "tools/btc_06c_candidate.py").read_text(encoding="utf-8"))
    assert "btc_06c" not in (ROOT / "etl/static_export.py").read_text(encoding="utf-8")


def test_contract_constants_cannot_drift_from_the_research_method():
    assert bc.METHOD_ID == b4.METHOD_ID and set(bc.HOLD_MONTHS) == set(b4.EXCEPTIONS) and bc.SUPPORTED_FROM == b4.FIRST_SUPPORTED_MONTH
    for y in range(2010, 2027):
        for m in range(1, 13):
            month = f"{y}-{m:02d}"
            assert bc.quality_of(month) == (b4.quality_of_month(month) if month >= "2010-08" else None), month
    assert bc.QUALITIES == ("Q3", "Q2", "Q1_CANDIDATE") and bc.DEFAULT_FROM == "2014-02"


# ---------------------------------------------------------------- frontend (static; browser end-to-end NOT executed) and governance
def test_frontend_keeps_gaps_and_stays_inactive():
    main = (ROOT / "frontend/src/main.tsx").read_text(encoding="utf-8")
    assert "connectNulls={false}" in main or "connectNulls" in main
    series = (ROOT / "frontend/src/series.ts").read_text(encoding="utf-8")
    assert "export type BtcStatus='PUBLISHED'|'WITHHELD'|'MISSING'" in series and "btc_meta?:BtcMeta" in series
    assert "p.btc_meta?.status==='PUBLISHED'" in series and "nf8" in main and "maximumFractionDigits:8" in main
    assert "sat_per_house:{label:'Satoshi per woning'" in series and "publication:'withheld'" in series


def test_governance_records_the_accepted_documents_without_inventing_a_release():
    decisions = (ROOT / "docs/governance/DECISIONS.md").read_text(encoding="utf-8")
    section = decisions[decisions.index("## ADR-012 / BTC-06"):]
    for needle in ("PC-BTC06-6", "voorwaardelijk", "BTC-06_DATA_CONTRACT_DRAFT.md", "RELEASE_APPROVALS", "CM_PRICEUSD_MONTHMEAN_C1_V1", "PUBLISHED", "WITHHELD",
                   "niet** als publicatie", "BTC-05A"):
        assert needle in section, needle
    assert not re.search(r"(?i)rechten\w* (zijn )?(vrijgegeven|gewaarborgd|goedgekeurd)|release(besluit)? (is )?genomen", section)
    contract = (ROOT / "docs/governance/DATA_CONTRACT.md").read_text(encoding="utf-8")
    assert "btc-monthly/1" in contract and bc.LEGACY_PUBLIC_SHA256 in contract and "RESEARCH_ONLY_HOLD" in contract
    table = decisions[:decisions.index("## Open beslisvragen")]
    for adr in ("ADR-004", "ADR-007", "ADR-008", "ADR-009"):
        assert any(adr in row and "PROPOSED" in row for row in table.splitlines() if row.startswith("|")), adr
    for name in ("BTC-06_PRODUCTION_METHODOLOGY_ADR_DRAFT.md", "BTC-06_DATA_CONTRACT_DRAFT.md", "BTC-06_PROJECT_CONTROL_DECISIONS.md"):
        assert (ROOT / "docs/research/btc-06" / name).is_file()
