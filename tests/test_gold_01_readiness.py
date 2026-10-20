"""GOLD-01 readiness facts (offline, synthetic inputs only).

Evidence for docs/research/GOLD_01_TECHNICAL_METHODOLOGY.md. These tests change no
behaviour and authorize nothing; they pin facts the readiness assessment relies on.
"""
from decimal import Decimal as D

import pytest

from etl.gold_monthly import GRAMS, build_candidate, parse_ecb
from etl.static_export import build, validate_gold


def _candidate(n=3):
    rows = build("data/cbs-housing.csv")["data"][:n]
    months = [r["period"] for r in rows]
    homes = {r["period"]: D(str(r["house_eur"])) for r in rows}
    gold = {m: D("281.7") + D(i) * D("13.3") for i, m in enumerate(months)}
    fx = {m: D("0.9") + D(i) / D(50) for i, m in enumerate(months)}
    return build_candidate(gold, fx, homes, {m: 20 for m in months}), homes, gold, fx


def test_ecb_monthly_mean_uses_only_present_days_without_imputation():
    raw = (b"TIME_PERIOD,OBS_VALUE,CURRENCY,CURRENCY_DENOM\n"
           b"2000-01-03,1.0,USD,EUR\n2000-01-04,1.5,USD,EUR\n2000-01-07,2.0,USD,EUR\n")
    fx, counts, _ = parse_ecb(raw)
    assert fx["2000-01"] == D("1.5") and counts["2000-01"] == 3  # no calendar-day divisor


def test_empty_ecb_observation_is_skipped_not_filled():
    raw = (b"TIME_PERIOD,OBS_VALUE,CURRENCY,CURRENCY_DENOM\n"
           b"2000-01-03,1.0,USD,EUR\n2000-01-04,,USD,EUR\n2000-01-05,3.0,USD,EUR\n")
    fx, counts, days = parse_ecb(raw)
    assert fx["2000-01"] == D("2") and counts["2000-01"] == 2 and days == 2


def test_no_minimum_fx_day_count_exists_for_a_month():
    # Known gap: a month with a single FX day is accepted (ADR-004 sets no minimum).
    fx, counts, _ = parse_ecb(b"TIME_PERIOD,OBS_VALUE\n2000-01-03,1.0\n")
    cand = build_candidate({"2000-01": D(300)}, fx, {"2000-01": D(1000)}, counts)
    assert cand["data"][0]["fx_days"] == 1


def test_adr004_formulas_exact_in_decimal():
    cand, homes, gold, fx = _candidate()
    base = gold["2000-01"] / fx["2000-01"]
    for r in cand["data"]:
        m = r["month"]
        eur = gold[m] / fx[m]
        assert D(r["gold_eur_oz"]) == eur
        assert D(r["gold_eur_gram"]) == eur / GRAMS
        assert D(r["gold_grams_per_house"]) == homes[m] / (eur / GRAMS)
        assert D(r["gold_index"]) == 100 * eur / base
    assert D(cand["data"][0]["gold_index"]) == 100


def test_public_gold_fields_allow_exact_backcalculation_of_eur_per_oz():
    """gold_eur_oz stays null, yet house_eur * 31.1034768 / gold_grams_per_house recovers it."""
    cand, homes, gold, fx = _candidate()
    rows = validate_gold(cand, {m: {"house_eur": float(h)} for m, h in homes.items()})
    for m, vals in rows.items():
        eur_back = float(homes[m]) * 31.1034768 / vals["gold_grams_per_house"]
        assert eur_back == pytest.approx(float(gold[m] / fx[m]), rel=1e-12)


def test_validate_gold_returns_unrounded_floats():
    cand, homes, _, _ = _candidate()
    rows = validate_gold(cand, {m: {"house_eur": float(h)} for m, h in homes.items()})
    assert len(repr(rows["2000-02"]["gold_index"])) > 12  # full float precision, no rounding policy


def test_candidate_never_authorizes_itself():
    cand, _, _, _ = _candidate()
    assert cand["publication_authorized"] is False
