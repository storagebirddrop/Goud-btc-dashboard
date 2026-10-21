import pytest
from tools.gold_03_preflight import verify_and_preview, CANDIDATE_SHA, CBS_SHA, PUBLIC_SHA


def test_gold03_fail_closed_wrong_candidate_hash():
    with pytest.raises(ValueError, match="UNAPPROVED_GOLD_CANDIDATE_SHA"):
        verify_and_preview(b'{"data":[]}', b'{"data":[]}', b"csv")


def test_gold03_unauthorized_baseline(monkeypatch):
    monkeypatch.setattr("tools.gold_03_preflight.sha",
                        lambda raw: CANDIDATE_SHA if raw == b"candidate" else "wrong")
    with pytest.raises(ValueError, match="CBS_BASELINE_REVISION"):
        verify_and_preview(b"candidate", b"public", b"cbs")


def test_gold03_invalid_candidate_after_pins(monkeypatch):
    monkeypatch.setattr("tools.gold_03_preflight.sha",
                        lambda raw: {b"candidate": CANDIDATE_SHA,
                                     b"public": PUBLIC_SHA, b"cbs": CBS_SHA}[raw])
    with pytest.raises(ValueError):
        verify_and_preview(b"candidate", b"public", b"cbs")

def test_gold03_rejects_missing_gold_months_with_pinned_hash(monkeypatch):
    candidate = b'{"data":[]}'
    public = b'{"data": []}'
    cbs = b"baseline"
    def pinned(raw):
        return CANDIDATE_SHA if raw is candidate else PUBLIC_SHA if raw is public else CBS_SHA
    monkeypatch.setattr("tools.gold_03_preflight.sha", pinned)
    with pytest.raises(ValueError, match="UNAPPROVED_MONTH_COVERAGE"):
        verify_and_preview(candidate, public, cbs)


def test_gold03_rejects_unauthorized_cbs_revision(monkeypatch):
    import json
    schema = {"period":"2000-01","house_eur":100.0,"hpi":100.0,
              "hpi_index":100.0,"gold_eur_oz":None,"gold_index":100.0,
              "gold_grams_per_house":1.0}
    before = {"data":[schema for _ in range(320)]}
    after = {"data":[dict(schema,house_eur=200.0) for _ in range(320)]}
    candidate = json.dumps(after).encode()
    public = json.dumps(before).encode()
    cbs = b"baseline"
    def pinned(raw):
        return CANDIDATE_SHA if raw is candidate else PUBLIC_SHA if raw is public else CBS_SHA
    monkeypatch.setattr("tools.gold_03_preflight.sha", pinned)
    with pytest.raises(ValueError, match="UNAUTHORIZED_CBS_OR_RAW_GOLD_CHANGE"):
        verify_and_preview(candidate, public, cbs)
