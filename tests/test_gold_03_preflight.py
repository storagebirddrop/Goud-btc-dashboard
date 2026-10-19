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
