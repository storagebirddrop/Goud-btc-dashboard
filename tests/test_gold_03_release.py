"""GOLD-03: the committed public JSON is the reviewed two-indicator release candidate.

Real committed files; no network. Raw gold/FX inputs are not in the repository, so the
independent formula replay against World Bank/ECB lives in the GOLD-02B workflow; here the
checks are: hash identity with the release record and the code pins, exact contract
(320 months, only two derived fields filled), CBS parity with build(csv), internal
ADR-004 consistency recomputed with Decimal, and fail-closed behaviour for anything else.
"""
import hashlib
import json
import math
from decimal import Decimal as D
from pathlib import Path

import pytest

from etl.cbs_historical_merge import BASELINE_JSON_SHA256
from etl.data_quality import main, validate, validate_gold_release_committed
from etl.gold_monthly import GRAMS, expected_months
from etl.gold_publication_candidate import APPROVED_PUBLIC_JSON_SHA256
from etl.static_export import build

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "data" / "cbs-housing.csv"
JSON = ROOT / "frontend" / "public" / "data" / "monthly.json"
RECORD = ROOT / "data" / "gold-release-record.json"
DERIVED = ("gold_index", "gold_grams_per_house")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv("GOLD_PUBLICATION_ENABLED", raising=False)
    monkeypatch.delenv("GOLD_PUBLICATION_APPROVAL", raising=False)


def rows():
    return json.loads(JSON.read_text(encoding="utf-8"))["data"]


def write(tmp_path, payload_rows):
    target = tmp_path / "monthly.json"
    target.write_bytes((json.dumps({"data": payload_rows}, ensure_ascii=False, separators=(",", ":"),
                                   allow_nan=False) + "\n").encode())
    return target


def record_for(tmp_path, target, **overrides):
    rec = json.loads(RECORD.read_text(encoding="utf-8"))
    sha = hashlib.sha256(target.read_bytes()).hexdigest()
    rec["artifact"]["sha256"] = sha
    rec["candidate_validation"]["candidate_sha256"] = sha
    rec.update(overrides)
    path = tmp_path / "record.json"
    path.write_text(json.dumps(rec), encoding="utf-8")
    return path


def test_pins_record_and_bytes_agree():
    sha = hashlib.sha256(JSON.read_bytes()).hexdigest()
    rec = json.loads(RECORD.read_text(encoding="utf-8"))
    assert sha == APPROVED_PUBLIC_JSON_SHA256 == BASELINE_JSON_SHA256
    assert rec["artifact"]["sha256"] == rec["candidate_validation"]["candidate_sha256"] == sha
    assert rec["sources"]["cbs_csv_sha256"] == hashlib.sha256(CSV.read_bytes()).hexdigest()
    assert rec["fields_published"] == list(DERIVED)


def test_exact_public_contract():
    data = rows()
    assert [r["period"] for r in data] == expected_months("2000-01", "2026-08")
    assert len(data) == 320
    for r in data:
        assert list(r) == ["period", "gold_eur_oz", "house_eur", "hpi", "gold_grams_per_house",
                           "gold_index", "hpi_index"]
        assert r["gold_eur_oz"] is None
        for f in DERIVED:
            assert isinstance(r[f], float) and math.isfinite(r[f]) and r[f] > 0
    assert data[0]["gold_index"] == 100 and data[0]["hpi_index"] == 100


def test_cbs_columns_equal_build_of_committed_csv():
    expected = build(CSV)["data"]
    for got, exp in zip(rows(), expected):
        assert {k: v for k, v in got.items() if k not in DERIVED} == \
               {k: v for k, v in exp.items() if k not in DERIVED}
        assert all(exp[f] is None for f in DERIVED)


def test_adr004_internal_consistency_recomputed_with_decimal():
    """grams = house * g/oz / EUR-oz and index = 100 * EUR-oz / EUR-oz[2000-01]
    imply grams * index / house == 100 * g/oz / EUR-oz[2000-01] for every month."""
    data = rows()
    eur_base = D(str(data[0]["house_eur"])) * GRAMS / D(str(data[0]["gold_grams_per_house"]))
    const = 100 * GRAMS / eur_base
    for r in data:
        k = D(str(r["gold_grams_per_house"])) * D(str(r["gold_index"])) / D(str(r["house_eur"]))
        assert abs(k - const) <= const * D("1e-9"), r["period"]
        eur_oz = D(str(r["house_eur"])) * GRAMS / D(str(r["gold_grams_per_house"]))
        assert abs(D(str(r["gold_index"])) - 100 * eur_oz / eur_base) <= D("1e-8") * D(str(r["gold_index"]))


def test_committed_mode_accepts_committed_files_and_reports_status():
    report = validate_gold_release_committed(CSV, JSON, RECORD)
    assert report["months"] == 320 and report["publication_authorized"] is False
    status = json.loads(RECORD.read_text(encoding="utf-8"))["release_authorization"]["status"]
    assert f"RELEASE STATUS PER RECORD: {status}" in report["attested_not_verified"]["PUBLICATION AUTHORIZED"]


def test_release_gate_requires_authorized_record_and_env(monkeypatch):
    with pytest.raises(ValueError, match="GOLD_PUBLICATION_ENABLED"):
        validate_gold_release_committed(CSV, JSON, RECORD, require_authorized=True)
    monkeypatch.setenv("GOLD_PUBLICATION_ENABLED", "true")
    monkeypatch.setenv("GOLD_PUBLICATION_APPROVAL", "APPROVED")
    rec = json.loads(RECORD.read_text(encoding="utf-8"))
    if rec["release_authorization"]["status"] == "NOT_AUTHORIZED":
        with pytest.raises(ValueError, match="NOT_AUTHORIZED"):
            validate_gold_release_committed(CSV, JSON, RECORD, require_authorized=True)
    else:  # owner released: the record must be complete and the gate passes
        assert validate_gold_release_committed(CSV, JSON, RECORD, require_authorized=True)["publication_authorized"]


