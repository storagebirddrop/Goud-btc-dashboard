"""Release-chain tests for the opt-in gold modes of etl.data_quality.

Housing data is the REAL committed data/cbs-housing.csv. Gold USD/oz and USD/EUR
inputs are SYNTHETIC (deterministic, labelled) -- they prove the validation gate
only and say nothing about real gold prices or FX rates. The real
static_export.build / validate_gold code is called (nothing is mocked).

GOLD-03 pins a PUBLIC JSON-v1 payload (no private candidate is retained), so the
'pinned public JSON' mode is the one usable in the release chain.
"""
import copy
import hashlib
import json
from decimal import Decimal as D
from pathlib import Path

import pytest

from etl.data_quality import main, validate
from etl.gold_monthly import build_candidate, parse_housing
from etl.static_export import build

REAL_CSV = Path(__file__).resolve().parents[1] / "data" / "cbs-housing.csv"
REAL_JSON = Path(__file__).resolve().parents[1] / "frontend" / "public" / "data" / "monthly.json"


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
    return cand, payload, target, hashlib.sha256(raw).hexdigest()


def repin(tmp_path, payload):
    target = tmp_path / "mutated.json"
    raw = public_bytes(payload)
    target.write_bytes(raw)
    return target, hashlib.sha256(raw).hexdigest()


def test_real_json_default_mode_unchanged():
    assert validate(REAL_CSV, REAL_JSON) == 320


def test_default_validator_rejects_gold_json_from_real_chain(release):
    _, _, target, _ = release
    with pytest.raises(ValueError, match="Unexpected unverified gold|differs"):
        validate(REAL_CSV, target)


def test_full_chain_candidate_mode(release, enabled):
    cand, payload, target, _ = release
    assert payload["data"][0]["gold_index"] == 100
    assert all(r["gold_eur_oz"] is None for r in payload["data"])
    assert validate(REAL_CSV, target, gold_candidate=cand, gold_approved=True) == 320


def test_full_chain_pinned_public_mode(release, enabled):
    _, _, target, sha = release
    assert validate(REAL_CSV, target, gold_approved=True, gold_public_sha256=sha) == 320


def test_full_chain_without_env_fails(release):
    cand, _, target, sha = release
    with pytest.raises(ValueError, match="Gold validation requires"):
        validate(REAL_CSV, target, gold_candidate=cand, gold_approved=True)
    with pytest.raises(ValueError, match="Gold validation requires"):
        validate(REAL_CSV, target, gold_approved=True, gold_public_sha256=sha)


def test_pending_tail_allowed_in_pinned_mode(tmp_path, monkeypatch, enabled):
    cand = synthetic_candidate(REAL_CSV, pending_tail=2)
    payload = build(REAL_CSV, gold_candidate=cand, gold_publication_approved=True)
    assert payload["data"][-1]["gold_index"] is None
    target, sha = repin(tmp_path, payload)
    assert validate(REAL_CSV, target, gold_approved=True, gold_public_sha256=sha) == 320


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
    cand, _, target, sha = release
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    with pytest.raises(ValueError, match="Gold validation requires"):
        validate(REAL_CSV, target, gold_candidate=cand, gold_approved=True)
    with pytest.raises(ValueError, match="Gold validation requires"):
        validate(REAL_CSV, target, gold_approved=True, gold_public_sha256=sha)


@pytest.mark.parametrize("approved", [1, "yes", "true", "APPROVED", 1.0, [True], None, False, 0])
def test_truthy_non_true_approval_rejected(release, enabled, approved):
    cand, _, target, sha = release
    with pytest.raises(ValueError, match="Gold validation requires"):
        validate(REAL_CSV, target, gold_candidate=cand, gold_approved=approved)
    with pytest.raises(ValueError, match="Gold validation requires"):
        validate(REAL_CSV, target, gold_approved=approved, gold_public_sha256=sha)


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


