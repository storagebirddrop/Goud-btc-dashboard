"""Release-chain tests for the opt-in gold modes of etl.data_quality.

Housing data is the REAL committed data/cbs-housing.csv. Gold USD/oz and USD/EUR
inputs are SYNTHETIC (deterministic, labelled) -- they prove the validation gate
only and say nothing about real gold prices or FX rates. The real
static_export.build / validate_gold code is called (nothing is mocked).

GOLD-03 pins a PUBLIC JSON-v1 payload (no private candidate is retained), so the
'release record' mode is the one usable in the release chain. All release records
below are SYNTHETIC TEST FIXTURES (fake World Bank/ECB hashes, fake authorizer);
no real approval record exists in this repository.
"""
import copy
import hashlib
import json
from decimal import Decimal as D
from pathlib import Path

import pytest

from etl.data_quality import (EXIT_PREFLIGHT_NOT_AUTHORIZED, main, validate,
                              validate_gold_release, validate_gold_release_record_preflight)
from etl.gold_monthly import build_candidate, parse_housing
from etl.static_export import build

REAL_CSV = Path(__file__).resolve().parents[1] / "data" / "cbs-housing.csv"
REAL_JSON = Path(__file__).resolve().parents[1] / "frontend" / "public" / "data" / "monthly.json"
CBS_SHA = hashlib.sha256(REAL_CSV.read_bytes()).hexdigest()
FAKE_WB = "a" * 64   # SYNTHETIC
FAKE_ECB = "b" * 64  # SYNTHETIC


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv("GOLD_PUBLICATION_ENABLED", raising=False)
    monkeypatch.delenv("GOLD_PUBLICATION_APPROVAL", raising=False)


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setenv("GOLD_PUBLICATION_ENABLED", "true")
    monkeypatch.setenv("GOLD_PUBLICATION_APPROVAL", "APPROVED")


def synthetic_candidate(csv_path, pending_tail=0):
    """SYNTHETIC gold/FX inputs joined to the real CBS house prices."""
    houses = parse_housing(Path(csv_path).read_bytes())
    months = sorted(m for m in houses if m >= "2000-01")
    cut = len(months) - pending_tail
    gold = {m: D("280") + D("0.9") * i for i, m in enumerate(months[:cut])}
    fx = {m: D("1.05") + D("0.0005") * (i % 40) for i, m in enumerate(months[:cut])}
    counts = {m: 20 for m in months[:cut]}
    return build_candidate(gold, fx, houses, counts)


