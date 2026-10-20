"""Synthetic, offline DATA-01C contract tests. No production data imports."""
from copy import deepcopy
import pytest
from tools.data_01_monthly_validator import validate, ObservationError, canonical, digest

H1="a"*64
H2="b"*64
EVIDENCE={H1:{"verified":True,"source_identity_sha256":H1},
          H2:{"verified":True,"source_identity_sha256":H2}}
METHOD={"gold_index":"ADR-004"}
def row(period="2026-08",metric="gold_index",value="100",hashref=H1,
        method="ADR-004",complete="COMPLETE",status="FINAL"):
    return dict(period=period,metric=metric,value=value,
                source_identity_sha256=hashref,methodology_version=method,
                completeness_status=complete,observation_status=status)
def check(old=None,new=None,**kwargs):
    opts=dict(approved_through="2026-08",as_of_period="2026-10",as_of_date_utc="2026-10-19",
              approved_metrics=["gold_index"],methodology_by_metric=METHOD,
              manifest_evidence=EVIDENCE)
    opts.update(kwargs)
    return validate([row()] if old is None else old,
                    [row()] if new is None else new,**opts)
def kinds(report): return [x["classification"] for x in report["classifications"]]
def reasons(report): return [reason for x in report["classifications"] for reason in x["reason_codes"]]

def test_unchanged_and_no_authorization():
    x=check()
    assert kinds(x)==["UNCHANGED"] and x["publication_authorized"] is False

def test_valid_append_and_calendar_february():
    x=check(new=[row(),row("2026-09",value="101")])
    assert kinds(x)==["UNCHANGED","APPEND_CANDIDATE"]
    assert x["validation_status"]=="APPEND_REVIEW"
    y=check(old=[row("2024-01")],new=[row("2024-01"),row("2024-02")],
            approved_through="2024-01",as_of_period="2024-03",as_of_date_utc="2024-03-01")
    assert kinds(y)==["UNCHANGED","APPEND_CANDIDATE"]

@pytest.mark.parametrize("new,expected",[
    ([row(),row("2026-09",complete="INCOMPLETE")],"PENDING"),
    ([row(),row("2026-09",status="PROVISIONAL")],"PENDING"),
    ([row(value="101")],"REVISION_REVIEW"),
    ([row(hashref=H2)],"REVISION_REVIEW"),
    ([row(method="ADR-004-v2")],"BLOCKED"),
    ([row(),row("2026-07")],"LATE_ARRIVAL"),
    ([row(),row("2026-11")],"BLOCKED"),
    ([row("2026-08",metric="hpi")],"BLOCKED"),
    ([], "BLOCKED"),
])
def test_classification(new,expected):
    assert expected in kinds(check(new=new))

def test_source_change_same_value_has_reason():
    x=check(new=[row(hashref=H2)])
    assert "CHANGED_SOURCE_IDENTITY_SHA256" in reasons(x)

def test_missing_manifest_and_unverified_manifest():
    assert "MANIFEST_NOT_PROVIDED" in reasons(check(manifest_evidence=None))
    assert "MANIFEST_NOT_VERIFIED" in reasons(check(manifest_evidence={H1:{"verified":False}}))

@pytest.mark.parametrize("bad",[
    [row(),row()],
    [row(period="2026-13")],
    [row(value="NaN")],
    [row(value=1.0)],
    [row(value="-1")],
    [row(value="1.00")],
    [row(metric="unauthorized_metric")],
    [row(hashref="invalid")],
    [row(method="not valid!")],
])
def test_invalid_observation_fail_closed(bad):
    with pytest.raises(ObservationError):
        check(new=bad)

def test_duplicate_approved():
    with pytest.raises(ObservationError,match="DUPLICATE_APPROVED"):
        check(old=[row(),row()])

def test_historical_gap():
    x=check(old=[row("2026-06"),row("2026-08")],
            new=[row("2026-06"),row("2026-08")])
    assert "UNEXPECTED_HISTORICAL_GAP" in reasons(x)

def test_append_gap():
    x=check(new=[row(),row("2026-10")])
    assert "UNEXPECTED_APPEND_GAP" in reasons(x)

def test_explicit_missing_source_is_not_silently_filled():
    x=check(old=[row("2026-07",value=None,complete="SOURCE_UNAVAILABLE"),row()],
            new=[row("2026-07",value=None,complete="SOURCE_UNAVAILABLE"),row()])
    assert "UNEXPECTED_HISTORICAL_GAP" not in reasons(x)
    assert "UNCHANGED" in kinds(x)