def test_candidate_plus_pin_ambiguous_rejected(release, enabled):
    cand, _, target, sha = release
    with pytest.raises(ValueError, match="exactly one"):
        validate(REAL_CSV, target, gold_candidate=cand, gold_approved=True, gold_public_sha256=sha)


def test_pin_without_approval_rejected(release, enabled):
    _, _, target, sha = release
    with pytest.raises(ValueError, match="Gold validation requires"):
        validate(REAL_CSV, target, gold_public_sha256=sha)


@pytest.mark.parametrize("pin", ["", "abc", "A" * 64, " " + "a" * 63, "g" * 64, 123, b"a" * 64])
def test_malformed_pin_rejected(release, enabled, pin):
    _, _, target, _ = release
    with pytest.raises(ValueError):
        validate(REAL_CSV, target, gold_approved=True, gold_public_sha256=pin)


def test_wrong_pin_rejected(release, enabled):
    _, _, target, _ = release
    with pytest.raises(ValueError, match="pinned sha256"):
        validate(REAL_CSV, target, gold_approved=True, gold_public_sha256="0" * 64)


def test_any_byte_change_breaks_pin(release, enabled):
    _, _, target, sha = release
    target.write_bytes(target.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="pinned sha256"):
        validate(REAL_CSV, target, gold_approved=True, gold_public_sha256=sha)


def test_real_null_gold_json_not_valid_as_gold_release(enabled):
    sha = hashlib.sha256(REAL_JSON.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="basis"):
        validate(REAL_CSV, REAL_JSON, gold_approved=True, gold_public_sha256=sha)


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
def test_pinned_mode_structural_checks_even_with_matching_pin(release, tmp_path, enabled, name):
    """The attacker re-pins the mutated bytes, so only the structural checks can catch it."""
    _, payload, _, _ = release
    mutated = copy.deepcopy(payload)
    PINNED_MUTATIONS[name](mutated)
    target, sha = repin(tmp_path, mutated)
    with pytest.raises(ValueError):
        validate(REAL_CSV, target, gold_approved=True, gold_public_sha256=sha)


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_json_tokens_rejected(release, tmp_path, enabled, token):
    _, _, target, _ = release
    raw = target.read_text(encoding="utf-8").replace('"gold_index":100.0', f'"gold_index":{token}', 1)
    assert token in raw
    bad = tmp_path / "bad.json"
    bad.write_text(raw, encoding="utf-8")
    sha = hashlib.sha256(bad.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="Non-finite"):
        validate(REAL_CSV, bad, gold_approved=True, gold_public_sha256=sha)


def test_sub_tolerance_tamper_is_caught_only_by_pin(release, tmp_path, enabled):
    """Documents the limit: a 1e-12 relative change passes structure but never the pin."""
    _, payload, target, sha = release
    mutated = copy.deepcopy(payload)
    mutated["data"][10]["gold_index"] *= 1 + 1e-12
    other, other_sha = repin(tmp_path, mutated)
    assert validate(REAL_CSV, other, gold_approved=True, gold_public_sha256=other_sha) == 320
    with pytest.raises(ValueError, match="pinned sha256"):
        validate(REAL_CSV, other, gold_approved=True, gold_public_sha256=sha)


def test_gold_before_2000_rejected_in_pinned_mode(tmp_path, enabled):
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
    target, sha = repin(tmp_path, payload)
    with pytest.raises(ValueError):
        validate(csv_path, target, gold_approved=True, gold_public_sha256=sha)


def test_cli_pinned_flags(release, enabled, monkeypatch):
    _, _, target, sha = release
    base = ["x", "--input", str(REAL_CSV), "--output", str(target)]
    monkeypatch.setattr("sys.argv", base + ["--gold-public-sha256", sha, "--approve-gold"])
    main()
    monkeypatch.setattr("sys.argv", base + ["--gold-public-sha256", sha])  # no --approve-gold
    with pytest.raises(ValueError):
        main()
    monkeypatch.setattr("sys.argv", base)  # default mode still rejects gold
    with pytest.raises(ValueError):
        main()
