"""Opt-in gold mode of etl.data_quality.validate.

All fixtures are SYNTHETIC. They prove the validation gate only; they are not
source data and say nothing about real gold prices or FX rates.
"""
import copy
import csv
import json
from decimal import Decimal as D

import pytest

from etl.data_quality import validate, main
from etl.gold_monthly import build_candidate
from etl.static_export import build

ROWS = [("2000-01", "50", "100000"), ("2000-02", "55", "105000")]


def make(tmp_path):
    src = tmp_path / "housing.csv"
    with src.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "series", "value"])
        for m, hpi, house in ROWS:
            w.writerow([m, "nl_hpi", hpi])
            w.writerow([m, "nl_house_avg_eur", house])
    cand = build_candidate({"2000-01": D("300"), "2000-02": D("320")},
                           {"2000-01": D("1.2"), "2000-02": D("1.25")},
                           {m: D(h) for m, _, h in ROWS}, {"2000-01": 20, "2000-02": 20})
    return src, cand


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setenv("GOLD_PUBLICATION_ENABLED", "true")
    monkeypatch.setenv("GOLD_PUBLICATION_APPROVAL", "APPROVED")


def write(tmp_path, payload):
    t = tmp_path / "monthly.json"
    t.write_text(json.dumps(payload), encoding="utf-8")
    return t


def gold_payload(src, cand):
    return build(src, gold_candidate=cand, gold_publication_approved=True)


def test_gold_mode_accepts_valid_synthetic(tmp_path, enabled):
    src, cand = make(tmp_path)
    target = write(tmp_path, gold_payload(src, cand))
    assert validate(src, target, gold_candidate=cand, gold_approved=True) == 2


def test_default_mode_rejects_gold_json(tmp_path, enabled):
    src, cand = make(tmp_path)
    target = write(tmp_path, gold_payload(src, cand))
    with pytest.raises(ValueError):
        validate(src, target)


def test_default_mode_still_accepts_null_gold(tmp_path, enabled):
    src, _ = make(tmp_path)
    assert validate(src, write(tmp_path, build(src))) == 2


def test_approval_without_candidate_rejected(tmp_path, enabled):
    src, cand = make(tmp_path)
    target = write(tmp_path, gold_payload(src, cand))
    with pytest.raises(ValueError, match="Gold validation requires"):
        validate(src, target, gold_approved=True)


def test_candidate_without_approval_rejected(tmp_path, enabled):
    src, cand = make(tmp_path)
    target = write(tmp_path, gold_payload(src, cand))
    with pytest.raises(ValueError, match="Gold validation requires"):
        validate(src, target, gold_candidate=cand)


@pytest.mark.parametrize("env", [
    {}, {"GOLD_PUBLICATION_ENABLED": "true"}, {"GOLD_PUBLICATION_APPROVAL": "APPROVED"},
    {"GOLD_PUBLICATION_ENABLED": "TRUE", "GOLD_PUBLICATION_APPROVAL": "APPROVED"},
    {"GOLD_PUBLICATION_ENABLED": "true", "GOLD_PUBLICATION_APPROVAL": "DENIED"},
])
def test_gold_mode_without_env_rejected(tmp_path, monkeypatch, env):
    src, cand = make(tmp_path)
    with monkeypatch.context() as m:
        m.setenv("GOLD_PUBLICATION_ENABLED", "true")
        m.setenv("GOLD_PUBLICATION_APPROVAL", "APPROVED")
        target = write(tmp_path, gold_payload(src, cand))
    monkeypatch.delenv("GOLD_PUBLICATION_ENABLED", raising=False)
    monkeypatch.delenv("GOLD_PUBLICATION_APPROVAL", raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    with pytest.raises(ValueError, match="Gold validation requires"):
        validate(src, target, gold_candidate=cand, gold_approved=True)


MUTATIONS = {
    "tampered_gold_index": lambda p: p["data"][1].update({"gold_index": 999.0}),
    "tampered_grams": lambda p: p["data"][0].update({"gold_grams_per_house": 1.0}),
    "extra_month": lambda p: p["data"].append({**p["data"][-1], "period": "2000-03"}),
    "missing_month": lambda p: p["data"].pop(),
    "gold_eur_oz_not_null": lambda p: p["data"][0].update({"gold_eur_oz": 300.0}),
    "wrong_index_base": lambda p: [r.update({"gold_index": r["gold_index"] * 2}) for r in p["data"]],
    "gold_dropped": lambda p: p["data"][1].update({"gold_index": None, "gold_grams_per_house": None}),
    "house_changed": lambda p: p["data"][0].update({"house_eur": 1.0}),
    "extra_key": lambda p: p.update({"unreviewed": True}),
}


@pytest.mark.parametrize("name", MUTATIONS)
def test_gold_mode_rejects_manipulation(tmp_path, enabled, name):
    src, cand = make(tmp_path)
    payload = gold_payload(src, cand)
    MUTATIONS[name](payload)
    with pytest.raises(ValueError):
        validate(src, write(tmp_path, payload), gold_candidate=cand, gold_approved=True)


def test_gold_mode_rejects_bad_candidate(tmp_path, enabled):
    src, cand = make(tmp_path)
    target = write(tmp_path, gold_payload(src, cand))
    bad = copy.deepcopy(cand)
    bad["data"][0]["gold_eur_oz"] = "999"
    with pytest.raises(ValueError):
        validate(src, target, gold_candidate=bad, gold_approved=True)


def test_gold_mode_rejects_json_without_gold(tmp_path, enabled):
    src, cand = make(tmp_path)
    target = write(tmp_path, build(src))  # null gold although candidate supplied
    with pytest.raises(ValueError, match="differs"):
        validate(src, target, gold_candidate=cand, gold_approved=True)


def test_cli_gold_flags(tmp_path, enabled, monkeypatch):
    src, cand = make(tmp_path)
    target = write(tmp_path, gold_payload(src, cand))
    cfile = tmp_path / "cand.json"
    cfile.write_text(json.dumps(cand), encoding="utf-8")
    base = ["x", "--input", str(src), "--output", str(target)]
    monkeypatch.setattr("sys.argv", base + ["--gold-candidate", str(cfile), "--approve-gold"])
    main()
    monkeypatch.setattr("sys.argv", base)
    with pytest.raises(ValueError):
        main()
