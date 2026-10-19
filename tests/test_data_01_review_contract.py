import pytest
from tools.data_01_review_contract import inspect, digest, ReviewBlocked

RAW = b"pinned external response"
SHA = digest(RAW)

def row(p, v=100, *, currency="EUR", fx="USD_PER_EUR"):
    return dict(period=p, metric="gold_index", value=v, currency=currency, fx_direction=fx)

def check(old, new, **kwargs):
    args = dict(source_id="approved", approved_source_id="approved",
                raw_bytes=RAW, expected_sha=SHA, complete_through="2026-09")
    args.update(kwargs)
    return inspect(old, new, **args)

def test_valid_append():
    assert check([row("2026-08")], [row("2026-08"), row("2026-09", 101)])["append_count"] == 1

@pytest.mark.parametrize("old,new,extra,code", [
    ([row("2026-08")], [row("2026-08"),row("2026-10")], {}, "INCOMPLETE_OR_FUTURE_MONTH"),
    ([row("2026-07")], [row("2026-07"),row("2026-09")], {}, "MISSING_SOURCE_MONTH"),
    ([], [{"garbage": 1}], {}, "INVALID_PAYLOAD"),
    ([], [row("2026-08"),row("2026-08")], {}, "DUPLICATE_PERIOD_METRIC"),
    ([], [row("2026-08",currency="USD")], {}, "FX_DIRECTION_OR_CURRENCY"),
    ([], [row("2026-08",fx="EUR_PER_USD")], {}, "FX_DIRECTION_OR_CURRENCY"),
    ([row("2026-08")], [row("2026-08", 105)], {}, "HISTORICAL_REVISION_REVIEW_REQUIRED"),
    ([row("2026-08")], [], {}, "MISSING_APPROVED_OBSERVATIONS"),
    ([], [row("2026-08",float("nan"))], {}, "INVALID_VALUE"),
    ([], [row("2026-08")], {"source_id":"other"}, "SOURCE_SWITCH_REQUIRES_APPROVAL"),
    ([], [row("2026-08")], {"expected_sha":"0"*64}, "SOURCE_HASH_MISMATCH"),
    ([], [row("2026-08")], {"publish":True}, "PUBLICATION_NOT_AUTHORIZED"),
])
def test_fail_closed(old,new,extra,code):
    with pytest.raises(ReviewBlocked, match=code):
        check(old,new,**extra)

def test_repeat_is_deterministic_and_does_not_mutate():
    old = [row("2026-08")]
    new = old + [row("2026-09",101)]
    before = repr((old,new))
    assert check(old,new) == check(old,new)
    assert repr((old,new)) == before
