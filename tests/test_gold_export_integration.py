import copy
import json
from decimal import Decimal as D
import pytest
from etl.static_export import build
from etl.gold_monthly import build_candidate

def fixture_candidate():
    gold={"2000-01":D("300"),"2000-02":D("320")}
    fx={"2000-01":D("1.2"),"2000-02":D("1.25")}
    rows=build("data/cbs-housing.csv")["data"]
    house={"2000-01":D(str(rows[0]["house_eur"])),"2000-02":D(str(rows[1]["house_eur"]))}
    return build_candidate(gold,fx,house,{"2000-01":20,"2000-02":20})

def test_default_exactly_unchanged(monkeypatch,tmp_path):
    monkeypatch.delenv("GOLD_PUBLICATION_ENABLED",raising=False)
    monkeypatch.delenv("GOLD_PUBLICATION_APPROVAL",raising=False)
    base=build("data/cbs-housing.csv")
    assert base==build("data/cbs-housing.csv",gold_candidate=fixture_candidate(),gold_publication_approved=True)
    assert all(r["gold_eur_oz"] is None and r["gold_index"] is None and r["gold_grams_per_house"] is None for r in base["data"])
    assert base==json.loads(open("frontend/public/data/monthly.json").read())

@pytest.mark.parametrize("enabled,approval",[
    ("TRUE","APPROVED"),("true","approved"),("false","APPROVED"),
    ("true",""),("true","DENIED"),("","APPROVED")
])
def test_bad_configuration_fails_closed(monkeypatch,enabled,approval):
    monkeypatch.setenv("GOLD_PUBLICATION_ENABLED",enabled)
    monkeypatch.setenv("GOLD_PUBLICATION_APPROVAL",approval)
    assert all(r["gold_index"] is None for r in build("data/cbs-housing.csv",gold_candidate=fixture_candidate(),gold_publication_approved=True)["data"])

def test_authorized_values_and_other_fields_unchanged(monkeypatch):
    monkeypatch.setenv("GOLD_PUBLICATION_ENABLED","true")
    monkeypatch.setenv("GOLD_PUBLICATION_APPROVAL","APPROVED")
    before=build("data/cbs-housing.csv")
    after=build("data/cbs-housing.csv",gold_candidate=fixture_candidate(),gold_publication_approved=True)
    assert after["data"][0]["gold_eur_oz"] is None
    assert after["data"][0]["gold_index"]==100
    assert after["data"][1]["gold_eur_oz"] is None
    assert after["data"][1]["gold_index"]==102.4
    assert after["data"][0]["gold_grams_per_house"]==float(D(str(before["data"][0]["house_eur"]))/(D("250")/D("31.1034768")))
    for a,b in zip(after["data"],before["data"]):
        for key in b:
            if key not in ("gold_eur_oz","gold_index","gold_grams_per_house"):
                assert a[key]==b[key]
    assert all(r["gold_index"] is None for r in after["data"][2:])

def test_historical_gap_blocks(monkeypatch):
    monkeypatch.setenv("GOLD_PUBLICATION_ENABLED","true")
    monkeypatch.setenv("GOLD_PUBLICATION_APPROVAL","APPROVED")
    c=fixture_candidate()
    c["coverage"][1]["status"]="missing_historical"
    with pytest.raises(ValueError):
        build("data/cbs-housing.csv",gold_candidate=c,gold_publication_approved=True)

def test_missing_basis_blocks(monkeypatch):
    monkeypatch.setenv("GOLD_PUBLICATION_ENABLED","true")
    monkeypatch.setenv("GOLD_PUBLICATION_APPROVAL","APPROVED")
    c=fixture_candidate()
    c["data"]=c["data"][1:]
    with pytest.raises(ValueError):
        build("data/cbs-housing.csv",gold_candidate=c,gold_publication_approved=True)

def test_modified_price_or_house_blocks(monkeypatch):
    monkeypatch.setenv("GOLD_PUBLICATION_ENABLED","true")
    monkeypatch.setenv("GOLD_PUBLICATION_APPROVAL","APPROVED")
    for field in ("gold_eur_oz","house_eur"):
        c=fixture_candidate()
        c["data"][0][field]="999"
        with pytest.raises(ValueError):
            build("data/cbs-housing.csv",gold_candidate=c,gold_publication_approved=True)

def test_no_candidate_blocks_when_approved(monkeypatch):
    monkeypatch.setenv("GOLD_PUBLICATION_ENABLED","true")
    monkeypatch.setenv("GOLD_PUBLICATION_APPROVAL","APPROVED")
    with pytest.raises(ValueError):
        build("data/cbs-housing.csv",gold_publication_approved=True)