def public_bytes(payload):
    return (json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n").encode()


def make_record(raw_or_sha, payload, *, status="AUTHORIZED"):
    """SYNTHETIC release record for a payload (valid unless the test mutates it)."""
    sha = raw_or_sha if isinstance(raw_or_sha, str) else hashlib.sha256(raw_or_sha).hexdigest()
    rows = payload["data"]
    return {
        "schema_version": 1,
        "artifact": {"sha256": sha, "months": len(rows),
                     "first_period": rows[0]["period"], "last_period": rows[-1]["period"]},
        "fields_published": ["gold_index", "gold_grams_per_house"],
        "methodology": {"adr": "ADR-004", "status": "ACCEPTED"},
        "sources": {"worldbank_workbook_sha256": FAKE_WB, "ecb_sha256": FAKE_ECB, "cbs_csv_sha256": CBS_SHA},
        "candidate_validation": {"candidate_sha256": sha, "review_run": "SYNTHETIC-TEST-RUN-1", "result": "PASS"},
        "release_authorization": (
            {"status": "AUTHORIZED", "authorized_by": "synthetic-owner", "authorized_at": "2026-10-20",
             "reference": "SYNTHETIC test reference"} if status == "AUTHORIZED" else
            {"status": "NOT_AUTHORIZED", "authorized_by": "", "authorized_at": "", "reference": ""}),
    }


@pytest.fixture
def release(tmp_path, monkeypatch):
    """Build the gold public JSON with the real exporter, as GOLD-02 does."""
    cand = synthetic_candidate(REAL_CSV)
    with monkeypatch.context() as m:
        m.setenv("GOLD_PUBLICATION_ENABLED", "true")
        m.setenv("GOLD_PUBLICATION_APPROVAL", "APPROVED")
        payload = build(REAL_CSV, gold_candidate=cand, gold_publication_approved=True)
    raw = public_bytes(payload)
    target = tmp_path / "monthly.json"
    target.write_bytes(raw)
    return cand, payload, target, make_record(raw, payload)


def repin(tmp_path, payload):
    """Write mutated bytes AND a record matching them (attacker re-pins)."""
    target = tmp_path / "mutated.json"
    raw = public_bytes(payload)
    target.write_bytes(raw)
    rec = make_record(raw, payload if payload.get("data") else {"data": [{"period": "x"}]})
    return target, rec


def run_release(target, record, **kw):
    return validate(REAL_CSV, target, gold_approved=True, gold_release_record=record, **kw)


@pytest.fixture
def null_gold_json(tmp_path):
    """The pre-release (GOLD-01 HOLD) public JSON, regenerated from the CSV: gold fields all null."""
    target = tmp_path / "null-gold.json"
    target.write_bytes(public_bytes(build(REAL_CSV)))
    return target


def test_default_mode_accepts_null_gold_json_only(null_gold_json):
    assert validate(REAL_CSV, null_gold_json) == 320


def test_default_mode_rejects_the_published_gold_json():
    """Fail-closed default: the published GOLD-03 JSON is only valid in committed-record mode."""
    with pytest.raises(ValueError, match="Unexpected unverified gold|differs"):
        validate(REAL_CSV, REAL_JSON)


def test_default_validator_rejects_gold_json_from_real_chain(release):
    _, _, target, _ = release
    with pytest.raises(ValueError, match="Unexpected unverified gold|differs"):
        validate(REAL_CSV, target)


def test_full_chain_candidate_mode(release, enabled):
    cand, payload, target, _ = release
    assert payload["data"][0]["gold_index"] == 100
    assert all(r["gold_eur_oz"] is None for r in payload["data"])
    assert validate(REAL_CSV, target, gold_candidate=cand, gold_approved=True) == 320


def test_full_chain_release_record_mode(release, enabled):
    _, _, target, rec = release
    assert run_release(target, rec) == 320


def test_release_record_from_file(release, enabled, tmp_path):
    _, _, target, rec = release
    path = tmp_path / "record.json"
    path.write_text(json.dumps(rec), encoding="utf-8")
    assert run_release(target, path) == 320
    assert run_release(target, str(path)) == 320


def test_full_chain_without_env_fails(release):
    cand, _, target, rec = release
    with pytest.raises(ValueError, match="Gold validation requires"):
        validate(REAL_CSV, target, gold_candidate=cand, gold_approved=True)
    with pytest.raises(ValueError, match="Gold validation requires"):
        run_release(target, rec)


def test_pending_tail_allowed_in_release_mode(tmp_path, enabled):
    cand = synthetic_candidate(REAL_CSV, pending_tail=2)
    payload = build(REAL_CSV, gold_candidate=cand, gold_publication_approved=True)
    assert payload["data"][-1]["gold_index"] is None
    target, rec = repin(tmp_path, payload)
    assert run_release(target, rec) == 320


@pytest.mark.parametrize("env", [
    {"GOLD_PUBLICATION_ENABLED": "True", "GOLD_PUBLICATION_APPROVAL": "APPROVED"},
    {"GOLD_PUBLICATION_ENABLED": "true ", "GOLD_PUBLICATION_APPROVAL": "APPROVED"},
    {"GOLD_PUBLICATION_ENABLED": " true", "GOLD_PUBLICATION_APPROVAL": "APPROVED"},
    {"GOLD_PUBLICATION_ENABLED": "1", "GOLD_PUBLICATION_APPROVAL": "APPROVED"},
    {"GOLD_PUBLICATION_ENABLED": "true", "GOLD_PUBLICATION_APPROVAL": "approved"},
    {"GOLD_PUBLICATION_ENABLED": "true", "GOLD_PUBLICATION_APPROVAL": "APPROVED "},
    {"GOLD_PUBLICATION_ENABLED": "true", "GOLD_PUBLICATION_APPROVAL": ""},
    {"GOLD_PUBLICATION_ENABLED": "", "GOLD_PUBLICATION_APPROVAL": "APPROVED"},
])
def test_env_variants_rejected(release, monkeypatch, env):
    cand, _, target, rec = release
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    with pytest.raises(ValueError, match="Gold validation requires"):
        validate(REAL_CSV, target, gold_candidate=cand, gold_approved=True)
    with pytest.raises(ValueError, match="Gold validation requires"):
        run_release(target, rec)


@pytest.mark.parametrize("approved", [1, "yes", "true", "APPROVED", 1.0, [True], None, False, 0])
def test_truthy_non_true_approval_rejected(release, enabled, approved):
    cand, _, target, rec = release
    with pytest.raises(ValueError, match="Gold validation requires"):
        validate(REAL_CSV, target, gold_candidate=cand, gold_approved=approved)
    with pytest.raises(ValueError, match="Gold validation requires"):
        validate(REAL_CSV, target, gold_approved=approved, gold_release_record=rec)


@pytest.mark.parametrize("bad_candidate", [{}, [], "x", {"data": [], "coverage": [], "publication_authorized": False}])
def test_empty_or_invalid_candidate_rejected(release, enabled, bad_candidate):
    _, _, target, _ = release
    with pytest.raises(ValueError):
        validate(REAL_CSV, target, gold_candidate=bad_candidate, gold_approved=True)


@pytest.mark.parametrize("name", ["no_coverage", "authorized_true", "authorized_missing", "extra_month_in_data"])
def test_candidate_metadata_attacks_rejected(release, enabled, name):
    cand, _, target, _ = release
    bad = copy.deepcopy(cand)
    if name == "no_coverage":
        del bad["coverage"]
    elif name == "authorized_true":
        bad["publication_authorized"] = True
    elif name == "authorized_missing":
        del bad["publication_authorized"]
    else:
        bad["data"].append(dict(bad["data"][-1], month="2030-01"))
    with pytest.raises(ValueError):
        validate(REAL_CSV, target, gold_candidate=bad, gold_approved=True)


def test_candidate_plus_record_ambiguous_rejected(release, enabled):
    cand, _, target, rec = release
    with pytest.raises(ValueError, match="exactly one"):
        validate(REAL_CSV, target, gold_candidate=cand, gold_approved=True, gold_release_record=rec)


def test_record_without_approval_rejected(release, enabled):
    _, _, target, rec = release
    with pytest.raises(ValueError, match="Gold validation requires"):
        validate(REAL_CSV, target, gold_release_record=rec)


def test_missing_record_rejected(release, enabled, tmp_path):
    _, _, target, _ = release
    with pytest.raises(FileNotFoundError):
        run_release(target, tmp_path / "does-not-exist.json")
    # approval flag alone, no candidate and no record, is not an accepted mode
    with pytest.raises(ValueError, match="exactly one"):
        validate(REAL_CSV, target, gold_approved=True)


@pytest.mark.parametrize("bare", ["a" * 64, "", 123, b"a" * 64, ["a" * 64], {"sha256": "a" * 64}])
def test_bare_sha_instead_of_record_rejected(release, enabled, bare):
    _, _, target, _ = release
    if isinstance(bare, str) and bare:
        # a bare sha string is interpreted as a record PATH: never as a pin
        with pytest.raises(OSError):
            run_release(target, bare)
    else:
        with pytest.raises((ValueError, OSError)):
            run_release(target, bare)


def test_removed_pin_parameter_not_accepted(release, enabled):
    _, _, target, rec = release
    with pytest.raises(TypeError):
        validate(REAL_CSV, target, gold_approved=True, gold_public_sha256=rec["artifact"]["sha256"])


def set_path(rec, path, value):
    node = rec
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value


def del_path(rec, path):
    node = rec
    for key in path[:-1]:
        node = node[key]
    del node[path[-1]]


RECORD_MUTATIONS = {
    "artifact_sha_wrong": lambda r: set_path(r, ("artifact", "sha256"), "0" * 64),
    "artifact_sha_malformed": lambda r: set_path(r, ("artifact", "sha256"), "A" * 64),
    "artifact_sha_not_str": lambda r: set_path(r, ("artifact", "sha256"), 123),
    "months_wrong": lambda r: set_path(r, ("artifact", "months"), 319),
    "months_bool": lambda r: set_path(r, ("artifact", "months"), True),
    "months_str": lambda r: set_path(r, ("artifact", "months"), "320"),
    "first_wrong": lambda r: set_path(r, ("artifact", "first_period"), "2000-02"),
    "first_malformed": lambda r: set_path(r, ("artifact", "first_period"), "2000-13"),
    "last_wrong": lambda r: set_path(r, ("artifact", "last_period"), "2026-07"),
    "cbs_sha_wrong": lambda r: set_path(r, ("sources", "cbs_csv_sha256"), "0" * 64),
    "wb_sha_malformed": lambda r: set_path(r, ("sources", "worldbank_workbook_sha256"), "xyz"),
    "ecb_sha_missing": lambda r: del_path(r, ("sources", "ecb_sha256")),
    "candidate_sha_differs": lambda r: set_path(r, ("candidate_validation", "candidate_sha256"), "c" * 64),
    "candidate_result_fail": lambda r: set_path(r, ("candidate_validation", "result"), "FAIL"),
    "candidate_result_missing": lambda r: del_path(r, ("candidate_validation", "result")),
    "review_run_empty": lambda r: set_path(r, ("candidate_validation", "review_run"), " "),
    "adr_other": lambda r: set_path(r, ("methodology", "adr"), "ADR-005"),
    "adr_status_proposed": lambda r: set_path(r, ("methodology", "status"), "PROPOSED"),
    "fields_with_raw_gold": lambda r: set_path(r, ("fields_published",), ["gold_index", "gold_grams_per_house", "gold_eur_oz"]),
    "fields_only_one": lambda r: set_path(r, ("fields_published",), ["gold_index"]),
    "fields_reordered": lambda r: set_path(r, ("fields_published",), ["gold_grams_per_house", "gold_index"]),
    "unknown_top_key": lambda r: r.update(extra=1),
    "unknown_nested_key": lambda r: r["artifact"].update(extra=1),
    "missing_top_key": lambda r: r.pop("sources"),
    "schema_version_2": lambda r: r.update(schema_version=2),
    "schema_version_bool": lambda r: r.update(schema_version=True),
    "auth_not_authorized": lambda r: set_path(r, ("release_authorization", "status"), "NOT_AUTHORIZED"),
    "auth_status_empty": lambda r: set_path(r, ("release_authorization", "status"), ""),
    "auth_missing": lambda r: r.pop("release_authorization"),
    "auth_by_empty": lambda r: set_path(r, ("release_authorization", "authorized_by"), ""),
    "auth_reference_empty": lambda r: set_path(r, ("release_authorization", "reference"), "  "),
    "auth_at_empty": lambda r: set_path(r, ("release_authorization", "authorized_at"), ""),
    "auth_at_not_date": lambda r: set_path(r, ("release_authorization", "authorized_at"), "yesterday"),
    "auth_at_impossible": lambda r: set_path(r, ("release_authorization", "authorized_at"), "2026-13-45"),
    "auth_at_number": lambda r: set_path(r, ("release_authorization", "authorized_at"), 20261020),
    "auth_extra_key": lambda r: r["release_authorization"].update(extra=1),
    "record_is_list": lambda r: r.clear() or r.update({}),
}


@pytest.mark.parametrize("name", RECORD_MUTATIONS)
def test_every_wrong_record_field_rejected(release, enabled, name):
    _, _, target, rec = release
    bad = copy.deepcopy(rec)
    RECORD_MUTATIONS[name](bad)
    with pytest.raises(ValueError):
        run_release(target, bad)


def test_record_not_object_rejected(release, enabled):
    _, _, target, rec = release
    with pytest.raises(ValueError):
        run_release(target, [rec])


def test_wrong_artifact_bytes_rejected(release, enabled):
    _, _, target, rec = release
    bad = copy.deepcopy(rec)
    bad["artifact"]["sha256"] = bad["candidate_validation"]["candidate_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="pinned sha256"):
        run_release(target, bad)


def test_any_byte_change_breaks_record(release, enabled):
    _, _, target, rec = release
    target.write_bytes(target.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="pinned sha256"):
        run_release(target, rec)


def test_cbs_baseline_change_breaks_record(release, enabled, tmp_path):
    _, _, target, rec = release
    other = tmp_path / "other.csv"
    other.write_bytes(REAL_CSV.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="CBS csv sha256"):
        validate(other, target, gold_approved=True, gold_release_record=rec)


def test_real_null_gold_json_not_valid_as_gold_release(enabled, null_gold_json):
    raw = null_gold_json.read_bytes()
    rec = make_record(raw, json.loads(raw))
    with pytest.raises(ValueError, match="basis"):
        run_release(null_gold_json, rec)


def _mutate_row(i, **kw):
    return lambda p: p["data"][i].update(kw)


PINNED_MUTATIONS = {
    "index_one_value_changed": lambda p: p["data"][10].update(gold_index=p["data"][10]["gold_index"] * 1.000001),
    "grams_one_value_changed": lambda p: p["data"][10].update(gold_grams_per_house=p["data"][10]["gold_grams_per_house"] * 1.000001),
    "eur_oz_published": _mutate_row(5, gold_eur_oz=1234.5),
    "index_base_not_100": lambda p: [r.update(gold_index=r["gold_index"] * 2) for r in p["data"]],
    "partial_months_only": lambda p: [r.update(gold_index=None, gold_grams_per_house=None) for r in p["data"][:100]],
    "gap_in_middle": _mutate_row(50, gold_index=None, gold_grams_per_house=None),
    "one_field_null": _mutate_row(50, gold_index=None),
    "bool_value": _mutate_row(7, gold_index=True),
    "string_value": _mutate_row(7, gold_index="101.5"),
    "zero_value": _mutate_row(7, gold_grams_per_house=0),
    "negative_value": _mutate_row(7, gold_grams_per_house=-1.0),
    "house_changed": _mutate_row(3, house_eur=1.0),
    "hpi_changed": _mutate_row(3, hpi=1.0),
    "hpi_index_changed": _mutate_row(3, hpi_index=1.0),
    "extra_row_field": _mutate_row(3, extra=1),
    "missing_row_field": lambda p: p["data"][3].pop("hpi"),
    "top_level_extra_key": lambda p: p.update(unreviewed=True),
    "row_order_swapped": lambda p: p["data"].insert(0, p["data"].pop(1)),
    "missing_month": lambda p: p["data"].pop(100),
    "duplicate_month": lambda p: p["data"].insert(100, dict(p["data"][100])),
    "extra_month": lambda p: p["data"].append(dict(p["data"][-1], period="2099-01")),
    "empty_data": lambda p: p.update(data=[]),
}


@pytest.mark.parametrize("name", PINNED_MUTATIONS)
def test_release_mode_structural_checks_even_with_matching_record(release, tmp_path, enabled, name):
    """The attacker re-pins the mutated bytes, so only the content checks can catch it."""
    _, payload, _, _ = release
    mutated = copy.deepcopy(payload)
    PINNED_MUTATIONS[name](mutated)
    target, rec = repin(tmp_path, mutated)
    with pytest.raises(ValueError):
        run_release(target, rec)


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_json_tokens_rejected(release, tmp_path, enabled, token):
    _, payload, target, _ = release
    raw = target.read_text(encoding="utf-8").replace('"gold_index":100.0', f'"gold_index":{token}', 1)
    assert token in raw
    bad = tmp_path / "bad.json"
    bad.write_text(raw, encoding="utf-8")
    with pytest.raises(ValueError, match="Non-finite"):
        run_release(bad, make_record(bad.read_bytes(), payload))


def test_sub_tolerance_tamper_is_caught_only_by_hash(release, tmp_path, enabled):
    """Documents the limit: a 1e-12 relative change passes content checks, never the hash."""
    _, payload, target, rec = release
    mutated = copy.deepcopy(payload)
    mutated["data"][10]["gold_index"] *= 1 + 1e-12
    other, other_rec = repin(tmp_path, mutated)
    assert run_release(other, other_rec) == 320
    with pytest.raises(ValueError, match="pinned sha256"):
        run_release(other, rec)


def test_gold_before_2000_rejected_in_release_mode(tmp_path, enabled):
    lines = ["date,series,value"]
    for y in range(1995, 2001):
        for m in range(1, 13):
            lines.append(f"{y}-{m:02d},nl_house_avg_eur,{100000 + (y - 1995) * 1000 + m}")
            if y >= 2000:
                lines.append(f"{y}-{m:02d},nl_hpi,{50 + m}")
    csv_path = tmp_path / "h.csv"
    csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    payload = build(csv_path)
    payload["data"][0].update(gold_index=100.0, gold_grams_per_house=1.0)  # 1995-01
    target, rec = repin(tmp_path, payload)
    rec["sources"]["cbs_csv_sha256"] = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    with pytest.raises(ValueError):
        validate(csv_path, target, gold_approved=True, gold_release_record=rec)


# ---- levels, preflight (non-authorizing rehearsal) ----

def test_report_separates_levels(release, enabled):
    _, _, target, rec = release
    report = validate_gold_release(REAL_CSV, target, rec, gold_approved=True)
    assert report["hash_verified"] == {"artifact_sha256": rec["artifact"]["sha256"], "cbs_csv_sha256": CBS_SHA}
    assert set(report["attested_not_verified"]) == {"SOURCE", "METHODOLOGY APPROVED", "PUBLICATION AUTHORIZED"}
    assert report["attested_not_verified"]["SOURCE"]["ecb_sha256"] == FAKE_ECB
    assert report["content_validated"] and report["publication_authorized"] is True


def test_preflight_never_authorizes_even_with_authorized_record(release):
    """No env, no approval flag needed; the result is never 'authorized'."""
    _, _, target, rec = release
    report = validate_gold_release_record_preflight(REAL_CSV, target, rec)
    assert report["publication_authorized"] is False
    assert "NOT AUTHORIZED" in report["attested_not_verified"]["PUBLICATION AUTHORIZED"]


def test_preflight_accepts_not_authorized_record(release):
    _, payload, target, _ = release
    rec = make_record(target.read_bytes(), payload, status="NOT_AUTHORIZED")
    assert validate_gold_release_record_preflight(REAL_CSV, target, rec)["publication_authorized"] is False


def test_not_authorized_record_refused_by_release_validation(release, enabled):
    _, payload, target, _ = release
    rec = make_record(target.read_bytes(), payload, status="NOT_AUTHORIZED")
    with pytest.raises(ValueError, match="NOT_AUTHORIZED"):
        run_release(target, rec)


@pytest.mark.parametrize("name", [n for n in RECORD_MUTATIONS if not n.startswith("auth_") and n != "record_is_list"])
def test_preflight_still_checks_hashes_and_content(release, name):
    _, _, target, rec = release
    bad = copy.deepcopy(rec)
    RECORD_MUTATIONS[name](bad)
    with pytest.raises(ValueError):
        validate_gold_release_record_preflight(REAL_CSV, target, bad)


def test_preflight_rejects_content_tampering(release, tmp_path):
    _, payload, _, _ = release
    mutated = copy.deepcopy(payload)
    mutated["data"][10]["gold_index"] *= 1.01
    target, rec = repin(tmp_path, mutated)
    with pytest.raises(ValueError, match="inconsistent"):
        validate_gold_release_record_preflight(REAL_CSV, target, rec)


def test_preflight_rejects_real_null_gold_json(null_gold_json):
    raw = null_gold_json.read_bytes()
    with pytest.raises(ValueError, match="basis"):
        validate_gold_release_record_preflight(REAL_CSV, null_gold_json, make_record(raw, json.loads(raw)))


# ---- CLI ----

def _write_record(tmp_path, rec):
    path = tmp_path / "record.json"
    path.write_text(json.dumps(rec), encoding="utf-8")
    return str(path)


def test_cli_release_record_flags(release, enabled, monkeypatch, tmp_path, capsys):
    _, _, target, rec = release
    path = _write_record(tmp_path, rec)
    base = ["x", "--input", str(REAL_CSV), "--output", str(target)]
    monkeypatch.setattr("sys.argv", base + ["--gold-release-record", path, "--approve-gold"])
    main()
    out = capsys.readouterr().out
    for label in ("HASH VERIFIED", "CONTENT VALIDATED", "ATTESTED BY RECORD, NOT VERIFIED BY CODE",
                  "SOURCE", "METHODOLOGY APPROVED", "PUBLICATION AUTHORIZED"):
        assert label in out
    assert "NOT AUTHORIZED" not in out
    monkeypatch.setattr("sys.argv", base + ["--gold-release-record", path])  # no --approve-gold
    with pytest.raises(ValueError):
        main()
    monkeypatch.setattr("sys.argv", base)  # default mode still rejects gold
    with pytest.raises(ValueError):
        main()


def test_cli_release_record_without_env_rejected(release, monkeypatch, tmp_path):
    _, _, target, rec = release
    path = _write_record(tmp_path, rec)
    monkeypatch.setattr("sys.argv", ["x", "--input", str(REAL_CSV), "--output", str(target),
                                     "--gold-release-record", path, "--approve-gold"])
    with pytest.raises(ValueError, match="Gold validation requires"):
        main()


def test_cli_bare_sha_flag_removed(release, enabled, monkeypatch):
    _, _, target, rec = release
    monkeypatch.setattr("sys.argv", ["x", "--input", str(REAL_CSV), "--output", str(target),
                                     "--gold-public-sha256", rec["artifact"]["sha256"], "--approve-gold"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2


def test_cli_preflight_exit_code_and_message(release, monkeypatch, tmp_path, capsys):
    """Works without env/approval and never reports an authorized release."""
    _, _, target, rec = release
    path = _write_record(tmp_path, rec)
    monkeypatch.setattr("sys.argv", ["x", "--input", str(REAL_CSV), "--output", str(target),
                                     "--gold-release-record", path, "--preflight"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == EXIT_PREFLIGHT_NOT_AUTHORIZED == 3
    out = capsys.readouterr().out
    assert "PUBLICATION NOT AUTHORIZED" in out and "HASH VERIFIED" in out


def test_cli_preflight_failure_is_error_not_exit_3(release, monkeypatch, tmp_path):
    _, _, target, rec = release
    rec["artifact"]["sha256"] = "0" * 64
    path = _write_record(tmp_path, rec)
    monkeypatch.setattr("sys.argv", ["x", "--input", str(REAL_CSV), "--output", str(target),
                                     "--gold-release-record", path, "--preflight"])
    with pytest.raises(ValueError):
        main()


@pytest.mark.parametrize("extra", [["--approve-gold"], ["--gold-candidate", "x.json"], []])
def test_cli_preflight_flag_combinations(release, monkeypatch, tmp_path, extra):
    _, _, target, rec = release
    args = ["x", "--input", str(REAL_CSV), "--output", str(target), "--preflight"]
    if extra != []:
        args += ["--gold-release-record", _write_record(tmp_path, rec)]
    monkeypatch.setattr("sys.argv", args + extra)
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