def test_default_mode_stays_fail_closed_for_gold():
    with pytest.raises(ValueError):
        validate(CSV, JSON)


def test_cli_committed_mode(capsys, monkeypatch):
    monkeypatch.setattr("sys.argv", ["dq", "--gold-release-record", str(RECORD), "--committed"])
    main()
    assert "Validated 320 consecutive months" in capsys.readouterr().out


AUTHORIZED = {"status": "AUTHORIZED", "authorized_by": "projecteigenaar", "authorized_at": "2026-10-22",
              "reference": "test fixture (not a real authorization)"}


def _run_default(monkeypatch, record):
    from etl.data_quality import validate_production_state
    return validate_production_state(CSV, JSON, record)


def test_production_state_fails_closed_while_record_not_authorized(monkeypatch):
    # the committed record of this PR is NOT_AUTHORIZED: the default production check must refuse the gold JSON
    rec = json.loads(RECORD.read_text(encoding="utf-8"))
    if rec["release_authorization"]["status"] == "AUTHORIZED":
        pytest.skip("owner released")
    with pytest.raises(ValueError, match="NOT_AUTHORIZED"):
        _run_default(monkeypatch, RECORD)


def test_production_state_accepts_authorized_record_without_env(tmp_path, monkeypatch):
    path = record_for(tmp_path, JSON, release_authorization=dict(AUTHORIZED))
    count, report = _run_default(monkeypatch, path)  # no env flags: authorization lives in the record
    assert count == 320 and report["publication_authorized"] is True


@pytest.mark.parametrize("broken", [
    {"status": "AUTHORIZED", "authorized_by": None, "authorized_at": "2026-10-22", "reference": "x"},
    {"status": "AUTHORIZED", "authorized_by": "o", "authorized_at": None, "reference": "x"},
    {"status": "AUTHORIZED", "authorized_by": "o", "authorized_at": "morgen", "reference": "x"},
    {"status": "NOT_AUTHORIZED", "authorized_by": "o", "authorized_at": "2026-10-22", "reference": "x"},
])
def test_production_state_rejects_incomplete_authorization(tmp_path, monkeypatch, broken):
    with pytest.raises(ValueError):
        _run_default(monkeypatch, record_for(tmp_path, JSON, release_authorization=broken))


def test_production_state_rejects_authorized_record_for_other_bytes(tmp_path, monkeypatch):
    data = rows()
    data[5]["gold_index"] *= 1.0001
    target = write(tmp_path, data)
    from etl.data_quality import validate_production_state
    path = record_for(tmp_path, target, release_authorization=dict(AUTHORIZED))
    with pytest.raises(ValueError):  # record matches the bytes, but not the code pin
        validate_production_state(CSV, target, path)


def test_production_state_missing_record_fails_and_null_gold_is_unchanged(tmp_path, monkeypatch):
    from etl.data_quality import validate_production_state
    with pytest.raises(ValueError, match="missing"):
        validate_production_state(CSV, JSON, tmp_path / "nope.json")
    null_json = tmp_path / "null.json"
    null_json.write_bytes((json.dumps(build(CSV), ensure_ascii=False, separators=(",", ":"), allow_nan=False)
                           + "\n").encode())
    count, report = validate_production_state(CSV, null_json, tmp_path / "nope.json")
    assert count == 320 and report is None


def test_cli_committed_without_record_rejected(monkeypatch):
    monkeypatch.setattr("sys.argv", ["dq", "--committed"])
    with pytest.raises(SystemExit):
        main()


def test_unreviewed_gold_eur_oz_fails_even_with_matching_record(tmp_path):
    data = rows()
    data[5]["gold_eur_oz"] = 2500.0
    target = write(tmp_path, data)
    with pytest.raises(ValueError):
        validate_gold_release_committed(CSV, target, record_for(tmp_path, target))


def test_changed_gold_value_fails_against_record(tmp_path):
    data = rows()
    data[7]["gold_index"] = data[7]["gold_index"] * 1.0000001
    target = write(tmp_path, data)
    with pytest.raises(ValueError, match="differ from release record"):
        validate_gold_release_committed(CSV, target, RECORD)


def test_rebuilt_record_but_not_code_pin_fails(tmp_path):
    """A new JSON plus a matching new record is still refused: the code pin must change too."""
    data = rows()
    data[7]["gold_index"] = data[7]["gold_index"] * 1.0000001
    data[7]["gold_grams_per_house"] = data[7]["gold_grams_per_house"] / 1.0000001
    target = write(tmp_path, data)
    with pytest.raises(ValueError, match="code pin"):
        validate_gold_release_committed(CSV, target, record_for(tmp_path, target))


def test_changed_cbs_field_fails(tmp_path):
    data = rows()
    data[3]["house_eur"] = data[3]["house_eur"] + 1
    target = write(tmp_path, data)
    with pytest.raises(ValueError):
        validate_gold_release_committed(CSV, target, record_for(tmp_path, target))


def test_missing_record_fails(tmp_path):
    with pytest.raises(FileNotFoundError):
        validate_gold_release_committed(CSV, JSON, tmp_path / "absent.json")