def test_btc_research_only():
    btc=row(metric="btc_eur_research",method="RESEARCH_ONLY")
    x=check(old=[],new=[btc],approved_metrics=["btc_eur_research"],
            methodology_by_metric={"btc_eur_research":"RESEARCH_ONLY"})
    assert x["publication_authorized"] is False
    with pytest.raises(ObservationError,match="BTC_NOT_APPROVED"):
        check(old=[],new=[row(metric="btc_eur_research",method="PRODUCTION")],
              approved_metrics=["btc_eur_research"],
              methodology_by_metric={"btc_eur_research":"RESEARCH_ONLY"})

def test_deterministic_and_read_only():
    old=[row()]
    new=[row(),row("2026-09")]
    a,b=deepcopy(old),deepcopy(new)
    x=check(old=old,new=new)
    assert canonical(x)==canonical(check(old=old,new=new))
    assert digest(x)==digest(check(old=old,new=new))
    assert old==a and new==b
    assert x["publication_authorized"] is False

def test_no_network_fallback(monkeypatch):
    import urllib.request
    monkeypatch.setattr(urllib.request,"urlopen",lambda *args,**kwargs: (_ for _ in ()).throw(AssertionError("network")))
    assert check()["validation_status"]=="NO_CHANGE"

def test_invalid_future_policy_and_boundary():
    with pytest.raises(ObservationError,match="FUTURE_POLICY_NOT_APPROVED"):
        check(permitted_future=True)
    with pytest.raises(ObservationError,match="AS_OF_BEFORE_APPROVED_BOUNDARY"):
        check(as_of_period="2026-07",as_of_date_utc="2026-07-01")

@pytest.mark.parametrize("reference,period,expected",[
    ("2026-10-19","2026-10","PENDING"),
    ("2026-10-19","2026-09","APPEND_CANDIDATE"),
    ("2026-11-01","2026-10","APPEND_CANDIDATE"),
    ("2024-03-01","2024-02","APPEND_CANDIDATE"),
    ("2024-02-29","2024-02","PENDING"),
    ("2023-03-01","2023-02","APPEND_CANDIDATE"),
    ("2023-02-28","2023-02","PENDING"),
    ("2026-10-19","2026-11","BLOCKED"),
])
def test_utc_month_closure(reference,period,expected):
    approved_period="2023-01" if period.startswith("2023") else "2024-01" if period.startswith("2024") else "2026-08"
    old=[row(approved_period)]
    new=old+[row(period)]
    result=check(old=old,new=new,approved_through=approved_period,
                 as_of_period=reference[:7],as_of_date_utc=reference)
    assert expected in kinds(result)
    if expected=="PENDING":
        assert "CALENDAR_MONTH_NOT_CLOSED" in reasons(result)
    assert result["publication_authorized"] is False

@pytest.mark.parametrize("complete,status,expected",[
    ("COMPLETE","FINAL","APPEND_CANDIDATE"),
    ("INCOMPLETE","FINAL","PENDING"),
    ("COMPLETE","PROVISIONAL","PENDING"),
])
def test_source_completeness_independent_of_calendar(complete,status,expected):
    x=check(new=[row(),row("2026-09",complete=complete,status=status)])
    assert expected in kinds(x)

@pytest.mark.parametrize("reference,period,error",[
    ("2026-02-30","2026-02","INVALID_AS_OF_DATE_UTC"),
    ("2026-10-19T00:00:00Z","2026-10","INVALID_AS_OF_DATE_UTC"),
    ("2026-10-19","2026-09","AS_OF_PERIOD_DATE_MISMATCH"),
])
def test_invalid_utc_reference(reference,period,error):
    with pytest.raises(ObservationError,match=error):
        check(as_of_date_utc=reference,as_of_period=period)

def test_only_unchanged_no_change():
    assert check()["validation_status"]=="NO_CHANGE"

def test_empty_valid_comparison_no_change():
    assert check(old=[],new=[])["validation_status"]=="NO_CHANGE"

def test_only_append_review():
    x=check(old=[],new=[row("2026-09")],approved_through="2026-08")
    assert x["validation_status"]=="APPEND_REVIEW"

def test_only_pending():
    x=check(old=[row("2026-09")],new=[row("2026-09"),row("2026-10")],approved_through="2026-09")
    assert x["validation_status"]=="PENDING"

def test_append_plus_pending_priority():
    x=check(new=[row(),row("2026-09"),row("2026-10")])
    assert x["validation_status"]=="PENDING"

def test_append_plus_revision_priority():
    x=check(new=[row(value="101"),row("2026-09")])
    assert x["validation_status"]=="REVIEW_REQUIRED"

def test_append_plus_blocked_priority():
    x=check(new=[row(),row("2026-09"),row("2026-11")])
    assert x["validation_status"]=="BLOCKED"

def test_running_month_does_not_hide_historical_revision():
    x=check(new=[row(value="101"),row("2026-09"),row("2026-10")])
    assert "REVISION_REVIEW" in kinds(x)
    assert x["validation_status"]=="REVIEW_REQUIRED"
